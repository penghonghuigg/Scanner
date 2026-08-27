from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=200)


class AuthUser(BaseModel):
    id: int
    username: str
    display_name: str
    role: Literal["ADMIN", "OPERATOR", "VIEWER"]
    branch_code: str | None
    branch_name: str | None
