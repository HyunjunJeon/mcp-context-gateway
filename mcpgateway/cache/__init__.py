# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/cache/__init__.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

캐시 패키지.
MCP Gateway를 위한 캐싱 컴포넌트들을 제공합니다:
- 리소스 콘텐츠 캐싱
- 세션 레지스트리 관리
"""

# 캐시 모듈에서 주요 클래스들을 임포트하여 외부에서 쉽게 사용할 수 있도록 함
from mcpgateway.cache.resource_cache import ResourceCache
from mcpgateway.cache.session_registry import SessionRegistry

# 패키지 외부에 노출할 공개 인터페이스 정의
__all__ = ["ResourceCache", "SessionRegistry"]
