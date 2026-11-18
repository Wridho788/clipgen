"""Built-in campaign brief presets for creator workflows."""

from app.schemas import CampaignBrief


CAMPAIGN_PRESETS: tuple[CampaignBrief, ...] = (
    CampaignBrief(
        id="yava_happy_health",
        name="YAVA Happy Health Podcast",
        description="Clipping podcast dengan hook cepat, product placement natural, dan CTA keranjang kuning.",
        platforms=["tiktok", "instagram_reels"],
        min_clip_seconds=60,
        max_clip_seconds=90,
        hook_required=True,
        hook_max_seconds=3,
        preferred_hook_types=["humor", "emosi", "kontroversial", "payoff"],
        required_visuals=["YA'Bar terlihat jelas dan natural"],
        cta="Klik keranjang kuning untuk mencoba YA'Bar.",
        hashtags=["YAVA", "HappyHealth", "YABar", "energiONterus", "GulaLontar", "enakDANsehat"],
        prohibited_terms=["diet", "gendut", "gemuk", "kurus", "bodyshaming"],
        title_style="brand_safe",
        source_only=True,
        organic_only=False,
        avoid_misleading_edits=True,
        positive_brand_tone=True,
        allow_voiceover=False,
        retention_lock=True,
    ),
    CampaignBrief(
        id="rumah_ningrat",
        name="Rumah Ningrat — Rumah di Luar Nalar",
        description="Klip organik yang menonjolkan visi founder tanpa memotong konteks secara menyesatkan.",
        platforms=["tiktok", "instagram_reels", "facebook"],
        min_clip_seconds=15,
        max_clip_seconds=120,
        hook_required=True,
        hook_max_seconds=3,
        preferred_hook_types=["menarik", "kontroversial", "lucu", "insight"],
        required_phrases=["Rumah di Luar Nalar"],
        mentions=[
            "@Ibnutrusmigroup",
            "@rumahningrat_official",
            "@rumahningratgold",
            "@ibnutrusmigroup_",
            "@rumahningratofficial",
        ],
        hashtags=["rumahningrat", "ibnutrusmigroup", "rumahsubidi", "untukhiduplebihbaik"],
        title_style="curiosity_truthful",
        source_only=True,
        organic_only=True,
        avoid_misleading_edits=True,
        positive_brand_tone=True,
        allow_voiceover=False,
        retention_lock=True,
    ),
)


def list_campaign_presets() -> list[dict[str, object]]:
    return [preset.model_dump() for preset in CAMPAIGN_PRESETS]


def get_campaign_preset(preset_id: str) -> CampaignBrief | None:
    return next((preset for preset in CAMPAIGN_PRESETS if preset.id == preset_id), None)
