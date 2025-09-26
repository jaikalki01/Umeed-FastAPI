from datetime import timedelta, datetime
import random, requests
from fastapi import APIRouter, HTTPException, Depends, Request, Body
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER
from starlette.middleware.sessions import SessionMiddleware

from app.models.models import User, UserOTP, india_tz
from app.schemas.authentication import UserLogin, Token, UserResponse, MobileOTPLogin
from app.utils.database import get_db
from app.utils.authenticate import (
    create_access_token,
    authenticate_user,
    get_current_user,
    check_user_role, ACCESS_TOKEN_EXPIRE_MINUTES, get_user,
)

router = APIRouter()

@router.post("/login")
def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    identifier = form_data.username.strip()  # email or mobile
    password = form_data.password.strip()
    user = authenticate_user(db, identifier, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(data={"sub": user.email})
    #find_user.onlineUsers ==True
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }






otp_store = {}
def send_otp_sms(mobile: str, otp: str) -> bool:
    if mobile.startswith("91"):
        url = "http://sms.messageindia.in/v2/sendSMS"
        payload = {
            "username": "sameerji",
            "message":  f"Your UUMEED OTP is {otp}, valid for 2 minutes. Do not share it. umeed.app", #f"Your OTP for mobile application jyotishionline login is {otp} jyotishi online",
            "sendername": "UUMEED",
            "smstype": "TRANS",
            "numbers": mobile,
            "apikey": "242d4043-4734-4ae8-acb6-bcbb5b855bcc",
            "peid": "1701175032658751812",
            "templateid": "1707175679144355660" #"1707175048832142304"
        }
    else:
        url = "http://148.251.129.118/wapp/api/send"
        payload = {
            "apikey": "c26b5da4b3e9485cbf3413df31080450",
            "mobile": mobile,
            "msg": f"Your OTP for mobile application Umeed App is {otp} Umeed App"
        }

    response = requests.get(url, params=payload)
    return response.status_code == 200

"""@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user.email})

    user_response = user
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }"""

"""@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    identifier = form_data.username.strip()
    password_or_otp = form_data.password.strip()

    user = db.query(User).filter(
        (User.email == identifier) | (User.mobile == identifier)
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    mobile_clean = user.mobile.replace("+", "")

    # Case 1: Only mobile number is submitted → Generate and send OTP
    if mobile_clean == identifier and not password_or_otp:
        otp = str(random.randint(100000, 999999))
        otp_store[user.id] = otp  # Store OTP temporarily
        success = send_otp_sms(mobile_clean, otp)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send OTP")
        return {"message": "OTP sent to your mobile number", "user_id": user.id}

    # Case 2: Mobile + OTP
    if mobile_clean == identifier and password_or_otp.isdigit():
        stored_otp = otp_store.get(user.id)
        if stored_otp != password_or_otp:
            raise HTTPException(status_code=401, detail="Invalid or expired OTP")

        # Optional: Remove OTP after successful use
        del otp_store[user.id]

        access_token = create_access_token(data={"sub": user.email})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user.email})

    user_response = user
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_response
    }
    # Case 3: Email + Password"""

