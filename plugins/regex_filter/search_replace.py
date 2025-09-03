# -*- coding: utf-8 -*-
"""텍스트 검색 및 교체를 위한 간단한 예제 플러그인.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor

이 모듈은 정규식을 사용하여 텍스트에서 패턴을 검색하고
교체하는 플러그인을 구현합니다.
"""
# Standard
import re

# Third-Party
from pydantic import BaseModel

# First-Party
from mcpgateway.plugins.framework import (
    Plugin,
    PluginConfig,
    PluginContext,
    PromptPosthookPayload,
    PromptPosthookResult,
    PromptPrehookPayload,
    PromptPrehookResult,
    ToolPostInvokePayload,
    ToolPostInvokeResult,
    ToolPreInvokePayload,
    ToolPreInvokeResult
)


class SearchReplace(BaseModel):
    """검색 및 교체 작업을 위한 설정 모델."""
    search: str   # 검색할 패턴 (정규식 가능)
    replace: str  # 교체할 텍스트

class SearchReplaceConfig(BaseModel):
    """검색 및 교체 플러그인의 설정 모델."""
    words: list[SearchReplace]  # 검색 및 교체 규칙들의 목록



class SearchReplacePlugin(Plugin):
    """정규식을 사용한 검색 및 교체 플러그인의 예제 구현.

    이 플러그인은 프롬프트, 도구 호출, 도구 결과에서 설정된
    패턴들을 검색하여 지정된 텍스트로 교체합니다.
    """
    def __init__(self, config: PluginConfig):
        """검색 및 교체 플러그인을 초기화합니다.

        Args:
            config: 플러그인 설정 객체
        """
        # 부모 클래스 초기화
        super().__init__(config)

        # 설정에서 검색/교체 규칙들을 로드하고 검증
        self._srconfig = SearchReplaceConfig.model_validate(self._config.config)

        # 정규식 패턴들을 컴파일하여 튜플 리스트로 저장 (성능 최적화)
        self.__patterns = []
        for word in self._srconfig.words:
            self.__patterns.append((r'{}'.format(word.search), word.replace))




    async def prompt_pre_fetch(self, payload: PromptPrehookPayload, context: PluginContext) -> PromptPrehookResult:
        """프롬프트 검색 전 텍스트 검색 및 교체를 수행하는 메서드.

        프롬프트의 인자들에서 설정된 패턴들을 검색하여
        지정된 텍스트로 교체합니다.

        Args:
            payload: 분석할 프롬프트 페이로드
            context: 후크 호출에 대한 맥락 정보

        Returns:
            플러그인 분석 결과, 프롬프트 진행 여부 포함
        """
        # 프롬프트 인자가 있는 경우에만 처리
        if payload.args:
            # 각 패턴에 대해 모든 인자들을 순회하며 교체 수행
            for pattern in self.__patterns:
                for key in payload.args:
                    # 현재 인자의 값이 문자열인 경우에만 교체 수행
                    if isinstance(payload.args[key], str):
                        # 정규식을 사용하여 패턴 검색 및 교체
                        value = re.sub(
                            pattern[0],  # 검색 패턴
                            pattern[1],  # 교체 텍스트
                            payload.args[key]  # 대상 텍스트
                        )
                        payload.args[key] = value

        # 수정된 페이로드를 포함하여 결과 반환
        return PromptPrehookResult(modified_payload=payload)

    async def prompt_post_fetch(self, payload: PromptPosthookPayload, context: PluginContext) -> PromptPosthookResult:
        """프롬프트 렌더링 후 텍스트 검색 및 교체를 수행하는 메서드.

        렌더링된 프롬프트의 메시지들에서 설정된 패턴들을 검색하여
        지정된 텍스트로 교체합니다.

        Args:
            payload: 분석할 프롬프트 페이로드
            context: 후크 호출에 대한 맥락 정보

        Returns:
            플러그인 분석 결과, 프롬프트 진행 여부 포함
        """

        # 프롬프트 결과에 메시지가 있는 경우에만 처리
        if payload.result.messages:
            # 각 메시지에 대해 패턴 교체 수행
            for index, message in enumerate(payload.result.messages):
                for pattern in self.__patterns:
                    # 메시지의 텍스트 콘텐츠에서 패턴 검색 및 교체
                    value = re.sub(
                        pattern[0],  # 검색 패턴
                        pattern[1],  # 교체 텍스트
                        message.content.text  # 대상 텍스트
                    )
                    # 교체된 텍스트를 메시지에 다시 설정
                    payload.result.messages[index].content.text = value

        # 수정된 페이로드를 포함하여 결과 반환
        return PromptPosthookResult(modified_payload=payload)

    async def tool_pre_invoke(self, payload: ToolPreInvokePayload, context: PluginContext) -> ToolPreInvokeResult:
        """도구 호출 전 텍스트 검색 및 교체를 수행하는 메서드.

        도구의 인자들에서 설정된 패턴들을 검색하여
        지정된 텍스트로 교체합니다.

        Args:
            payload: 분석할 도구 페이로드
            context: 후크 호출에 대한 맥락 정보

        Returns:
            플러그인 분석 결과, 도구 진행 여부 포함
        """
        # 도구 인자가 있는 경우에만 처리
        if payload.args:
            # 각 패턴에 대해 모든 인자들을 순회하며 교체 수행
            for pattern in self.__patterns:
                for key in payload.args:
                    # 현재 인자의 값이 문자열인 경우에만 교체 수행
                    if isinstance(payload.args[key], str):
                        # 정규식을 사용하여 패턴 검색 및 교체
                        value = re.sub(
                            pattern[0],  # 검색 패턴
                            pattern[1],  # 교체 텍스트
                            payload.args[key]  # 대상 텍스트
                        )
                        payload.args[key] = value

        # 수정된 페이로드를 포함하여 결과 반환
        return ToolPreInvokeResult(modified_payload=payload)

    async def tool_post_invoke(self, payload: ToolPostInvokePayload, context: PluginContext) -> ToolPostInvokeResult:
        """도구 호출 후 결과 텍스트에서 검색 및 교체를 수행하는 메서드.

        도구 실행 결과에서 설정된 패턴들을 검색하여
        지정된 텍스트로 교체합니다.

        Args:
            payload: 분석할 도구 결과 페이로드
            context: 후크 호출에 대한 맥락 정보

        Returns:
            플러그인 분석 결과, 도구 결과 진행 여부 포함
        """
        # 도구 결과가 딕셔너리인 경우 처리
        if payload.result and isinstance(payload.result, dict):
            # 각 패턴에 대해 결과 딕셔너리의 모든 값들을 순회하며 교체 수행
            for pattern in self.__patterns:
                for key in payload.result:
                    # 현재 값이 문자열인 경우에만 교체 수행
                    if isinstance(payload.result[key], str):
                        # 정규식을 사용하여 패턴 검색 및 교체
                        value = re.sub(
                            pattern[0],  # 검색 패턴
                            pattern[1],  # 교체 텍스트
                            payload.result[key]  # 대상 텍스트
                        )
                        payload.result[key] = value

        # 도구 결과가 문자열인 경우 처리
        elif payload.result and isinstance(payload.result, str):
            # 각 패턴에 대해 문자열 전체에서 교체 수행
            for pattern in self.__patterns:
                payload.result = re.sub(
                    pattern[0],  # 검색 패턴
                    pattern[1],  # 교체 텍스트
                    payload.result  # 대상 텍스트
                )

        # 수정된 페이로드를 포함하여 결과 반환
        return ToolPostInvokeResult(modified_payload=payload)
