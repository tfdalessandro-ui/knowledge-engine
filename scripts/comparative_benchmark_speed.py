"""Step 9, Dimension B: speed & resource efficiency. Client-side p50/p95
latency for each reachable target (this engine, OpenSearch, SearXNG), plus
server-side CPU/RSS sampled during the burst -- `docker stats` for the two
containerized targets, /proc for this engine's own uvicorn process (PID
read live via `systemctl --user show`, not hardcoded).

All on the SAME shared 2-core sensalis-node box -- there is no comparable
separate hardware available to run this on, so this is explicitly a
same-box comparison, not an isolated-hardware one. Stated here rather than
silently implied.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from comparative_benchmark import (  # noqa: E402
    EngineIndex, OpenSearchIndex, SearXNGIndex,
    load_judgments, url_relevant_docs, web_subset, run_latency,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _engine_pid() -> str | None:
    from config import get_settings

    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", get_settings().service_name, "-p", "MainPID"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        pid = out.split("=", 1)[1]
        return pid if pid != "0" else None
    except Exception:  # noqa: BLE001
        return None


def _proc_snapshot(pid: str) -> dict:
    try:
        status = Path(f"/proc/{pid}/status").read_text()
        rss_kb = next(l for l in status.splitlines() if l.startswith("VmRSS:")).split()[1]
        stat = Path(f"/proc/{pid}/stat").read_text().split()
        utime, stime = int(stat[13]), int(stat[14])  # clock ticks
        return {"rss_kb": int(rss_kb), "cpu_ticks": utime + stime}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _docker_stats(container: str) -> dict:
    try:
        out = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}\t{{.MemUsage}}", container],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        cpu, mem = out.split("\t")
        return {"cpu_pct": cpu, "mem_usage": mem}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def main():
    jbq = load_judgments()
    queries = list(jbq.keys())
    web_q_list = list(web_subset(jbq).keys())
    doc_id_to_url_stem = url_relevant_docs(jbq)

    results = {}

    print(f"[speed] this-engine: {len(queries)} queries...")
    pid = _engine_pid()
    before = _proc_snapshot(pid) if pid else {"error": "no PID"}
    results["this-engine"] = run_latency(EngineIndex(), queries)
    after = _proc_snapshot(pid) if pid else {"error": "no PID"}
    results["this-engine"]["server_pid"] = pid
    results["this-engine"]["rss_kb_after"] = after.get("rss_kb")
    results["this-engine"]["cpu_ticks_delta"] = (
        after.get("cpu_ticks", 0) - before.get("cpu_ticks", 0) if "cpu_ticks" in after and "cpu_ticks" in before else None
    )
    print(results["this-engine"])

    print(f"[speed] opensearch: {len(queries)} queries...")
    results["opensearch"] = run_latency(OpenSearchIndex(), queries)
    results["opensearch"]["docker_stats_snapshot"] = _docker_stats("opensearch_ke")
    print(results["opensearch"])

    print(f"[speed] searxng: {len(web_q_list)} queries (web subset -- see Dimension A note; "
          f"currently degraded, engines suspended, see run notes)...")
    results["searxng"] = run_latency(SearXNGIndex(doc_id_to_url_stem), web_q_list)
    results["searxng"]["docker_stats_snapshot"] = _docker_stats("searxng")
    results["searxng"]["note"] = ("SearXNG's own upstream engines (brave/duckduckgo/google cse/startpage) "
                                    "were suspended for rate-limiting/CAPTCHA at the time of this run -- "
                                    "latency still measured (a real round-trip to a mostly-empty response), "
                                    "just noting relevance scored 0 separately for the same reason.")
    print(results["searxng"])

    results["google-bing"] = {"status": "NOT_ATTEMPTED", "reason": "no API credentials (see Dimension A)"}
    results["_hardware_note"] = ("All targets measured on the same shared 2-core sensalis-node box -- "
                                   "no separate comparable hardware was available for an isolated-hardware run.")

    out_path = REPO_ROOT / "data" / "comparative_benchmark_results.json"
    existing = json.loads(out_path.read_text()) if out_path.exists() else {}
    existing["dimension_B_speed"] = results
    out_path.write_text(json.dumps(existing, indent=2))
    print(f"\n[speed] Dimension B written -> {out_path}")


if __name__ == "__main__":
    main()
