import os
"""POUW Chain - 在 3 台 VPS 上安装依赖并配置 systemd 服务"""
import paramiko
import time

servers = [
    ("118.195.149.137", "Node1-Seed"),
    ("1.13.141.28", "Node2-Miner"),
    ("175.27.156.47", "Node3-Full"),
]
password = os.environ.get("SSH_PASSWORD", "")
username = "ubuntu"
remote_dir = "/opt/pouw-chain"


def run_cmd(ssh, cmd, timeout=120):
    """执行远程命令并返回输出"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err


for ip, name in servers:
    print(f"\n{'='*50}")
    print(f"  Setting up {name} ({ip})")
    print(f"{'='*50}")

    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    try:
        ssh.connect(ip, username=username, password=password, timeout=15)
        print("  SSH connected")

        # 1. Install system packages
        print("  [1/4] Installing system packages...")
        out, err = run_cmd(ssh,
            "sudo apt-get update -qq && "
            "sudo apt-get install -y -qq python3 python3-pip python3-venv > /dev/null 2>&1 && "
            "echo 'SYSTEM_OK'",
            timeout=180
        )
        if "SYSTEM_OK" in out:
            print("  System packages installed")
        else:
            print(f"  Warning: {err[:200] if err else 'unknown'}")

        # 2. Create venv and install requirements
        print("  [2/4] Creating Python venv & installing requirements...")
        out, err = run_cmd(ssh,
            f"cd {remote_dir} && "
            f"python3 -m venv venv && "
            f"source venv/bin/activate && "
            f"pip install --upgrade pip > /dev/null 2>&1 && "
            f"pip install -r requirements.txt 2>&1 | tail -3 && "
            f"echo 'VENV_OK'",
            timeout=300
        )
        if "VENV_OK" in out:
            print("  Python venv ready")
        else:
            print(f"  Output: {out[-300:]}")
            print(f"  Error: {err[:300] if err else 'none'}")

        # 3. Create systemd service
        print("  [3/4] Creating systemd service...")
        service_content = f"""[Unit]
Description=POUW Multi-Sector Chain Node - {name}
After=network.target

[Service]
Type=simple
User={username}
WorkingDirectory={remote_dir}
ExecStart={remote_dir}/venv/bin/python main.py --config config.yaml --data-dir {remote_dir}/data
Restart=always
RestartSec=10
StandardOutput=append:{remote_dir}/logs/node.log
StandardError=append:{remote_dir}/logs/node.err

[Install]
WantedBy=multi-user.target"""

        out, err = run_cmd(ssh,
            f"echo '{service_content}' | sudo tee /etc/systemd/system/pouw-chain.service > /dev/null && "
            f"sudo systemctl daemon-reload && "
            f"echo 'SERVICE_OK'"
        )
        if "SERVICE_OK" in out:
            print("  systemd service configured")
        else:
            print(f"  Warning: {err[:200] if err else out[:200]}")

        # 4. Verify
        print("  [4/4] Verifying installation...")
        out, err = run_cmd(ssh,
            f"cd {remote_dir} && "
            f"source venv/bin/activate && "
            f"python -c \"import yaml; print('yaml OK')\" && "
            f"python -c \"import asyncio; print('asyncio OK')\" && "
            f"ls -la main.py config.yaml && "
            f"echo 'VERIFY_OK'"
        )
        if "VERIFY_OK" in out:
            print(f"  {name} setup complete!")
        else:
            print(f"  Verify output: {out}")

        ssh.close()

    except Exception as e:
        print(f"  ERROR: {e}")
        try:
            ssh.close()
        except:
            pass

print(f"\n{'='*50}")
print("  All servers setup complete!")
print(f"{'='*50}")
print("\nNext: Run scripts/start_nodes.py to start all nodes")
