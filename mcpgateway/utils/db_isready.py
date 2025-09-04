#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/db_isready.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

db_isready - 구성된 데이터베이스가 준비될 때까지 대기
==========================================================
이 헬퍼는 주어진 데이터베이스(SQLAlchemy URL로 정의됨)가
간단한 왕복 쿼리 ``SELECT 1``에 성공적으로 응답할 때까지 차단합니다.
컨테이너 **준비도/헬스 프로브**로 유용하거나, DB에 의존하는 서비스의
시작을 지연시키기 위해 Python 코드에서 임포트하여 사용할 수 있습니다.

스크립트로 실행 시 종료 코드
-----------------------------------
* ``0`` - 데이터베이스 준비됨.
* ``1`` - 모든 시도 소진 / 타임아웃.
* ``2`` - :pypi:`SQLAlchemy`가 **설치되지 않음**.
* ``3`` - 유효하지 않은 파라미터 조합 (``max_tries``/``interval``/``timeout``).

기능
--------
* 설치된 버전에서 지원하는 **모든** SQLAlchemy URL을 허용.
* 타이밍 조정 (시도 횟수, 간격, 연결 타임아웃)은
  *환경 변수* **또는** *CLI 플래그*를 통해 구성 가능 - 아래 참조.
* **동기식** (차단) 또는 **비동기식**으로 작동 - 간단히
  ``await wait_for_db_ready()``를 사용.
* 로그 라인에 나타나는 자격 증명은 자동으로 **삭제됨**.
* ``sqlalchemy``에만 의존 (이미 *mcpgateway*에 필요).

환경 변수
---------------------
스크립트는 :pydata:`mcpgateway.config.settings`로 폴백하지만,
아래 값들은 환경 변수 **또는** 해당 명령줄 옵션을 통해 재정의할 수 있습니다.

+------------------------+----------------------------------------------+-----------+
| 이름                   | 설명                                         | 기본값    |
+========================+==============================================+===========+
| ``DATABASE_URL``       | SQLAlchemy connection URL                    | ``sqlite:///./mcp.db`` |
| ``DB_WAIT_MAX_TRIES``  | 포기하기 전 최대 시도 횟수                   | ``30``    |
| ``DB_WAIT_INTERVAL``   | 시도 간 지연 *(초)*                          | ``2``     |
| ``DB_CONNECT_TIMEOUT`` | 시도당 연결 타임아웃 *(초)*                  | ``2``     |
| ``LOG_LEVEL``          | ``--log-level``로 설정되지 않은 경우 로그 상세도 | ``INFO`` |
+------------------------+----------------------------------------------+-----------+

사용 예시
--------------
Shell ::

    python3 db_isready.py
    python3 db_isready.py --database-url "sqlite:///./mcp.db" --max-tries 2 --interval 1 --timeout 1

Python ::

    from mcpgateway.utils.db_isready import wait_for_db_ready

    # 동기식/차단
    wait_for_db_ready(sync=True)

    # 비동기식
    import asyncio
    asyncio.run(wait_for_db_ready())

