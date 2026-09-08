"""Annotate local abbreviation pairs in BioC XML using the PLOD model."""

from __future__ import annotations

import argparse
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import bioc

from .bioc_io import open_bioc
from .config import load_config
from .logging_utils import configure_logging

LOG = logging.getLogger(__name__)
MODEL_NAME = "surrey-nlp/flair-abbr-pubmed-filtered"
posinf = float("inf")

# See PLODv2 GitHub at https://github.com/surrey-nlp/PLODv2-CLM4AbbrDetection


def _merge_adjacent_entities(
    entities: list[dict[str, Any]], text: str
) -> list[dict[str, Any]]:
    if not entities:
        return []
    merge_groups = [[0]]
    for i, entity in enumerate(entities[1:]):
        entity_index = i + 1
        current_group = merge_groups[-1]
        current = entities[current_group[-1]]
        if entity["start"] <= current["end"] + 1:
            # Merge
            current_group.append(entity_index)
        else:
            # Add new group
            merge_groups.append([entity_index])
    merged = []
    for group in merge_groups:
        if not group:
            continue
        m = dict()
        m["start"] = min(entities[ei]["start"] for ei in group)
        m["end"] = max(entities[ei]["end"] for ei in group)
        m["word"] = text[m["start"] : m["end"]]
        m["score"] = sum(float(entities[ei]["score"]) for ei in group) / len(group)
        merged.append(m)
    # TODO Merging is rare with PLODv2, check instances to see if needed
    # LOG.debug(f"TRACE Merged len = {len(merged)} from original len = {len(entities)}")
    return merged


def check_match(f1: dict[str, Any], f2: dict[str, Any], text: str) -> bool:
    dist = f2["start"] - f1["end"]
    if dist <= 0:
        return False
    f1t = text[f1["start"] : f1["end"]]
    f2t = text[f2["start"] : f2["end"]]

    # Check for cases like:
    # - "lysosomal storage disorders (LSDs)"
    # - "Apolipoprotein E ( Apoe )"
    # - "heat-stable antigen (HSA, CD24, nectadrin)"
    # - "N-methyl-D-aspartate (NMDA; or AMPA)"
    if re.search(rf"\b{re.escape(f1t)} *\( *{re.escape(f2t)} *[),;]", text):
        return True

    # Check for "Type 2 diabetes [T2D]"
    if re.search(rf"\b{re.escape(f1t)} *\[ *{re.escape(f2t)} *\]", text):
        return True

    # TODO Add extra spaces and recheck
    # Check for "(Mucopolysaccharidosis Type IIIA, MPS-IIIA)"
    if re.search(rf"\( *{re.escape(f1t)}[,;] *{re.escape(f2t)} *\)", text):
        return True

    # TODO Add extra spaces and recheck
    # Check for "CASP3: caspase 3;" or "FDC, follicular dendritic cell."
    return re.search(rf"\b{re.escape(f1t)}[,:] *{re.escape(f2t)}[;.]", text) is not None


def _cost(lf: dict[str, Any], sf: dict[str, Any], text: str) -> float:
    lf_len = lf["end"] - lf["start"]
    sf_len = sf["end"] - sf["start"]
    match = False
    if lf["end"] <= sf["start"]:
        dist = sf["start"] - lf["end"]
        match = check_match(lf, sf, text)
    elif sf["end"] <= lf["start"]:
        dist = lf["start"] - sf["end"]
        match = check_match(sf, lf, text)
    else:
        return posinf
    if dist > lf_len + sf_len:
        return posinf
    if match:
        return 0.0
    return float(dist)


