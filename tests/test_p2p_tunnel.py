"""测试 P2P 加密数据通道的完整流程"""
import os
import time
import shutil
from core.p2p_data_tunnel import (
    P2PDataServer, P2PDataClient, P2PResultServer,
    TunnelCrypto, TicketManager
)


def test_crypto_roundtrip():
    """测试 ECDH + AES-256-GCM 加密解密"""
    priv_a, pub_a = TunnelCrypto.generate_keypair()
    priv_b, pub_b = TunnelCrypto.generate_keypair()

    shared_a = TunnelCrypto.compute_shared_secret(priv_a, pub_b)
    shared_b = TunnelCrypto.compute_shared_secret(priv_b, pub_a)
    assert shared_a == shared_b, "ECDH 共享密钥不匹配"

    plaintext = b"Hello, P2P encrypted tunnel!"
    nonce, ct, tag = TunnelCrypto.encrypt(shared_a, plaintext)
    decrypted = TunnelCrypto.decrypt(shared_b, nonce, ct, tag)
    assert decrypted == plaintext, "AES-GCM 加解密失败"
    print("[PASS] ECDH + AES-GCM 加密解密正确")


def test_ticket_encrypt_decrypt():
    """测试连接票据加密/解密（矿工 IP 对服务器不可见）"""
    user_priv, user_pub = TunnelCrypto.generate_keypair()
    miner_priv, miner_pub = TunnelCrypto.generate_keypair()

    tm = TicketManager()
    tm.register_miner_direct("miner_001", "10.0.0.50", 9999, miner_pub)

    ticket = tm.create_ticket(
        task_id="task_abc",
        user_id="user_xyz",
        miner_id="miner_001",
        user_pubkey=user_pub,
    )

    assert ticket is not None
    assert ticket.transfer_mode == "p2p"
    assert ticket.user_encrypted_endpoint != ""

    # 用户解密矿工端点
    endpoint = tm.decrypt_ticket_endpoint(ticket.user_encrypted_endpoint, user_priv)
    assert endpoint is not None
    assert endpoint["ip"] == "10.0.0.50"
    assert endpoint["port"] == 9999
    assert endpoint["token"] == ticket.session_token
    print("[PASS] 票据加密/解密正确，矿工 IP 安全传递")


def test_ticket_relay_fallback():
    """测试矿工未注册 P2P 时回退到中转模式"""
    tm = TicketManager()
    _, user_pub = TunnelCrypto.generate_keypair()

    ticket = tm.create_ticket(
        task_id="task_relay",
        user_id="user_001",
        miner_id="miner_not_registered",
        user_pubkey=user_pub,
        relay_endpoint="127.0.0.1:8545",
    )

    assert ticket is not None
    assert ticket.transfer_mode == "relay"
    print("[PASS] 未注册矿工自动回退到中转模式")


def test_ticket_validation():
    """测试票据验证"""
    tm = TicketManager()
    _, user_pub = TunnelCrypto.generate_keypair()
    _, miner_pub = TunnelCrypto.generate_keypair()

    tm.register_miner_direct("miner_002", "192.168.0.1", 8000, miner_pub)
    ticket = tm.create_ticket("task_val", "user_val", "miner_002", user_pub)

    assert tm.validate_ticket(ticket.ticket_id, ticket.session_token) is True
    assert tm.validate_ticket(ticket.ticket_id, "wrong_token") is False
    assert tm.validate_ticket("nonexistent", ticket.session_token) is False

    tm.revoke_ticket(ticket.ticket_id)
    assert tm.validate_ticket(ticket.ticket_id, ticket.session_token) is False
    print("[PASS] 票据验证和吊销正确")


def test_p2p_data_transfer():
    """测试完整的 P2P 加密数据传输"""
    test_dir = "data/test_p2p_recv"
    try:
        # 1. 矿工启动 P2P 数据服务器
        server = P2PDataServer(host="127.0.0.1", port=0, data_dir=test_dir)
        server.start()
        port = server.actual_port

        # 2. 生成密钥和票据
        user_priv, user_pub = TunnelCrypto.generate_keypair()
        tm = TicketManager()
        tm.register_miner_direct("miner_t", "127.0.0.1", port, server.public_key)

        ticket = tm.create_ticket("task_p2p", "user_p2p", "miner_t", user_pub)
        endpoint = tm.decrypt_ticket_endpoint(ticket.user_encrypted_endpoint, user_priv)

        # 3. 矿工授权会话
        server.authorize_session(ticket.session_token, "task_p2p", "user_p2p")

        # 4. 用户发送数据
        test_data = b"POUW P2P Test Data " * 5000  # ~95KB
        client = P2PDataClient()
        result = client.send_data(
            host=endpoint["ip"],
            port=endpoint["port"],
            session_token=endpoint["token"],
            data=test_data,
            filename="test_input.bin",
        )

        assert result is not None, "传输失败：无返回结果"
        assert result["received"] == len(test_data), f"数据不完整: {result['received']} != {len(test_data)}"

        # 5. 验证文件
        recv_path = os.path.join(test_dir, "task_p2p", "test_input.bin")
        assert os.path.exists(recv_path), f"文件不存在: {recv_path}"
        with open(recv_path, "rb") as f:
            received_data = f.read()
        assert received_data == test_data, "接收的数据内容不匹配"

        print(f"[PASS] P2P 加密传输成功: {len(test_data)} bytes, hash={result['hash'][:16]}...")

        server.stop()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_p2p_unauthorized_rejected():
    """测试未授权连接被拒绝"""
    test_dir = "data/test_p2p_reject"
    try:
        server = P2PDataServer(host="127.0.0.1", port=0, data_dir=test_dir)
        server.start()
        port = server.actual_port

        # 不授权，直接连接
        client = P2PDataClient()
        result = client.send_data(
            host="127.0.0.1",
            port=port,
            session_token="invalid_token",
            data=b"should be rejected",
            filename="evil.bin",
        )

        assert result is None, "未授权连接应该被拒绝"
        print("[PASS] 未授权连接被正确拒绝")

        server.stop()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_miner_p2p_readiness():
    """测试矿工 P2P 就绪状态查询"""
    tm = TicketManager()
    assert tm.is_miner_p2p_ready("nonexistent") is False

    _, pub = TunnelCrypto.generate_keypair()
    tm.register_miner_direct("miner_ready", "10.0.0.1", 5000, pub)
    assert tm.is_miner_p2p_ready("miner_ready") is True
    assert tm.get_miner_pubkey("miner_ready") == pub
    print("[PASS] 矿工 P2P 就绪状态查询正确")


if __name__ == "__main__":
    test_crypto_roundtrip()
    test_ticket_encrypt_decrypt()
    test_ticket_relay_fallback()
    test_ticket_validation()
    test_p2p_data_transfer()
    test_p2p_unauthorized_rejected()
    test_miner_p2p_readiness()
    print("\n========== ALL P2P TUNNEL TESTS PASSED ==========")
