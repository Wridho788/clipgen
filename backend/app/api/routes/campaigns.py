"""Campaign brief presets and lightweight compliance helpers."""

from fastapi import APIRouter, HTTPException

from app.schemas import CampaignBrief
from app.services.campaign_briefs import get_campaign_preset, list_campaign_presets

router = APIRouter()


@router.get("/presets", response_model=list[CampaignBrief])
async def campaign_presets():
    return list_campaign_presets()


@router.get("/presets/{preset_id}", response_model=CampaignBrief)
async def campaign_preset(preset_id: str):
    preset = get_campaign_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Campaign preset tidak ditemukan")
    return preset
