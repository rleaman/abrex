"""Corpus adapter implementations."""

from abrex.corpora.adapters.fixture import FixtureCorpusAdapter
from abrex.corpora.adapters.historical import (
    BioCCorpusAdapter,
    DelimitedPairCorpusAdapter,
    SDUAcronymIdentificationAdapter,
)

__all__ = [
    "BioCCorpusAdapter",
    "DelimitedPairCorpusAdapter",
    "FixtureCorpusAdapter",
    "SDUAcronymIdentificationAdapter",
]
