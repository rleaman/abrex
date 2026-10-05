"""Score imported T067 predictions and freeze the primary fresh-check report."""

from __future__ import annotations

from pathlib import Path

from abrex.literature.fresh_readout import materialize_fresh_readout


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    evidence = root / "evidence/T067"
    imported = root / ".artifacts/T067/imported-linux-results"
    materialize_fresh_readout(
        prediction_corpus_path=evidence / "fresh-prediction-input-v1.jsonl",
        prediction_corpus_manifest_path=(
            evidence / "fresh-prediction-input-v1.manifest.json"
        ),
        gold_corpus_path=evidence / "fresh-strict-gold-v1.jsonl",
        gold_corpus_manifest_path=evidence / "fresh-strict-gold-v1.manifest.json",
        ledger_path=evidence / "fresh-eligibility-ledger-v1.json",
        run_manifest_path=evidence / "fresh-run-manifest-v1.json",
        prediction_paths={
            "schwartz_hearst": (imported / "t067-schwartz-hearst/predictions.jsonl"),
            "plodv2_pairing": (
                imported / "t067-plodv2-pairing-linux/predictions.jsonl"
            ),
        },
        result_paths={
            "schwartz_hearst": imported / "t067-schwartz-hearst/result.json",
            "plodv2_pairing": (imported / "t067-plodv2-pairing-linux/result.json"),
        },
        report_path=root / "docs/artifacts/T067-fresh-evaluation-readout-v1.json",
        report_markdown_path=root / "docs/T067-fresh-evaluation-readout.md",
        disposition_path=evidence / "prediction-dispositions-v1.jsonl",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
