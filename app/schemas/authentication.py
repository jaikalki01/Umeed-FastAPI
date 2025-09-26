from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, constr


class UserResponse(BaseModel):
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
    mobilecode: Optional[str]
    partnerExpectations: Optional[str]
    bio: Optional[str]
    status: Optional[str]
    memtype: Optional[str]
    membershipExpiryDate: Optional[date]
    photo1: Optional[str]
    lastSeen: Optional[datetime]

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str

# ✅ Token Data
class Token(BaseModel):
    access_token: str
    token_type: str
    user_role: Optional[str] = None


    @classmethod
    def from_user(cls, access_token: str, token_type: str, role: int):
        """Map role using if-else conditions."""
        if role == 1:
            mapped_role = "user"
        elif role == 2:
            mapped_role = "seller"
        elif role == 3:
            mapped_role = "admin"
        else:
            mapped_role = "unknown"

        return cls(
            access_token=access_token,
            token_type=token_type,
            user_role=mapped_role
        )

class MobileOTPLogin(BaseModel):
    country_code: constr(min_length=1)
    mobile: constr(min_length=10, max_length=15)
    otp: Optional[constr(min_length=6, max_length=6)] = None
