"""Application service for single-document and batch resolver execution."""

from __future__ import annotations

from collections.abc import Iterable

from abrex.domain import Document
from abrex.resolvers.base import (
    ExecutionErrorPolicy,
    PredictionDiagnostic,
    PredictionRecord,
    PredictionValidationError,
    PredictionValidationMode,
    Resolver,
    ResolverExecutionError,
    ResolverMetadata,
    ResolverRunResult,
)
from abrex.resolvers.validation import validate_predictions


class ResolverExecutor:
    """Execute one resolver while enforcing the canonical document contract."""

    def __init__(
        self,
        resolver: Resolver,
        *,
        resolver_key: str | None = None,
        implementation_version: str | None = None,
        validation_mode: PredictionValidationMode = "strict",
        error_policy: ExecutionErrorPolicy = "raise",
    ) -> None:
        if not callable(getattr(resolver, "resolve", None)):
            raise TypeError("resolver must provide a callable resolve method")
        if validation_mode not in ("strict", "permissive"):
            raise ValueError(
                f"Unsupported prediction validation mode: {validation_mode!r}"
            )
        if error_policy not in ("raise", "collect"):
            raise ValueError(f"Unsupported execution error policy: {error_policy!r}")
        key = resolver_key or _resolver_string(resolver, "identity")
        version = implementation_version or _resolver_string(
            resolver, "version", default="unknown"
        )
        self.resolver = resolver
        self.metadata = ResolverMetadata(key, version)
        self.validation_mode = validation_mode
        self.error_policy = error_policy

    def resolve_document(
        self, document: Document, *, mode: PredictionValidationMode | None = None
    ) -> PredictionRecord:
        """Resolve one canonical document and validate every returned value."""

        if not isinstance(document, Document):
            raise TypeError("document must be a Document")
        raw_predictions = self._invoke(document)
        try:
            validated = validate_predictions(
                document,
                raw_predictions,
                resolver=self.metadata,
                mode=mode or self.validation_mode,
            )
        except PredictionValidationError:
            raise
        return PredictionRecord(
            document.document_id,
            predictions=validated.predictions,
            diagnostics=validated.diagnostics,
        )

    def resolve_documents(
        self,
        documents: Iterable[object],
        *,
        mode: PredictionValidationMode | None = None,
        error_policy: ExecutionErrorPolicy | None = None,
    ) -> ResolverRunResult:
        """Resolve a batch, optionally collecting structured execution errors."""

        selected_error_policy = error_policy or self.error_policy
        if selected_error_policy not in ("raise", "collect"):
            raise ValueError(
                f"Unsupported execution error policy: {selected_error_policy!r}"
            )
        records: list[PredictionRecord] = []
        errors: list[ResolverExecutionError] = []
        try:
            source_documents = iter(documents)
        except TypeError as error:
            raise ResolverExecutionError(
                "Resolver batch input must be iterable",
                resolver_key=self.metadata.key,
                document_id=None,
                phase="input",
                cause=error,
            ) from error

        try:
            for document in source_documents:
                if not isinstance(document, Document):
                    batch_error = ResolverExecutionError(
                        "Resolver batch input must contain Document values",
                        resolver_key=self.metadata.key,
                        document_id=None,
                        phase="input",
                    )
                    if selected_error_policy == "raise":
                        raise batch_error
                    errors.append(batch_error)
                    continue
                try:
                    records.append(self.resolve_document(document, mode=mode))
                except PredictionValidationError:
                    raise
                except ResolverExecutionError as execution_error:
                    if selected_error_policy == "raise":
                        raise
                    errors.append(execution_error)
                    records.append(_execution_error_record(document, execution_error))
        except PredictionValidationError:
            raise
        except ResolverExecutionError:
            raise
        except Exception as error:
            raise ResolverExecutionError(
                f"Resolver batch input could not be consumed: {error}",
                resolver_key=self.metadata.key,
                document_id=None,
                phase="input",
                cause=error,
            ) from error
        return ResolverRunResult(self.metadata, tuple(records), tuple(errors))

    def resolve_batch(
        self,
        documents: Iterable[object],
        *,
        mode: PredictionValidationMode | None = None,
        error_policy: ExecutionErrorPolicy | None = None,
    ) -> ResolverRunResult:
        """Alias for :meth:`resolve_documents` for batch-oriented callers."""

        return self.resolve_documents(documents, mode=mode, error_policy=error_policy)

    def _invoke(self, document: Document) -> tuple[object, ...]:
        try:
            returned = self.resolver.resolve(document)
        except Exception as error:
            raise ResolverExecutionError(
                f"Resolver {self.metadata.key!r} failed for document "
                f"{document.document_id!r}: {error}",
                resolver_key=self.metadata.key,
                document_id=document.document_id,
                phase="resolve",
                cause=error,
            ) from error
        try:
            return tuple(returned)
        except Exception as error:
            raise ResolverExecutionError(
                f"Resolver {self.metadata.key!r} output could not be materialized "
                f"for document {document.document_id!r}: {error}",
                resolver_key=self.metadata.key,
                document_id=document.document_id,
                phase="materialize",
                cause=error,
            ) from error


def _resolver_string(
    resolver: Resolver, name: str, *, default: str | None = None
) -> str:
    value = getattr(resolver, name, default)
    if not isinstance(value, str) or not value.strip():
        if default is not None:
            return default
        raise ValueError(f"resolver {name} must be a non-empty string")
    return value


def _execution_error_record(
    document: Document, error: ResolverExecutionError
) -> PredictionRecord:
    diagnostic = PredictionDiagnostic(
        "error",
        "RESOLVER_EXECUTION_FAILED",
        str(error),
        document.document_id,
        action="dropped",
        phase=error.phase,
        details=tuple(
            item
            for item in (
                ("resolver_key", error.resolver_key),
                ("cause_type", error.cause_type or ""),
            )
            if item[1]
        ),
    )
    return PredictionRecord(document.document_id, diagnostics=(diagnostic,))


__all__ = ["ResolverExecutor"]
