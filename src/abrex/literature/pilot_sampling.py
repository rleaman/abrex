"""Bounded HTTP and reproducible numeric-UID sampling for T051."""

from __future__ import annotations

import hashlib
import json
import random
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, cast

from abrex.literature.pilot_models import FrameRecord, PilotConfig

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


class PilotLimitError(RuntimeError):
    """Raised when a configured acquisition limit is reached."""


Transport = Callable[[str, float, str, int], bytes]


@dataclass(slots=True)
class RequestBudget:
    """Mutable, serializable accounting owned by one pilot run."""

    started_monotonic: float = field(default_factory=time.monotonic)
    total_bytes: int = 0
    metadata_requests: int = 0
    reached: list[str] = field(default_factory=list)

    def elapsed(self) -> float:
        return time.monotonic() - self.started_monotonic


class BoundedClient:
    """NCBI client enforcing retries, response, aggregate-byte, and time limits."""

    def __init__(
        self,
        config: PilotConfig,
        budget: RequestBudget,
        *,
        transport: Transport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.budget = budget
        self._transport = transport or _urlopen
        self._sleep = sleeper

    def get(self, url: str, *, metadata: bool = False) -> bytes:
        """Retrieve one response under all configured limits."""

        if self.budget.elapsed() >= self.config.max_elapsed_seconds:
            self._reach("max_elapsed_seconds")
        if (
            metadata
            and self.budget.metadata_requests >= self.config.max_metadata_requests
        ):
            self._reach("max_metadata_requests")
        last_error: OSError | None = None
        for retry in range(self.config.request_retries + 1):
            if self.budget.elapsed() >= self.config.max_elapsed_seconds:
                self._reach("max_elapsed_seconds")
            if (
                metadata
                and self.budget.metadata_requests >= self.config.max_metadata_requests
            ):
                self._reach("max_metadata_requests")
            if metadata:
                self.budget.metadata_requests += 1
            remaining_bytes = self.config.max_total_bytes - self.budget.total_bytes
            if remaining_bytes <= 0:
                self._reach("max_total_bytes")
            remaining_time = self.config.max_elapsed_seconds - self.budget.elapsed()
            if remaining_time <= 0:
                self._reach("max_elapsed_seconds")
            try:
                payload = self._transport(
                    url,
                    min(self.config.request_timeout_seconds, remaining_time),
                    self.config.user_agent,
                    min(self.config.max_response_bytes, remaining_bytes),
                )
                self.budget.total_bytes += len(payload)
                if len(payload) > self.config.max_response_bytes:
                    self._reach("max_response_bytes")
                if self.budget.total_bytes > self.config.max_total_bytes:
                    self._reach("max_total_bytes")
                if self.budget.elapsed() > self.config.max_elapsed_seconds:
                    self._reach("max_elapsed_seconds")
                if self.config.delay_seconds:
                    self._sleep(self.config.delay_seconds)
                return payload
            except PilotLimitError:
                raise
            except OSError as error:
                last_error = error
                if retry < self.config.request_retries:
                    self._sleep(self.config.retry_backoff_seconds * (2**retry))
        raise OSError(f"request failed after bounded retries: {last_error}")

    def _reach(self, name: str) -> None:
        if name not in self.budget.reached:
            self.budget.reached.append(name)
        raise PilotLimitError(f"pilot reached {name}")


def discover_uid_frame(
    database: str,
    client: BoundedClient,
    *,
    ceiling: int,
) -> FrameRecord:
    """Find and verify the highest assigned UID by bounded range-count queries."""

    if database not in {"pmc", "pubmed"}:
        raise ValueError(f"unsupported database: {database}")
    if ceiling < 1:
        raise ValueError("ceiling must be positive")
    hashes: list[str] = []
    population, digest = _range_count(database, 1, ceiling, client)
    hashes.append(digest)
    if population == 0:
        raise ValueError(f"{database} UID frame is empty")
    unfiltered_count, digest = _term_count(database, "all[filter]", client)
    hashes.append(digest)
    if unfiltered_count != population:
        raise ValueError(
            f"{database} ceiling {ceiling} truncates the unfiltered population: "
            f"frame={population}, unfiltered={unfiltered_count}"
        )
    low = 1
    high = ceiling
    while low < high:
        middle = (low + high + 1) // 2
        count, digest = _range_count(database, middle, ceiling, client)
        hashes.append(digest)
        if count:
            low = middle
        else:
            high = middle - 1
    query = (
        f"1:{ceiling}[uid] count equals all[filter] count; "
        "binary nonempty-range verification"
    )
    return FrameRecord(
        database=cast(Literal["pmc", "pubmed"], database),
        lower_bound=1,
        upper_bound=low,
        population_count=population,
        verified_at=datetime.now(UTC).isoformat(),
        verification_query=query,
        response_hashes=tuple(hashes),
    )


def deterministic_uid_draws(
    seed: int, arm: str, upper_bound: int, maximum: int
) -> tuple[int, ...]:
    """Draw unique numeric identifiers uniformly without replacement."""

    if upper_bound < 1 or maximum < 0:
        raise ValueError("draw bounds must be non-negative and frame nonempty")
    count = min(maximum, upper_bound)
    arm_seed = int.from_bytes(
        hashlib.sha256(f"{seed}:{arm}".encode()).digest()[:8], "big"
    )
    return tuple(random.Random(arm_seed).sample(range(1, upper_bound + 1), count))


def _range_count(
    database: str, lower: int, upper: int, client: BoundedClient
) -> tuple[int, str]:
    term = f"{lower}:{upper}[uid]"
    return _term_count(database, term, client)


def _term_count(database: str, term: str, client: BoundedClient) -> tuple[int, str]:
    query = urllib.parse.urlencode(
        {"db": database, "term": term, "rettype": "count", "retmode": "json"}
    )
    payload = client.get(f"{NCBI_ESEARCH}?{query}", metadata=True)
    try:
        decoded = json.loads(payload)
        count = int(decoded["esearchresult"]["count"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {database} ESearch count response") from error
    return count, hashlib.sha256(payload).hexdigest()


def _urlopen(url: str, timeout: float, user_agent: str, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return cast(bytes, response.read(max_bytes + 1))


__all__ = [
    "BoundedClient",
    "PilotLimitError",
    "RequestBudget",
    "deterministic_uid_draws",
    "discover_uid_frame",
]
