#!/usr/bin/env python3
"""Compare OCR engines on the synthetic holdout; write a local benchmark receipt."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from ocr_common import character_error_rate  # noqa: E402
from vision_cli import analyze  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "ocr"
LABELS = FIXTURES / "labels.v1.json"


def exact_token_hits(text: str, tokens: list[str]) -> dict:
    upper = text.upper()
    hits = {token: token.upper() in upper for token in tokens}
    uncertain = [token for token, ok in hits.items() if not ok]
    return {
        "hits": hits,
        "all_exact": all(hits.values()) if tokens else True,
        "uncertain_tokens": uncertain,
    }


def run_case(case: dict, engine: str, tesseract_bin: str | None, paddle_python: str | None) -> dict:
    image = FIXTURES / case["image"]
    started = time.perf_counter()
    receipt = analyze(
        image,
        engine=engine,
        timeout_sec=180.0 if engine == "paddle" else 60.0,
        dpi_scale=1.0,
        privacy="SYNTHETIC_PUBLIC",
        tesseract_bin=tesseract_bin,
        lang="eng" if engine == "tesseract" else "auto",
        paddle_python=paddle_python,
    )
    latency = (time.perf_counter() - started) * 1000.0
    hypothesis = receipt.get("full_text") or ""
    reference = case.get("reference_text") or ""
    cer = character_error_rate(reference, hypothesis)
    tokens = exact_token_hits(hypothesis, case.get("exact_tokens") or [])
    return {
        "case_id": case["id"],
        "engine": engine,
        "status": receipt["status"],
        "engine_id": receipt["engine_id"],
        "cer": round(cer, 6),
        "latency_ms": round(receipt.get("latency_ms") or latency, 3),
        "region_count": len(receipt.get("regions") or []),
        "exact_tokens": tokens,
        "proof_ceiling": receipt["proof_ceiling"],
        "action_authority": receipt["action_authority"],
        "semantic_verdict": receipt["semantic_verdict"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engines", default="tesseract,paddle")
    parser.add_argument("--tesseract-bin", default=r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    parser.add_argument("--paddle-python", default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    rows = []
    for engine in engines:
        for case in labels["cases"]:
            rows.append(run_case(
                case,
                engine,
                args.tesseract_bin if Path(args.tesseract_bin).is_file() else None,
                args.paddle_python,
            ))
    by_engine = {}
    for row in rows:
        by_engine.setdefault(row["engine"], []).append(row)
    summary = {}
    for engine, engine_rows in by_engine.items():
        usable = [r for r in engine_rows if r["status"] in {"OK", "NO_TEXT"}]
        cers = [r["cer"] for r in usable if r["case_id"] != "blank"]
        summary[engine] = {
            "cases": len(engine_rows),
            "usable": len(usable),
            "mean_cer": round(statistics.mean(cers), 6) if cers else None,
            "p50_latency_ms": round(statistics.median([r["latency_ms"] for r in usable]), 3) if usable else None,
            "engine_unavailable": all(r["status"] == "ENGINE_UNAVAILABLE" for r in engine_rows),
        }
    payload = {
        "contract_id": "automation.visual-ocr-benchmark/v1",
        "holdout": labels["contract_id"],
        "privacy_classification": "SYNTHETIC_PUBLIC",
        "semantic_verdict": "NOT_EVALUATED",
        "action_authority": "NONE",
        "proof_ceiling": "SYNTHETIC_BENCHMARK_NOT_LIVE_HOST",
        "summary": summary,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
