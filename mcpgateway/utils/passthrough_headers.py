# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/passthrough_headers.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

HTTP 헤더 패스스루 유틸리티.
MCP Gateway에서 HTTP 헤더 패스스루 기능을 처리하는 유틸리티를 제공합니다.
기존 인증 메커니즘과의 충돌을 방지하면서 들어오는 클라이언트 요청에서
특정 헤더를 백킹 MCP 서버로 전달할 수 있습니다.

주요 기능:
- 환경 변수와 데이터베이스를 통한 글로벌 구성 지원
- 게이트웨이별 헤더 구성 재정의
- 기존 인증 헤더와의 지능적인 충돌 감지
- 명시적 허용 목록 처리로 보안 우선 접근
- 디버깅 및 모니터링을 위한 포괄적인 로깅
- 헤더 검증 및 정리

헤더 패스스루 시스템은 다음과 같은 우선순위 계층을 따릅니다:
1. 게이트웨이별 헤더 (최고 우선순위)
2. 글로벌 데이터베이스 구성
3. 환경 변수 기본값 (최저 우선순위)

사용 예시:
    헤더 패스스루 기능의 자세한 예시는
    tests/unit/mcpgateway/utils/test_passthrough_headers*.py에 있는
    포괄적인 단위 테스트를 참조하세요.
