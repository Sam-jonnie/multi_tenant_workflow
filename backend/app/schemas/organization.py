from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.enums import OrgRole

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class OrganizationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=150)
    slug: str | None = Field(None, min_length=2, max_length=150, pattern=SLUG_PATTERN)
    description: str | None = Field(None, max_length=2000)


class OrganizationUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(None, min_length=2, max_length=150)
    description: str | None = Field(None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_cannot_be_null(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("name cannot be null")
        return value


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MemberAdd(BaseModel):
    email: EmailStr
    role: OrgRole = OrgRole.TEAM_MEMBER


class MemberRoleUpdate(BaseModel):
    role: OrgRole


class MemberStatusUpdate(BaseModel):
    is_active: bool


class MemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str
    username: str
    full_name: str
    role: OrgRole
    is_active: bool
    joined_at: datetime