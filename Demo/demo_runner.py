import json
import sys
import time
import urllib.request

RPC_URL = "http://127.0.0.1:18545"


def rpc(method, params=None, timeout=20):
    payload = json.dumps({
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
        "id": int(time.time() * 1000) % 100000,
    }).encode("utf-8")
    req = urllib.request.Request(
        RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if "error" in body and body["error"]:
        raise RuntimeError(f"RPC {method} failed: {body['error']}")
    return body.get("result")


def wait_node_ready(retry=30):
    for _ in range(retry):
        try:
            rpc("blockchain_getHeight", {})
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError("Node RPC is not ready on 18545")


def main():
    print("[Demo] Waiting node ready...")
    wait_node_ready()

    print("[Demo] Creating two accounts (Order + Mining)...")
    order_wallet = rpc("wallet_create", {"password": "demo-order"})
    miner_wallet = rpc("wallet_create", {"password": "demo-miner"})
    order_addr = order_wallet.get("address")
    miner_addr = miner_wallet.get("address")
    if not order_addr or not miner_addr:
        raise RuntimeError("Failed to create demo accounts")

    print(f"[Demo] Order Account: {order_addr}")
    print(f"[Demo] Mining Account: {miner_addr}")

    print("[Demo] Start mining account in task mode...")
    mining_start = rpc("mining_start", {
        "address": miner_addr,
        "mode": "task_only",
    })
    print("[Demo] mining_start:", mining_start)

    print("[Demo] Place FREE order from Order Account...")
    submitted = rpc("compute_submitOrder", {
        "gpu_type": "RTX4090",
        "gpu_count": 1,
        "duration_hours": 1,
        "price_per_hour": 0,
        "free_order": True,
        "buyer_address": order_addr,
        "program": "print('demo program running')",
    })
    order_id = submitted.get("orderId")
    if not order_id:
        raise RuntimeError("compute_submitOrder did not return orderId")
    print("[Demo] order submitted:", submitted)

    print("[Demo] Mining Account accepts order...")
    accepted = rpc("compute_acceptOrder", {
        "order_id": order_id,
        "miner_address": miner_addr,
    })
    task_id = accepted.get("taskId")
    print("[Demo] accepted:", accepted)

    print("[Demo] Check mining status (must see accepted order + running program)...")
    mining_status = rpc("mining_getStatus", {"address": miner_addr})
    print("[Demo] acceptedOrders:", len(mining_status.get("acceptedOrders", [])))
    print("[Demo] runningPrograms:", len(mining_status.get("runningPrograms", [])))

    print("[Demo] Complete order and return result to Order Account...")
    completed = rpc("compute_completeOrder", {
        "order_id": order_id,
        "task_id": task_id,
        "result_data": "demo_result_ok",
    })
    print("[Demo] completed:", completed)

    print("[Demo] Query order result (Order Account should receive it)...")
    order_info = rpc("compute_getOrder", {"order_id": order_id})
    print(json.dumps({
        "orderId": order_id,
        "status": order_info.get("status"),
        "result": order_info.get("result"),
        "buyerAddress": order_info.get("buyerAddress"),
        "acceptedBy": order_info.get("acceptedBy"),
        "buyerBalanceAfter": order_info.get("buyerBalanceAfter"),
        "minerBalanceAfter": order_info.get("minerBalanceAfter"),
    }, ensure_ascii=False, indent=2))

    print("[Demo] Show other feature samples...")
    print("chain_getInfo:", rpc("chain_getInfo", {}))
    print("blockchain_getHeight:", rpc("blockchain_getHeight", {}))
    print("orderbook_submitBid free:", rpc("orderbook_submitBid", {
        "gpuType": "RTX4090",
        "gpuCount": 1,
        "maxPricePerHour": 0,
        "duration": 1,
    }))

    print("\n[Demo] SUCCESS: full demo flow completed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[Demo] FAILED: {exc}")
        sys.exit(1)
