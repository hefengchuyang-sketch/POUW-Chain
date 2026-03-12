import os
"""POUW Chain - 按顺序启动 3 个节点并验证"""
import paramiko
import time
import json

servers = [
    ("118.195.149.137", "Node1-Seed"),
    ("1.13.141.28", "Node2-Miner"),
    ("175.27.156.47", "Node3-Full"),
]
password = os.environ.get("SSH_PASSWORD", "")
username = "ubuntu"


def run_cmd(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip(), stderr.read().decode().strip()


def ssh_connect(ip):
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    ssh.connect(ip, username=username, password=password, timeout=15)
    return ssh


# Step 1: 先启动种子节点
print("=" * 50)
print("  Step 1: 启动种子节点 (118.195.149.137)")
print("=" * 50)
ssh = ssh_connect(servers[0][0])
run_cmd(ssh, "sudo systemctl stop pouw-chain 2>/dev/null; sudo systemctl start pouw-chain")
print("  Node1-Seed started")
ssh.close()

# Step 2: 等待种子节点就绪
print("\n  等待种子节点启动 (15 秒)...")
time.sleep(15)

# Step 3: 启动其他节点
for ip, name in servers[1:]:
    print(f"\n  启动 {name} ({ip})...")
    ssh = ssh_connect(ip)
    run_cmd(ssh, "sudo systemctl stop pouw-chain 2>/dev/null; sudo systemctl start pouw-chain")
    print(f"  {name} started")
    ssh.close()

# Step 4: 等待所有节点运行
print("\n  等待所有节点运行 (20 秒)...")
time.sleep(20)

# Step 5: 验证
print("\n" + "=" * 50)
print("  验证节点状态")
print("=" * 50)

for ip, name in servers:
    print(f"\n--- {name} ({ip}) ---")
    ssh = ssh_connect(ip)

    # 检查服务状态
    out, err = run_cmd(ssh, "sudo systemctl is-active pouw-chain")
    status = out.strip()
    if status == "active":
        print(f"  systemd: ACTIVE")
    else:
        print(f"  systemd: {status}")
        # 查看错误日志
        out, err = run_cmd(ssh, "sudo journalctl -u pouw-chain --no-pager -n 20")
        print(f"  Journal: {out[-500:]}")
        out, err = run_cmd(ssh, "cat /opt/pouw-chain/logs/node.err | tail -20")
        print(f"  Stderr: {out[-500:]}")

    # 查看节点日志
    out, err = run_cmd(ssh, "cat /opt/pouw-chain/logs/node.log | tail -10")
    if out:
        print(f"  Log (last 10 lines):")
        for line in out.split("\n")[-10:]:
            print(f"    {line}")

    ssh.close()

print(f"\n{'='*50}")
print("  启动完成!")
print(f"{'='*50}")
print("\nRPC 测试命令:")
for ip, name in servers:
    print(f"  curl -s http://{ip}:8545 -X POST -H 'Content-Type: application/json' "
          f"-d '{{\"jsonrpc\":\"2.0\",\"method\":\"chain_getInfo\",\"params\":[],\"id\":1}}'")