class PLOD_Abbreviation_Detector:
    def __init__(self, device_name: str):
        """Load the PLOD v2 Flair tagger and return a text-to-entities function."""
        try:
            import flair
            import torch
            from flair.data import Sentence
            from flair.models import SequenceTagger
        except ImportError as exc:
            raise RuntimeError(
                "PLOD v2 abbreviation detection requires flair and torch;"
                + "install the project dependencies."
            ) from exc
        self.Sentence = Sentence

        if device_name == "auto":
            device_name = "cuda" if torch.cuda.is_available() else "cpu"
        if device_name == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA was requested, but no CUDA-enabled GPU is available."
            )
        if device_name not in {"cpu", "cuda"}:
            raise ValueError("abbreviations.device must be auto, cpu, or cuda")

        self.device = torch.device(device_name)
        flair.device = self.device
        LOG.info("Running PLOD v2 abbreviation model on device %s", device_name)
        self.tagger = SequenceTagger.load(MODEL_NAME)
        self.tagger.to(self.device)

    def detect(self, text: str) -> list[dict[str, Any]]:
        if not text:
            return []
        sentence = self.Sentence(text)
        self.tagger.predict(sentence)
        entities = []
        for span in sentence.get_spans("ner"):
            label = span.get_label("ner")
            entities.append(
                {
                    "entity_group": label.value,
                    "word": span.text,
                    "start": span.start_position,
                    "end": span.end_position,
                    "score": float(label.score),
                }
            )
        return entities

    def annotate_passage(self, passage: bioc.BioCPassage) -> int:
        """Replace a passage's annotations and relations with PLOD results."""
        text = passage.text or ""
        passage.annotations = []
        passage.relations = []
        # if LOG.isEnabledFor(logging.DEBUG):
        #    self.log_token_predictions(text)
        entities = self.detect(text)
        # "entity_group" will always be in {"LF, "AC"}
        long_forms = [e for e in entities if e["entity_group"] == "LF"]
        short_forms = [e for e in entities if e["entity_group"] == "AC"]
        # LOG.debug(f"TRACE Original long_forms = {long_forms}")
        # LOG.debug(f"TRACE Original short_forms = {short_forms}")
        long_forms = _merge_adjacent_entities(long_forms, text)
        short_forms = _merge_adjacent_entities(short_forms, text)
        # LOG.debug(f"TRACE Merged long_forms = {long_forms}")
        # LOG.debug(f"TRACE Merged short_forms = {short_forms}")

        # if LOG.isEnabledFor(logging.DEBUG):
        #    for lf_index, lf in enumerate(long_forms):
        #        LOG.debug(f"TRACE Merged long_form #{lf_index}: {lf}")
        #    for sf_index, sf in enumerate(short_forms):
        #        LOG.debug(f"TRACE Merged short_form #{sf_index}: {sf}")
        if not long_forms or not short_forms:
            return 0

        costs = []
        for lf_index, lf in enumerate(long_forms):
            for sf_index, sf in enumerate(short_forms):
                cost = _cost(lf, sf, text)
                # LOG.debug(
                #    f"TRACE cost for LF #{lf_index} {lf} "
                #    + "with SF #{sf_index} {sf} = {cost}"
                # )
                if cost != posinf:
                    costs.append((cost, (lf_index, sf_index)))
        costs.sort()

        # Read pairings into annotations & relations
        relations = []
        lf_used = set()
        sf_used = set()
        for cost, (lf_index, sf_index) in costs:
            if cost == posinf or lf_index in lf_used or sf_index in sf_used:
                continue
            lf_used.add(lf_index)
            sf_used.add(sf_index)
            lf = long_forms[lf_index]
            sf = short_forms[sf_index]
            r_index = len(relations)
            # LOG.debug(
            #    f"TRACE pairing LF #{lf_index} {lf} with SF #{sf_index} {sf} "
            #    + f"and cost {cost} as relation #{r_index}"
            # )
            lf_ann = bioc.BioCAnnotation()
            lf_ann.id = f"LF{r_index}"
            lf_ann.infons = {"ABBR": "LongForm", "type": "ABBR"}
            lf_ann.locations = [bioc.BioCLocation(lf["start"], lf["end"] - lf["start"])]
            lf_ann.text = text[lf["start"] : lf["end"]]
            sf_ann = bioc.BioCAnnotation()
            sf_ann.id = f"SF{r_index}"
            sf_ann.infons = {"ABBR": "ShortForm", "type": "ABBR"}
            sf_ann.locations = [bioc.BioCLocation(sf["start"], sf["end"] - sf["start"])]
            sf_ann.text = text[sf["start"] : sf["end"]]
            passage.annotations.extend([lf_ann, sf_ann])
            relation = bioc.BioCRelation()
            relation.id = f"R{r_index}"
            relation.infons = {"type": "ABBR", "cost": cost}
            relation.nodes = [
                bioc.BioCNode(lf_ann.id, "LongForm"),
                bioc.BioCNode(sf_ann.id, "ShortForm"),
            ]
            relations.append(relation)
            # LOG.debug(
            #    f'TRACE relation #{r_index}: LF = "{lf_ann.text}"'
            #    + ' SF = "{sf_ann.text}"'
            # )
        passage.relations.extend(relations)
        return len(relations)


def _input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted((*input_path.glob("*.xml"), *input_path.glob("*.xml.gz")))
    raise FileNotFoundError(f"Abbreviation input path does not exist: {input_path}")


def _write_collection(path: Path, collection: bioc.BioCCollection) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = ".gz" if str(path).endswith(".gz") else ""
    fd, temporary = tempfile.mkstemp(
        prefix=f"{path.name}.", suffix=suffix, dir=path.parent
    )
    os.close(fd)
    try:
        with open_bioc(Path(temporary), "wt") as handle:
            bioc.dump(collection, handle)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(config_path: Path) -> None:
    config = load_config(config_path)
    detector = PLOD_Abbreviation_Detector(config.abbreviation_device)
    LOG.info("Abbreviation detector loaded")
    input_files = _input_files(config.abbreviation_input)
    output_is_file = config.abbreviation_input.is_file()
    for input_file in input_files:
        output = (
            config.abbreviation_output
            if output_is_file
            else config.abbreviation_output / input_file.name
        )
        LOG.debug(f"Detecting abbreviations from {input_file} to {output}")
        with open_bioc(input_file) as handle:
            collection = bioc.load(handle)
        count = 0
        for document_index, document in enumerate(collection.documents):
            LOG.debug(
                f"Detecting abbreviations in document {document.id}: "
                + f"{document_index + 1} / {len(collection.documents)}"
            )
            for passage_index, passage in enumerate(document.passages):
                LOG.debug(
                    f"Detecting abbreviations in document {document.id} "
                    + f"passage: {passage_index + 1} / {len(document.passages)}"
                )
                found_count = detector.annotate_passage(passage)
                LOG.debug(
                    f"Found {found_count} abbreviation pairs in document {document.id} "
                    + f"passage: {passage_index + 1}"
                )
                count += found_count
        _write_collection(output, collection)
        LOG.info("Wrote %d abbreviation pairs from %s to %s", count, input_file, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/pipeline.yaml"))
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"]
    )
    parser.add_argument("--log-file", type=Path)
    args = parser.parse_args()
    configure_logging(args.log_level, args.log_file)
    run(args.config)


if __name__ == "__main__":
    main()
