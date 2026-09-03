# T016 - PMC/PubMed Production Adapter

## Goal

Integrate the resolver into biomedical literature processing without coupling literature retrieval/parsing to core abbreviation science.

## Depends on

T005, T010.

## Scope

Define an adapter layer from existing PubMed/PMC article representation into canonical `Document` objects and back to downstream entity-linking consumers.

Support stable provenance from article identifiers and sections.

## Design constraints

- core resolver package must not depend on NCBI retrieval APIs;
- networking/retrieval is outside the resolver interface;
- section/document segmentation policy is explicit/configurable;
- downstream entity pipeline integration stays behind an adapter boundary.

## Acceptance criteria

An article already present locally can be converted to canonical documents, resolved through a YAML-selected resolver, and mapped back to article provenance without changing core resolver/evaluator code.
