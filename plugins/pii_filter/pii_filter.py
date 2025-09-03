# -*- coding: utf-8 -*-
"""MCP 게이트웨이를 위한 PII 필터 플러그인.

Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

이 플러그인은 프롬프트와 응답에서 개인 식별 정보(PII)를 탐지하고 마스킹합니다.
SSN, 신용카드, 이메일, 전화번호 등을 포함합니다.
"""

# Standard
import re
from enum import Enum
from typing import Any, Pattern, Dict, List, Tuple

# Third-Party
from pydantic import BaseModel, Field

# First-Party
from mcpgateway.plugins.framework import (
    Plugin,
    PluginConfig,
    PluginContext,
    PluginViolation,
    PromptPosthookPayload,
    PromptPosthookResult,
    PromptPrehookPayload,
    PromptPrehookResult,
    ToolPreInvokePayload,
    ToolPreInvokeResult,
    ToolPostInvokePayload,
    ToolPostInvokeResult,
)
from mcpgateway.services.logging_service import LoggingService

# Initialize logging service first
logging_service = LoggingService()
logger = logging_service.get_logger(__name__)


class PIIType(str, Enum):
    """탐지할 수 있는 PII(개인 식별 정보)의 유형들."""

    SSN = "ssn"                    # 사회보장번호
    CREDIT_CARD = "credit_card"    # 신용카드 번호
    EMAIL = "email"               # 이메일 주소
    PHONE = "phone"               # 전화번호
    IP_ADDRESS = "ip_address"     # IP 주소
    DATE_OF_BIRTH = "date_of_birth" # 생년월일
    PASSPORT = "passport"         # 여권 번호
    DRIVER_LICENSE = "driver_license" # 운전면허증 번호
    BANK_ACCOUNT = "bank_account" # 은행 계좌 번호
    MEDICAL_RECORD = "medical_record" # 의료 기록 번호
    AWS_KEY = "aws_key"          # AWS 액세스 키
    API_KEY = "api_key"          # API 키
    CUSTOM = "custom"            # 사용자 정의 패턴


class MaskingStrategy(str, Enum):
    """탐지된 PII를 마스킹하는 전략들."""

    REDACT = "redact"     # [REDACTED]로 교체
    PARTIAL = "partial"   # 부분 정보 표시 (예: ***-**-1234)
    HASH = "hash"        # 해시로 교체
    TOKENIZE = "tokenize" # 토큰으로 교체
    REMOVE = "remove"    # 완전히 제거


class PIIPattern(BaseModel):
    """PII 패턴을 위한 설정 클래스."""

    type: PIIType                    # PII 유형
    pattern: str                    # 정규식 패턴
    description: str               # 패턴 설명
    mask_strategy: MaskingStrategy = MaskingStrategy.REDACT  # 마스킹 전략 (기본값: REDACT)
    enabled: bool = True           # 패턴 활성화 여부 (기본값: True)


class PIIFilterConfig(BaseModel):
    """PII 필터 플러그인을 위한 설정 클래스."""

    # 특정 PII 유형에 대한 탐지 활성화/비활성화
    detect_ssn: bool = Field(default=True, description="사회보장번호 탐지")
    detect_credit_card: bool = Field(default=True, description="신용카드 번호 탐지")
    detect_email: bool = Field(default=True, description="이메일 주소 탐지")
    detect_phone: bool = Field(default=True, description="전화번호 탐지")
    detect_ip_address: bool = Field(default=True, description="IP 주소 탐지")
    detect_date_of_birth: bool = Field(default=True, description="생년월일 탐지")
    detect_passport: bool = Field(default=True, description="여권 번호 탐지")
    detect_driver_license: bool = Field(default=True, description="운전면허증 번호 탐지")
    detect_bank_account: bool = Field(default=True, description="은행 계좌 번호 탐지")
    detect_medical_record: bool = Field(default=True, description="의료 기록 번호 탐지")
    detect_aws_keys: bool = Field(default=True, description="AWS 액세스 키 탐지")
    detect_api_keys: bool = Field(default=True, description="일반 API 키 탐지")

    # 마스킹 설정
    default_mask_strategy: MaskingStrategy = Field(
        default=MaskingStrategy.REDACT,
        description="기본 마스킹 전략"
    )
    redaction_text: str = Field(default="[REDACTED]", description="삭제 시 사용할 텍스트")

    # 동작 설정
    block_on_detection: bool = Field(
        default=False,
        description="PII 탐지 시 요청 차단"
    )
    log_detections: bool = Field(default=True, description="PII 탐지 로그 기록")
    include_detection_details: bool = Field(
        default=True,
        description="메타데이터에 탐지 상세 정보 포함"
    )

    # 사용자 정의 패턴
    custom_patterns: List[PIIPattern] = Field(
        default_factory=list,
        description="탐지할 사용자 정의 PII 패턴들"
    )

    # 화이트리스트 설정
    whitelist_patterns: List[str] = Field(
        default_factory=list,
        description="PII 탐지에서 제외할 패턴들"
    )


