"""POUW Chain - 热更新代码到 3 台 VPS 并重启"""
import paramiko
import os
import time

servers = [
    ("118.195.149.137", "Node1-Seed"),
    ("1.13.141.28", "Node2-Miner"),
    ("175.27.156.47", "Node3-Full"),
]
password = os.environ.get("SSH_PASSWORD", "")
username = "ubuntu"
local_dir = r"C:\Users\17006\Desktop\maincoin"
remote_dir = "/opt/pouw-chain"


def run_cmd(ssh, cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode().strip(), stderr.read().decode().strip()


def ssh_connect(ip):
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
    ssh.connect(ip, username=username, password=password, timeout=15)
    return ssh


for ip, name in servers:
    print(f"\n=== Updating {name} ({ip}) ===")
    ssh = ssh_connect(ip)

    # Stop service
    run_cmd(ssh, "sudo systemctl stop pouw-chain")
    time.sleep(2)
    print("  Service stopped")

    # Upload updated files
    sftp = ssh.open_sftp()
    for f in ["consensus.py", "tcp_network.py"]:
        sftp.put(os.path.join(local_dir, "core", f), f"{remote_dir}/core/{f}")
    sftp.put(os.path.join(local_dir, "main.py"), f"{remote_dir}/main.py")
    sftp.close()
    print("  Files updated")

    # Clear old data for clean start
    run_cmd(ssh, f"rm -rf {remote_dir}/data/* {remote_dir}/logs/*")
    print("  Old data cleared")

    ssh.close()

# Start nodes in order
print("\n=== Starting nodes in order ===")
# Start seed first
ssh = ssh_connect(servers[0][0])
run_cmd(ssh, "sudo systemctl start pouw-chain")
ssh.close()
print("  Node1-Seed started")

time.sleep(12)

# Start others
for ip, name in servers[1:]:
    ssh = ssh_connect(ip)
    run_cmd(ssh, "sudo systemctl start pouw-chain")
    ssh.close()
    print(f"  {name} started")

time.sleep(15)

# Verify
print("\n=== Verifying ===")
for ip, name in servers:
    ssh = ssh_connect(ip)

    out, _ = run_cmd(ssh, "sudo systemctl is-active pouw-chain")
    print(f"\n{name} ({ip}): {out}")

    out, _ = run_cmd(ssh, f"tail -15 {remote_dir}/logs/node.log")
    if out:
        for line in out.split("\n")[-10:]:
            print(f"  {line}")

    # Check for errors
    out, _ = run_cmd(ssh, f"tail -5 {remote_dir}/logs/node.err")
    if out and "Error" in out:
        print(f"  ERRORS: {out[-200:]}")

    ssh.close()

print("\n=== Update complete! ===")
