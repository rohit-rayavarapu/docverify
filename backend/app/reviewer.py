from fastapi import APIRouter, Depends, HTTPException

from .login import current_user
from .registration import RegisteredUser


router = APIRouter(prefix="/api/reviewer", tags=["Reviewer"])


def require_reviewer(user: RegisteredUser = Depends(current_user)) -> RegisteredUser:
    if user.role != "Reviewer":
        raise HTTPException(status_code=403, detail="Reviewer access required")
    return user


@router.get("/dashboard", response_model=RegisteredUser)
def reviewer_dashboard(reviewer: RegisteredUser = Depends(require_reviewer)):
    return reviewer