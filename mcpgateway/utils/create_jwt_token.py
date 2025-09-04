#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/create_jwt_token.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

JWT 토큰 생성 및 검증 유틸리티 모듈.
* **스크립트로 실행** - 친화적인 CLI (플래그 없이 작동).
* **라이브러리로 임포트** - 드롭인 비동기 함수 `create_jwt_token` & `get_jwt_token`
  하위 호환성을 위해 유지되며, 공유 코어 헬퍼에 위임합니다.

빠른 사용법
-----------
CLI (기본 시크릿, 기본 페이로드):
    $ python3 jwt_cli.py

라이브러리:
    from mcpgateway.utils.create_jwt_token import create_jwt_token, get_jwt_token

    # 비동기 컨텍스트 내에서
    jwt = await create_jwt_token({"username": "alice"})

Doctest 예시
------------
>>> from mcpgateway.utils import create_jwt_token as jwt_util
>>> jwt_util.settings.jwt_secret_key = 'secret'
>>> jwt_util.settings.jwt_algorithm = 'HS256'
>>> token = jwt_util._create_jwt_token({'sub': 'alice'}, expires_in_minutes=1, secret='secret', algorithm='HS256')
>>> import jwt
>>> jwt.decode(token, 'secret', algorithms=['HS256'])['sub'] == 'alice'
True
>>> import asyncio
>>> t = asyncio.run(jwt_util.create_jwt_token({'sub': 'bob'}, expires_in_minutes=1, secret='secret', algorithm='HS256'))
>>> jwt.decode(t, 'secret', algorithms=['HS256'])['sub'] == 'bob'
True
"""

# Future
from __future__ import annotations

# ===========================================
# 표준 라이브러리 임포트
# ===========================================
import argparse      # 명령줄 인자 파싱
import asyncio        # 비동기 작업 지원
import datetime as _dt  # 날짜/시간 처리
import json           # JSON 데이터 처리
import sys            # 시스템 관련 기능
from typing import Any, Dict, List, Sequence  # 타입 힌트

# ===========================================
# 외부 라이브러리 임포트 (Third-Party)
# ===========================================
import jwt  # PyJWT - JSON Web Token 처리 라이브러리

# ===========================================
# 내부 모듈 임포트 (First-Party)
# ===========================================
from mcpgateway.config import settings  # 애플리케이션 설정

__all__: Sequence[str] = (
    "create_jwt_token",
    "get_jwt_token",
    "_create_jwt_token",
)

# ---------------------------------------------------------------------------
# Defaults & constants
# ---------------------------------------------------------------------------
DEFAULT_SECRET: str = settings.jwt_secret_key
DEFAULT_ALGO: str = settings.jwt_algorithm
DEFAULT_EXP_MINUTES: int = settings.token_expiry  # 7 days (in minutes)
DEFAULT_USERNAME: str = settings.basic_auth_user


# ---------------------------------------------------------------------------
# Core sync helper (used by both CLI & async wrappers)
# ---------------------------------------------------------------------------


def _create_jwt_token(
    data: Dict[str, Any],
    expires_in_minutes: int = DEFAULT_EXP_MINUTES,
    secret: str = DEFAULT_SECRET,
    algorithm: str = DEFAULT_ALGO,
) -> str:
    """
    서명된 JWT 토큰 문자열을 반환합니다 (동기식, 타임존 인식).

    Args:
        data: 토큰에 인코딩할 페이로드 데이터를 포함하는 딕셔너리.
        expires_in_minutes: 토큰 만료 시간 (분 단위). 기본값은 7일입니다.
            0으로 설정하면 만료를 비활성화합니다.
        secret: 토큰 서명에 사용할 시크릿 키.
        algorithm: 사용할 서명 알고리즘.

    Returns:
        JWT 토큰 문자열.

    Doctest:
    >>> from mcpgateway.utils import create_jwt_token as jwt_util
    >>> jwt_util.settings.jwt_secret_key = 'secret'
    >>> jwt_util.settings.jwt_algorithm = 'HS256'
    >>> token = jwt_util._create_jwt_token({'sub': 'alice'}, expires_in_minutes=1, secret='secret', algorithm='HS256')
    >>> import jwt
    >>> jwt.decode(token, 'secret', algorithms=['HS256'])['sub'] == 'alice'
    True
    """
    # ===========================================
    # JWT 페이로드 구성 및 서명
    # ===========================================

    # 입력 데이터를 복사하여 수정하지 않도록 함
    payload = data.copy()

    # 만료 시간 설정 (양수인 경우에만)
    if expires_in_minutes > 0:
        # 현재 UTC 시간에 만료 시간(분)을 더하여 만료 시각 계산
        expire = _dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(minutes=expires_in_minutes)
        payload["exp"] = int(expire.timestamp())  # Unix 타임스탬프로 변환하여 저장
    else:
        # 만료 없는 토큰에 대한 보안 경고
        print(
            "⚠️  WARNING: Creating token without expiration. This is a security risk!\n"
            "   Consider using --exp with a value > 0 for production use.\n"
            "   Once JWT API (#425) is available, use it for automatic token renewal.",
            file=sys.stderr,
        )

    # JWT 라이브러리를 사용하여 페이로드를 인코딩하고 서명하여 반환
    return jwt.encode(payload, secret, algorithm=algorithm)


# ---------------------------------------------------------------------------
# **Async** wrappers for backward compatibility
# ---------------------------------------------------------------------------


async def create_jwt_token(
    data: Dict[str, Any],
    expires_in_minutes: int = DEFAULT_EXP_MINUTES,
    *,
    secret: str = DEFAULT_SECRET,
    algorithm: str = DEFAULT_ALGO,
) -> str:
    """
    기존 코드를 위한 비동기 파사드. 내부적으로 동기식으로 거의 즉시 실행됩니다.

    Args:
        data: 토큰에 인코딩할 페이로드 데이터를 포함하는 딕셔너리.
        expires_in_minutes: 토큰 만료 시간 (분 단위). 기본값은 7일입니다.
            0으로 설정하면 만료를 비활성화합니다.
        secret: 토큰 서명에 사용할 시크릿 키.
        algorithm: 사용할 서명 알고리즘.

    Returns:
        JWT 토큰 문자열.

    Doctest:
    >>> from mcpgateway.utils import create_jwt_token as jwt_util
    >>> jwt_util.settings.jwt_secret_key = 'secret'
    >>> jwt_util.settings.jwt_algorithm = 'HS256'
    >>> import asyncio
    >>> t = asyncio.run(jwt_util.create_jwt_token({'sub': 'bob'}, expires_in_minutes=1, secret='secret', algorithm='HS256'))
    >>> import jwt
    >>> jwt.decode(t, 'secret', algorithms=['HS256'])['sub'] == 'bob'
    True
    """
    return _create_jwt_token(data, expires_in_minutes, secret, algorithm)


async def get_jwt_token() -> str:
    """기본 관리자 사용자명을 포함한 토큰을 반환합니다 (기존 동작 미러링).

    Returns:
        기본 관리자 사용자명을 포함한 JWT 토큰 문자열.
    """
    user_data = {"username": DEFAULT_USERNAME}
    return await create_jwt_token(user_data)


# ---------------------------------------------------------------------------
# **Decode** helper (non-verifying) - used by the CLI
# ---------------------------------------------------------------------------


def _decode_jwt_token(token: str, algorithms: List[str] | None = None) -> Dict[str, Any]:
    """Decode *without* signature verification-handy for inspection.

    Args:
        token: JWT token string to decode.
        algorithms: List of allowed algorithms for decoding. Defaults to [DEFAULT_ALGO].

    Returns:
        Dictionary containing the decoded payload.
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=algorithms or [DEFAULT_ALGO],
        # options={"require": ["exp"]},  # Require expiration
    )


