"""Corpus adapter implementations."""

from abrex.corpora.adapters.fixture import FixtureCorpusAdapter
from abrex.corpora.adapters.historical import (
    BioCCorpusAdapter,
    BioCLocationPolicy,
    BioCPairingPolicy,
    BioCTextPolicy,
    DelimitedPairCorpusAdapter,
    SDUAcronymDisambiguationAdapter,
    SDUAcronymExtractionAdapter,
    SDUAcronymIdentificationAdapter,
)

__all__ = [
    "BioCCorpusAdapter",
    "BioCPairingPolicy",
    "BioCTextPolicy",
    "BioCLocationPolicy",
    "DelimitedPairCorpusAdapter",
    "FixtureCorpusAdapter",
    "SDUAcronymDisambiguationAdapter",
    "SDUAcronymExtractionAdapter",
    "SDUAcronymIdentificationAdapter",
]
