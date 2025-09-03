# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/manager.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor, Mihai Criveti

플러그인 관리자.
게이트웨이 전체의 후크 포인트에서 플러그인을 관리하고 호출하는 모듈입니다.

이 모듈은 다음과 같은 핵심 플러그인 관리 기능을 제공합니다:
- 플러그인 라이프사이클 관리 (초기화, 실행, 종료)
- 플러그인 실행을 위한 타임아웃 보호
- 자동 정리 기능이 있는 컨텍스트 관리
- 우선순위 기반 플러그인 순서 지정
- 프롬프트/서버/테넌트 기반 조건부 플러그인 실행

Examples:
    >>> # 설정으로 플러그인 관리자 초기화
    >>> manager = PluginManager("plugins/config.yaml")
    >>> # await manager.initialize()  # 비동기 컨텍스트에서 호출

    >>> # 테스트 페이로드 및 컨텍스트 생성
    >>> from mcpgateway.plugins.framework.models import PromptPrehookPayload, GlobalContext
    >>> payload = PromptPrehookPayload(name="test", args={"user": "input"})
    >>> context = GlobalContext(request_id="123")
    >>> # result, contexts = await manager.prompt_pre_fetch(payload, context)  # 비동기 컨텍스트에서 호출
"""

# Standard - 표준 라이브러리 import
import asyncio          # 비동기 작업을 위한 모듈
import logging          # 로깅을 위한 모듈
import time             # 시간 관련 작업을 위한 모듈
from typing import Any, Callable, Coroutine, Dict, Generic, Optional, Tuple, TypeVar  # 타입 힌팅을 위한 모듈들

# First-Party - 프로젝트 내부 모듈 import
from mcpgateway.plugins.framework.base import Plugin, PluginRef  # 기본 플러그인 클래스들
from mcpgateway.plugins.framework.loader.config import ConfigLoader  # 설정 로더
from mcpgateway.plugins.framework.loader.plugin import PluginLoader  # 플러그인 로더
from mcpgateway.plugins.framework.models import (
    Config,                    # 설정 모델
    GlobalContext,             # 전역 컨텍스트
    HookType,                  # 후크 타입
    PluginCondition,           # 플러그인 조건
    PluginContext,             # 플러그인 컨텍스트
    PluginContextTable,        # 플러그인 컨텍스트 테이블
    PluginMode,                # 플러그인 모드
    PluginResult,              # 플러그인 결과
    PluginViolation,           # 플러그인 위반사항
    PromptPosthookPayload,     # 프롬프트 사후 후크 페이로드
    PromptPosthookResult,      # 프롬프트 사후 후크 결과
    PromptPrehookPayload,      # 프롬프트 사전 후크 페이로드
    PromptPrehookResult,       # 프롬프트 사전 후크 결과
    ResourcePostFetchPayload,  # 리소스 사후 페치 페이로드
    ResourcePostFetchResult,   # 리소스 사후 페치 결과
    ResourcePreFetchPayload,   # 리소스 사전 페치 페이로드
    ResourcePreFetchResult,    # 리소스 사전 페치 결과
    ToolPostInvokePayload,     # 도구 사후 호출 페이로드
    ToolPostInvokeResult,      # 도구 사후 호출 결과
    ToolPreInvokePayload,      # 도구 사전 호출 페이로드
    ToolPreInvokeResult,       # 도구 사전 호출 결과
)
from mcpgateway.plugins.framework.registry import PluginInstanceRegistry  # 플러그인 인스턴스 레지스트리
from mcpgateway.plugins.framework.utils import (
    post_prompt_matches,       # 프롬프트 사후 매칭 함수
    post_resource_matches,     # 리소스 사후 매칭 함수
    post_tool_matches,         # 도구 사후 매칭 함수
    pre_prompt_matches,        # 프롬프트 사전 매칭 함수
    pre_resource_matches,      # 리소스 사전 매칭 함수
    pre_tool_matches,          # 도구 사전 매칭 함수
)

# 순환 import를 방지하기 위해 표준 logging 사용 (plugins -> services -> plugins)
logger = logging.getLogger(__name__)

# 제네릭 타입 변수
T = TypeVar("T")

# 설정 상수들
DEFAULT_PLUGIN_TIMEOUT = 30        # 기본 플러그인 타임아웃 (초)
MAX_PAYLOAD_SIZE = 1_000_000       # 최대 페이로드 크기 (1MB)
CONTEXT_CLEANUP_INTERVAL = 300     # 컨텍스트 정리 간격 (5분)
CONTEXT_MAX_AGE = 3600             # 컨텍스트 최대 유지 시간 (1시간)


class PluginTimeoutError(Exception):
    """플러그인 실행이 타임아웃 제한을 초과할 때 발생하는 예외."""


class PayloadSizeError(ValueError):
    """페이로드가 허용된 최대 크기를 초과할 때 발생하는 예외."""


class PluginExecutor(Generic[T]):
    """타임아웃 보호 및 오류 처리를 통해 플러그인 목록을 실행합니다.

    이 클래스는 우선순위 순서대로 플러그인을 실행하며 다음과 같은 기능을 처리합니다:
    - 각 플러그인에 대한 타임아웃 보호
    - 플러그인 간 컨텍스트 관리
    - 플러그인 실패가 게이트웨이에 영향을 미치지 않도록 하는 오류 격리
    - 여러 플러그인으로부터의 메타데이터 집계

    Examples:
        >>> from mcpgateway.plugins.framework import PromptPrehookPayload
        >>> executor = PluginExecutor[PromptPrehookPayload]()
        >>> # 비동기 컨텍스트에서:
        >>> # result, contexts = await executor.execute(
        >>> #     plugins=[plugin1, plugin2],
        >>> #     payload=payload,
        >>> #     global_context=context,
        >>> #     plugin_run=pre_prompt_fetch,
        >>> #     compare=pre_prompt_matches
        >>> # )
    """

    def __init__(self, timeout: int = DEFAULT_PLUGIN_TIMEOUT):
        """플러그인 실행자를 초기화합니다.

        Args:
            timeout: 각 플러그인의 최대 실행 시간 (초).
        """
        # 타임아웃 설정 저장
        self.timeout = timeout

    async def execute(
        self,
        plugins: list[PluginRef],
        payload: T,
        global_context: GlobalContext,
        plugin_run: Callable[[PluginRef, T, PluginContext], Coroutine[Any, Any, PluginResult[T]]],
        compare: Callable[[T, list[PluginCondition], GlobalContext], bool],
        local_contexts: Optional[PluginContextTable] = None,
    ) -> tuple[PluginResult[T], PluginContextTable | None]:
        """타임아웃 보호를 통해 우선순위 순서대로 플러그인을 실행합니다.

        Args:
            plugins: 우선순위별로 정렬된 실행할 플러그인 목록
            payload: 플러그인들이 처리할 페이로드
            global_context: 모든 플러그인에 대한 요청 메타데이터를 포함하는 공유 컨텍스트
            plugin_run: 특정 플러그인 후크를 실행하는 비동기 함수
            compare: 플러그인 조건이 현재 컨텍스트와 일치하는지 확인하는 함수
            local_contexts: 이전 후크 실행으로부터의 기존 컨텍스트들 (선택사항)

        Returns:
            튜플로 구성된 결과:
            - 처리 상태, 수정된 페이로드, 메타데이터를 포함하는 PluginResult
            - 각 플러그인에 대한 업데이트된 로컬 컨텍스트를 포함하는 PluginContextTable

        Raises:
            PayloadSizeError: 페이로드가 MAX_PAYLOAD_SIZE를 초과하는 경우

        Examples:
            >>> # 타임아웃 보호를 통해 플러그인 실행
            >>> from mcpgateway.plugins.framework import HookType
            >>> executor = PluginExecutor(timeout=30)
            >>> # 레지스트리 인스턴스가 있다고 가정:
            >>> # plugins = registry.get_plugins_for_hook(HookType.PROMPT_PRE_FETCH)
            >>> # 비동기 컨텍스트에서:
            >>> # result, contexts = await executor.execute(
            >>> #     plugins=plugins,
            >>> #     payload=PromptPrehookPayload(name="test", args={}),
            >>> #     global_context=GlobalContext(request_id="123"),
            >>> #     plugin_run=pre_prompt_fetch,
            >>> #     compare=pre_prompt_matches
            >>> # )
        """
        # 플러그인이 없는 경우 빈 결과 반환
        if not plugins:
            return (PluginResult[T](modified_payload=None), None)

        # 페이로드 크기 검증
        self._validate_payload_size(payload)

        res_local_contexts = {}
        combined_metadata = {}
        current_payload: T | None = None

        for pluginref in plugins:
            # Check if plugin conditions match current context
            if pluginref.conditions and not compare(payload, pluginref.conditions, global_context):
                logger.debug(f"Skipping plugin {pluginref.name} - conditions not met")
                continue

            # Get or create local context for this plugin
            local_context_key = global_context.request_id + pluginref.uuid
            if local_contexts and local_context_key in local_contexts:
                local_context = local_contexts[local_context_key]
            else:
                local_context = PluginContext(request_id=global_context.request_id, user=global_context.user, tenant_id=global_context.tenant_id, server_id=global_context.server_id)
            res_local_contexts[local_context_key] = local_context

            try:
                # Execute plugin with timeout protection
                result = await self._execute_with_timeout(pluginref, plugin_run, current_payload or payload, local_context)

                # Aggregate metadata from all plugins
                if result.metadata:
                    combined_metadata.update(result.metadata)

                # Track payload modifications
                if result.modified_payload is not None:
                    current_payload = result.modified_payload

                # Set plugin name in violation if present
                if result.violation:
                    result.violation.plugin_name = pluginref.plugin.name

                # Handle plugin blocking the request
                if not result.continue_processing:
                    if pluginref.plugin.mode == PluginMode.ENFORCE:
                        logger.warning(f"Plugin {pluginref.plugin.name} blocked request in enforce mode")
                        return (PluginResult[T](continue_processing=False, modified_payload=current_payload, violation=result.violation, metadata=combined_metadata), res_local_contexts)
                    if pluginref.plugin.mode == PluginMode.PERMISSIVE:
                        logger.warning(f"Plugin {pluginref.plugin.name} would block (permissive mode): {result.violation.description if result.violation else 'No description'}")

            except asyncio.TimeoutError:
                logger.error(f"Plugin {pluginref.name} timed out after {self.timeout}s")
                if pluginref.plugin.mode == PluginMode.ENFORCE:
                    violation = PluginViolation(
                        reason="Plugin timeout",
                        description=f"Plugin {pluginref.name} exceeded {self.timeout}s timeout",
                        code="PLUGIN_TIMEOUT",
                        details={"timeout": self.timeout, "plugin": pluginref.name},
                    )
                    return (PluginResult[T](continue_processing=False, violation=violation, modified_payload=current_payload, metadata=combined_metadata), res_local_contexts)
                # In permissive mode, continue with next plugin
                continue

            except Exception as e:
                logger.error(f"Plugin {pluginref.name} failed with error: {str(e)}", exc_info=True)
                if pluginref.plugin.mode == PluginMode.ENFORCE:
                    violation = PluginViolation(
                        reason="Plugin error", description=f"Plugin {pluginref.name} encountered an error: {str(e)}", code="PLUGIN_ERROR", details={"error": str(e), "plugin": pluginref.name}
                    )
                    return (PluginResult[T](continue_processing=False, violation=violation, modified_payload=current_payload, metadata=combined_metadata), res_local_contexts)
                # In permissive mode, continue with next plugin
                continue

        return (PluginResult[T](continue_processing=True, modified_payload=current_payload, violation=None, metadata=combined_metadata), res_local_contexts)

    async def _execute_with_timeout(self, pluginref: PluginRef, plugin_run: Callable, payload: T, context: PluginContext) -> PluginResult[T]:
        """Execute a plugin with timeout protection.

        Args:
            pluginref: Reference to the plugin to execute.
            plugin_run: Function to execute the plugin.
            payload: Payload to process.
            context: Plugin execution context.

        Returns:
            Result from plugin execution.

        Raises:
            asyncio.TimeoutError: If plugin exceeds timeout.
        """
        return await asyncio.wait_for(plugin_run(pluginref, payload, context), timeout=self.timeout)

    def _validate_payload_size(self, payload: Any) -> None:
        """Validate that payload doesn't exceed size limits.

        Args:
            payload: The payload to validate.

        Raises:
            PayloadSizeError: If payload exceeds MAX_PAYLOAD_SIZE.
        """
        # For PromptPrehookPayload, check args size
        if hasattr(payload, "args") and payload.args:
            total_size = sum(len(str(v)) for v in payload.args.values())
            if total_size > MAX_PAYLOAD_SIZE:
                raise PayloadSizeError(f"Payload size {total_size} exceeds limit of {MAX_PAYLOAD_SIZE} bytes")
        # For PromptPosthookPayload, check result size
        elif hasattr(payload, "result") and payload.result:
            # Estimate size of result messages
            total_size = len(str(payload.result))
            if total_size > MAX_PAYLOAD_SIZE:
                raise PayloadSizeError(f"Result size {total_size} exceeds limit of {MAX_PAYLOAD_SIZE} bytes")


async def pre_prompt_fetch(plugin: PluginRef, payload: PromptPrehookPayload, context: PluginContext) -> PromptPrehookResult:
    """Call plugin's prompt pre-fetch hook.

    Args:
        plugin: The plugin to execute.
        payload: The prompt payload to be analyzed.
        context: Contextual information about the hook call.

    Returns:
        The result of the plugin execution.

    Examples:
        >>> from mcpgateway.plugins.framework.base import PluginRef
        >>> from mcpgateway.plugins.framework import Plugin, PromptPrehookPayload, PluginContext, GlobalContext
        >>> # Assuming you have a plugin instance:
        >>> # plugin_ref = PluginRef(my_plugin)
        >>> payload = PromptPrehookPayload(name="test", args={"key": "value"})
        >>> context = PluginContext(request_id="123")
        >>> # In async context:
        >>> # result = await pre_prompt_fetch(plugin_ref, payload, context)
    """
    return await plugin.plugin.prompt_pre_fetch(payload, context)


async def post_prompt_fetch(plugin: PluginRef, payload: PromptPosthookPayload, context: PluginContext) -> PromptPosthookResult:
    """Call plugin's prompt post-fetch hook.

    Args:
        plugin: The plugin to execute.
        payload: The prompt payload to be analyzed.
        context: Contextual information about the hook call.

    Returns:
        The result of the plugin execution.

    Examples:
        >>> from mcpgateway.plugins.framework.base import PluginRef
        >>> from mcpgateway.plugins.framework import Plugin, PromptPosthookPayload, PluginContext, GlobalContext
        >>> from mcpgateway.models import PromptResult
        >>> # Assuming you have a plugin instance:
        >>> # plugin_ref = PluginRef(my_plugin)
        >>> result = PromptResult(messages=[])
        >>> payload = PromptPosthookPayload(name="test", result=result)
        >>> context = PluginContext(request_id="123")
        >>> # In async context:
        >>> # result = await post_prompt_fetch(plugin_ref, payload, context)
    """
    return await plugin.plugin.prompt_post_fetch(payload, context)


async def pre_tool_invoke(plugin: PluginRef, payload: ToolPreInvokePayload, context: PluginContext) -> ToolPreInvokeResult:
    """Call plugin's tool pre-invoke hook.

    Args:
        plugin: The plugin to execute.
        payload: The tool payload to be analyzed.
        context: Contextual information about the hook call.

    Returns:
        The result of the plugin execution.

    Examples:
        >>> from mcpgateway.plugins.framework.base import PluginRef
        >>> from mcpgateway.plugins.framework import Plugin, ToolPreInvokePayload, PluginContext, GlobalContext
        >>> # Assuming you have a plugin instance:
        >>> # plugin_ref = PluginRef(my_plugin)
        >>> payload = ToolPreInvokePayload(name="calculator", args={"operation": "add", "a": 5, "b": 3})
        >>> context = PluginContext(request_id="123")
        >>> # In async context:
        >>> # result = await pre_tool_invoke(plugin_ref, payload, context)
    """
    return await plugin.plugin.tool_pre_invoke(payload, context)


async def post_tool_invoke(plugin: PluginRef, payload: ToolPostInvokePayload, context: PluginContext) -> ToolPostInvokeResult:
    """Call plugin's tool post-invoke hook.

    Args:
        plugin: The plugin to execute.
        payload: The tool result payload to be analyzed.
        context: Contextual information about the hook call.

    Returns:
        The result of the plugin execution.

    Examples:
        >>> from mcpgateway.plugins.framework.base import PluginRef
        >>> from mcpgateway.plugins.framework import Plugin, ToolPostInvokePayload, PluginContext, GlobalContext
        >>> # Assuming you have a plugin instance:
        >>> # plugin_ref = PluginRef(my_plugin)
        >>> payload = ToolPostInvokePayload(name="calculator", result={"result": 8, "status": "success"})
        >>> context = PluginContext(request_id="123")
        >>> # In async context:
        >>> # result = await post_tool_invoke(plugin_ref, payload, context)
    """
    return await plugin.plugin.tool_post_invoke(payload, context)


async def pre_resource_fetch(plugin: PluginRef, payload: ResourcePreFetchPayload, context: PluginContext) -> ResourcePreFetchResult:
    """Call plugin's resource pre-fetch hook.

    Args:
        plugin: The plugin to execute.
        payload: The resource payload to be analyzed.
        context: The plugin context.

    Returns:
        ResourcePreFetchResult with processing status.

    Examples:
        >>> from mcpgateway.plugins.framework.base import PluginRef
        >>> from mcpgateway.plugins.framework import Plugin, ResourcePreFetchPayload, PluginContext, GlobalContext
        >>> # Assuming you have a plugin instance:
        >>> # plugin_ref = PluginRef(my_plugin)
        >>> payload = ResourcePreFetchPayload(uri="file:///data.txt", metadata={"cache": True})
        >>> context = PluginContext(request_id="123")
        >>> # In async context:
        >>> # result = await pre_resource_fetch(plugin_ref, payload, context)
    """
    return await plugin.plugin.resource_pre_fetch(payload, context)


async def post_resource_fetch(plugin: PluginRef, payload: ResourcePostFetchPayload, context: PluginContext) -> ResourcePostFetchResult:
    """Call plugin's resource post-fetch hook.

    Args:
        plugin: The plugin to execute.
        payload: The resource content payload to be analyzed.
        context: The plugin context.

    Returns:
        ResourcePostFetchResult with processing status.

    Examples:
        >>> from mcpgateway.plugins.framework.base import PluginRef
        >>> from mcpgateway.plugins.framework import Plugin, ResourcePostFetchPayload, PluginContext, GlobalContext
        >>> from mcpgateway.models import ResourceContent
        >>> # Assuming you have a plugin instance:
        >>> # plugin_ref = PluginRef(my_plugin)
        >>> content = ResourceContent(type="resource", uri="file:///data.txt", text="Data")
        >>> payload = ResourcePostFetchPayload(uri="file:///data.txt", content=content)
        >>> context = PluginContext(request_id="123")
        >>> # In async context:
        >>> # result = await post_resource_fetch(plugin_ref, payload, context)
    """
    return await plugin.plugin.resource_post_fetch(payload, context)


class PluginManager:
    """플러그인 라이프사이클을 관리하는 플러그인 관리자.

    이 클래스는 애플리케이션 전체에서 일관된 플러그인 관리를 보장하기 위해
    싱글톤 패턴을 구현합니다. 다음과 같은 기능을 처리합니다:
    - 설정으로부터의 플러그인 검색 및 로딩
    - 플러그인 라이프사이클 관리 (초기화, 실행, 종료)
    - 자동 정리 기능이 있는 컨텍스트 관리
    - 후크 실행 오케스트레이션

    Attributes:
        config: 로드된 플러그인 설정
        plugin_count: 현재 로드된 플러그인의 수
        initialized: 관리자가 초기화되었는지 여부

    Examples:
        >>> # 플러그인 관리자 초기화
        >>> manager = PluginManager("plugins/config.yaml")
        >>> # 비동기 컨텍스트에서:
        >>> # await manager.initialize()
        >>> # print(f"로드된 플러그인 수: {manager.plugin_count}")
        >>>
        >>> # 프롬프트 후크 실행
        >>> from mcpgateway.plugins.framework import PromptPrehookPayload, GlobalContext
        >>> payload = PromptPrehookPayload(name="test", args={})
        >>> context = GlobalContext(request_id="req-123")
        >>> # 비동기 컨텍스트에서:
        >>> # result, contexts = await manager.prompt_pre_fetch(payload, context)
        >>>
        >>> # 완료 시 종료
        >>> # await manager.shutdown()
    """

    __shared_state: dict[Any, Any] = {}
    _loader: PluginLoader = PluginLoader()
    _initialized: bool = False
    _registry: PluginInstanceRegistry = PluginInstanceRegistry()
    _config: Config | None = None
    _pre_prompt_executor: PluginExecutor[PromptPrehookPayload] = PluginExecutor[PromptPrehookPayload]()
    _post_prompt_executor: PluginExecutor[PromptPosthookPayload] = PluginExecutor[PromptPosthookPayload]()
    _pre_tool_executor: PluginExecutor[ToolPreInvokePayload] = PluginExecutor[ToolPreInvokePayload]()
    _post_tool_executor: PluginExecutor[ToolPostInvokePayload] = PluginExecutor[ToolPostInvokePayload]()
    _resource_pre_executor: PluginExecutor[ResourcePreFetchPayload] = PluginExecutor[ResourcePreFetchPayload]()
    _resource_post_executor: PluginExecutor[ResourcePostFetchPayload] = PluginExecutor[ResourcePostFetchPayload]()

    # Context cleanup tracking
    _context_store: Dict[str, Tuple[PluginContextTable, float]] = {}
    _last_cleanup: float = 0

    def __init__(self, config: str = "", timeout: int = DEFAULT_PLUGIN_TIMEOUT):
        """플러그인 관리자를 초기화합니다.

        Args:
            config: 플러그인 설정 파일 경로 (YAML)
            timeout: 각 플러그인의 최대 실행 시간 (초)

        Examples:
            >>> # 설정 파일로 초기화
            >>> manager = PluginManager("plugins/config.yaml")

            >>> # 사용자 정의 타임아웃으로 초기화
            >>> manager = PluginManager("plugins/config.yaml", timeout=60)
        """
        # 싱글톤 패턴을 위한 공유 상태 설정
        self.__dict__ = self.__shared_state

        # 설정 파일이 제공된 경우 로드
        if config:
            self._config = ConfigLoader.load_config(config)

        # 모든 실행자의 타임아웃 업데이트
        self._pre_prompt_executor.timeout = timeout
        self._post_prompt_executor.timeout = timeout
        self._pre_tool_executor.timeout = timeout
        self._post_tool_executor.timeout = timeout
        self._resource_pre_executor.timeout = timeout
        self._resource_post_executor.timeout = timeout

        # 컨텍스트 추적이 아직 초기화되지 않은 경우 초기화
        if not hasattr(self, "_context_store"):
            self._context_store = {}
            self._last_cleanup = time.time()

    @property
    def config(self) -> Config | None:
        """플러그인 관리자 설정.

        Returns:
            설정되지 않은 경우 플러그인 설정 객체 또는 None
        """
        return self._config

    @property
    def plugin_count(self) -> int:
        """로드된 플러그인의 수.

        Returns:
            현재 로드된 플러그인의 수
        """
        return self._registry.plugin_count

    @property
    def initialized(self) -> bool:
        """플러그인 관리자 초기화 상태.

        Returns:
            플러그인 관리자가 초기화된 경우 True
        """
        return self._initialized

    def get_plugin(self, name: str) -> Optional[Plugin]:
        """이름으로 플러그인을 검색합니다.

        Args:
            name: 반환할 플러그인의 이름

        Returns:
            플러그인 객체
        """
        plugin_ref = self._registry.get_plugin(name)
        return plugin_ref.plugin if plugin_ref else None

    async def initialize(self) -> None:
        """플러그인 관리자를 초기화하고 설정된 모든 플러그인을 로드합니다.

        이 메서드는 다음을 수행합니다:
        1. 설정 파일에서 플러그인 설정들을 로드
        2. 활성화된 각 플러그인을 인스턴스화
        3. 레지스트리에 플러그인들을 등록
        4. 플러그인 초기화를 검증

        Raises:
            ValueError: 플러그인이 초기화되거나 등록될 수 없는 경우

        Examples:
            >>> manager = PluginManager("plugins/config.yaml")
            >>> # 비동기 컨텍스트에서:
            >>> # await manager.initialize()
            >>> # 이제 플러그인을 실행할 준비가 되었습니다
        """
        # 이미 초기화된 경우 조용히 리턴
        if self._initialized:
            logger.debug("플러그인 관리자가 이미 초기화되었습니다")
            return

        # 설정에서 플러그인들 가져오기
        plugins = self._config.plugins if self._config and self._config.plugins else []
        loaded_count = 0

        # 각 플러그인을 로드하고 인스턴스화
        for plugin_config in plugins:
            if plugin_config.mode != PluginMode.DISABLED:
                try:
                    # 플러그인 로드 및 인스턴스화
                    plugin = await self._loader.load_and_instantiate_plugin(plugin_config)
                    if plugin:
                        # 레지스트리에 등록
                        self._registry.register(plugin)
                        loaded_count += 1
                        logger.info(f"플러그인 로드됨: {plugin_config.name} (모드: {plugin_config.mode})")
                    else:
                        raise ValueError(f"플러그인을 인스턴스화할 수 없습니다: {plugin_config.name}")
                except Exception as e:
                    logger.error(f"플러그인 로드 실패 {plugin_config.name}: {str(e)}")
                    raise ValueError(f"플러그인을 등록하고 초기화할 수 없습니다: {plugin_config.name}") from e
            else:
                logger.debug(f"비활성화된 플러그인 건너뜀: {plugin_config.name}")

        # 초기화 완료 표시
        self._initialized = True
        logger.info(f"플러그인 관리자가 {loaded_count}개의 플러그인으로 초기화되었습니다")

    async def shutdown(self) -> None:
        """모든 플러그인을 종료하고 리소스를 정리합니다.

        이 메서드는 다음을 수행합니다:
        1. 등록된 모든 플러그인을 종료
        2. 플러그인 레지스트리를 정리
        3. 저장된 컨텍스트들을 정리
        4. 초기화 상태를 재설정

        Examples:
            >>> manager = PluginManager("plugins/config.yaml")
            >>> # 비동기 컨텍스트에서:
            >>> # await manager.initialize()
            >>> # ... 관리자 사용 ...
            >>> # await manager.shutdown()
        """
        logger.info("플러그인 관리자를 종료합니다")

        # 모든 플러그인 종료
        await self._registry.shutdown()

        # 컨텍스트 저장소 정리
        self._context_store.clear()

        # 상태 재설정
        self._initialized = False
        logger.info("플러그인 관리자 종료 완료")

    async def _cleanup_old_contexts(self) -> None:
        """메모리 누수를 방지하기 위해 CONTEXT_MAX_AGE보다 오래된 컨텍스트들을 제거합니다.

        이 메서드는 후크 실행 중에 주기적으로 호출되어 더 이상 필요하지 않은
        오래된 컨텍스트들을 정리합니다.
        """
        current_time = time.time()

        # CONTEXT_CLEANUP_INTERVAL 초마다 정리
        if current_time - self._last_cleanup < CONTEXT_CLEANUP_INTERVAL:
            return

        # 만료된 컨텍스트 찾기
        expired_keys = [key for key, (_, timestamp) in self._context_store.items() if current_time - timestamp > CONTEXT_MAX_AGE]

        # 만료된 컨텍스트 제거
        for key in expired_keys:
            del self._context_store[key]

        if expired_keys:
            logger.info(f"만료된 플러그인 컨텍스트 {len(expired_keys)}개를 정리했습니다")

        self._last_cleanup = current_time

    async def prompt_pre_fetch(
        self,
        payload: PromptPrehookPayload,
        global_context: GlobalContext,
        local_contexts: Optional[PluginContextTable] = None,
    ) -> tuple[PromptPrehookResult, PluginContextTable | None]:
        """프롬프트가 검색되고 렌더링되기 전에 사전 페치 후크를 실행합니다.

        Args:
            payload: 이름과 인자를 포함하는 프롬프트 페이로드
            global_context: 요청 메타데이터를 포함하는 모든 플러그인을 위한 공유 컨텍스트
            local_contexts: 이전 실행으로부터의 기존 컨텍스트들 (선택사항)

        Returns:
            튜플로 구성된 결과:
            - 처리 상태와 수정된 페이로드를 포함하는 PromptPrehookResult
            - 사후 페치 후크를 위한 업데이트된 컨텍스트를 포함하는 PluginContextTable

        Raises:
            PayloadSizeError: 페이로드가 크기 제한을 초과하는 경우

        Examples:
            >>> manager = PluginManager("plugins/config.yaml")
            >>> # 비동기 컨텍스트에서:
            >>> # await manager.initialize()
            >>>
            >>> from mcpgateway.plugins.framework import PromptPrehookPayload, GlobalContext
            >>> payload = PromptPrehookPayload(
            ...     name="greeting",
            ...     args={"user": "Alice"}
            ... )
            >>> context = GlobalContext(
            ...     request_id="req-123",
            ...     user="alice@example.com"
            ... )
            >>>
            >>> # 비동기 컨텍스트에서:
            >>> # result, contexts = await manager.prompt_pre_fetch(payload, context)
            >>> # if result.continue_processing:
            >>> #     # 프롬프트 처리 진행
            >>> #     modified_payload = result.modified_payload or payload
        """
        # 주기적으로 오래된 컨텍스트 정리
        await self._cleanup_old_contexts()

        # 이 후크에 대해 설정된 플러그인들 가져오기
        plugins = self._registry.get_plugins_for_hook(HookType.PROMPT_PRE_FETCH)

        # 플러그인들 실행
        result = await self._pre_prompt_executor.execute(plugins, payload, global_context, pre_prompt_fetch, pre_prompt_matches, local_contexts)

        # 잠재적 재사용을 위해 컨텍스트 저장
        if result[1]:
            self._context_store[global_context.request_id] = (result[1], time.time())

        return result

    async def prompt_post_fetch(
        self, payload: PromptPosthookPayload, global_context: GlobalContext, local_contexts: Optional[PluginContextTable] = None
    ) -> tuple[PromptPosthookResult, PluginContextTable | None]:
        """프롬프트가 렌더링된 후 사후 페치 후크를 실행합니다.

        Args:
            payload: 렌더링된 메시지를 포함하는 프롬프트 결과 페이로드
            global_context: 요청 메타데이터를 포함하는 모든 플러그인을 위한 공유 컨텍스트
            local_contexts: 사전 페치 후크 실행으로부터의 컨텍스트들 (선택사항)

        Returns:
            튜플로 구성된 결과:
            - 처리 상태와 수정된 결과를 포함하는 PromptPosthookResult
            - 최종 컨텍스트를 포함하는 PluginContextTable

        Raises:
            PayloadSizeError: 페이로드가 크기 제한을 초과하는 경우

        Examples:
            >>> # prompt_pre_fetch 예제에서 계속
            >>> from mcpgateway.models import PromptResult, Message, TextContent, Role
            >>> from mcpgateway.plugins.framework import PromptPosthookPayload, GlobalContext
            >>>
            >>> # TextContent를 포함하는 적절한 Message 생성
            >>> message = Message(
            ...     role=Role.USER,
            ...     content=TextContent(type="text", text="Hello")
            ... )
            >>> prompt_result = PromptResult(messages=[message])
            >>>
            >>> post_payload = PromptPosthookPayload(
            ...     name="greeting",
            ...     result=prompt_result
            ... )
            >>>
            >>> manager = PluginManager("plugins/config.yaml")
            >>> context = GlobalContext(request_id="req-123")
            >>>
            >>> # 비동기 컨텍스트에서:
            >>> # result, _ = await manager.prompt_post_fetch(
            >>> #     post_payload,
            >>> #     context,
            >>> #     contexts  # 사전 페치로부터
            >>> # )
            >>> # if result.modified_payload:
            >>> #     # 수정된 결과 사용
            >>> #     final_result = result.modified_payload.result
        """
        # 이 후크에 대해 설정된 플러그인들 가져오기
        plugins = self._registry.get_plugins_for_hook(HookType.PROMPT_POST_FETCH)

        # 플러그인들 실행
        result = await self._post_prompt_executor.execute(plugins, payload, global_context, post_prompt_fetch, post_prompt_matches, local_contexts)

        # 사후 페치 후 저장된 컨텍스트 정리
        if global_context.request_id in self._context_store:
            del self._context_store[global_context.request_id]

        return result

    async def tool_pre_invoke(
        self,
        payload: ToolPreInvokePayload,
        global_context: GlobalContext,
        local_contexts: Optional[PluginContextTable] = None,
    ) -> tuple[ToolPreInvokeResult, PluginContextTable | None]:
        """도구가 호출되기 전에 사전 호출 후크를 실행합니다.

        Args:
            payload: 이름과 인자를 포함하는 도구 페이로드
            global_context: 요청 메타데이터를 포함하는 모든 플러그인을 위한 공유 컨텍스트
            local_contexts: 이전 실행으로부터의 기존 컨텍스트들 (선택사항)

        Returns:
            튜플로 구성된 결과:
            - 처리 상태와 수정된 페이로드를 포함하는 ToolPreInvokeResult
            - 사후 호출 후크를 위한 업데이트된 컨텍스트를 포함하는 PluginContextTable

        Raises:
            PayloadSizeError: 페이로드가 크기 제한을 초과하는 경우

        Examples:
            >>> manager = PluginManager("plugins/config.yaml")
            >>> # 비동기 컨텍스트에서:
            >>> # await manager.initialize()
            >>>
            >>> from mcpgateway.plugins.framework import ToolPreInvokePayload, GlobalContext
            >>> payload = ToolPreInvokePayload(
            ...     name="calculator",
            ...     args={"operation": "add", "a": 5, "b": 3}
            ... )
            >>> context = GlobalContext(
            ...     request_id="req-123",
            ...     user="alice@example.com"
            ... )
            >>>
            >>> # 비동기 컨텍스트에서:
            >>> # result, contexts = await manager.tool_pre_invoke(payload, context)
            >>> # if result.continue_processing:
            >>> #     # 도구 호출 진행
            >>> #     modified_payload = result.modified_payload or payload
        """
        # 주기적으로 오래된 컨텍스트 정리
        await self._cleanup_old_contexts()

        # 이 후크에 대해 설정된 플러그인들 가져오기
        plugins = self._registry.get_plugins_for_hook(HookType.TOOL_PRE_INVOKE)

        # 플러그인들 실행
        result = await self._pre_tool_executor.execute(plugins, payload, global_context, pre_tool_invoke, pre_tool_matches, local_contexts)

        # 잠재적 재사용을 위해 컨텍스트 저장
        if result[1]:
            self._context_store[global_context.request_id] = (result[1], time.time())

        return result

    async def tool_post_invoke(
        self, payload: ToolPostInvokePayload, global_context: GlobalContext, local_contexts: Optional[PluginContextTable] = None
    ) -> tuple[ToolPostInvokeResult, PluginContextTable | None]:
        """도구가 호출된 후 사후 호출 후크를 실행합니다.

        Args:
            payload: 호출 결과를 포함하는 도구 결과 페이로드
            global_context: 요청 메타데이터를 포함하는 모든 플러그인을 위한 공유 컨텍스트
            local_contexts: 사전 호출 후크 실행으로부터의 컨텍스트들 (선택사항)

        Returns:
            튜플로 구성된 결과:
            - 처리 상태와 수정된 결과를 포함하는 ToolPostInvokeResult
            - 최종 컨텍스트를 포함하는 PluginContextTable

        Raises:
            PayloadSizeError: 페이로드가 크기 제한을 초과하는 경우

        Examples:
            >>> # tool_pre_invoke 예제에서 계속
            >>> from mcpgateway.plugins.framework import ToolPostInvokePayload, GlobalContext
            >>>
            >>> post_payload = ToolPostInvokePayload(
            ...     name="calculator",
            ...     result={"result": 8, "status": "success"}
            ... )
            >>>
            >>> manager = PluginManager("plugins/config.yaml")
            >>> context = GlobalContext(request_id="req-123")
            >>>
            >>> # 비동기 컨텍스트에서:
            >>> # result, _ = await manager.tool_post_invoke(
            >>> #     post_payload,
            >>> #     context,
            >>> #     contexts  # 사전 호출로부터
            >>> # )
            >>> # if result.modified_payload:
            >>> #     # 수정된 결과 사용
            >>> #     final_result = result.modified_payload.result
        """
        # 이 후크에 대해 설정된 플러그인들 가져오기
        plugins = self._registry.get_plugins_for_hook(HookType.TOOL_POST_INVOKE)

        # 플러그인들 실행
        result = await self._post_tool_executor.execute(plugins, payload, global_context, post_tool_invoke, post_tool_matches, local_contexts)

        # 사후 호출 후 저장된 컨텍스트 정리
        if global_context.request_id in self._context_store:
            del self._context_store[global_context.request_id]

        return result

    async def resource_pre_fetch(
        self,
        payload: ResourcePreFetchPayload,
        global_context: GlobalContext,
        local_contexts: Optional[PluginContextTable] = None,
    ) -> tuple[ResourcePreFetchResult, PluginContextTable | None]:
        """리소스가 페치되기 전에 사전 페치 후크를 실행합니다.

        Args:
            payload: URI와 메타데이터를 포함하는 리소스 페이로드
            global_context: 요청 메타데이터를 포함하는 모든 플러그인을 위한 공유 컨텍스트
            local_contexts: 이전 후크 실행으로부터의 기존 컨텍스트들 (선택사항)

        Returns:
            튜플로 구성된 결과:
            - 처리 상태와 수정된 페이로드를 포함하는 ResourcePreFetchResult
            - 상태 관리를 위한 플러그인 컨텍스트를 포함하는 PluginContextTable

        Examples:
            >>> manager = PluginManager("plugins/config.yaml")
            >>> # 비동기 컨텍스트에서:
            >>> # await manager.initialize()
            >>> # payload = ResourcePreFetchPayload("file:///data.txt")
            >>> # context = GlobalContext(request_id="123", server_id="srv1")
            >>> # result, contexts = await manager.resource_pre_fetch(payload, context)
            >>> # if result.continue_processing:
            >>> #     # 수정된 페이로드 사용
            >>> #     uri = result.modified_payload.uri
        """
        # 이 후크에 대해 설정된 플러그인들 가져오기
        plugins = self._registry.get_plugins_for_hook(HookType.RESOURCE_PRE_FETCH)

        # 플러그인들 실행
        result = await self._resource_pre_executor.execute(plugins, payload, global_context, pre_resource_fetch, pre_resource_matches, local_contexts)

        # 잠재적 사후 페치를 위해 컨텍스트 저장
        if result[1]:
            self._context_store[global_context.request_id] = (result[1], time.time())

        # 주기적 정리
        await self._cleanup_old_contexts()

        return result

    async def resource_post_fetch(
        self, payload: ResourcePostFetchPayload, global_context: GlobalContext, local_contexts: Optional[PluginContextTable] = None
    ) -> tuple[ResourcePostFetchResult, PluginContextTable | None]:
        """리소스가 페치된 후 사후 페치 후크를 실행합니다.

        Args:
            payload: 페치된 데이터를 포함하는 리소스 콘텐츠 페이로드
            global_context: 요청 메타데이터를 포함하는 모든 플러그인을 위한 공유 컨텍스트
            local_contexts: 사전 페치 후크 실행으로부터의 컨텍스트들 (선택사항)

        Returns:
            튜플로 구성된 결과:
            - 처리 상태와 수정된 콘텐츠를 포함하는 ResourcePostFetchResult
            - 업데이트된 플러그인 컨텍스트를 포함하는 PluginContextTable

        Examples:
            >>> manager = PluginManager("plugins/config.yaml")
            >>> # 비동기 컨텍스트에서:
            >>> # await manager.initialize()
            >>> # from mcpgateway.models import ResourceContent
            >>> # content = ResourceContent(type="resource", uri="file:///data.txt", text="Data")
            >>> # payload = ResourcePostFetchPayload("file:///data.txt", content)
            >>> # context = GlobalContext(request_id="123", server_id="srv1")
            >>> # contexts = self._context_store.get("123")  # 사전 페치로부터
            >>> # result, _ = await manager.resource_post_fetch(payload, context, contexts)
            >>> # if result.continue_processing:
            >>> #     # 수정된 결과 사용
            >>> #     final_content = result.modified_payload.content
        """
        # 이 후크에 대해 설정된 플러그인들 가져오기
        plugins = self._registry.get_plugins_for_hook(HookType.RESOURCE_POST_FETCH)

        # 플러그인들 실행
        result = await self._resource_post_executor.execute(plugins, payload, global_context, post_resource_fetch, post_resource_matches, local_contexts)

        # 사후 페치 후 저장된 컨텍스트 정리
        if global_context.request_id in self._context_store:
            del self._context_store[global_context.request_id]

        return result
