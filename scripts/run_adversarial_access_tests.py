import base64
import hashlib
import json
import os
import sys
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


def expect_denied(fn) -> bool:
    try:
        fn()
        return False
    except RPCError:
        return True


def run_adversarial_suite(rounds: int = 20):
    service = NodeRPCService()
    service._FILE_RATE_MAX["init_upload"] = max(service._FILE_RATE_MAX.get("init_upload", 10), rounds * 5)
    service._FILE_RATE_MAX["upload_chunk"] = max(service._FILE_RATE_MAX.get("upload_chunk", 200), rounds * 10)
    service._FILE_RATE_MAX["download_chunk"] = max(service._FILE_RATE_MAX.get("download_chunk", 100), rounds * 10)
    service._file_rate_limits = {}

    payload = b"adversarial-access-test-payload"
    checksum = hashlib.sha256(payload).hexdigest()
    payload_b64 = base64.b64encode(payload).decode("ascii")

    results = {
        "nonOwnerUploadSessionDenied": 0,
        "nonOwnerFileInfoDenied": 0,
        "nonOwnerFileDownloadDenied": 0,
        "nonOwnerTaskOutputDenied": 0,
        "malformedFileRefRejected": 0,
        "adminCrossOwnerAllowed": 0,
        "totalChecks": 0,
    }

    sample_ids = {}

    for i in range(1, rounds + 1):
        owner = f"owner_{i}"
        attacker = f"attacker_{i}"
        miner = f"miner_{i}"
        admin = "security_admin"

        init = service._file_init_upload(
            filename="attack_case.csv",
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
            inputFilename="attack_case.csv",
            program="result={'status':'ok','kind':'adversarial-access-check'}",
        )
        order_id = submit["orderId"]

        accepted = service._compute_accept_order(order_id=order_id, miner_address=miner)
        task_id = accepted["taskId"]

        service._compute_complete_order(order_id=order_id, task_id=task_id)

        if i == 1:
            sample_ids = {
                "uploadId": upload_id,
                "fileRef": file_ref,
                "orderId": order_id,
                "taskId": task_id,
            }

        checks = [
            (
                "nonOwnerUploadSessionDenied",
                lambda: service._file_get_upload_progress(uploadId=upload_id, auth_context=auth(attacker)),
                True,
            ),
            (
                "nonOwnerFileInfoDenied",
                lambda: service._file_get_info(fileRef=file_ref, auth_context=auth(attacker)),
                True,
            ),
            (
                "nonOwnerFileDownloadDenied",
                lambda: service._file_download_chunk(fileRef=file_ref, offset=0, length=16, auth_context=auth(attacker)),
                True,
            ),
            (
                "nonOwnerTaskOutputDenied",
                lambda: service._task_get_outputs(task_id=task_id, auth_context=auth(attacker)),
                True,
            ),
            (
                "malformedFileRefRejected",
                lambda: service._file_get_info(fileRef="../etc/passwd", auth_context=auth(owner)),
                True,
            ),
            (
                "adminCrossOwnerAllowed",
                lambda: service._file_get_info(fileRef=file_ref, auth_context=auth(admin, is_admin=True)),
                False,
            ),
        ]

        for key, fn, expect_block in checks:
            if expect_block:
                ok = expect_denied(fn)
            else:
                try:
                    fn()
                    ok = True
                except RPCError:
                    ok = False

            results["totalChecks"] += 1
            if ok:
                results[key] += 1

    metrics = {}
    for key in [
        "nonOwnerUploadSessionDenied",
        "nonOwnerFileInfoDenied",
        "nonOwnerFileDownloadDenied",
        "nonOwnerTaskOutputDenied",
        "malformedFileRefRejected",
        "adminCrossOwnerAllowed",
    ]:
        metrics[key + "Rate"] = round(100.0 * results[key] / rounds, 2)

    return {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rounds": rounds,
        "sampleIds": sample_ids,
        "results": results,
        "metrics": metrics,
    }


def to_markdown(report: dict) -> str:
    m = report["metrics"]
    s = report["sampleIds"]
    return "\n".join(
        [
            "# Adversarial Access Control Report",
            "",
            "## Executive Summary",
            f"- Rounds: {report['rounds']}",
            f"- Non-owner upload-session denial: {m['nonOwnerUploadSessionDeniedRate']}%",
            f"- Non-owner file info denial: {m['nonOwnerFileInfoDeniedRate']}%",
            f"- Non-owner file download denial: {m['nonOwnerFileDownloadDeniedRate']}%",
            f"- Non-owner task output denial: {m['nonOwnerTaskOutputDeniedRate']}%",
            f"- Malformed fileRef rejection: {m['malformedFileRefRejectedRate']}%",
            f"- Admin cross-owner access allowed: {m['adminCrossOwnerAllowedRate']}%",
            "",
            "## Scenarios",
            "1. Cross-user upload session probing",
            "2. Cross-user file metadata access",
            "3. Cross-user file content download",
            "4. Cross-user task output read",
            "5. Path-traversal-like malformed fileRef input",
            "6. Admin override verification",
            "",
            "## Sample IDs",
            f"- uploadId: {s.get('uploadId', '')}",
            f"- fileRef: {s.get('fileRef', '')}",
            f"- orderId: {s.get('orderId', '')}",
            f"- taskId: {s.get('taskId', '')}",
            "",
            "## Reproducibility",
            f"- Generated at (UTC): {report['generatedAt']}",
            "- Command: python scripts/run_adversarial_access_tests.py --rounds 20",
        ]
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run adversarial access control tests")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--out-dir", default=os.path.join("docs", "reports"))
    args = parser.parse_args()

    rounds = max(1, int(args.rounds))
    report = run_adversarial_suite(rounds=rounds)

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, "adversarial_access_report.json")
    md_path = os.path.join(args.out_dir, "adversarial_access_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))

    print(
        json.dumps(
            {
                "jsonReport": json_path,
                "markdownReport": md_path,
                "rounds": rounds,
                "metrics": report["metrics"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
