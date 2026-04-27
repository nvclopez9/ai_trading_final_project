"""Entrypoint del harness: ``python -m tests.ai_eval``.

- Corre ``run_all()`` y persiste ``tests/ai_eval/last_report.json``.
- Exit code 0 si todos los escenarios pasaron o si hubo skip controlado
  (sin LLM disponible). Exit code 1 si algún escenario falló.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Añadimos la raíz del repo al sys.path para poder hacer ``from src...``
# cuando se invoca con ``python -m tests.ai_eval`` desde la raíz.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.ai_eval.report import write_report  # noqa: E402
from tests.ai_eval.runner import run_all  # noqa: E402


def main() -> int:
    results = run_all()
    out_path = Path(__file__).parent / "last_report.json"
    write_report(results, out_path)

    if results.get("skipped"):
        print(f"[ai_eval] SKIPPED: {results.get('reason', '')}")
        print(f"[ai_eval] report -> {out_path}")
        return 0

    total = results.get("total", 0)
    passed = results.get("passed", 0)
    failed = results.get("failed", 0)
    print(f"[ai_eval] {passed}/{total} passed, {failed} failed")
    for r in results.get("results", []):
        flag = "PASS" if r.get("passed") else "FAIL"
        print(f"  [{flag}] {r['id']}  tools={[tc.get('name') for tc in r.get('tool_calls', [])]}"
              f"  unverified={r.get('unverified', 0)}  failures={r.get('failures', [])}")
    print(f"[ai_eval] report -> {out_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