class PIIDetector:
    """PII 탐지를 위한 핵심 로직 클래스.

    이 클래스는 텍스트에서 다양한 유형의 PII를 탐지하고
    적절한 마스킹 전략을 적용하는 기능을 제공합니다.
    """

    def __init__(self, config: PIIFilterConfig):
        """PII 탐지기를 설정으로 초기화합니다.

        Args:
            config: PII 필터 설정 객체
        """
        self.config = config
        # PII 유형별로 컴파일된 정규식 패턴들을 저장하는 딕셔너리
        self.patterns: Dict[PIIType, List[Tuple[Pattern, MaskingStrategy]]] = {}
        # 패턴들을 컴파일하여 준비
        self._compile_patterns()
        # 화이트리스트 패턴들도 컴파일
        self._compile_whitelist()

    def _compile_patterns(self) -> None:
        """PII 탐지를 위한 정규식 패턴들을 컴파일합니다.

        설정에서 활성화된 PII 유형에 따라 적절한 정규식 패턴들을
        생성하고 컴파일하여 탐지 준비를 완료합니다.
        """
        # 컴파일할 패턴들을 저장할 리스트
        patterns = []

        # 사회보장번호 패턴 - 하이픈 포함 형식과 9자리 연속 형식 모두 지원
        if self.config.detect_ssn:
            patterns.append(PIIPattern(
                type=PIIType.SSN,
                pattern=r'\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b',
                description="미국 사회보장번호",
                mask_strategy=MaskingStrategy.PARTIAL
            ))

        # 신용카드 패턴 - 일반적인 16자리 카드 번호 형식 (하이픈이나 공백 포함)
        if self.config.detect_credit_card:
            patterns.append(PIIPattern(
                type=PIIType.CREDIT_CARD,
                pattern=r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
                description="신용카드 번호",
                mask_strategy=MaskingStrategy.PARTIAL
            ))

        # Email patterns
        if self.config.detect_email:
            patterns.append(PIIPattern(
                type=PIIType.EMAIL,
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                description="Email address",
                mask_strategy=MaskingStrategy.PARTIAL
            ))

        # Phone number patterns (US and international)
        if self.config.detect_phone:
            patterns.extend([
                PIIPattern(
                    type=PIIType.PHONE,
                    pattern=r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
                    description="US phone number",
                    mask_strategy=MaskingStrategy.PARTIAL
                ),
                PIIPattern(
                    type=PIIType.PHONE,
                    pattern=r'\b\+?[1-9]\d{1,14}\b',
                    description="International phone number",
                    mask_strategy=MaskingStrategy.PARTIAL
                )
            ])

        # IP Address patterns (IPv4 and IPv6)
        if self.config.detect_ip_address:
            patterns.extend([
                PIIPattern(
                    type=PIIType.IP_ADDRESS,
                    pattern=r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
                    description="IPv4 address",
                    mask_strategy=MaskingStrategy.REDACT
                ),
                PIIPattern(
                    type=PIIType.IP_ADDRESS,
                    pattern=r'\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b',
                    description="IPv6 address",
                    mask_strategy=MaskingStrategy.REDACT
                )
            ])

        # Date of Birth patterns
        if self.config.detect_date_of_birth:
            patterns.extend([
                PIIPattern(
                    type=PIIType.DATE_OF_BIRTH,
                    pattern=r'\b(?:DOB|Date of Birth|Born|Birthday)[:\s]+\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
                    description="Date of birth with label",
                    mask_strategy=MaskingStrategy.REDACT
                ),
                PIIPattern(
                    type=PIIType.DATE_OF_BIRTH,
                    pattern=r'\b(?:0[1-9]|1[0-2])[-/](?:0[1-9]|[12]\d|3[01])[-/](?:19|20)\d{2}\b',
                    description="Date in MM/DD/YYYY format",
                    mask_strategy=MaskingStrategy.REDACT
                )
            ])

        # Passport patterns
        if self.config.detect_passport:
            patterns.append(PIIPattern(
                type=PIIType.PASSPORT,
                pattern=r'\b[A-Z]{1,2}\d{6,9}\b',
                description="Passport number",
                mask_strategy=MaskingStrategy.REDACT
            ))

        # Driver's License patterns (US states)
        if self.config.detect_driver_license:
            patterns.append(PIIPattern(
                type=PIIType.DRIVER_LICENSE,
                pattern=r'\b(?:DL|License|Driver\'?s? License)[#:\s]+[A-Z0-9]{5,20}\b',
                description="Driver's license number",
                mask_strategy=MaskingStrategy.REDACT
            ))

        # Bank Account patterns
        if self.config.detect_bank_account:
            patterns.extend([
                PIIPattern(
                    type=PIIType.BANK_ACCOUNT,
                    pattern=r'\b\d{8,17}\b',  # Generic bank account
                    description="Bank account number",
                    mask_strategy=MaskingStrategy.REDACT
                ),
                PIIPattern(
                    type=PIIType.BANK_ACCOUNT,
                    pattern=r'\b[A-Z]{2}\d{2}[A-Z0-9]{4}\d{7}(?:\d{3})?\b',  # IBAN
                    description="IBAN",
                    mask_strategy=MaskingStrategy.PARTIAL
                )
            ])

        # Medical Record patterns
        if self.config.detect_medical_record:
            patterns.append(PIIPattern(
                type=PIIType.MEDICAL_RECORD,
                pattern=r'\b(?:MRN|Medical Record)[#:\s]+[A-Z0-9]{6,12}\b',
                description="Medical record number",
                mask_strategy=MaskingStrategy.REDACT
            ))

        # AWS Access Key patterns
        if self.config.detect_aws_keys:
            patterns.extend([
                PIIPattern(
                    type=PIIType.AWS_KEY,
                    pattern=r'\bAKIA[0-9A-Z]{16}\b',
                    description="AWS Access Key ID",
                    mask_strategy=MaskingStrategy.REDACT
                ),
                PIIPattern(
                    type=PIIType.AWS_KEY,
                    pattern=r'\b[A-Za-z0-9/+=]{40}\b',
                    description="AWS Secret Access Key",
                    mask_strategy=MaskingStrategy.REDACT
                )
            ])

        # Generic API Key patterns
        if self.config.detect_api_keys:
            patterns.append(PIIPattern(
                type=PIIType.API_KEY,
                pattern=r'\b(?:api[_-]?key|apikey|api_token|access[_-]?token)[:\s]+[\'"]?[A-Za-z0-9\-_]{20,}[\'"]?\b',
                description="Generic API key",
                mask_strategy=MaskingStrategy.REDACT
            ))

        # Add custom patterns
        patterns.extend(self.config.custom_patterns)

        # Compile patterns by type
        for pattern_config in patterns:
            if pattern_config.enabled:
                compiled = re.compile(pattern_config.pattern, re.IGNORECASE)
                if pattern_config.type not in self.patterns:
                    self.patterns[pattern_config.type] = []
                self.patterns[pattern_config.type].append(
                    (compiled, pattern_config.mask_strategy)
                )

    def _compile_whitelist(self) -> None:
        """Compile whitelist patterns."""
        self.whitelist_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.config.whitelist_patterns
        ]

    def _is_whitelisted(self, text: str, match_start: int, match_end: int) -> bool:
        """Check if a matched pattern is whitelisted.

        Args:
            text: The full text
            match_start: Start position of the match
            match_end: End position of the match

        Returns:
            True if the match is whitelisted
        """
        match_text = text[match_start:match_end]
        for pattern in self.whitelist_patterns:
            if pattern.search(match_text):
                return True
        return False

    def detect(self, text: str) -> Dict[PIIType, List[Dict]]:
        """Detect PII in text.

        Args:
            text: Text to scan for PII

        Returns:
            Dictionary of detected PII by type
        """
        detections = {}

        for pii_type, pattern_list in self.patterns.items():
            type_detections = []
            seen_ranges = []  # Track ranges we've already detected

            for pattern, mask_strategy in pattern_list:
                for match in pattern.finditer(text):
                    if not self._is_whitelisted(text, match.start(), match.end()):
                        # Check if this overlaps with any existing detection
                        overlaps = False
                        for start, end in seen_ranges:
                            if (match.start() >= start and match.start() < end) or \
                            (match.end() > start and match.end() <= end) or \
                            (match.start() <= start and match.end() >= end):
                                overlaps = True
                                break

                        if not overlaps:
                            type_detections.append({
                                'value': match.group(),
                                'start': match.start(),
                                'end': match.end(),
                                'mask_strategy': mask_strategy
                            })
                            seen_ranges.append((match.start(), match.end()))

            if type_detections:
                detections[pii_type] = type_detections

        return detections

    def mask(self, text: str, detections: Dict[PIIType, List[Dict]]) -> str:
        """Mask detected PII in text.

        Args:
            text: Original text
            detections: Dictionary of detected PII

        Returns:
            Text with PII masked
        """
        if not detections:
            return text

        # Sort all detections by position (reverse order for replacement)
        all_detections = []
        for pii_type, items in detections.items():
            for item in items:
                item['type'] = pii_type
                all_detections.append(item)

        all_detections.sort(key=lambda x: x['start'], reverse=True)

        # Apply masking
        masked_text = text
        for detection in all_detections:
            strategy = detection.get('mask_strategy', self.config.default_mask_strategy)
            masked_value = self._apply_mask(
                detection['value'],
                detection['type'],
                strategy
            )
            masked_text = (
                masked_text[:detection['start']] +
                masked_value +
                masked_text[detection['end']:]
            )

        return masked_text

    def _apply_mask(self, value: str, pii_type: PIIType, strategy: MaskingStrategy) -> str:
        """Apply masking strategy to a value.

        Args:
            value: Value to mask
            pii_type: Type of PII
            strategy: Masking strategy to apply

        Returns:
            Masked value
        """
        if strategy == MaskingStrategy.REDACT:
            return self.config.redaction_text

        elif strategy == MaskingStrategy.PARTIAL:
            # Show partial information based on type
            if pii_type == PIIType.SSN:
                if len(value) >= 4:
                    return f"***-**-{value[-4:]}"
                return self.config.redaction_text

            elif pii_type == PIIType.CREDIT_CARD:
                if len(value) >= 4:
                    return f"****-****-****-{value[-4:]}"
                return self.config.redaction_text

            elif pii_type == PIIType.EMAIL:
                parts = value.split('@')
                if len(parts) == 2:
                    name = parts[0]
                    if len(name) > 2:
                        return f"{name[0]}***{name[-1]}@{parts[1]}"
                    return f"***@{parts[1]}"
                return self.config.redaction_text

            elif pii_type == PIIType.PHONE:
                if len(value) >= 4:
                    return f"***-***-{value[-4:]}"
                return self.config.redaction_text

            else:
                # For other types, show first and last characters
                if len(value) > 2:
                    return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"
                return self.config.redaction_text

        elif strategy == MaskingStrategy.HASH:
            import hashlib
            return f"[HASH:{hashlib.sha256(value.encode()).hexdigest()[:8]}]"

        elif strategy == MaskingStrategy.TOKENIZE:
            import uuid
            # In production, you'd store the mapping
            return f"[TOKEN:{uuid.uuid4().hex[:8]}]"

        elif strategy == MaskingStrategy.REMOVE:
            return ""

        return self.config.redaction_text


