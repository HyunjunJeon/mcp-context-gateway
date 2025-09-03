# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/models.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor, Mihai Criveti

플러그인을 위한 Pydantic 모델들.
이 모듈은 기본 플러그인 계층과 관련된 Pydantic 모델들을 구현합니다.
설정, 컨텍스트, 오류 모델들을 포함합니다.
"""

# Standard - 표준 라이브러리 import
from enum import Enum        # 열거형을 위한 모듈
from pathlib import Path     # 파일 경로 처리를 위한 모듈
from typing import Any, Generic, Optional, Self, TypeVar  # 타입 힌팅을 위한 모듈들

# Third-Party - 서드파티 라이브러리 import
from pydantic import BaseModel, field_serializer, field_validator, model_validator, PrivateAttr, ValidationInfo  # Pydantic 모델 관련 클래스들

# First-Party - 프로젝트 내부 모듈 import
from mcpgateway.models import PromptResult  # 프롬프트 결과 모델
from mcpgateway.plugins.framework.constants import AFTER, EXTERNAL_PLUGIN_TYPE, IGNORE_CONFIG_EXTERNAL, PYTHON_SUFFIX, SCRIPT, URL  # 플러그인 상수들
from mcpgateway.schemas import TransportType  # 전송 타입 스키마
from mcpgateway.validators import SecurityValidator  # 보안 검증 유틸리티

# 제네릭 타입 변수 정의
T = TypeVar("T")


class HookType(str, Enum):
    """MCP Forge Gateway 후크 포인트들.

    Attributes:
        prompt_pre_fetch: 프롬프트 사전 페치 후크
        prompt_post_fetch: 프롬프트 사후 페치 후크
        tool_pre_invoke: 도구 사전 호출 후크
        tool_post_invoke: 도구 사후 호출 후크
        resource_pre_fetch: 리소스 사전 페치 후크
        resource_post_fetch: 리소스 사후 페치 후크

    Examples:
        >>> HookType.PROMPT_PRE_FETCH
        <HookType.PROMPT_PRE_FETCH: 'prompt_pre_fetch'>
        >>> HookType.PROMPT_PRE_FETCH.value
        'prompt_pre_fetch'
        >>> HookType('prompt_post_fetch')
        <HookType.PROMPT_POST_FETCH: 'prompt_post_fetch'>
        >>> list(HookType)  # doctest: +ELLIPSIS
        [<HookType.PROMPT_PRE_FETCH: 'prompt_pre_fetch'>, <HookType.PROMPT_POST_FETCH: 'prompt_post_fetch'>, <HookType.TOOL_PRE_INVOKE: 'tool_pre_invoke'>, <HookType.TOOL_POST_INVOKE: 'tool_post_invoke'>, ...]
    """

    # 프롬프트 관련 후크 포인트들
    PROMPT_PRE_FETCH = "prompt_pre_fetch"    # 프롬프트 렌더링 전 실행
    PROMPT_POST_FETCH = "prompt_post_fetch"  # 프롬프트 렌더링 후 실행

    # 도구 관련 후크 포인트들
    TOOL_PRE_INVOKE = "tool_pre_invoke"      # 도구 호출 전 실행
    TOOL_POST_INVOKE = "tool_post_invoke"    # 도구 호출 후 실행

    # 리소스 관련 후크 포인트들
    RESOURCE_PRE_FETCH = "resource_pre_fetch"   # 리소스 페치 전 실행
    RESOURCE_POST_FETCH = "resource_post_fetch" # 리소스 페치 후 실행


class PluginMode(str, Enum):
    """플러그인의 작동 모드.

    Attributes:
       enforce: 플러그인 결과를 강제 적용합니다.
       permissive: 결과를 감사하지만 강제 적용하지 않습니다.
       disabled: 플러그인이 비활성화됩니다.

    Examples:
        >>> PluginMode.ENFORCE
        <PluginMode.ENFORCE: 'enforce'>
        >>> PluginMode.PERMISSIVE.value
        'permissive'
        >>> PluginMode('disabled')
        <PluginMode.DISABLED: 'disabled'>
        >>> 'enforce' in [m.value for m in PluginMode]
        True
    """

    # 플러그인 모드 값들
    ENFORCE = "enforce"        # 강제 모드 - 플러그인 결과를 무조건 적용
    PERMISSIVE = "permissive"  # 허용 모드 - 결과를 감사하지만 강제하지 않음
    DISABLED = "disabled"      # 비활성화 모드 - 플러그인 실행하지 않음


class ToolTemplate(BaseModel):
    """도구 템플릿.

    Attributes:
        tool_name (str): 도구의 이름
        fields (Optional[list[str]]): 영향을 받는 도구 필드들
        result (bool): True인 경우 도구 출력을 분석

    Examples:
        >>> tool = ToolTemplate(tool_name="my_tool")
        >>> tool.tool_name
        'my_tool'
        >>> tool.result
        False
        >>> tool2 = ToolTemplate(tool_name="analyzer", fields=["input", "params"], result=True)
        >>> tool2.fields
        ['input', 'params']
        >>> tool2.result
        True
    """

    # 도구 템플릿 필드들
    tool_name: str                         # 도구의 고유 이름
    fields: Optional[list[str]] = None     # 플러그인이 적용될 필드 목록
    result: bool = False                   # 도구 결과를 분석할지 여부


class PromptTemplate(BaseModel):
    """프롬프트 템플릿.

    Attributes:
        prompt_name (str): 프롬프트의 이름
        fields (Optional[list[str]]): 영향을 받는 프롬프트 필드들
        result (bool): True인 경우 도구 출력을 분석

    Examples:
        >>> prompt = PromptTemplate(prompt_name="greeting")
        >>> prompt.prompt_name
        'greeting'
        >>> prompt.result
        False
        >>> prompt2 = PromptTemplate(prompt_name="question", fields=["context"], result=True)
        >>> prompt2.fields
        ['context']
    """

    # 프롬프트 템플릿 필드들
    prompt_name: str                       # 프롬프트의 고유 이름
    fields: Optional[list[str]] = None     # 플러그인이 적용될 필드 목록
    result: bool = False                   # 프롬프트 결과를 분석할지 여부


class ResourceTemplate(BaseModel):
    """리소스 템플릿.

    Attributes:
        resource_uri (str): 리소스의 URI
        fields (Optional[list[str]]): 영향을 받는 리소스 필드들
        result (bool): True인 경우 리소스 출력을 분석

    Examples:
        >>> resource = ResourceTemplate(resource_uri="file:///data.txt")
        >>> resource.resource_uri
        'file:///data.txt'
        >>> resource.result
        False
        >>> resource2 = ResourceTemplate(resource_uri="http://api/data", fields=["content"], result=True)
        >>> resource2.fields
        ['content']
    """

    # 리소스 템플릿 필드들
    resource_uri: str                      # 리소스의 URI 경로
    fields: Optional[list[str]] = None     # 플러그인이 적용될 필드 목록
    result: bool = False                   # 리소스 결과를 분석할지 여부


class PluginCondition(BaseModel):
    """플러그인이 실행되어야 하는 조건들.

    Attributes:
        server_ids (Optional[set[str]]): 서버 ID들의 집합
        tenant_ids (Optional[set[str]]): 테넌트 ID들의 집합
        tools (Optional[set[str]]): 도구 이름들의 집합
        prompts (Optional[set[str]]): 프롬프트 이름들의 집합
        resources (Optional[set[str]]): 리소스 URI들의 집합
        user_patterns (Optional[list[str]]): 사용자 패턴 목록
        content_types (Optional[list[str]]): 콘텐츠 타입 목록

    Examples:
        >>> cond = PluginCondition(server_ids={"server1", "server2"})
        >>> "server1" in cond.server_ids
        True
        >>> cond2 = PluginCondition(tools={"tool1"}, prompts={"prompt1"})
        >>> cond2.tools
        {'tool1'}
        >>> cond3 = PluginCondition(user_patterns=["admin", "root"])
        >>> len(cond3.user_patterns)
        2
    """

    # 플러그인 실행 조건 필드들
    server_ids: Optional[set[str]] = None      # 특정 서버에서만 실행
    tenant_ids: Optional[set[str]] = None      # 특정 테넌트에서만 실행
    tools: Optional[set[str]] = None           # 특정 도구에만 적용
    prompts: Optional[set[str]] = None         # 특정 프롬프트에만 적용
    resources: Optional[set[str]] = None       # 특정 리소스에만 적용
    user_patterns: Optional[list[str]] = None  # 특정 사용자 패턴에만 적용
    content_types: Optional[list[str]] = None  # 특정 콘텐츠 타입에만 적용

    @field_serializer("server_ids", "tenant_ids", "tools", "prompts")
    def serialize_set(self, value: set[str] | None) -> list[str] | None:
        """MCP를 위한 PluginCondition의 set 객체들을 직렬화합니다.

        Args:
            value: 서버 ID, 테넌트 ID, 도구 또는 프롬프트들의 집합

        Returns:
            직렬화 가능한 리스트 형태의 집합
        """
        # 값이 있는 경우 리스트로 변환
        if value:
            values = []
            for key in value:
                values.append(key)
            return values
        return None


class AppliedTo(BaseModel):
    """플러그인이 적용될 도구/프롬프트/리소스 및 필드들.

    Attributes:
        tools (Optional[list[ToolTemplate]]): 적용될 도구와 필드들
        prompts (Optional[list[PromptTemplate]]): 적용될 프롬프트와 필드들
        resources (Optional[list[ResourceTemplate]]): 적용될 리소스와 필드들
    """

    # 플러그인 적용 대상들
    tools: Optional[list[ToolTemplate]] = None       # 적용될 도구 템플릿들
    prompts: Optional[list[PromptTemplate]] = None   # 적용될 프롬프트 템플릿들
    resources: Optional[list[ResourceTemplate]] = None  # 적용될 리소스 템플릿들


class MCPConfig(BaseModel):
    """외부 MCP 플러그인 객체들을 위한 MCP 설정.

    Attributes:
        proto (TransportType): MCP 전송 타입. SSE, STDIO, 또는 STREAMABLEHTTP일 수 있음
        url (Optional[str]): MCP URL. MCP 전송 타입이 SSE 또는 STREAMABLEHTTP일 때만 유효
        script (Optional[str]): 플러그인 서버를 실행하는 STDIO 스크립트의 경로와 이름. STDIO 타입에서만 유효
    """

    # MCP 설정 필드들
    proto: TransportType                    # 전송 프로토콜 (SSE, STDIO, STREAMABLEHTTP)
    url: Optional[str] = None              # MCP 서버 URL (HTTP 전송 시 사용)
    script: Optional[str] = None           # STDIO 스크립트 경로

    @field_validator(URL, mode=AFTER)
    @classmethod
    def validate_url(cls, url: str | None) -> str | None:
        """스트림 가능한 HTTP 연결을 위한 MCP URL을 검증합니다.

        Args:
            url: 검증할 URL

        Raises:
            ValueError: URL 검증에 실패한 경우

        Returns:
            검증된 URL 또는 설정되지 않은 경우 None
        """
        if url:
            # 보안 검증을 통해 URL 유효성 확인
            result = SecurityValidator.validate_url(url)
            return result
        return url

    @field_validator(SCRIPT, mode=AFTER)
    @classmethod
    def validate_script(cls, script: str | None) -> str | None:
        """MCP STDIO 스크립트를 검증합니다.

        Args:
            script: 검증할 스크립트

        Raises:
            ValueError: 스크립트가 존재하지 않거나 .py 확장자가 없는 경우

        Returns:
            검증된 문자열 또는 설정되지 않은 경우 None
        """
        if script:
            file_path = Path(script)
            # 파일 존재 여부 확인
            if not file_path.is_file():
                raise ValueError(f"MCP 서버 스크립트 {script}이(가) 존재하지 않습니다.")
            # Python 파일 확장자 확인
            if file_path.suffix != PYTHON_SUFFIX:
                raise ValueError(f"MCP 서버 스크립트 {script}에 .py 확장자가 없습니다.")
        return script


class PluginConfig(BaseModel):
    """플러그인 설정.

    Attributes:
        name (str): 플러그인의 고유 이름
        description (str): 플러그인 설명
        author (str): 플러그인 작성자
        kind (str): 플러그인의 종류 또는 타입. 일반적으로 완전한 객체 타입
        namespace (str): 플러그인이 위치한 네임스페이스
        version (str): 플러그인의 버전
        hooks (list[HookType]): 플러그인이 호출될 후크 포인트들의 목록
        tags (list[str]): 플러그인을 검색할 수 있도록 하는 태그 목록
        mode (PluginMode): 플러그인이 활성화되어 있는지 여부
        priority (int): 플러그인이 실행되는 순서. 낮은 값이 높은 우선순위
        conditions (Optional[list[PluginCondition]]): 플러그인이 실행되는 조건들
        applied_to (Optional[list[AppliedTo]]): 플러그인이 적용될 도구, 필드들
        config (dict[str, Any]): 플러그인별 특정 설정들
        mcp (Optional[MCPConfig]): kind가 "external"일 때의 외부 플러그인을 위한 MCP 설정
    """

    # 기본 플러그인 정보
    name: str                                    # 플러그인의 고유 식별자
    description: Optional[str] = None           # 플러그인에 대한 설명
    author: Optional[str] = None                # 플러그인 작성자 정보
    kind: str                                   # 플러그인 타입 (클래스 경로)
    namespace: Optional[str] = None             # 플러그인 네임스페이스
    version: Optional[str] = None               # 플러그인 버전

    # 실행 관련 설정
    hooks: Optional[list[HookType]] = None      # 적용될 후크 포인트들
    tags: Optional[list[str]] = None            # 검색을 위한 태그들
    mode: PluginMode = PluginMode.ENFORCE       # 플러그인 실행 모드
    priority: Optional[int] = None              # 실행 우선순위 (낮을수록 높음)

    # 적용 조건 및 대상
    conditions: Optional[list[PluginCondition]] = None  # 실행 조건들
    applied_to: Optional[list[AppliedTo]] = None        # 적용 대상들

    # 설정 및 외부 연결
    config: Optional[dict[str, Any]] = None     # 플러그인별 설정
    mcp: Optional[MCPConfig] = None             # 외부 MCP 연결 설정

    @model_validator(mode=AFTER)
    def check_url_or_script_filled(self) -> Self:  # pylint: disable=bad-classmethod-argument
        """MCP 서버 설정에 따라 URL 또는 스크립트 중 하나가 설정되어 있는지 확인합니다.

        Raises:
            ValueError: STDIO 설정 시 스크립트가 정의되지 않았거나 HTTP 전송 시 URL이 정의되지 않은 경우

        Returns:
            검증 후의 모델
        """
        if not self.mcp:
            return self
        if self.mcp.proto == TransportType.STDIO and not self.mcp.script:
            raise ValueError(f"플러그인 {self.name}의 전송 타입이 STDIO로 설정되었으나 스크립트 값이 없습니다")
        if self.mcp.proto in (TransportType.STREAMABLEHTTP, TransportType.SSE) and not self.mcp.url:
            raise ValueError(f"플러그인 {self.name}의 전송 타입이 HTTP로 설정되었으나 URL 값이 없습니다")
        if self.mcp.proto not in (TransportType.SSE, TransportType.STREAMABLEHTTP, TransportType.STDIO):
            raise ValueError(f"플러그인 {self.name}은 전송 타입을 SSE, STREAMABLEHTTP 또는 STDIO 중 하나로 설정해야 합니다")
        return self

    @model_validator(mode=AFTER)
    def check_config_and_external(self, info: ValidationInfo) -> Self:  # pylint: disable=bad-classmethod-argument
        """플러그인의 kind가 'external'일 때 'config' 섹션이 정의되지 않았는지 확인합니다. 외부 플러그인의 경우 개발자가 플러그인 설정 섹션의 항목들을 재정의할 수 없기 때문입니다.

        Args:
            info: Pydantic 모델 검증 중 전달되는 컨텍스트 정보. 검증 순서를 결정하는 데 사용됩니다.

        Raises:
            ValueError: STDIO 설정 시 스크립트가 정의되지 않았거나 HTTP 전송 시 URL이 정의되지 않은 경우

        Returns:
            검증 후의 모델
        """
        ignore_config_external = False
        if info and info.context and IGNORE_CONFIG_EXTERNAL in info.context:
            ignore_config_external = info.context[IGNORE_CONFIG_EXTERNAL]

        if not ignore_config_external and self.config and self.kind == EXTERNAL_PLUGIN_TYPE:
            raise ValueError(f"""외부 플러그인 {self.name}에 'config' 섹션을 설정할 수 없습니다.""" """'config' 섹션 설정은 플러그인 서버에서만 가능합니다.""")

        if self.kind == EXTERNAL_PLUGIN_TYPE and not self.mcp:
            raise ValueError(f"외부 플러그인 {self.name}에는 'mcp' 섹션을 설정해야 합니다")

        return self


class PluginManifest(BaseModel):
    """플러그인 매니페스트.

    Attributes:
        description (str): 플러그인 설명
        author (str): 플러그인 작성자
        version (str): 플러그인 버전
        tags (list[str]): 플러그인을 검색할 수 있도록 하는 태그 목록
        available_hooks (list[str]): 플러그인이 호출 가능한 후크 포인트 목록
        default_config (dict[str, Any]): 기본 설정들
    """

    # 플러그인 매니페스트 필드들
    description: str                       # 플러그인 설명
    author: str                            # 플러그인 작성자
    version: str                           # 플러그인 버전
    tags: list[str]                        # 검색 태그들
    available_hooks: list[str]             # 사용 가능한 후크들
    default_config: dict[str, Any]         # 기본 설정


class PluginErrorModel(BaseModel):
    """외부 플러그인 내부의 예외/오류를 나타내는 플러그인 오류.

    Attributes:
        message (str): 오류 이유
        code (str): 오류 코드
        details (dict[str, Any]): 추가 오류 세부 사항
        plugin_name (str): 플러그인 이름
    """

    # 플러그인 오류 필드들
    message: str                           # 오류 메시지
    code: Optional[str] = ""               # 오류 코드
    details: Optional[dict[str, Any]] = {} # 오류 세부 사항
    plugin_name: str                       # 오류가 발생한 플러그인


class PluginViolation(BaseModel):
    """정책 위반을 나타내는 플러그인 위반사항.

    Attributes:
        reason (str): 위반 이유
        description (str): 위반에 대한 더 자세한 설명
        code (str): 위반 코드
        details (dict[str, Any]): 추가 위반 세부 사항
        _plugin_name (str): 플러그인 이름, 플러그인 관리자에 의해 설정되는 비공개 속성

    Examples:
        >>> violation = PluginViolation(
        ...     reason="Invalid input",
        ...     description="The input contains prohibited content",
        ...     code="PROHIBITED_CONTENT",
        ...     details={"field": "message", "value": "test"}
        ... )
        >>> violation.reason
        'Invalid input'
        >>> violation.code
        'PROHIBITED_CONTENT'
        >>> violation.plugin_name = "content_filter"
        >>> violation.plugin_name
        'content_filter'
    """

    # 플러그인 위반 필드들
    reason: str                          # 위반 이유
    description: str                     # 위반 설명
    code: str                            # 위반 코드
    details: dict[str, Any]              # 위반 세부 사항
    _plugin_name: str = PrivateAttr(default="")  # 플러그인 이름 (비공개)

    @property
    def plugin_name(self) -> str:
        """플러그인 이름 속성의 getter.

        Returns:
            위반사항과 연관된 플러그인 이름
        """
        return self._plugin_name

    @plugin_name.setter
    def plugin_name(self, name: str) -> None:
        """플러그인 이름 속성의 setter.

        Args:
            name: 플러그인 이름

        Raises:
            ValueError: 이름이 비어있거나 문자열이 아닌 경우
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("이름은 비어있지 않은 문자열이어야 합니다.")
        self._plugin_name = name


