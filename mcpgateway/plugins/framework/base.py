# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/base.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor, Mihai Criveti

기본 플러그인 구현.
이 모듈은 기본 플러그인 객체를 구현합니다.
서버의 다음 위치들에 대한 사전/사후 후크를 지원하여
AI 안전성, 보안 및 비즈니스 처리를 수행합니다:
server_pre_register / server_post_register - 가상 서버 검증용
tool_pre_invoke / tool_post_invoke - 가드레일용
prompt_pre_fetch / prompt_post_fetch - 프롬프트 필터링용
resource_pre_fetch / resource_post_fetch - 콘텐츠 필터링용
auth_pre_check / auth_post_check - 사용자 정의 인증 로직용
federation_pre_sync / federation_post_sync - 게이트웨이 페데레이션용
"""

# Standard
import uuid

# First-Party
from mcpgateway.plugins.framework.models import (
    HookType,
    PluginCondition,
    PluginConfig,
    PluginContext,
    PluginMode,
    PromptPosthookPayload,
    PromptPosthookResult,
    PromptPrehookPayload,
    PromptPrehookResult,
    ResourcePostFetchPayload,
    ResourcePostFetchResult,
    ResourcePreFetchPayload,
    ResourcePreFetchResult,
    ToolPostInvokePayload,
    ToolPostInvokeResult,
    ToolPreInvokePayload,
    ToolPreInvokeResult,
)


class Plugin:
    """서버 전체의 다양한 위치에서 입력과 출력을 사전/사후 처리하는 기본 플러그인 객체.

    Examples:
        >>> from mcpgateway.plugins.framework import PluginConfig, HookType, PluginMode
        >>> config = PluginConfig(
        ...     name="test_plugin",
        ...     description="테스트 플러그인",
        ...     author="test",
        ...     kind="mcpgateway.plugins.framework.Plugin",
        ...     version="1.0.0",
        ...     hooks=[HookType.PROMPT_PRE_FETCH],
        ...     tags=["test"],
        ...     mode=PluginMode.ENFORCE,
        ...     priority=50
        ... )
        >>> plugin = Plugin(config)
        >>> plugin.name
        'test_plugin'
        >>> plugin.priority
        50
        >>> plugin.mode
        <PluginMode.ENFORCE: 'enforce'>
        >>> HookType.PROMPT_PRE_FETCH in plugin.hooks
        True
    """

    def __init__(self, config: PluginConfig) -> None:
        """설정으로 플러그인을 초기화합니다.

        Args:
            config: 플러그인 설정

        Examples:
            >>> from mcpgateway.plugins.framework import PluginConfig, HookType
            >>> config = PluginConfig(
            ...     name="simple_plugin",
            ...     description="간단한 테스트",
            ...     author="test",
            ...     kind="test.Plugin",
            ...     version="1.0.0",
            ...     hooks=[HookType.PROMPT_POST_FETCH],
            ...     tags=["simple"]
            ... )
            >>> plugin = Plugin(config)
            >>> plugin._config.name
            'simple_plugin'
        """
        self._config = config

    @property
    def priority(self) -> int:
        """플러그인의 우선순위를 반환합니다.

        Returns:
            플러그인의 우선순위.
        """
        return self._config.priority

    @property
    def config(self) -> PluginConfig:
        """플러그인의 설정을 반환합니다.

        Returns:
            플러그인의 설정.
        """
        return self._config

    @property
    def mode(self) -> PluginMode:
        """플러그인의 모드를 반환합니다.

        Returns:
            플러그인의 모드.
        """
        return self._config.mode

    @property
    def name(self) -> str:
        """플러그인의 이름을 반환합니다.

        Returns:
            플러그인의 이름.
        """
        return self._config.name

    @property
    def hooks(self) -> list[HookType]:
        """플러그인의 현재 설정된 후크들을 반환합니다.

        Returns:
            플러그인의 설정된 후크들.
        """
        return self._config.hooks

    @property
    def tags(self) -> list[str]:
        """Return the plugin's tags.

        Returns:
            Plugin's tags.
        """
        return self._config.tags

    @property
    def conditions(self) -> list[PluginCondition] | None:
        """Return the plugin's conditions for operation.

        Returns:
            Plugin's conditions for executing.
        """
        return self._config.conditions

    async def initialize(self) -> None:
        """Initialize the plugin."""

    async def prompt_pre_fetch(self, payload: PromptPrehookPayload, context: PluginContext) -> PromptPrehookResult:
        """Plugin hook run before a prompt is retrieved and rendered.

        Args:
            payload: The prompt payload to be analyzed.
            context: contextual information about the hook call. Including why it was called.

        Raises:
            NotImplementedError: needs to be implemented by sub class.
        """
        raise NotImplementedError(
            f"""'prompt_pre_fetch' not implemented for plugin {self._config.name}
                                    of plugin type {type(self)}
                                   """
        )

    async def prompt_post_fetch(self, payload: PromptPosthookPayload, context: PluginContext) -> PromptPosthookResult:
        """Plugin hook run after a prompt is rendered.

        Args:
            payload: The prompt payload to be analyzed.
            context: Contextual information about the hook call.

        Raises:
            NotImplementedError: needs to be implemented by sub class.
        """
        raise NotImplementedError(
            f"""'prompt_post_fetch' not implemented for plugin {self._config.name}
                                    of plugin type {type(self)}
                                   """
        )

    async def tool_pre_invoke(self, payload: ToolPreInvokePayload, context: PluginContext) -> ToolPreInvokeResult:
        """Plugin hook run before a tool is invoked.

        Args:
            payload: The tool payload to be analyzed.
            context: Contextual information about the hook call.

        Raises:
            NotImplementedError: needs to be implemented by sub class.
        """
        raise NotImplementedError(
            f"""'tool_pre_invoke' not implemented for plugin {self._config.name}
                                    of plugin type {type(self)}
                                   """
        )

    async def tool_post_invoke(self, payload: ToolPostInvokePayload, context: PluginContext) -> ToolPostInvokeResult:
        """Plugin hook run after a tool is invoked.

        Args:
            payload: The tool result payload to be analyzed.
            context: Contextual information about the hook call.

        Raises:
            NotImplementedError: needs to be implemented by sub class.
        """
        raise NotImplementedError(
            f"""'tool_post_invoke' not implemented for plugin {self._config.name}
                                    of plugin type {type(self)}
                                   """
        )

    async def resource_pre_fetch(self, payload: ResourcePreFetchPayload, context: PluginContext) -> ResourcePreFetchResult:
        """Plugin hook run before a resource is fetched.

        Args:
            payload: The resource payload to be analyzed.
            context: Contextual information about the hook call.

        Raises:
            NotImplementedError: needs to be implemented by sub class.
        """
        raise NotImplementedError(
            f"""'resource_pre_fetch' not implemented for plugin {self._config.name}
                                    of plugin type {type(self)}
                                   """
        )

    async def resource_post_fetch(self, payload: ResourcePostFetchPayload, context: PluginContext) -> ResourcePostFetchResult:
        """Plugin hook run after a resource is fetched.

        Args:
            payload: The resource content payload to be analyzed.
            context: Contextual information about the hook call.

        Raises:
            NotImplementedError: needs to be implemented by sub class.
        """
        raise NotImplementedError(
            f"""'resource_post_fetch' not implemented for plugin {self._config.name}
                                    of plugin type {type(self)}
                                   """
        )

    async def shutdown(self) -> None:
        """Plugin cleanup code."""


class PluginRef:
    """Plugin reference which contains a uuid.

    Examples:
        >>> from mcpgateway.plugins.framework import PluginConfig, HookType, PluginMode
        >>> config = PluginConfig(
        ...     name="ref_test",
        ...     description="Reference test",
        ...     author="test",
        ...     kind="test.Plugin",
        ...     version="1.0.0",
        ...     hooks=[HookType.PROMPT_PRE_FETCH],
        ...     tags=["ref", "test"],
        ...     mode=PluginMode.PERMISSIVE,
        ...     priority=100
        ... )
        >>> plugin = Plugin(config)
        >>> ref = PluginRef(plugin)
        >>> ref.name
        'ref_test'
        >>> ref.priority
        100
        >>> ref.mode
        <PluginMode.PERMISSIVE: 'permissive'>
        >>> len(ref.uuid)  # UUID is a 32-character hex string
        32
        >>> ref.tags
        ['ref', 'test']
    """

    def __init__(self, plugin: Plugin):
        """Initialize a plugin reference.

        Args:
            plugin: The plugin to reference.

        Examples:
            >>> from mcpgateway.plugins.framework import PluginConfig, HookType
            >>> config = PluginConfig(
            ...     name="plugin_ref",
            ...     description="Test",
            ...     author="test",
            ...     kind="test.Plugin",
            ...     version="1.0.0",
            ...     hooks=[HookType.PROMPT_POST_FETCH],
            ...     tags=[]
            ... )
            >>> plugin = Plugin(config)
            >>> ref = PluginRef(plugin)
            >>> ref._plugin.name
            'plugin_ref'
            >>> isinstance(ref._uuid, uuid.UUID)
            True
        """
        self._plugin = plugin
        self._uuid = uuid.uuid4()

    @property
    def plugin(self) -> Plugin:
        """Return the underlying plugin.

        Returns:
            The underlying plugin.
        """
        return self._plugin

    @property
    def uuid(self) -> str:
        """Return the plugin's UUID.

        Returns:
            Plugin's UUID.
        """
        return self._uuid.hex

    @property
    def priority(self) -> int:
        """Returns the plugin's priority.

        Returns:
            Plugin's priority.
        """
        return self._plugin.priority

    @property
    def name(self) -> str:
        """Return the plugin's name.

        Returns:
            Plugin's name.
        """
        return self._plugin.name

    @property
    def hooks(self) -> list[HookType]:
        """Returns the plugin's currently configured hooks.

        Returns:
            Plugin's configured hooks.
        """
        return self._plugin.hooks

    @property
    def tags(self) -> list[str]:
        """Return the plugin's tags.

        Returns:
            Plugin's tags.
        """
        return self._plugin.tags

    @property
    def conditions(self) -> list[PluginCondition] | None:
        """Return the plugin's conditions for operation.

        Returns:
            Plugin's conditions for operation.
        """
        return self._plugin.conditions

    @property
    def mode(self) -> PluginMode:
        """Return the plugin's mode.

        Returns:
            Plugin's mode.
        """
        return self.plugin.mode
