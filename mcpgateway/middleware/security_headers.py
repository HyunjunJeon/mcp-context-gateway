# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/middleware/security_headers.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

MCP 게이트웨이용 보안 헤더 미들웨어.

이 모듈은 XSS, 클릭재킹, MIME 스니핑, 크로스-오리진 공격 등
일반적인 공격을 방지하기 위한 필수 보안 헤더를 구현합니다.
"""

# Third-Party - 외부 라이브러리
from starlette.middleware.base import BaseHTTPMiddleware  # FastAPI 미들웨어 기본 클래스
from starlette.requests import Request  # HTTP 요청 객체
from starlette.responses import Response  # HTTP 응답 객체

# First-Party - 내부 모듈
from mcpgateway.config import settings  # 애플리케이션 설정


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    모든 응답에 필수 보안 헤더를 추가하는 보안 헤더 미들웨어.

    이 미들웨어는 다양한 공격과 보안 취약점을 방지하는 헤더를 추가함으로써
    보안 모범 사례를 구현합니다.

    추가되는 보안 헤더:
    - X-Content-Type-Options: MIME 타입 스니핑 방지
    - X-Frame-Options: 클릭재킹 공격 방지
    - X-XSS-Protection: 레거시 XSS 보호 비활성화 (최신 브라우저는 CSP 사용)
    - Referrer-Policy: 요청과 함께 전송되는 리퍼러 정보 제어
    - Content-Security-Policy: XSS 및 기타 코드 인젝션 공격 방지
    - Strict-Transport-Security: HTTPS 연결 강제 (적절한 경우)

    제거되는 민감한 헤더:
    - X-Powered-By: 서버 기술 스택 노출 제거
    - Server: 서버 버전 정보 제거
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        요청을 처리하고 응답에 보안 헤더를 추가합니다.

        Args:
            request: 들어오는 HTTP 요청
            call_next: 다음 미들웨어 또는 엔드포인트 핸들러

        Returns:
            보안 헤더가 추가된 응답
        """
        # 1. 다음 핸들러로 요청을 전달하여 응답 생성
        response = await call_next(request)

        # 2. 보안 헤더 활성화 여부 확인
        # 설정에서 보안 헤더가 비활성화된 경우 그대로 반환
        if not settings.security_headers_enabled:
            return response

        # 3. 기본 보안 헤더 추가 (설정에 따라 조건부 적용)
        # MIME 타입 스니핑 방지 헤더
        if settings.x_content_type_options_enabled:
            response.headers["X-Content-Type-Options"] = "nosniff"

        # 클릭재킹 방지 헤더
        if settings.x_frame_options:
            response.headers["X-Frame-Options"] = settings.x_frame_options

        # 레거시 XSS 보호 비활성화 (최신 브라우저는 CSP 사용)
        if settings.x_xss_protection_enabled:
            response.headers["X-XSS-Protection"] = "0"

        # IE 다운로드 실행 방지 헤더
        if settings.x_download_options_enabled:
            response.headers["X-Download-Options"] = "noopen"

        # 리퍼러 정보 전송 정책 설정
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 4. 콘텐츠 보안 정책 (CSP) 설정
        # Admin UI와 호환되면서 보안을 제공하도록 설계된 CSP
        # XSS 및 코드 인젝션 공격을 방지하는 핵심 보안 메커니즘
        csp_directives = [
            "default-src 'self'",  # 기본적으로 같은 오리진만 허용
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.tailwindcss.com https://cdn.jsdelivr.net",  # 스크립트 소스 허용
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net",  # 스타일 소스 허용
            "img-src 'self' data: https:",  # 이미지 소스 허용
            "font-src 'self' data:",  # 폰트 소스 허용
            "connect-src 'self' ws: wss: https:",  # 연결 소스 허용 (WebSocket 포함)
            "frame-ancestors 'none'",  # 모든 프레이밍 금지 (클릭재킹 방지)
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives) + ";"

        # 5. HTTP 엄격 전송 보안 (HSTS) 설정 (HTTPS 연결용)
        # HTTPS 연결 강제 및 중간자 공격 방지를 위한 설정
        if settings.hsts_enabled and (request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https"):
            hsts_value = f"max-age={settings.hsts_max_age}"
            if settings.hsts_include_subdomains:
                hsts_value += "; includeSubDomains"  # 서브도메인에도 적용
            response.headers["Strict-Transport-Security"] = hsts_value

        # 6. 민감한 서버 정보 헤더 제거 (설정에 따라 조건부 적용)
        # 서버 기술 스택이나 버전 정보가 노출되는 것을 방지
        if settings.remove_server_headers:
            if "X-Powered-By" in response.headers:
                del response.headers["X-Powered-By"]  # 서버 기술 스택 정보 제거
            if "Server" in response.headers:
                del response.headers["Server"]  # 서버 버전 정보 제거

        # 7. 보안 헤더가 추가된 응답 반환
        return response