class PluginSettings(BaseModel):
    """전역 플러그인 설정.

    Attributes:
        parallel_execution_within_band (bool): 동일한 우선순위의 플러그인을 병렬로 실행
        plugin_timeout (int): 플러그인 작업의 타임아웃 값
        fail_on_plugin_error (bool): 플러그인 연결 오류 발생 시 에러 처리 여부
        enable_plugin_api (bool): 플러그인을 전역적으로 활성화 또는 비활성화
        plugin_health_check_interval (int): 헬스 체크 간격
    """

    # 전역 플러그인 설정 필드들
    parallel_execution_within_band: bool = False  # 동일 우선순위 플러그인 병렬 실행
    plugin_timeout: int = 30                     # 플러그인 타임아웃 (초)
    fail_on_plugin_error: bool = False           # 플러그인 오류 시 실패 처리
    enable_plugin_api: bool = False              # 플러그인 API 활성화
    plugin_health_check_interval: int = 60       # 헬스 체크 간격 (초)


class Config(BaseModel):
    """플러그인을 위한 설정들.

    Attributes:
        plugins: 활성화할 플러그인 목록
        plugin_dirs: 플러그인을 찾을 디렉토리들
        plugin_settings: 플러그인을 위한 전역 설정
    """

    # 플러그인 설정 필드들
    plugins: Optional[list[PluginConfig]] = []  # 활성화할 플러그인들
    plugin_dirs: list[str] = []                 # 플러그인 검색 디렉토리들
    plugin_settings: PluginSettings             # 전역 플러그인 설정


