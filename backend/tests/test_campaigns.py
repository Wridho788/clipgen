import json

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import run_migrations
from app.models import Base, Job, User
from app.schemas import CampaignBrief, CampaignConfigData
from app.services import campaigns as service
from app.services.campaign_briefs import CAMPAIGN_PRESETS

OWNER = "user-a"
OTHER = "user-b"


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'campaigns.db'}")
    Base.metadata.create_all(engine)
    run_migrations(engine)  # seeds the built-in presets
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _config(min_seconds=15, max_seconds=60, **overrides) -> CampaignConfigData:
    rules = CampaignBrief(min_clip_seconds=min_seconds, max_clip_seconds=max_seconds, hashtags=["#Promo"])
    return CampaignConfigData(objective="Naikkan awareness", rules=rules, **overrides)


def _create(db, owner=OWNER, name="Campaign A", **kwargs):
    return service.create_campaign(
        db,
        owner_id=owner,
        name=name,
        campaign_type="custom",
        source="user_created",
        config=kwargs.pop("config", _config()),
        **kwargs,
    )


def test_create_campaign_starts_at_version_one_unconfirmed(db):
    campaign = _create(db, raw_source_text="teks mentah")

    configuration = service.get_configuration(db, campaign.id, OWNER)
    assert configuration.version == 1
    assert configuration.raw_source_text == "teks mentah"
    assert configuration.user_confirmed_at is None
    assert service.to_summary_response(db, campaign).confirmed is False


def test_confirmed_flag_stamps_confirmation_time(db):
    campaign = _create(db, confirmed=True)

    assert service.get_configuration(db, campaign.id, OWNER).user_confirmed_at is not None


def test_edit_appends_new_version_and_keeps_old_one(db):
    campaign = _create(db)

    new_version = service.add_configuration_version(
        db, campaign.id, OWNER, _config(30, 90), name="Campaign A v2"
    )

    assert new_version.version == 2
    versions = service.list_configurations(db, campaign.id, OWNER)
    assert [item.version for item in versions] == [1, 2]
    old = CampaignConfigData.model_validate_json(versions[0].config_json)
    assert (old.rules.min_clip_seconds, old.rules.max_clip_seconds) == (15, 60)
    assert service.get_campaign(db, campaign.id, OWNER).name == "Campaign A v2"


def test_job_brief_is_pinned_so_later_edits_do_not_change_it(db):
    campaign = _create(db)
    brief, version = service.resolve_job_brief(db, campaign.id, OWNER)
    assert version == 1
    assert brief.id == campaign.id
    assert brief.name == "Campaign A"

    service.add_configuration_version(db, campaign.id, OWNER, _config(30, 90))

    pinned_brief, pinned_version = service.resolve_job_brief(db, campaign.id, OWNER, version=1)
    latest_brief, latest_version = service.resolve_job_brief(db, campaign.id, OWNER)
    assert (pinned_version, pinned_brief.max_clip_seconds) == (1, 60)
    assert (latest_version, latest_brief.max_clip_seconds) == (2, 90)
    # The snapshot a job already stored is a plain value, untouched by the edit.
    assert brief.max_clip_seconds == 60


def test_campaign_platforms_override_rule_platforms_in_snapshot(db):
    campaign = _create(db, config=_config(platforms=["youtube"]))

    brief, _ = service.resolve_job_brief(db, campaign.id, OWNER)

    assert brief.platforms == ["youtube"]


def test_unknown_version_is_not_found(db):
    campaign = _create(db)

    with pytest.raises(service.CampaignNotFound):
        service.get_configuration(db, campaign.id, OWNER, version=9)


def test_archived_campaign_cannot_start_jobs_or_be_edited(db):
    campaign = _create(db)
    service.set_archived(db, campaign.id, OWNER, True)

    with pytest.raises(service.CampaignArchived):
        service.resolve_job_brief(db, campaign.id, OWNER)
    with pytest.raises(service.CampaignArchived):
        service.add_configuration_version(db, campaign.id, OWNER, _config())
    assert campaign.id not in [item.id for item in service.list_campaigns(db, OWNER)]
    assert campaign.id in [item.id for item in service.list_campaigns(db, OWNER, include_archived=True)]

    service.set_archived(db, campaign.id, OWNER, False)
    assert service.resolve_job_brief(db, campaign.id, OWNER)[1] == 1