class PIIFilterPlugin(Plugin):
    """민감한 정보를 탐지하고 마스킹하는 PII 필터 플러그인.

    이 플러그인은 프롬프트, 도구 호출, 도구 결과에서 개인 식별 정보(PII)를
    탐지하고 설정된 마스킹 전략에 따라 정보를 보호합니다.
    """

    def __init__(self, config: PluginConfig):
        """PII 필터 플러그인을 초기화합니다.

        Args:
            config: 플러그인 설정 객체
        """
        # 부모 클래스 초기화
        super().__init__(config)

        # PII 필터 설정을 검증하고 로드
        self.pii_config = PIIFilterConfig.model_validate(self._config.config)

        # PII 탐지기를 생성하여 패턴들을 컴파일
        self.detector = PIIDetector(self.pii_config)

        # 탐지 및 마스킹 통계 카운터 초기화
        self.detection_count = 0  # 총 탐지 횟수
        self.masked_count = 0     # 마스킹된 항목 수

    async def prompt_pre_fetch(
        self,
        payload: PromptPrehookPayload,
        context: PluginContext
    ) -> PromptPrehookResult:
        """프롬프트 검색 전 PII를 탐지하고 마스킹하는 메서드.

        프롬프트의 인자들을 검사하여 PII가 포함되어 있는지 확인하고,
        발견된 경우 설정에 따라 마스킹하거나 요청을 차단합니다.

        Args:
            payload: 프롬프트 페이로드 (인자들 포함)
            context: 플러그인 실행 맥락 정보

        Returns:
            마스킹된 PII가 포함된 결과 또는 차단을 위한 위반사항
        """
        if not payload.args:
            return PromptPrehookResult()

        all_detections = {}
        modified_args = {}

        # Process each argument
        for key, value in payload.args.items():
            if isinstance(value, str):
                detections = self.detector.detect(value)

                if detections:
                    all_detections[key] = detections

                    if self.pii_config.log_detections:
                        logger.warning(
                            f"PII detected in prompt argument '{key}': "
                            f"{', '.join(detections.keys())}"
                        )

                    if self.pii_config.block_on_detection:
                        violation = PluginViolation(
                            reason="PII detected in prompt",
                            description=f"Sensitive information detected in argument '{key}'",
                            code="PII_DETECTED",
                            details={
                                "field": key,
                                "types": list(detections.keys()),
                                "count": sum(len(items) for items in detections.values())
                            }
                        )
                        return PromptPrehookResult(
                            continue_processing=False,
                            violation=violation
                        )

                    # Mask the PII
                    masked_value = self.detector.mask(value, detections)
                    modified_args[key] = masked_value
                    self.masked_count += sum(len(items) for items in detections.values())
                else:
                    modified_args[key] = value
            else:
                modified_args[key] = value

        # Update context with detection metadata
        if all_detections and self.pii_config.include_detection_details:
            context.metadata["pii_detections"] = {
                "pre_fetch": {
                    "detected": True,
                    "fields": list(all_detections.keys()),
                    "types": list(set(
                        pii_type
                        for field_detections in all_detections.values()
                        for pii_type in field_detections.keys()
                    )),
                    "total_count": sum(
                        len(items)
                        for field_detections in all_detections.values()
                        for items in field_detections.values()
                    )
                }
            }

        # Return modified payload if PII was masked
        if all_detections:
            return PromptPrehookResult(
                modified_payload=PromptPrehookPayload(
                    name=payload.name,
                    args=modified_args
                )
            )

        return PromptPrehookResult()

    async def prompt_post_fetch(
        self,
        payload: PromptPosthookPayload,
        context: PluginContext
    ) -> PromptPosthookResult:
        """Process prompt after rendering to detect and mask PII in response.

        Args:
            payload: The prompt result payload
            context: Plugin context

        Returns:
            Result with masked PII in messages
        """
        if not payload.result.messages:
            return PromptPosthookResult()

        modified = False
        all_detections = {}

        # Process each message
        for message in payload.result.messages:
            if message.content and hasattr(message.content, 'text'):
                text = message.content.text
                detections = self.detector.detect(text)

                if detections:
                    all_detections[f"message_{message.role}"] = detections

                    if self.pii_config.log_detections:
                        logger.warning(
                            f"PII detected in {message.role} message: "
                            f"{', '.join(detections.keys())}"
                        )

                    # Mask the PII
                    masked_text = self.detector.mask(text, detections)
                    message.content.text = masked_text
                    modified = True
                    self.masked_count += sum(len(items) for items in detections.values())

        # Update context with post-fetch detection metadata
        if all_detections and self.pii_config.include_detection_details:
            if "pii_detections" not in context.metadata:
                context.metadata["pii_detections"] = {}

            context.metadata["pii_detections"]["post_fetch"] = {
                "detected": True,
                "messages": list(all_detections.keys()),
                "types": list(set(
                    pii_type
                    for msg_detections in all_detections.values()
                    for pii_type in msg_detections.keys()
                )),
                "total_count": sum(
                    len(items)
                    for msg_detections in all_detections.values()
                    for items in msg_detections.values()
                )
            }

        # Add summary statistics
        context.metadata["pii_filter_stats"] = {
            "total_detections": self.detection_count,
            "total_masked": self.masked_count
        }

        if modified:
            return PromptPosthookResult(modified_payload=payload)

        return PromptPosthookResult()

    async def tool_pre_invoke(self, payload: ToolPreInvokePayload, context: PluginContext) -> ToolPreInvokeResult:
        """Detect and mask PII in tool arguments before invocation.

        Args:
            payload: The tool payload containing arguments.
            context: Plugin execution context.

        Returns:
            Result with potentially modified tool arguments.
        """
        logger.debug(f"Processing tool pre-invoke for tool '{payload.name}' with {len(payload.args) if payload.args else 0} arguments")

        if not payload.args:
            return ToolPreInvokeResult()

        modified = False
        all_detections = {}

        # Use intelligent nested processing for tool arguments
        modified, detections = self._process_nested_data_for_pii(payload.args, "args", all_detections)

        if detections:
            detected_types = list(set(
                pii_type
                for arg_detections in all_detections.values()
                for pii_type in arg_detections.keys()
            ))
            if self.pii_config.log_detections:
                logger.warning(
                    f"PII detected in tool '{payload.name}' arguments: {', '.join(map(str, detected_types))}"
                )

        if detections and self.pii_config.block_on_detection:
            violation = PluginViolation(
                reason="PII detected in tool arguments",
                description=f"Detected PII in tool arguments",
                code="PII_DETECTED_IN_TOOL_ARGS",
                details={
                    "detected_types": list(set(
                        pii_type
                        for arg_detections in all_detections.values()
                        for pii_type in arg_detections.keys()
                    )),
                    "total_count": sum(
                        len(items)
                        for arg_detections in all_detections.values()
                        for items in arg_detections.values()
                    )
                }
            )
            return ToolPreInvokeResult(continue_processing=False, violation=violation)

        # Store detection metadata
        if all_detections and self.pii_config.include_detection_details:
            if "pii_detections" not in context.metadata:
                context.metadata["pii_detections"] = {}

            context.metadata["pii_detections"]["tool_pre_invoke"] = {
                "detected": True,
                "arguments": list(all_detections.keys()),
                "types": list(set(
                    pii_type
                    for arg_detections in all_detections.values()
                    for pii_type in arg_detections.keys()
                )),
                "total_count": sum(
                    len(items)
                    for arg_detections in all_detections.values()
                    for items in arg_detections.values()
                )
            }

        if modified:
            logger.info(f"Modified tool '{payload.name}' arguments to mask PII")
            return ToolPreInvokeResult(modified_payload=payload)

        return ToolPreInvokeResult()

    async def tool_post_invoke(self, payload: ToolPostInvokePayload, context: PluginContext) -> ToolPostInvokeResult:
        """Detect and mask PII in tool results after invocation.

        Args:
            payload: The tool result payload.
            context: Plugin execution context.

        Returns:
            Result with potentially modified tool results.
        """
        logger.debug(f"Processing tool post-invoke for tool '{payload.name}', result type: {type(payload.result).__name__}")

        if not payload.result:
            return ToolPostInvokeResult()

        modified = False
        all_detections = {}

        # Handle string results
        if isinstance(payload.result, str):
            detections = self.detector.detect(payload.result)
            if detections:
                all_detections["result"] = detections
                self.detection_count += sum(len(items) for items in detections.values())

                if self.pii_config.log_detections:
                    logger.warning(f"PII detected in tool result: {', '.join(detections.keys())}")

                # Check if we should block
                if self.pii_config.block_on_detection:
                    violation = PluginViolation(
                        reason="PII detected in tool result",
                        description=f"Detected {', '.join(detections.keys())} in tool output",
                        code="PII_DETECTED_IN_TOOL_RESULT",
                        details={
                            "detected_types": list(detections.keys()),
                            "count": sum(len(items) for items in detections.values())
                        }
                    )
                    return ToolPostInvokeResult(continue_processing=False, violation=violation)

                # Mask the PII
                payload.result = self.detector.mask(payload.result, detections)
                modified = True
                self.masked_count += sum(len(items) for items in detections.values())

                # Handle dictionary results - use recursive traversal
        elif isinstance(payload.result, dict):
            modified, detections = self._process_nested_data_for_pii(payload.result, "result", all_detections)
            if detections and self.pii_config.block_on_detection:
                violation = PluginViolation(
                    reason="PII detected in tool result",
                    description=f"Detected PII in nested tool result data",
                    code="PII_DETECTED_IN_TOOL_RESULT",
                    details={
                        "detected_types": list(set(
                            pii_type
                            for field_detections in all_detections.values()
                            for pii_type in field_detections.keys()
                        )),
                        "total_count": sum(
                            len(items)
                            for field_detections in all_detections.values()
                            for items in field_detections.values()
                        )
                    }
                )
                return ToolPostInvokeResult(continue_processing=False, violation=violation)

        # Store detection metadata
        if all_detections and self.pii_config.include_detection_details:
            if "pii_detections" not in context.metadata:
                context.metadata["pii_detections"] = {}

            context.metadata["pii_detections"]["tool_post_invoke"] = {
                "detected": True,
                "fields": list(all_detections.keys()),
                "types": list(set(
                    pii_type
                    for field_detections in all_detections.values()
                    for pii_type in field_detections.keys()
                )),
                "total_count": sum(
                    len(items)
                    for field_detections in all_detections.values()
                    for items in field_detections.values()
                )
            }

        # Update summary statistics
        context.metadata["pii_filter_stats"] = {
            "total_detections": self.detection_count,
            "total_masked": self.masked_count
        }

        if modified:
            logger.info(f"Modified tool '{payload.name}' result to mask PII")
            return ToolPostInvokeResult(modified_payload=payload)

        return ToolPostInvokeResult()

    def _process_nested_data_for_pii(self, data: Any, path: str, all_detections: dict) -> tuple[bool, bool]:
        """
        Recursively process nested data structures to find and mask PII.

        Args:
            data: The data structure to process (dict, list, str, or other)
            path: The current path in the data structure for logging
            all_detections: Dictionary to store all detections found

        Returns:
            Tuple of (modified, has_detections) where:
            - modified: True if any data was modified
            - has_detections: True if any PII was detected
        """
        modified = False
        has_detections = False

        if isinstance(data, str):
            # Process string data - check for PII and also try to parse as JSON
            detections = self.detector.detect(data)
            if detections:
                all_detections[path] = detections
                self.detection_count += sum(len(items) for items in detections.values())
                has_detections = True

                if self.pii_config.log_detections:
                    logger.warning(f"PII detected in tool result at '{path}': {', '.join(detections.keys())}")

                # Mask the PII in-place if possible
                if hasattr(data, '__setitem__'):  # This won't work for strings, but we handle that in the caller
                    masked_data = self.detector.mask(data, detections)
                    # We can't modify strings in place, so return the masked version
                    # The caller needs to handle the assignment
                    modified = True
                    self.masked_count += sum(len(items) for items in detections.values())

            # Try to parse as JSON and process nested content
            try:
                import json
                parsed_json = json.loads(data)
                json_modified, json_detections = self._process_nested_data_for_pii(parsed_json, f"{path}(json)", all_detections)
                has_detections = has_detections or json_detections
                # Note: JSON modification will be handled by the caller using the detections
                if json_modified:
                    modified = True
            except (json.JSONDecodeError, TypeError):
                # Not valid JSON, that's fine
                pass

        elif isinstance(data, dict):
            # Process dictionary recursively
            for key, value in data.items():
                current_path = f"{path}.{key}"
                value_modified, value_detections = self._process_nested_data_for_pii(value, current_path, all_detections)

                if value_modified and isinstance(value, str):
                    # Handle string masking including JSON strings
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[key] = self.detector.mask(value, detections)
                        modified = True

                    # Also check for JSON content that needs re-serialization
                    json_path = f"{current_path}(json)"
                    if any(path.startswith(json_path) for path in all_detections.keys()):
                        try:
                            import json
                            parsed_json = json.loads(value)
                            # Apply masking to the parsed JSON
                            self._apply_pii_masking_to_parsed_json(parsed_json, json_path, all_detections)
                            # Re-serialize with masked data
                            data[key] = json.dumps(parsed_json, ensure_ascii=False, separators=(',', ':'))
                            modified = True
                        except (json.JSONDecodeError, TypeError):
                            pass
                elif value_modified:
                    modified = True

                has_detections = has_detections or value_detections

        elif isinstance(data, list):
            # Process list recursively
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                item_modified, item_detections = self._process_nested_data_for_pii(item, current_path, all_detections)

                if item_modified and isinstance(item, str):
                    # Handle string masking in list including JSON strings
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[i] = self.detector.mask(item, detections)
                        modified = True

                    # Also check for JSON content that needs re-serialization
                    json_path = f"{current_path}(json)"
                    if any(path.startswith(json_path) for path in all_detections.keys()):
                        try:
                            import json
                            parsed_json = json.loads(item)
                            # Apply masking to the parsed JSON
                            self._apply_pii_masking_to_parsed_json(parsed_json, json_path, all_detections)
                            # Re-serialize with masked data
                            data[i] = json.dumps(parsed_json, ensure_ascii=False, separators=(',', ':'))
                            modified = True
                        except (json.JSONDecodeError, TypeError):
                            pass
                elif item_modified:
                    modified = True

                has_detections = has_detections or item_detections

        # For other types (int, bool, None, etc.), no processing needed

        return modified, has_detections

    def _apply_pii_masking_to_parsed_json(self, data: Any, base_path: str, all_detections: dict) -> None:
        """
        Apply PII masking to parsed JSON data using detections that were already found.

        Args:
            data: The parsed JSON data structure
            base_path: The base path for this JSON data
            all_detections: Dictionary containing all PII detections
        """
        if isinstance(data, str):
            # Check if this path has detections
            current_detections = all_detections.get(base_path, {})
            if current_detections:
                # This won't work since strings are immutable, but the caller handles assignment
                return self.detector.mask(data, current_detections)

        elif isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{base_path}.{key}"
                if isinstance(value, str):
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[key] = self.detector.mask(value, detections)
                else:
                    self._apply_pii_masking_to_parsed_json(value, current_path, all_detections)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{base_path}[{i}]"
                if isinstance(item, str):
                    detections = all_detections.get(current_path, {})
                    if detections:
                        data[i] = self.detector.mask(item, detections)
                else:
                    self._apply_pii_masking_to_parsed_json(item, current_path, all_detections)

    async def shutdown(self) -> None:
        """플러그인 종료 시 정리 작업을 수행합니다.

        플러그인이 종료될 때 필요한 정리 작업을 수행하고
        최종 마스킹 통계를 로그에 기록합니다.
        """
        logger.info(
            "PII 필터 플러그인 종료 중. "
            f"총 마스킹된 항목 수: {self.masked_count}개"
        )
