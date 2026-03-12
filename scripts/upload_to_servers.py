"""POUW Chain - 自动上传代码到 3 台 VPS"""
import paramiko
import os
import time

servers = [
    ("118.195.149.137", "config.node1.yaml"),
    ("1.13.141.28", "config.node2.yaml"),
    ("175.27.156.47", "config.node3.yaml"),
]
password = os.environ.get("SSH_PASSWORD", "")
username = "ubuntu"
local_dir = r"C:\Users\17006\Desktop\maincoin"
remote_dir = "/opt/pouw-chain"

for ip, config_file in servers:
    print(f"\n=== Deploying to {ip} ===")
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    try:
        ssh.connect(ip, username=username, password=password, timeout=15)
        print(f"  SSH connected")

        stdin, stdout, stderr = ssh.exec_command(
            f"sudo mkdir -p {remote_dir}/core {remote_dir}/deploy {remote_dir}/data {remote_dir}/wallets {remote_dir}/logs && sudo chown -R {username}:{username} {remote_dir}"
        )
        stdout.read()
        time.sleep(1)

        sftp = ssh.open_sftp()

        # Upload core/*.py
        core_dir = os.path.join(local_dir, "core")
        count = 0
        for f in os.listdir(core_dir):
            if f.endswith(".py"):
                sftp.put(os.path.join(core_dir, f), f"{remote_dir}/core/{f}")
                count += 1
        print(f"  core/ {count} files uploaded")

        # Upload main files
        for f in ["main.py", "requirements.txt"]:
            sftp.put(os.path.join(local_dir, f), f"{remote_dir}/{f}")
        print(f"  main.py + requirements.txt uploaded")

        # Upload config
        sftp.put(
            os.path.join(local_dir, "deploy", config_file),
            f"{remote_dir}/config.yaml",
        )
        print(f"  config.yaml ({config_file}) uploaded")

        sftp.close()
        ssh.close()
        print(f"  {ip} DONE")
    except Exception as e:
        print(f"  ERROR on {ip}: {e}")
        try:
            ssh.close()
        except:
            pass

print("\n=== All uploads complete! ===")
