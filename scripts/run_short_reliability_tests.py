import argparse
import base64
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rpc.models import RPCError
from core.rpc_service import NodeRPCService


def auth(user: str, is_admin: bool = False):
    return {
        "user": user,
        "user_address": user,
        "is_admin": is_admin,
    }


def p95(values):
    if not values:
        return 0.0
    arr = sorted(values)
    idx = max(0, min(len(arr) - 1, int(round(0.95 * (len(arr) - 1)))))
    return float(arr[idx])


def run_concurrency_suite(service: NodeRPCService, total_cases: int, workers: int):
    lock = threading.Lock()
    latencies_ms = []
    success = 0
    failures = []

    payload = b"short-reliability-concurrency-payload"
    checksum = hashlib.sha256(payload).hexdigest()
    payload_b64 = base64.b64encode(payload).decode("ascii")

    def one_case(i: int):
        owner = f"conc_owner_{i}"
        miner = f"conc_miner_{i}"
        start = time.perf_counter()

        init = service._file_init_upload(
            filename=f"concurrency_{i}.csv",
            totalSize=len(payload),
            checksumSha256=checksum,
            auth_context=auth(owner),
        )
        upload_id = init["uploadId"]

        service._file_upload_chunk(
            uploadId=upload_id,
            chunkIndex=0,
            data=payload_b64,
            auth_context=auth(owner),
        )

        finalized = service._file_finalize_upload(uploadId=upload_id, auth_context=auth(owner))
        file_ref = finalized["fileRef"]

        submit = service._compute_submit_order(
            gpu_type="CPU",
            gpu_count=1,
            price_per_hour=0,
            duration_hours=1,
            free_order=True,
            buyer_address=owner,
            inputDataRef=file_ref,
            inputFilename=f"concurrency_{i}.csv",
            program="result={'status':'ok','suite':'concurrency'}",
        )
        order_id = submit["orderId"]

        accepted = service._compute_accept_order(order_id=order_id, miner_address=miner)
        task_id = accepted["taskId"]
        service._compute_complete_order(order_id=order_id, task_id=task_id)

        outputs = service._task_get_outputs(task_id=task_id, auth_context=auth(owner))
        denied_non_owner = False
        try:
            service._task_get_outputs(task_id=task_id, auth_context=auth(miner))
        except RPCError:
            denied_non_owner = True

        elapsed_ms = (time.perf_counter() - start) * 1000
        if not outputs:
            raise RuntimeError("owner outputs empty")
        if not denied_non_owner:
            raise RuntimeError("non-owner output read not denied")
        return elapsed_ms

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [executor.submit(one_case, i) for i in range(1, total_cases + 1)]
        for fut in as_completed(futures):
            try:
                ms = fut.result()
                with lock:
                    success += 1
                    latencies_ms.append(ms)
            except Exception as exc:
                with lock:
                    failures.append(str(exc))

    return {
        "cases": total_cases,
        "workers": workers,
        "success": success,
        "failure": len(failures),
        "successRate": round(100.0 * success / total_cases, 2) if total_cases else 0.0,
        "avgLatencyMs": round(sum(latencies_ms) / len(latencies_ms), 3) if latencies_ms else 0.0,
        "p95LatencyMs": round(p95(latencies_ms), 3) if latencies_ms else 0.0,
        "failureSamples": failures[:5],
    }


def run_reproducibility_suite(rounds: int):
    service = NodeRPCService()
    service._FILE_RATE_MAX["init_upload"] = max(service._FILE_RATE_MAX.get("init_upload", 10), rounds * 10)
    service._FILE_RATE_MAX["upload_chunk"] = max(service._FILE_RATE_MAX.get("upload_chunk", 200), rounds * 20)
    service._FILE_RATE_MAX["download_chunk"] = max(service._FILE_RATE_MAX.get("download_chunk", 100), rounds * 20)
    service._file_rate_limits = {}

    payload = ("reproducibility-fixed-payload-2026-04-09\n" * 64).encode("utf-8")
    checksum = hashlib.sha256(payload).hexdigest()
    payload_b64 = base64.b64encode(payload).decode("ascii")

    hash_matches = 0
    sample_ref = ""

    for i in range(1, rounds + 1):
        owner = f"repro_owner_{i}"
        init = service._file_init_upload(
            filename="repro.txt",
            totalSize=len(payload),
            checksumSha256=checksum,
            auth_context=auth(owner),
        )
        upload_id = init["uploadId"]

        service._file_upload_chunk(uploadId=upload_id, chunkIndex=0, data=payload_b64, auth_context=auth(owner))
        finalized = service._file_finalize_upload(uploadId=upload_id, auth_context=auth(owner))
        file_ref = finalized["fileRef"]

        downloaded = service._file_download_chunk(
            fileRef=file_ref,
            offset=0,
            length=len(payload),
            auth_context=auth(owner),
        )
        data = base64.b64decode(downloaded["data"])
        if hashlib.sha256(data).hexdigest() == checksum:
            hash_matches += 1

        if i == 1:
            sample_ref = file_ref

    return {
        "rounds": rounds,
        "hashMatch": hash_matches,
        "hashMatchRate": round(100.0 * hash_matches / rounds, 2) if rounds else 0.0,
        "sampleFileRef": sample_ref,
        "expectedSha256": checksum,
    }


