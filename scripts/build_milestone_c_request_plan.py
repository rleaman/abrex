"""Build the no-network TypeSafe and Luna authorization plan for Milestone C."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from abrex.domain import Document
from abrex.literature import read_blind_packet
from abrex.resolvers.direct_extraction import (
    DirectExtractionClient,
    DirectExtractionResolver,
)
from abrex.resolvers.jev import JevCandidateJudgeResolver

TYPE_SAFE_HISTORICAL_USD_PER_MILLION_INPUT_TOKENS = 0.042


class _NoCallClient:
    def create_response(self, **_: object) -> dict[str, object]:
        raise AssertionError("request-plan construction must not call a provider")


def build_plan(
    packet_path: Path,
    clp_request_path: Path,
    clp_response_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Count deterministic request chunks without sending scientific data."""

    packet = read_blind_packet(packet_path)
    documents = tuple(Document(case.case_id, case.text) for case in packet.cases)
    jev = JevCandidateJudgeResolver(
        model="jev-1.13.0",
        policy_version="abrex-candidate-split-v2",
        definition_threshold=0.75,
        orientation_threshold=0.95,
        cache_path=Path(".artifacts/campaign-2026-10/milestone-c/jev-plan-cache.jsonl"),
        cache_only=True,
        maximum_candidates_per_document=512,
        maximum_candidates_per_request=64,
        maximum_request_characters=48_000,
        maximum_network_requests=0,
        maximum_input_tokens=10_000_000,
        timeout_seconds=30,
        retries=0,
        concurrency=8,
    )
    candidate_count = 0
    candidate_documents = 0
    logical_requests = 0
    request_characters = 0
    estimated_input_tokens = 0
    for document in documents:
        generated = jev.pipeline.generate(document)
        candidates = tuple(generated.candidates)
        candidate_count += len(candidates)
        if not candidates:
            continue
        candidate_documents += 1
        chunks = jev._chunks(document, candidates)  # noqa: SLF001
        logical_requests += len(chunks)
        for chunk in chunks:
            state, questions = jev._request(document, chunk)  # noqa: SLF001
            characters = _json_characters(state, questions)
            request_characters += characters
            estimated_input_tokens += max(1, characters // 4)

    clp_request = json.loads(clp_request_path.read_text(encoding="utf-8"))
    clp_response = json.loads(clp_response_path.read_text(encoding="utf-8"))
    clp_documents = clp_request.get("documents")
    clp_results = clp_response.get("documents")
    if not isinstance(clp_documents, list) or not isinstance(clp_results, list):
        raise TypeError("CLP request and response must contain document arrays")
    unresolved = sum(item.get("disposition") == "UNRESOLVED" for item in clp_results)
    clp_live_requests = unresolved
    clp_estimated_tokens = sum(
        max(1, len(json.dumps(item, ensure_ascii=False)) // 4) for item in clp_documents
    )

    typesafe_estimate = estimated_input_tokens + clp_estimated_tokens
    typesafe_token_cap = _round_up(typesafe_estimate * 1.5, 1000)
    typesafe_cost_cap = 0.05
    if (
        typesafe_token_cap
        * TYPE_SAFE_HISTORICAL_USD_PER_MILLION_INPUT_TOKENS
        / 1_000_000
        > typesafe_cost_cap
    ):
        raise ValueError("TypeSafe token plan exceeds the prepared monetary cap")

    direct = DirectExtractionResolver(
        client=cast(DirectExtractionClient, _NoCallClient()),
        model="${AZURE_OPENAI_DEPLOYMENT}",
        policy_version="source-grounded-direct-v1",
        prompt_version="abrex-quote-grounded-2026-10-06-i02",
        reasoning_effort="low",
        cache_path=Path(
            "evidence/campaign-2026-10/milestone-c/luna-confirmatory-cache.jsonl"
        ),
        attempt_ledger_path=Path(
            "evidence/campaign-2026-10/milestone-c/luna-confirmatory-attempts.jsonl"
        ),
        cache_only=True,
        provider="azure_openai",
        endpoint="${AZURE_OPENAI_ENDPOINT}",
        api_key_env="AZURE_OPENAI_API_KEY",
        maximum_document_characters=48_000,
        maximum_network_attempts=120,
        maximum_estimated_input_tokens=1_000_000,
        maximum_output_tokens_per_request=8192,
        monetary_cap_usd=0.10,
        input_usd_per_million_tokens=0.10,
        output_usd_per_million_tokens=0.50,
        timeout_seconds=180,
        retries=0,
    )
    luna_characters = 0
    luna_estimated_tokens = 0
    for document in documents:
        payload = direct.request_payload(document)
        characters = len(
            json.dumps(
                payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            )
        )
        luna_characters += characters
        luna_estimated_tokens += max(1, characters // 4)
    luna_input_cap = _round_up(luna_estimated_tokens * 1.25, 1000)

    plan: dict[str, object] = {
        "schema_version": "campaign-2026-10-milestone-c-request-plan-v1",
        "status": "prepared_no_requests_sent",
        "packet": {
            "path": packet_path.as_posix(),
            "packet_id": packet.packet_id,
            "content_sha256": packet.content_sha256,
            "passages": len(packet.cases),
        },
        "typesafe": {
            "model": "jev-1.13.0",
            "candidate_judge": {
                "passages_examined_offline": len(documents),
                "passages_with_candidates": candidate_documents,
                "candidates": candidate_count,
                "logical_requests": logical_requests,
                "serialized_request_characters": request_characters,
                "estimated_input_tokens": estimated_input_tokens,
            },
            "complete_clp": {
                "source_declared_abbr_sections": len(clp_documents),
                "rules_only_unresolved_sections": unresolved,
                "logical_requests": clp_live_requests,
                "estimated_input_tokens": clp_estimated_tokens,
                "maximum_pair_review_followups": 0,
            },
            "authorization_request": {
                "maximum_network_requests": logical_requests + clp_live_requests,
                "retries": 0,
                "maximum_input_tokens": typesafe_token_cap,
                "monetary_cap_usd": typesafe_cost_cap,
                "cost_basis": (
                    "conservative token cap at the $0.042/M input-token rate "
                    "recorded for the prior Jev development run; provider billing "
                    "must be checked before execution because current live pricing "
                    "could not be retrieved"
                ),
            },
        },
        "luna": {
            "provider": "azure_openai",
            "model_route": "${AZURE_OPENAI_DEPLOYMENT}",
            "prompt_version": "abrex-quote-grounded-2026-10-06-i02",
            "passages": len(documents),
            "logical_requests": len(documents),
            "serialized_request_characters": luna_characters,
            "estimated_input_tokens": luna_estimated_tokens,
            "authorization_request": {
                "maximum_network_attempts": len(documents),
                "retries": 0,
                "maximum_estimated_input_tokens": luna_input_cap,
                "maximum_output_tokens_per_request": 8192,
                "monetary_cap_usd": 0.10,
                "input_usd_per_million_tokens": 0.10,
                "output_usd_per_million_tokens": 0.50,
            },
        },
        "boundary": {
            "candidate_generation_was_offline": True,
            "requests_sent": 0,
            "predictions_materialized": False,
            "review_packet_modified": False,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return plan


def _json_characters(state: object, questions: object) -> int:
    return len(
        json.dumps(
            {"state": state, "questions": questions},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _round_up(value: float, unit: int) -> int:
    return int(math.ceil(value / unit) * unit)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packet",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-c/review-packet-blind-v1.json"
        ),
    )
    parser.add_argument(
        "--clp-request",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-c/clp-rules-only-request-v1.json"
        ),
    )
    parser.add_argument(
        "--clp-response",
        type=Path,
        default=Path(
            "evidence/campaign-2026-10/milestone-c/clp-rules-only-response-v1.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evidence/campaign-2026-10/milestone-c/request-plan-v1.json"),
    )
    args = parser.parse_args(argv)
    plan = build_plan(args.packet, args.clp_request, args.clp_response, args.output)
    print(json.dumps(plan, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
