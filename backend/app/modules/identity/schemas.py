"""identity 入参/出参。"""

from __future__ import annotations

from datetime import datetime

from app.core.fields import EmailStr, NameStr, PasswordStr
from app.core.schemas import CreateSchema, SchemaBase, UpdateSchema


class UserRegister(CreateSchema):
    email: EmailStr
    password: PasswordStr
    display_name: NameStr


class UserLogin(CreateSchema):
    email: EmailStr
    password: PasswordStr


class UserOut(SchemaBase):
    id: str
    email: str
    display_name: str
    status: str
    created_at: datetime


class TokenOut(SchemaBase):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class WorkspaceCreate(CreateSchema):
    name: NameStr


class WorkspaceUpdate(UpdateSchema):
    name: NameStr | None = None


class WorkspaceOut(SchemaBase):
    id: str
    name: str
    created_by: str
    role: str | None = None
    created_at: datetime
    updated_at: datetime
