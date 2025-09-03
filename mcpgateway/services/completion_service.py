# -*- coding: utf-8 -*-
"""위치: ./mcpgateway/services/completion_service.py
저작권 2025
SPDX-License-Identifier: Apache-2.0
저자: Mihai Criveti

자동 완성 서비스 구현 모듈

MCP 사양에 따라 인자 자동 완성 기능을 구현합니다.
프롬프트 인자와 리소스 URI에 대한 자동 완성 제안을 처리합니다.

예시:
    >>> from mcpgateway.services.completion_service import CompletionService, CompletionError
    >>> service = CompletionService()
    >>> isinstance(service, CompletionService)
    True
    >>> service._custom_completions
    {}
"""

# 표준 라이브러리 임포트
from typing import Any, Dict, List

# 서드파티 라이브러리 임포트
from sqlalchemy import select
from sqlalchemy.orm import Session

# 자체 라이브러리 임포트
from mcpgateway.db import Prompt as DbPrompt
from mcpgateway.db import Resource as DbResource
from mcpgateway.models import CompleteResult
from mcpgateway.services.logging_service import LoggingService

# 로깅 서비스 초기화
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


class CompletionError(Exception):
    """자동 완성 관련 오류들의 기본 클래스입니다.

    예시:
        >>> from mcpgateway.services.completion_service import CompletionError
        >>> err = CompletionError("Invalid reference")
        >>> str(err)
        'Invalid reference'
        >>> isinstance(err, Exception)
        True
    """


