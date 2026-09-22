"""Batch-level cleaning: duplicate detection and quality-issue tallying.

Nothing is silently dropped — duplicates are flagged and excluded from the
"accepted" set, but the counts always add up to rows_received so the
DataQualityRecord is a faithful audit trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.model.schemas import ThermalObservation


@dataclass
class CleaningResult:
    accepted: list[ThermalObservation]
    rejected_count: int
    flagged_count: int
    issue_counts: dict[str, int] = field(default_factory=dict)


def deduplicate(observations: list[ThermalObservation]) -> tuple[list[ThermalObservation], int]:
    seen: set[str] = set()
    deduped: list[ThermalObservation] = []
    dup_count = 0
    for o in observations:
        if o.observation_id in seen:
            dup_count += 1
            continue
        seen.add(o.observation_id)
        deduped.append(o)
    return deduped, dup_count


def clean_batch(observations: list[ThermalObservation], rejected_rows: int) -> CleaningResult:
    deduped, dup_count = deduplicate(observations)

    issue_counts: dict[str, int] = {}
    flagged = 0
    for o in deduped:
        if o.quality_flags:
            flagged += 1
        for q in o.quality_flags:
            issue_counts[q.value] = issue_counts.get(q.value, 0) + 1
    if dup_count:
        issue_counts[QualityIssueDuplicate] = dup_count

    return CleaningResult(
        accepted=deduped,
        rejected_count=rejected_rows,
        flagged_count=flagged,
        issue_counts=issue_counts,
    )


QualityIssueDuplicate = "DUPLICATE_SUSPECTED"
