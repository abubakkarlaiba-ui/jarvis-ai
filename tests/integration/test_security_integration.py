import pytest
from jarvis.core.security import SecurityManager


@pytest.mark.integration
class TestAuthFlow:
    def test_full_auth_flow(self):
        sec = SecurityManager()
        sec.register("inttestuser", "securepass123")
        token = sec.login("inttestuser", "securepass123")
        assert token is not None
        user = sec.get_user(token)
        assert user is not None
        sec.logout(token)
        assert sec.get_user(token) is None


@pytest.mark.integration
class TestPermissions:
    def test_permission_checks(self):
        sec = SecurityManager()
        sec.grant_permission("user1", "read")
        assert sec.check_permission("user1", "read") is True
        sec.revoke_permission("user1", "read")
        assert sec.check_permission("user1", "read") is False


@pytest.mark.integration
class TestRoles:
    def test_role_assignment(self):
        sec = SecurityManager()
        sec.assign_role("user1", "admin")
        assert sec.has_role("user1", "admin") is True
        perms = sec.get_role_permissions("admin")
        assert isinstance(perms, (list, set))


@pytest.mark.integration
class TestAPIKeys:
    def test_api_key_lifecycle(self):
        sec = SecurityManager()
        key_id, key_secret = sec.create_api_key("user1", "test_key")
        assert key_id is not None
        valid = sec.validate_api_key(key_id, key_secret)
        assert valid is True
        sec.revoke_api_key(key_id)
        assert sec.validate_api_key(key_id, key_secret) is False


@pytest.mark.integration
class TestRateLimiting:
    def test_rate_limiting(self):
        sec = SecurityManager()
        for _ in range(5):
            assert sec.check_rate_limit("user1") is True
        exceeded = sec.check_rate_limit("user1", limit=5)
        assert exceeded is False


@pytest.mark.integration
class TestAuditLogging:
    def test_audit_logging(self):
        sec = SecurityManager()
        sec.register("audituser", "pass123")
        logs = sec.get_audit_logs()
        assert len(logs) > 0


@pytest.mark.integration
class TestEncryption:
    def test_encryption_flow(self):
        sec = SecurityManager()
        plaintext = "sensitive data"
        ciphertext = sec.encrypt(plaintext)
        assert ciphertext != plaintext
        decrypted = sec.decrypt(ciphertext)
        assert decrypted == plaintext


@pytest.mark.integration
class TestBackupRestore:
    def test_backup_restore(self):
        sec = SecurityManager()
        sec.register("backupuser", "pass123")
        backup_id = sec.create_backup()
        assert backup_id is not None
        sec.restore_backup(backup_id)
        user = sec.get_user_by_username("backupuser")
        assert user is not None
