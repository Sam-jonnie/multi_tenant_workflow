from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field


def _check_strength(value: str) -> str:
    if not any(c.islower() for c in value):
        raise ValueError("Password must contain a lowercase letter.")
    if not any(c.isupper() for c in value):
        raise ValueError("Password must contain an uppercase letter.")
    if not any(c.isdigit() for c in value):
        raise ValueError("Password must contain a digit.")
    return value


StrongPassword = Annotated[
    str, Field(min_length=8, max_length=128), AfterValidator(_check_strength)
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    full_name: str = Field(min_length=1, max_length=120)
    password: StrongPassword


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: StrongPassword


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds