from enum import Enum

from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional, List, Union
from datetime import datetime, date

class UserPublicResponseSelf(BaseModel):
    id: str
    email: str
    name: Optional[str]
    gender: Optional[str]
    dob: Optional[date]
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
    phonehide: Optional[bool] = Field(True, description="Hide phone number from public")
    mobilecode: Optional[str]
    partnerExpectations: Optional[str]
    partnerExpectations_approval: Optional[bool]
    bio: Optional[str]
    bio_approval: Optional[bool]
    status: Optional[str]
    memtype: Optional[str]
    membershipExpiryDate: Optional[date]
    photoProtect: Optional[bool]
    chatcontact: Optional[bool]
    devicetoken: Optional[str]
    pagecount: Optional[int]
    onlineUsers: Optional[bool]
    mobileverify: Optional[bool]
    verify_status: Optional[bool]
    verify_email: Optional[bool]
    video_min: Optional[int]
    voice_min: Optional[int]
    photo1: Optional[str]
    photo1Approve: Optional[bool]
    photo2: Optional[str]
    photo2Approve: Optional[bool]
    chat_msg: Optional[int]
    photohide: Optional[bool]
    lastSeen: Optional[datetime]

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class UserPublicResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    gender: Optional[str]
    dob: Optional[date]
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
    partnerExpectations_approval: Optional[bool]
    bio: Optional[str]
    bio_approval: Optional[bool]
    status: Optional[str]
    memtype: Optional[str]
    membershipExpiryDate: Optional[date]
    photoProtect: Optional[bool]
    chatcontact: Optional[bool]
    devicetoken: Optional[str]
    pagecount: Optional[int]
    onlineUsers: Optional[bool]
    mobileverify: Optional[bool]
    verify_status: Optional[bool]
    verify_email: Optional[bool]
    video_min: Optional[int]
    voice_min: Optional[int]
    photo1: Optional[str]
    photo1Approve: Optional[bool]
    photo2: Optional[str]
    photo2Approve: Optional[bool]
    chat_msg: Optional[int]
    photohide: Optional[bool]
    lastSeen: Optional[datetime]
    isMatched: Optional[bool] = False
    match_status: str = "none"  # one of: 'none', 'pending', 'accepted'
    isBlocked: Optional[bool] = False
    isSaved: Optional[bool] = False
    isBlockedBySelf: Optional[bool] = False
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class BlockUserPayload(BaseModel):
    user_id: str
    reason: Optional[str] = None

class RequestPayload(BaseModel):
    user_id: str  # This is the receiver_id

class MatchRequestResponsePayload(BaseModel):
    user_id: str
    status: str  # expected values: "accepted" or "rejected"

class MatchRequestResponse(BaseModel):
    id: int
    fromUserId: str
    toUserId: str
    status: str
    createdAt: datetime

    class Config:
        from_attributes = True  # Enable ORM to Pydantic model conversion



class PaginatedMatchRequests(BaseModel):
    total: int
    page: int
    limit: int
    hasNext: bool
    results: List[MatchRequestResponse]

class NotificationStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    view = "view"
    rejected = "rejected"
    msg = "msg"

class NotificationCreate(BaseModel):
    receiver_id: str
    status: NotificationStatus
    message: str = ""

class NotificationOut(BaseModel):
    id: int
    sender_id: Union[UserPublicResponse, None]  # or list if needed
    receiver_id: str
    status: NotificationStatus
    message: Optional[str] = ""
    is_read: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class NotificationRequest(BaseModel):
    title: str
    body: str
    image: str = None  # Optional
    token: str      # Device FCM token


class PaymentOut(BaseModel):
    id: int
    user_id: str
    mobile_no: Optional[str]
    email_id: Optional[str]
    currency: Optional[str]
    amount: Optional[float]
    order_id: Optional[str]
    payment_id: Optional[str]
    status: Optional[str]
    date: Optional[date]

    class Config:
        from_attributes = True

class ProfilesResponse(BaseModel):
    total: int
    offset: int
    limit: int
    users: List[UserPublicResponse]
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)