from datetime import datetime, date
from typing import Optional, TypeVar, List

from pydantic import BaseModel



# ---------- Pydantic Schema ----------
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    gender: Optional[str]
    dob: Optional[str]
    age: Optional[int]
    maritalStatus: Optional[str]
    education: Optional[str]
    occupation: Optional[str]
    language: Optional[str]
    height: Optional[str]
    diet: Optional[str]
    smoke: Optional[str]
    drink: Optional[str]
    city_name: Optional[str]
    postal: Optional[str]
    state: Optional[str]
    country: Optional[str]
    mobile: Optional[str]
    phonehide: Optional[bool]
    mobilecode: Optional[str]
    partnerExpectations: Optional[str]
    bio: Optional[str]
    status: Optional[str]
    memtype: Optional[str]
    membershipExpiryDate: Optional[str]
    photoProtect: Optional[bool]
    chatcontact: Optional[str]
    devicetoken: Optional[str]
    pagecount: Optional[int]
    onlineUsers: Optional[bool]
    mobileverify: Optional[bool]
    verify_status: Optional[str]
    verify_email: Optional[str]
    video_min: Optional[int]
    voice_min: Optional[int]
    photo1: Optional[str]
    photo1Approve: Optional[bool]
    photo2: Optional[str]
    photo2Approve: Optional[bool]
    chat_msg: Optional[str]
    photohide: Optional[bool]
    lastSeen: Optional[str]

    class Config:
        from_attributes = True

class MetaData(BaseModel):
    total: int
    page: int
    limit: int
    pages: int

T = TypeVar("T")

class ListResponse(BaseModel):
    success: bool
    message: str
    meta: MetaData
    data: List[T]

class PaginatedUsers(BaseModel):
    total: int
    page: int
    limit: int
    users: list[UserResponse]

class AgoraConfigBase(BaseModel):
    app_id: str
    app_certificate: Optional[str] = None
    app_name: Optional[str] = None
    environment: Optional[str] = "prod"
    status: Optional[bool] = True

class AgoraConfigCreate(AgoraConfigBase):
    pass

class AgoraConfigUpdate(BaseModel):
    app_certificate: Optional[str] = None
    app_name: Optional[str] = None
    environment: Optional[str] = None
    status: Optional[bool] = None

class AgoraConfigResponse(AgoraConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MembershipBase(BaseModel):
    membership_name: str
    inr_price: float
    usd_price: float
    video_mins: int
    voice_mins: int
    chat_no: int
    days: int
    status: Optional[str] = "active"
    is_active: Optional[bool] = True


class MembershipCreate(MembershipBase):
    pass


class MembershipUpdate(BaseModel):
    membership_name: Optional[str]
    inr_price: Optional[float]
    usd_price: Optional[float]
    video_mins: Optional[int]
    voice_mins: Optional[int]
    chat_no: Optional[int]
    days: Optional[int]
    status: Optional[str]
    is_active: Optional[bool]


class MembershipOut(MembershipBase):
    id: int

    class Config:
        from_attributes = True
# ---------- API ----------

class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[date] = None
    age: Optional[int] = None
    maritalStatus: Optional[str] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    language: Optional[str] = None
    height: Optional[str] = None
    diet: Optional[str] = None
    smoke: Optional[str] = None
    drink: Optional[str] = None
    city_name: Optional[str] = None
    postal: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    mobile: Optional[str] = None
    phonehide: Optional[bool] = None
    mobilecode: Optional[str] = None
    partnerExpectations: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[str] = None
    memtype: Optional[str] = None
    membershipExpiryDate: Optional[date] = None
    photoProtect: Optional[bool] = None
    chatcontact: Optional[bool] = None
    devicetoken: Optional[str] = None
    pagecount: Optional[int] = None
    onlineUsers: Optional[bool] = None
    mobileverify: Optional[bool] = None
    verify_status: Optional[bool] = None
    verify_email: Optional[bool] = None
    video_min: Optional[int] = None
    voice_min: Optional[int] = None
    photo1: Optional[str] = None
    photo1Approve: Optional[bool] = None
    photo2: Optional[str] = None
    photo2Approve: Optional[bool] = None
    chat_msg: Optional[int] = None
    photohide: Optional[bool] = None