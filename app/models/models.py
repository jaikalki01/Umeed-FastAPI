import random
import string
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import (
    Column, Integer, String, Float, ForeignKey, Boolean, DateTime,  Text, Date, func
)
from enum import Enum as PyEnum
from sqlalchemy.orm import relationship, declarative_base, backref
from datetime import datetime
import pytz
from sqlalchemy.types import Enum as SQLEnum
# Set India time zone (IST)
india_tz = pytz.timezone('Asia/Kolkata')

Base = declarative_base()
user_token = str(uuid4())
ROLE_MAPPING = {
    'user': 1,
    'admin': 3,
    'seller': 2
}

class User(Base):
    __tablename__ = "users"

    id = Column(String(10), primary_key=True, index=True)  # e.g., 'UD1'
    email = Column(String(100), unique=True, nullable=False)
    password= Column(String(255))
    name = Column(String(100))
    gender = Column(String(50))
    dob = Column(Date)
    age = Column(Integer)
    maritalStatus = Column(String(50))
    education = Column(String(100))
    occupation = Column(String(100))
    language = Column(String(255))
    height = Column(String(10))
    diet = Column(String(50))
    smoke = Column(String(50))
    drink = Column(String(50))
    city_name = Column(String(100))
    postal = Column(Text)
    state = Column(String(100))
    country = Column(String(100))
    mobile = Column(String(20))
    phonehide = Column(Boolean, default=True, nullable=True)
    mobilecode = Column(String(10))
    partnerExpectations = Column(Text)
    partnerExpectations_approval = Column(Boolean, default=False)
    bio = Column(Text)
    bio_approval = Column(Boolean, default=False)
    status = Column(String(20))
    memtype = Column(String(20))
    membershipExpiryDate = Column(Date)
    photoProtect = Column(Boolean, default=False)
    chatcontact = Column(Boolean, default=True)
    devicetoken = Column(String(255))
    pagecount = Column(Integer, default=0)
    onlineUsers = Column(Boolean)
    mobileverify = Column(Boolean, default=False)
    verify_status = Column(Boolean, default=False)
    verify_email = Column(Boolean, default=False)
    video_min = Column(Integer, default=0)
    voice_min = Column(Integer, default=0)
    photo1 = Column(String(500))
    photo1Approve = Column(Boolean, default=False)
    photo2 = Column(String(500))
    photo2Approve = Column(Boolean, default=False)
    chat_msg = Column(Integer, default=0)
    photohide = Column(Boolean, default=False)
    lastSeen = Column(DateTime, default=lambda: datetime.now(india_tz))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_signup_complete = Column(Boolean, default=False, nullable=False)
    # optionally track when completed:
    signup_completed_at = Column(DateTime, nullable=True)
    # Relationships
    #saved_profiles = relationship("SavedProfile", back_populates="user")
    saved_profiles = relationship(
        "SavedProfile",
        foreign_keys="[SavedProfile.user_id]",
        back_populates="user",
        cascade="all, delete",
        passive_deletes=True
    )
    sent_requests = relationship(
        "MatchRequest",
        foreign_keys="[MatchRequest.sender_id]",
        back_populates="sender",
        cascade="all, delete",
        passive_deletes=True
    )
    received_requests = relationship(
        "MatchRequest",
        foreign_keys="[MatchRequest.receiver_id]",
        back_populates="receiver",
        cascade="all, delete",
        passive_deletes=True
    )
    blocked_profiles = relationship(
        "BlockedProfile",
        foreign_keys="[BlockedProfile.blocker_id]",
        back_populates="blocker",
        cascade="all, delete",
        passive_deletes=True
    )

    chats_sent = relationship(
        "ChatMessage", foreign_keys="[ChatMessage.sender_id]",
        back_populates="sender", cascade="all, delete", passive_deletes=True
    )
    chats_received = relationship(
        "ChatMessage", foreign_keys="[ChatMessage.receiver_id]",
        back_populates="receiver", cascade="all, delete", passive_deletes=True
    )


    views_received = relationship(
        "ProfileView",
        foreign_keys="[ProfileView.user_id]",
        back_populates="receiver",
        cascade="all, delete",
        passive_deletes=True
    )

    views_made = relationship(
        "ProfileView",
        foreign_keys="[ProfileView.viewed_by_id]",
        back_populates="viewer",
        cascade="all, delete",
        passive_deletes=True
    )

    sent_notify = relationship(
        "Notification",
        foreign_keys="[Notification.sender_id]",
        back_populates="sender",
        cascade="all, delete",
        passive_deletes=True
    )
    received_notify = relationship(
        "Notification",
        foreign_keys="[Notification.receiver_id]",
        back_populates="receiver",
        cascade="all, delete",
        passive_deletes=True
    )
    # in User model
    otp = relationship("UserOTP", uselist=False, back_populates="user")
    payment = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    contact = relationship("Contact", back_populates="user", cascade="all, delete-orphan")

class UserOTP(Base):
    __tablename__ = "user_otps"

    #id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(10), ForeignKey("users.id"),primary_key=True, unique=True)
    otp = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(india_tz))

    user = relationship("User", back_populates="otp")

class SavedProfile(Base):
    __tablename__ = "saved_profiles"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    saved_user_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))

    user = relationship("User", foreign_keys=[user_id], back_populates="saved_profiles")
    saved_user = relationship("User", foreign_keys=[saved_user_id])


