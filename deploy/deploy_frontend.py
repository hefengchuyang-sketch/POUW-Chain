"""
部署前端和更新后端到所有3台服务器
1. 上传更新后的 main.py 和 core/rpc_service.py
2. 上传 frontend/dist/ 静态文件
3. 重启服务
4. 验证前端和RPC可访问
"""

import paramiko
import os
import time
import json
import urllib.request

SERVERS = [
    {"name": "Node1-Seed", "host": "118.195.149.137", "internal": "10.206.0.14"},
    {"name": "Node2-Miner", "host": "1.13.141.28", "internal": "10.206.0.16"},
    {"name": "Node3-Full", "host": "175.27.156.47", "internal": "10.206.0.47"},
]

SSH_USER = "ubuntu"
SSH_PASS = os.environ.get("SSH_PASSWORD", "")
REMOTE_BASE = "/opt/pouw-chain"
LOCAL_BASE = r"c:\Users\17006\Desktop\maincoin"

# 需要上传的后端文件
BACKEND_FILES = [
    ("main.py", "main.py"),
    ("core/rpc_service.py", "core/rpc_service.py"),
]

# 前端文件
FRONTEND_FILES = [
    ("frontend/dist/index.html", "frontend/dist/index.html"),
    ("frontend/dist/assets/index-BIp64Hhi.js", "frontend/dist/assets/index-BIp64Hhi.js"),
    ("frontend/dist/assets/index-uwLloVWC.css", "frontend/dist/assets/index-uwLloVWC.css"),
]


def ssh_connect(host):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())
    client.connect(host, username=SSH_USER, password=SSH_PASS, timeout=15)
    return client


