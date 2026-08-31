from typing import Optional
from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4)
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=100)


class UserLoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    name: str
    email: str


class AuthTokenResponse(BaseModel):
    token: str
    user: UserResponse
