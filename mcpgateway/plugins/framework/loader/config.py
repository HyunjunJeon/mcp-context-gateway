# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/loader/config.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor, Mihai Criveti

설정 로더 구현.
이 모듈은 플러그인을 위한 설정들을 로드합니다.
"""

# Standard - 표준 라이브러리 import
import os  # 파일 시스템 작업을 위한 모듈

# Third-Party - 서드파티 라이브러리 import
import jinja2  # 템플릿 엔진 (환경변수 치환용)
import yaml    # YAML 파일 파싱을 위한 모듈

# First-Party - 프로젝트 내부 모듈 import
from mcpgateway.plugins.framework.models import Config  # 설정 모델


class ConfigLoader:
    """설정 파일을 로드하는 클래스.

    YAML 형식의 설정 파일을 읽어와서 플러그인 설정 객체로 변환합니다.
    Jinja2 템플릿 엔진을 사용하여 환경변수를 치환할 수 있습니다.

    Examples:
        >>> import tempfile
        >>> import os
        >>> from mcpgateway.plugins.framework.models import PluginSettings
        >>> # 임시 설정 파일 생성
        >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        ...     _ = f.write(\"\"\"
        ... plugin_settings:
        ...   enable_plugin_api: true
        ...   plugin_timeout: 30
        ... plugin_dirs: ['/path/to/plugins']
        ... \"\"\")
        ...     temp_path = f.name
        >>> try:
        ...     config = ConfigLoader.load_config(temp_path, use_jinja=False)
        ...     config.plugin_settings.enable_plugin_api
        ... finally:
        ...     os.unlink(temp_path)
        True
    """

    @staticmethod
    def load_config(config: str, use_jinja: bool = True) -> Config:
        """파일 경로에서 플러그인 설정을 로드합니다.

        Args:
            config: 설정 파일 경로
            use_jinja: True인 경우 Jinja를 사용하여 환경변수 치환

        Returns:
            플러그인 설정 객체

        Examples:
            >>> import tempfile
            >>> import os
            >>> with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            ...     _ = f.write(\"\"\"
            ... plugin_settings:
            ...   plugin_timeout: 60
            ...   enable_plugin_api: false
            ... plugin_dirs: []
            ... \"\"\")
            ...     temp_path = f.name
            >>> try:
            ...     cfg = ConfigLoader.load_config(temp_path, use_jinja=False)
            ...     cfg.plugin_settings.plugin_timeout
            ... finally:
            ...     os.unlink(temp_path)
            60
        """
        # 설정 파일을 읽어옴
        with open(os.path.normpath(config), "r", encoding="utf-8") as file:
            template = file.read()

            # Jinja 템플릿 처리 (환경변수 치환)
            if use_jinja:
                # Jinja 환경 생성 및 템플릿 렌더링
                jinja_env = jinja2.Environment(loader=jinja2.BaseLoader(), autoescape=True)
                rendered_template = jinja_env.from_string(template).render(env=os.environ)
            else:
                # Jinja 처리 없이 원본 템플릿 사용
                rendered_template = template

            # YAML 파싱
            config_data = yaml.safe_load(rendered_template)

        # Config 객체로 변환하여 반환
        return Config(**config_data)
