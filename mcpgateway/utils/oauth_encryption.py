# -*- coding: utf-8 -*-
"""Location: ./mcpgateway/utils/oauth_encryption.py
Copyright 2025
SPDX-License-Identifier: Apache-2.0
Authors: Mihai Criveti

OAuth 암호화 유틸리티.

이 모듈은 구성의 AUTH_ENCRYPTION_SECRET를 사용하여 OAuth 클라이언트 시크릿에 대한
암호화 및 복호화 기능을 제공합니다.
"""

# Standard
import base64
import logging
from typing import Optional

# Third-Party
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class OAuthEncryption:
    """OAuth 클라이언트 시크릿의 암호화 및 복호화를 처리합니다."""

    def __init__(self, encryption_secret: str):
        """암호화 핸들러를 초기화합니다.

        Args:
            encryption_secret: 암호화/복호화용 시크릿 키
        """
        self.encryption_secret = encryption_secret.encode()
        self._fernet = None

    def _get_fernet(self) -> Fernet:
        """암호화를 위한 Fernet 인스턴스를 가져오거나 생성합니다.

        Returns:
            암호화/복호화용 Fernet 인스턴스
        """
        if self._fernet is None:
            # Derive a key from the encryption secret using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"mcp_gateway_oauth",  # Fixed salt for consistency
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self.encryption_secret))
            self._fernet = Fernet(key)
        return self._fernet

    def encrypt_secret(self, plaintext: str) -> str:
        """평문 시크릿을 암호화합니다.

        Args:
            plaintext: 암호화할 시크릿

        Returns:
            Base64로 인코딩된 암호화된 문자열

        Raises:
            Exception: 암호화 실패 시
        """
        try:
            fernet = self._get_fernet()
            encrypted = fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt OAuth secret: {e}")
            raise

    def decrypt_secret(self, encrypted_text: str) -> Optional[str]:
        """Decrypt an encrypted secret.

        Args:
            encrypted_text: Base64-encoded encrypted string

        Returns:
            Decrypted secret string, or None if decryption fails
        """
        try:
            fernet = self._get_fernet()
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_text.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to decrypt OAuth secret: {e}")
            return None

    def is_encrypted(self, text: str) -> bool:
        """Check if a string appears to be encrypted.

        Args:
            text: String to check

        Returns:
            True if the string appears to be encrypted
        """
        try:
            # Try to decode as base64 and check if it looks like encrypted data
            decoded = base64.urlsafe_b64decode(text.encode())
            # Encrypted data should be at least 32 bytes (Fernet minimum)
            return len(decoded) >= 32
        except Exception:
            return False


def get_oauth_encryption(encryption_secret: str) -> OAuthEncryption:
    """Get an OAuth encryption instance.

    Args:
        encryption_secret: Secret key for encryption/decryption

    Returns:
        OAuthEncryption instance
    """
    return OAuthEncryption(encryption_secret)
