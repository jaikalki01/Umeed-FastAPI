import os
from operator import or_

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, Form, File, Body
from fastapi.security import OAuth2PasswordRequestForm
from firebase_admin import messaging
from pydantic import BaseModel
from sqlalchemy import func, desc, and_, update, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta

from starlette import schemas, status

from app.crud.banner_crud import create_banner1_with_file, get_all_banner1, update_banner1_with_file, \
    create_banner2_with_file, get_all_banner2, update_banner2_with_file
from app.models import models
from app.models.models import User, Payment, BlockedProfile, MatchRequest, SavedProfile, AgoraConfig, MembershipPlan, \
    india_tz, ChatMessage, ProfileView, Notification, UserOTP, Contact, ChatRoom, ChatLog
from app.schemas.admin_schemas import ListResponse, MetaData, AgoraConfigResponse, AgoraConfigCreate, AgoraConfigUpdate, \
    MembershipOut, MembershipCreate, MembershipUpdate, UserUpdateRequest
from app.schemas.banner_schemas import BannerResponse
from app.schemas.user_schemas import PaymentOut, UserPublicResponse  # 👈 adjust if needed
from app.utils.authenticate import get_current_user, set_password, authenticate_user, create_access_token, \
    authenticate_user_admin

from app.utils.database import get_db
# ✅ Pydantic response schema

# ✅ GET users with pagination + optional status filter
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.models.models import User
from app.utils.database import get_db


router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/login")
def login(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
):
    identifier = form_data.username.strip()  # email or mobile
    password = form_data.password.strip()
    get_user = db.query(User).filter(User.email==identifier, User.status=="Admin").first()
    if not get_user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user = authenticate_user_admin(db, identifier, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(data={"sub": user.email})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }


