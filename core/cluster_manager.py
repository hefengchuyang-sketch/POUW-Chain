import urllib.request as urlrequest
import urllib.error as urlerror
import json
import logging
from dataclasses import asdict
import sys
import os

_CLUSTER_WORKERS = []
_NEXT_WORKER = 0

def init_cluster_from_config(config: dict):
    global _CLUSTER_WORKERS
    if "cluster" in config:
        if config["cluster"].get("mode") == "master":
            _CLUSTER_WORKERS = config["cluster"].get("workers", [])
            logging.getLogger().info(f"🚀 Cluster Master initialized with workers: {_CLUSTER_WORKERS}")

def is_master() -> bool:
    return len(_CLUSTER_WORKERS) > 0

def get_cluster_hardware_summary() -> dict:
    total_compute = 0.0
    total_memory = 0.0
    models = []
    
    for worker in _CLUSTER_WORKERS:
        try:
            req = urlrequest.Request(
                f"{worker}/rpc",
                data=json.dumps({"jsonrpc":"2.0", "method":"cluster_hardware", "id":1, "params":{}}).encode(),
                headers={'Content-Type': 'application/json'}
            )
            resp = urlrequest.urlopen(req, timeout=5)
            res = json.loads(resp.read().decode())
            if 'result' in res:
                data = res['result']
                total_compute += data.get('compute_power', 0)
                total_memory += data.get('memory_gb', 0)
                models.append(data.get('model', 'Unknown'))
        except Exception as e:
            logging.getLogger().warning(f"Failed to fetch hardware from worker {worker}: {e}")
            
    if not models:
        return None
        
    models_set = list(set(models))
    model_str = f"Cluster: {' + '.join(models_set)}"
    if len(model_str) > 30:
        model_str = model_str[:27] + "..."
        
    return {
        "name": model_str,
        "compute_power": total_compute,
        "memory_gb": total_memory,
        "worker_count": len(_CLUSTER_WORKERS)
    }

def dispatch_task_to_cluster(task, miner_id: str):
    global _NEXT_WORKER
    if not _CLUSTER_WORKERS:
        return None
        
    worker = _CLUSTER_WORKERS[_NEXT_WORKER % len(_CLUSTER_WORKERS)]
    _NEXT_WORKER = (_NEXT_WORKER + 1) % len(_CLUSTER_WORKERS)
    
    payload = {
        "jsonrpc": "2.0",
        "method": "cluster_execute",
        "params": {
            "task": asdict(task),
            "miner_id": miner_id
        },
        "id": 1
    }
    payload["params"]["task"]["task_type"] = task.task_type.value
    
    try:
        req = urlrequest.Request(
            f"{worker}/rpc",
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        resp = urlrequest.urlopen(req, timeout=300)
        res = json.loads(resp.read().decode('utf-8'))
        
        from core.pouw_executor import RealPoUWResult
        if 'error' in res:
            return RealPoUWResult(task.task_id, miner_id, {"error": str(res['error'])}, 0.0, 0.0, False)
            
        if 'result' in res:
            r = res['result']
            return RealPoUWResult(
                r['task_id'], 
                r['miner_id'], 
                r['result'], 
                r['score'], 
                r['execution_time'], 
                r['verified'], 
                r.get('computation_proof', '')
            )
            
        return RealPoUWResult(task.task_id, miner_id, {"error": "Invalid worker response"}, 0.0, 0.0, False)
    except Exception as e:
        from core.pouw_executor import RealPoUWResult
        return RealPoUWResult(task.task_id, miner_id, {"error": f"Cluster worker failed: {e}"}, 0.0, 0.0, False)