class PromptPrehookPayload(BaseModel):
    """프롬프트 사전 후크를 위한 프롬프트 페이로드.

    Attributes:
        name (str): 프롬프트 템플릿의 이름
        args (dict[str,str]): 프롬프트 템플릿 인자들

    Examples:
        >>> payload = PromptPrehookPayload(name="test_prompt", args={"user": "alice"})
        >>> payload.name
        'test_prompt'
        >>> payload.args
        {'user': 'alice'}
        >>> payload2 = PromptPrehookPayload(name="empty")
        >>> payload2.args
        {}
        >>> p = PromptPrehookPayload(name="greeting", args={"name": "Bob", "time": "morning"})
        >>> p.name
        'greeting'
        >>> p.args["name"]
        'Bob'
    """

    # 프롬프트 사전 후크 페이로드 필드들
    name: str                                    # 프롬프트 템플릿 이름
    args: Optional[dict[str, str]] = {}          # 프롬프트 템플릿 인자들


class PromptPosthookPayload(BaseModel):
    """A prompt payload for a prompt posthook.

    Attributes:
        name (str): The prompt name.
        result (PromptResult): The prompt after its template is rendered.

     Examples:
        >>> from mcpgateway.models import PromptResult, Message, TextContent
        >>> msg = Message(role="user", content=TextContent(type="text", text="Hello World"))
        >>> result = PromptResult(messages=[msg])
        >>> payload = PromptPosthookPayload(name="greeting", result=result)
        >>> payload.name
        'greeting'
        >>> payload.result.messages[0].content.text
        'Hello World'
        >>> from mcpgateway.models import PromptResult, Message, TextContent
        >>> msg = Message(role="assistant", content=TextContent(type="text", text="Test output"))
        >>> r = PromptResult(messages=[msg])
        >>> p = PromptPosthookPayload(name="test", result=r)
        >>> p.name
        'test'
    """

    name: str
    result: PromptResult


