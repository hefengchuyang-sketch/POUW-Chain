from core.rpc_service import NodeRPCService


def test_rpc_registry_includes_sbox_policy_methods():
    svc = NodeRPCService()
    assert svc.registry.has("sbox_getEncryptionPolicy")
    assert svc.registry.has("sbox_setEncryptionPolicy")
    assert svc.registry.has("sbox_getDowngradeAudit")
    assert svc.registry.has("chain_updateMechanismStrategy")


def test_rpc_sbox_policy_get_set_roundtrip():
    svc = NodeRPCService()

    get1 = svc._sbox_get_encryption_policy()
    assert get1["status"] == "success"

    upd = svc._sbox_set_encryption_policy(
        policyVersion="v2.2-test",
        defaultLevel="enhanced",
        enforceEnhancedDefault=True,
        allowDowngradeToStandard=True,
        downgradeRequiresAudit=True,
        maxSessionMessages=200000,
        maxSessionSeconds=1800,
    )
    assert upd["status"] == "success"
    assert upd["policy"]["policyVersion"] == "v2.2-test"

    get2 = svc._sbox_get_encryption_policy()
    assert get2["status"] == "success"
    assert get2["policy"]["policyVersion"] == "v2.2-test"

    audit = svc._sbox_get_downgrade_audit(limit=20)
    assert audit["status"] == "success"
    assert isinstance(audit["events"], list)
