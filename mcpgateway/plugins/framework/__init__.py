# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/__init__.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Fred Araujo

플러그인 프레임워크 패키지.
코어 MCP 게이트웨이 플러그인 컴포넌트들을 노출합니다:
- Context: 컨텍스트 관리
- Manager: 플러그인 관리자
- Payloads: 페이로드 모델들
- Models: 데이터 모델들
- ExternalPluginServer: 외부 플러그인 서버
"""

# First-Party - 플러그인 프레임워크의 주요 컴포넌트들을 import
from mcpgateway.plugins.framework.base import Plugin  # 기본 플러그인 클래스
from mcpgateway.plugins.framework.errors import PluginError, PluginViolationError  # 플러그인 관련 예외 클래스들
from mcpgateway.plugins.framework.external.mcp.server import ExternalPluginServer  # 외부 플러그인 서버
from mcpgateway.plugins.framework.loader.config import ConfigLoader  # 설정 파일 로더
from mcpgateway.plugins.framework.loader.plugin import PluginLoader  # 플러그인 로더
from mcpgateway.plugins.framework.manager import PluginManager  # 플러그인 관리자
from mcpgateway.plugins.framework.models import (
    GlobalContext,           # 전역 컨텍스트
    HookType,               # 후크 타입 열거형
    PluginCondition,        # 플러그인 실행 조건
    PluginConfig,           # 플러그인 설정
    PluginContext,          # 플러그인 컨텍스트
    PluginErrorModel,       # 플러그인 오류 모델
    PluginMode,             # 플러그인 모드
    PluginResult,           # 플러그인 실행 결과
    PluginViolation,        # 플러그인 위반사항
    PromptPosthookPayload,  # 프롬프트 사후 후크 페이로드
    PromptPosthookResult,   # 프롬프트 사후 후크 결과
    PromptPrehookPayload,   # 프롬프트 사전 후크 페이로드
    PromptPrehookResult,    # 프롬프트 사전 후크 결과
    PromptResult,           # 프롬프트 결과
    ResourcePostFetchPayload, # 리소스 사후 페치 페이로드
    ResourcePostFetchResult,  # 리소스 사후 페치 결과
    ResourcePreFetchPayload,  # 리소스 사전 페치 페이로드
    ResourcePreFetchResult,   # 리소스 사전 페치 결과
    ToolPostInvokePayload,   # 도구 사후 호출 페이로드
    ToolPostInvokeResult,    # 도구 사후 호출 결과
    ToolPreInvokePayload,    # 도구 사전 호출 페이로드
    ToolPreInvokeResult,     # 도구 사전 호출 결과
)

# 공개 API로 노출할 클래스와 함수들의 목록
__all__ = [
    # 설정 및 로더 클래스들
    "ConfigLoader",           # 설정 파일 로더
    "PluginLoader",          # 플러그인 로더
    "ExternalPluginServer",   # 외부 플러그인 서버

    # 플러그인 관리
    "PluginManager",         # 플러그인 관리자
    "Plugin",                # 기본 플러그인 클래스

    # 모델 및 타입들
    "GlobalContext",         # 전역 컨텍스트
    "PluginContext",         # 플러그인 컨텍스트
    "HookType",             # 후크 타입
    "PluginMode",           # 플러그인 모드
    "PluginCondition",      # 플러그인 조건
    "PluginConfig",         # 플러그인 설정
    "PluginResult",         # 플러그인 결과
    "PluginViolation",      # 플러그인 위반사항

    # 오류 처리
    "PluginError",          # 플러그인 오류
    "PluginErrorModel",     # 플러그인 오류 모델
    "PluginViolationError", # 플러그인 위반 오류

    # 페이로드 및 결과 클래스들
    "PromptPrehookPayload",    # 프롬프트 사전 후크 페이로드
    "PromptPrehookResult",     # 프롬프트 사전 후크 결과
    "PromptPosthookPayload",   # 프롬프트 사후 후크 페이로드
    "PromptPosthookResult",    # 프롬프트 사후 후크 결과
    "PromptResult",           # 프롬프트 결과

    "ToolPreInvokePayload",   # 도구 사전 호출 페이로드
    "ToolPreInvokeResult",    # 도구 사전 호출 결과
    "ToolPostInvokePayload",  # 도구 사후 호출 페이로드
    "ToolPostInvokeResult",   # 도구 사후 호출 결과

    "ResourcePreFetchPayload", # 리소스 사전 페치 페이로드
    "ResourcePreFetchResult",  # 리소스 사전 페치 결과
    "ResourcePostFetchPayload", # 리소스 사후 페치 페이로드
    "ResourcePostFetchResult",  # 리소스 사후 페치 결과
]
