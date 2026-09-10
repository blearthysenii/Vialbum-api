from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import CurrentUser, DatabaseSession, MediaStorage
from app.core.rate_limit import public_auth_rate_limit
from app.schemas.user import (
    AccessToken,
    AccountDeletionRequest,
    AccountExistsRequest,
    AccountExistsResponse,
    EmailExistsRequest,
    EmailExistsResponse,
    LoginRequest,
    UserCreate,
    UsernameExistsRequest,
    UsernameExistsResponse,
    UserRead,
)
from app.services.account import AccountService
from app.services.auth import AuthService
from app.services.users import UserService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: DatabaseSession) -> UserRead:
    return UserRead.model_validate(AuthService(session).register(payload))


@router.post("/login", response_model=AccessToken)
def login(payload: LoginRequest, session: DatabaseSession) -> AccessToken:
    return AuthService(session).login(payload)


@router.post(
    "/email-exists",
    response_model=EmailExistsResponse,
    dependencies=[Depends(public_auth_rate_limit())],
)
def email_exists(payload: EmailExistsRequest, session: DatabaseSession) -> EmailExistsResponse:
    return EmailExistsResponse(exists=AuthService(session).email_exists(payload))


@router.post(
    "/username-exists",
    response_model=UsernameExistsResponse,
    dependencies=[Depends(public_auth_rate_limit())],
)
def username_exists(
    payload: UsernameExistsRequest, session: DatabaseSession
) -> UsernameExistsResponse:
    return UsernameExistsResponse(exists=AuthService(session).username_exists(payload))


@router.post(
    "/account-exists",
    response_model=AccountExistsResponse,
    dependencies=[Depends(public_auth_rate_limit())],
)
def account_exists(
    payload: AccountExistsRequest, session: DatabaseSession
) -> AccountExistsResponse:
    return AccountExistsResponse(exists=AuthService(session).account_exists(payload))


@router.get("/me", response_model=UserRead)
def me(
    current_user: CurrentUser, session: DatabaseSession, storage: MediaStorage
) -> UserRead:
    return UserService(session, storage).serialize(current_user)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountDeletionRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
    storage: MediaStorage,
) -> Response:
    AccountService(session, storage).delete(current_user, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
