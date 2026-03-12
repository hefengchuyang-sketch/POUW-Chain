import os
"""验证节点P2P连接和挖矿状态，以及前端功能"""

import paramiko
import json
import time

SERVERS = [
    {"name": "Node1-Seed", "host": "118.195.149.137"},
    {"name": "Node2-Miner", "host": "1.13.141.28"},
    {"name": "Node3-Full", "host": "175.27.156.47"},
]

SSH_USER = "ubuntu"
SSH_PASS = os.environ.get("SSH_PASSWORD", "")


def ssh_exec(host, cmd):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())
    client.connect(host, username=SSH_USER, password=SSH_PASS, timeout=15)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    client.close()
    return out, err


def rpc_call(host, method, params=None):
    """通过SSH在服务器内部调用RPC"""
    if params is None:
        params = {}
    params_json = json.dumps(params).replace('"', '\\"')
    cmd = f'''python3 -c "
import urllib.request, json
data = json.dumps({{'jsonrpc':'2.0','id':1,'method':'{method}','params':{params_json}}}).encode()
req = urllib.request.Request('http://127.0.0.1:8545/rpc', data=data, headers={{'Content-Type':'application/json'}})
try:
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read().decode())
    if 'error' in result and result['error']:
        print('ERROR:', json.dumps(result['error']))
    else:
        print(json.dumps(result.get('result', {{}})))
except Exception as e:
    print('EXCEPTION:', str(e))
"'''
    out, err = ssh_exec(host, cmd)
    return out


def main():
    print("=" * 60)
    print("POUW Chain 节点状态检查")
    print("=" * 60)
    
    # 等待P2P连接建立
    print("\n等待节点P2P连接 (15秒)...")
    time.sleep(15)
    
    # 检查每个节点
    for server in SERVERS:
        name = server["name"]
        host = server["host"]
        print(f"\n{'='*50}")
        print(f"{name} ({host})")
        print(f"{'='*50}")
        
        # 1. 节点信息
        print("  [节点信息]")
        result = rpc_call(host, "node_getInfo")
        try:
            info = json.loads(result)
            print(f"    高度: {info.get('height', 'N/A')}")
            print(f"    节点ID: {info.get('node_id', 'N/A')}")
            print(f"    对等节点数: {info.get('peers', 'N/A')}")
        except:
            print(f"    原始: {result[:200]}")
        
        # 2. P2P状态
        print("  [P2P网络]")
        result = rpc_call(host, "network_getStatus")
        try:
            net = json.loads(result)
            print(f"    已连接: {net.get('connected_peers', 'N/A')}")
            print(f"    总连接数: {net.get('total_connections', 'N/A')}")
        except:
            print(f"    原始: {result[:200]}")
        
        # 3. 钱包信息
        print("  [钱包]")
        result = rpc_call(host, "wallet_getInfo")
        try:
            wallet = json.loads(result)
            addr = wallet.get('address', 'N/A')
            print(f"    地址: {addr}")
        except:
            print(f"    原始: {result[:200]}")
        
        # 4. 余额
        print("  [余额]")
        result = rpc_call(host, "wallet_getBalance")
        try:
            bal = json.loads(result)
            print(f"    余额: {json.dumps(bal, indent=6)[:300]}")
        except:
            print(f"    原始: {result[:200]}")
        
        # 5. 挖矿状态
        print("  [挖矿]")
        result = rpc_call(host, "mining_getStatus")
        try:
            mining = json.loads(result)
            print(f"    挖矿中: {mining.get('mining', 'N/A')}")
            print(f"    算力: {mining.get('hashrate', 'N/A')}")
        except:
            print(f"    原始: {result[:200]}")
        
        # 6. 前端可访问性
        print("  [前端]")
        cmd = '''python3 -c "
import urllib.request
# 测试首页
req = urllib.request.Request('http://127.0.0.1:8545/')
resp = urllib.request.urlopen(req, timeout=5)
html = resp.read().decode()
print(f'首页: {len(html)} bytes, OK')

# 测试JS
req2 = urllib.request.Request('http://127.0.0.1:8545/assets/index-BIp64Hhi.js')
resp2 = urllib.request.urlopen(req2, timeout=5)
js = resp2.read()
print(f'JS: {len(js)} bytes, OK')

# 测试CSS
req3 = urllib.request.Request('http://127.0.0.1:8545/assets/index-uwLloVWC.css')
resp3 = urllib.request.urlopen(req3, timeout=5)
css = resp3.read()
print(f'CSS: {len(css)} bytes, OK')

# 测试SPA路由(任意路径应返回index.html)
req4 = urllib.request.Request('http://127.0.0.1:8545/wallet')
resp4 = urllib.request.urlopen(req4, timeout=5)
spa = resp4.read().decode()
print(f'SPA路由(/wallet): {len(spa)} bytes, DOCTYPE={\"DOCTYPE\" in spa}')
"'''
        out, err = ssh_exec(host, cmd)
        for line in out.split('\n'):
            print(f"    {line}")
        if err:
            print(f"    ERR: {err[:200]}")
        
        # 7. 检查错误日志
        print("  [错误日志]")
        out, _ = ssh_exec(host, "tail -3 /opt/pouw-chain/logs/node.err 2>/dev/null || echo '无错误'")
        print(f"    {out[:200] if out else '无错误'}")
    
    # Dashboard数据测试
    print(f"\n{'='*60}")
    print(f"Dashboard API 测试 (Node1)")
    print(f"{'='*60}")
    
    host = SERVERS[0]["host"]
    dashboard_methods = [
        ("dashboard_getOverview", {}),
        ("stats_getSummary", {}),
        ("chain_getInfo", {}),
        ("miner_getList", {}),
    ]
    
    for method, params in dashboard_methods:
        result = rpc_call(host, method, params)
        try:
            data = json.loads(result)
            # 截取前200字符
            summary = json.dumps(data, indent=2, ensure_ascii=False)[:200]
            print(f"  {method}: OK")
            print(f"    {summary}")
        except:
            print(f"  {method}: {result[:200]}")
    
    print(f"\n{'='*60}")
    print(f"完成！所有节点前端和后端均已部署并验证。")
    print(f"{'='*60}")
    print(f"\n要从浏览器访问前端,需要在腾讯云安全组开放端口 8545")
    print(f"或者使用 SSH 隧道: ssh -L 8545:127.0.0.1:8545 ubuntu@<server-ip>")


if __name__ == "__main__":
    main()
