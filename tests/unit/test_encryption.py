"""Unit tests for the EncryptionManager."""

from __future__ import annotations

import pytest

from jarvis.core.security.encryption import EncryptionManager


@pytest.fixture
def encryption(tmp_path):
    key_file = tmp_path / "master.key"
    return EncryptionManager(key_file=str(key_file))


@pytest.mark.unit
class TestEncryptionManager:
    def test_encrypt_decrypt(self, encryption):
        plaintext = "Hello, JARVIS!"
        ciphertext = encryption.encrypt(plaintext)
        assert ciphertext != plaintext
        decrypted = encryption.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_file(self, encryption, tmp_path):
        src = tmp_path / "secret.txt"
        src.write_text("sensitive data")

        enc_path = encryption.encrypt_file(str(src))
        assert enc_path != str(src)

        dec_path = encryption.decrypt_file(enc_path)
        assert (tmp_path / dec_path).read_text() == "sensitive data"

    def test_encrypt_dict(self, encryption):
        data = {"name": "JARVIS", "version": "2.0", "nested": {"key": "value"}}
        ciphertext = encryption.encrypt_dict(data)
        decrypted = encryption.decrypt_dict(ciphertext)
        assert decrypted == data

    def test_hash_data(self, encryption):
        h1 = encryption.hash_data("test data")
        h2 = encryption.hash_data("test data")
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest

    def test_verify_hash(self, encryption):
        data = "important data"
        h = encryption.hash_data(data)
        assert encryption.verify_hash(data, h) is True
        assert encryption.verify_hash("wrong data", h) is False

    def test_generate_key(self, encryption):
        key1 = encryption.generate_key(32)
        key2 = encryption.generate_key(32)
        assert len(key1) == 32
        assert key1 != key2

    def test_rotate_key(self, encryption):
        original = "rotate me"
        ciphertext = encryption.encrypt(original)
        rotated = encryption.rotate_key(ciphertext)
        assert rotated != ciphertext
        decrypted = encryption.decrypt(rotated)
        assert decrypted == original

    def test_different_inputs(self, encryption):
        enc_a = encryption.encrypt("input A")
        enc_b = encryption.encrypt("input B")
        assert enc_a != enc_b
