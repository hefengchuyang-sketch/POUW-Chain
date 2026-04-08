import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.rpc.models import RPCError
from core.rpc_service import NodeRPCService
from core.file_transfer import CHUNK_SIZE


def auth(user: str, is_admin: bool = False):
    return {
        "user": user,
        "user_address": user,
        "is_admin": is_admin,
    }


def deterministic_payload(size_bytes: int, seed: str) -> bytes:
    h = hashlib.sha256(seed.encode("utf-8")).digest()
    out = bytearray()
    while len(out) < size_bytes:
        h = hashlib.sha256(h).digest()
        out.extend(h)
    return bytes(out[:size_bytes])


def p95(values):
    if not values:
        return 0.0
    arr = sorted(values)
    idx = max(0, min(len(arr) - 1, int(round(0.95 * (len(arr) - 1)))))
    return float(arr[idx])


def expect_rpc_error(fn) -> bool:
    try:
        fn()
        return False
    except (RPCError, ValueError):
        return True


def run_suite(rounds: int = 6, payload_size_mb: int = 9):
    service = NodeRPCService()
    service._FILE_RATE_MAX["init_upload"] = max(service._FILE_RATE_MAX.get("init_upload", 10), rounds * 10)
    service._FILE_RATE_MAX["upload_chunk"] = max(service._FILE_RATE_MAX.get("upload_chunk", 200), rounds * 50)
    service._FILE_RATE_MAX["download_chunk"] = max(service._FILE_RATE_MAX.get("download_chunk", 100), rounds * 50)
    service._file_rate_limits = {}

    payload_size = payload_size_mb * 1024 * 1024 + 123
    payload = deterministic_payload(payload_size, seed="maincoin-large-chunk-test")
    checksum = hashlib.sha256(payload).hexdigest()

    total_rounds = max(1, int(rounds))
    results = {
        "multiChunkUploadSuccess": 0,
        "integrityVerified": 0,
        "ownerOnlyDownloadEnforced": 0,
        "invalidChunkRejected": 0,
        "malformedFileRefRejected": 0,
        "totalChecks": 0,
    }

    upload_lat_ms = []
    verify_lat_ms = []
    sample_ids = {}

    for i in range(1, total_rounds + 1):
        owner = f"chunk_owner_{i}"
        attacker = f"chunk_attacker_{i}"

        start_upload = time.perf_counter()
        init = service._file_init_upload(
            filename="public_large.bin",
            totalSize=len(payload),
            checksumSha256=checksum,
            auth_context=auth(owner),
        )
        upload_id = init["uploadId"]

        chunk_count = (len(payload) + CHUNK_SIZE - 1) // CHUNK_SIZE
        for chunk_index in range(chunk_count):
            begin = chunk_index * CHUNK_SIZE
            end = min(begin + CHUNK_SIZE, len(payload))
            chunk = payload[begin:end]
            service._file_upload_chunk(
                uploadId=upload_id,
                chunkIndex=chunk_index,
                data=base64.b64encode(chunk).decode("ascii"),
                auth_context=auth(owner),
            )

        finalized = service._file_finalize_upload(uploadId=upload_id, auth_context=auth(owner))
        file_ref = finalized["fileRef"]
        upload_ms = (time.perf_counter() - start_upload) * 1000
        upload_lat_ms.append(upload_ms)

        if i == 1:
            sample_ids = {
                "uploadId": upload_id,
                "fileRef": file_ref,
                "chunkCount": chunk_count,
                "payloadSizeBytes": len(payload),
            }

        results["multiChunkUploadSuccess"] += 1
        results["totalChecks"] += 1

        start_verify = time.perf_counter()
        rehashed = hashlib.sha256()
        offset = 0
        while offset < len(payload):
            resp = service._file_download_chunk(
                fileRef=file_ref,
                offset=offset,
                length=CHUNK_SIZE,
                auth_context=auth(owner),
            )
            block = base64.b64decode(resp["data"])
            rehashed.update(block)
            offset += len(block)

        verify_ms = (time.perf_counter() - start_verify) * 1000
        verify_lat_ms.append(verify_ms)

        if rehashed.hexdigest() == checksum:
            results["integrityVerified"] += 1
        results["totalChecks"] += 1

        if expect_rpc_error(lambda: service._file_download_chunk(fileRef=file_ref, offset=0, length=64, auth_context=auth(attacker))):
            results["ownerOnlyDownloadEnforced"] += 1
        results["totalChecks"] += 1

        bad_init = service._file_init_upload(
            filename="tamper.bin",
            totalSize=len(payload),
            checksumSha256=checksum,
            auth_context=auth(owner),
        )
        bad_upload_id = bad_init["uploadId"]
        wrong_chunk = payload[: CHUNK_SIZE - 1]
        if expect_rpc_error(
            lambda: service._file_upload_chunk(
                uploadId=bad_upload_id,
                chunkIndex=0,
                data=base64.b64encode(wrong_chunk).decode("ascii"),
                auth_context=auth(owner),
            )
        ):
            results["invalidChunkRejected"] += 1
        results["totalChecks"] += 1

        if expect_rpc_error(lambda: service._file_get_info(fileRef="..\\evil", auth_context=auth(owner))):
            results["malformedFileRefRejected"] += 1
        results["totalChecks"] += 1

    metrics = {
        "rounds": total_rounds,
        "payloadSizeBytes": len(payload),
        "chunkSizeBytes": CHUNK_SIZE,
        "expectedChunks": (len(payload) + CHUNK_SIZE - 1) // CHUNK_SIZE,
        "multiChunkUploadSuccessRate": round(100.0 * results["multiChunkUploadSuccess"] / total_rounds, 2),
        "integrityVerifiedRate": round(100.0 * results["integrityVerified"] / total_rounds, 2),
        "ownerOnlyDownloadEnforcedRate": round(100.0 * results["ownerOnlyDownloadEnforced"] / total_rounds, 2),
        "invalidChunkRejectedRate": round(100.0 * results["invalidChunkRejected"] / total_rounds, 2),
        "malformedFileRefRejectedRate": round(100.0 * results["malformedFileRefRejected"] / total_rounds, 2),
        "avgUploadMs": round(sum(upload_lat_ms) / len(upload_lat_ms), 3) if upload_lat_ms else 0.0,
        "p95UploadMs": round(p95(upload_lat_ms), 3) if upload_lat_ms else 0.0,
        "avgVerifyMs": round(sum(verify_lat_ms) / len(verify_lat_ms), 3) if verify_lat_ms else 0.0,
        "p95VerifyMs": round(p95(verify_lat_ms), 3) if verify_lat_ms else 0.0,
    }

    return {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": results,
        "metrics": metrics,
        "sampleIds": sample_ids,
    }