class PluginResult(BaseModel, Generic[T]):
    """A result of the plugin hook processing. The actual type is dependent on the hook.

    Attributes:
            continue_processing (bool): Whether to stop processing.
            modified_payload (Optional[Any]): The modified payload if the plugin is a transformer.
            violation (Optional[PluginViolation]): violation object.
            metadata (Optional[dict[str, Any]]): additional metadata.

     Examples:
        >>> result = PluginResult()
        >>> result.continue_processing
        True
        >>> result.metadata
        {}
        >>> from mcpgateway.plugins.framework import PluginViolation
        >>> violation = PluginViolation(
        ...     reason="Test", description="Test desc", code="TEST", details={}
        ... )
        >>> result2 = PluginResult(continue_processing=False, violation=violation)
        >>> result2.continue_processing
        False
        >>> result2.violation.code
        'TEST'
        >>> r = PluginResult(metadata={"key": "value"})
        >>> r.metadata["key"]
        'value'
        >>> r2 = PluginResult(continue_processing=False)
        >>> r2.continue_processing
        False
    """

    continue_processing: bool = True
    modified_payload: Optional[T] = None
    violation: Optional[PluginViolation] = None
    metadata: Optional[dict[str, Any]] = {}


PromptPrehookResult = PluginResult[PromptPrehookPayload]
PromptPosthookResult = PluginResult[PromptPosthookPayload]


