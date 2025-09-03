# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/constants.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor

플러그인 상수 파일.
이 모듈은 프레임워크 전체에서 사용되는 플러그인 관련 상수들의 모음을 저장합니다.
"""

# 모델 상수들
# 특수 플러그인 타입들
EXTERNAL_PLUGIN_TYPE = "external"  # 외부 플러그인 타입 식별자

# MCP 관련 상수들
PYTHON_SUFFIX = ".py"        # Python 파일 확장자
URL = "url"                  # URL 키
SCRIPT = "script"            # 스크립트 키
AFTER = "after"              # after 키 (타이밍 관련)

# 일반적인 키 이름들
NAME = "name"                           # 이름 키
PYTHON = "python"                       # Python 실행 명령어
PLUGIN_NAME = "plugin_name"            # 플러그인 이름 키
PAYLOAD = "payload"                    # 페이로드 키
CONTEXT = "context"                    # 컨텍스트 키
GET_PLUGIN_CONFIG = "get_plugin_config" # 플러그인 설정 가져오기 키
IGNORE_CONFIG_EXTERNAL = "ignore_config_external"  # 외부 설정 무시 플래그