class CompletionService:
    """MCP 자동 완성 서비스 클래스입니다.

    다음 항목들에 대한 인자 자동 완성을 처리합니다:
    - 스키마 기반 프롬프트 인자
    - 템플릿을 사용한 리소스 URI
    - 사용자 정의 자동 완성 소스
    """

    def __init__(self):
        """자동 완성 서비스를 초기화합니다.

        예시:
            >>> from mcpgateway.services.completion_service import CompletionService
            >>> service = CompletionService()
            >>> hasattr(service, '_custom_completions')
            True
            >>> service._custom_completions
            {}
        """
        # 사용자 정의 자동 완성 값들을 저장하는 딕셔너리
        self._custom_completions: Dict[str, List[str]] = {}

    async def initialize(self) -> None:
        """자동 완성 서비스를 초기화합니다."""
        logger.info("자동 완성 서비스 초기화 중")

    async def shutdown(self) -> None:
        """자동 완성 서비스를 종료하고 리소스를 정리합니다."""
        logger.info("자동 완성 서비스 종료 중")
        # 사용자 정의 자동 완성 데이터 정리
        self._custom_completions.clear()

    async def handle_completion(self, db: Session, request: Dict[str, Any]) -> CompleteResult:
        """자동 완성 요청을 처리합니다.

        Args:
            db: 데이터베이스 세션
            request: 자동 완성 요청 데이터

        Returns:
            제안사항이 포함된 자동 완성 결과

        Raises:
            CompletionError: 자동 완성 처리 실패 시

        예시:
            >>> from mcpgateway.services.completion_service import CompletionService
            >>> from unittest.mock import MagicMock
            >>> service = CompletionService()
            >>> db = MagicMock()
            >>> request = {'ref': {'type': 'ref/prompt', 'name': 'prompt1'}, 'argument': {'name': 'arg1', 'value': ''}}
            >>> db.execute.return_value.scalars.return_value.all.return_value = []
            >>> import asyncio
            >>> try:
            ...     asyncio.run(service.handle_completion(db, request))
            ... except Exception:
            ...     pass
        """
        try:
            # 요청에서 참조 정보와 인자 정보를 추출
            ref = request.get("ref", {})
            ref_type = ref.get("type")
            arg = request.get("argument", {})
            arg_name = arg.get("name")
            arg_value = arg.get("value", "")

            # 필수 정보가 없는 경우 오류 발생
            if not ref_type or not arg_name:
                raise CompletionError("참조 타입 또는 인자 이름이 누락되었습니다")

            # 참조 타입에 따라 적절한 자동 완성 처리
            if ref_type == "ref/prompt":
                # 프롬프트 인자 자동 완성
                result = await self._complete_prompt_argument(db, ref, arg_name, arg_value)
            elif ref_type == "ref/resource":
                # 리소스 URI 자동 완성
                result = await self._complete_resource_uri(db, ref, arg_value)
            else:
                # 지원하지 않는 참조 타입
                raise CompletionError(f"유효하지 않은 참조 타입: {ref_type}")

            return result

        except Exception as e:
            logger.error(f"자동 완성 오류: {e}")
            raise CompletionError(str(e))

    async def _complete_prompt_argument(self, db: Session, ref: Dict[str, Any], arg_name: str, arg_value: str) -> CompleteResult:
        """프롬프트 인자 값을 자동 완성합니다.

        Args:
            db: 데이터베이스 세션
            ref: 프롬프트 참조 정보
            arg_name: 인자 이름
            arg_value: 현재 인자 값

        Returns:
            자동 완성 제안사항들

        Raises:
            CompletionError: 프롬프트가 없거나 찾을 수 없는 경우

        예시:
            >>> from mcpgateway.services.completion_service import CompletionService, CompletionError
            >>> from unittest.mock import MagicMock
            >>> import asyncio
            >>> service = CompletionService()
            >>> db = MagicMock()

            >>> # 프롬프트 이름 누락 테스트
            >>> ref = {}
            >>> try:
            ...     asyncio.run(service._complete_prompt_argument(db, ref, 'arg1', 'val'))
            ... except CompletionError as e:
            ...     str(e)
            'Missing prompt name'

            >>> # 사용자 정의 자동 완성 테스트
            >>> service.register_completions('color', ['red', 'green', 'blue'])
            >>> db.execute.return_value.scalar_one_or_none.return_value = MagicMock(
            ...     argument_schema={'properties': {'color': {'name': 'color'}}}
            ... )
            >>> result = asyncio.run(service._complete_prompt_argument(
            ...     db, {'name': 'test'}, 'color', 'r'
            ... ))
            >>> result.completion['values']
            ['red', 'green']
        """
        # 프롬프트 이름 추출
        prompt_name = ref.get("name")
        if not prompt_name:
            raise CompletionError("프롬프트 이름이 누락되었습니다")

        # 데이터베이스에서 프롬프트 조회
        prompt = db.execute(select(DbPrompt).where(DbPrompt.name == prompt_name).where(DbPrompt.is_active)).scalar_one_or_none()

        if not prompt:
            raise CompletionError(f"프롬프트를 찾을 수 없습니다: {prompt_name}")

        # 스키마에서 인자 찾기
        arg_schema = None
        for arg in prompt.argument_schema.get("properties", {}).values():
            if arg.get("name") == arg_name:
                arg_schema = arg
                break

        if not arg_schema:
            raise CompletionError(f"인자를 찾을 수 없습니다: {arg_name}")

        # enum 값이 정의된 경우 해당 값들 반환
        if "enum" in arg_schema:
            # 입력값과 일치하는 enum 값들 필터링
            values = [v for v in arg_schema["enum"] if arg_value.lower() in str(v).lower()]
            return CompleteResult(
                completion={
                    "values": values[:100],  # 최대 100개로 제한
                    "total": len(values),
                    "hasMore": len(values) > 100,
                }
            )

        # 사용자 정의 자동 완성 확인
        if arg_name in self._custom_completions:
            # 입력값과 일치하는 사용자 정의 값들 필터링
            values = [v for v in self._custom_completions[arg_name] if arg_value.lower() in v.lower()]
            return CompleteResult(
                completion={
                    "values": values[:100],  # 최대 100개로 제한
                    "total": len(values),
                    "hasMore": len(values) > 100,
                }
            )

        # 자동 완성 제안사항이 없는 경우
        return CompleteResult(completion={"values": [], "total": 0, "hasMore": False})

    async def _complete_resource_uri(self, db: Session, ref: Dict[str, Any], arg_value: str) -> CompleteResult:
        """리소스 URI를 자동 완성합니다.

        Args:
            db: 데이터베이스 세션
            ref: 리소스 참조 정보
            arg_value: 현재 URI 값

        Returns:
            URI 자동 완성 제안사항들

        Raises:
            CompletionError: URI 템플릿이 누락된 경우

        예시:
            >>> from mcpgateway.services.completion_service import CompletionService, CompletionError
            >>> from unittest.mock import MagicMock
            >>> import asyncio
            >>> service = CompletionService()
            >>> db = MagicMock()

            >>> # URI 템플릿 누락 테스트
            >>> ref = {}
            >>> try:
            ...     asyncio.run(service._complete_resource_uri(db, ref, 'test'))
            ... except CompletionError as e:
            ...     str(e)
            'Missing URI template'

            >>> # 리소스 필터링 테스트
            >>> ref = {'uri': 'template://'}
            >>> mock_resources = [
            ...     MagicMock(uri='file://doc1.txt'),
            ...     MagicMock(uri='file://doc2.txt'),
            ...     MagicMock(uri='http://example.com')
            ... ]
            >>> db.execute.return_value.scalars.return_value.all.return_value = mock_resources
            >>> result = asyncio.run(service._complete_resource_uri(db, ref, 'doc'))
            >>> len(result.completion['values'])
            2
            >>> 'file://doc1.txt' in result.completion['values']
            True
        """
        # 기본 URI 템플릿 추출
        uri_template = ref.get("uri")
        if not uri_template:
            raise CompletionError("URI 템플릿이 누락되었습니다")

        # 활성화된 모든 리소스 조회
        resources = db.execute(select(DbResource).where(DbResource.is_active)).scalars().all()

        # URI 패턴으로 필터링
        matches = []
        for resource in resources:
            # 입력값이 리소스 URI에 포함되어 있는지 확인
            if arg_value.lower() in resource.uri.lower():
                matches.append(resource.uri)

        return CompleteResult(
            completion={
                "values": matches[:100],  # 최대 100개로 제한
                "total": len(matches),
                "hasMore": len(matches) > 100,
            }
        )

    def register_completions(self, arg_name: str, values: List[str]) -> None:
        """사용자 정의 자동 완성 값을 등록합니다.

        Args:
            arg_name: 인자 이름
            values: 자동 완성 값들

        예시:
            >>> from mcpgateway.services.completion_service import CompletionService
            >>> service = CompletionService()
            >>> service.register_completions('arg1', ['a', 'b'])
            >>> service._custom_completions['arg1']
            ['a', 'b']
            >>> service.register_completions('arg2', ['x', 'y', 'z'])
            >>> len(service._custom_completions)
            2
            >>> service.register_completions('arg1', ['c'])  # 덮어쓰기
            >>> service._custom_completions['arg1']
            ['c']
        """
        # 인자 이름에 대한 자동 완성 값들을 저장
        self._custom_completions[arg_name] = list(values)

    def unregister_completions(self, arg_name: str) -> None:
        """사용자 정의 자동 완성 값을 등록 해제합니다.

        Args:
            arg_name: 인자 이름

        예시:
            >>> from mcpgateway.services.completion_service import CompletionService
            >>> service = CompletionService()
            >>> service.register_completions('arg1', ['a', 'b'])
            >>> service.unregister_completions('arg1')
            >>> 'arg1' in service._custom_completions
            False
        """
        # 지정된 인자의 사용자 정의 자동 완성 값들을 제거
        self._custom_completions.pop(arg_name, None)
