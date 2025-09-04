# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/federation/__init__.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

페데레이션 패키지.
MCP Gateway 페데레이션을 위한 컴포넌트들을 제공합니다:
- 게이트웨이 검색
- 요청 포워딩
- 페데레이션 관리
"""

# 페데레이션 모듈에서 주요 서비스 클래스들을 임포트하여 외부에서 쉽게 사용할 수 있도록 함
from mcpgateway.federation.discovery import DiscoveryService
from mcpgateway.federation.forward import ForwardingService

# 패키지 외부에 노출할 공개 인터페이스 정의
__all__ = [
    "DiscoveryService",
    "ForwardingService",
]
