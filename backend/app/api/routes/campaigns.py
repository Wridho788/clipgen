"""Campaigns: versioned CRUD plus the legacy hardcoded brief presets."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import (
    CampaignBrief,
    CampaignConfigurationResponse,
    CampaignCreateRequest,
    CampaignDetailResponse,
    CampaignDuplicateRequest,
    CampaignImportAnalyzeRequest,
    CampaignImportDraft,
    CampaignSummaryResponse,
    CampaignUpdateRequest,
)
from app.services import campaigns as campaign_service
from app.services.campaign_briefs import get_campaign_preset, list_campaign_presets
from app.services.campaign_import import CampaignImportError, analyze_campaign_text

router = APIRouter()


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, campaign_service.CampaignNotFound):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


# Declared before ``/{campaign_id}`` so "presets" is never read as an id.
@router.get("/presets", response_model=list[CampaignBrief])
async def campaign_presets():
    return list_campaign_presets()


@router.get("/presets/{preset_id}", response_model=CampaignBrief)
async def campaign_preset(preset_id: str):
    preset = get_campaign_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Campaign preset tidak ditemukan")
    return preset


@router.get("", response_model=list[CampaignSummaryResponse])
def list_campaigns(
    include_archived: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaigns = campaign_service.list_campaigns(db, current_user.id, include_archived)
    return [campaign_service.to_summary_response(db, campaign) for campaign in campaigns]


@router.post("", response_model=CampaignDetailResponse, status_code=201)
def create_campaign(
    data: CampaignCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    campaign = campaign_service.create_campaign(
        db,
        owner_id=current_user.id,
        name=data.name,
        campaign_type=data.type,
        source=data.source,
        config=data.config,
        source_name=data.source_name,
        source_url=data.source_url,
        raw_source_text=data.raw_source_text,
        confirmed=data.confirmed,
    )
    return campaign_service.to_detail_response(db, campaign)


@router.post("/analyze", response_model=CampaignImportDraft)
def analyze_campaign(
    data: CampaignImportAnalyzeRequest,
    current_user: User = Depends(get_current_user),
):
    """Parse pasted campaign text into a reviewable draft; nothing is saved."""
    try:
        return analyze_campaign_text(data.text)
    except CampaignImportError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        campaign = campaign_service.get_campaign(db, campaign_id, current_user.id)
    except campaign_service.CampaignNotFound as error:
        raise _http_error(error) from error
    return campaign_service.to_detail_response(db, campaign)


@router.put("/{campaign_id}", response_model=CampaignDetailResponse)
def update_campaign(
    campaign_id: str,
    data: CampaignUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save an edit as a new configuration version; old versions are kept."""
    try:
        campaign_service.add_configuration_version(
            db,
            campaign_id,
            current_user.id,
            data.config,
            name=data.name,
            source_name=data.source_name,
            source_url=data.source_url,
            raw_source_text=data.raw_source_text,
            confirmed=data.confirmed,
        )
        campaign = campaign_service.get_campaign(db, campaign_id, current_user.id)
    except (campaign_service.CampaignNotFound, campaign_service.CampaignArchived) as error:
        raise _http_error(error) from error
    return campaign_service.to_detail_response(db, campaign)


@router.get("/{campaign_id}/versions", response_model=list[CampaignConfigurationResponse])
def list_versions(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        configurations = campaign_service.list_configurations(db, campaign_id, current_user.id)
    except campaign_service.CampaignNotFound as error:
        raise _http_error(error) from error
    return [campaign_service.to_configuration_response(item) for item in configurations]


@router.get("/{campaign_id}/versions/{version}", response_model=CampaignConfigurationResponse)
def get_version(
    campaign_id: str,
    version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        configuration = campaign_service.get_configuration(db, campaign_id, current_user.id, version)
    except campaign_service.CampaignNotFound as error:
        raise _http_error(error) from error
    return campaign_service.to_configuration_response(configuration)


@router.post("/{campaign_id}/duplicate", response_model=CampaignDetailResponse, status_code=201)
def duplicate_campaign(
    campaign_id: str,
    data: CampaignDuplicateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        copy = campaign_service.duplicate_campaign(
            db, campaign_id, current_user.id, data.name if data else None
        )
    except campaign_service.CampaignNotFound as error:
        raise _http_error(error) from error
    return campaign_service.to_detail_response(db, copy)


@router.post("/{campaign_id}/archive", response_model=CampaignSummaryResponse)
def archive_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _set_archived(db, campaign_id, current_user, True)


@router.post("/{campaign_id}/unarchive", response_model=CampaignSummaryResponse)
def unarchive_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _set_archived(db, campaign_id, current_user, False)


def _set_archived(db: Session, campaign_id: str, current_user: User, archived: bool):
    try:
        campaign = campaign_service.set_archived(db, campaign_id, current_user.id, archived)
    except campaign_service.CampaignNotFound as error:
        raise _http_error(error) from error
    return campaign_service.to_summary_response(db, campaign)
