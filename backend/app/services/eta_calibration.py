"""Calibrate new ETA values from completed local jobs without external telemetry."""
from statistics import median

from sqlalchemy.orm import Session

from app.models import Job


def calibrate_stage_estimates(
    db: Session,
    source_type: str,
    baseline: dict[str, float],
    limit: int = 30,
) -> tuple[dict[str, float], dict[str, float]]:
    """Apply a bounded calibration that becomes stronger with more evidence.

    The first completed job can already signal that a device is slower than the
    generic baseline, but affects a new ETA only slightly. The confidence ramps
    to full strength after five compatible completed jobs.
    """
    jobs = (
        db.query(Job)
        .filter(Job.status == "done", Job.source_type == source_type)
        .order_by(Job.completed_at.desc())
        .limit(limit)
        .all()
    )
    ratios_by_stage: dict[str, list[float]] = {stage: [] for stage in baseline}
    for job in jobs:
        previous_estimates = job.stage_estimates
        for stage, expected in previous_estimates.items():
            actual = job.stage_metrics.get(stage, 0.0)
            if stage not in ratios_by_stage or expected <= 0 or actual <= 0:
                continue
            ratios_by_stage[stage].append(actual / expected)

    factors: dict[str, float] = {}
    calibrated: dict[str, float] = {}
    for stage, estimate in baseline.items():
        ratios = ratios_by_stage.get(stage, [])
        if ratios:
            observed = median(ratios)
            confidence = min(1.0, len(ratios) / 5.0)
            factor = 1.0 + ((observed - 1.0) * confidence)
        else:
            factor = 1.0
        factor = min(2.5, max(0.6, factor))
        factors[stage] = round(factor, 2)
        calibrated[stage] = round(float(estimate) * factor, 1)
    return calibrated, factors
