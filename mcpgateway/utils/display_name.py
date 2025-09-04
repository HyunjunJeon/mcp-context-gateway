# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/display_name.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

표시 이름 유틸리티.
이 모듈은 기술적인 도구 이름을 사용자 친화적인 표시 이름으로 변환하는 유틸리티를 제공합니다.

예시:
    >>> from mcpgateway.utils.display_name import generate_display_name
    >>> generate_display_name("duckduckgo_search")
    'Duckduckgo Search'
    >>> generate_display_name("weather-api")
    'Weather Api'
    >>> generate_display_name("get_user.profile")
    'Get User Profile'
"""

# Standard
import re


def generate_display_name(technical_name: str) -> str:
    """기술적인 도구 이름을 사람이 읽기 쉬운 표시 이름으로 변환합니다.

    언더스코어, 하이픈, 점을 공백으로 변환한 후 첫 글자를 대문자로 만듭니다.

    Args:
        technical_name: 기술적인 도구 이름 (예: "duckduckgo_search")

    Returns:
        str: 사람이 읽기 쉬운 표시 이름 (예: "Duckduckgo Search")

    Examples:
        >>> generate_display_name("duckduckgo_search")
        'Duckduckgo Search'
        >>> generate_display_name("weather-api")
        'Weather Api'
        >>> generate_display_name("get_user.profile")
        'Get User Profile'
        >>> generate_display_name("simple_tool")
        'Simple Tool'
        >>> generate_display_name("UPPER_CASE")
        'Upper Case'
        >>> generate_display_name("mixed_Case-Name.test")
        'Mixed Case Name Test'
        >>> generate_display_name("")
        ''
        >>> generate_display_name("single")
        'Single'
        >>> generate_display_name("multiple___underscores")
        'Multiple Underscores'
        >>> generate_display_name("tool_with-mixed.separators")
        'Tool With Mixed Separators'
    """
    if not technical_name:
        return ""

    # 언더스코어, 하이픈, 점을 공백으로 변환
    display_name = re.sub(r"[_\-\.]+", " ", technical_name)

    # 추가 공백 제거 및 첫 글자 대문자로 변환
    display_name = " ".join(display_name.split())  # 공백 정규화

    if display_name:
        # 각 단어의 첫 글자를 대문자로 (타이틀 케이스)
        display_name = display_name.title()

    return display_name
