# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/plugins/framework/errors.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Teryl Taylor

플러그인을 위한 Pydantic 모델들.
이 모듈은 기본 플러그인 계층과 관련된 Pydantic 모델들을 구현합니다.
설정, 컨텍스트, 오류 모델들을 포함합니다.
"""

# First-Party - 플러그인 프레임워크의 모델들을 import
from mcpgateway.plugins.framework.models import PluginErrorModel, PluginViolation


class PluginViolationError(Exception):
    """플러그인 위반 오류.

    플러그인이 정책이나 규칙을 위반했을 때 발생하는 오류입니다.

    Attributes:
        violation (PluginViolation): 플러그인 위반사항 객체
        message (str): 위반 이유 메시지
    """

    def __init__(self, message: str, violation: PluginViolation | None = None):
        """플러그인 위반 오류를 초기화합니다.

        Args:
            message: 위반 오류의 이유
            violation: 플러그인 위반 객체의 세부 사항
        """
        self.message = message
        self.violation = violation
        super().__init__(self.message)


class PluginError(Exception):
    """플러그인 내부 오류를 위한 오류 객체.

    플러그인 실행 중 발생하는 내부 오류들을 처리하기 위한 클래스입니다.

    Attributes:
        error (PluginErrorModel): 플러그인 오류 객체
    """

    def __init__(self, error: PluginErrorModel):
        """플러그인 오류를 초기화합니다.

        Args:
            error: 플러그인 오류 세부 사항
        """
        self.error = error
        super().__init__(self.error.message)


def convert_exception_to_error(exception: Exception, plugin_name: str) -> PluginErrorModel:
    """예외 객체를 PluginErrorModel로 변환합니다. 주로 외부 플러그인 오류 처리에 사용됩니다.

    Args:
        exception: 변환할 예외 객체
        plugin_name: 예외가 발생한 플러그인의 이름

    Returns:
        HTTP로 전송할 수 있는 Pydantic 플러그인 오류 객체
    """
    return PluginErrorModel(message=repr(exception), plugin_name=plugin_name)
