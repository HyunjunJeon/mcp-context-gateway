# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/registry.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

플러그인 인스턴스 레지스트리.
플러그인 인스턴스들을 저장하고 후크 포인트들을 관리하는 모듈입니다.
"""

# Standard - 표준 라이브러리 import
from collections import defaultdict  # 후크 타입별 플러그인 저장을 위한 기본값 딕셔너리
import logging                     # 로깅을 위한 모듈
from typing import Optional        # 타입 힌팅을 위한 Optional

# First-Party - 플러그인 프레임워크 컴포넌트들
from mcpgateway.plugins.framework.base import Plugin, PluginRef  # 기본 플러그인 클래스와 참조 클래스
from mcpgateway.plugins.framework.models import HookType         # 후크 타입 열거형

# 순환 import를 방지하기 위해 표준 logging 사용 (plugins -> services -> plugins)
logger = logging.getLogger(__name__)


class PluginInstanceRegistry:
    """로드된 플러그인들을 관리하기 위한 레지스트리.

    이 클래스는 플러그인 인스턴스들의 등록, 검색, 후크별 그룹화 등을 담당합니다.
    플러그인 관리자가 플러그인들을 효율적으로 찾고 실행할 수 있도록 지원합니다.

    Examples:
        >>> from mcpgateway.plugins.framework import Plugin, PluginConfig, HookType
        >>> registry = PluginInstanceRegistry()
        >>> config = PluginConfig(
        ...     name="test",
        ...     description="테스트",
        ...     author="test",
        ...     kind="test.Plugin",
        ...     version="1.0",
        ...     hooks=[HookType.PROMPT_PRE_FETCH],
        ...     tags=[]
        ... )
        >>> plugin = Plugin(config)
        >>> registry.register(plugin)
        >>> registry.get_plugin("test").name
        'test'
        >>> len(registry.get_plugins_for_hook(HookType.PROMPT_PRE_FETCH))
        1
        >>> registry.unregister("test")
        >>> registry.get_plugin("test") is None
        True
    """

    def __init__(self) -> None:
        """플러그인 인스턴스 레지스트리를 초기화합니다.

        Examples:
            >>> registry = PluginInstanceRegistry()
            >>> isinstance(registry._plugins, dict)
            True
            >>> isinstance(registry._hooks, dict)
            True
            >>> len(registry._plugins)
            0
        """
        # 플러그인 이름 -> PluginRef 매핑을 저장하는 딕셔너리
        self._plugins: dict[str, PluginRef] = {}

        # 후크 타입별 플러그인 목록을 저장하는 딕셔너리 (기본값: 빈 리스트)
        self._hooks: dict[HookType, list[PluginRef]] = defaultdict(list)

        # 우선순위 정렬된 플러그인 목록을 캐싱하기 위한 딕셔너리
        self._priority_cache: dict[HookType, list[PluginRef]] = {}

    def register(self, plugin: Plugin) -> None:
        """플러그인 인스턴스를 등록합니다.

        Args:
            plugin: 등록할 플러그인 인스턴스

        Raises:
            ValueError: 플러그인이 이미 등록되어 있는 경우
        """
        # 이미 등록된 플러그인인지 확인
        if plugin.name in self._plugins:
            raise ValueError(f"플러그인 {plugin.name}은(는) 이미 등록되어 있습니다")

        # 플러그인 참조 객체 생성
        plugin_ref = PluginRef(plugin)

        # 플러그인을 메인 레지스트리에 저장
        self._plugins[plugin.name] = plugin_ref

        # 후크별로 플러그인 등록
        for hook_type in plugin.hooks:
            self._hooks[hook_type].append(plugin_ref)
            # 해당 후크의 우선순위 캐시 무효화
            self._priority_cache.pop(hook_type, None)

        # 등록 완료 로그 기록
        logger.info(f"플러그인 등록됨: {plugin.name}, 후크: {[h.name for h in plugin.hooks]}")

    def unregister(self, plugin_name: str) -> None:
        """플러그인 이름을 기준으로 플러그인을 등록 해제합니다.

        Args:
            plugin_name: 등록 해제할 플러그인의 이름

        Returns:
            None
        """
        # 플러그인이 등록되어 있지 않은 경우 조용히 리턴
        if plugin_name not in self._plugins:
            return

        # 메인 레지스트리에서 플러그인 제거
        plugin = self._plugins.pop(plugin_name)

        # 모든 후크에서 플러그인 제거
        for hook_type in plugin.hooks:
            # 해당 후크 타입의 플러그인 목록에서 제거
            self._hooks[hook_type] = [p for p in self._hooks[hook_type] if p.name != plugin_name]
            # 우선순위 캐시 무효화
            self._priority_cache.pop(hook_type, None)

        # 등록 해제 완료 로그 기록
        logger.info(f"플러그인 등록 해제됨: {plugin_name}")

    def get_plugin(self, name: str) -> Optional[PluginRef]:
        """이름으로 플러그인을 검색합니다.

        Args:
            name: 반환할 플러그인의 이름

        Returns:
            플러그인 참조 객체 (찾지 못한 경우 None)
        """
        return self._plugins.get(name)

    def get_plugins_for_hook(self, hook_type: HookType) -> list[PluginRef]:
        """특정 후크 타입에 대한 모든 플러그인을 우선순위 순서대로 반환합니다.

        Args:
            hook_type: 후크 타입

        Returns:
            플러그인 인스턴스들의 리스트 (우선순위 정렬됨)
        """
        # 우선순위 캐시에 해당 후크 타입이 없는 경우
        if hook_type not in self._priority_cache:
            # 우선순위(priority) 기준으로 정렬 (낮은 값이 높은 우선순위)
            plugins = sorted(self._hooks[hook_type], key=lambda p: p.priority)
            # 캐시에 저장하여 다음 요청 시 재사용
            self._priority_cache[hook_type] = plugins
        return self._priority_cache[hook_type]

    def get_all_plugins(self) -> list[PluginRef]:
        """등록된 모든 플러그인 인스턴스들을 반환합니다.

        Returns:
            등록된 플러그인 인스턴스들의 리스트
        """
        return list(self._plugins.values())

    @property
    def plugin_count(self) -> int:
        """등록된 플러그인의 수를 반환합니다.

        Returns:
            등록된 플러그인의 수
        """
        return len(self._plugins)

    async def shutdown(self) -> None:
        """모든 플러그인을 종료합니다."""
        # 모든 플러그인에 대해 종료 작업 수행
        for plugin_ref in self._plugins.values():
            try:
                # 각 플러그인의 shutdown 메서드 호출
                await plugin_ref.plugin.shutdown()
            except Exception as e:
                # 개별 플러그인 종료 실패는 로그만 기록하고 계속 진행
                logger.error(f"플러그인 종료 중 오류 발생 {plugin_ref.plugin.name}: {e}")

        # 레지스트리 정리
        self._plugins.clear()
        self._hooks.clear()
        self._priority_cache.clear()
