from pydantic import BaseModel, EmailStr, Field

from src.app.schema.user import UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class DeviceInfo(BaseModel):
    ip: str
    os: str
    browser: str
    device: str
    user_agent: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    info: DeviceInfo