class MatchRequest(Base):
    __tablename__ = "match_requests"

    id = Column(Integer, primary_key=True)
    sender_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=lambda: datetime.now(india_tz))
    is_read = Column(Boolean, default=False)
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_requests")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_requests")



class BlockedProfile(Base):
    __tablename__ = "blocked_profiles"

    id = Column(Integer, primary_key=True)
    blocker_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    blocked_user_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    reason = Column(String(255))  # Optional

    blocker = relationship(
        "User",
        foreign_keys=[blocker_id],
        back_populates="blocked_profiles"
    )
    blocked_user = relationship(
        "User",
        foreign_keys=[blocked_user_id]
    )





class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True)
    user1_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    user2_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=lambda: datetime.now(india_tz))

    user1 = relationship("User", foreign_keys=[user1_id])
    user2 = relationship("User", foreign_keys=[user2_id])
    messages = relationship(
        "ChatMessage",
        back_populates="room",
        cascade="all, delete",
        passive_deletes=True
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"))
    sender_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    message = Column(Text)
    timestamp = Column(DateTime, default=lambda: datetime.now(india_tz))
    is_read = Column(Boolean, default=False)

    room = relationship("ChatRoom", back_populates="messages")
    sender = relationship("User", foreign_keys=[sender_id], back_populates="chats_sent")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="chats_received")


class ProfileView(Base):
    __tablename__ = "profile_views"

    id = Column(String(10), primary_key=True, index=True)
    user_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))        # The user being viewed
    viewed_by_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))   # The user who viewed

    viewed_at = Column(DateTime, default=func.now())
    is_read = Column(Boolean, default=False)
    # Define explicit relationships
    receiver = relationship("User", foreign_keys=[user_id], back_populates="views_received")
    viewer = relationship("User", foreign_keys=[viewed_by_id], back_populates="views_made")
class NotificationStatus(str, PyEnum):  # use `str` to store enum as string
    pending = "pending"
    accepted = "accepted"
    view = "view"
    rejected = "rejected"
    msg = "msg"

class Notification(Base):
    __tablename__ = "notification"

    id = Column(Integer, primary_key=True)
    sender_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    receiver_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))

    # ✅ Direct enum inside
    status = Column(SQLEnum(NotificationStatus, name="notification_status", native_enum=False), default=NotificationStatus.pending, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(india_tz))
    message = Column(Text)
    is_read = Column(Boolean, default=False)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_notify")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_notify")


class Payment(Base):
    __tablename__ = 'user_payment'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    mobile_no = Column(String(20))
    email_id = Column(String(255))
    currency = Column(String(255))
    amount = Column(Float)
    order_id = Column(String(250))
    payment_id = Column(String(250))
    status = Column(String(50))
    date= Column(Date)
    user = relationship("User", back_populates="payment")

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(10), ForeignKey("users.id", ondelete="CASCADE"))
    subject = Column(String(250), nullable=False)
    message = Column(Text, nullable=False)
    user = relationship("User", back_populates="contact")

class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(String(10), ForeignKey("users.id"))
    receiver_id = Column(String(10), ForeignKey("users.id"))
    timestamp = Column(DateTime, default=lambda: datetime.now(india_tz))

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


class Banner1(Base):
    __tablename__ = "banner1"
    id = Column(Integer, primary_key=True, index=True)
    banner_name = Column(String(255), nullable=False)
    banner_url = Column(String(255), nullable=True)  # stores file path


class Banner2(Base):
    __tablename__ = "banner2"
    id = Column(Integer, primary_key=True, index=True)
    banner_name = Column(String(255), nullable=False)
    banner_url = Column(String(255), nullable=True)

class AgoraConfig(Base):
    __tablename__ = "agora_configs"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String(255), nullable=False, unique=True)
    app_certificate = Column(String(255), nullable=True)
    app_name = Column(String(100), nullable=True)
    environment = Column(String(50), default="prod")  # dev/staging/prod
    status = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class MembershipPlan(Base):
    __tablename__ = "membership_plans"

    id = Column(Integer, primary_key=True, index=True)
    membership_name = Column(String(100), nullable=False, unique=True)
    inr_price = Column(Float, nullable=False)
    usd_price = Column(Float, nullable=False)
    video_mins = Column(Integer, nullable=False)
    voice_mins = Column(Integer, nullable=False)
    chat_no = Column(Integer, nullable=False)
    days = Column(Integer, nullable=False)
    status = Column(String(20), default="active")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())



class SignupSession(Base):
    __tablename__ = "signup_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)  # already hashed by caller
    name = Column(String(100), nullable=False)
    gender = Column(String(50), nullable=False)
    dob = Column(Date, nullable=False)
    maritalStatus = Column(String(50))
    education = Column(String(100))
    occupation = Column(String(100))
    language = Column(String(255))
    height = Column(String(10))
    diet = Column(String(50))
    smoke = Column(String(50))
    drink = Column(String(50))
    city_name = Column(String(100))
    postal = Column(Text)
    state = Column(String(100))
    country = Column(String(100))
    mobile = Column(String(20))
    mobilecode = Column(String(10))
    partnerExpectations = Column(Text)
    bio = Column(Text)
    status = Column(String(20), default="pending")
    memtype = Column(String(20), default="Free")
    membershipExpiryDate = Column(Date, nullable=True)

    # ✅ Added photo fields
    photo1 = Column(String(255), nullable=True)
    photo2 = Column(String(255), nullable=True)
    photo1Approve = Column(Boolean, default=False)
    photo2Approve = Column(Boolean, default=False)

    otp = Column(String(6), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)