"""

# 표준 라이브러리
import logging
import re
from typing import Dict, Optional

# 서드파티 라이브러리
from sqlalchemy.orm import Session

# 퍼스트파티 모듈
from mcpgateway.config import settings
from mcpgateway.db import Gateway as DbGateway
from mcpgateway.db import GlobalConfig

# 로거 초기화
logger = logging.getLogger(__name__)

# 헤더 이름 검증 정규식 - 문자, 숫자, 하이픈 허용
HEADER_NAME_REGEX = re.compile(r"^[A-Za-z0-9\-]+$")

# 최대 헤더 값 길이 (4KB)
MAX_HEADER_VALUE_LENGTH = 4096


class PassthroughHeadersError(Exception):
    """패스스루 헤더 관련 오류들의 기본 클래스.

    Examples:
        >>> error = PassthroughHeadersError("Test error")
        >>> str(error)
        'Test error'
        >>> isinstance(error, Exception)
        True
    """


def sanitize_header_value(value: str, max_length: int = MAX_HEADER_VALUE_LENGTH) -> str:
    """보안을 위해 헤더 값을 정리합니다.

    위험한 문자를 제거하고 길이 제한을 적용합니다.

    Args:
        value: 정리할 헤더 값
        max_length: 허용되는 최대 길이

    Returns:
        정리된 헤더 값
    """
    # 헤더 인젝션 방지를 위해 개행문자와 캐리지 리턴 제거
    value = value.replace("\r", "").replace("\n", "")

    # 최대 길이로 자르기
    value = value[:max_length]

    # 탭(ASCII 9)과 스페이스(ASCII 32)를 제외한 제어 문자 제거
    value = "".join(c for c in value if ord(c) >= 32 or c == "\t")

    return value.strip()


def validate_header_name(name: str) -> bool:
    """허용된 패턴에 대해 헤더 이름을 검증합니다.

    Args:
        name: 검증할 헤더 이름

    Returns:
        유효하면 True, 그렇지 않으면 False
    """
    return bool(HEADER_NAME_REGEX.match(name))


def get_passthrough_headers(request_headers: Dict[str, str], base_headers: Dict[str, str], db: Session, gateway: Optional[DbGateway] = None) -> Dict[str, str]:
    """대상 게이트웨이에 패스스루될 헤더들을 가져옵니다.

    이 함수는 MCP Gateway에서 HTTP 헤더 패스스루의 핵심 로직을 구현합니다.
    구성 설정과 보안 정책을 기반으로 들어오는 클라이언트 요청에서
    백킹 MCP 서버로 전달될 헤더들을 결정합니다.

    구성 우선순위 (높음에서 낮음):
    1. 게이트웨이별 passthrough_headers 설정
    2. 글로벌 데이터베이스 구성 (GlobalConfig.passthrough_headers)
    3. 환경 변수 DEFAULT_PASSTHROUGH_HEADERS

    보안 기능:
    - 기능 플래그 제어 (기본적으로 비활성화)
    - 기존 기본 헤더와의 충돌 방지 (예: Content-Type)
    - 게이트웨이 인증과의 Authorization 헤더 충돌 차단
    - 헤더 이름 검증 (정규식 패턴 매칭)
    - 헤더 값 정리 (위험한 문자 제거, 제한 적용)
    - 디버깅을 위한 모든 충돌 및 건너뛴 헤더 로깅
    - 견고성을 위한 대소문자 구분 없는 헤더 매칭

    Args:
        request_headers (Dict[str, str]): 들어오는 HTTP 요청의 헤더들.
            키는 헤더 이름, 값은 헤더 값이어야 합니다.
            예시: {"Authorization": "Bearer token123", "X-Tenant-Id": "acme"}
        base_headers (Dict[str, str]): 최종 결과에 항상 포함되어야 하는 기본 헤더들.
            패스스루 헤더보다 우선순위가 높습니다.
            예시: {"Content-Type": "application/json", "User-Agent": "MCPGateway/1.0"}
        db (Session): 글로벌 구성을 쿼리하기 위한 SQLAlchemy 데이터베이스 세션.
            GlobalConfig.passthrough_headers 설정을 검색하는데 사용됩니다.
        gateway (Optional[DbGateway]): 대상 게이트웨이 인스턴스. 제공되면
            글로벌 설정을 재정의하기 위해 gateway.passthrough_headers를 사용합니다.
            또한 게이트웨이 인증과의 Authorization 헤더 충돌을 방지하기 위해
            gateway.auth_type을 확인합니다.

    Returns:
        Dict[str, str]: 요청의 허용된 패스스루 헤더와 결합된 기본 헤더들의 딕셔너리.
            기본 헤더는 보존되며, 패스스루 헤더는 보안 정책과 충돌하지 않는 경우에만
            추가됩니다.

    Raises:
        예외가 발생하지 않습니다. 오류는 경고로 로깅되고 처리가 계속됩니다.
        데이터베이스 연결 문제는 db.query() 호출에서 전파될 수 있습니다.

    Examples:
        기본적으로 기능이 비활성화됨 (보안 우선):
        >>> from unittest.mock import Mock, patch
        >>> with patch(__name__ + ".settings") as mock_settings:
        ...     mock_settings.enable_header_passthrough = False
        ...     mock_settings.default_passthrough_headers = ["X-Tenant-Id"]
        ...     mock_db = Mock()
        ...     mock_db.query.return_value.first.return_value = None
        ...     request_headers = {"x-tenant-id": "should-be-ignored"}
        ...     base_headers = {"Content-Type": "application/json"}
        ...     get_passthrough_headers(request_headers, base_headers, mock_db)
        {'Content-Type': 'application/json'}

        활성화된 기능, 충돌 감지 및 보안 기능의 자세한 예시는
        tests/unit/mcpgateway/utils/test_passthrough_headers*.py에 있는
        포괄적인 단위 테스트를 참조하세요.

    참고:
        헤더 이름은 대소문자를 구분하지 않고 매칭되지만,
        allowed_headers 구성에서 원래 대소문자가 보존됩니다.
        요청 헤더 값은 request_headers 딕셔너리에 대해 대소문자를 구분하지 않고 매칭됩니다.
    """
    # 기본 헤더들로 시작하여 복사본 생성
    passthrough_headers = base_headers.copy()

    # 기능이 비활성화된 경우 조기 반환
    if not settings.enable_header_passthrough:
        logger.debug("ENABLE_HEADER_PASSTHROUGH 플래그를 통해 헤더 패스스루가 비활성화됨")
        return passthrough_headers

    # 먼저 글로벌 패스스루 헤더들을 가져옴
    global_config = db.query(GlobalConfig).first()
    allowed_headers = global_config.passthrough_headers if global_config else settings.default_passthrough_headers

    # 게이트웨이별 헤더가 글로벌 구성을 재정의
    if gateway:
        if gateway.passthrough_headers is not None:
            allowed_headers = gateway.passthrough_headers

    # 요청 헤더에 대한 대소문자 구분 없는 조회 생성
    request_headers_lower = {k.lower(): v for k, v in request_headers.items()} if request_headers else {}

    # 충돌을 확인하기 위해 인증 헤더들을 가져옴
    base_headers_keys = {key.lower(): key for key in passthrough_headers.keys()}

    # 요청에서 허용된 헤더들을 복사
    if request_headers_lower and allowed_headers:
        for header_name in allowed_headers:
            # 헤더 이름 검증
            if not validate_header_name(header_name):
                logger.warning(f"유효하지 않은 헤더 이름 '{header_name}' - 건너뜀 (패턴과 일치해야 함: {HEADER_NAME_REGEX.pattern})")
                continue

            header_lower = header_name.lower()
            header_value = request_headers_lower.get(header_lower)

            if header_value:
                # 헤더 값 정리
                try:
                    sanitized_value = sanitize_header_value(header_value)
                    if not sanitized_value:
                        logger.warning(f"헤더 {header_name} 값이 정리 후 비어있음 - 건너뜀")
                        continue
                except Exception as e:
                    logger.warning(f"헤더 {header_name} 정리 실패: {e} - 건너뜀")
                    continue

                # 기존 인증 헤더와 충돌하는 경우 건너뜀
                if header_lower in base_headers_keys:
                    logger.warning(f"사전 정의된 헤더와 충돌하므로 {header_name} 헤더 패스스루 건너뜀")
                    continue

                # 게이트웨이 인증과 충돌하는 경우 건너뜀
                if gateway:
                    if gateway.auth_type == "basic" and header_lower == "authorization":
                        logger.warning(f"게이트웨이 {gateway.name}의 basic auth 구성으로 인해 Authorization 헤더 패스스루 건너뜀")
                        continue
                    if gateway.auth_type == "bearer" and header_lower == "authorization":
                        logger.warning(f"게이트웨이 {gateway.name}의 bearer auth 구성으로 인해 Authorization 헤더 패스스루 건너뜀")
                        continue

                # 구성에서 원래 헤더 이름 대소문자 사용, 요청에서 정리된 값 사용
                passthrough_headers[header_name] = sanitized_value
                logger.debug(f"패스스루 헤더 추가됨: {header_name}")
            else:
                logger.debug(f"요청 헤더에서 {header_name}을 찾을 수 없음, 패스스루 건너뜀")

    logger.debug(f"최종 패스스루 헤더들: {list(passthrough_headers.keys())}")
    return passthrough_headers


async def set_global_passthrough_headers(db: Session) -> None:
    """아직 구성되지 않은 경우 데이터베이스에 글로벌 패스스루 헤더들을 설정합니다.

    이 함수는 GlobalConfig 테이블에 글로벌 패스스루 헤더들이 이미 설정되어 있는지 확인합니다.
    설정되어 있지 않은 경우 settings.default_passthrough_headers의 기본 헤더들로 초기화합니다.

    Args:
        db (Session): GlobalConfig를 쿼리하고 업데이트하기 위한 SQLAlchemy 데이터베이스 세션.

    Raises:
        PassthroughHeadersError: 데이터베이스에서 패스스루 헤더들을 업데이트할 수 없는 경우.

    Examples:
        기본 헤더들의 성공적인 삽입:
        >>> import pytest
        >>> from unittest.mock import Mock, patch
        >>> @pytest.mark.asyncio
        ... @patch("mcpgateway.utils.passthrough_headers.settings")
        ... async def test_default_headers(mock_settings):
        ...     mock_settings.enable_header_passthrough = True
        ...     mock_settings.default_passthrough_headers = ["X-Tenant-Id", "X-Trace-Id"]
        ...     mock_db = Mock()
        ...     mock_db.query.return_value.first.return_value = None
        ...     await set_global_passthrough_headers(mock_db)
        ...     mock_db.add.assert_called_once()
        ...     mock_db.commit.assert_called_once()

        데이터베이스 쓰기 실패:
        >>> import pytest
        >>> from unittest.mock import Mock, patch
        >>> from mcpgateway.utils.passthrough_headers import PassthroughHeadersError
        >>> @pytest.mark.asyncio
        ... @patch("mcpgateway.utils.passthrough_headers.settings")
        ... async def test_db_write_failure(mock_settings):
        ...     mock_settings.enable_header_passthrough = True
        ...     mock_db = Mock()
        ...     mock_db.query.return_value.first.return_value = None
        ...     mock_db.commit.side_effect = Exception("DB write failed")
        ...     with pytest.raises(PassthroughHeadersError):
        ...         await set_global_passthrough_headers(mock_db)
        ...     mock_db.rollback.assert_called_once()

        구성 이미 존재 (DB 쓰기 없음):
        >>> import pytest
        >>> from unittest.mock import Mock, patch
        >>> from mcpgateway.models import GlobalConfig
        >>> @pytest.mark.asyncio
        ... @patch("mcpgateway.utils.passthrough_headers.settings")
        ... async def test_existing_config(mock_settings):
        ...     mock_settings.enable_header_passthrough = True
        ...     mock_db = Mock()
        ...     existing = Mock(spec=GlobalConfig)
        ...     existing.passthrough_headers = ["X-Tenant-ID", "Authorization"]
        ...     mock_db.query.return_value.first.return_value = existing
        ...     await set_global_passthrough_headers(mock_db)
        ...     mock_db.add.assert_not_called()
        ...     mock_db.commit.assert_not_called()
        ...     assert existing.passthrough_headers == ["X-Tenant-ID", "Authorization"]

    참고:
        이 함수는 일반적으로 애플리케이션 시작 중에 호출되어
        게이트웨이 작업 전에 글로벌 구성이 준비되었는지 확인합니다.
    """
    # 글로벌 구성을 쿼리
    global_config = db.query(GlobalConfig).first()

    # 글로벌 구성이 없는 경우
    if not global_config:
        config_headers = settings.default_passthrough_headers
        if config_headers:
            allowed_headers = []
            for header_name in config_headers:
                # 헤더 이름 검증
                if not validate_header_name(header_name):
                    logger.warning(f"유효하지 않은 헤더 이름 '{header_name}' - 건너뜀 (패턴과 일치해야 함: {HEADER_NAME_REGEX.pattern})")
                    continue

                allowed_headers.append(header_name)
        try:
            # 글로벌 구성에 패스스루 헤더들을 추가하고 커밋
            db.add(GlobalConfig(passthrough_headers=allowed_headers))
            db.commit()
        except Exception as e:
            # 예외 발생 시 롤백하고 사용자 정의 예외 발생
            db.rollback()
            raise PassthroughHeadersError(f"패스스루 헤더들 업데이트 실패: {str(e)}")
