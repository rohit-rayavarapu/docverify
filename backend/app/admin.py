import psycopg
from fastapi import APIRouter, Depends, HTTPException

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