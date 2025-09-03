# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/tools/cli.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Fred Araujo

mcpplugins CLI ─ 플러그인 저작 및 패키징을 위한 명령줄 도구
이 모듈은 다음을 통해 **콘솔 스크립트**로 노출됩니다:

    [project.scripts]
    mcpplugins = "mcpgateway.plugins.tools.cli:main"

사용자가 간단히 `mcpplugins ...`를 입력하여 CLI를 사용할 수 있습니다.

기능
────
* bootstrap: 템플릿에서 새로운 플러그인 프로젝트 생성
* install: Python 환경에 플러그인 설치
* package: 플러그인을 도구로 제공하는 MCP 서버 빌드

일반적인 사용법
───────────────
```console
$ mcpplugins --help
```
"""

# Standard
import logging
from pathlib import Path
import shutil
import subprocess  # nosec B404 # Safe: Used only for git commands with hardcoded args
from typing import Optional

# Third-Party
from copier import run_copy
import typer
from typing_extensions import Annotated

# First-Party
from mcpgateway.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------
DEFAULT_TEMPLATE_URL = "https://github.com/IBM/mcp-context-forge.git"
DEFAULT_AUTHOR_NAME = "<changeme>"
DEFAULT_AUTHOR_EMAIL = "<changeme>"
DEFAULT_PROJECT_DIR = Path("./.")
DEFAULT_INSTALL_MANIFEST = Path("plugins/install.yaml")
DEFAULT_IMAGE_TAG = "contextforge-plugin:latest"  # TBD: add plugin name and version
DEFAULT_IMAGE_BUILDER = "docker"
DEFAULT_BUILD_CONTEXT = "."
DEFAULT_CONTAINERFILE_PATH = Path("docker/Dockerfile")
DEFAULT_VCS_REF = "main"
DEFAULT_INSTALLER = "uv pip install"

# ---------------------------------------------------------------------------
# CLI (overridable via environment variables)
# ---------------------------------------------------------------------------

markup_mode = settings.plugins_cli_markup_mode or typer.core.DEFAULT_MARKUP_MODE
app = typer.Typer(
    help="Command line tools for authoring and packaging plugins.",
    add_completion=settings.plugins_cli_completion,
    rich_markup_mode=None if markup_mode == "disabled" else markup_mode,
)

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def command_exists(command_name):
    """Check if a given command-line utility exists and is executable.

    Args:
        command_name: The name of the command to check (e.g., "ls", "git").

    Returns:
        True if the command exists and is executable, False otherwise.
    """
    return shutil.which(command_name) is not None


def git_user_name() -> str:
    """Return the current git user name from the environment.

    Returns:
        The git user name configured in the user's environment.

    Examples:
        >>> user_name = git_user_name()
        >>> isinstance(user_name, str)
        True
    """
    try:
        res = subprocess.run(["git", "config", "user.name"], stdout=subprocess.PIPE, check=False)  # nosec B607 B603 # Safe: hardcoded git command
        return res.stdout.strip().decode() if not res.returncode else DEFAULT_AUTHOR_NAME
    except Exception:
        return DEFAULT_AUTHOR_NAME


def git_user_email() -> str:
    """Return the current git user email from the environment.

    Returns:
        The git user email configured in the user's environment.

    Examples:
        >>> user_name = git_user_email()
        >>> isinstance(user_name, str)
        True
    """
    try:
        res = subprocess.run(["git", "config", "user.email"], stdout=subprocess.PIPE, check=False)  # nosec B607 B603 # Safe: hardcoded git command
        return res.stdout.strip().decode() if not res.returncode else DEFAULT_AUTHOR_EMAIL
    except Exception:
        return DEFAULT_AUTHOR_EMAIL


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
@app.command(help="Creates a new plugin project from template.")
def bootstrap(
    destination: Annotated[Path, typer.Option("--destination", "-d", help="플러그인 프로젝트를 부트스트랩할 디렉토리.")] = DEFAULT_PROJECT_DIR,
    template_url: Annotated[str, typer.Option("--template_url", "-u", help="플러그인 copier 템플릿의 URL.")] = DEFAULT_TEMPLATE_URL,
    vcs_ref: Annotated[str, typer.Option("--vcs_ref", "-r", help="템플릿에 사용할 버전 관리 시스템 태그/브랜치/커밋.")] = DEFAULT_VCS_REF,
    answers_file: Optional[Annotated[typer.FileText, typer.Option("--answers_file", "-a", help="부트스트랩에 사용할 응답 파일.")]] = None,
    defaults: Annotated[bool, typer.Option("--defaults", help="기본값으로 부트스트랩.")] = False,
    dry_run: Annotated[bool, typer.Option("--dry_run", help="실행하지만 변경하지 않음.")] = False,
):
    """템플릿에서 새로운 플러그인 프로젝트를 부트스트랩합니다.

    Args:
        destination: 플러그인 프로젝트를 부트스트랩할 디렉토리.
        template_url: 플러그인 copier 템플릿의 URL.
        vcs_ref: 템플릿에 사용할 버전 관리 시스템 태그/브랜치/커밋.
        answers_file: 대화형 모드를 건너뛰기 위해 사용할 수 있는 copier 응답 파일.
        defaults: 기본값으로 부트스트랩.
        dry_run: 실행하지만 변경하지 않음.
    """
    try:
        if command_exists("git"):
            run_copy(
                src_path=template_url,
                dst_path=destination,
                answers_file=answers_file,
                defaults=defaults,
                vcs_ref=vcs_ref,
                data={"default_author_name": git_user_name(), "default_author_email": git_user_email()},
                pretend=dry_run,
            )
        else:
            logger.warning("A git client was not found in the environment to copy remote template.")
    except Exception:
        logger.exception("An error was caught while copying template.")


@app.callback()
def callback():  # pragma: no cover
    """This function exists to force 'bootstrap' to be a subcommand."""


# @app.command(help="Installs plugins into a Python environment.")
# def install(
#     install_manifest: Annotated[typer.FileText, typer.Option("--install_manifest", "-i", help="The install manifest describing which plugins to install.")] = DEFAULT_INSTALL_MANIFEST,
#     installer: Annotated[str, typer.Option("--installer", "-c", help="The install command to install plugins.")] = DEFAULT_INSTALLER,
# ):
#     typer.echo(f"Installing plugin packages from {install_manifest.name}")
#     data = yaml.safe_load(install_manifest)
#     manifest = InstallManifest.model_validate(data)
#     for pkg in manifest.packages:
#         typer.echo(f"Installing plugin package {pkg.package} from {pkg.repository}")
#         repository = os.path.expandvars(pkg.repository)
#         cmd = installer.split(" ")
#         if pkg.extras:
#             cmd.append(f"{pkg.package}[{','.join(pkg.extras)}]@{repository}")
#         else:
#             cmd.append(f"{pkg.package}@{repository}")
#         subprocess.run(cmd)


# @app.command(help="Builds an MCP server to serve plugins as tools.")
# def package(
#     image_tag: Annotated[str, typer.Option("--image_tag", "-t", help="The container image tag to generated container.")] = DEFAULT_IMAGE_TAG,
#     containerfile: Annotated[Path, typer.Option("--containerfile", "-c", help="The Dockerfile used to build the container.")] = DEFAULT_CONTAINERFILE_PATH,
#     builder: Annotated[str, typer.Option("--builder", "-b", help="The container builder, compatible with docker build.")] = DEFAULT_IMAGE_BUILDER,
#     build_context: Annotated[Path, typer.Option("--build_context", "-p", help="The container builder context, specified as a path.")] = DEFAULT_BUILD_CONTEXT,
# ):
#     typer.echo("Building MCP server image")
#     cmd = builder.split(" ")
#     cmd.extend(["-f", containerfile, "-t", image_tag, build_context])
#     subprocess.run(cmd)


def main() -> None:  # noqa: D401 - imperative mood is fine here
    """*mcpplugins* 콘솔 스크립트의 진입점.

    명령줄 인자를 처리하고 버전 요청을 처리하며,
    다른 모든 인자들을 적절한 기본값과 함께 Uvicorn에 전달합니다.

    환경 변수:
        PLUGINS_CLI_COMPLETION: 플러그인 CLI의 자동 완성 활성화 (기본값: false)
        PLUGINS_CLI_MARKUP_MODE: 플러그인 CLI의 마크업 모드 설정 (기본값: rich)
            유효한 옵션:
                rich: rich 마크업 사용
                markdown: 도움말 문자열에 마크다운 허용
                disabled: 마크업 비활성화
            설정되지 않은 경우(주석 처리됨), rich가 감지되면 "rich"를 사용하고 그렇지 않으면 비활성화합니다.
    """
    app()


if __name__ == "__main__":  # pragma: no cover - executed only when run directly
    main()
