# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/routers/well_known.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

Well-Known URI 핸들러 라우터.
이 모듈은 security.txt 및 robots.txt와 같은 표준 well-known URI를 지원하는
유연한 /.well-known/* 엔드포인트 핸들러를 구현합니다.
기본값은 크롤링이 비활성화된 비공개 API 배포를 가정합니다.
"""

# Standard
from datetime import datetime, timedelta, timezone
from typing import Optional

# Third-Party
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

# First-Party
from mcpgateway.config import settings
from mcpgateway.services.logging_service import LoggingService
from mcpgateway.utils.verify_credentials import require_auth

# Get logger instance
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)

router = APIRouter(tags=["well-known"])

# Well-known URI registry with validation
WELL_KNOWN_REGISTRY = {
    "robots.txt": {"content_type": "text/plain", "description": "Robot exclusion standard", "rfc": "RFC 9309"},
    "security.txt": {"content_type": "text/plain", "description": "Security contact information", "rfc": "RFC 9116"},
    "ai.txt": {"content_type": "text/plain", "description": "AI usage policies", "rfc": "Draft"},
    "dnt-policy.txt": {"content_type": "text/plain", "description": "Do Not Track policy", "rfc": "W3C"},
    "change-password": {"content_type": "text/plain", "description": "Change password URL", "rfc": "RFC 8615"},
}


def validate_security_txt(content: str) -> Optional[str]:
    """security.txt 형식을 검증하고 누락된 헤더를 추가합니다.

    Args:
        content: 검증할 security.txt 내용.

    Returns:
        헤더가 추가된 검증된 security.txt 내용, 또는 내용이 비어있는 경우 None.
    """
    if not content:
        return None

    lines = content.strip().split("\n")

    # Expires 필드가 있는지 확인
    has_expires = any(line.strip().startswith("Expires:") for line in lines)

    # Expires 필드가 없으면 추가 (현재로부터 6개월 후)
    if not has_expires:
        expires = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=180)
        lines.append(f"Expires: {expires.isoformat()}Z")

    # 필수 헤더로 시작하는지 확인
    validated = []

    # 헤더 주석이 없으면 추가
    if not lines[0].startswith("#"):
        validated.append("# Security contact information for MCP Gateway")
        validated.append(f"# Generated: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}Z")
        validated.append("")

    validated.extend(lines)

    return "\n".join(validated)


@router.get("/.well-known/{filename:path}", include_in_schema=False)
async def get_well_known_file(filename: str, response: Response, request: Request):
    """
    well-known URI 파일을 제공합니다.

    지원:
    - robots.txt: 로봇 제외 표준 (기본값: 모두 허용 안함)
    - security.txt: 보안 연락처 정보 (구성된 경우)
    - 사용자 정의 파일: 구성을 통한 추가 well-known 파일

    Args:
        filename: 요청된 well-known 파일명
        response: 헤더를 위한 FastAPI 응답 객체
        request: 로깅을 위한 FastAPI 요청 객체

    Returns:
        요청된 파일의 일반 텍스트 내용

    Raises:
        HTTPException: 파일을 찾을 수 없거나 well-known이 비활성화된 경우 404
    """
    # 1. well-known 기능이 활성화되어 있는지 확인
    if not settings.well_known_enabled:
        raise HTTPException(status_code=404, detail="Not found")

    # 2. 파일명 정규화 (선행 슬래시 제거)
    filename = filename.strip("/")

    # 3. 공통 헤더 준비
    common_headers = {"Cache-Control": f"public, max-age={settings.well_known_cache_max_age}"}

    # 4. robots.txt 처리
    if filename == "robots.txt":
        headers = {**common_headers, "X-Robots-Tag": "noindex, nofollow"}
        return PlainTextResponse(content=settings.well_known_robots_txt, media_type="text/plain; charset=utf-8", headers=headers)

    # 5. security.txt 처리
    elif filename == "security.txt":
        if not settings.well_known_security_txt_enabled:
            raise HTTPException(status_code=404, detail="security.txt not configured")

        content = validate_security_txt(settings.well_known_security_txt)
        if not content:
            raise HTTPException(status_code=404, detail="security.txt not configured")

        return PlainTextResponse(content=content, media_type="text/plain; charset=utf-8", headers=common_headers)

    # 6. 사용자 정의 파일 처리
    elif filename in settings.custom_well_known_files:
        content = settings.custom_well_known_files[filename]

        # 콘텐츠 타입 결정
        content_type = "text/plain; charset=utf-8"
        if filename in WELL_KNOWN_REGISTRY:
            content_type = f"{WELL_KNOWN_REGISTRY[filename]['content_type']}; charset=utf-8"

        return PlainTextResponse(content=content, media_type=content_type, headers=common_headers)

    # 7. 파일을 찾을 수 없음
    else:
        # 알려진 well-known URI에 대한 유용한 오류 메시지 제공
        if filename in WELL_KNOWN_REGISTRY:
            raise HTTPException(status_code=404, detail=f"{filename} is not configured. This is a {WELL_KNOWN_REGISTRY[filename]['description']} file.")
        else:
            raise HTTPException(status_code=404, detail="Not found")


@router.get("/admin/well-known", response_model=dict)
async def get_well_known_status(user: str = Depends(require_auth)):
    """
    well-known URI 구성 상태를 조회합니다.

    Args:
        user: 의존성 주입을 통한 인증된 사용자.

    Returns:
        well-known 구성 상태와 사용 가능한 파일을 포함하는 딕셔너리.
    """
    configured_files = []

    # 항상 사용 가능
    configured_files.append({"path": "/.well-known/robots.txt", "enabled": True, "description": "Robot exclusion standard", "cache_max_age": settings.well_known_cache_max_age})

    # 조건부로 사용 가능
    if settings.well_known_security_txt_enabled:
        configured_files.append({"path": "/.well-known/security.txt", "enabled": True, "description": "Security contact information", "cache_max_age": settings.well_known_cache_max_age})

    # 사용자 정의 파일들
    for filename in settings.custom_well_known_files:
        configured_files.append({"path": f"/.well-known/{filename}", "enabled": True, "description": "Custom well-known file", "cache_max_age": settings.well_known_cache_max_age})

    return {"enabled": settings.well_known_enabled, "configured_files": configured_files, "supported_files": list(WELL_KNOWN_REGISTRY.keys()), "cache_max_age": settings.well_known_cache_max_age}
