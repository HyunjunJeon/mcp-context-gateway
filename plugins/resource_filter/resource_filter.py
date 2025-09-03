# -*- coding: utf-8 -*-
"""리소스 필터 플러그인 - 리소스 후크 기능 데모.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

이 플러그인은 resource_pre_fetch 및 resource_post_fetch 후크를 사용하여
리소스 콘텐츠를 필터링하고 수정하는 방법을 보여줍니다.
다음과 같은 기능들을 수행할 수 있습니다:
- URI 패턴이나 프로토콜에 기반하여 리소스 차단
- 리소스 콘텐츠 크기 제한
- 리소스 콘텐츠에서 민감한 정보 삭제
- 리소스에 메타데이터 추가
"""

import re
from urllib.parse import urlparse

from mcpgateway.plugins.framework import (
    Plugin,
    PluginConfig,
    PluginContext,
    PluginMode,
    PluginViolation,
    ResourcePostFetchPayload,
    ResourcePostFetchResult,
    ResourcePreFetchPayload,
    ResourcePreFetchResult,
)


class ResourceFilterPlugin(Plugin):
    """리소스를 필터링하고 수정하는 플러그인.

    이 플러그인은 리소스 후크를 사용하여 다음 기능들을 수행합니다:
    - 리소스 가져오기 전 URI 검증
    - 가져온 후 콘텐츠 필터링
    - 리소스에 메타데이터 추가
    - 특정 프로토콜이나 도메인 차단
    """

    def __init__(self, config: PluginConfig) -> None:
        """리소스 필터 플러그인을 초기화합니다.

        Args:
            config: 필터 설정을 포함하는 플러그인 설정
        """
        # 부모 클래스 초기화
        super().__init__(config)

        # 플러그인 설정에서 필터링 옵션들을 로드 (기본값 포함)
        plugin_config = config.config if config.config else {}

        # 최대 콘텐츠 크기 설정 (기본값: 1MB)
        self.max_content_size = plugin_config.get("max_content_size", 1048576)

        # 허용되는 프로토콜 목록 (기본값: file, http, https)
        self.allowed_protocols = plugin_config.get("allowed_protocols", ["file", "http", "https"])

        # 차단된 도메인 목록
        self.blocked_domains = plugin_config.get("blocked_domains", [])

        # 콘텐츠 필터링 규칙들
        self.content_filters = plugin_config.get("content_filters", [])

    async def resource_pre_fetch(
        self, payload: ResourcePreFetchPayload, context: PluginContext
    ) -> ResourcePreFetchResult:
        """리소스 가져오기 전 요청을 검증하고 수정하는 메서드.

        Args:
            payload: URI와 메타데이터를 포함하는 리소스 사전 가져오기 페이로드
            context: 플러그인 실행 맥락

        Returns:
            계속 진행 여부와 수정사항을 나타내는 ResourcePreFetchResult
        """
        # URI 파싱 시도
        try:
            parsed = urlparse(payload.uri)
        except Exception as e:
            # URI 파싱 실패 시 위반사항 생성
            violation = PluginViolation(
                reason="유효하지 않은 URI",
                description=f"리소스 URI를 파싱할 수 없습니다: {e}",
                code="INVALID_URI",
                details={"uri": payload.uri, "error": str(e)}
            )
            return ResourcePreFetchResult(
                continue_processing=False,
                violation=violation
            )

        # Check if URI has a scheme
        if not parsed.scheme:
            violation = PluginViolation(
                reason="Invalid URI format",
                description="URI must have a valid scheme (protocol)",
                code="INVALID_URI",
                details={"uri": payload.uri}
            )
            # In permissive mode, log but continue
            if self.mode == PluginMode.PERMISSIVE:
                return ResourcePreFetchResult(
                    continue_processing=True,
                    violation=violation,
                    modified_payload=payload
                )
            return ResourcePreFetchResult(
                continue_processing=False,
                violation=violation
            )

        # Check protocol
        if parsed.scheme not in self.allowed_protocols:
            violation = PluginViolation(
                reason="Protocol not allowed",
                description=f"Protocol '{parsed.scheme}' is not in allowed list",
                code="PROTOCOL_BLOCKED",
                details={
                    "uri": payload.uri,
                    "protocol": parsed.scheme,
                    "allowed": self.allowed_protocols
                }
            )
            # In permissive mode, log but continue
            if self.mode == PluginMode.PERMISSIVE:
                return ResourcePreFetchResult(
                    continue_processing=True,
                    violation=violation,
                    modified_payload=payload
                )
            return ResourcePreFetchResult(
                continue_processing=False,
                violation=violation
            )

        # Check domain blocking (case-insensitive)
        if parsed.netloc:
            # Convert both to lowercase for comparison
            domain_lower = parsed.netloc.lower()
            blocked_domains_lower = [d.lower() for d in self.blocked_domains]
            if domain_lower in blocked_domains_lower or any(domain_lower.endswith('.' + d) for d in blocked_domains_lower):
                violation = PluginViolation(
                    reason="Domain is blocked",
                    description=f"Domain '{parsed.netloc}' is in blocked list",
                    code="DOMAIN_BLOCKED",
                    details={
                        "uri": payload.uri,
                        "domain": parsed.netloc
                    }
                )
                # In permissive mode, log but continue
                if self.mode == PluginMode.PERMISSIVE:
                    return ResourcePreFetchResult(
                        continue_processing=True,
                        violation=violation,
                        modified_payload=payload
                    )
                return ResourcePreFetchResult(
                    continue_processing=False,
                    violation=violation
                )

        # Add metadata to track this plugin processed the request
        modified_payload = ResourcePreFetchPayload(
            uri=payload.uri,
            metadata={
                **payload.metadata,
                "validated": True,
                "protocol": parsed.scheme,
                "request_id": context.request_id,
                "user": context.user,
                "resource_filter_plugin": "pre_fetch_validated",
                "allowed_size": self.max_content_size
            }
        )

        # Store validation info in context for post-fetch
        context.set_state("uri_validated", True)
        context.set_state("original_uri", payload.uri)

        return ResourcePreFetchResult(
            continue_processing=True,
            modified_payload=modified_payload,
            metadata={"validation": "passed"}
        )

    async def resource_post_fetch(
        self, payload: ResourcePostFetchPayload, context: PluginContext
    ) -> ResourcePostFetchResult:
        """가져온 후 리소스 콘텐츠를 필터링하고 수정하는 메서드.

        Args:
            payload: 가져온 콘텐츠를 포함하는 리소스 사후 가져오기 페이로드
            context: 플러그인 실행 맥락

        Returns:
            잠재적으로 수정된 콘텐츠를 포함하는 ResourcePostFetchResult
        """
        # 사전 가져오기 검증이 수행되었는지 확인
        if not context.get_state("uri_validated"):
            # 이 리소스는 사전 가져오기에서 검증되지 않았으므로 처리 건너뜀
            return ResourcePostFetchResult(
                continue_processing=True,
                modified_payload=payload
            )

        # Process content if it's text
        modified_content = payload.content
        content_was_modified = False

        # Apply content filters if we have text content
        if hasattr(payload.content, 'text') and payload.content.text:
            original_text = payload.content.text
            filtered_text = original_text

            # Check content size
            if len(filtered_text.encode('utf-8')) > self.max_content_size:
                violation = PluginViolation(
                    reason="Content exceeds maximum size",
                    description=f"Resource content exceeds maximum size of {self.max_content_size} bytes",
                    code="CONTENT_TOO_LARGE",
                    details={
                        "uri": payload.uri,
                        "size": len(filtered_text.encode('utf-8')),
                        "max_size": self.max_content_size
                    }
                )
                # In permissive mode, log but continue
                if self.mode == PluginMode.PERMISSIVE:
                    return ResourcePostFetchResult(
                        continue_processing=True,
                        violation=violation,
                        modified_payload=payload
                    )
                return ResourcePostFetchResult(
                    continue_processing=False,
                    violation=violation
                )

            # Apply content filters
            for filter_rule in self.content_filters:
                pattern = filter_rule.get("pattern")
                replacement = filter_rule.get("replacement", "***")
                if pattern:
                    filtered_text = re.sub(
                        pattern,
                        replacement,
                        filtered_text,
                        flags=re.IGNORECASE
                    )

            # Update content if it was modified
            if filtered_text != original_text:
                # Create new content object with filtered text
                from mcpgateway.models import ResourceContent
                modified_content = ResourceContent(
                    type=payload.content.type,
                    uri=payload.content.uri,
                    text=filtered_text
                )
                content_was_modified = True
                context.set_state("content_filtered", True)

        # Only create modified payload if content was actually modified
        if content_was_modified:
            modified_payload = ResourcePostFetchPayload(
                uri=payload.uri,
                content=modified_content
            )
        else:
            # Return original payload if nothing was modified
            modified_payload = payload

        return ResourcePostFetchResult(
            continue_processing=True,
            modified_payload=modified_payload,
            metadata={
                "filtered": context.get_state("content_filtered", False),
                "original_uri": context.get_state("original_uri")
            }
        )
