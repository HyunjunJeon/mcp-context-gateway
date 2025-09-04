# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/cli.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

mcpgateway CLI ─ Uvicorn을 감싸는 얇은 래퍼
이 모듈은 다음을 통해 **콘솔 스크립트**로 노출됩니다:

    [project.scripts]
    mcpgateway = "mcpgateway.cli:main"

이를 통해 사용자는 긴 명령어인
`uvicorn mcpgateway.main:app ...` 대신 간단히 `mcpgateway ...`를 입력할 수 있습니다.

기능
────
* 사용자가 명시적으로 제공하지 않은 경우 기본 FastAPI 애플리케이션 경로
  (``mcpgateway.main:app``)를 주입합니다.
* 사용자가 ``--host``/``--port``를 전달하거나 환경 변수
  ``MCG_HOST`` 및 ``MCG_PORT``를 통해 재정의하지 않는 한
  합리적인 기본 호스트/포트(127.0.0.1:4444)를 추가합니다.
* 모든 나머지 인자를 Uvicorn의 자체 CLI로 있는 그대로 전달하므로
  `--reload`, `--workers` 등이 정확히 동일하게 작동합니다.

일반적인 사용법
───────────────
```console
$ mcpgateway --reload                 # 127.0.0.1:4444에서 개발 서버 실행
$ mcpgateway --workers 4              # 프로덕션 스타일 다중 프로세스
$ mcpgateway 127.0.0.1:8000 --reload  # 명시적 호스트/포트는 기본값을 제외
$ mcpgateway mypkg.other:app          # 다른 ASGI 콜러블 실행
```
"""

# Future
from __future__ import annotations

# ===========================================
# 표준 라이브러리 임포트
# ===========================================
import os       # 운영체제 인터페이스 (환경 변수 접근)
import sys      # 시스템 관련 기능 (sys.argv 등)
from typing import List  # 타입 힌트

# ===========================================
# 외부 라이브러리 임포트 (Third-Party)
# ===========================================
import uvicorn  # ASGI 서버

# ===========================================
# 내부 모듈 임포트 (First-Party)
# ===========================================
from mcpgateway import __version__  # 버전 정보

# ===========================================
# 구성 기본값 (환경 변수를 통해 재정의 가능)
# ===========================================
DEFAULT_APP = "mcpgateway.main:app"  # FastAPI 인스턴스로의 점선 경로
DEFAULT_HOST = os.getenv("MCG_HOST", "127.0.0.1")  # 기본 호스트 주소
DEFAULT_PORT = int(os.getenv("MCG_PORT", "4444"))  # 기본 포트 번호

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _needs_app(arg_list: List[str]) -> bool:
    """CLI 호출에 위치 APP 경로가 *없는* 경우 *True*를 반환합니다.

    Uvicorn의 인자 문법에 따르면, **첫 번째** 비플래그 토큰이
    애플리케이션 경로로 사용됩니다. 따라서 *arg_list*의 첫 번째 요소를 확인합니다.
    대시로 시작하면 옵션이므로 APP 경로가 누락되었고, 우리의 경로를 주입해야 합니다.

    Args:
        arg_list (List[str]): 인자 목록

    Returns:
        bool: CLI 호출에 위치 APP 경로가 *없는* 경우 *True* 반환

    Examples:
        >>> _needs_app([])
        True
        >>> _needs_app(["--reload"])
        True
        >>> _needs_app(["myapp.main:app"])
        False
    """

    return len(arg_list) == 0 or arg_list[0].startswith("-")


def _insert_defaults(raw_args: List[str]) -> List[str]:
    """필요한 곳에 기본값을 추가한 *새로운* argv를 반환합니다.

    Args:
        raw_args (List[str]): CLI에 대한 입력 인자 목록

    Returns:
        List[str]: 인자 목록

    Examples:
        >>> result = _insert_defaults([])
        >>> result[0]
        'mcpgateway.main:app'
        >>> result = _insert_defaults(["myapp.main:app", "--reload"])
        >>> result[0]
        'myapp.main:app'
    """

    args = list(raw_args)  # 얕은 복사 - 이걸 변경할 것입니다

    # 1️⃣  애플리케이션 경로가 있는지 확인
    if _needs_app(args):
        args.insert(0, DEFAULT_APP)

    # 2️⃣  UNIX 도메인 소켓이 아닌 경우 호스트/포트 제공
    if "--uds" not in args:
        # 호스트가 제공되지 않은 경우 기본 호스트 추가
        if "--host" not in args and "--http" not in args:
            args.extend(["--host", DEFAULT_HOST])
        # 포트가 제공되지 않은 경우 기본 포트 추가
        if "--port" not in args:
            args.extend(["--port", str(DEFAULT_PORT)])

    return args


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: D401 - imperative mood is fine here
    """*mcpgateway* 콘솔 스크립트의 진입점 (Uvicorn에 위임).

    명령줄 인자를 처리하고, 버전 요청을 처리하며,
    합리적인 기본값을 주입하여 다른 모든 인자를 Uvicorn으로 전달합니다.

    구성 관리를 위한 내보내기/가져오기 하위 명령도 지원합니다.

    환경 변수:
        MCG_HOST: 기본 호스트 (기본값: "127.0.0.1")
        MCG_PORT: 기본 포트 (기본값: "4444")
    """

    # ===========================================
    # 명령 처리 및 라우팅
    # ===========================================

    # 1. 내보내기/가져오기 명령인지 먼저 확인
    if len(sys.argv) > 1 and sys.argv[1] in ["export", "import"]:
        # 순환 임포트 방지를 위해 필요할 때만 임포트
        # First-Party
        from mcpgateway.cli_export_import import main_with_subcommands  # pylint: disable=import-outside-toplevel,cyclic-import

        main_with_subcommands()
        return

    # 2. 버전 플래그 확인
    if "--version" in sys.argv or "-V" in sys.argv:
        print(f"mcpgateway {__version__}")
        return

    # 3. 프로그램 이름을 버리고 나머지를 검사
    user_args = sys.argv[1:]
    uvicorn_argv = _insert_defaults(user_args)

    # 4. Uvicorn의 `main()`이 sys.argv를 사용하므로 패치하고 실행
    sys.argv = ["mcpgateway", *uvicorn_argv]
    uvicorn.main()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":  # pragma: no cover - executed only when run directly
    main()
