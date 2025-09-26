from typing import Optional

from pydantic import BaseModel
from datetime import datetime

class MessageResponse(BaseModel):
    id: int
    sender_id: str
    receiver_id: str
    message: str
    timestamp: datetime
    is_read: bool

    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: str
    name: str
    photo1: str
    city_name: Optional[str]
    occupation: Optional[str]

    class Config:
        from_attributes = True