# ---------------------------------------------------------------------------
# CLI Parsing & helpers
# ---------------------------------------------------------------------------


def _parse_args():
    """Parse command line arguments for JWT token operations.

    Sets up an argument parser with mutually exclusive options for:
    - Creating tokens with username (-u/--username)
    - Creating tokens with custom data (-d/--data)
    - Decoding existing tokens (--decode)

    Additional options control expiration, secret key, algorithm, and output format.

    Returns:
        argparse.Namespace: Parsed command line arguments containing:
            - username: Optional username for simple payload
            - data: Optional JSON or key=value pairs for custom payload
            - decode: Optional token string to decode
            - exp: Expiration time in minutes (default: DEFAULT_EXP_MINUTES)
            - secret: Secret key for signing (default: DEFAULT_SECRET)
            - algo: Signing algorithm (default: DEFAULT_ALGO)
            - pretty: Whether to pretty-print payload before encoding

    Examples:
        >>> # Simulating command line args
        >>> import sys
        >>> sys.argv = ['jwt_cli.py', '-u', 'alice', '-e', '60']
        >>> args = _parse_args()  # doctest: +SKIP
        >>> args.username  # doctest: +SKIP
        'alice'
        >>> args.exp  # doctest: +SKIP
        60
    """
    p = argparse.ArgumentParser(
        description="Generate or inspect JSON Web Tokens.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    group = p.add_mutually_exclusive_group()
    group.add_argument("-u", "--username", help="Add username=<value> to the payload.")
    group.add_argument("-d", "--data", help="Raw JSON payload or comma-separated key=value pairs.")
    group.add_argument("--decode", metavar="TOKEN", help="Token string to decode (no verification).")

    p.add_argument(
        "-e",
        "--exp",
        type=int,
        default=DEFAULT_EXP_MINUTES,
        help="Expiration in minutes (0 disables the exp claim).",
    )
    p.add_argument("-s", "--secret", default=DEFAULT_SECRET, help="Secret key for signing.")
    p.add_argument("--algo", default=DEFAULT_ALGO, help="Signing algorithm to use.")
    p.add_argument("--pretty", action="store_true", help="Pretty-print payload before encoding.")

    return p.parse_args()


def _payload_from_cli(args) -> Dict[str, Any]:
    """Extract JWT payload from parsed command line arguments.

    Processes arguments in priority order:
    1. If username is specified, creates {"username": <value>}
    2. If data is specified, parses as JSON or key=value pairs
    3. Otherwise, returns default payload with admin username

    The data argument supports two formats:
    - JSON string: '{"key": "value", "foo": "bar"}'
    - Comma-separated pairs: 'key=value,foo=bar'

    Args:
        args: Parsed command line arguments from argparse containing
              username, data, and other JWT options.

    Returns:
        Dict[str, Any]: The payload dictionary to encode in the JWT.

    Raises:
        ValueError: If data contains invalid key=value pairs (missing '=').

    Examples:
        >>> from argparse import Namespace
        >>> args = Namespace(username='alice', data=None)
        >>> _payload_from_cli(args)
        {'username': 'alice'}
        >>> args = Namespace(username=None, data='{"role": "admin", "id": 123}')
        >>> _payload_from_cli(args)
        {'role': 'admin', 'id': 123}
        >>> args = Namespace(username=None, data='name=bob,role=user')
        >>> _payload_from_cli(args)
        {'name': 'bob', 'role': 'user'}
        >>> args = Namespace(username=None, data='invalid_format')
        >>> _payload_from_cli(args)  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        ValueError: Invalid key=value pair: 'invalid_format'
    """
    if args.username is not None:
        return {"username": args.username}

    if args.data is not None:
        # Attempt JSON first
        try:
            return json.loads(args.data)
        except json.JSONDecodeError:
            pairs = [kv.strip() for kv in args.data.split(",") if kv.strip()]
            payload: Dict[str, Any] = {}
            for pair in pairs:
                if "=" not in pair:
                    raise ValueError(f"Invalid key=value pair: '{pair}'")
                k, v = pair.split("=", 1)
                payload[k.strip()] = v.strip()
            return payload

    # Fallback default payload
    return {"username": DEFAULT_USERNAME}


# ---------------------------------------------------------------------------
# Entry point for ``python3 jwt_cli.py``
# ---------------------------------------------------------------------------


def main() -> None:  # pragma: no cover
    """JWT 명령줄 인터페이스의 진입점.

    두 가지 주요 작동 모드를 제공합니다:
    1. 토큰 생성: 지정된 페이로드로 새 JWT 생성
    2. 토큰 디코딩: 기존 JWT를 디코딩하여 표시 (검증하지 않음)

    생성 모드에서는 다음을 지원합니다:
    - 간단한 사용자명 페이로드 (-u/--username)
    - 사용자 정의 JSON 또는 key=value 페이로드 (-d/--data)
    - 설정 가능한 만료, 시크릿, 알고리즘
    - 선택적 인코딩 전 페이로드 예쁘게 출력

    디코딩 모드에서는 디코딩된 페이로드를 포맷된 JSON으로 표시합니다.

    함수는 다양한 컨텍스트에서 실행되는 것을 처리합니다:
    - 직접 스크립트 실행: 동기식으로 실행
    - 기존 asyncio 루프 내: 차단 방지를 위해 executor에 위임

    Examples:
        Command line usage::

            # Create token with username
            $ python jwt_cli.py -u alice
            eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...

            # Create token with custom data
            $ python jwt_cli.py -d '{"role": "admin", "dept": "IT"}'
            eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...

            # Decode existing token
            $ python jwt_cli.py --decode eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
            {
              "username": "alice",
              "exp": 1234567890
            }

            # Pretty print payload before encoding
            $ python jwt_cli.py -u bob --pretty
            Payload:
            {
              "username": "bob"
            }
            -
            eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
    """
    # ===========================================
    # CLI 인자 파싱 및 처리
    # ===========================================
    args = _parse_args()

    # 디코딩 모드가 우선권을 가짐
    if args.decode:
        # 토큰 디코딩 및 JSON 형식으로 출력
        decoded = _decode_jwt_token(args.decode, algorithms=[args.algo])
        json.dump(decoded, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
        return

    # CLI 인자에서 페이로드 추출
    payload = _payload_from_cli(args)

    # 예쁘게 출력 옵션이 활성화된 경우 페이로드 표시
    if args.pretty:
        print("Payload:")
        print(json.dumps(payload, indent=2, default=str))
        print("-")

    # JWT 토큰 생성 및 출력
    token = _create_jwt_token(payload, args.exp, args.secret, args.algo)
    print(token)


if __name__ == "__main__":
    # ``python3 -m mcpgateway.utils.create_jwt_token``을 통한 실행도 지원
    try:
        # 기존 asyncio 루프가 있는 경우 존중 (예: uvicorn 개발 서버 내부)
        loop = asyncio.get_running_loop()
        loop.run_until_complete(asyncio.sleep(0))  # 루프가 살아있는지 확인하는 no-op
    except RuntimeError:
        # 루프 없음 - 간단한 CLI 호출이므로 동기식으로 main 실행
        main()
    else:
        # 활성 asyncio 프로그램 내부에 있음 - 차단 방지를 위해 executor에 위임
        loop.run_in_executor(None, main)
