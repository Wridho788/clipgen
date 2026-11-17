"""Campaign persistence with immutable, numbered configuration versions.

Editing a campaign never rewrites history: ``add_configuration_version`` appends
a new row. Jobs keep a snapshot of the brief they were created with (see
``resolve_job_brief``), so a later campaign edit cannot silently change the
rules an old job was evaluated against.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.models import Campaign, CampaignConfiguration
from app.schemas import (
    CampaignBrief,
    CampaignConfigData,
    CampaignConfigurationResponse,
    CampaignDetailResponse,
    CampaignSummaryResponse,
)
from app.services.campaign_briefs import CAMPAIGN_PRESETS

PRESET_SOURCE_NAME = "Preset bawaan"


class CampaignNotFound(LookupError):
    """Campaign or version does not exist (or is not visible to the user)."""


class CampaignArchived(RuntimeError):
    """Archived campaigns stay readable but cannot start new jobs or versions."""


def preset_campaign_id(preset_id: str) -> str:
    return f"preset-{preset_id}"


def _visible(query, owner_id: str | None):
    """Built-in presets (owner NULL) are visible to every user."""
    return query.filter(or_(Campaign.owner_id.is_(None), Campaign.owner_id == owner_id))


def get_campaign(db: Session, campaign_id: str, owner_id: str | None) -> Campaign:
    campaign = _visible(db.query(Campaign).filter(Campaign.id == campaign_id), owner_id).first()
    if campaign is None:
        raise CampaignNotFound("Campaign tidak ditemukan")
    return campaign


def list_campaigns(db: Session, owner_id: str | None, include_archived: bool = False) -> list[Campaign]:
    query = _visible(db.query(Campaign), owner_id)
    if not include_archived:
        query = query.filter(Campaign.status == "active")
    return query.order_by(Campaign.updated_at.desc(), Campaign.name.asc()).all()


def _latest_configuration(db: Session, campaign_id: str) -> CampaignConfiguration:
    configuration = (
        db.query(CampaignConfiguration)
        .filter(CampaignConfiguration.campaign_id == campaign_id)
        .order_by(CampaignConfiguration.version.desc())
        .first()
    )
    if configuration is None:
        raise CampaignNotFound("Campaign belum punya konfigurasi")
    return configuration


def get_configuration(
    db: Session, campaign_id: str, owner_id: str | None, version: int | None = None
) -> CampaignConfiguration:
    get_campaign(db, campaign_id, owner_id)
    if version is None:
        return _latest_configuration(db, campaign_id)
    configuration = (
        db.query(CampaignConfiguration)
        .filter(CampaignConfiguration.campaign_id == campaign_id, CampaignConfiguration.version == version)
        .first()
    )
    if configuration is None:
        raise CampaignNotFound(f"Versi {version} tidak ditemukan")
    return configuration


def list_configurations(db: Session, campaign_id: str, owner_id: str | None) -> list[CampaignConfiguration]:
    get_campaign(db, campaign_id, owner_id)
    return (
        db.query(CampaignConfiguration)
        .filter(CampaignConfiguration.campaign_id == campaign_id)
        .order_by(CampaignConfiguration.version.asc())
        .all()
    )


def _new_configuration(
    campaign_id: str,
    version: int,
    config: CampaignConfigData,
    raw_source_text: str | None,
    confirmed: bool,
) -> CampaignConfiguration:
    return CampaignConfiguration(
        id=str(uuid4()),
        campaign_id=campaign_id,
        version=version,
        config_json=config.model_dump_json(),
        raw_source_text=raw_source_text,
        user_confirmed_at=datetime.utcnow() if confirmed else None,
    )


def create_campaign(
    db: Session,
    *,
    owner_id: str | None,
    name: str,
    campaign_type: str,
    source: str,
    config: CampaignConfigData,
    source_name: str | None = None,
    source_url: str | None = None,
    raw_source_text: str | None = None,
    confirmed: bool = False,
) -> Campaign:
    campaign = Campaign(
        id=str(uuid4()),
        owner_id=owner_id,
        name=name.strip(),
        type=campaign_type,
        source=source,
        source_name=source_name,
        source_url=source_url,
        status="active",
    )
    db.add(campaign)
    db.flush()
    db.add(_new_configuration(campaign.id, 1, config, raw_source_text, confirmed))
    db.commit()
    db.refresh(campaign)
    return campaign


def add_configuration_version(
    db: Session,
    campaign_id: str,
    owner_id: str | None,
    config: CampaignConfigData,
    *,
    name: str | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    raw_source_text: str | None = None,
    confirmed: bool = False,
) -> CampaignConfiguration:
    """Append a new version; earlier versions are left untouched."""
    campaign = get_campaign(db, campaign_id, owner_id)
    if campaign.status == "archived":
        raise CampaignArchived("Campaign diarsipkan; aktifkan kembali sebelum mengubahnya")
    latest_version = (
        db.query(func.max(CampaignConfiguration.version))
        .filter(CampaignConfiguration.campaign_id == campaign_id)
        .scalar()
        or 0
    )
    configuration = _new_configuration(campaign_id, latest_version + 1, config, raw_source_text, confirmed)
    db.add(configuration)
    if name is not None:
        campaign.name = name.strip()
    if source_name is not None:
        campaign.source_name = source_name
    if source_url is not None:
        campaign.source_url = source_url
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(configuration)
    return configuration


def duplicate_campaign(
    db: Session, campaign_id: str, owner_id: str | None, name: str | None = None
) -> Campaign:
    """Copy the latest configuration into a new, independent campaign (version 1)."""
    source = get_campaign(db, campaign_id, owner_id)
    latest = _latest_configuration(db, campaign_id)
    copy = Campaign(
        id=str(uuid4()),
        owner_id=owner_id,
        name=(name or f"{source.name} (salinan)").strip(),
        type=source.type,
        source="user_created",
        source_name=source.source_name,
        source_url=source.source_url,
        status="active",
    )
    db.add(copy)
    db.flush()
    db.add(
        CampaignConfiguration(
            id=str(uuid4()),
            campaign_id=copy.id,
            version=1,
            config_json=latest.config_json,
            raw_source_text=latest.raw_source_text,
            user_confirmed_at=latest.user_confirmed_at,
        )
    )
    db.commit()
    db.refresh(copy)
    return copy


def set_archived(db: Session, campaign_id: str, owner_id: str | None, archived: bool) -> Campaign:
    campaign = get_campaign(db, campaign_id, owner_id)
    campaign.status = "archived" if archived else "active"
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    return campaign


def resolve_job_brief(
    db: Session, campaign_id: str, owner_id: str | None, version: int | None = None
) -> tuple[CampaignBrief, int]:
    """Pin a configuration version and return the brief snapshot for a new job.

    ``version=None`` pins the latest version at call time; the returned number is
    what the job must record so later edits cannot change it.
    """
    campaign = get_campaign(db, campaign_id, owner_id)
    if campaign.status == "archived":
        raise CampaignArchived("Campaign diarsipkan dan tidak bisa dipakai untuk job baru")
    configuration = get_configuration(db, campaign_id, owner_id, version)
    data = CampaignConfigData.model_validate_json(configuration.config_json)
    brief = data.rules.model_copy(
        update={
            "id": campaign.id,
            "name": campaign.name,
            "platforms": data.platforms or data.rules.platforms,
        }
    )
    return CampaignBrief.model_validate(brief.model_dump()), configuration.version


def to_configuration_response(configuration: CampaignConfiguration) -> CampaignConfigurationResponse:
    return CampaignConfigurationResponse(
        campaign_id=configuration.campaign_id,
        version=configuration.version,
        config=CampaignConfigData.model_validate_json(configuration.config_json),
        raw_source_text=configuration.raw_source_text,
        user_confirmed_at=configuration.user_confirmed_at,
        created_at=configuration.created_at,
    )


def to_summary_response(db: Session, campaign: Campaign) -> CampaignSummaryResponse:
    latest = _latest_configuration(db, campaign.id)
    return CampaignSummaryResponse(
        id=campaign.id,
        name=campaign.name,
        type=campaign.type,
        source=campaign.source,
        source_name=campaign.source_name,
        source_url=campaign.source_url,
        status=campaign.status,
        latest_version=latest.version,
        confirmed=latest.user_confirmed_at is not None,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


def to_detail_response(db: Session, campaign: Campaign) -> CampaignDetailResponse:
    latest = _latest_configuration(db, campaign.id)
    summary = to_summary_response(db, campaign)
    return CampaignDetailResponse(**summary.model_dump(), configuration=to_configuration_response(latest))


def seed_preset_campaigns(connection) -> None:
    """Insert the built-in presets as ``custom`` campaigns (idempotent).

    Runs inside migration 003 with a raw connection, so it uses plain SQL rather
    than the ORM session. Presets are ``user_created`` campaigns with no owner,
    stamped confirmed because they are the project's own curated rules; existing
    rows (even if the user archived or edited them) are never overwritten.
    """
    now = datetime.utcnow()
    for preset in CAMPAIGN_PRESETS:
        campaign_id = preset_campaign_id(preset.id)
        exists = connection.execute(
            text("SELECT 1 FROM campaigns WHERE id = :id"), {"id": campaign_id}
        ).first()
        if exists:
            continue
        config = CampaignConfigData(
            brief=preset.description,
            platforms=list(preset.platforms),
            rules=preset,
        )
        connection.execute(
            text(
                "INSERT INTO campaigns (id, owner_id, name, type, source, source_name, status, created_at, updated_at)"
                " VALUES (:id, NULL, :name, 'custom', 'user_created', :source_name, 'active', :now, :now)"
            ),
            {"id": campaign_id, "name": preset.name, "source_name": PRESET_SOURCE_NAME, "now": now},
        )
        connection.execute(
            text(
                "INSERT INTO campaign_configurations"
                " (id, campaign_id, version, config_json, raw_source_text, user_confirmed_at, created_at)"
                " VALUES (:id, :campaign_id, 1, :config_json, NULL, :now, :now)"
            ),
            {
                "id": str(uuid4()),
                "campaign_id": campaign_id,
                "config_json": config.model_dump_json(),
                "now": now,
            },
        )