@router.post("/login-otp")
async def login_otp(
    payload: MobileOTPLogin,
    db: Session = Depends(get_db)
):
    """
    Mobile OTP Login.

    Case 1: country_code + mobile → Send OTP
    Case 2: country_code + mobile + otp → Verify OTP

    Content-Type: application/json
    """

    country_code = payload.country_code.strip()
    mobile = payload.mobile.strip()
    otp = payload.otp
    full_mobile = country_code + mobile

    # Fix: match with full_mobile
    user = db.query(User).filter(User.mobile == mobile).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check user status
    match user.status:
        case "Banned":
            raise HTTPException(status_code=403, detail="User account is banned")
        case "Deleted":
            raise HTTPException(status_code=403, detail="User account is deleted or deactivated")
        case _:
            pass

    # Handle OTP logic
    match otp:
        # ✅ Case 1: Send OTP
        case None:
            gen_otp = str(random.randint(100000, 999999))
            db.query(UserOTP).filter_by(user_id=user.id).delete()
            db.commit()
            db.add(UserOTP(user_id=user.id, otp=gen_otp, created_at=datetime.now()))
            db.commit()
            sent = send_otp_sms(full_mobile, gen_otp)
            if not sent:
                raise HTTPException(status_code=500, detail="Failed to send OTP")
            return {"message": "OTP sent", "user_id": user.id}

        # ✅ Case 2: Verify OTP
        case o if o.isdigit():
            otp_entry = db.query(UserOTP).filter_by(user_id=user.id, otp=o).first()
            if not otp_entry:
                raise HTTPException(status_code=401, detail="Invalid OTP")

            # Safely compare datetime
            try:
                created_at = otp_entry.created_at.replace(tzinfo=india_tz)
            except Exception:
                created_at = otp_entry.created_at  # fallback if already aware

            if datetime.now(india_tz) - created_at > timedelta(minutes=30):
                db.delete(otp_entry)
                db.commit()
                raise HTTPException(status_code=401, detail="OTP expired")
            user.mobileverify=True
            user.verify_status = True
            user.onlineUsers =True
            db.commit()
            db.delete(otp_entry)
            db.commit()
            db.refresh(user)
            token = create_access_token(data={"sub": user.email})
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": user
            }

        # ❌ Invalid OTP format
        case _:
            raise HTTPException(status_code=400, detail="Invalid OTP format")





class MobileOTPRequest(BaseModel):
    country_code: str
    mobile: str


@router.post("/send-mobile-otp")
def send_mobile_otp(payload: MobileOTPRequest, db: Session = Depends(get_db)):
    full_mobile = payload.country_code.strip() + payload.mobile.strip()

    user = db.query(User).filter(
        User.mobile == payload.mobile.strip(),
        #User.mobilecode == payload.country_code.strip()
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.mobileverify is True:
        raise HTTPException(status_code=401, detail="Mobile already verified")
        #return {"message": "Mobile already verified"}

    otp = str(random.randint(100000, 999999))

    # Clear previous OTPs
    db.query(UserOTP).filter(UserOTP.user_id == user.id).delete()
    db.commit()

    # Save new OTP
    otp_entry = UserOTP(user_id=user.id, otp=otp, created_at=datetime.now())
    db.add(otp_entry)
    db.commit()

    # Send OTP (mocked with SMS/WhatsApp)
    sent = send_otp_sms(full_mobile, otp) #if payload.country_code == "91" else send_otp_whatsapp(full_mobile, otp)

    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send OTP")

    return {"message": "OTP sent successfully"}



class VerifyMobileOTPRequest(BaseModel):
    country_code: str
    mobile: str
    otp: str


@router.post("/verify-mobile-otp")
def verify_mobile_otp(payload: VerifyMobileOTPRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.mobile == payload.mobile.strip(),
        #User.mobilecode == payload.country_code.strip()
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 🚨 New: If already verified, skip OTP validation
    if user.mobileverify:
        token = create_access_token(data={"sub": user.email})
        return {
            "message": "Mobile number is already verified.",
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "mobile": user.mobile,
                "mobileverify": user.mobileverify
            }
        }

    # Proceed to check OTP
    otp_entry = db.query(UserOTP).filter_by(user_id=user.id, otp=payload.otp).first()
    if not otp_entry:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    try:
        created_at = otp_entry.created_at.replace(tzinfo=india_tz)
    except Exception:
        created_at = otp_entry.created_at

    if datetime.now(india_tz) - created_at > timedelta(minutes=30):
        db.delete(otp_entry)
        db.commit()
        raise HTTPException(status_code=401, detail="OTP expired")

    db.delete(otp_entry)
    user.mobileverify = True
    user.verify_status=True
    db.commit()

    token = create_access_token(data={"sub": user.email})

    return {
        "message": "OTP verified successfully",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "mobile": user.mobile,
            "mobileverify": user.mobileverify
        }
    }

