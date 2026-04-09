import pytest

from core.sbox_crypto import (
    SBoxEncryptionLevel,
    clear_sbox_downgrade_audit,
    get_sbox_downgrade_audit,
    get_sbox_encryption_policy,
    set_sbox_encryption_policy,
    sbox_encrypt,
    _unpack_header,
)


class _NoSBoxLib:
    current = None

    def get_latest(self, n):
        return []


def test_sbox_fallback_records_audit_when_allowed(monkeypatch):
    import core.sbox_crypto as sc

    old = get_sbox_encryption_policy()
    clear_sbox_downgrade_audit()
    monkeypatch.setattr(sc, "get_sbox_library", lambda: _NoSBoxLib())

    try:
        set_sbox_encryption_policy(
            enforceEnhancedDefault=True,
            allowDowngradeToStandard=True,
            downgradeRequiresAudit=True,
            defaultLevel="enhanced",
        )

        key = b"k" * 32
        packet = sbox_encrypt(b"hello", key, sbox=None, level=SBoxEncryptionLevel.ENHANCED)
        level, _nonce, _prefix, _flags = _unpack_header(packet)
        assert level == SBoxEncryptionLevel.STANDARD

        events = get_sbox_downgrade_audit(10)
        assert len(events) >= 1
        assert events[-1]["reason"] == "sbox_unavailable_fallback_standard"
    finally:
        set_sbox_encryption_policy(**old)
        clear_sbox_downgrade_audit()


def test_sbox_fallback_denied_by_policy(monkeypatch):
    import core.sbox_crypto as sc

    old = get_sbox_encryption_policy()
    monkeypatch.setattr(sc, "get_sbox_library", lambda: _NoSBoxLib())

    try:
        set_sbox_encryption_policy(
            enforceEnhancedDefault=True,
            allowDowngradeToStandard=False,
            downgradeRequiresAudit=True,
            defaultLevel="enhanced",
        )

        key = b"k" * 32
        with pytest.raises(ValueError):
            sbox_encrypt(b"hello", key, sbox=None, level=SBoxEncryptionLevel.ENHANCED)
    finally:
        set_sbox_encryption_policy(**old)
