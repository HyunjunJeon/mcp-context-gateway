# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/routers/oauth_router.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

MCP 게이트웨이를 위한 OAuth 라우터.

이 모듈은 다음과 같은 OAuth 2.0 인증 코드 플로우 엔드포인트를 처리합니다:
- OAuth 플로우 시작
- OAuth 콜백 처리
- 토큰 관리
"""

# Standard - 표준 라이브러리
import logging
from typing import Any, Dict

# Third-Party - 외부 라이브러리
from fastapi import APIRouter, Depends, HTTPException, Query, Request  # FastAPI 라우터 및 의존성
from fastapi.responses import HTMLResponse, RedirectResponse  # HTTP 응답 타입
from sqlalchemy import select  # SQL 쿼리 빌더
from sqlalchemy.orm import Session  # 데이터베이스 세션

# First-Party - 내부 모듈
from mcpgateway.db import Gateway, get_db  # 게이트웨이 모델과 DB 세션
from mcpgateway.services.oauth_manager import OAuthError, OAuthManager  # OAuth 관리 서비스
from mcpgateway.services.token_storage_service import TokenStorageService  # 토큰 저장소

# 로거 초기화
logger = logging.getLogger(__name__)

# OAuth 라우터 생성 - /oauth 경로의 모든 엔드포인트 처리
oauth_router = APIRouter(prefix="/oauth", tags=["oauth"])


@oauth_router.get("/authorize/{gateway_id}")
async def initiate_oauth_flow(gateway_id: str, request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    """지정된 게이트웨이에 대한 OAuth 2.0 인증 코드 플로우를 시작합니다.

    이 엔드포인트는 주어진 게이트웨이에 대한 OAuth 구성을 검색하고,
    게이트웨이가 인증 코드 플로우를 지원하는지 검증한 후,
    OAuth 제공자의 인증 URL로 사용자를 리다이렉트하여 OAuth 프로세스를 시작합니다.

    Args:
        gateway_id: 인증할 게이트웨이의 고유 식별자.
        request: FastAPI 요청 객체.
        db: 데이터베이스 세션 의존성.

    Returns:
        OAuth 제공자의 인증 URL로의 리다이렉트 응답.

    Raises:
        HTTPException: 게이트웨이를 찾을 수 없거나, OAuth용으로 구성되지 않았거나,
            인증 코드 플로우를 사용하지 않는 경우. 시작 과정에서 예기치 않은 오류가 발생한 경우.
    """
    try:
        # 단계 1: 게이트웨이 구성 검증
        # 데이터베이스에서 게이트웨이 정보를 조회하고 OAuth 구성 확인
        gateway = db.execute(select(Gateway).where(Gateway.id == gateway_id)).scalar_one_or_none()

        if not gateway:
            raise HTTPException(status_code=404, detail="Gateway not found")

        if not gateway.oauth_config:
            raise HTTPException(status_code=400, detail="Gateway is not configured for OAuth")

        if gateway.oauth_config.get("grant_type") != "authorization_code":
            raise HTTPException(status_code=400, detail="Gateway is not configured for Authorization Code flow")

        # 단계 2: OAuth 플로우 초기화
        # OAuth 관리자를 생성하고 인증 코드 플로우를 시작하여 인증 URL 획득
        oauth_manager = OAuthManager(token_storage=TokenStorageService(db))
        auth_data = await oauth_manager.initiate_authorization_code_flow(gateway_id, gateway.oauth_config)

        logger.info(f"Initiated OAuth flow for gateway {gateway_id}")

        # 단계 3: 사용자 리다이렉트
        # OAuth 제공자의 인증 페이지로 사용자를 리다이렉트
        return RedirectResponse(url=auth_data["authorization_url"])

    except HTTPException:
        # HTTP 예외는 그대로 전파 (클라이언트 오류)
        raise
    except Exception as e:
        # 예상치 못한 오류 로깅 및 서버 오류로 변환
        logger.error(f"Failed to initiate OAuth flow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate OAuth flow: {str(e)}")


@oauth_router.get("/callback")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    # Remove the gateway_id parameter requirement
    request: Request = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """OAuth 콜백을 처리하고 인증 프로세스를 완료합니다.

    이 엔드포인트는 사용자가 접근을 승인한 후 OAuth 제공자에 의해 호출됩니다.
    인증 코드와 상태 파라미터를 받아 상태를 검증하고,
    해당 게이트웨이 구성을 검색한 후 코드를 액세스 토큰으로 교환합니다.

    Args:
        code (str): OAuth 제공자가 반환한 인증 코드.
        state (str): CSRF 보호를 위한 상태 파라미터로 게이트웨이 ID를 인코딩합니다.
        request (Request): 들어오는 HTTP 요청 객체.
        db (Session): 데이터베이스 세션 의존성.

    Returns:
        HTMLResponse: OAuth 인증 프로세스의 결과를 나타내는 HTML 응답.
    """

    try:
        # 1. 상태 파라미터에서 게이트웨이 ID 추출 (CSRF 보호)
        if "_" not in state:
            return HTMLResponse(content="<h1>❌ Invalid state parameter</h1>", status_code=400)

        gateway_id = state.split("_")[0]

        # 2. 게이트웨이 구성 정보 조회
        gateway = db.execute(select(Gateway).where(Gateway.id == gateway_id)).scalar_one_or_none()

        if not gateway:
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>OAuth Authorization Failed</title></head>
                <body>
                    <h1>❌ OAuth Authorization Failed</h1>
                    <p>Error: Gateway not found</p>
                    <a href="/admin#gateways">Return to Admin Panel</a>
                </body>
                </html>
                """,
                status_code=404,
            )

        if not gateway.oauth_config:
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head><title>OAuth Authorization Failed</title></head>
                <body>
                    <h1>❌ OAuth Authorization Failed</h1>
                    <p>Error: Gateway has no OAuth configuration</p>
                    <a href="/admin#gateways">Return to Admin Panel</a>
                </body>
                </html>
                """,
                status_code=400,
            )

        # 3. OAuth 플로우 완료 - 인증 코드를 액세스 토큰으로 교환
        oauth_manager = OAuthManager(token_storage=TokenStorageService(db))

        result = await oauth_manager.complete_authorization_code_flow(gateway_id, code, state, gateway.oauth_config)

        logger.info(f"Completed OAuth flow for gateway {gateway_id}, user {result.get('user_id')}")

        # 4. 성공 페이지 반환 및 관리 패널로 돌아가기 옵션 제공
        return HTMLResponse(
            content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Authorization Successful</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .success {{ color: #059669; }}
                .error {{ color: #dc2626; }}
                .info {{ color: #2563eb; }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #3b82f6;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
                .button:hover {{ background-color: #2563eb; }}
            </style>
        </head>
        <body>
            <h1 class="success">✅ OAuth Authorization Successful</h1>
            <div class="info">
                <p><strong>Gateway:</strong> {gateway.name}</p>
                <p><strong>User ID:</strong> {result.get("user_id", "Unknown")}</p>
                <p><strong>Expires:</strong> {result.get("expires_at", "Unknown")}</p>
                <p><strong>Status:</strong> Authorization completed successfully</p>
            </div>

            <div style="margin: 30px 0;">
                <h3>Next Steps:</h3>
                <p>Now that OAuth authorization is complete, you can fetch tools from the MCP server:</p>
                <button onclick="fetchTools()" class="button" style="background-color: #059669;">
                    🔧 Fetch Tools from MCP Server
                </button>
                <div id="fetch-status" style="margin-top: 15px;"></div>
            </div>

            <a href="/admin#gateways" class="button">Return to Admin Panel</a>

            <script>
            async function fetchTools() {{
                const button = event.target;
                const statusDiv = document.getElementById('fetch-status');

                button.disabled = true;
                button.textContent = '⏳ Fetching Tools...';
                statusDiv.innerHTML = '<p style="color: #2563eb;">Fetching tools from MCP server...</p>';

                try {{
                    const response = await fetch('/oauth/fetch-tools/{gateway_id}', {{
                        method: 'POST'
                    }});

                    const result = await response.json();

                    if (response.ok) {{
                        statusDiv.innerHTML = `
                            <div style="color: #059669; padding: 15px; background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 5px;">
                                <h4>✅ Tools Fetched Successfully!</h4>
                                <p>${{result.message}}</p>
                            </div>
                        `;
                        button.textContent = '✅ Tools Fetched';
                        button.style.backgroundColor = '#059669';
                    }} else {{
                        throw new Error(result.detail || 'Failed to fetch tools');
                    }}
                }} catch (error) {{
                    statusDiv.innerHTML = `
                        <div style="color: #dc2626; padding: 15px; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 5px;">
                            <h4>❌ Failed to Fetch Tools</h4>
                            <p><strong>Error:</strong> ${{error.message}}</p>
                            <p>You can still return to the admin panel and try again later.</p>
                        </div>
                    `;
                    button.textContent = '❌ Retry Fetch Tools';
                    button.style.backgroundColor = '#dc2626';
                    button.disabled = false;
                }}
            }}
            </script>
        </body>
        </html>
        """
        )

    except OAuthError as e:
        logger.error(f"OAuth callback failed: {str(e)}")
        return HTMLResponse(
            content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Authorization Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .error {{ color: #dc2626; }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #3b82f6;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
                .button:hover {{ background-color: #2563eb; }}
            </style>
        </head>
        <body>
            <h1 class="error">❌ OAuth Authorization Failed</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <p>Please check your OAuth configuration and try again.</p>
            <a href="/admin#gateways" class="button">Return to Admin Panel</a>
        </body>
        </html>
        """,
            status_code=400,
        )

    except Exception as e:
        logger.error(f"Unexpected error in OAuth callback: {str(e)}")
        return HTMLResponse(
            content=f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Authorization Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .error {{ color: #dc2626; }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #3b82f6;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    margin-top: 20px;
                }}
                .button:hover {{ background-color: #2563eb; }}
            </style>
        </head>
        <body>
            <h1 class="error">❌ OAuth Authorization Failed</h1>
            <p><strong>Unexpected Error:</strong> {str(e)}</p>
            <p>Please contact your administrator for assistance.</p>
            <a href="/admin#gateways" class="button">Return to Admin Panel</a>
        </body>
        </html>
        """,
            status_code=500,
        )


@oauth_router.get("/status/{gateway_id}")
async def get_oauth_status(gateway_id: str, db: Session = Depends(get_db)) -> dict:
    """게이트웨이에 대한 OAuth 상태를 조회합니다.

    Args:
        gateway_id: 게이트웨이의 ID
        db: 데이터베이스 세션

    Returns:
        OAuth 상태 정보

    Raises:
        HTTPException: 게이트웨이를 찾을 수 없거나 상태 조회 중 오류가 발생한 경우
    """
    try:
        # 1. 게이트웨이 구성 정보 조회
        gateway = db.execute(select(Gateway).where(Gateway.id == gateway_id)).scalar_one_or_none()

        if not gateway:
            raise HTTPException(status_code=404, detail="Gateway not found")

        if not gateway.oauth_config:
            return {"oauth_enabled": False, "message": "Gateway is not configured for OAuth"}

        # 2. OAuth 구성 정보 추출 및 검증
        oauth_config = gateway.oauth_config
        grant_type = oauth_config.get("grant_type")

        if grant_type == "authorization_code":
            # 인증 코드 플로우의 경우 기본 정보 반환
            # 실제 구현에서는 인증된 사용자, 토큰 상태 등을 표시할 수 있음
            return {
                "oauth_enabled": True,
                "grant_type": grant_type,
                "client_id": oauth_config.get("client_id"),
                "scopes": oauth_config.get("scopes", []),
                "authorization_url": oauth_config.get("authorization_url"),
                "redirect_uri": oauth_config.get("redirect_uri"),
                "message": "Gateway configured for Authorization Code flow",
            }
        else:
            # 다른 OAuth 플로우 타입의 경우
            return {
                "oauth_enabled": True,
                "grant_type": grant_type,
                "client_id": oauth_config.get("client_id"),
                "scopes": oauth_config.get("scopes", []),
                "message": f"Gateway configured for {grant_type} flow",
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get OAuth status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get OAuth status: {str(e)}")


@oauth_router.post("/fetch-tools/{gateway_id}")
async def fetch_tools_after_oauth(gateway_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """OAuth 완료 후 MCP 서버에서 도구를 가져옵니다 (인증 코드 플로우용).

    Args:
        gateway_id: 도구를 가져올 게이트웨이의 ID
        db: 데이터베이스 세션

    Returns:
        성공 상태와 가져온 도구 수를 포함하는 딕셔너리

    Raises:
        HTTPException: 도구 가져오기가 실패한 경우
    """
    try:
        # 1. 게이트웨이 서비스를 통한 도구 가져오기
        from mcpgateway.services.gateway_service import GatewayService

        gateway_service = GatewayService()
        result = await gateway_service.fetch_tools_after_oauth(db, gateway_id)
        tools_count = len(result.get("tools", []))

        return {"success": True, "message": f"Successfully fetched and created {tools_count} tools"}

    except Exception as e:
        logger.error(f"Failed to fetch tools after OAuth for gateway {gateway_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tools: {str(e)}")