def to_markdown(report: dict) -> str:
    m = report["metrics"]
    s = report.get("sampleIds", {})
    return "\n".join(
        [
            "# Large Chunk Integrity Report",
            "",
            "## Executive Summary",
            f"- Rounds: {m['rounds']}",
            f"- Payload size: {m['payloadSizeBytes']} bytes",
            f"- Chunk size: {m['chunkSizeBytes']} bytes",
            f"- Expected chunks per file: {m['expectedChunks']}",
            f"- Multi-chunk upload success: {m['multiChunkUploadSuccessRate']}%",
            f"- End-to-end integrity verification: {m['integrityVerifiedRate']}%",
            f"- Owner-only download enforcement: {m['ownerOnlyDownloadEnforcedRate']}%",
            f"- Invalid chunk rejection: {m['invalidChunkRejectedRate']}%",
            f"- Malformed fileRef rejection: {m['malformedFileRefRejectedRate']}%",
            "",
            "## Timing (ms)",
            f"- Avg upload: {m['avgUploadMs']}",
            f"- P95 upload: {m['p95UploadMs']}",
            f"- Avg integrity verify: {m['avgVerifyMs']}",
            f"- P95 integrity verify: {m['p95VerifyMs']}",
            "",
            "## Sample IDs",
            f"- uploadId: {s.get('uploadId', '')}",
            f"- fileRef: {s.get('fileRef', '')}",
            f"- chunkCount: {s.get('chunkCount', '')}",
            "",
            "## Reproducibility",
            f"- Generated at (UTC): {report['generatedAt']}",
            "- Command: python scripts/run_large_chunk_integrity_tests.py --rounds 6 --payload-mb 9",
        ]
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run large chunk integrity and adversarial upload checks")
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--payload-mb", type=int, default=9)
    parser.add_argument("--out-dir", default=os.path.join("docs", "reports"))
    args = parser.parse_args()

    report = run_suite(rounds=max(1, args.rounds), payload_size_mb=max(5, args.payload_mb))

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "large_chunk_integrity_report.json")
    md_path = os.path.join(args.out_dir, "large_chunk_integrity_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))

    print(
        json.dumps(
            {
                "jsonReport": json_path,
                "markdownReport": md_path,
                "metrics": report["metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
