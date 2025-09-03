# -*- coding: utf-8 -*-
"""텍스트 검색 및 교체를 위한 간단한 예제 플러그인.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Fred Araujo

이 모듈은 플러그인을 위한 설정을 로드합니다.
"""
# Third-Party
from pydantic import BaseModel

# First-Party
from mcpgateway.plugins.framework import (
    Plugin,
    PluginConfig,
    PluginContext,
    PluginViolation,
    PromptPrehookPayload,
    PromptPrehookResult
)
from mcpgateway.services.logging_service import LoggingService

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


class DenyListConfig(BaseModel):
    """거부 목록 플러그인의 설정 모델.

    Attributes:
        words: 거부할 단어들의 목록
    """
    words: list[str]


class DenyListPlugin(Plugin):
    """거부 목록 플러그인의 예제 구현.

    이 플러그인은 프롬프트에서 지정된 금지 단어들을 탐지하고
    요청을 차단하거나 경고를 기록합니다.
    """

    def __init__(self, config: PluginConfig):
        """거부 목록 플러그인을 초기화합니다.

        Args:
            config: 플러그인 설정 객체
        """
        # 부모 클래스 초기화 - 기본 플러그인 설정 로드
        super().__init__(config)

        # 설정에서 거부 단어 목록을 로드하고 검증
        self._dconfig = DenyListConfig.model_validate(self._config.config)

        # 거부 단어 목록을 내부 리스트로 변환하여 빠른 검색을 위해 준비
        self._deny_list = []
        for word in self._dconfig.words:
            self._deny_list.append(word)

    async def prompt_pre_fetch(self, payload: PromptPrehookPayload, context: PluginContext) -> PromptPrehookResult:
        """프롬프트가 검색되고 렌더링되기 전에 실행되는 플러그인 후크.

        이 메서드는 프롬프트의 인자들을 검사하여 거부 목록에 있는
        단어들이 포함되어 있는지 확인하고, 발견되면 요청을 차단합니다.

        Args:
            payload: 분석할 프롬프트 페이로드
            context: 후크 호출에 대한 맥락 정보

        Returns:
            플러그인 분석 결과, 프롬프트 진행 여부 포함
        """
        # 프롬프트 인자가 있는 경우에만 검사 수행
        if payload.args:
            # 각 인자에 대해 거부 단어 검사
            for key in payload.args:
                # 현재 인자의 값이 문자열인 경우에만 검사
                if isinstance(payload.args[key], str):
                    # 거부 목록의 어떤 단어가 현재 인자에 포함되어 있는지 확인
                    if any(word in payload.args[key] for word in self._deny_list):
                        # 위반 사항 생성 - 요청을 차단하기 위한 정보
                        violation = PluginViolation(
                            reason="프롬프트가 허용되지 않음",  # Prompt not allowed
                            description="프롬프트에서 거부 단어가 발견됨",  # A deny word was found in the prompt
                            code="deny",
                            details={},
                        )
                        # 발견된 거부 단어에 대한 경고 로그 기록
                        logger.warning(f"프롬프트 인자 '{key}'에서 거부 단어가 감지됨")
                        # 요청 차단을 나타내는 결과 반환
                        return PromptPrehookResult(
                            modified_payload=payload,
                            violation=violation,
                            continue_processing=False
                        )

        # 거부 단어가 발견되지 않은 경우, 수정되지 않은 페이로드로 진행 허용
        return PromptPrehookResult(modified_payload=payload)


    async def shutdown(self) -> None:
        """플러그인 종료 시 정리 작업을 수행합니다.

        플러그인이 종료될 때 필요한 정리 작업을 수행하고
        최종 상태를 로그에 기록합니다.
        """
        # 플러그인 종료를 로그에 기록
        logger.info("거부 목록 플러그인 종료 중")
