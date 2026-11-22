from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from .login import current_user
from .registration import RegisteredUser


router = APIRouter(prefix="/api/admin", tags=["Admin"])


def require_admin(user: RegisteredUser = Depends(current_user)) -> RegisteredUser:
    if user.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get(
    "/users",
    response_model=list[RegisteredUser],
    dependencies=[Depends(require_admin)],
)
def list_users():
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            rows = connection.execute(
                "SELECT id, email, role FROM users ORDER BY id"
            ).fetchall()
    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="Database unavailable") from None

    return [
        RegisteredUser(id=user_id, email=email, role=role)
        for user_id, email, role in rows
    ]


class RoleChange(BaseModel):
    role: Literal["Applicant", "Reviewer", "Admin"]


@router.patch("/users/{user_id}/role", response_model=RegisteredUser)
def change_role(user_id: int, request: RoleChange, actor: RegisteredUser = Depends(require_admin)):
    if actor.id == user_id:
        raise HTTPException(409, "Use another administrator to change your own role")
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            # Lock both accounts in stable order and recheck authorization before writing.
            rows = connection.execute(
                "SELECT id, role FROM users WHERE id IN (%s, %s) ORDER BY id FOR UPDATE",
                (actor.id, user_id),
            ).fetchall()
            roles = dict(rows)
            if roles.get(actor.id) != "Admin":
                raise HTTPException(403, "Admin access required")
            if user_id not in roles:
                raise HTTPException(404, "User not found")
            row = connection.execute(
                "UPDATE users SET role = %s WHERE id = %s RETURNING id, email, role",
                (request.role, user_id),
            ).fetchone()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None
    return RegisteredUser(id=row[0], email=row[1], role=row[2])
