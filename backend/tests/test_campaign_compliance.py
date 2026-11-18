from app.schemas import CampaignBrief
from app.services.campaign_compliance import evaluate_campaign_compliance


def test_campaign_compliance_blocks_prohibited_terms_and_missing_phrase():
    brief = CampaignBrief(
        id="rumah",
        name="Rumah",
        required_phrases=["Rumah di Luar Nalar"],
        prohibited_terms=["bodyshaming"],
        min_clip_seconds=15,
        max_clip_seconds=120,
    )
    result = evaluate_campaign_compliance(
        brief,
        transcript_text="Ini contoh bodyshaming yang tidak boleh.",
        title="Judul",
        caption="Caption",
        duration_seconds=30,
    )

    assert result["status"] == "blocked"
    assert any(check["key"] == "prohibited_terms" and check["status"] == "blocked" for check in result["checks"])
    assert any(check["key"] == "required_phrases" and check["status"] == "blocked" for check in result["checks"])


def test_campaign_compliance_marks_visual_review_without_blocking():
    brief = CampaignBrief(id="yava", name="YAVA", required_visuals=["YA'Bar terlihat"])
    result = evaluate_campaign_compliance(
        brief,
        transcript_text="Percakapan yang aman dan cukup panjang.",
        caption="Caption",
        hashtags=[],
        duration_seconds=30,
    )

    assert result["status"] == "review_required"
    assert any(check["key"] == "visuals" and check["status"] == "review_required" for check in result["checks"])
