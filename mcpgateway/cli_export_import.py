# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/cli_export_import.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

내보내기/가져오기 CLI 명령.
이 모듈은 MCP 게이트웨이 구성의 내보내기 및 가져오기를 위한 CLI 명령을 제공합니다.
사양에 따라 다음 기능을 구현합니다:
- 필터링 옵션을 포함한 완전한 구성 내보내기
- 충돌 해결 전략을 포함한 구성 가져오기
- 가져오기용 드라이런 검증
- 교차 환경 키 회전 지원
- 진행률 보고 및 상태 추적
"""

# ===========================================
# 표준 라이브러리 임포트
# ===========================================
import argparse      # 명령줄 인자 파싱
import asyncio        # 비동기 작업 지원
import base64         # Base64 인코딩/디코딩
from datetime import datetime  # 날짜/시간 처리
import json           # JSON 데이터 처리
import logging        # 로깅 기능
import os             # 운영체제 인터페이스
from pathlib import Path  # 경로 처리
import sys            # 시스템 관련 기능
from typing import Any, Dict, Optional  # 타입 힌트

# ===========================================
# 외부 라이브러리 임포트 (Third-Party)
# ===========================================
import aiohttp        # 비동기 HTTP 클라이언트

# ===========================================
# 내부 모듈 임포트 (First-Party)
# ===========================================
from mcpgateway import __version__      # 버전 정보
from mcpgateway.config import settings  # 애플리케이션 설정

# ===========================================
# 로깅 설정
# ===========================================
logger = logging.getLogger(__name__)

# ===========================================
# 사용자 정의 예외 클래스
# ===========================================
class CLIError(Exception):
    """CLI 관련 오류의 기본 클래스."""


class AuthenticationError(CLIError):
    """인증 실패 시 발생하는 오류."""


async def get_auth_token() -> Optional[str]:
    """환경 변수 또는 구성에서 인증 토큰을 가져옵니다.

    환경 변수 MCPGATEWAY_BEARER_TOKEN을 먼저 확인하고,
    없으면 기본 인증 설정을 사용하여 Basic 인증 토큰을 생성합니다.

    Returns:
        인증 토큰 문자열 또는 구성되지 않은 경우 None
    """
    # 1. 환경 변수에서 Bearer 토큰 확인
    token = os.getenv("MCPGATEWAY_BEARER_TOKEN")
    if token:
        return token

    # 2. 기본 인증이 구성된 경우 Basic 인증 토큰 생성
    if settings.basic_auth_user and settings.basic_auth_password:
        # 사용자명:비밀번호를 Base64로 인코딩하여 Basic 인증 헤더 생성
        creds = base64.b64encode(f"{settings.basic_auth_user}:{settings.basic_auth_password}".encode()).decode()
        return f"Basic {creds}"

    # 3. 인증 설정이 없는 경우 None 반환
    return None


async def make_authenticated_request(method: str, url: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """게이트웨이 API에 인증된 HTTP 요청을 수행합니다.

    Args:
        method: HTTP 메서드 (GET, POST 등)
        url: 요청할 URL 경로
        json_data: 요청 본문용 선택적 JSON 데이터
        params: 선택적 쿼리 파라미터

    Returns:
        API로부터의 JSON 응답

    Raises:
        AuthenticationError: 인증이 구성되지 않은 경우
        CLIError: API 요청이 실패한 경우
    """
    # ===========================================
    # 인증 토큰 획득 및 검증
    # ===========================================
    token = await get_auth_token()
    if not token:
        raise AuthenticationError("인증이 구성되지 않았습니다. MCPGATEWAY_BEARER_TOKEN 환경 변수를 설정하거나 BASIC_AUTH_USER/BASIC_AUTH_PASSWORD를 구성하세요.")

    # ===========================================
    # HTTP 헤더 구성
    # ===========================================
    headers = {"Content-Type": "application/json"}
    # 토큰 타입에 따라 Authorization 헤더 설정
    if token.startswith("Basic "):
        headers["Authorization"] = token
    else:
        headers["Authorization"] = f"Bearer {token}"

    # ===========================================
    # 게이트웨이 URL 구성
    # ===========================================
    gateway_url = f"http://{settings.host}:{settings.port}"
    full_url = f"{gateway_url}{url}"

    # ===========================================
    # HTTP 요청 실행
    # ===========================================
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request(method=method, url=full_url, json=json_data, params=params, headers=headers) as response:
                # HTTP 오류 상태 코드 확인
                if response.status >= 400:
                    error_text = await response.text()
                    raise CLIError(f"API 요청 실패 ({response.status}): {error_text}")

                # 성공 응답의 JSON 데이터 반환
                return await response.json()

        except aiohttp.ClientError as e:
            # 네트워크 연결 오류 처리
            raise CLIError(f"게이트웨이 연결 실패 {gateway_url}: {str(e)}")


async def export_command(args: argparse.Namespace) -> None:
    """내보내기 명령을 실행합니다.

    Args:
        args: 파싱된 명령줄 인자
    """
    try:
        # ===========================================
        # 내보내기 작업 시작 알림
        # ===========================================
        print(f"게이트웨이에서 구성 내보내기 중: http://{settings.host}:{settings.port}")

        # ===========================================
        # API 파라미터 구성
        # ===========================================
        params = {}
        if args.types:
            params["types"] = args.types  # 포함할 엔티티 타입들
        if args.exclude_types:
            params["exclude_types"] = args.exclude_types  # 제외할 엔티티 타입들
        if args.tags:
            params["tags"] = args.tags  # 필터링할 태그들
        if args.include_inactive:
            params["include_inactive"] = "true"  # 비활성 엔티티 포함
        if not args.include_dependencies:
            params["include_dependencies"] = "false"  # 의존성 엔티티 제외

        # ===========================================
        # 내보내기 API 요청 실행
        # ===========================================
        export_data = await make_authenticated_request("GET", "/export", params=params)

        # ===========================================
        # 출력 파일 경로 결정
        # ===========================================
        if args.output:
            output_file = Path(args.output)
        else:
            # 기본 파일명: 타임스탬프 포함
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            output_file = Path(f"mcpgateway-export-{timestamp}.json")

        # ===========================================
        # 내보내기 데이터 파일에 쓰기
        # ===========================================
        output_file.parent.mkdir(parents=True, exist_ok=True)  # 부모 디렉토리 생성
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)  # 가독성 있게 저장

        # ===========================================
        # 내보내기 결과 요약 출력
        # ===========================================
        metadata = export_data.get("metadata", {})
        entity_counts = metadata.get("entity_counts", {})
        total_entities = sum(entity_counts.values())

        print("✅ 내보내기가 성공적으로 완료되었습니다!")
        print(f"📁 출력 파일: {output_file}")
        print(f"📊 총 {total_entities}개 엔티티 내보내기:")
        for entity_type, count in entity_counts.items():
            if count > 0:
                print(f"   • {entity_type}: {count}")

        # 상세 정보 출력 (verbose 모드)
        if args.verbose:
            print("\n🔍 내보내기 상세 정보:")
            print(f"   • 버전: {export_data.get('version')}")
            print(f"   • 내보내기 시각: {export_data.get('exported_at')}")
            print(f"   • 내보내기 실행자: {export_data.get('exported_by')}")
            print(f"   • 소스 게이트웨이: {export_data.get('source_gateway')}")

    except Exception as e:
        print(f"❌ 내보내기 실패: {str(e)}", file=sys.stderr)
        sys.exit(1)


async def import_command(args: argparse.Namespace) -> None:
    """가져오기 명령을 실행합니다.

    Args:
        args: 파싱된 명령줄 인자
    """
    try:
        # ===========================================
        # 입력 파일 검증
        # ===========================================
        input_file = Path(args.input_file)
        if not input_file.exists():
            print(f"❌ 입력 파일을 찾을 수 없음: {input_file}", file=sys.stderr)
            sys.exit(1)

        print(f"{input_file}에서 구성 가져오기 중")

        # ===========================================
        # 가져오기 데이터 로딩
        # ===========================================
        with open(input_file, "r", encoding="utf-8") as f:
            import_data = json.load(f)

        # ===========================================
        # 요청 데이터 구성
        # ===========================================
        request_data = {
            "import_data": import_data,
            "conflict_strategy": args.conflict_strategy,  # 충돌 해결 전략
            "dry_run": args.dry_run,                     # 드라이런 모드
        }

        # 선택적 파라미터 추가
        if args.rekey_secret:
            request_data["rekey_secret"] = args.rekey_secret  # 새 암호화 시크릿

        if args.include:
            # include 파라미터 파싱: "tool:tool1,tool2;server:server1"
            selected_entities = {}
            for selection in args.include.split(";"):
                if ":" in selection:
                    entity_type, entity_list = selection.split(":", 1)
                    entities = [e.strip() for e in entity_list.split(",") if e.strip()]
                    selected_entities[entity_type] = entities
            request_data["selected_entities"] = selected_entities  # 선택적 엔티티들

        # ===========================================
        # 가져오기 API 요청 실행
        # ===========================================
        result = await make_authenticated_request("POST", "/import", json_data=request_data)

        # ===========================================
        # 결과 출력
        # ===========================================
        status = result.get("status", "unknown")
        progress = result.get("progress", {})

        if args.dry_run:
            print("🔍 드라이런 검증 완료!")
        else:
            print(f"✅ 가져오기 {status}!")

        print("📊 결과:")
        print(f"   • 총 엔티티: {progress.get('total', 0)}")
        print(f"   • 처리됨: {progress.get('processed', 0)}")
        print(f"   • 생성됨: {progress.get('created', 0)}")
        print(f"   • 업데이트됨: {progress.get('updated', 0)}")
        print(f"   • 건너뜀: {progress.get('skipped', 0)}")
        print(f"   • 실패: {progress.get('failed', 0)}")

        # Show warnings if any
        warnings = result.get("warnings", [])
        if warnings:
            print(f"\n⚠️  Warnings ({len(warnings)}):")
            for warning in warnings[:5]:  # Show first 5 warnings
                print(f"   • {warning}")
            if len(warnings) > 5:
                print(f"   • ... and {len(warnings) - 5} more warnings")

        # Show errors if any
        errors = result.get("errors", [])
        if errors:
            print(f"\n❌ Errors ({len(errors)}):")
            for error in errors[:5]:  # Show first 5 errors
                print(f"   • {error}")
            if len(errors) > 5:
                print(f"   • ... and {len(errors) - 5} more errors")

        if args.verbose:
            print("\n🔍 Import details:")
            print(f"   • Import ID: {result.get('import_id')}")
            print(f"   • Started at: {result.get('started_at')}")
            print(f"   • Completed at: {result.get('completed_at')}")

        # Exit with error code if there were failures
        if progress.get("failed", 0) > 0:
            sys.exit(1)

    except Exception as e:
        print(f"❌ Import failed: {str(e)}", file=sys.stderr)
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """내보내기/가져오기 명령을 위한 인자 파서를 생성합니다.

    Returns:
        구성된 인자 파서
    """
    parser = argparse.ArgumentParser(prog="mcpgateway", description="MCP 게이트웨이 구성 내보내기/가져오기 도구")

    parser.add_argument("--version", "-V", action="version", version=f"mcpgateway {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export gateway configuration")
    export_parser.add_argument("--output", "--out", "-o", help="Output file path (default: mcpgateway-export-YYYYMMDD-HHMMSS.json)")
    export_parser.add_argument("--types", "--type", help="Comma-separated entity types to include (tools,gateways,servers,prompts,resources,roots)")
    export_parser.add_argument("--exclude-types", help="Comma-separated entity types to exclude")
    export_parser.add_argument("--tags", help="Comma-separated tags to filter by")
    export_parser.add_argument("--include-inactive", action="store_true", help="Include inactive entities in export")
    export_parser.add_argument("--no-dependencies", action="store_true", help="Don't include dependent entities")
    export_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    export_parser.set_defaults(func=export_command, include_dependencies=True)

    # Import command
    import_parser = subparsers.add_parser("import", help="Import gateway configuration")
    import_parser.add_argument("input_file", help="Input file containing export data")
    import_parser.add_argument("--conflict-strategy", choices=["skip", "update", "rename", "fail"], default="update", help="How to handle naming conflicts (default: update)")
    import_parser.add_argument("--dry-run", action="store_true", help="Validate but don't make changes")
    import_parser.add_argument("--rekey-secret", help="New encryption secret for cross-environment imports")
    import_parser.add_argument("--include", help="Selective import: entity_type:name1,name2;entity_type2:name3")
    import_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    import_parser.set_defaults(func=import_command)

    return parser


def main_with_subcommands() -> None:
    """내보내기/가져오기 하위 명령을 지원하는 메인 CLI 진입점."""
    parser = create_parser()

    # ===========================================
    # 명령 인자 검증 및 처리
    # ===========================================

    # 내보내기/가져오기 명령인지 확인
    if len(sys.argv) > 1 and sys.argv[1] in ["export", "import"]:
        args = parser.parse_args()

        if hasattr(args, "func"):
            # 의존성 포함 플래그 처리 (no-dependencies 플래그의 반대)
            if hasattr(args, "include_dependencies"):
                args.include_dependencies = not getattr(args, "no_dependencies", False)

            # 비동기 명령 실행
            try:
                asyncio.run(args.func(args))
            except KeyboardInterrupt:
                print("\n❌ 사용자가 작업을 취소했습니다", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(1)
    else:
        # 원래의 uvicorn 기반 CLI로 폴백
        # First-Party
        from mcpgateway.cli import main  # pylint: disable=import-outside-toplevel,cyclic-import

        main()


if __name__ == "__main__":
    main_with_subcommands()
