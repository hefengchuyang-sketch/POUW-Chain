import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RPC_URL = "http://127.0.0.1:8545"


def run_cmd(cmd: List[str], timeout: int = 120) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT: {' '.join(cmd)}"
    except Exception as exc:
        return False, f"ERROR: {' '.join(cmd)} -> {exc}"

    ok = proc.returncode == 0
    output = (proc.stdout or "").strip()
    return ok, output


def rpc_call(url: str, method: str, params=None, timeout: int = 8) -> Dict:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or [],
        "id": 1,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        return {"error": {"message": f"rpc_unreachable:{exc}"}}
    except Exception as exc:
        return {"error": {"message": f"rpc_request_failed:{exc}"}}


def summarize_pytest(output: str) -> Dict[str, int]:
    summary = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
    }
    patterns = {
        "passed": r"(\d+)\s+passed",
        "failed": r"(\d+)\s+failed",
        "errors": r"(\d+)\s+error",
        "skipped": r"(\d+)\s+skipped",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            summary[key] = int(match.group(1))
    return summary


def phase_startup_checks(python_cmd: str) -> Tuple[bool, Dict[str, str]]:
    results: Dict[str, str] = {}

    checks = [
        [python_cmd, "-3", "scripts/compile_check.py"],
        [python_cmd, "-3", "-c", "from main import POUWNode; print('startup-import-ok')"],
    ]

    all_ok = True
    for cmd in checks:
        ok, output = run_cmd(cmd)
        label = " ".join(cmd[2:])
        results[label] = output.splitlines()[-1] if output else ""
        if not ok:
            all_ok = False

    return all_ok, results


def phase_rpc_checks(rpc_url: str) -> Tuple[bool, List[Dict[str, str]]]:
    calls = [
        ("getinfo", []),
        ("getblockcount", []),
        ("getnetworkinfo", []),
        ("orderbook_getMarketPrice", [{"gpuType": "RTX4090"}]),
        ("billing_estimateTask", [{"gpuType": "RTX4090", "durationHours": 1}]),
    ]

    report = []
    all_ok = True

    for method, params in calls:
        resp = rpc_call(rpc_url, method, params=params)
        if "error" in resp:
            all_ok = False
            err = resp.get("error")
            if isinstance(err, dict):
                message = str(err.get("message", "unknown_error"))
            else:
                message = str(err)
            report.append({"method": method, "ok": "false", "detail": message})
            continue
        report.append({"method": method, "ok": "true", "detail": "ok"})

    return all_ok, report


def phase_test_summary(python_cmd: str) -> Tuple[bool, Dict[str, int], str]:
    cmd = [
        python_cmd,
        "-3",
        "-m",
        "pytest",
        "tests/test_rpc_error_contract.py",
        "tests/test_security_baseline_enforcement.py",
        "-q",
    ]
    ok, output = run_cmd(cmd, timeout=180)
    summary = summarize_pytest(output)
    return ok, summary, output


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified smoke checks for startup, RPC and test summary")
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument("--skip-rpc", action="store_true")
    args = parser.parse_args()

    python_cmd = "py"

    startup_ok, startup_report = phase_startup_checks(python_cmd)

    rpc_ok = True
    rpc_report: List[Dict[str, str]] = []
    if not args.skip_rpc:
        rpc_ok, rpc_report = phase_rpc_checks(args.rpc_url)

    tests_ok, tests_summary, tests_output = phase_test_summary(python_cmd)

    print("=" * 72)
    print("UNIFIED SMOKE SUMMARY")
    print("=" * 72)
    print(f"startup_checks: {'PASS' if startup_ok else 'FAIL'}")
    for k, v in startup_report.items():
        print(f"  - {k}: {v}")

    if args.skip_rpc:
        print("rpc_checks: SKIPPED")
    else:
        print(f"rpc_checks: {'PASS' if rpc_ok else 'FAIL'}")
        for item in rpc_report:
            print(f"  - {item['method']}: {item['ok']} ({item['detail']})")

    print(f"tests: {'PASS' if tests_ok else 'FAIL'}")
    print(
        "  - passed={passed} failed={failed} errors={errors} skipped={skipped}".format(
            **tests_summary
        )
    )

    if not tests_ok:
        print("-" * 72)
        print("pytest output")
        print("-" * 72)
        print(tests_output)

    overall_ok = startup_ok and tests_ok and (args.skip_rpc or rpc_ok)
    print("=" * 72)
    print(f"overall: {'PASS' if overall_ok else 'FAIL'}")
    print("=" * 72)

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
