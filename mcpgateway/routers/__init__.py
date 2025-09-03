# -*- coding: utf-8 -*-
"""MCP Gateway 라우터 모듈.

이 패키지는 MCP Gateway의 모든 API 라우터를 포함합니다:
- OAuth 2.0 인증 플로우 (oauth_router)
- 역방향 프록시 연결 (reverse_proxy)
- 표준 웹 리소스 (well_known)
"""

# 라우터 모듈들을 미리 임포트하여 편의성 제공
from . import oauth_router, reverse_proxy, well_known

__all__ = ["oauth_router", "reverse_proxy", "well_known"]