Doctest 예시
----------------
>>> from mcpgateway.utils.db_isready import wait_for_db_ready
>>> import logging
>>> class DummyLogger:
...     def __init__(self): self.infos = []
...     def info(self, msg): self.infos.append(msg)
...     def debug(self, msg): pass
...     def error(self, msg): pass
...     @property
...     def handlers(self): return [True]
>>> import sys
>>> sys.modules['sqlalchemy'] = type('sqlalchemy', (), {
...     'create_engine': lambda *a, **k: type('E', (), {'connect': lambda self: type('C', (), {'execute': lambda self, q: 1, '__enter__': lambda self: self, '__exit__': lambda self, exc_type, exc_val, exc_tb: None})()})(),
...     'text': lambda q: q,
...     'engine': type('engine', (), {'Engine': object, 'URL': object, 'url': type('url', (), {'make_url': lambda u: type('U', (), {'get_backend_name': lambda self: "sqlite"})()}),}),
...     'exc': type('exc', (), {'OperationalError': Exception})
... })
>>> wait_for_db_ready(database_url='sqlite:///./mcp.db', max_tries=1, interval=1, timeout=1, logger=DummyLogger(), sync=True)
>>> try:
...     wait_for_db_ready(database_url='sqlite:///./mcp.db', max_tries=0, interval=1, timeout=1, logger=DummyLogger(), sync=True)
... except RuntimeError as e:
...     print('error')
error
"""

# Future
from __future__ import annotations

# Standard
# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------
import argparse
import asyncio
import logging
import os
import re
import sys
import time
from typing import Any, Dict, Final, Optional

# ---------------------------------------------------------------------------
# Third-party imports - abort early if SQLAlchemy is missing
# ---------------------------------------------------------------------------
try:
    # Third-Party
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine, URL
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.exc import OperationalError
except ImportError:  # pragma: no cover - handled at runtime for the CLI
    sys.stderr.write("SQLAlchemy not installed - aborting (pip install sqlalchemy)\n")
    sys.exit(2)

# ---------------------------------------------------------------------------
# Optional project settings (silently ignored if mcpgateway package is absent)
# ---------------------------------------------------------------------------
try:
    # First-Party
    from mcpgateway.config import settings
except Exception:  # pragma: no cover - fallback minimal settings

    class _Settings:
        """Fallback dummy settings when *mcpgateway* is not import-able."""

        database_url: str = "sqlite:///./mcp.db"
        log_level: str = "INFO"

    settings = _Settings()  # type: ignore

# ---------------------------------------------------------------------------
# Environment variable names
# ---------------------------------------------------------------------------
ENV_DB_URL: Final[str] = "DATABASE_URL"
ENV_MAX_TRIES: Final[str] = "DB_WAIT_MAX_TRIES"
ENV_INTERVAL: Final[str] = "DB_WAIT_INTERVAL"
ENV_TIMEOUT: Final[str] = "DB_CONNECT_TIMEOUT"

# ---------------------------------------------------------------------------
# Defaults - overridable via env-vars or CLI flags
# ---------------------------------------------------------------------------
DEFAULT_DB_URL: Final[str] = os.getenv(ENV_DB_URL, settings.database_url)
DEFAULT_MAX_TRIES: Final[int] = int(os.getenv(ENV_MAX_TRIES, "30"))
DEFAULT_INTERVAL: Final[float] = float(os.getenv(ENV_INTERVAL, "2"))
DEFAULT_TIMEOUT: Final[int] = int(os.getenv(ENV_TIMEOUT, "2"))
DEFAULT_LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", settings.log_level).upper()

# ---------------------------------------------------------------------------
# Helpers - sanitising / formatting util functions
# ---------------------------------------------------------------------------
_CRED_RE: Final[re.Pattern[str]] = re.compile(r"://([^:/?#]+):([^@]+)@")
_PWD_RE: Final[re.Pattern[str]] = re.compile(r"(?i)(password|pwd)=([^\s]+)")


def _sanitize(txt: str) -> str:
    """Hide credentials contained in connection strings or driver errors.

    Args:
        txt: Arbitrary text that may contain a DB DSN or ``password=...``
            parameter.

    Returns:
        Same *txt* but with credentials replaced by ``***``.
    """

    redacted = _CRED_RE.sub(r"://\\1:***@", txt)
    return _PWD_RE.sub(r"\\1=***", redacted)


def _format_target(url: URL) -> str:
    """Return a concise *host[:port]/db* representation for logging.

    Args:
        url: A parsed :class:`sqlalchemy.engine.url.URL` instance.

    Returns:
        Human-readable connection target string suitable for log messages.
    """

    if url.get_backend_name() == "sqlite":
        return url.database or "<memory>"

    host: str = url.host or "localhost"
    port: str = f":{url.port}" if url.port else ""
    db: str = f"/{url.database}" if url.database else ""
    return f"{host}{port}{db}"


# ---------------------------------------------------------------------------
# Public API - *wait_for_db_ready*
# ---------------------------------------------------------------------------


def wait_for_db_ready(
    *,
    database_url: str = DEFAULT_DB_URL,
    max_tries: int = DEFAULT_MAX_TRIES,
    interval: float = DEFAULT_INTERVAL,
    timeout: int = DEFAULT_TIMEOUT,
    logger: Optional[logging.Logger] = None,
    sync: bool = False,
) -> None:
    """
    데이터베이스가 ``SELECT 1``에 응답할 때까지 차단합니다.

    헬퍼는 **비동기식으로** await할 수 있거나, ``sync=True``를 전달하여
    *차단 모드*로 호출할 수 있습니다.

    Args:
        database_url: 조사할 SQLAlchemy URL. ``$DATABASE_URL``로 폴백되거나
            프로젝트 기본값(보통 디스크상의 SQLite 파일)을 사용합니다.
        max_tries: 포기하기 전 총 연결 시도 횟수.
        interval: 시도 간 지연 *초 단위*.
        timeout: 시도당 연결 타임아웃 초(지원되는 경우 DB 드라이버에 전달됨).
        logger: 선택적 사용자 정의 :class:`logging.Logger`. 생략하면 기본적으로
            ``"db_isready"``라는 이름의 로거가 지연 구성됩니다.
        sync: *True*일 때, executor 내에서 프로브를 스케줄링하는 대신
            **현재** 스레드에서 실행합니다. 실행 중인 이벤트 루프 내에서
            이 플래그를 설정하면 해당 루프가 차단됩니다!

    Raises:
        RuntimeError: *유효하지 않은* 파라미터가 제공되었거나 구성된 시도 횟수 후에도
            데이터베이스를 사용할 수 없는 경우.

    Doctest:
    >>> from mcpgateway.utils.db_isready import wait_for_db_ready
    >>> import logging
    >>> class DummyLogger:
    ...     def __init__(self): self.infos = []
    ...     def info(self, msg): self.infos.append(msg)
    ...     def debug(self, msg): pass
    ...     def error(self, msg): pass
    ...     @property
    ...     def handlers(self): return [True]
    >>> import sys
    >>> sys.modules['sqlalchemy'] = type('sqlalchemy', (), {
    ...     'create_engine': lambda *a, **k: type('E', (), {'connect': lambda self: type('C', (), {'execute': lambda self, q: 1, '__enter__': lambda self: self, '__exit__': lambda self, exc_type, exc_val, exc_tb: None})()})(),
    ...     'text': lambda q: q,
    ...     'engine': type('engine', (), {'Engine': object, 'URL': object, 'url': type('url', (), {'make_url': lambda u: type('U', (), {'get_backend_name': lambda self: "sqlite"})()}),}),
    ...     'exc': type('exc', (), {'OperationalError': Exception})
    ... })
    >>> wait_for_db_ready(database_url='sqlite:///./mcp.db', max_tries=1, interval=1, timeout=1, logger=DummyLogger(), sync=True)
    >>> try:
    ...     wait_for_db_ready(database_url='sqlite:///./mcp.db', max_tries=0, interval=1, timeout=1, logger=DummyLogger(), sync=True)
    ... except RuntimeError as e:
    ...     print('error')
    error
    """

    # 로거 초기화 (제공되지 않은 경우 기본 로거 생성)
    log = logger or logging.getLogger("db_isready")
    # 기본 구성 한 번만 수행 - 이후 log.setLevel 존중
    if not log.handlers:
        logging.basicConfig(
            level=getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO),
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    # 파라미터 유효성 검증
    if max_tries < 1 or interval <= 0 or timeout <= 0:
        raise RuntimeError("Invalid max_tries / interval / timeout values")

    # 데이터베이스 URL 파싱 및 정보 추출
    url_obj: URL = make_url(database_url)
    backend: str = url_obj.get_backend_name()
    target: str = _format_target(url_obj)

    # 조사 시작 로깅
    log.info(f"Probing {backend} at {target} (timeout={timeout}s, interval={interval}s, max_tries={max_tries})")

    # 데이터베이스 연결 인자 설정
    connect_args: Dict[str, Any] = {}
    # 대부분의 드라이버가 이 파라미터를 존중함 - 다른 드라이버에는 무해
    if backend.startswith(("postgresql", "mysql")):
        connect_args["connect_timeout"] = timeout

    # 데이터베이스 엔진 생성 (백엔드별로 다르게 구성)
    if backend == "sqlite":
        # SQLite는 풀 오버플로/타임아웃 파라미터를 지원하지 않음
        engine: Engine = create_engine(
            database_url,
            connect_args=connect_args,
        )
    else:
        # 다른 데이터베이스는 전체 풀링 구성 지원
        engine: Engine = create_engine(
            database_url,
            pool_pre_ping=True,  # 연결 유효성 사전 확인
            pool_size=1,         # 최소 풀 크기
            max_overflow=0,      # 오버플로 방지
            connect_args=connect_args,
        )

    def _probe() -> None:  # noqa: D401 - 내부 헬퍼 함수
        """현재 스레드 또는 별도 스레드에서 실행되는 내부 동기식 프로브.

        Returns:
            None - DB가 응답하면 함수가 성공적으로 종료됨.

        Raises:
            RuntimeError: ``max_tries`` 시도 소진 후 전달됨.
        """

        # 시작 시간 기록 (성능 측정용)
        start = time.perf_counter()
        # 최대 시도 횟수만큼 반복
        for attempt in range(1, max_tries + 1):
            try:
                # 데이터베이스 연결 및 간단한 쿼리 실행
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                # 경과 시간 계산 및 성공 로깅
                elapsed = time.perf_counter() - start
                log.info(f"Database ready after {elapsed:.2f}s (attempt {attempt})")
                return
            except OperationalError as exc:
                # 실패 시도 로깅 (자격 증명 삭제됨)
                log.debug(f"Attempt {attempt}/{max_tries} failed ({_sanitize(str(exc))}) - retrying in {interval:.1f}s")
            # 다음 시도 전 대기
            time.sleep(interval)
        # 모든 시도 실패 시 예외 발생
        raise RuntimeError(f"Database not ready after {max_tries} attempts")

    # 실행 모드에 따른 프로브 실행
    if sync:
        # 동기 모드: 현재 스레드에서 직접 실행
        _probe()
    else:
        # 비동기 모드: 이벤트 루프 차단 방지를 위해 기본 executor에 오프로드
        loop = asyncio.get_event_loop()
        loop.run_until_complete(loop.run_in_executor(None, _probe))


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _parse_cli() -> argparse.Namespace:
    """Parse command-line arguments for the *db_isready* CLI wrapper.

    Returns:
        Parsed :class:`argparse.Namespace` holding all CLI options.

    Examples:
        >>> import sys
        >>> # Save original argv
        >>> original_argv = sys.argv
        >>>
        >>> # Test default values
        >>> sys.argv = ['db_isready.py']
        >>> args = _parse_cli()
        >>> args.database_url == DEFAULT_DB_URL
        True
        >>> args.max_tries == DEFAULT_MAX_TRIES
        True
        >>> args.interval == DEFAULT_INTERVAL
        True
        >>> args.timeout == DEFAULT_TIMEOUT
        True
        >>> args.log_level == DEFAULT_LOG_LEVEL
        True

        >>> # Test custom values
        >>> sys.argv = ['db_isready.py', '--database-url', 'postgresql://localhost/test',
        ...             '--max-tries', '5', '--interval', '1.5', '--timeout', '10',
        ...             '--log-level', 'DEBUG']
        >>> args = _parse_cli()
        >>> args.database_url
        'postgresql://localhost/test'
        >>> args.max_tries
        5
        >>> args.interval
        1.5
        >>> args.timeout
        10
        >>> args.log_level
        'DEBUG'

        >>> # Restore original argv
        >>> sys.argv = original_argv
    """

    parser = argparse.ArgumentParser(
        description="Wait until the configured database is ready.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--database-url",
        default=DEFAULT_DB_URL,
        help="SQLAlchemy URL (env DATABASE_URL)",
    )
    parser.add_argument("--max-tries", type=int, default=DEFAULT_MAX_TRIES, help="Maximum connection attempts")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL, help="Delay between attempts in seconds")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Per-attempt connect timeout in seconds")
    parser.add_argument("--log-level", default=DEFAULT_LOG_LEVEL, help="Logging level (DEBUG, INFO, ...)")
    return parser.parse_args()


def main() -> None:  # pragma: no cover
    """CLI entry-point.

    * Parses command-line options.
    * Applies ``--log-level`` to the *db_isready* logger **before** the first
      message is emitted.
    * Delegates the actual probing to :func:`wait_for_db_ready`.
    * Exits with:

        * ``0`` - database became ready.
        * ``1`` - connection attempts exhausted.
        * ``2`` - SQLAlchemy missing (handled on import).
        * ``3`` - invalid parameter combination.
    """
    cli_args = _parse_cli()

    log = logging.getLogger("db_isready")
    log.setLevel(cli_args.log_level.upper())

    try:
        wait_for_db_ready(
            database_url=cli_args.database_url,
            max_tries=cli_args.max_tries,
            interval=cli_args.interval,
            timeout=cli_args.timeout,
            sync=True,
            logger=log,
        )
    except RuntimeError as exc:
        log.error(f"Database unavailable: {exc}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
