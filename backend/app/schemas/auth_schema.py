import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_一-龥]+$")
    password: str = Field(min_length=6, max_length=64)
    email: str | None = None

    @field_validator("email")
    @classmethod
    def email_optional(cls, v):
        if v is not None and ("@" not in v or len(v) > 255):
            raise ValueError("邮箱格式不正确")
        return v


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=64)


class ChangePasswordIn(BaseModel):
    old_password: str = Field(min_length=1, max_length=64)
    new_password: str = Field(min_length=6, max_length=64)


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None = None
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
