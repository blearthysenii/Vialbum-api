from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.schemas.user import AccessToken, AccountDeletionRequest, LoginRequest, UserCreate, UserRead
from app.services.account import AccountService
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: DatabaseSession) -> UserRead:
    return UserRead.model_validate(AuthService(session).register(payload))


@router.post("/login", response_model=AccessToken)
def login(payload: LoginRequest, session: DatabaseSession) -> AccessToken:
    return AuthService(session).login(payload)


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountDeletionRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> Response:
    AccountService(session, storage).delete(current_user, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