def test_duplicate_is_independent_copy_at_version_one(db):
    original = _create(db, raw_source_text="sumber", confirmed=True)
    service.add_configuration_version(
        db, original.id, OWNER, _config(30, 90), raw_source_text="sumber v2", confirmed=True
    )

    copy = service.duplicate_campaign(db, original.id, OWNER)

    assert copy.id != original.id
    assert copy.name == "Campaign A (salinan)"
    configuration = service.get_configuration(db, copy.id, OWNER)
    assert configuration.version == 1
    assert configuration.raw_source_text == "sumber v2"
    assert CampaignConfigData.model_validate_json(configuration.config_json).rules.max_clip_seconds == 90
    # Confirmation carries over: the copy holds rules the user already reviewed.
    assert service.to_summary_response(db, copy).confirmed is True
    service.add_configuration_version(db, copy.id, OWNER, _config(5, 10))
    assert service.get_configuration(db, original.id, OWNER).version == 2


def test_campaigns_are_scoped_to_their_owner(db):
    campaign = _create(db, owner=OWNER)

    with pytest.raises(service.CampaignNotFound):
        service.get_campaign(db, campaign.id, OTHER)
    assert campaign.id not in [item.id for item in service.list_campaigns(db, OTHER)]


def test_builtin_presets_are_seeded_once_and_visible_to_everyone(db):
    ids = {item.id for item in service.list_campaigns(db, OTHER)}
    expected = {service.preset_campaign_id(preset.id) for preset in CAMPAIGN_PRESETS}
    assert expected <= ids

    brief, version = service.resolve_job_brief(db, service.preset_campaign_id("yava_happy_health"), OTHER)
    assert version == 1
    assert brief.min_clip_seconds == 60 and "YAVA" in brief.hashtags

    # Re-seeding never overwrites or duplicates rows the user may have edited.
    service.add_configuration_version(
        db, service.preset_campaign_id("yava_happy_health"), OTHER, _config(20, 30), name="Diubah"
    )
    with db.get_bind().begin() as connection:
        service.seed_preset_campaigns(connection)
    db.expire_all()
    assert len([item for item in service.list_campaigns(db, OTHER) if item.id in expected]) == len(expected)
    assert service.get_campaign(db, service.preset_campaign_id("yava_happy_health"), OTHER).name == "Diubah"


def test_job_records_campaign_provenance(db):
    campaign = _create(db)
    db.add(User(id=OWNER, username="a", display_name="A"))
    job = Job(
        id="job-1",
        owner_id=OWNER,
        source_type="upload",
        source_path="/x.mp4",
        campaign_id=campaign.id,
        campaign_configuration_version=1,
    )
    db.add(job)
    db.commit()

    assert db.get(Job, "job-1").campaign_id == campaign.id
    assert db.get(Job, "job-1").campaign_configuration_version == 1


def test_resolve_campaign_link_without_campaign_passes_inline_brief_through(db):
    from app.api.routes.videos import _resolve_campaign_link

    user = User(id=OWNER, username="a", display_name="A")

    assert _resolve_campaign_link(db, user, None, None, '{"x":1}') == ('{"x":1}', None, None)
    assert _resolve_campaign_link(db, user, "  ", None, None) == (None, None, None)
    with pytest.raises(HTTPException) as error:
        _resolve_campaign_link(db, user, None, 2, None)
    assert error.value.status_code == 422


def test_resolve_campaign_link_pins_version_and_rejects_bad_requests(db):
    from app.api.routes.videos import _resolve_campaign_link

    user = User(id=OWNER, username="a", display_name="A")
    campaign = _create(db)

    brief_json, campaign_id, version = _resolve_campaign_link(db, user, f" {campaign.id} ", None, None)
    assert (campaign_id, version) == (campaign.id, 1)
    assert json.loads(brief_json)["id"] == campaign.id

    with pytest.raises(HTTPException) as both:
        _resolve_campaign_link(db, user, campaign.id, None, "{}")
    assert both.value.status_code == 422
    with pytest.raises(HTTPException) as missing:
        _resolve_campaign_link(db, user, "no-such-id", None, None)
    assert missing.value.status_code == 404
    with pytest.raises(HTTPException) as bad_version:
        _resolve_campaign_link(db, user, campaign.id, 7, None)
    assert bad_version.value.status_code == 404

    service.set_archived(db, campaign.id, OWNER, True)
    with pytest.raises(HTTPException) as archived:
        _resolve_campaign_link(db, user, campaign.id, None, None)
    assert archived.value.status_code == 409


def test_stored_brief_reads_the_snapshot_embedded_in_job_options():
    from app.api.routes.jobs import _stored_brief

    assert _stored_brief(Job(processing_options=None)) is None
    assert _stored_brief(Job(processing_options="not json")) is None
    assert _stored_brief(Job(processing_options=json.dumps({"campaign_brief": None}))) is None
    stored = Job(processing_options=json.dumps({"campaign_brief": {"id": "c1", "name": "C"}}))
    assert _stored_brief(stored) == CampaignBrief(id="c1", name="C").model_dump()
