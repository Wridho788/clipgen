from sqlalchemy import create_engine, inspect, text

from app.database import MIGRATIONS, SCHEMA_VERSION, current_schema_version, run_migrations

LEGACY_SCHEMA = [
    # Tables as created by v1.0.0 (commit e36ea1c) before any upgrade column.
    "CREATE TABLE users (id VARCHAR PRIMARY KEY, username VARCHAR NOT NULL, display_name VARCHAR NOT NULL,"
    " password_hash VARCHAR, created_at DATETIME, updated_at DATETIME)",
    "CREATE TABLE jobs (id VARCHAR PRIMARY KEY, source_type VARCHAR NOT NULL, source_path VARCHAR NOT NULL,"
    " status VARCHAR NOT NULL, progress INTEGER NOT NULL, error_message TEXT, transcript_json TEXT,"
    " created_at DATETIME, updated_at DATETIME)",
    "CREATE TABLE clips (id VARCHAR PRIMARY KEY, job_id VARCHAR NOT NULL, start_time FLOAT NOT NULL,"
    " end_time FLOAT NOT NULL, highlight_score FLOAT NOT NULL, file_path VARCHAR, title VARCHAR,"
    " caption TEXT, hashtags TEXT, status VARCHAR NOT NULL, created_at DATETIME)",
]


def _legacy_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        for statement in LEGACY_SCHEMA:
            connection.execute(text(statement))
        connection.execute(text(
            "INSERT INTO jobs (id, source_type, source_path, status, progress, created_at)"
            " VALUES ('j1', 'upload', '/x.mp4', 'done', 100, '2026-01-01')"
        ))
        for index, created in enumerate(("2026-01-01 00:00:02", "2026-01-01 00:00:01")):
            connection.execute(text(
                "INSERT INTO clips (id, job_id, start_time, end_time, highlight_score, file_path, status, created_at)"
                f" VALUES ('c{index}', 'j1', {index * 30}.5, {index * 30 + 20}.25, 0, '/clip{index}.mp4', 'ready', '{created}')"
            ))
    return engine


def test_migrations_upgrade_legacy_database_and_preserve_data(tmp_path):
    engine = _legacy_engine(tmp_path)
    assert current_schema_version(engine) == 0

    applied = run_migrations(engine)

    assert applied == [version for version, _, _ in MIGRATIONS]
    assert current_schema_version(engine) == SCHEMA_VERSION
    clip_columns = {column["name"] for column in inspect(engine).get_columns("clips")}
    assert {"edit_json", "edit_revision", "review_status", "suggested_start_time", "position"} <= clip_columns
    job_columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    assert {"error_code", "stage_metrics_json", "owner_id"} <= job_columns

    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT id, start_time, suggested_start_time, suggested_end_time, review_status,"
            " edit_revision, rendered_revision, position, algorithm_version FROM clips ORDER BY id"
        )).fetchall()
    assert rows[0] == ("c0", 0.5, 0.5, 20.25, "suggested", 0, 0, 2, "even-spacing-v1")
    # Positions follow creation order (c1 was created first).
    assert rows[1][7] == 1


def test_migrations_are_idempotent(tmp_path):
    engine = _legacy_engine(tmp_path)
    run_migrations(engine)
    assert run_migrations(engine) == []
    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar()
    assert count == len(MIGRATIONS)


def test_migrations_on_fresh_create_all_schema(tmp_path):
    from app.models import Base

    engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    Base.metadata.create_all(engine)
    assert run_migrations(engine) == [version for version, _, _ in MIGRATIONS]
    assert current_schema_version(engine) == SCHEMA_VERSION


def test_unknown_columns_are_not_dropped(tmp_path):
    engine = _legacy_engine(tmp_path)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE clips ADD COLUMN future_field TEXT"))
        connection.execute(text("UPDATE clips SET future_field = 'keep me'"))
    run_migrations(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT DISTINCT future_field FROM clips")).scalar() == "keep me"


def test_campaign_migration_adds_tables_job_columns_and_presets(tmp_path):
    engine = _legacy_engine(tmp_path)
    run_migrations(engine)

    assert {"campaigns", "campaign_configurations"} <= set(inspect(engine).get_table_names())
    job_columns = {column["name"] for column in inspect(engine).get_columns("jobs")}
    assert {"campaign_id", "campaign_configuration_version"} <= job_columns
    with engine.connect() as connection:
        # Legacy jobs stay unlinked; their brief (if any) remains in processing_options.
        assert connection.execute(text("SELECT campaign_id FROM jobs WHERE id = 'j1'")).scalar() is None
        presets = connection.execute(text("SELECT id, owner_id, type, status FROM campaigns ORDER BY id")).fetchall()
        versions = connection.execute(text("SELECT COUNT(*) FROM campaign_configurations")).scalar()
    assert presets == [
        ("preset-rumah_ningrat", None, "custom", "active"),
        ("preset-yava_happy_health", None, "custom", "active"),
    ]
    assert versions == 2
