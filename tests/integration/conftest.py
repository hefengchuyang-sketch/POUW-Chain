"""Integration tests that require a running node on localhost:8545.

Run separately with:
    python -m pytest tests/integration/ -v

These tests are excluded from the default pytest run because they
need a live node.
"""
import pytest

def pytest_collection_modifyitems(config, items):
    """Skip integration tests in this directory unless the node is reachable."""
    import urllib.request
    import ssl
    node_available = False
    # 尝试 HTTP 和 HTTPS（节点可能启用了自签名 TLS）
    for url in ["http://127.0.0.1:8545", "https://127.0.0.1:8545"]:
        try:
            ctx = None
            if url.startswith("https"):
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            urllib.request.urlopen(url, timeout=2, context=ctx)
            node_available = True
            break
        except Exception:
            pass

    if not node_available:
        skip = pytest.mark.skip(reason="需要运行中的节点 (python main.py)")
        integration_dir = str(__file__).replace("\\", "/").rsplit("/", 1)[0]
        for item in items:
            item_path = str(item.fspath).replace("\\", "/")
            if item_path.startswith(integration_dir):
                item.add_marker(skip)
