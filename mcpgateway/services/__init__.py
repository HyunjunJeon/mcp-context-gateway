# -*- coding: utf-8 -*-
"""위치: ./mcpgateway/services/__init__.py
저작권 2025
SPDX-License-Identifier: Apache-2.0
저자: Mihai Criveti

서비스 패키지 초기화 모듈

MCP 게이트웨이의 핵심 서비스들을 노출합니다:
- 도구 관리 (Tool management)
- 리소스 처리 (Resource handling)
- 프롬프트 템플릿 (Prompt templates)
- 게이트웨이 조율 (Gateway coordination)
"""

# 코어 서비스 클래스 및 예외 클래스들을 임포트합니다.
from mcpgateway.services.gateway_service import GatewayError, GatewayService
from mcpgateway.services.prompt_service import PromptError, PromptService
from mcpgateway.services.resource_service import ResourceError, ResourceService
from mcpgateway.services.tool_service import ToolError, ToolService

__all__ = [
    "ToolService",
    "ToolError",
    "ResourceService",
    "ResourceError",
    "PromptService",
    "PromptError",
    "GatewayService",
    "GatewayError",
]