def ssh_exec(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err


def upload_file(sftp, local_path, remote_path):
    """上传文件，自动创建目录"""
    remote_dir = os.path.dirname(remote_path).replace('\\', '/')
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        # 递归创建目录
        parts = remote_dir.split('/')
        for i in range(2, len(parts) + 1):
            d = '/'.join(parts[:i])
            try:
                sftp.stat(d)
            except FileNotFoundError:
                sftp.mkdir(d)
    sftp.put(local_path, remote_path)


def deploy_to_server(server):
    name = server["name"]
    host = server["host"]
    print(f"\n{'='*60}")
    print(f"部署到 {name} ({host})")
    print(f"{'='*60}")
    
    client = ssh_connect(host)
    sftp = client.open_sftp()
    
    # 1. 创建前端目录
    print(f"  [1/4] 创建前端目录...")
    ssh_exec(client, f"mkdir -p {REMOTE_BASE}/frontend/dist/assets")
    
    # 2. 上传后端文件
    print(f"  [2/4] 上传后端文件...")
    for local_rel, remote_rel in BACKEND_FILES:
        local_path = os.path.join(LOCAL_BASE, local_rel)
        remote_path = f"{REMOTE_BASE}/{remote_rel}"
        upload_file(sftp, local_path, remote_path)
        print(f"    ✓ {remote_rel}")
    
    # 3. 上传前端文件
    print(f"  [3/4] 上传前端文件...")
    for local_rel, remote_rel in FRONTEND_FILES:
        local_path = os.path.join(LOCAL_BASE, local_rel)
        remote_path = f"{REMOTE_BASE}/{remote_rel}"
        upload_file(sftp, local_path, remote_path)
        size = os.path.getsize(local_path)
        print(f"    ✓ {remote_rel} ({size:,} bytes)")
    
    # 4. 重启服务
    print(f"  [4/4] 重启服务...")
    ssh_exec(client, "sudo systemctl restart pouw-chain")
    time.sleep(3)
    
    # 验证服务状态
    out, err = ssh_exec(client, "sudo systemctl is-active pouw-chain")
    print(f"    服务状态: {out}")
    
    if out != "active":
        # 检查错误日志
        out2, _ = ssh_exec(client, f"tail -20 {REMOTE_BASE}/logs/node.err")
        print(f"    错误日志:\n{out2}")
    
    # 验证前端文件存在
    out, _ = ssh_exec(client, f"ls -la {REMOTE_BASE}/frontend/dist/")
    print(f"    前端文件:\n{out}")
    
    # 验证日志中有前端检测
    time.sleep(2)
    out, _ = ssh_exec(client, f"grep -i '前端\|Frontend\|static' {REMOTE_BASE}/logs/node.log | tail -5")
    print(f"    前端日志: {out}")
    
    sftp.close()
    client.close()
    return out == "active" or "active" in out


def test_rpc(host, port=8545):
    """测试 RPC 可用性"""
    try:
        data = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "node_getInfo",
            "params": {}
        }).encode()
        req = urllib.request.Request(
            f"http://{host}:{port}/rpc",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result.get("result", {})
    except Exception as e:
        return {"error": str(e)}


def test_frontend(host, port=8545):
    """测试前端页面可访问"""
    try:
        req = urllib.request.Request(f"http://{host}:{port}/")
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode()
            return "POUW" in html or "<!DOCTYPE" in html
    except Exception as e:
        return False


def main():
    print("=" * 60)
    print("POUW Chain 前端部署")
    print("=" * 60)
    
    # 验证本地文件存在
    all_files = BACKEND_FILES + FRONTEND_FILES
    for local_rel, _ in all_files:
        local_path = os.path.join(LOCAL_BASE, local_rel)
        if not os.path.isfile(local_path):
            print(f"✗ 找不到: {local_path}")
            return
        print(f"✓ {local_rel} ({os.path.getsize(local_path):,} bytes)")
    
    # 部署到所有服务器
    results = {}
    for server in SERVERS:
        try:
            ok = deploy_to_server(server)
            results[server["name"]] = ok
        except Exception as e:
            print(f"  ✗ 部署失败: {e}")
            results[server["name"]] = False
    
    # 等待服务完全启动
    print(f"\n等待服务启动 (10秒)...")
    time.sleep(10)
    
    # 测试连接（通过SSH端口转发方式从服务器内部测试）
    print(f"\n{'='*60}")
    print(f"验证部署结果")
    print(f"{'='*60}")
    
    for server in SERVERS:
        name = server["name"]
        host = server["host"]
        internal = server["internal"]
        print(f"\n{name} ({host}):")
        
        try:
            client = ssh_connect(host)
            
            # RPC测试(从服务器内部)
            cmd = f'''python3 -c "
import urllib.request, json
data = json.dumps({{'jsonrpc':'2.0','id':1,'method':'node_getInfo','params':{{}}}}).encode()
req = urllib.request.Request('http://127.0.0.1:8545/rpc', data=data, headers={{'Content-Type':'application/json'}})
resp = urllib.request.urlopen(req, timeout=5)
result = json.loads(resp.read().decode())
print('RPC OK:', json.dumps(result.get('result',{{}}), indent=2)[:200])
"'''
            out, err = ssh_exec(client, cmd)
            print(f"  RPC: {out[:200]}")
            if err:
                print(f"  RPC err: {err[:200]}")
            
            # 前端测试(从服务器内部)
            cmd2 = f'''python3 -c "
import urllib.request
req = urllib.request.Request('http://127.0.0.1:8545/')
resp = urllib.request.urlopen(req, timeout=5)
html = resp.read().decode()
print('Frontend OK, length:', len(html), 'DOCTYPE' in html)
"'''
            out2, err2 = ssh_exec(client, cmd2)
            print(f"  Frontend: {out2}")
            if err2:
                print(f"  Frontend err: {err2[:200]}")
            
            # 静态资源测试
            cmd3 = f'''python3 -c "
import urllib.request
req = urllib.request.Request('http://127.0.0.1:8545/assets/index-uwLloVWC.css')
resp = urllib.request.urlopen(req, timeout=5)
css = resp.read().decode()
print('CSS OK, length:', len(css))
"'''
            out3, err3 = ssh_exec(client, cmd3)
            print(f"  CSS: {out3}")
            
            client.close()
        except Exception as e:
            print(f"  ✗ 验证失败: {e}")
    
    # 总结
    print(f"\n{'='*60}")
    print(f"部署总结")
    print(f"{'='*60}")
    for name, ok in results.items():
        status = "✓ 成功" if ok else "✗ 失败"
        print(f"  {name}: {status}")
    
    print(f"\n注意: 公网端口 8545 需要在腾讯云安全组中开放才能从浏览器访问！")
    print(f"当前可通过SSH进入服务器后访问 http://127.0.0.1:8545/")
    for server in SERVERS:
        print(f"  {server['name']}: http://{server['host']}:8545/")


if __name__ == "__main__":
    main()
