# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/handlers/sampling.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

MCP 샘플링 핸들러 구현.
MCP LLM 상호작용을 위한 샘플링 핸들러를 구현합니다.
모델 선택, 샘플링 선호도, 메시지 생성을 처리합니다.

예시:
    >>> import asyncio
    >>> from mcpgateway.models import ModelPreferences
    >>> handler = SamplingHandler()
    >>> asyncio.run(handler.initialize())
    >>>
    >>> # 모델 선택 테스트
    >>> prefs = ModelPreferences(
    ...     cost_priority=0.2,
    ...     speed_priority=0.3,
    ...     intelligence_priority=0.5
    ... )
    >>> handler._select_model(prefs)
    'claude-3-haiku'
    >>>
    >>> # 메시지 검증 테스트
    >>> msg = {
    ...     "role": "user",
    ...     "content": {"type": "text", "text": "Hello"}
    ... }
    >>> handler._validate_message(msg)
    True
    >>>
    >>> # 모의 샘플링 테스트
    >>> messages = [msg]
    >>> response = handler._mock_sample(messages)
    >>> print(response)
    You said: Hello
    Here is my response...
    >>>
    >>> asyncio.run(handler.shutdown())
"""

# Standard
from typing import Any, Dict, List

# Third-Party
from sqlalchemy.orm import Session

# First-Party
from mcpgateway.models import CreateMessageResult, ModelPreferences, Role, TextContent
from mcpgateway.services.logging_service import LoggingService

# 로깅 서비스 초기화 - 모든 핸들러에서 공통으로 사용되는 로거 설정
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


class SamplingError(Exception):
    """샘플링 오류를 위한 기본 클래스입니다."""


class SamplingHandler:
    """MCP 샘플링 요청 핸들러.

    다음 기능을 처리합니다:
    - 선호도 기반 모델 선택
    - 메시지 샘플링 요청
    - 컨텍스트 관리
    - 콘텐츠 검증

    예시:
        >>> handler = SamplingHandler()
        >>> handler._supported_models['claude-3-haiku']
        (0.8, 0.9, 0.7)
        >>> len(handler._supported_models)
        4
    """

    def __init__(self):
        """샘플링 핸들러를 초기화합니다.

        예시:
            >>> handler = SamplingHandler()
            >>> isinstance(handler._supported_models, dict)
            True
            >>> 'claude-3-opus' in handler._supported_models
            True
            >>> handler._supported_models['claude-3-sonnet']
            (0.5, 0.7, 0.9)
        """
        # 지원되는 모델 설정: (비용 효율성, 속도, 지능) 점수
        # 점수가 높을수록 해당 특성이 우수함 (0.0 ~ 1.0 범위)
        self._supported_models = {
            # 저비용/고속/중간 지능 모델
            "claude-3-haiku": (0.8, 0.9, 0.7),
            # 중간 비용/중간 속도/고지능 모델
            "claude-3-sonnet": (0.5, 0.7, 0.9),
            # 고비용/저속/최고 지능 모델
            "claude-3-opus": (0.2, 0.5, 1.0),
            # 중간 비용/고속/고지능 모델
            "gemini-1.5-pro": (0.6, 0.8, 0.8),
        }

    async def initialize(self) -> None:
        """샘플링 핸들러를 초기화합니다.

        예시:
            >>> import asyncio
            >>> handler = SamplingHandler()
            >>> asyncio.run(handler.initialize())
            >>> # 핸들러가 이제 초기화되었습니다
        """
        logger.info("Initializing sampling handler")

    async def shutdown(self) -> None:
        """샘플링 핸들러를 종료합니다.

        예시:
            >>> import asyncio
            >>> handler = SamplingHandler()
            >>> asyncio.run(handler.initialize())
            >>> asyncio.run(handler.shutdown())
            >>> # 핸들러가 이제 종료되었습니다
        """
        logger.info("Shutting down sampling handler")

    async def create_message(self, db: Session, request: Dict[str, Any]) -> CreateMessageResult:
        """샘플링 요청으로부터 메시지를 생성합니다.

        Args:
            db: 데이터베이스 세션
            request: 샘플링 요청 파라미터

        Returns:
            샘플링된 메시지 결과

        Raises:
            SamplingError: 샘플링에 실패한 경우

        예시:
            >>> import asyncio
            >>> from unittest.mock import Mock
            >>> handler = SamplingHandler()
            >>> db = Mock()
            >>>
            >>> # 유효한 요청으로 테스트
            >>> request = {
            ...     "messages": [{
            ...         "role": "user",
            ...         "content": {"type": "text", "text": "Hello"}
            ...     }],
            ...     "maxTokens": 100,
            ...     "modelPreferences": {
            ...         "cost_priority": 0.3,
            ...         "speed_priority": 0.3,
            ...         "intelligence_priority": 0.4
            ...     }
            ... }
            >>> result = asyncio.run(handler.create_message(db, request))
            >>> result.role
            <Role.ASSISTANT: 'assistant'>
            >>> result.content.type
            'text'
            >>> result.stop_reason
            'maxTokens'
            >>>
            >>> # 메시지가 없는 경우 테스트
            >>> bad_request = {
            ...     "messages": [],
            ...     "maxTokens": 100,
            ...     "modelPreferences": {
            ...         "cost_priority": 0.3,
            ...         "speed_priority": 0.3,
            ...         "intelligence_priority": 0.4
            ...     }
            ... }
            >>> try:
            ...     asyncio.run(handler.create_message(db, bad_request))
            ... except SamplingError as e:
            ...     print(str(e))
            No messages provided
            >>>
            >>> # 최대 토큰이 없는 경우 테스트
            >>> bad_request = {
            ...     "messages": [{"role": "user", "content": {"type": "text", "text": "Hi"}}],
            ...     "modelPreferences": {
            ...         "cost_priority": 0.3,
            ...         "speed_priority": 0.3,
            ...         "intelligence_priority": 0.4
            ...     }
            ... }
            >>> try:
            ...     asyncio.run(handler.create_message(db, bad_request))
            ... except SamplingError as e:
            ...     print(str(e))
            Max tokens not specified
        """
        try:
            # 1. 요청 파라미터 추출 및 검증
            # 메시지 목록, 최대 토큰 수, 모델 선호도 등을 요청에서 추출
            messages = request.get("messages", [])
            max_tokens = request.get("maxTokens")
            model_prefs = ModelPreferences.model_validate(request.get("modelPreferences", {}))
            include_context = request.get("includeContext", "none")
            request.get("metadata", {})

            # 2. 요청 유효성 검증
            # 필수 파라미터가 누락되지 않았는지 확인
            if not messages:
                raise SamplingError("No messages provided")
            if not max_tokens:
                raise SamplingError("Max tokens not specified")

            # 3. 모델 선택
            # 사용자 선호도(비용, 속도, 지능)에 기반하여 최적의 모델 선택
            model = self._select_model(model_prefs)
            logger.info(f"Selected model: {model}")

            # 4. 컨텍스트 추가 (선택사항)
            # 요청된 경우 추가 컨텍스트 정보를 메시지에 포함
            if include_context != "none":
                messages = await self._add_context(db, messages, include_context)

            # 5. 메시지 유효성 검증
            # 각 메시지의 형식과 콘텐츠가 올바른지 검증
            for msg in messages:
                if not self._validate_message(msg):
                    raise SamplingError(f"Invalid message format: {msg}")

            # 6. 샘플링 수행
            # TODO: 실제 모델 샘플링 구현 예정 - 현재는 모의 응답 반환
            # 실제 구현 시 선택된 모델을 사용하여 LLM API 호출
            response = self._mock_sample(messages=messages)

            # 7. 결과 구성 및 반환
            # 샘플링 결과를 표준 응답 형식으로 구성하여 반환
            return CreateMessageResult(
                content=TextContent(type="text", text=response),
                model=model,
                role=Role.ASSISTANT,
                stop_reason="maxTokens",
            )

        except Exception as e:
            # 예외 처리 및 로깅
            # 발생한 오류를 로그에 기록하고 표준화된 오류로 변환하여 상위로 전달
            logger.error(f"Sampling error: {e}")
            raise SamplingError(str(e))

    def _select_model(self, preferences: ModelPreferences) -> str:
        """선호도에 기반하여 모델을 선택합니다.

        Args:
            preferences: 모델 선택 선호도

        Returns:
            선택된 모델 이름

        Raises:
            SamplingError: 적합한 모델을 찾을 수 없는 경우

        예시:
            >>> from mcpgateway.models import ModelPreferences, ModelHint
            >>> handler = SamplingHandler()
            >>>
            >>> # 지능 우선순위 테스트
            >>> prefs = ModelPreferences(
            ...     cost_priority=1.0,
            ...     speed_priority=0.0,
            ...     intelligence_priority=1.0
            ... )
            >>> handler._select_model(prefs)
            'claude-3-opus'
            >>>
            >>> # 속도 우선순위 테스트
            >>> prefs = ModelPreferences(
            ...     cost_priority=0.0,
            ...     speed_priority=1.0,
            ...     intelligence_priority=0.0
            ... )
            >>> handler._select_model(prefs)
            'claude-3-haiku'
            >>>
            >>> # 균형 잡힌 선호도 테스트
            >>> prefs = ModelPreferences(
            ...     cost_priority=0.33,
            ...     speed_priority=0.33,
            ...     intelligence_priority=0.34
            ... )
            >>> model = handler._select_model(prefs)
            >>> model in handler._supported_models
            True
            >>>
            >>> # 모델 힌트와 함께 테스트
            >>> prefs = ModelPreferences(
            ...     hints=[ModelHint(name="opus")],
            ...     cost_priority=0.5,
            ...     speed_priority=0.3,
            ...     intelligence_priority=0.2
            ... )
            >>> handler._select_model(prefs)
            'claude-3-opus'
            >>>
            >>> # 빈 지원 모델 테스트 (오류 발생)
            >>> handler._supported_models = {}
            >>> try:
            ...     handler._select_model(prefs)
            ... except SamplingError as e:
            ...     print(str(e))
            No suitable model found
        """
        # 모델 힌트 우선 확인
        # 명시적인 모델 힌트가 있는 경우 해당 모델을 우선 선택
        if preferences.hints:
            for hint in preferences.hints:
                for model in self._supported_models:
                    if hint.name and hint.name in model:
                        return model

        # 선호도 기반 모델 점수 계산
        # 각 모델의 특성(비용, 속도, 지능)을 사용자 선호도와 곱하여 종합 점수 계산
        best_score = -1
        best_model = None

        for model, caps in self._supported_models.items():
            # 비용 점수: 비용 효율성이 높을수록 높은 점수 (1 - 비용 우선순위로 변환)
            cost_score = caps[0] * (1 - preferences.cost_priority)
            # 속도 점수: 속도 우선순위에 따라 가중치 부여
            speed_score = caps[1] * preferences.speed_priority
            # 지능 점수: 지능 우선순위에 따라 가중치 부여
            intel_score = caps[2] * preferences.intelligence_priority

            # 세 가지 특성의 평균 점수 계산
            total_score = (cost_score + speed_score + intel_score) / 3

            # 최고 점수의 모델 선택
            if total_score > best_score:
                best_score = total_score
                best_model = model

        if not best_model:
            raise SamplingError("No suitable model found")

        return best_model

    async def _add_context(self, _db: Session, messages: List[Dict[str, Any]], _context_type: str) -> List[Dict[str, Any]]:
        """메시지에 컨텍스트를 추가합니다.

        Args:
            _db: 데이터베이스 세션
            messages: 메시지 목록
            _context_type: 컨텍스트 포함 타입

        Returns:
            컨텍스트가 추가된 메시지

        예시:
            >>> import asyncio
            >>> from unittest.mock import Mock
            >>> handler = SamplingHandler()
            >>> db = Mock()
            >>>
            >>> messages = [
            ...     {"role": "user", "content": {"type": "text", "text": "Hello"}},
            ...     {"role": "assistant", "content": {"type": "text", "text": "Hi there!"}}
            ... ]
            >>>
            >>> # 'none' 컨텍스트 타입으로 테스트
            >>> result = asyncio.run(handler._add_context(db, messages, "none"))
            >>> result == messages
            True
            >>>
            >>> # 'all' 컨텍스트 타입으로 테스트 (현재 동일한 메시지 반환)
            >>> result = asyncio.run(handler._add_context(db, messages, "all"))
            >>> result == messages
            True
            >>> len(result)
            2
        """
        # TODO: 컨텍스트 타입에 따른 컨텍스트 수집 구현 예정 - 현재는 동작하지 않음
        # 실제 구현 시 데이터베이스에서 관련 컨텍스트 정보를 조회하여 메시지에 추가
        # 현재는 원본 메시지를 그대로 반환
        return messages

    def _validate_message(self, message: Dict[str, Any]) -> bool:
        """메시지 형식을 검증합니다.

        Args:
            message: 검증할 메시지

        Returns:
            유효한 경우 True

        예시:
            >>> handler = SamplingHandler()
            >>>
            >>> # 유효한 텍스트 메시지
            >>> msg = {"role": "user", "content": {"type": "text", "text": "Hello"}}
            >>> handler._validate_message(msg)
            True
            >>>
            >>> # 유효한 어시스턴트 메시지
            >>> msg = {"role": "assistant", "content": {"type": "text", "text": "Hi!"}}
            >>> handler._validate_message(msg)
            True
            >>>
            >>> # 유효한 이미지 메시지
            >>> msg = {
            ...     "role": "user",
            ...     "content": {
            ...         "type": "image",
            ...         "data": "base64data",
            ...         "mime_type": "image/png"
            ...     }
            ... }
            >>> handler._validate_message(msg)
            True
            >>>
            >>> # 역할 누락
            >>> msg = {"content": {"type": "text", "text": "Hello"}}
            >>> handler._validate_message(msg)
            False
            >>>
            >>> # 잘못된 역할
            >>> msg = {"role": "system", "content": {"type": "text", "text": "Hello"}}
            >>> handler._validate_message(msg)
            False
            >>>
            >>> # 콘텐츠 누락
            >>> msg = {"role": "user"}
            >>> handler._validate_message(msg)
            False
            >>>
            >>> # 잘못된 콘텐츠 타입
            >>> msg = {"role": "user", "content": {"type": "audio"}}
            >>> handler._validate_message(msg)
            False
            >>>
            >>> # 텍스트 콘텐츠가 문자열이 아님
            >>> msg = {"role": "user", "content": {"type": "text", "text": 123}}
            >>> handler._validate_message(msg)
            False
            >>>
            >>> # 이미지 데이터 누락
            >>> msg = {"role": "user", "content": {"type": "image", "mime_type": "image/png"}}
            >>> handler._validate_message(msg)
            False
            >>>
            >>> # 잘못된 구조
            >>> handler._validate_message("not a dict")
            False
        """
        try:
            # 필수 필드 검증: 역할과 콘텐츠가 있어야 함
            if "role" not in message or "content" not in message or message["role"] not in ("user", "assistant"):
                return False

            # 콘텐츠 타입별 유효성 검증
            content = message["content"]
            if content.get("type") == "text":
                # 텍스트 타입: 텍스트 필드가 문자열이어야 함
                if not isinstance(content.get("text"), str):
                    return False
            elif content.get("type") == "image":
                # 이미지 타입: 데이터와 MIME 타입이 모두 있어야 함
                if not (content.get("data") and content.get("mime_type")):
                    return False
            else:
                # 지원되지 않는 콘텐츠 타입
                return False

            return True

        except Exception:
            # 예외 발생 시 유효하지 않은 것으로 처리
            return False

    def _mock_sample(
        self,
        messages: List[Dict[str, Any]],
    ) -> str:
        """테스트용 모의 샘플링 응답을 생성합니다.

        Args:
            messages: 입력 메시지

        Returns:
            샘플링된 응답 텍스트

        예시:
            >>> handler = SamplingHandler()
            >>>
            >>> # 단일 사용자 메시지
            >>> messages = [{"role": "user", "content": {"type": "text", "text": "Hello world"}}]
            >>> handler._mock_sample(messages)
            'You said: Hello world\\nHere is my response...'
            >>>
            >>> # 여러 메시지의 대화
            >>> messages = [
            ...     {"role": "user", "content": {"type": "text", "text": "Hi"}},
            ...     {"role": "assistant", "content": {"type": "text", "text": "Hello!"}},
            ...     {"role": "user", "content": {"type": "text", "text": "How are you?"}}
            ... ]
            >>> handler._mock_sample(messages)
            'You said: How are you?\\nHere is my response...'
            >>>
            >>> # 이미지 메시지
            >>> messages = [{
            ...     "role": "user",
            ...     "content": {"type": "image", "data": "base64", "mime_type": "image/png"}
            ... }]
            >>> handler._mock_sample(messages)
            'You said: I see the image you shared.\\nHere is my response...'
            >>>
            >>> # 사용자 메시지 없음
            >>> messages = [{"role": "assistant", "content": {"type": "text", "text": "Hi"}}]
            >>> handler._mock_sample(messages)
            "I'm not sure what to respond to."
            >>>
            >>> # 빈 메시지
            >>> handler._mock_sample([])
            "I'm not sure what to respond to."
        """
        # 마지막 사용자 메시지 추출
        # 가장 최근의 사용자 메시지를 찾아서 응답 생성에 사용
        last_msg = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_msg = msg
                break

        if not last_msg:
            return "I'm not sure what to respond to."

        # 사용자 입력 텍스트 추출
        user_text = ""
        content = last_msg["content"]
        if content["type"] == "text":
            # 텍스트 메시지: 실제 텍스트 내용 사용
            user_text = content["text"]
        elif content["type"] == "image":
            # 이미지 메시지: 이미지 공유 메시지로 변환
            user_text = "I see the image you shared."

        # 간단한 응답 생성
        # 실제 구현 시에는 선택된 모델을 사용하여 더 지능적인 응답 생성
        return f"You said: {user_text}\nHere is my response..."