def run_restart_recovery_suite():
    owner = "restart_owner"
    payload = b"restart-recovery-file-payload"
    checksum = hashlib.sha256(payload).hexdigest()
    payload_b64 = base64.b64encode(payload).decode("ascii")

    service_1 = NodeRPCService()
    init = service_1._file_init_upload(
        filename="restart_case.txt",
        totalSize=len(payload),
        checksumSha256=checksum,
        auth_context=auth(owner),
    )
    upload_id = init["uploadId"]
    service_1._file_upload_chunk(uploadId=upload_id, chunkIndex=0, data=payload_b64, auth_context=auth(owner))
    finalized = service_1._file_finalize_upload(uploadId=upload_id, auth_context=auth(owner))
    file_ref = finalized["fileRef"]

    service_2 = NodeRPCService()

    info_ok = False
    download_ok = False
    denied_non_owner = False

    try:
        info = service_2._file_get_info(fileRef=file_ref, auth_context=auth(owner))
        info_ok = bool(info and (info.get("fileRef") == file_ref or info.get("file_ref") == file_ref))
    except Exception:
        info_ok = False

    try:
        d = service_2._file_download_chunk(fileRef=file_ref, offset=0, length=len(payload), auth_context=auth(owner))
        restored = base64.b64decode(d["data"])
        download_ok = hashlib.sha256(restored).hexdigest() == checksum
    except Exception:
        download_ok = False

    try:
        service_2._file_get_info(fileRef=file_ref, auth_context=auth("restart_attacker"))
        denied_non_owner = False
    except RPCError:
        denied_non_owner = True

    return {
        "fileRef": file_ref,
        "ownerFileInfoAfterRestart": info_ok,
        "ownerDownloadAfterRestart": download_ok,
        "nonOwnerDeniedAfterRestart": denied_non_owner,
    }


def to_markdown(report: dict) -> str:
    c = report["concurrency"]
    r = report["restartRecovery"]
    p = report["reproducibility"]
    return "\n".join(
        [
            "# Short Reliability Validation Report",
            "",
            "## Executive Summary",
            f"- Generated at (UTC): {report['generatedAt']}",
            f"- Concurrency: {c['success']}/{c['cases']} success ({c['successRate']}%), workers={c['workers']}",
            f"- Concurrency avg/p95 latency: {c['avgLatencyMs']} ms / {c['p95LatencyMs']} ms",
            f"- Restart recovery (owner file info): {'PASS' if r['ownerFileInfoAfterRestart'] else 'FAIL'}",
            f"- Restart recovery (owner download): {'PASS' if r['ownerDownloadAfterRestart'] else 'FAIL'}",
            f"- Restart recovery (non-owner denied): {'PASS' if r['nonOwnerDeniedAfterRestart'] else 'FAIL'}",
            f"- Reproducibility hash match: {p['hashMatch']}/{p['rounds']} ({p['hashMatchRate']}%)",
            "",
            "## Local Scope Note",
            "- This suite is designed for local pre-production validation and does not model multi-region network faults.",
            "",
            "## Reproducibility",
            "- Command: python scripts/run_short_reliability_tests.py --cases 24 --workers 8 --repro-rounds 20",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Run short local reliability validation suite")
    parser.add_argument("--cases", type=int, default=24, help="Total concurrent cases")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers")
    parser.add_argument("--repro-rounds", type=int, default=20, help="Rounds for reproducibility check")
    parser.add_argument("--out-dir", default=os.path.join("docs", "reports"))
    args = parser.parse_args()

    cases = max(6, int(args.cases))
    workers = max(2, int(args.workers))
    repro_rounds = max(5, int(args.repro_rounds))

    service = NodeRPCService()
    service._FILE_RATE_MAX["init_upload"] = max(service._FILE_RATE_MAX.get("init_upload", 10), cases * 5)
    service._FILE_RATE_MAX["upload_chunk"] = max(service._FILE_RATE_MAX.get("upload_chunk", 200), cases * 10)
    service._FILE_RATE_MAX["download_chunk"] = max(service._FILE_RATE_MAX.get("download_chunk", 100), cases * 10)
    service._file_rate_limits = {}

    report = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "concurrency": run_concurrency_suite(service=service, total_cases=cases, workers=workers),
        "restartRecovery": run_restart_recovery_suite(),
        "reproducibility": run_reproducibility_suite(rounds=repro_rounds),
    }

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "short_reliability_report.json")
    md_path = os.path.join(args.out_dir, "short_reliability_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))

    print(
        json.dumps(
            {
                "jsonReport": json_path,
                "markdownReport": md_path,
                "concurrency": report["concurrency"],
                "restartRecovery": report["restartRecovery"],
                "reproducibility": report["reproducibility"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
