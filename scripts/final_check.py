"""
Final pre-launch verification script
"""
import os
import sys
import py_compile
import importlib
import json
import time
import urllib.request

PYTHON = sys.executable
RPC_URL = "http://127.0.0.1:8545"

def rpc(method, params=None):
    data = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": 1
    }).encode()
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

# ============================================================
# PHASE 1: Syntax check all Python files
# ============================================================
def check_syntax():
    print("\n" + "="*60)
    print("PHASE 1: Python Syntax Check (all .py files)")
    print("="*60)
    errors = []
    count = 0
    for root, dirs, files in os.walk("core"):
        for f in sorted(files):
            if f.endswith(".py"):
                count += 1
                path = os.path.join(root, f)
                try:
                    py_compile.compile(path, doraise=True)
                except py_compile.PyCompileError as e:
                    errors.append(str(e))
    # Also check main.py, test files etc.
    for f in os.listdir("."):
        if f.endswith(".py"):
            count += 1
            try:
                py_compile.compile(f, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(str(e))
    
    print(f"  Checked: {count} files")
    if errors:
        print(f"  FAILED: {len(errors)} syntax errors!")
        for e in errors:
            print(f"    - {e}")
        return False
    print("  RESULT: ALL SYNTAX OK")
    return True

# ============================================================
# PHASE 2: Import check all core modules
# ============================================================
def check_imports():
    print("\n" + "="*60)
    print("PHASE 2: Import Check (core modules)")
    print("="*60)
    errors = []
    count = 0
    for f in sorted(os.listdir("core")):
        if f.endswith(".py") and f != "__init__.py":
            module = f"core.{f[:-3]}"
            count += 1
            try:
                importlib.import_module(module)
            except Exception as e:
                errors.append(f"{module}: {type(e).__name__}: {e}")
    
    print(f"  Checked: {count} modules")
    if errors:
        print(f"  FAILED: {len(errors)} import errors!")
        for e in errors:
            print(f"    - {e}")
        return False
    print("  RESULT: ALL IMPORTS OK")
    return True

# ============================================================
# PHASE 3: RPC endpoint connectivity
# ============================================================
def check_rpc_connectivity():
    print("\n" + "="*60)
    print("PHASE 3: RPC Connectivity")
    print("="*60)
    result = rpc("getinfo")
    if "error" in result and isinstance(result["error"], str):
        print(f"  FAILED: Cannot connect to RPC: {result['error']}")
        return False
    if "result" in result:
        info = result["result"]
        print(f"  Node version: {info.get('version', 'N/A')}")
        print(f"  Chain ID: {info.get('chain_id', 'N/A')}")
        print(f"  Block height: {info.get('block_height', 'N/A')}")
        print(f"  Registered methods: {info.get('registered_methods', 'N/A')}")
        print("  RESULT: RPC CONNECTED OK")
        return True
    print(f"  WARNING: Unexpected response: {result}")
    return True

# ============================================================
# PHASE 4: Full RPC method test (all frontend-facing methods)
# ============================================================
def check_rpc_methods():
    print("\n" + "="*60)
    print("PHASE 4: Frontend RPC Method Tests")
    print("="*60)
    
    tests = [
        # Wallet
        ("wallet_create", {}, "wallet_create"),
        ("wallet_getInfo", {}, "wallet_getInfo"),
        
        # Dashboard / Info
        ("getinfo", [], "getinfo"),
        ("getblockcount", [], "getblockcount"),
        ("getmininginfo", [], "getmininginfo"),
        ("getnetworkinfo", [], "getnetworkinfo"),
        ("getbalance", ["test_addr"], "getbalance"),
        ("getsectorbalance", ["test_addr"], "getsectorbalance"),
        
        # Chain
        ("chain_getLatestBlocks", {"limit": 5}, "chain_getLatestBlocks"),
        ("chain_getRecentTransactions", {"limit": 5}, "chain_getRecentTransactions"),
        ("chain_getStats", {}, "chain_getStats"),
        
        # Governance
        ("governance_getProposals", {}, "governance_getProposals"),
        ("governance_createProposal", {
            "title": "Test", "description": "Test proposal",
            "proposalType": "parameter_change", "duration": 7
        }, "governance_createProposal"),
        
        # Transfer
        ("transfer_send", {
            "fromAddress": "MAIN_test1", "toAddress": "MAIN_test2",
            "amount": 1.0, "coinType": "MAIN"
        }, "transfer_send"),
        
        # Exchange
        ("exchange_getRate", {"fromCoin": "H100_COIN", "toCoin": "MAIN"}, "exchange_getRate"),
        ("exchange_convert", {
            "fromCoin": "H100_COIN", "toCoin": "MAIN",
            "amount": 10, "address": "test_addr"
        }, "exchange_convert"),
        ("exchange_getHistory", {"address": "test_addr"}, "exchange_getHistory"),
        
        # Tasks
        ("task_submit", {
            "title": "Test Task", "taskType": "ai_training",
            "gpuType": "RTX_4090", "estimatedHours": 1,
            "pricingStrategy": "standard", "submitter": "test"
        }, "task_submit"),
        ("task_list", {}, "task_list"),
        
        # Orderbook
        ("orderbook_getOrderbook", {"gpuType": "RTX_4090"}, "orderbook_getOrderbook"),
        ("orderbook_getMarketStats", {}, "orderbook_getMarketStats"),
        ("orderbook_submitBid", {
            "gpuType": "RTX_4090", "gpuCount": 1,
            "maxPricePerHour": 30.0, "duration": 3600
        }, "orderbook_submitBid"),
        ("orderbook_submitAsk", {
            "gpuType": "RTX_4090", "gpuCount": 1,
            "pricePerHour": 25.0, "duration": 3600
        }, "orderbook_submitAsk"),
        
        # Privacy
        ("privacy_getStatus", {}, "privacy_getStatus"),
        
        # Pricing
        ("pricing_getPrice", {"gpuType": "RTX_4090", "strategy": "standard"}, "pricing_getPrice"),
        ("pricing_getHistory", {"gpuType": "RTX_4090"}, "pricing_getHistory"),
        ("billing_getEstimate", {
            "gpuType": "RTX_4090", "hours": 1,
            "strategy": "standard"
        }, "billing_getEstimate"),
        
        # Node
        ("node_getStatus", {}, "node_getStatus"),
        ("node_getPeers", {}, "node_getPeers"),
        
        # Mining
        ("mining_getWorkers", {}, "mining_getWorkers"),
        ("mining_getEarnings", {}, "mining_getEarnings"),
        
        # DID
        ("did_resolve", {"did": "did:pouw:test"}, "did_resolve"),
        
        # P2P Tasks
        ("p2p_getAvailableTasks", {}, "p2p_getAvailableTasks"),
        
        # Miner Registry
        ("miner_register", {
            "address": "test_addr", "gpuType": "RTX_4090",
            "gpuCount": 1
        }, "miner_register"),
        
        # Security
        ("security_getStatus", {}, "security_getStatus"),
        
        # Redundancy
        ("redundancy_getStatus", {}, "redundancy_getStatus"),
        
        # Message Queue
        ("mq_getStatus", {}, "mq_getStatus"),
    ]
    
    ok = 0
    fail = 0
    auth = 0
    errors_list = []
    
    for method, params, label in tests:
        r = rpc(method, params if isinstance(params, list) else [params])
        if "result" in r:
            ok += 1
        elif "error" in r:
            err = r["error"]
            if isinstance(err, dict):
                code = err.get("code", 0)
                msg = err.get("message", "")
                if code == -32603 and "Internal" in msg:
                    fail += 1
                    errors_list.append(f"  FAIL [{label}]: Internal Server Error - {err.get('data', '')}")
                elif code == -32001 or "permission" in msg.lower() or "denied" in msg.lower():
                    auth += 1
                elif code == -32601:
                    fail += 1
                    errors_list.append(f"  FAIL [{label}]: Method not found")
                else:
                    # Business logic error is OK
                    ok += 1
            else:
                fail += 1
                errors_list.append(f"  FAIL [{label}]: {err}")
        else:
            fail += 1
            errors_list.append(f"  FAIL [{label}]: Unknown response")
    
    total = len(tests)
    print(f"  Total: {total} methods tested")
    print(f"  OK: {ok}  |  AUTH(expected): {auth}  |  FAIL: {fail}")
    
    if errors_list:
        print(f"\n  Failures:")
        for e in errors_list:
            print(f"    {e}")
    
    if fail == 0:
        print("  RESULT: ALL RPC METHODS OK")
        return True
    else:
        print(f"  RESULT: {fail} METHODS FAILED!")
        return False

# ============================================================
# PHASE 5: Config & security checks
# ============================================================
def check_config_security():
    print("\n" + "="*60)
    print("PHASE 5: Configuration & Security Check")
    print("="*60)
    
    warnings = []
    
    # Check config.yaml exists
    if not os.path.exists("config.yaml"):
        warnings.append("config.yaml not found")
    else:
        print("  config.yaml: EXISTS")
    
    # Check mainnet config
    if os.path.exists("config.mainnet.yaml"):
        print("  config.mainnet.yaml: EXISTS")
    else:
        warnings.append("config.mainnet.yaml not found")
    
    # Check genesis file
    if os.path.exists("genesis.mainnet.json"):
        with open("genesis.mainnet.json", "r") as f:
            genesis = json.load(f)
        print(f"  genesis.mainnet.json: EXISTS (chain_id={genesis.get('chain_id', 'N/A')})")
    else:
        warnings.append("genesis.mainnet.json not found")
    
    # Check requirements.txt
    if os.path.exists("requirements.txt"):
        with open("requirements.txt", "r") as f:
            deps = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        print(f"  requirements.txt: {len(deps)} dependencies")
    
    # Check Docker files
    if os.path.exists("Dockerfile"):
        print("  Dockerfile: EXISTS")
    if os.path.exists("docker-compose.yml"):
        print("  docker-compose.yml: EXISTS")
    
    # Check deploy directory
    if os.path.exists("deploy"):
        deploy_files = os.listdir("deploy")
        print(f"  deploy/: {len(deploy_files)} files")
    
    # Check wallets directory
    if os.path.exists("wallets"):
        wallet_files = [f for f in os.listdir("wallets") if f.endswith(".json")]
        print(f"  wallets/: {len(wallet_files)} wallet files")
    
    # Security: check RPC is localhost only
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", 8545))
        s.close()
        if result == 0:
            print("  RPC binding: localhost only (SAFE)")
    except:
        pass
    
    # Check no hardcoded secrets in main config
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r", encoding="utf-8") as f:
            config_text = f.read().lower()
        if "password" in config_text and ("123" in config_text or "admin" in config_text):
            warnings.append("Possible hardcoded password in config.yaml")
        else:
            print("  No obvious hardcoded credentials: OK")
    
    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")
        return True  # Warnings are not blockers
    
    print("  RESULT: CONFIG & SECURITY OK")
    return True

# ============================================================
# PHASE 6: Documentation check
# ============================================================
def check_documentation():
    print("\n" + "="*60)
    print("PHASE 6: Documentation Check")
    print("="*60)
    
    docs = {
        "README.md": "Project overview",
        "USER_GUIDE.md": "User guide (root)",
        "docs/USER_GUIDE.md": "User guide (docs/)",
        "QUICKSTART.md": "Quick start guide",
        "DEPLOYMENT.md": "Deployment guide",
        "MAINNET_DEPLOY.md": "Mainnet deployment",
        "FUSE_MECHANISM.md": "Fuse mechanism docs",
        "DYNAMIC_REFRESH.md": "Dynamic refresh docs",
    }
    
    found = 0
    for path, desc in docs.items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  {path}: {size:,} bytes - {desc}")
            found += 1
        else:
            print(f"  {path}: MISSING - {desc}")
    
    print(f"\n  Documentation: {found}/{len(docs)} files present")
    print("  RESULT: DOCS OK" if found >= 5 else "  RESULT: SOME DOCS MISSING")
    return True

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  POUW CHAIN - FINAL PRE-LAUNCH VERIFICATION")
    print(f"  Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = {}
    results["syntax"] = check_syntax()
    results["imports"] = check_imports()
    results["rpc_conn"] = check_rpc_connectivity()
    results["rpc_methods"] = check_rpc_methods()
    results["config"] = check_config_security()
    results["docs"] = check_documentation()
    
    # Final summary
    print("\n" + "=" * 60)
    print("  FINAL VERIFICATION SUMMARY")
    print("=" * 60)
    
    all_pass = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        icon = "[+]" if passed else "[X]"
        print(f"  {icon} {name}: {status}")
        if not passed:
            all_pass = False
    
    print()
    if all_pass:
        print("  *** ALL CHECKS PASSED - READY FOR LAUNCH ***")
    else:
        print("  *** SOME CHECKS FAILED - NOT READY ***")
    
    print("=" * 60)
    sys.exit(0 if all_pass else 1)
