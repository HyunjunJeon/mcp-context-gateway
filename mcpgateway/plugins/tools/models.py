# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/tools/models.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Fred Araujo

스키마 검증을 위한 MCP 플러그인 CLI 모델.
이 모듈은 스키마 검증을 위한 모델을 정의합니다.
"""

# Standard

# Third-Party
from pydantic import BaseModel


class InstallManifestPackage(BaseModel):
    """
    저장소에서 설치할 플러그인 패키지와 의존성을 지정하는
    단일 설치 매니페스트 레코드.
    """

    package: str          # 패키지 이름
    repository: str       # 저장소 URL
    extras: list[str] | None = None  # 추가 의존성 목록


class InstallManifest(BaseModel):
    """
    설치할 플러그인 패키지와 의존성을 설명하는 레코드들의
    목록을 포함하는 설치 매니페스트.
    """

    packages: list[InstallManifestPackage]  # 설치할 패키지들의 목록
