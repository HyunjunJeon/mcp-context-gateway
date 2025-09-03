# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/utils.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor, Mihai Criveti

플러그인 계층을 위한 유틸리티 모듈.
이 모듈은 플러그인과 관련된 유틸리티 함수들을 구현합니다.
"""

# Standard - 표준 라이브러리 import
from functools import cache  # 함수 결과 캐싱을 위한 데코레이터
import importlib           # 동적 모듈 임포트를 위한 모듈
from types import ModuleType  # 모듈 타입 힌팅을 위한 클래스

# First-Party - 플러그인 프레임워크 모델들
from mcpgateway.plugins.framework.models import (
    GlobalContext,           # 전역 컨텍스트
    PluginCondition,         # 플러그인 실행 조건
    PromptPosthookPayload,   # 프롬프트 사후 후크 페이로드
    PromptPrehookPayload,    # 프롬프트 사전 후크 페이로드
    ResourcePostFetchPayload, # 리소스 사후 페치 페이로드
    ResourcePreFetchPayload,  # 리소스 사전 페치 페이로드
    ToolPostInvokePayload,   # 도구 사후 호출 페이로드
    ToolPreInvokePayload,    # 도구 사전 호출 페이로드
)


@cache  # noqa - 캐시 데코레이터로 함수 결과를 캐싱하여 성능 향상
def import_module(mod_name: str) -> ModuleType:
    """모듈을 동적으로 임포트합니다.

    이 함수는 캐싱을 통해 동일한 모듈에 대한 반복적인 임포트를 최적화합니다.

    Args:
        mod_name: 완전한 모듈 이름 (예: 'package.module')

    Returns:
        임포트된 모듈 객체

    Examples:
        >>> import sys
        >>> mod = import_module('sys')
        >>> mod is sys
        True
        >>> os_mod = import_module('os')
        >>> hasattr(os_mod, 'path')
        True
    """
    return importlib.import_module(mod_name)


def parse_class_name(name: str) -> tuple[str, str]:
    """클래스 이름을 모듈 경로와 클래스명으로 분리합니다.

    완전한 클래스 이름(예: 'package.module.ClassName')을
    모듈 경로('package.module')와 클래스명('ClassName')으로 분리합니다.

    Args:
        name: 정규화된 클래스 이름

    Returns:
        모듈 경로와 클래스명으로 이루어진 튜플

    Examples:
        >>> parse_class_name('module.submodule.ClassName')
        ('module.submodule', 'ClassName')
        >>> parse_class_name('SimpleClass')
        ('', 'SimpleClass')
        >>> parse_class_name('package.Class')
        ('package', 'Class')
    """
    # 오른쪽에서 첫 번째 점('.')을 기준으로 분리
    clslist = name.rsplit(".", 1)

    # 점이 있는 경우 (패키지.클래스 형식)
    if len(clslist) == 2:
        return (clslist[0], clslist[1])

    # 점이 없는 경우 (단순 클래스명)
    return ("", name)


def matches(condition: PluginCondition, context: GlobalContext) -> bool:
    """플러그인 조건이 현재 컨텍스트와 일치하는지 확인합니다.

    플러그인의 실행 조건들과 현재의 전역 컨텍스트를 비교하여
    플러그인이 실행되어야 하는지 여부를 결정합니다.

    Args:
        condition: 플러그인의 실행에 필요한 조건들
        context: 전역 컨텍스트 정보

    Returns:
        조건이 일치하면 True, 그렇지 않으면 False

    Examples:
        >>> from mcpgateway.plugins.framework import GlobalContext, PluginCondition
        >>> cond = PluginCondition(server_ids={"srv1", "srv2"})
        >>> ctx = GlobalContext(request_id="req1", server_id="srv1")
        >>> matches(cond, ctx)
        True
        >>> ctx2 = GlobalContext(request_id="req2", server_id="srv3")
        >>> matches(cond, ctx2)
        False
        >>> cond2 = PluginCondition(user_patterns=["admin"])
        >>> ctx3 = GlobalContext(request_id="req3", user="admin_user")
        >>> matches(cond2, ctx3)
        True
    """
    # 서버 ID 확인 - 지정된 서버에서만 실행되는 경우
    if condition.server_ids and context.server_id not in condition.server_ids:
        return False

    # 테넌트 ID 확인 - 지정된 테넌트에서만 실행되는 경우
    if condition.tenant_ids and context.tenant_id not in condition.tenant_ids:
        return False

    # 사용자 패턴 확인 - 간단한 포함 검사 (정규식으로 확장 가능)
    if condition.user_patterns and context.user:
        # 사용자 이름에 지정된 패턴 중 하나라도 포함되어 있는지 확인
        if not any(pattern in context.user for pattern in condition.user_patterns):
            return False

    # 모든 조건을 통과한 경우 True 반환
    return True


def pre_prompt_matches(payload: PromptPrehookPayload, conditions: list[PluginCondition], context: GlobalContext) -> bool:
    """프롬프트 사전 후크에 대한 일치 여부를 확인합니다.

    프롬프트가 렌더링되기 전에 플러그인의 조건들과 페이로드를 비교하여
    해당 플러그인이 실행되어야 하는지 결정합니다.

    Args:
        payload: 프롬프트 사전 후크 페이로드
        conditions: 플러그인의 실행에 필요한 조건들 목록
        context: 전역 컨텍스트

    Returns:
        플러그인이 조건에 일치하면 True

    Examples:
        >>> from mcpgateway.plugins.framework import PluginCondition, PromptPrehookPayload, GlobalContext
        >>> payload = PromptPrehookPayload(name="greeting", args={})
        >>> cond = PluginCondition(prompts={"greeting"})
        >>> ctx = GlobalContext(request_id="req1")
        >>> pre_prompt_matches(payload, [cond], ctx)
        True
        >>> payload2 = PromptPrehookPayload(name="other", args={})
        >>> pre_prompt_matches(payload2, [cond], ctx)
        False
    """
    # 초기 결과값 설정
    current_result = True

    # 각 조건에 대해 순차적으로 검사
    for index, condition in enumerate(conditions):
        # 기본 컨텍스트 매칭 확인 (서버, 테넌트, 사용자 패턴 등)
        if not matches(condition, context):
            current_result = False

        # 프롬프트 이름이 지정된 프롬프트 목록에 포함되는지 확인
        if condition.prompts and payload.name not in condition.prompts:
            current_result = False

        # 현재 조건을 모두 만족하는 경우 True 반환
        if current_result:
            return True

        # 마지막 조건이 아닌 경우 다음 조건 검사를 위해 결과 초기화
        if index < len(conditions) - 1:
            current_result = True

    # 모든 조건을 검사한 결과 반환
    return current_result


def post_prompt_matches(payload: PromptPosthookPayload, conditions: list[PluginCondition], context: GlobalContext) -> bool:
    """프롬프트 사후 후크에 대한 일치 여부를 확인합니다.

    프롬프트가 렌더링된 후에 플러그인의 조건들과 페이로드를 비교하여
    해당 플러그인이 실행되어야 하는지 결정합니다.

    Args:
        payload: 프롬프트 사후 후크 페이로드
        conditions: 플러그인의 실행에 필요한 조건들 목록
        context: 전역 컨텍스트

    Returns:
        플러그인이 조건에 일치하면 True
    """
    # 초기 결과값 설정
    current_result = True

    # 각 조건에 대해 순차적으로 검사
    for index, condition in enumerate(conditions):
        # 기본 컨텍스트 매칭 확인 (서버, 테넌트, 사용자 패턴 등)
        if not matches(condition, context):
            current_result = False

        # 프롬프트 이름이 지정된 프롬프트 목록에 포함되는지 확인
        if condition.prompts and payload.name not in condition.prompts:
            current_result = False

        # 현재 조건을 모두 만족하는 경우 True 반환
        if current_result:
            return True

        # 마지막 조건이 아닌 경우 다음 조건 검사를 위해 결과 초기화
        if index < len(conditions) - 1:
            current_result = True

    # 모든 조건을 검사한 결과 반환
    return current_result


def pre_tool_matches(payload: ToolPreInvokePayload, conditions: list[PluginCondition], context: GlobalContext) -> bool:
    """도구 사전 호출 후크에 대한 일치 여부를 확인합니다.

    도구가 호출되기 전에 플러그인의 조건들과 페이로드를 비교하여
    해당 플러그인이 실행되어야 하는지 결정합니다.

    Args:
        payload: 도구 사전 호출 페이로드
        conditions: 플러그인의 실행에 필요한 조건들 목록
        context: 전역 컨텍스트

    Returns:
        플러그인이 조건에 일치하면 True

    Examples:
        >>> from mcpgateway.plugins.framework import PluginCondition, ToolPreInvokePayload, GlobalContext
        >>> payload = ToolPreInvokePayload(name="calculator", args={})
        >>> cond = PluginCondition(tools={"calculator"})
        >>> ctx = GlobalContext(request_id="req1")
        >>> pre_tool_matches(payload, [cond], ctx)
        True
        >>> payload2 = ToolPreInvokePayload(name="other", args={})
        >>> pre_tool_matches(payload2, [cond], ctx)
        False
    """
    # 초기 결과값 설정
    current_result = True

    # 각 조건에 대해 순차적으로 검사
    for index, condition in enumerate(conditions):
        # 기본 컨텍스트 매칭 확인 (서버, 테넌트, 사용자 패턴 등)
        if not matches(condition, context):
            current_result = False

        # 도구 이름이 지정된 도구 목록에 포함되는지 확인
        if condition.tools and payload.name not in condition.tools:
            current_result = False

        # 현재 조건을 모두 만족하는 경우 True 반환
        if current_result:
            return True

        # 마지막 조건이 아닌 경우 다음 조건 검사를 위해 결과 초기화
        if index < len(conditions) - 1:
            current_result = True

    # 모든 조건을 검사한 결과 반환
    return current_result


def post_tool_matches(payload: ToolPostInvokePayload, conditions: list[PluginCondition], context: GlobalContext) -> bool:
    """도구 사후 호출 후크에 대한 일치 여부를 확인합니다.

    도구가 호출된 후에 플러그인의 조건들과 페이로드를 비교하여
    해당 플러그인이 실행되어야 하는지 결정합니다.

    Args:
        payload: 도구 사후 호출 페이로드
        conditions: 플러그인의 실행에 필요한 조건들 목록
        context: 전역 컨텍스트

    Returns:
        플러그인이 조건에 일치하면 True

    Examples:
        >>> from mcpgateway.plugins.framework import PluginCondition, ToolPostInvokePayload, GlobalContext
        >>> payload = ToolPostInvokePayload(name="calculator", result={"result": 8})
        >>> cond = PluginCondition(tools={"calculator"})
        >>> ctx = GlobalContext(request_id="req1")
        >>> post_tool_matches(payload, [cond], ctx)
        True
        >>> payload2 = ToolPostInvokePayload(name="other", result={"result": 8})
        >>> post_tool_matches(payload2, [cond], ctx)
        False
    """
    current_result = True
    for index, condition in enumerate(conditions):
        if not matches(condition, context):
            current_result = False

        if condition.tools and payload.name not in condition.tools:
            current_result = False
        if current_result:
            return True
        if index < len(conditions) - 1:
            current_result = True
    return current_result


def pre_resource_matches(payload: ResourcePreFetchPayload, conditions: list[PluginCondition], context: GlobalContext) -> bool:
    """리소스 사전 페치 후크에 대한 일치 여부를 확인합니다.

    리소스가 페치되기 전에 플러그인의 조건들과 페이로드를 비교하여
    해당 플러그인이 실행되어야 하는지 결정합니다.

    Args:
        payload: 리소스 사전 페치 페이로드
        conditions: 플러그인의 실행에 필요한 조건들 목록
        context: 전역 컨텍스트

    Returns:
        플러그인이 조건에 일치하면 True

    Examples:
        >>> from mcpgateway.plugins.framework import PluginCondition, ResourcePreFetchPayload, GlobalContext
        >>> payload = ResourcePreFetchPayload(uri="file:///data.txt")
        >>> cond = PluginCondition(resources={"file:///data.txt"})
        >>> ctx = GlobalContext(request_id="req1")
        >>> pre_resource_matches(payload, [cond], ctx)
        True
        >>> payload2 = ResourcePreFetchPayload(uri="http://api/other")
        >>> pre_resource_matches(payload2, [cond], ctx)
        False
    """
    current_result = True
    for index, condition in enumerate(conditions):
        if not matches(condition, context):
            current_result = False

        if condition.resources and payload.uri not in condition.resources:
            current_result = False
        if current_result:
            return True
        if index < len(conditions) - 1:
            current_result = True
    return current_result


def post_resource_matches(payload: ResourcePostFetchPayload, conditions: list[PluginCondition], context: GlobalContext) -> bool:
    """리소스 사후 페치 후크에 대한 일치 여부를 확인합니다.

    리소스가 페치된 후에 플러그인의 조건들과 페이로드를 비교하여
    해당 플러그인이 실행되어야 하는지 결정합니다.

    Args:
        payload: 리소스 사후 페치 페이로드
        conditions: 플러그인의 실행에 필요한 조건들 목록
        context: 전역 컨텍스트

    Returns:
        플러그인이 조건에 일치하면 True

    Examples:
        >>> from mcpgateway.plugins.framework import PluginCondition, ResourcePostFetchPayload, GlobalContext
        >>> from mcpgateway.models import ResourceContent
        >>> content = ResourceContent(type="resource", uri="file:///data.txt", text="Test")
        >>> payload = ResourcePostFetchPayload(uri="file:///data.txt", content=content)
        >>> cond = PluginCondition(resources={"file:///data.txt"})
        >>> ctx = GlobalContext(request_id="req1")
        >>> post_resource_matches(payload, [cond], ctx)
        True
        >>> payload2 = ResourcePostFetchPayload(uri="http://api/other", content=content)
        >>> post_resource_matches(payload2, [cond], ctx)
        False
    """
    current_result = True
    for index, condition in enumerate(conditions):
        if not matches(condition, context):
            current_result = False

        if condition.resources and payload.uri not in condition.resources:
            current_result = False
        if current_result:
            return True
        if index < len(conditions) - 1:
            current_result = True
    return current_result
