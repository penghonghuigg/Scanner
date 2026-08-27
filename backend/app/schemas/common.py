from typing import Literal

from pydantic import BaseModel

from app.schemas.auth import AuthUser


class SuccessEnvelope[PayloadT](BaseModel):
    success: Literal[True] = True
    data: PayloadT
    trace_id: str


class AuthPayload(BaseModel):
    user: AuthUser


class EmptyPayload(BaseModel):
    pass
