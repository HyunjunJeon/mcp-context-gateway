# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/metrics_common.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

서비스 모듈 간 메트릭 처리를 위한 공통 유틸리티.
"""

# Standard
from typing import List

# First-Party
from mcpgateway.schemas import TopPerformer


def build_top_performers(results: List) -> List[TopPerformer]:
    """
    데이터베이스 쿼리 결과를 TopPerformer 객체로 변환합니다.

    이 유틸리티 함수는 데이터베이스 쿼리 결과를 메트릭과 함께 TopPerformer 객체로
    변환해야 하는 서비스 모듈 간의 코드 중복을 제거합니다.

    Args:
        results: 데이터베이스 쿼리 결과 리스트, 각 항목은 다음을 포함:
            - id: 엔티티 ID
            - name: 엔티티 이름
            - execution_count: 총 실행 횟수
            - avg_response_time: 평균 응답 시간
            - success_rate: 성공률 백분율
            - last_execution: 마지막 실행 타임스탬프

    Returns:
        List[TopPerformer]: 적절한 타입 변환을 적용한 TopPerformer 객체 리스트

    Examples:
        >>> from unittest.mock import MagicMock
        >>> result = MagicMock()
        >>> result.id = 1
        >>> result.name = "test"
        >>> result.execution_count = 10
        >>> result.avg_response_time = 1.5
        >>> result.success_rate = 85.0
        >>> result.last_execution = None
        >>> performers = build_top_performers([result])
        >>> len(performers)
        1
        >>> performers[0].id
        1
        >>> performers[0].execution_count
        10
        >>> performers[0].avg_response_time
        1.5
    """
    return [
        TopPerformer(
            id=result.id,
            name=result.name,
            execution_count=result.execution_count or 0,
            avg_response_time=float(result.avg_response_time) if result.avg_response_time else None,
            success_rate=float(result.success_rate) if result.success_rate else None,
            last_execution=result.last_execution,
        )
        for result in results
    ]
