import hashlib
import random
import re
from datetime import datetime, timedelta



from jose import JWTError, jwt
from fastapi import HTTPException, Depends, WebSocket, requests
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette import status
from starlette.responses import RedirectResponse
# ✅ Get Current User from Token
from jose import JWTError, ExpiredSignatureError
from app.models.models import User
from app.schemas.user_schemas import UserPublicResponse, UserPublicResponseSelf
#from app.crud.authenticate import get_user
from app.utils.database import get_db

from pathlib import Path

from fastapi import UploadFile, Request
from passlib.context import CryptContext

# Set up password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

import pytz

# Set India time zone (IST)
india_tz = pytz.timezone('Asia/Kolkata')

# ✅ JWT Config
SECRET_KEY = "youggigigi867564secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200  # 30 days


# ✅ OAuth2 Password Bearer (For Token Auth)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def set_password(password: str) -> str:
    return hashlib.md5(password.encode()).hexdigest()
    #self.ConfirmPassword = md5_hash

    # Function to check if the provided password matches the hashed password in the User model


def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def check_password(plain_password: str, hashed_password: str) -> bool:
    return hashlib.md5(plain_password.encode()).hexdigest() == hashed_password


# ✅ Verify password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Check if it's bcrypt (passlib can handle this)
    if hashed_password.startswith("$2a$") or hashed_password.startswith("$2b$"):
        return pwd_context.verify(plain_password, hashed_password)
    else:
        # Fallback to MD5 for legacy passwords
        return hashlib.md5(plain_password.encode()).hexdigest() == hashed_password



# ✅ Generate JWT Token
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    #print(f"Token payload: {to_encode}")  # ✅ Check the payload before encoding
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ✅ Authenticate User with Username and Password
# utils/authenticate.py

def get_user(db: Session, identifier: str):
    return db.query(User).filter(
        or_(
            User.email == identifier,
            User.mobile == identifier,


        )
    ).first()




def authenticate_user(db: Session, identifier: str, password: str):
    user = get_user(db, identifier.strip())

    if not user:
        # print("❌ User not found")
        return None
    # if not user.mobileverify == True:
    #     raise HTTPException(status_code=401, detail="Mobile number not verified; please login via Mobile OTP")


    if not verify_password(password, user.password):
        # print("❌ Incorrect password")
        return None

    if not user.status or user.status.lower() not in {"active", "paid", "exclusive"}:
        # print(f"❌ Invalid user status: {user.status}")
        return None


    user.onlineUsers =True
    db.commit()
    db.refresh(user)

    return UserPublicResponseSelf(
        **user.__dict__,

    )


    #return user

def authenticate_user_admin(db: Session, identifier: str, password: str):
    user = get_user(db, identifier.strip())

    if not user:
        # print("❌ User not found")
        return None
    # if not user.mobileverify == True:
    #     raise HTTPException(status_code=401, detail="Mobile number not verified; please login via Mobile OTP")


    if not verify_password(password, user.password):
        # print("❌ Incorrect password")
        return None

    if not user.status or user.status.lower() not in {'admin', 'Admin'}:
        # print(f"❌ Invalid user status: {user.status}")
        return None



    return UserPublicResponseSelf(
        **user.__dict__,

    )


    #return user







def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise credentials_exception

    user = get_user(db, username)  # ✅ FIXED
    if user is None:
        raise credentials_exception

    return user



# ✅ Check Role Permission (Admin, Seller, User)
def check_user_role(required_role: int):
    def role_checker(user: User = Depends(get_current_user)):
        if user.role != required_role:
            raise HTTPException(status_code=403, detail="Access denied. Insufficient permissions")
        return user
    return role_checker

async def get_current_user_ws(websocket: WebSocket, db: Session = Depends(get_db)) -> User:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            await websocket.close(code=1008)
            return

        user = get_user(db, email)  # ✅ FIXED
        if user is None:
            await websocket.close(code=1008)
            return

        return user

    except ExpiredSignatureError:
        await websocket.close(code=4003)
    except JWTError:
        await websocket.close(code=1008)



otp_store = {}


def generate_otp():
    return str(random.randint(100000, 999999))

import requests  # ✅ Correct import

def send_otp(mobilecode: str, mobile: str, otp: str) -> bool:
    full_mobile = f"{mobilecode}{mobile}"

    if mobilecode == "91":
        # Send SMS for Indian numbers
        url = "http://sms.messageindia.in/v2/sendSMS"
        payload = {
            "username": "sameerji",
            "message": f"Your UUMEED OTP is {otp}, valid for 2 minutes. Do not share it. umeed.app",
            # f"Your OTP for mobile application jyotishionline login is {otp} jyotishi online",
            "sendername": "UUMEED",
            "smstype": "TRANS",
            "numbers": full_mobile,
            "apikey": "242d4043-4734-4ae8-acb6-bcbb5b855bcc",
            "peid": "1701175032658751812",
            "templateid": "1707175679144355660"  # "1707175048832142304"
        }
        response = requests.get(url, params=payload)
    else:
        # Send WhatsApp for non-Indian numbers
        url = "http://148.251.129.118/wapp/api/send"
        payload = {
            "apikey": "c26b5da4b3e9485cbf3413df31080450",
            "mobile": full_mobile,
            "msg": f"Your OTP for mobile application Umeed App is {otp} Umeed App"
        }
        response = requests.get(url, params=payload)

    return response.status_code == 200


