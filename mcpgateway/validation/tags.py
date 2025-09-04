# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/validation/tags.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

태그 검증 및 정규화 유틸리티.
모든 MCP Gateway 엔티티(도구, 리소스, 프롬프트, 서버, 게이트웨이)에서 사용되는 태그의 검증과 정규화를 제공합니다.
"""

# 표준 라이브러리 임포트
import re
from typing import List, Optional


class TagValidator:
    """엔티티 태그를 위한 검증기 및 정규화 도구.

    태그가 일관된 포맷 규칙을 따르도록 보장합니다:
    - 최소 길이: 2자
    - 최대 길이: 50자
    - 허용 문자: 소문자, 숫자, 하이픈, 콜론, 점
    - 시작과 끝은 반드시 영숫자여야 함
    - 자동 소문자 변환 및 공백 제거

    Examples:
        >>> TagValidator.normalize("Finance")
        'finance'
        >>> TagValidator.normalize("  ANALYTICS  ")
        'analytics'
        >>> TagValidator.validate("ml")
        True
        >>> TagValidator.validate("a")
        False
        >>> TagValidator.validate_list(["Finance", "FINANCE", " finance "])
        ['finance']

    Attributes:
        MIN_LENGTH (int): 허용되는 최소 태그 길이 (2).
        MAX_LENGTH (int): 허용되는 최대 태그 길이 (50).
        ALLOWED_PATTERN (str): 유효한 태그를 위한 정규식 패턴.
    """

    # 태그 길이 제한 설정
    MIN_LENGTH = 2
    MAX_LENGTH = 50
    # 패턴: 영숫자로 시작, 중간에 하이픈/콜론/점이 올 수 있음, 영숫자로 끝남
    # 단일 문자 태그는 영숫자인 경우 허용됨
    ALLOWED_PATTERN = r"^[a-z0-9]([a-z0-9\-\:\.]*[a-z0-9])?$"

    @staticmethod
    def normalize(tag: str) -> str:
        """태그를 표준 포맷으로 정규화합니다.

        소문자로 변환하고 공백을 제거하며, 공백을 하이픈으로 대체합니다.

        Args:
            tag: 정규화할 태그 문자열.

        Returns:
            정규화된 태그 문자열.

        Examples:
            >>> TagValidator.normalize("Machine-Learning")
            'machine-learning'
            >>> TagValidator.normalize("  API  ")
            'api'
            >>> TagValidator.normalize("data  processing")
            'data-processing'
            >>> TagValidator.normalize("Machine Learning")
            'machine-learning'
            >>> TagValidator.normalize("under_score")
            'under-score'
        """
        # 공백 제거 및 소문자 변환
        normalized = tag.strip().lower()
        # 여러 개의 공백을 단일 하이픈으로 변환
        normalized = "-".join(normalized.split())
        # 일관성을 위해 언더스코어를 하이픈으로 변환
        normalized = normalized.replace("_", "-")
        return normalized

    @staticmethod
    def validate(tag: str) -> bool:
        """단일 태그의 유효성을 검증합니다.

        태그가 모든 요구사항을 충족하는지 확인합니다. 공백이 포함된 태그는
        정규화되더라도 원본 형태에서는 유효하지 않은 것으로 간주됩니다.

        Args:
            tag: 검증할 태그.

        Returns:
            태그가 유효하면 True, 그렇지 않으면 False.

        Examples:
            >>> TagValidator.validate("analytics")
            True
            >>> TagValidator.validate("ml-models")
            True
            >>> TagValidator.validate("v2.0")
            True
            >>> TagValidator.validate("team:backend")
            True
            >>> TagValidator.validate("")
            False
            >>> TagValidator.validate("a")
            False
            >>> TagValidator.validate("-invalid")
            False
            >>> TagValidator.validate("invalid tag")
            False
        """
        # 먼저 원본 입력에서 공백 확인 (원본 형태에서는 유효하지 않음)
        if " " in tag:
            return False

        # 태그 정규화 수행
        normalized = TagValidator.normalize(tag)

        # 길이 제약 조건 확인
        if len(normalized) < TagValidator.MIN_LENGTH:
            return False
        if len(normalized) > TagValidator.MAX_LENGTH:
            return False

        # 패턴 확인
        if not re.match(TagValidator.ALLOWED_PATTERN, normalized):
            return False

        return True

    @staticmethod
    def validate_list(tags: Optional[List[str]]) -> List[str]:
        """태그 리스트를 검증하고 정규화합니다.

        유효하지 않은 태그를 필터링하고 중복을 제거하며, 엣지 케이스를 처리합니다.

        Args:
            tags: 검증하고 정규화할 태그 리스트.

        Returns:
            유효하고 정규화된 고유 태그 리스트.

        Examples:
            >>> TagValidator.validate_list(["Analytics", "ANALYTICS", "ml"])
            ['analytics', 'ml']
            >>> TagValidator.validate_list(["", "a", "valid-tag"])
            ['valid-tag']
            >>> TagValidator.validate_list(None)
            []
            >>> TagValidator.validate_list([" Finance ", "FINANCE", "  finance  "])
            ['finance']
            >>> TagValidator.validate_list(["API", None, "", "  ", "api"])
            ['api']
            >>> TagValidator.validate_list(["Machine Learning", "machine-learning"])
            ['machine-learning']
        """
        # 빈 리스트나 None인 경우 빈 리스트 반환
        if not tags:
            return []

        # None 값 필터링 및 모든 값을 문자열로 변환
        string_tags = [str(tag) for tag in tags if tag is not None]

        # 모든 태그 정규화 수행
        normalized_tags = []
        for tag in string_tags:
            # 빈 문자열이나 공백만 있는 문자열은 건너뜀
            if tag and tag.strip():
                normalized_tags.append(TagValidator.normalize(tag))

        # 유효한 태그만 필터링하고 순서를 유지하며 중복 제거
        seen = set()
        valid_tags = []
        for tag in normalized_tags:
            # 유효성 검증 및 중복 확인
            if tag and TagValidator.validate(tag) and tag not in seen:
                seen.add(tag)
                valid_tags.append(tag)

        return valid_tags

    @staticmethod
    def get_validation_errors(tags: List[str]) -> List[str]:
        """태그 리스트의 검증 에러를 가져옵니다.

        유효하지 않은 태그에 대한 구체적인 에러 메시지를 반환합니다.

        Args:
            tags: 확인할 태그 리스트.

        Returns:
            유효하지 않은 태그에 대한 에러 메시지 리스트.

        Examples:
            >>> TagValidator.get_validation_errors(["", "a", "valid-tag", "-invalid"])
            ['Tag "" is too short (minimum 2 characters)', 'Tag "a" is too short (minimum 2 characters)', 'Tag "-invalid" contains invalid characters or format']
        """
        # 에러 메시지를 저장할 리스트 초기화
        errors = []

        # 각 태그에 대해 검증 수행
        for tag in tags:
            # 태그 정규화
            normalized = TagValidator.normalize(tag)

            # 길이 검증
            if len(normalized) < TagValidator.MIN_LENGTH:
                if len(normalized) == 0:
                    errors.append(f'Tag "{tag}" is too short (minimum {TagValidator.MIN_LENGTH} characters)')
                else:
                    errors.append(f'Tag "{normalized}" is too short (minimum {TagValidator.MIN_LENGTH} characters)')
            elif len(normalized) > TagValidator.MAX_LENGTH:
                errors.append(f'Tag "{normalized}" is too long (maximum {TagValidator.MAX_LENGTH} characters)')
            elif not re.match(TagValidator.ALLOWED_PATTERN, normalized):
                errors.append(f'Tag "{normalized}" contains invalid characters or format')

        return errors


def validate_tags_field(tags: Optional[List[str]]) -> List[str]:
    """태그를 위한 Pydantic 필드 검증기.

    Pydantic 모델에서 필드 검증기로 사용하세요.
    유효하지 않은 태그를 자동으로 필터링하고 유효한 태그만 반환합니다.
    태그가 고유하고 정규화되며 유효한지 보장합니다.

    Args:
        tags: 검증할 태그 리스트.

    Returns:
        검증되고 정규화된 고유 태그 리스트 (유효하지 않은 태그는 필터링됨).

    Examples:
        >>> validate_tags_field(["Analytics", "ml"])
        ['analytics', 'ml']
        >>> validate_tags_field(["valid", "", "a", "invalid-"])
        ['valid']
        >>> validate_tags_field(None)
        []
        >>> validate_tags_field(["API", "api", "  API  "])
        ['api']
        >>> validate_tags_field(["machine learning", "Machine-Learning", "ML"])
        ['machine-learning', 'ml']
    """
    # None, 빈 리스트 및 기타 falsy 값 처리
    if not tags:
        return []

    # 리스트인지 확인 (실수로 단일 문자열이 전달될 수 있음)
    if isinstance(tags, str):
        tags = [tags]

    # 태그에 쉼표로 구분된 값이 포함될 수 있는 경우 처리
    # 누군가 "tag1,tag2,tag3"를 단일 문자열로 전달하는 경우를 도움
    expanded_tags = []
    for tag in tags:
        if tag and isinstance(tag, str) and "," in tag:
            # 쉼표로 분리하여 개별 태그 추가
            expanded_tags.extend(t.strip() for t in tag.split(",") if t.strip())
        else:
            expanded_tags.append(tag)

    # 유효성 검증 및 정규화, 유효하지 않은 태그 필터링
    valid_tags = TagValidator.validate_list(expanded_tags)

    return valid_tags
