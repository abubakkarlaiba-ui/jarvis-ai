"""
Security module — AES-256 encryption for data at rest and in transit.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Union

from jarvis.core.security.base import APIKey


class EncryptionManager:
    """
    AES-256 encryption manager for the JARVIS security module.
    Uses cryptography library's AES-CBC or falls back to Fernet.
    """

    def __init__(self, master_key: str = None, key_file: str = "./data/security/master.key"):
        self.key_file = Path(key_file)
        self._cryptography_available = False
        self._master_key: bytes = b""
        self._fernet = None

        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding as sym_padding
            self._cryptography_available = True
            self._Cipher = Cipher
            self._algorithms = algorithms
            self._modes = modes
            self._sym_padding = sym_padding
        except ImportError:
            try:
                from cryptography.fernet import Fernet
                self._Fernet = Fernet
            except ImportError:
                raise ImportError(
                    "Neither cryptography.hazmat nor cryptography.fernet is available. "
                    "Install cryptography: pip install cryptography"
                )

        if master_key:
            self._master_key = master_key.encode("utf-8") if isinstance(master_key, str) else master_key
        else:
            self._master_key = self._get_or_create_master_key()

        if not self._cryptography_available:
            key_b64 = base64.urlsafe_b64encode(self._master_key[:32].ljust(32, b'\0'))
            self._fernet = self._Fernet(key_b64)

    def _derive_key(self, password: str, salt: bytes) -> bytes:
        """Derive 32-byte key using PBKDF2-SHA256."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations=100_000,
            dklen=32
        )

    def _get_or_create_master_key(self) -> bytes:
        """Load or generate master key."""
        self.key_file.parent.mkdir(parents=True, exist_ok=True)

        if self.key_file.exists():
            return self.key_file.read_bytes()

        key = os.urandom(32)
        self.key_file.write_bytes(key)
        try:
            os.chmod(self.key_file, 0o600)
        except (OSError, AttributeError):
            pass
        return key

    def encrypt(self, data: Union[str, bytes]) -> str:
        """Encrypt data, return base64-encoded ciphertext with salt+iv prefix."""
        if isinstance(data, str):
            data = data.encode("utf-8")

        if self._cryptography_available:
            return self._encrypt_aes(data)
        else:
            return self._encrypt_fernet(data)

    def _encrypt_aes(self, data: bytes) -> str:
        """Encrypt using AES-256-CBC."""
        salt = os.urandom(16)
        iv = os.urandom(16)
        key = self._derive_key(base64.b64encode(self._master_key).decode(), salt)

        padder = self._sym_padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()

        cipher = self._Cipher(self._algorithms.AES(key), self._modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded_data) + encryptor.finalize()

        payload = salt + iv + ciphertext
        return base64.b64encode(payload).decode("utf-8")

    def _encrypt_fernet(self, data: bytes) -> str:
        """Encrypt using Fernet."""
        return self._fernet.encrypt(data).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt base64-encoded ciphertext."""
        if self._cryptography_available:
            return self._decrypt_aes(ciphertext)
        else:
            return self._decrypt_fernet(ciphertext)

    def _decrypt_aes(self, ciphertext: str) -> str:
        """Decrypt AES-256-CBC ciphertext."""
        payload = base64.b64decode(ciphertext)
        salt = payload[:16]
        iv = payload[16:32]
        encrypted_data = payload[32:]

        key = self._derive_key(base64.b64encode(self._master_key).decode(), salt)

        cipher = self._Cipher(self._algorithms.AES(key), self._modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

        unpadder = self._sym_padding.PKCS7(128).unpadder()
        data = unpadder.update(padded_data) + unpadder.finalize()

        return data.decode("utf-8")

    def _decrypt_fernet(self, ciphertext: str) -> str:
        """Decrypt Fernet ciphertext."""
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")

    def encrypt_file(self, file_path: str, output_path: str = None) -> str:
        """Encrypt file contents."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        data = path.read_bytes()
        encrypted = self.encrypt(data)

        if output_path is None:
            output_path = str(path) + ".enc"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(encrypted)
        return output_path

    def decrypt_file(self, file_path: str, output_path: str = None) -> str:
        """Decrypt file contents."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ciphertext = path.read_text()
        decrypted = self.decrypt(ciphertext)

        if output_path is None:
            output_path = str(path).replace(".enc", "")
            if output_path == str(path):
                output_path = str(path) + ".dec"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(decrypted)
        return output_path

    def encrypt_dict(self, data: dict) -> str:
        """Encrypt a dictionary as JSON."""
        json_str = json.dumps(data, default=str)
        return self.encrypt(json_str)

    def decrypt_dict(self, ciphertext: str) -> dict:
        """Decrypt back to dictionary."""
        json_str = self.decrypt(ciphertext)
        return json.loads(json_str)

    def hash_data(self, data: str) -> str:
        """SHA-256 hash for integrity checks."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def verify_hash(self, data: str, expected_hash: str) -> bool:
        """Verify data matches hash."""
        return self.hash_data(data) == expected_hash

    def generate_key(self, length: int = 32) -> bytes:
        """Generate random key."""
        return os.urandom(length)

    def rotate_key(self, old_ciphertext: str) -> str:
        """Re-encrypt with current master key."""
        decrypted = self.decrypt(old_ciphertext)
        return self.encrypt(decrypted)