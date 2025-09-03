# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/loader/plugin.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor, Mihai Criveti

플러그인 로더 구현.
이 모듈은 플러그인 로더를 구현합니다.
"""

# Standard - 표준 라이브러리 import
import logging  # 로깅을 위한 모듈
from typing import cast, Type  # 타입 힌팅을 위한 모듈

# First-Party - 프로젝트 내부 모듈 import
from mcpgateway.plugins.framework.base import Plugin  # 기본 플러그인 클래스
from mcpgateway.plugins.framework.constants import EXTERNAL_PLUGIN_TYPE  # 외부 플러그인 타입 상수
from mcpgateway.plugins.framework.external.mcp.client import ExternalPlugin  # 외부 플러그인 클라이언트
from mcpgateway.plugins.framework.models import PluginConfig  # 플러그인 설정 모델
from mcpgateway.plugins.framework.utils import import_module, parse_class_name  # 유틸리티 함수들

# 순환 import를 방지하기 위해 표준 logging 사용 (plugins -> services -> plugins)
logger = logging.getLogger(__name__)


class PluginLoader:
    """플러그인을 로드하고 인스턴스화하기 위한 플러그인 로더 객체.

    Examples:
        >>> loader = PluginLoader()
        >>> isinstance(loader._plugin_types, dict)
        True
        >>> len(loader._plugin_types)
        0
    """

    def __init__(self) -> None:
        """플러그인 로더를 초기화합니다.

        Examples:
            >>> loader = PluginLoader()
            >>> loader._plugin_types
            {}
        """
        # 플러그인 타입들을 저장하는 딕셔너리 (타입 이름 -> 플러그인 클래스)
        self._plugin_types: dict[str, Type[Plugin]] = {}

    def __get_plugin_type(self, kind: str) -> Type[Plugin]:
        """Python 모듈에서 플러그인 타입을 임포트합니다.

        Args:
            kind: 등록할 플러그인의 완전한 타입 이름

        Raises:
            Exception: 모듈을 임포트할 수 없는 경우

        Returns:
            플러그인 타입
        """
        try:
            # 클래스 이름을 모듈명과 클래스명으로 분리
            (mod_name, cls_name) = parse_class_name(kind)

            # 모듈 임포트
            module = import_module(mod_name)

            # 모듈에서 클래스 가져오기
            class_ = getattr(module, cls_name)

            # Plugin 타입으로 캐스팅하여 반환
            return cast(Type[Plugin], class_)

        except Exception:
            # 임포트 실패 시 예외 로깅
            logger.exception("플러그인 타입 '%s'을(를) 임포트할 수 없습니다", kind)
            raise

    def __register_plugin_type(self, kind: str) -> None:
        """플러그인 타입을 등록합니다.

        Args:
            kind: 등록할 플러그인의 완전한 타입 이름
        """
        # 이미 등록되어 있지 않은 경우에만 등록
        if kind not in self._plugin_types:
            if kind == EXTERNAL_PLUGIN_TYPE:
                # 외부 플러그인 타입인 경우 ExternalPlugin 사용
                plugin_type = ExternalPlugin
            else:
                # 일반 플러그인 타입인 경우 동적 임포트
                plugin_type = self.__get_plugin_type(kind)

            # 타입을 레지스트리에 저장
            self._plugin_types[kind] = plugin_type

    async def load_and_instantiate_plugin(self, config: PluginConfig) -> Plugin | None:
        """설정이 주어지면 플러그인을 로드하고 인스턴스화합니다.

        Args:
            config: 플러그인 설정

        Returns:
            플러그인 인스턴스
        """
        # 플러그인 타입이 아직 등록되지 않은 경우 등록
        if config.kind not in self._plugin_types:
            self.__register_plugin_type(config.kind)

        # 등록된 플러그인 타입 가져오기
        plugin_type = self._plugin_types[config.kind]

        if plugin_type:
            # 플러그인 인스턴스 생성
            plugin = plugin_type(config)

            # 플러그인 초기화
            await plugin.initialize()

            # 초기화된 플러그인 반환
            return plugin

        # 플러그인 타입을 찾을 수 없는 경우 None 반환
        return None

    async def shutdown(self) -> None:
        """플러그인 로더를 종료하고 정리합니다.

        Examples:
           >>> import asyncio
           >>> loader = PluginLoader()
           >>> asyncio.run(loader.shutdown())
           >>> loader._plugin_types
           {}
        """
        # 등록된 플러그인 타입들이 있는 경우 정리
        if self._plugin_types:
            self._plugin_types.clear()
