from typing import Annotated

import psycopg
from fastapi import APIRouter, HTTPException
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, StringConstraints
from pwdlib import PasswordHash

router = APIRouter()
password_hasher = PasswordHash.recommended()


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)] | None = None
    email: EmailStr
    password: SecretStr = Field(min_length=15, max_length=128)


class RegisteredUser(BaseModel):
    id: int
    email: str
    role: str


@router.post("/api/register", status_code=201, response_model=RegisteredUser)
def register_user(request: RegistrationRequest):
    password_hash = password_hasher.hash(request.password.get_secret_value())

    try:
        with psycopg.connect(connect_timeout=3) as connection:
            user_id, email, role = connection.execute(
                """
                INSERT INTO users (email, password_hash, full_name)
                VALUES (%s, %s, %s)
                RETURNING id, email, role
                """,
                (str(request.email), password_hash, request.full_name),
            ).fetchone()
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="Email already registered")
    except psycopg.OperationalError:
        raise HTTPException(status_code=503, detail="Database unavailable")

    return RegisteredUser(id=user_id, email=email, role=role)
