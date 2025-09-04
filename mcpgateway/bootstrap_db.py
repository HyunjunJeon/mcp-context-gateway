# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/bootstrap_db.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Madhav Kandukuri

MCP 게이트웨이를 위한 데이터베이스 부트스트랩/업그레이드 진입점.
이 스크립트는 다음 작업을 수행합니다:

1. ``settings.database_url``에서 동기 SQLAlchemy ``Engine``을 생성합니다.
2. 이 파일로부터 두 단계 상위에 있는 *alembic.ini* 파일을 찾아 마이그레이션을 수행합니다.
3. 데이터베이스가 아직 비어있는 경우 (``gateways`` 테이블이 없는 경우):
   - ``Base.metadata.create_all()``로 기본 스키마를 구축합니다
   - Alembic이 최신 상태임을 알 수 있도록 마이그레이션 헤드를 스탬프합니다
4. 그렇지 않은 경우, 미결된 Alembic 리비전을 적용합니다.
5. 성공 시 **"Database ready"** 메시지를 로깅합니다.

``python3 -m mcpgateway.bootstrap_db`` 또는
``python3 mcpgateway/bootstrap_db.py``로 직접 호출할 수 있습니다.

사용 예시:
    >>> from mcpgateway.bootstrap_db import logging_service, logger
    >>> logging_service is not None
    True
    >>> logger is not None
    True
    >>> hasattr(logger, 'info')
    True
    >>> from mcpgateway.bootstrap_db import Base
    >>> hasattr(Base, 'metadata')
    True
"""

# ===========================================
# 표준 라이브러리 임포트
# ===========================================
import asyncio
from importlib.resources import files

# ===========================================
# 외부 라이브러리 임포트 (Third-Party)
# ===========================================
# 데이터베이스 마이그레이션 도구
from alembic import command
from alembic.config import Config
# SQLAlchemy 데이터베이스 엔진 및 검사 도구
from sqlalchemy import create_engine, inspect

# ===========================================
# 내부 모듈 임포트 (First-Party)
# ===========================================
from mcpgateway.config import settings      # 애플리케이션 설정
from mcpgateway.db import Base              # 데이터베이스 모델 베이스 클래스
from mcpgateway.services.logging_service import LoggingService  # 로깅 서비스

# ===========================================
# 로깅 서비스 초기화
# ===========================================
# 다른 컴포넌트보다 먼저 로깅 서비스를 초기화하여 모든 로깅이 올바르게 처리되도록 함
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


async def main() -> None:
    """
    데이터베이스 스키마를 부트스트랩하거나 업그레이드한 후 준비 상태를 로깅합니다.

    빈 데이터베이스의 경우 `create_all()` + `alembic stamp head`를 실행하고,
    그렇지 않은 경우 `alembic upgrade head`만 실행하여 애플리케이션 데이터를 그대로 유지합니다.

    Args:
        None
    """
    # ===========================================
    # 데이터베이스 엔진 및 Alembic 설정
    # ===========================================

    # 1. SQLAlchemy 엔진 생성 - 동기 모드로 데이터베이스 연결
    engine = create_engine(settings.database_url)

    # 2. Alembic 설정 파일 경로 찾기 - 컨테이너 내 경로로 변환
    ini_path = files("mcpgateway").joinpath("alembic.ini")
    cfg = Config(str(ini_path))  # 컨테이너 내 경로
    cfg.attributes["configure_logger"] = True  # 로거 설정 활성화

    # 3. 데이터베이스 연결을 통한 스키마 관리
    with engine.begin() as conn:
        # Alembic 설정에 연결 및 URL 설정
        cfg.attributes["connection"] = conn
        cfg.set_main_option("sqlalchemy.url", settings.database_url)

        # 데이터베이스 검사 도구로 기존 테이블 확인
        insp = inspect(conn)

        # 4. 데이터베이스 상태에 따른 처리 분기
        if "gateways" not in insp.get_table_names():
            # 빈 데이터베이스 감지 - 기본 스키마 생성 및 마이그레이션 헤드 스탬핑
            logger.info("빈 데이터베이스 감지 - 기본 스키마 생성 중")
            Base.metadata.create_all(bind=conn)  # 기본 테이블 생성
            command.stamp(cfg, "head")           # 마이그레이션 헤드 스탬핑
        else:
            # 기존 데이터베이스 - 마이그레이션 적용
            command.upgrade(cfg, "head")  # 최신 마이그레이션까지 업그레이드

    # 5. 데이터베이스 준비 완료 로깅
    logger.info("데이터베이스 준비 완료")


if __name__ == "__main__":
    asyncio.run(main())
