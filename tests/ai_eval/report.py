"""Serializa los resultados del harness a JSON en disco."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def write_report(results: dict, path: str | os.PathLike) -> None:
    """Escribe un report JSON con timestamp + resumen + detalle por escenario.

    ``results`` es el dict devuelto por ``run_all()``.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    if results.get("skipped"):
        payload = {
            "timestamp": timestamp,
            "skipped": True,
            "reason": results.get("reason", ""),
            "total": results.get("total", 0),
            "passed": 0,
            "failed": 0,
            "by_scenario": {},
        }
    else:
        by_scenario = {}
        for r in results.get("results", []):
            by_scenario[r["id"]] = {
                "passed": r.get("passed", False),
                "failures": r.get("failures", []),
                "tool_calls": [tc.get("name") for tc in r.get("tool_calls", [])],
                "unverified": r.get("unverified", 0),
                "elapsed_s": r.get("elapsed_s", 0),
                "input": r.get("input", ""),
                # truncamos output para no inflar el JSON
                "output_preview": (r.get("output", "") or "")[:500],
            }
        payload = {
            "timestamp": timestamp,
            "skipped": False,
            "total": results.get("total", 0),
            "passed": results.get("passed", 0),
            "failed": results.get("failed", 0),
            "by_scenario": by_scenario,
        }

    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
