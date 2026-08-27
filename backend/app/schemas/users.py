from pydantic import BaseModel, ConfigDict, Field


class CreateUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=100)
    branch_code: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=6, max_length=64)
    password_confirmation: str = Field(min_length=6, max_length=64)
