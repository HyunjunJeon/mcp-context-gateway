# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/security_cookies.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

MCP Gateway용 보안 쿠키 유틸리티.

이 모듈은 일반적인 쿠키 기반 공격을 방지하기 위해 적절한 보안 속성으로
안전한 인증 쿠키를 설정하는 유틸리티를 제공합니다.
"""

# Third-Party
from fastapi import Response

# First-Party
from mcpgateway.config import settings


def set_auth_cookie(response: Response, token: str, remember_me: bool = False) -> None:
    """
    Set authentication cookie with security flags.

    Configures the JWT token as a secure HTTP-only cookie with appropriate
    security attributes to prevent XSS and CSRF attacks.

    Args:
        response: FastAPI response object to set the cookie on
        token: JWT token to store in the cookie
        remember_me: If True, sets longer expiration time (30 days vs 1 hour)

    Security attributes set:
    - httponly: Prevents JavaScript access to the cookie
    - secure: HTTPS only in production environments
    - samesite: CSRF protection (configurable, defaults to 'lax')
    - path: Cookie scope limitation
    - max_age: Automatic expiration
    """
    # Set expiration based on remember_me preference
    max_age = 30 * 24 * 3600 if remember_me else 3600  # 30 days or 1 hour

    # Determine if we should use secure flag
    # In production or when explicitly configured, require HTTPS
    use_secure = (settings.environment == "production") or settings.secure_cookies

    response.set_cookie(
        key="jwt_token",
        value=token,
        max_age=max_age,
        httponly=True,  # Prevents JavaScript access
        secure=use_secure,  # HTTPS only in production
        samesite=settings.cookie_samesite,  # CSRF protection
        path="/",  # Cookie scope
    )


def clear_auth_cookie(response: Response) -> None:
    """
    Clear authentication cookie securely.

    Removes the JWT token cookie by setting it to expire immediately
    with the same security attributes used when setting it.

    Args:
        response: FastAPI response object to clear the cookie from
    """
    # Use same security settings as when setting the cookie
    use_secure = (settings.environment == "production") or settings.secure_cookies

    response.delete_cookie(key="jwt_token", path="/", secure=use_secure, httponly=True, samesite=settings.cookie_samesite)


def set_session_cookie(response: Response, session_id: str, max_age: int = 3600) -> None:
    """
    Set session cookie with security flags.

    Configures a session ID cookie with appropriate security attributes.

    Args:
        response: FastAPI response object to set the cookie on
        session_id: Session identifier to store in the cookie
        max_age: Cookie expiration time in seconds (default: 1 hour)
    """
    use_secure = (settings.environment == "production") or settings.secure_cookies

    response.set_cookie(
        key="session_id",
        value=session_id,
        max_age=max_age,
        httponly=True,
        secure=use_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    """
    Clear session cookie securely.

    Args:
        response: FastAPI response object to clear the cookie from
    """
    use_secure = (settings.environment == "production") or settings.secure_cookies

    response.delete_cookie(key="session_id", path="/", secure=use_secure, httponly=True, samesite=settings.cookie_samesite)