class ToolPreInvokePayload(BaseModel):
    """A tool payload for a tool pre-invoke hook.

    Args:
        name: The tool name.
        args: The tool arguments for invocation.

    Examples:
        >>> payload = ToolPreInvokePayload(name="test_tool", args={"input": "data"})
        >>> payload.name
        'test_tool'
        >>> payload.args
        {'input': 'data'}
        >>> payload2 = ToolPreInvokePayload(name="empty")
        >>> payload2.args
        {}
        >>> p = ToolPreInvokePayload(name="calculator", args={"operation": "add", "a": 5, "b": 3})
        >>> p.name
        'calculator'
        >>> p.args["operation"]
        'add'

    """

    name: str
    args: Optional[dict[str, Any]] = {}


class ToolPostInvokePayload(BaseModel):
    """A tool payload for a tool post-invoke hook.

    Args:
        name: The tool name.
        result: The tool invocation result.

    Examples:
        >>> payload = ToolPostInvokePayload(name="calculator", result={"result": 8, "status": "success"})
        >>> payload.name
        'calculator'
        >>> payload.result
        {'result': 8, 'status': 'success'}
        >>> p = ToolPostInvokePayload(name="analyzer", result={"confidence": 0.95, "sentiment": "positive"})
        >>> p.name
        'analyzer'
        >>> p.result["confidence"]
        0.95
    """

    name: str
    result: Any


