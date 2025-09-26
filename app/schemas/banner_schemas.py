from pydantic import BaseModel, Field

class BannerBase(BaseModel):
    banner_name: str = Field(..., min_length=2, max_length=255)

class BannerCreate(BannerBase):
    pass

class BannerResponse(BannerBase):
    id: int
    banner_url: str | None = None

    class Config:
        from_attributes = True
