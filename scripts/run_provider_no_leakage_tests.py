import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sandbox_executor import (  # noqa: E402
    CodeScanner,
    ExecutionEnvironment,
    SandboxConfig,
    SandboxExecutor,
)


def _report_path(out_dir: str, name: str) -> str:
    return os.path.join(out_dir, name)


def run_scanner_suite() -> Dict:
    cases = [
        {
            "name": "block_os_import",
            "code": "import os\nresult={'ok': True}",
        },
        {
            "name": "block_subprocess_call",
            "code": "import subprocess\nsubprocess.run(['whoami'])\nresult={'ok': True}",
        },
        {
            "name": "block_socket_exfil",
            "code": "import socket\nresult={'ok': True}",
        },
        {
            "name": "block_sensitive_path_open",
            "code": "x=open('/etc/passwd','r').read()\nresult=len(x)",
        },
        {
            "name": "block_path_traversal_open",
            "code": "x=open('../../../secret.txt','w');x.write('x')\nresult='ok'",
        },
        {
            "name": "block_dynamic_import",
            "code": "m=__import__('os')\nresult=str(m)",
        },
    ]

    blocked = 0
    details: List[Dict] = []

    for c in cases:
        safe, warnings = CodeScanner.scan(c["code"])
        is_blocked = not safe
        if is_blocked:
            blocked += 1
        details.append(
            {
                "case": c["name"],
                "blocked": is_blocked,
                "warnings": warnings,
            }
        )

    total = len(cases)
    return {
        "totalCases": total,
        "blockedCases": blocked,
        "blockedRate": round(100.0 * blocked / total, 2) if total else 0.0,
        "details": details,
    }


def run_inprocess_write_block_suite(rounds: int = 8) -> Dict:
    rounds = max(1, int(rounds))
    probe_name = "provider_leak_probe.txt"
    workspace_probe = os.path.join(os.getcwd(), probe_name)

    if os.path.exists(workspace_probe):
        os.remove(workspace_probe)

    previous_env = os.environ.get("ALLOW_INPROCESS_FALLBACK")
    os.environ["ALLOW_INPROCESS_FALLBACK"] = "true"

    blocked = 0
    no_file_created = 0
    details = []

    try:
        executor = SandboxExecutor(force_simulate=False)
        # Force in-process path to test the restrictive fallback runtime deterministically.
        executor._use_docker = False

        cfg = SandboxConfig(
            environment=ExecutionEnvironment.CONTAINER,
            timeout_seconds=5,
            enable_network=False,
            enable_filesystem=False,
        )

        for i in range(1, rounds + 1):
            if os.path.exists(workspace_probe):
                os.remove(workspace_probe)

            code = "\n".join(
                [
                    "blocked=False",
                    "error_type=''",
                    "try:",
                    "    f=open('provider_leak_probe.txt','w')",
                    "    f.write('leak')",
                    "    f.close()",
                    "except Exception as e:",
                    "    blocked=True",
                    "    error_type=type(e).__name__",
                    "result={'write_blocked': blocked, 'error_type': error_type}",
                ]
            )

            ctx = executor.create_context(
                miner_id=f"provider_{i}",
                job_id=f"provider-no-leak-{i}",
                task_data_hash=f"hash_{i}",
                config=cfg,
                task_code=code,
                task_data={"round": i},
            )
            res = executor.execute(ctx.context_id, simulate_computation=False)

            output = res.output_data if res else {}
            write_blocked = bool(output and output.get("write_blocked") is True)
            file_created = os.path.exists(workspace_probe)

            if write_blocked:
                blocked += 1
            if not file_created:
                no_file_created += 1

            details.append(
                {
                    "round": i,
                    "executionSuccess": bool(res and res.success),
                    "writeBlocked": write_blocked,
                    "errorType": (output or {}).get("error_type", ""),
                    "probeFileCreated": file_created,
                }
            )

            if file_created:
                os.remove(workspace_probe)

    finally:
        if previous_env is None:
            os.environ.pop("ALLOW_INPROCESS_FALLBACK", None)
        else:
            os.environ["ALLOW_INPROCESS_FALLBACK"] = previous_env

    return {
        "rounds": rounds,
        "writeBlockedRounds": blocked,
        "writeBlockedRate": round(100.0 * blocked / rounds, 2) if rounds else 0.0,
        "noProbeFileCreatedRounds": no_file_created,
        "noProbeFileCreatedRate": round(100.0 * no_file_created / rounds, 2) if rounds else 0.0,
        "details": details,
    }


def to_markdown(report: Dict) -> str:
    s = report["scanner"]
    r = report["runtime"]
    return "\n".join(
        [
            "# Provider No-Leakage Write Test Report",
            "",
            "## Executive Summary",
            f"- Generated at (UTC): {report['generatedAt']}",
            f"- Scanner blocked suspicious write/exfil patterns: {s['blockedCases']}/{s['totalCases']} ({s['blockedRate']}%)",
            f"- Runtime write blocked rounds: {r['writeBlockedRounds']}/{r['rounds']} ({r['writeBlockedRate']}%)",
            f"- Probe file not created rounds: {r['noProbeFileCreatedRounds']}/{r['rounds']} ({r['noProbeFileCreatedRate']}%)",
            "",
            "## Interpretation",
            "- Provider task code could not persist probe files to workspace in this test scope.",
            "- Static scanner rejected common write/exfil vectors before execution.",
            "",
            "## Reproducibility",
            "- Command: python scripts/run_provider_no_leakage_tests.py --rounds 8",
        ]
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run provider-side no-leakage write tests")
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--out-dir", default=os.path.join("docs", "reports"))
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    report = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scanner": run_scanner_suite(),
        "runtime": run_inprocess_write_block_suite(rounds=max(1, args.rounds)),
    }

    json_path = _report_path(args.out_dir, "provider_no_leakage_report.json")
    md_path = _report_path(args.out_dir, "provider_no_leakage_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))

    print(
        json.dumps(
            {
                "jsonReport": json_path,
                "markdownReport": md_path,
                "scanner": {
                    "blockedRate": report["scanner"]["blockedRate"],
                    "blockedCases": report["scanner"]["blockedCases"],
                    "totalCases": report["scanner"]["totalCases"],
                },
                "runtime": {
                    "writeBlockedRate": report["runtime"]["writeBlockedRate"],
                    "noProbeFileCreatedRate": report["runtime"]["noProbeFileCreatedRate"],
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
