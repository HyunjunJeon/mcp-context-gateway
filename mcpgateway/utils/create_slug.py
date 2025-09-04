# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/create_slug.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Manav Gupta

MCP Gateway용 슬러그 생성 유틸리티.
텍스트로부터 URL 친화적인 슬러그를 생성하는 유틸리티를 제공합니다.
유니코드 정규화, 특수문자 교체, 축약어 처리를 통해 깔끔하고 읽기 쉬운 슬러그를 생성합니다.
"""

# Standard
import re
from unicodedata import normalize

# First-Party
from mcpgateway.config import settings

# Helper regex patterns
CONTRACTION_PATTERN = re.compile(r"(\w)[''](\w)")
NON_ALPHANUMERIC_PATTERN = re.compile(r"[\W_]+")

# Special character replacements that normalize() doesn't handle well
SPECIAL_CHAR_MAP = {
    "æ": "ae",
    "ß": "ss",
    "ø": "o",
}


def slugify(text):
    """텍스트로부터 ASCII 슬러그를 생성합니다.

    Args:
        text(str): 입력 텍스트

    Returns:
        str: 슬러그화된 텍스트

    Examples:
        기본 슬러그화:
        >>> slugify("Hello World")
        'hello-world'
        >>> slugify("Test-Case_123")
        'test-case-123'

        특수문자 처리:
        >>> slugify("Café & Restaurant")
        'cafe-restaurant'
        >>> slugify("user@example.com")
        'user-example-com'

        축약어 처리:
        >>> slugify("Don't Stop")
        'dont-stop'
        >>> slugify("It's Working")
        'its-working'

        엣지 케이스:
        >>> slugify("")
        ''
        >>> slugify("   ")
        ''
        >>> slugify("---test---")
        'test'
        >>> slugify("Multiple   Spaces")
        'multiple-spaces'

        유니코드 정규화:
        >>> slugify("Naïve résumé")
        'naive-resume'
        >>> slugify("Zürich")
        'zurich'
    """
    # 축약어에서 아포스트로피 제거하고 소문자로 변환
    slug = CONTRACTION_PATTERN.sub(r"\1\2", text.lower())
    # 연속된 비알파벳 문자들을 단일 하이픈으로 변환하고 양끝 정리
    slug = NON_ALPHANUMERIC_PATTERN.sub(settings.gateway_tool_name_separator, slug).strip(settings.gateway_tool_name_separator)
    # 특수문자 맵에서 정의된 문자들을 교체
    for special_char, replacement in SPECIAL_CHAR_MAP.items():
        slug = slug.replace(special_char, replacement)
    # 비ASCII 텍스트를 ASCII로 정규화
    slug = normalize("NFKD", slug).encode("ascii", "ignore").decode()
    return slug
