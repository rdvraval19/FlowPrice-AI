"""app/schemas/auth.py — Request and response schemas for auth endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["user", "vendor"] = "user"

    @field_validator("password")
    @classmethod
    def password_not_blank(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("Password must not be blank")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # seconds
    role: Literal["user", "vendor"]
    user_id: str


class UserPublic(BaseModel):
    """Safe user representation — never expose hashed_password."""
    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