ToolPreInvokeResult = PluginResult[ToolPreInvokePayload]
ToolPostInvokeResult = PluginResult[ToolPostInvokePayload]


class GlobalContext(BaseModel):
    """The global context, which shared across all plugins.

    Attributes:
            request_id (str): ID of the HTTP request.
            user (str): user ID associated with the request.
            tenant_id (str): tenant ID.
            server_id (str): server ID.

    Examples:
        >>> ctx = GlobalContext(request_id="req-123")
        >>> ctx.request_id
        'req-123'
        >>> ctx.user is None
        True
        >>> ctx2 = GlobalContext(request_id="req-456", user="alice", tenant_id="tenant1")
        >>> ctx2.user
        'alice'
        >>> ctx2.tenant_id
        'tenant1'
        >>> c = GlobalContext(request_id="123", server_id="srv1")
        >>> c.request_id
        '123'
        >>> c.server_id
        'srv1'
    """

    request_id: str
    user: Optional[str] = None
    tenant_id: Optional[str] = None
    server_id: Optional[str] = None


class PluginContext(GlobalContext):
    """The plugin's context, which lasts a request lifecycle.

    Attributes:
       metadata: context metadata.
       state:  the inmemory state of the request.
    """

    state: dict[str, Any] = {}
    metadata: dict[str, Any] = {}

    def get_state(self, key: str, default: Any = None) -> Any:
        """Get value from shared state.

        Args:
            key: The key to access the shared state.
            default: A default value if one doesn't exist.

        Returns:
            The state value.
        """
        return self.state.get(key, default)

    def set_state(self, key: str, value: Any) -> None:
        """Set value in shared state.

        Args:
            key: the key to add to the state.
            value: the value to add to the state.
        """
        self.state[key] = value

    async def cleanup(self) -> None:
        """Cleanup context resources."""
        self.state.clear()
        self.metadata.clear()


