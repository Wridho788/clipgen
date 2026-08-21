from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Job
from app.services.eta_calibration import calibrate_stage_estimates


def test_eta_calibration_uses_bounded_median_for_matching_stage_history(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'eta.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    baseline = {"transcribing": 100.0, "cutting": 20.0}

    with Session() as db:
        for index, multiplier in enumerate((1.5, 2.0, 2.5), start=1):
            db.add(
                Job(
                    id=f"job-{index}",
                    source_type="upload",
                    source_path=f"/tmp/{index}.mp4",
                    status="done",
                    stage_estimates_json='{"transcribing": 100, "cutting": 20}',
                    stage_metrics_json=(
                        '{"transcribing": %s, "cutting": %s}'
                        % (100 * multiplier, 20 * multiplier)
                    ),
                    completed_at=datetime.utcnow(),
                )
            )
        db.commit()

        estimates, factors = calibrate_stage_estimates(db, "upload", baseline)

    assert factors == {"transcribing": 1.6, "cutting": 1.6}
    assert estimates == {"transcribing": 160.0, "cutting": 32.0}


def test_eta_calibration_uses_a_small_adjustment_from_one_prior_job(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'eta-one.db'}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.add(
            Job(
                id="job-1",
                source_type="upload",
                source_path="/tmp/source.mp4",
                status="done",
                stage_estimates_json='{"transcribing": 100}',
                stage_metrics_json='{"transcribing": 200}',
                completed_at=datetime.utcnow(),
            )
        )
        db.commit()
        estimates, factors = calibrate_stage_estimates(db, "upload", {"transcribing": 100.0})

    assert factors == {"transcribing": 1.2}
    assert estimates == {"transcribing": 120.0}