@router.get("/users")
def get_users(
    status: Optional[str] = Query(None, description="Filter by user status"),
    gender: Optional[str] = Query(None, description="Filter by gender"),
    plans: Optional[str] = Query(None, description="Filter by plans"),
    online: Optional[bool] = Query(None, description="Filter by Online"),
    photo1: Optional[bool] = Query(None, description="Filter by Photo1"),
    photo2: Optional[bool] = Query(None, description="Filter by Photo2"),
    expectationsApproved:Optional[bool] = Query(None, description="Filter by Expectation"),
    bioApproved:Optional[bool] = Query(None, description="Filter by Bio"),
    search: Optional[str] = Query(None, description="Search by name, email, mobile, or user ID"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Number of users per page"),
    db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    query = db.query(User)

    # Dynamic filters with match-case
    filters = {
        "status": status,
        "gender": gender,
        "memtype": plans,
        "onlineUsers": online,
        "photo1Approve": photo1,
        "photo2Approve": photo2,
        "bio_approval":bioApproved,
        "partnerExpectations_approval":expectationsApproved
    }

    for field, value in filters.items():
        match value:
            case None:
                pass
            case _:
                query = query.filter(getattr(User, field) == value)

    # Search logic
    if search:
        search_lower = f"%{search.lower()}%"
        match search.isdigit():
            case True:
                query = query.filter(
                    or_(
                        User.id.like(search_lower),
                        User.mobile.like(search_lower)
                    )
                )
            case False:
                query = query.filter(
                    or_(

                        func.lower(User.name).like(search_lower),
                        func.lower(User.email).like(search_lower)
                    )
                )

    #
    allowed_statuses = ["active", "paid", "exclusive"]
    total = query.count()
    active_users=query.filter(func.lower(User.status) == "active").count() or 0
    banned_users = query.filter(User.status=="Banned").count() or 0
    deleted_users = query.filter(User.status=="Deleted").count() or 0
    pending_users = query.filter(func.lower(User.status) == "pending").count() or 0
    exclusive_users =query.filter(func.lower(User.status) == "exclusive").count() or 0
    paid_users=query.filter(func.lower(User.status) == "paid").count() or 0
    photo1_pending_users = query.filter(User.photo1Approve==False,func.lower(User.status).in_(allowed_statuses) ).count() or 0
    photo2_pending_users = query.filter(User.photo2Approve == False, func.lower(User.status).in_(allowed_statuses)).count() or 0
    bio_approval_pending_users = query.filter(User.bio_approval == False, func.lower(User.status).in_(allowed_statuses)).count() or 0
    partnerExpectations_approval_pending_users = query.filter(User.partnerExpectations_approval == False, func.lower(User.status).in_(allowed_statuses)).count() or 0
    #users = query.offset((page - 1) * limit).limit(limit).all()
    users = (
        query.order_by(desc(User.lastSeen))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {
        "success": True,
        "message": "Users fetched successfully",
        "meta": {
            "total": total,
            "page": page,
            "active_users": active_users,
            "banned_users": banned_users,
            "deleted_users": deleted_users,
            "pending_users": pending_users,
            "exclusive_users": exclusive_users,
            "paid_users": paid_users,
            "photo1_pending_users": photo1_pending_users,
            "photo2_pending_users": photo2_pending_users,
            "bio_approval_pending_users": bio_approval_pending_users,
            "partnerExpectations_approval_pending_users": partnerExpectations_approval_pending_users,

            "limit": limit,
            "pages": (total // limit) + (1 if total % limit != 0 else 0),
        },
        "data": users
    }

@router.get("/users/{user_id}", response_model=UserPublicResponse)
def get_profile_by_id(user_id: str, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)
                      ):
    if not current_user.status == "Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")


    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Return ORM object — Pydantic will handle conversion
    return user




# class UpdateUsersRequest(BaseModel):
#     # If provided, operate on these IDs (bulk). Otherwise operate on path user_id.
#     user_ids: Optional[List[str]] = None
#
#     # Fields allowed to change (all optional)
#     photo1Approve: Optional[bool] = None
#     photo2Approve: Optional[bool] = None
#     bioApproved: Optional[bool] = None
#     expectationsApproved: Optional[bool] = None
#     status: Optional[str] = None
#
#
# @router.put("/users/{user_id}")
# def update_user_membership(
#     user_id: str,
#     payload: UpdateUsersRequest = Body(...),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     # Authorization: only Admins allowed
#     if current_user.status != "Admin":
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorised")
#
#     # Determine target IDs: body.user_ids (bulk) or single path user_id
#     target_ids = payload.user_ids if payload.user_ids else [user_id]
#
#     # Validate: ensure at least one field to update was provided
#     if (
#         payload.photo1Approve is None
#         and payload.photo2Approve is None
#         and payload.bioApproved is None
#         and payload.expectationsApproved is None
#         and payload.status is None
#     ):
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update fields provided")
#
#     # Fetch users in one query
#     users = db.query(User).filter(User.id.in_(target_ids)).all()
#     found_ids = {str(u.id) for u in users}
#     failed_ids = [tid for tid in target_ids if tid not in found_ids]
#
#     updated_ids = []
#     # Apply updates
#     for u in users:
#         changed = False
#         if payload.photo1Approve is not None:
#             u.photo1Approve = bool(payload.photo1Approve)
#             changed = True
#         if payload.photo2Approve is not None:
#             u.photo2Approve = bool(payload.photo2Approve)
#             changed = True
#         if payload.bioApproved is not None:
#             # map incoming name to your model field if different
#             u.bio_approval = bool(payload.bioApproved)
#             changed = True
#         if payload.expectationsApproved is not None:
#             u.partnerExpectations_approval = bool(payload.expectationsApproved)
#             changed = True
#         if payload.status is not None:
#             # optional: sanitize/validate allowed status strings here
#             u.status = str(payload.status)
#             changed = True
#
#         if changed:
#             updated_ids.append(str(u.id))
#             db.add(u)
#
#     # Commit once
#     db.commit()
#
#     return {
#         "success": True,
#         "message": "Users updated",
#         "meta": {
#             "requested_ids": target_ids,
#             "updated_count": len(updated_ids),
#             "updated_ids": updated_ids,
#             "failed_ids": failed_ids,
#         },
#     }



# ✅ DELETE user (soft delete: sets status='deleted')
# @router.delete("/users/{user_id}")
# def delete_user(user_id: str, db: Session = Depends(get_db)):
#     user = db.query(User).filter(User.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#
#     db.delete(user)
#     db.commit()
#     return {"message": f"User {user_id} has been permanently deleted."}



# ---- Notification helper -------------------------------------------------
def send_notifications_to_tokens(title: str, body: str, image: Optional[str], tokens: List[str]) -> Dict[str, Any]:
    """
    Send a notification to a list of device tokens.
    Returns a dict with per-token success/failure info and an aggregate summary.
    Uses messaging.send_multicast when possible, otherwise loops.
    """
    tokens = [t for t in tokens if t]  # filter empty/None
    results = {"sent": [], "failed": []}

    if not tokens:
        return {"error": "no_tokens", "results": results}

    # Prefer multicast (more efficient) if many tokens and SDK available
    try:
        # Build Message for multicast (Notification part shared across tokens)
        notification = messaging.Notification(title=title, body=body, image=image) if (title or body or image) else None
        multicast = messaging.MulticastMessage(notification=notification, tokens=tokens)
        response = messaging.send_multicast(multicast)
        # response.responses is list of SendResponse objects matching tokens order
        for tok, resp in zip(tokens, response.responses):
            if resp.success:
                results["sent"].append({"token": tok, "message_id": resp.message_id})
            else:
                results["failed"].append({"token": tok, "error": resp.exception.args if resp.exception else "unknown"})
        results["success_count"] = response.success_count
        results["failure_count"] = response.failure_count
    except Exception:
        # Fall back to single sends if multicast fails for any reason
        for tok in tokens:
            try:
                msg = messaging.Message(
                    notification=messaging.Notification(title=title, body=body, image=image),
                    token=tok,
                )
                mid = messaging.send(msg)
                results["sent"].append({"token": tok, "message_id": mid})
            except Exception as e:
                results["failed"].append({"token": tok, "error": str(e)})
        results["success_count"] = len(results["sent"])
        results["failure_count"] = len(results["failed"])

    return results

# ---- Request model -------------------------------------------------------
class UpdateUsersRequest(BaseModel):
    user_ids: Optional[List[str]] = None
    photo1Approve: Optional[bool] = None
    photo2Approve: Optional[bool] = None
    bioApproved: Optional[bool] = None
    expectationsApproved: Optional[bool] = None
    status: Optional[str] = None

# ---- Endpoint -------------------------------------------------------------
@router.put("/users/{user_id}")
def update_user_membership(
    user_id: str,
    payload: UpdateUsersRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Authorization
    if current_user.status != "Admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorised")

    # Determine target IDs
    target_ids = payload.user_ids if payload.user_ids else [user_id]

    # Validate presence of at least one update field
    if (
        payload.photo1Approve is None
        and payload.photo2Approve is None
        and payload.bioApproved is None
        and payload.expectationsApproved is None
        and payload.status is None
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update fields provided")

    # Fetch users
    users = db.query(User).filter(User.id.in_(target_ids)).all()
    found_ids = {str(u.id) for u in users}
    failed_ids = [tid for tid in target_ids if tid not in found_ids]

    updated_ids = []
    # Track what changed per user so notification can be tailored
    changes_by_user: Dict[str, List[str]] = {}

    for u in users:
        changed = False
        change_descriptions: List[str] = []

        if payload.photo1Approve is not None:
            u.photo1Approve = bool(payload.photo1Approve)
            changed = True
            if payload.photo1Approve:
                change_descriptions.append("🎉 Congratulations! Your 1st Profile Picture has been approved.")
            else:
                change_descriptions.append("⚠️ Sorry! Your 1st Profile Picture was rejected.")

        if payload.photo2Approve is not None:
            u.photo2Approve = bool(payload.photo2Approve)
            changed = True
            if payload.photo2Approve:
                change_descriptions.append("🎉 Congratulations! Your 2nd Profile Picture has been approved.")
            else:
                change_descriptions.append("⚠️ Sorry! Your 2nd Profile Picture was rejected.")

        if payload.bioApproved is not None:
            u.bio_approval = bool(payload.bioApproved)
            changed = True
            if payload.bioApproved:
                change_descriptions.append("🎉 Congratulations! Your Bio has been approved.")
            else:
                change_descriptions.append("⚠️ Sorry! Your Bio was rejected.")

        if payload.expectationsApproved is not None:
            u.partnerExpectations_approval = bool(payload.expectationsApproved)
            changed = True
            if payload.expectationsApproved:
                change_descriptions.append("🎉 Congratulations! Your Partner Expectations have been approved.")
            else:
                change_descriptions.append("⚠️ Sorry! Your Partner Expectations were rejected.")

        if payload.status is not None:
            u.status = str(payload.status)
            changed = True
            change_descriptions.append(f"ℹ️ Your account status has been updated to '{payload.status}'.")

        if changed:
            updated_ids.append(str(u.id))
            changes_by_user[str(u.id)] = change_descriptions
            db.add(u)

    # Commit all changes once
    db.commit()

    # Send notifications to each updated user (if they have devicetoken)
    notifications_report = {}
    for uid in updated_ids:
        user_obj = next((x for x in users if str(x.id) == uid), None)
        if not user_obj:
            notifications_report[uid] = {"error": "user_not_found_after_commit"}
            continue

        # Ensure devicetoken attribute name matches your model
        token = getattr(user_obj, "devicetoken", None)
        if not token:
            notifications_report[uid] = {"error": "no_device_token", "details": "User has no devicetoken"}
            continue

        # Compose message
        changed_items = changes_by_user.get(uid, [])
        if len(changed_items) == 0:
            # nothing to notify
            notifications_report[uid] = {"skipped": "no_changes_detected"}
            continue

        title = "Profile Update"
        # join multiple change descriptions in a readable way
        body = "; ".join(changed_items)

        # If you want a shorter/longer body you can customize here
        send_result = send_notifications_to_tokens(title=title, body=body, image=None, tokens=[token])
        notifications_report[uid] = send_result

    return {
        "success": True,
        "message": "Users updated",
        "meta": {
            "requested_ids": target_ids,
            "updated_count": len(updated_ids),
            "updated_ids": updated_ids,
            "failed_ids": failed_ids,
            "notifications": notifications_report,
        },
    }



@router.get("/users/{user_id}/payments", response_model=List[PaymentOut])
def get_user_payments(user_id: str, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    payments = db.query(Payment).filter(Payment.user_id == user_id).all()
    return payments

# Add this to your router (e.g., admin.py or payment.py)
@router.get("/payments", response_model=List[PaymentOut])
def get_all_payments(db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)
                     ):
    if not current_user.status == "Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")


    payments = db.query(Payment).all()
    return payments









@router.get("/users-filter")
def get_users_filter(
    search: Optional[str] = Query(None, description="Search by name, username, etc."),
    status: Optional[str] = Query(None),
    plan: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    photo1: Optional[str] = Query(None),
    photo2: Optional[str] = Query(None),
    bio: Optional[str] = Query(None),
    expectation: Optional[str] = Query(None),
    db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")


    query = db.query(models.User)

    if search:
        query = query.filter(
            (models.User.username.ilike(f"%{search}%")) |
            (models.User.fullname.ilike(f"%{search}%"))
        )
    if status:
        query = query.filter(models.User.status == status)
    if plan:
        query = query.filter(models.User.plan == plan)
    if gender:
        query = query.filter(models.User.gender == gender)
    if photo1:
        query = query.filter(models.User.photo1 == photo1)
    if photo2:
        query = query.filter(models.User.photo2 == photo2)
    if bio:
        query = query.filter(models.User.bio.ilike(f"%{bio}%"))
    if expectation:
        query = query.filter(models.User.expectation == expectation)

    users = query.all()
    return {"count": len(users), "results": users}



UPLOAD_DIR = "static/uploads/banners"
os.makedirs(UPLOAD_DIR, exist_ok=True)



# Helper: Save file
async def save_file(file: UploadFile):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    return f"/{file_path}"


# -------------------- Banner1 --------------------
@router.post("/banner1/", response_model=BannerResponse)
async def create_banner1(
    banner_name: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")


    banner_url = await save_file(file) if file else None
    return create_banner1_with_file(db, banner_name, banner_url)


@router.get("/banner1/", response_model=list[BannerResponse])
def list_banner1(db: Session = Depends(get_db),


):

    return get_all_banner1(db)


@router.put("/banner1/{banner_id}", response_model=BannerResponse)
async def update_banner1(
    banner_id: int,
    banner_name: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    banner_url = await save_file(file) if file else None
    db_banner = update_banner1_with_file(db, banner_id, banner_name, banner_url)
    if not db_banner:
        raise HTTPException(status_code=404, detail="Banner1 not found")
    return db_banner


@router.delete("/banner1/{banner_id}")
def delete_banner1(banner_id: int, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    db_banner = delete_banner1(banner_id,db )
    if not db_banner:
        raise HTTPException(status_code=404, detail="Banner1 not found")
    return {"status": "success", "message": "Banner1 deleted"}


# -------------------- Banner2 --------------------
@router.post("/banner2/", response_model=BannerResponse)
async def create_banner2(
    banner_name: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    banner_url = await save_file(file) if file else None
    return create_banner2_with_file(db, banner_name, banner_url)


@router.get("/banner2/", response_model=list[BannerResponse])
def list_banner2(db: Session = Depends(get_db)

):

    return get_all_banner2(db)


@router.put("/banner2/{banner_id}", response_model=BannerResponse)
async def update_banner2(
    banner_id: int,
    banner_name: str = Form(...),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    banner_url = await save_file(file) if file else None
    db_banner = update_banner2_with_file(db, banner_id, banner_name, banner_url)
    if not db_banner:
        raise HTTPException(status_code=404, detail="Banner2 not found")
    return db_banner


@router.delete("/banner2/{banner_id}")
def delete_banner2(banner_id: int, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    db_banner = delete_banner2(banner_id,db)
    if not db_banner:
        raise HTTPException(status_code=404, detail="Banner2 not found")
    return {"status": "success", "message": "Banner2 deleted"}

@router.post("/agora_config", response_model=AgoraConfigResponse)
def create_agora_config(data: AgoraConfigCreate, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    existing = db.query(AgoraConfig).filter(AgoraConfig.app_id == data.app_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="App ID already exists")

    config = AgoraConfig(**data.dict())
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


# ✅ List all configs
@router.get("/agora_config", response_model=List[AgoraConfigResponse])
def list_agora_configs(db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    return db.query(AgoraConfig).all()


# ✅ Get single config
@router.get("/agora_config_list/{config_id}", response_model=AgoraConfigResponse)
def get_agora_config(config_id: int, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    config = db.query(AgoraConfig).filter(AgoraConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agora config not found")
    return config


# ✅ Update config
@router.put("/agora_config_upadte/{config_id}", response_model=AgoraConfigResponse)
def update_agora_config(config_id: int, data: AgoraConfigUpdate, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    config = db.query(AgoraConfig).filter(AgoraConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agora config not found")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config


# ✅ Delete config
@router.delete("/agora_config_del/{config_id}")
def delete_agora_config(config_id: int, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    config = db.query(AgoraConfig).filter(AgoraConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Agora config not found")

    db.delete(config)
    db.commit()
    return {"success": True, "message": "Agora config deleted successfully"}


# 🟢 Create
@router.post("/memberships", response_model=MembershipOut)
def create_membership(data: MembershipCreate, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    new_plan = MembershipPlan(**data.dict())
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    return new_plan


# 🟡 List
@router.get("/memberships", response_model=List[MembershipOut])
def list_memberships(skip: int = 0, limit: int = 100, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    return db.query(MembershipPlan).offset(skip).limit(limit).all()


# 🔵 Get One
@router.get("/memberships/{plan_id}", response_model=MembershipOut)
def get_membership(plan_id: int, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    plan = db.query(MembershipPlan).filter(MembershipPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Membership not found")
    return plan


# 🟠 Update
@router.put("/memberships/{plan_id}", response_model=MembershipOut)
def update_membership(plan_id: int, data: MembershipUpdate, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

):
    if not current_user.status == "Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    plan = db.query(MembershipPlan).filter(MembershipPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Membership not found")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(plan, key, value)

    db.commit()
    db.refresh(plan)
    return plan


# 🔴 Delete
@router.delete("/memberships/{plan_id}")
def delete_membership(plan_id: int, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

):
    if not current_user.status == "Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    plan = db.query(MembershipPlan).filter(MembershipPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Membership not found")

    db.delete(plan)
    db.commit()
    return {"message": "Membership deleted"}



def parse_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or value.strip() == "":
        return None
    return value.lower() in ["true", "1", "yes", "on"]


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    return int(value)


def parse_date(value: Optional[str]) -> Optional[date]:
    if value is None or value.strip() == "":
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@router.put("/users_key/{userId}", response_model=UserPublicResponse)
def update_user_key(
    userId: str,
    name: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    dob: Optional[str] = Form(None),  # accept as string
    age: Optional[str] = Form(None),
    maritalStatus: Optional[str] = Form(None),
    education: Optional[str] = Form(None),
    occupation: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    height: Optional[str] = Form(None),
    diet: Optional[str] = Form(None),
    smoke: Optional[str] = Form(None),
    drink: Optional[str] = Form(None),
    city_name: Optional[str] = Form(None),
    postal: Optional[str] = Form(None),
    state: Optional[str] = Form(None),
    country: Optional[str] = Form(None),
    mobile: Optional[str] = Form(None),
    phonehide: Optional[str] = Form(None),
    mobilecode: Optional[str] = Form(None),
    partnerExpectations: Optional[str] = Form(None),
    bio: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    memtype: Optional[str] = Form(None),
    membershipExpiryDate: Optional[str] = Form(None),
    photoProtect: Optional[str] = Form(None),
    chatcontact: Optional[str] = Form(None),
    devicetoken: Optional[str] = Form(None),
    pagecount: Optional[str] = Form(None),
    onlineUsers: Optional[str] = Form(None),
    mobileverify: Optional[str] = Form(None),
    verify_status: Optional[str] = Form(None),
    verify_email: Optional[str] = Form(None),
    video_min: Optional[str] = Form(None),
    voice_min: Optional[str] = Form(None),
    photo1Approve: Optional[str] = Form(None),
    photo2Approve: Optional[str] = Form(None),
    photo1: Optional[str] = Form(None),
    photo2: Optional[str] = Form(None),
    chat_msg: Optional[str] = Form(None),
    photohide: Optional[str] = Form(None),
        bio_approval: Optional[str] = Form(None),
    partnerExpectations_approval: Optional[str] =Form(None),
    db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    user = db.query(User).filter(User.id == userId).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {userId} not found"
        )

    # Convert and clean inputs
    update_data = {
        "name": name,
        "gender": gender,
        "dob": parse_date(dob),
        "age": parse_int(age),
        "maritalStatus": maritalStatus,
        "education": education,
        "occupation": occupation,
        "language": language,
        "height": height,
        "diet": diet,
        "smoke": smoke,
        "drink": drink,
        "city_name": city_name,
        "postal": postal,
        "state": state,
        "country": country,
        "mobile": mobile,
        "phonehide": parse_bool(phonehide),
        "mobilecode": mobilecode,
        "partnerExpectations": partnerExpectations,
        "bio": bio,
        "status": status,
        "memtype": memtype,
        "membershipExpiryDate": parse_date(membershipExpiryDate),
        "photoProtect": parse_bool(photoProtect),
        "chatcontact": parse_bool(chatcontact),
        "devicetoken": devicetoken,
        "pagecount": parse_int(pagecount),
        "onlineUsers": parse_bool(onlineUsers),
        "mobileverify": parse_bool(mobileverify),
        "verify_status": parse_bool(verify_status),
        "verify_email": parse_bool(verify_email),
        "video_min": parse_int(video_min),
        "voice_min": parse_int(voice_min),
        "photo1Approve": parse_bool(photo1Approve),
        "photo2Approve": parse_bool(photo2Approve),
        "photo1": photo1,
        "photo2": photo2,
        "chat_msg": parse_int(chat_msg),
        "photohide": parse_bool(photohide),
        "bio_approval":parse_bool(bio_approval),
        "partnerExpectations_approval":parse_bool(partnerExpectations_approval)
    }

    # Update only non-None values
    for key, value in update_data.items():
        if value is not None:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)

    return user
@router.post("/change-password")
def change_password(userId: str,password:str, db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)
):
    if not current_user.status=="Admin":
        raise HTTPException(status_code=401, detail="Unauthorised")

    # 1. Find user by email
    user = db.query(User).filter(User.id == userId).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")


    # 4. Hash new password and update
    user.password = set_password(password)
    db.commit()
    db.refresh(user)

    return {"message": "Password updated successfully"}


# @router.post("/run_maintenance_tasks")
# def run_maintenance_tasks(
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ) -> dict:
#     """
#     Runs maintenance tasks:
#       1. Delete ChatMessage older than 3 days
#       2. Delete pending MatchRequests older than 15 days
#       3. Activate users with membershipExpiryDate >= today
#     Returns a combined summary dict.
#     """
#     # Authorization
#     if current_user.status != "Admin":
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorised")
#
#     now = datetime.now(india_tz)
#     today = now.date()
#
#     try:
#         # --- 1. Delete chat messages older than 3 days ---
#         chat_cutoff = now - timedelta(days=3)
#         deleted_chats = db.query(ChatMessage).filter(ChatMessage.timestamp < chat_cutoff).delete(synchronize_session=False)
#
#         # --- 2. Delete pending match requests older than 15 days ---
#         mr_cutoff = now - timedelta(days=15)
#         deleted_match_requests = db.query(MatchRequest).filter(
#             and_(
#                 MatchRequest.status == "pending",
#                 MatchRequest.created_at < mr_cutoff
#             )
#         ).delete(synchronize_session=False)
#
#         # --- 3. Update user status to Active if membership valid ---
#
#         premium_to_active_stmt = (
#             update(User)
#             .where(User.membershipExpiryDate != None)
#             .where(User.membershipExpiryDate < today)
#             .where(func.lower(User.status).in_(["paid", "exclusive"]))  # only change premium statuses
#             .values(status="Active")
#         )
#         premium_to_active_result = db.execute(premium_to_active_stmt)
#         premium_to_active_count = premium_to_active_result.rowcount if premium_to_active_result.rowcount is not None else 0
#
#         # Commit all changes once
#         db.commit()
#
#     except Exception as exc:
#         # Rollback on error to keep session clean
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Maintenance job failed: {exc}")
#
#     return {
#         "success": True,
#         "timestamp": now.isoformat(),
#         "tasks": {
#             "chat_messages_deleted": {
#                 "cutoff": chat_cutoff.isoformat(),
#                 "deleted_count": int(deleted_chats or 0),
#             },
#             "pending_match_requests_deleted": {
#                 "cutoff": mr_cutoff.isoformat(),
#                 "deleted_count": int(deleted_match_requests or 0),
#             },
#             "users_activated": {
#                 "since": str(today),
#                 "updated_count": int(premium_to_active_count or 0),
#             },
#         },
#     }

@router.post("/run_maintenance_tasks")
def run_maintenance_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Runs maintenance tasks:
      1. Delete ChatMessage older than 3 days
      2. Delete pending MatchRequests older than 15 days
      3. Activate users with membershipExpiryDate >= today (keeps original logic)
      4. Permanently delete users whose status == 'deleted' (case-insensitive) AND lastSeen older than 30 days
    Returns a combined summary dict.
    """
    # Authorization
    if getattr(current_user, "status", None) != "Admin":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorised")

    now = datetime.now(india_tz)
    today = now.date()

    # Counters to report
    deleted_chats = deleted_match_requests = premium_to_active_count = 0
    users_marked_for_deletion_count = users_permanently_deleted = 0

    try:
        # --- 1. Delete chat messages older than 3 days ---
        chat_cutoff = now - timedelta(days=3)
        deleted_chats = db.query(ChatMessage).filter(ChatMessage.timestamp < chat_cutoff).delete(synchronize_session=False)

        # --- 2. Delete pending match requests older than 15 days ---
        mr_cutoff = now - timedelta(days=15)
        deleted_match_requests = db.query(MatchRequest).filter(
            and_(
                MatchRequest.status == "pending",
                MatchRequest.created_at < mr_cutoff
            )
        ).delete(synchronize_session=False)

        # --- 3. Update user status to Active if membership valid ---
        # (kept your original where clause logic — it updates certain premium statuses)
        premium_to_active_stmt = (
            update(User)
            .where(User.membershipExpiryDate != None)
            .where(User.membershipExpiryDate < today)
            .where(func.lower(User.status).in_(["paid", "exclusive"]))  # only change premium statuses
            .values(status="Active")
        )
        premium_to_active_result = db.execute(premium_to_active_stmt)
        premium_to_active_count = premium_to_active_result.rowcount or 0

        # --- 4. Permanently delete users with status 'deleted' and lastSeen older than 30 days ---
        delete_cutoff = now - timedelta(days=30)

        # find user ids matching the criteria (case-insensitive status)
        users_to_delete_q = db.query(User.id).filter(
            and_(
                func.lower(User.status) == "deleted",
                User.lastSeen != None,
                User.lastSeen < delete_cutoff
            )
        )
        users_to_delete_rows = users_to_delete_q.all()
        user_ids: List[str] = [r[0] for r in users_to_delete_rows] if users_to_delete_rows else []
        users_marked_for_deletion_count = len(user_ids)

        if user_ids:
            # 4.a Delete chat_logs rows referencing these users (no ON DELETE CASCADE)
            # Use ORM ChatLog if available; else raw SQL fallback.
            if "ChatLog" in globals() and ChatLog is not None:
                db.query(ChatLog).filter(
                    or_(ChatLog.sender_id.in_(user_ids), ChatLog.receiver_id.in_(user_ids))
                ).delete(synchronize_session=False)
            else:
                # raw SQL fallback
                db.execute(
                    text("DELETE FROM chat_logs WHERE sender_id IN :uids OR receiver_id IN :uids"),
                    {"uids": tuple(user_ids)}
                )

            # 4.b Delete chat_messages (should have ON DELETE CASCADE per your models, but delete explicitly for safety)
            if "ChatMessage" in globals() and ChatMessage is not None:
                db.query(ChatMessage).filter(
                    or_(ChatMessage.sender_id.in_(user_ids), ChatMessage.receiver_id.in_(user_ids))
                ).delete(synchronize_session=False)

            # 4.c Delete chat_rooms referencing these users
            if "ChatRoom" in globals() and ChatRoom is not None:
                db.query(ChatRoom).filter(
                    or_(ChatRoom.user1_id.in_(user_ids), ChatRoom.user2_id.in_(user_ids))
                ).delete(synchronize_session=False)

            # 4.d Delete saved_profiles where either side matches
            if "SavedProfile" in globals() and SavedProfile is not None:
                db.query(SavedProfile).filter(
                    or_(SavedProfile.user_id.in_(user_ids), SavedProfile.saved_user_id.in_(user_ids))
                ).delete(synchronize_session=False)

            # 4.e MatchRequest
            if "MatchRequest" in globals() and MatchRequest is not None:
                db.query(MatchRequest).filter(
                    or_(MatchRequest.sender_id.in_(user_ids), MatchRequest.receiver_id.in_(user_ids))
                ).delete(synchronize_session=False)

            # 4.f BlockedProfile
            if "BlockedProfile" in globals() and BlockedProfile is not None:
                db.query(BlockedProfile).filter(
                    or_(BlockedProfile.blocker_id.in_(user_ids), BlockedProfile.blocked_user_id.in_(user_ids))
                ).delete(synchronize_session=False)

            # 4.g ProfileView
            if "ProfileView" in globals() and ProfileView is not None:
                db.query(ProfileView).filter(
                    or_(ProfileView.user_id.in_(user_ids), ProfileView.viewed_by_id.in_(user_ids))
                ).delete(synchronize_session=False)

            # 4.h Notification
            if "Notification" in globals() and Notification is not None:
                db.query(Notification).filter(
                    or_(Notification.sender_id.in_(user_ids), Notification.receiver_id.in_(user_ids))
                ).delete(synchronize_session=False)

            # 4.i UserOTP (one-to-one)
            if "UserOTP" in globals() and UserOTP is not None:
                db.query(UserOTP).filter(UserOTP.user_id.in_(user_ids)).delete(synchronize_session=False)

            # 4.j Payment & Contact
            if "Payment" in globals() and Payment is not None:
                db.query(Payment).filter(Payment.user_id.in_(user_ids)).delete(synchronize_session=False)
            if "Contact" in globals() and Contact is not None:
                db.query(Contact).filter(Contact.user_id.in_(user_ids)).delete(synchronize_session=False)

            # After deleting dependents, delete the users themselves
            users_permanently_deleted = db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)

        # Commit all changes once
        db.commit()

    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Maintenance job failed: {exc}")

    return {
        "success": True,
        "timestamp": now.isoformat(),
        "tasks": {
            "chat_messages_deleted": {
                "cutoff": chat_cutoff.isoformat(),
                "deleted_count": int(deleted_chats or 0),
            },
            "pending_match_requests_deleted": {
                "cutoff": mr_cutoff.isoformat(),
                "deleted_count": int(deleted_match_requests or 0),
            },
            "users_activated": {
                "since": str(today),
                "updated_count": int(premium_to_active_count or 0),
            },
            "users_marked_for_permanent_deletion": {
                "lastseen_cutoff": delete_cutoff.isoformat(),
                "matched_count": int(users_marked_for_deletion_count or 0),
                "permanently_deleted": int(users_permanently_deleted or 0),
            },
        },
    }


def _serialize_model(instance) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for col in instance.__table__.columns:
        val = getattr(instance, col.name)
        if isinstance(val, (datetime, date)):
            data[col.name] = val.isoformat() if val is not None else None
        else:
            data[col.name] = val
    return data


@router.delete("/deleteUser", status_code=status.HTTP_200_OK)
def delete_user(
    userId: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a user and all dependent data. This handles chat_logs explicitly
    (their FKs lack ON DELETE CASCADE) and deletes other dependent tables too.
    IMPORTANT: protect this endpoint with admin-only access in production.
    """

    # Authorization example: uncomment & adapt
    # if getattr(current_user, "status", "").lower() != "admin":
    #     raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    user = db.query(User).filter(User.id == userId).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    deleted_record = _serialize_model(user)

    try:
        # 1) Remove rows from chat_logs (table that caused the FK error).
        # Prefer ORM if ChatLog model exists; otherwise use raw SQL. We delete both sender and receiver references.
        if "ChatLog" in globals() and ChatLog is not None:
            db.query(ChatLog).filter(
                (ChatLog.sender_id == userId) | (ChatLog.receiver_id == userId)
            ).delete(synchronize_session=False)
        else:
            # raw SQL fallback:
            db.execute(text("DELETE FROM chat_logs WHERE sender_id = :uid OR receiver_id = :uid"), {"uid": userId})

        # 2) Remove chat_messages (if any) - these have ondelete CASCADE in your model but we include for safety.
        if "ChatMessage" in globals() and ChatMessage is not None:
            db.query(ChatMessage).filter(
                (ChatMessage.sender_id == userId) | (ChatMessage.receiver_id == userId)
            ).delete(synchronize_session=False)

        # 3) Remove chat_rooms referencing this user (if any)
        if "ChatRoom" in globals() and ChatRoom is not None:
            db.query(ChatRoom).filter(
                (ChatRoom.user1_id == userId) | (ChatRoom.user2_id == userId)
            ).delete(synchronize_session=False)

        # 4) Saved profiles, match requests, blocked profiles, profile views, notifications, OTPs, payments, contacts
        if "SavedProfile" in globals() and SavedProfile is not None:
            db.query(SavedProfile).filter(
                (SavedProfile.user_id == userId) | (SavedProfile.saved_user_id == userId)
            ).delete(synchronize_session=False)

        if "MatchRequest" in globals() and MatchRequest is not None:
            db.query(MatchRequest).filter(
                (MatchRequest.sender_id == userId) | (MatchRequest.receiver_id == userId)
            ).delete(synchronize_session=False)

        if "BlockedProfile" in globals() and BlockedProfile is not None:
            db.query(BlockedProfile).filter(
                (BlockedProfile.blocker_id == userId) | (BlockedProfile.blocked_user_id == userId)
            ).delete(synchronize_session=False)

        if "ProfileView" in globals() and ProfileView is not None:
            db.query(ProfileView).filter(
                (ProfileView.user_id == userId) | (ProfileView.viewed_by_id == userId)
            ).delete(synchronize_session=False)

        if "Notification" in globals() and Notification is not None:
            db.query(Notification).filter(
                (Notification.sender_id == userId) | (Notification.receiver_id == userId)
            ).delete(synchronize_session=False)

        if "UserOTP" in globals() and UserOTP is not None:
            db.query(UserOTP).filter(UserOTP.user_id == userId).delete(synchronize_session=False)

        if "Payment" in globals() and Payment is not None:
            db.query(Payment).filter(Payment.user_id == userId).delete(synchronize_session=False)

        if "Contact" in globals() and Contact is not None:
            db.query(Contact).filter(Contact.user_id == userId).delete(synchronize_session=False)

        # 5) Finally delete the user row
        db.delete(user)
        db.commit()

        return {"success": True, "message": "User and dependent data deleted", "deleted_user": deleted_record}

    except IntegrityError as ie:
        db.rollback()
        # If this happens, there's still some FK referencing users.id we missed.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integrity error: {str(ie.orig) if getattr(ie, 'orig', None) else str(ie)}"
        )

    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {str(e)}")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {str(e)}")