PluginContextTable = dict[str, PluginContext]


class ResourcePreFetchPayload(BaseModel):
    """A resource payload for a resource pre-fetch hook.

    Attributes:
            uri: The resource URI.
            metadata: Optional metadata for the resource request.

    Examples:
        >>> payload = ResourcePreFetchPayload(uri="file:///data.txt")
        >>> payload.uri
        'file:///data.txt'
        >>> payload2 = ResourcePreFetchPayload(uri="http://api/data", metadata={"Accept": "application/json"})
        >>> payload2.metadata
        {'Accept': 'application/json'}
        >>> p = ResourcePreFetchPayload(uri="file:///docs/readme.md", metadata={"version": "1.0"})
        >>> p.uri
        'file:///docs/readme.md'
        >>> p.metadata["version"]
        '1.0'
    """

    uri: str
    metadata: Optional[dict[str, Any]] = {}


class ResourcePostFetchPayload(BaseModel):
    """A resource payload for a resource post-fetch hook.

    Attributes:
        uri: The resource URI.
        content: The fetched resource content.

    Examples:
        >>> from mcpgateway.models import ResourceContent
        >>> content = ResourceContent(type="resource", uri="file:///data.txt",
        ...     text="Hello World")
        >>> payload = ResourcePostFetchPayload(uri="file:///data.txt", content=content)
        >>> payload.uri
        'file:///data.txt'
        >>> payload.content.text
        'Hello World'
        >>> from mcpgateway.models import ResourceContent
        >>> resource_content = ResourceContent(type="resource", uri="test://resource", text="Test data")
        >>> p = ResourcePostFetchPayload(uri="test://resource", content=resource_content)
        >>> p.uri
        'test://resource'
    """

    uri: str
    content: Any


ResourcePreFetchResult = PluginResult[ResourcePreFetchPayload]
ResourcePostFetchResult = PluginResult[ResourcePostFetchPayload]
