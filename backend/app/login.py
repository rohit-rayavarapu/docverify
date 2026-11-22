import hashlib
import secrets

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, SecretStr

from .registration import RegisteredUser, password_hasher


router = APIRouter()
bearer = HTTPBearer(auto_error=False)
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/api/login", response_model=LoginResponse)
def login(request: LoginRequest):
    try:
        with psycopg.connect(connect_timeout=3) as connection:
            user = connection.execute(
                "SELECT id, password_hash FROM users WHERE lower(email) = lower(%s)",
                (str(request.email),),
            ).fetchone()

            stored_hash = user[1] if user else dummy_hash
            valid = password_hasher.verify(
                request.password.get_secret_value(), stored_hash
            )
            if user is None or not valid:
                raise HTTPException(401, "Invalid email or password")

            token = secrets.token_urlsafe(32)
            connection.execute(
                """
                INSERT INTO login_sessions (token_hash, user_id, expires_at)
                VALUES (%s, %s, now() + interval '1 hour')
                """,
                (token_digest(token), user[0]),
            )
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    return LoginResponse(access_token=token)


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> RegisteredUser:
    unauthorized = HTTPException(
        401, "Valid access token required", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized

    try:
        with psycopg.connect(connect_timeout=3) as connection:
            user = connection.execute(
                """
                SELECT u.id, u.email, u.role
                FROM login_sessions AS s
                JOIN users AS u ON u.id = s.user_id
                WHERE s.token_hash = %s AND s.expires_at > now()
                """,
                (token_digest(credentials.credentials),),
            ).fetchone()
    except psycopg.OperationalError:
        raise HTTPException(503, "Database unavailable") from None

    if user is None:
        raise unauthorized
    return RegisteredUser(id=user[0], email=user[1], role=user[2])


@router.get("/api/me", response_model=RegisteredUser)
def get_me(user: RegisteredUser = Depends(current_user)):
    return user