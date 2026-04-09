import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _safe_get(d: Optional[Dict[str, Any]], *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def _pass_rate(v: Optional[float]) -> bool:
    if v is None:
        return False
    try:
        return float(v) >= 99.0
    except Exception:
        return False


def build_summary(reports_dir: str) -> Dict[str, Any]:
    iris = _read_json(os.path.join(reports_dir, "public_dataset_validation_iris.json"))
    digits = _read_json(os.path.join(reports_dir, "public_dataset_validation_digits.json"))
    adversarial = _read_json(os.path.join(reports_dir, "adversarial_access_report.json"))
    large_chunk = _read_json(os.path.join(reports_dir, "large_chunk_integrity_report.json"))
    short_rel = _read_json(os.path.join(reports_dir, "short_reliability_report.json"))
    no_leak = _read_json(os.path.join(reports_dir, "provider_no_leakage_report.json"))

    checks = []

    # Public dataset checks
    iris_e2e = _safe_get(iris, "metrics", "endToEndSuccessRate")
    if iris_e2e is None:
        iris_e2e = _safe_get(iris, "metrics", "successRate")
    iris_owner = _safe_get(iris, "metrics", "ownerOnlyOutputEnforcedRate")
    if iris_owner is None:
        iris_owner = _safe_get(iris, "metrics", "ownerResultEnforcementRate")
    checks.append({"name": "Iris end-to-end", "value": iris_e2e, "pass": _pass_rate(iris_e2e)})
    checks.append({"name": "Iris owner-only output", "value": iris_owner, "pass": _pass_rate(iris_owner)})

    digits_e2e = _safe_get(digits, "metrics", "endToEndSuccessRate")
    if digits_e2e is None:
        digits_e2e = _safe_get(digits, "metrics", "successRate")
    digits_owner = _safe_get(digits, "metrics", "ownerOnlyOutputEnforcedRate")
    if digits_owner is None:
        digits_owner = _safe_get(digits, "metrics", "ownerResultEnforcementRate")
    checks.append({"name": "Digits end-to-end", "value": digits_e2e, "pass": _pass_rate(digits_e2e)})
    checks.append({"name": "Digits owner-only output", "value": digits_owner, "pass": _pass_rate(digits_owner)})

    # Adversarial checks
    adv_keys = [
        "nonOwnerUploadSessionDeniedRate",
        "nonOwnerFileInfoDeniedRate",
        "nonOwnerFileDownloadDeniedRate",
        "nonOwnerTaskOutputDeniedRate",
        "malformedFileRefRejectedRate",
        "adminCrossOwnerAllowedRate",
    ]
    for k in adv_keys:
        v = _safe_get(adversarial, "metrics", k)
        checks.append({"name": f"Adversarial {k}", "value": v, "pass": _pass_rate(v)})

    # Large chunk checks
    lc_keys = [
        "multiChunkUploadSuccessRate",
        "integrityVerifiedRate",
        "ownerOnlyDownloadEnforcedRate",
        "invalidChunkRejectedRate",
        "malformedFileRefRejectedRate",
    ]
    for k in lc_keys:
        v = _safe_get(large_chunk, "metrics", k)
        checks.append({"name": f"LargeChunk {k}", "value": v, "pass": _pass_rate(v)})

    # Short reliability checks
    sr_success = _safe_get(short_rel, "concurrency", "successRate")
    sr_repro = _safe_get(short_rel, "reproducibility", "hashMatchRate")
    sr_restart_info = bool(_safe_get(short_rel, "restartRecovery", "ownerFileInfoAfterRestart", default=False))
    sr_restart_dl = bool(_safe_get(short_rel, "restartRecovery", "ownerDownloadAfterRestart", default=False))
    sr_restart_deny = bool(_safe_get(short_rel, "restartRecovery", "nonOwnerDeniedAfterRestart", default=False))

    checks.append({"name": "ShortReliability concurrency success", "value": sr_success, "pass": _pass_rate(sr_success)})
    checks.append({"name": "ShortReliability reproducibility", "value": sr_repro, "pass": _pass_rate(sr_repro)})
    checks.append({"name": "ShortReliability restart owner info", "value": sr_restart_info, "pass": sr_restart_info})
    checks.append({"name": "ShortReliability restart owner download", "value": sr_restart_dl, "pass": sr_restart_dl})
    checks.append({"name": "ShortReliability restart non-owner deny", "value": sr_restart_deny, "pass": sr_restart_deny})

    # No leakage checks
    leak_scan = _safe_get(no_leak, "scanner", "blockedRate")
    leak_runtime_block = _safe_get(no_leak, "runtime", "writeBlockedRate")
    leak_runtime_nofile = _safe_get(no_leak, "runtime", "noProbeFileCreatedRate")

    checks.append({"name": "NoLeak scanner block rate", "value": leak_scan, "pass": _pass_rate(leak_scan)})
    checks.append({"name": "NoLeak runtime write blocked", "value": leak_runtime_block, "pass": _pass_rate(leak_runtime_block)})
    checks.append({"name": "NoLeak runtime no file created", "value": leak_runtime_nofile, "pass": _pass_rate(leak_runtime_nofile)})

    total = len(checks)
    passed = sum(1 for c in checks if c["pass"])

    return {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reportsDir": reports_dir,
        "totalChecks": total,
        "passedChecks": passed,
        "passRate": round(100.0 * passed / total, 2) if total else 0.0,
        "overallStatus": "PASS" if total > 0 and passed == total else "PARTIAL",
        "checks": checks,
        "sources": {
            "public_dataset_validation_iris": bool(iris),
            "public_dataset_validation_digits": bool(digits),
            "adversarial_access_report": bool(adversarial),
            "large_chunk_integrity_report": bool(large_chunk),
            "short_reliability_report": bool(short_rel),
            "provider_no_leakage_report": bool(no_leak),
        },
    }


def to_markdown(summary: Dict[str, Any]) -> str:
    lines = [
        "# Full Validation Summary",
        "",
        "## Executive Summary",
        f"- Generated at (UTC): {summary['generatedAt']}",
        f"- Overall status: {summary['overallStatus']}",
        f"- Checks passed: {summary['passedChecks']}/{summary['totalChecks']} ({summary['passRate']}%)",
        "",
        "## Source Reports Presence",
    ]

    for k, v in summary["sources"].items():
        lines.append(f"- {k}: {'present' if v else 'missing'}")

    lines.extend(["", "## Check Matrix"])
    for c in summary["checks"]:
        lines.append(f"- [{ 'PASS' if c['pass'] else 'FAIL' }] {c['name']}: {c['value']}")

    lines.extend(
        [
            "",
            "## Interpretation",
            "- This summary aggregates correctness, authorization, integrity, reliability, and provider-side no-leakage checks.",
            "- Local validation scope does not include multi-region distributed fault injection.",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate a full validation summary from all report JSON files")
    parser.add_argument("--reports-dir", default=os.path.join("docs", "reports"))
    args = parser.parse_args()

    os.makedirs(args.reports_dir, exist_ok=True)

    summary = build_summary(args.reports_dir)
    json_path = os.path.join(args.reports_dir, "full_validation_summary.json")
    md_path = os.path.join(args.reports_dir, "full_validation_summary.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(summary))

    print(
        json.dumps(
            {
                "jsonReport": json_path,
                "markdownReport": md_path,
                "overallStatus": summary["overallStatus"],
                "passRate": summary["passRate"],
                "passedChecks": summary["passedChecks"],
                "totalChecks": summary["totalChecks"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
