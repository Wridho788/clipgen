"""Deterministic analysis of pasted campaign text (no LLM, no network).

The importer only reports what the text says. Anything it cannot support with a
quoted ``evidence`` snippet stays ``not_provided``; ambiguous or conflicting
statements become ``needs_review`` and are listed in ``unresolved_items``.
Pasted text is treated purely as data: nothing in it can change what is
extracted beyond the patterns below.
"""
import re
from datetime import date

from app.schemas import CampaignImportDraft, ExtractedField

MAX_IMPORT_CHARS = 20_000
# Matches ``CampaignBrief.min/max_clip_seconds`` (le=120): longer requests are
# kept in the draft but flagged, never clamped silently.
MAX_SUPPORTED_CLIP_SECONDS = 120.0


class CampaignImportError(ValueError):
    """The pasted text cannot be analysed (for example, it is blank)."""


_NUMBER = r"(\d+(?:[.,]\d+)?)"
_UNIT = r"(detik|dtk|seconds?|secs?|s|menit|mnt|minutes?|min)\b"
_RANGE = re.compile(
    rf"{_NUMBER}\s*(?:{_UNIT})?\s*(?:-|–|—|sampai|hingga|s/d|to|and|dan)\s*{_NUMBER}\s*{_UNIT}",
    re.I,
)
_MIN = re.compile(
    rf"(?:minimal|minimum|min\.?|paling\s+singkat|at\s+least)\s*:?\s*{_NUMBER}\s*{_UNIT}", re.I
)
_MAX = re.compile(
    rf"(?:maksimal|maksimum|maximum|maks\.?|max\.?|paling\s+lama|at\s+most|tidak\s+lebih\s+dari)"
    rf"\s*:?\s*{_NUMBER}\s*{_UNIT}",
    re.I,
)
_HASHTAG = re.compile(r"(?<![\w/&])#([^\W\d_][\w]*)")
_MENTION = re.compile(r"(?<![\w.@])@([\w.]*\w)")
_URL = re.compile(r"https?://[^\s<>\"']+", re.I)
_PLATFORM_PATTERNS = (
    ("tiktok", re.compile(r"\btik\s?tok\b", re.I)),
    ("instagram_reels", re.compile(r"\b(?:instagram|ig)\s+reels?\b|\breels?\b", re.I)),
    ("youtube", re.compile(r"\byoutube(?:\s+shorts)?\b|\byt\s+shorts\b|\bshorts\b", re.I)),
    ("facebook", re.compile(r"\bfacebook\b|\bfb\b", re.I)),
)
_PLAIN_INSTAGRAM = re.compile(r"\b(?:instagram|ig)\b", re.I)
_PROHIBIT_LIST = re.compile(
    r"(?:dilarang(?:\s+(?:menyebut(?:kan)?|memakai|menggunakan))?|prohibited(?:\s+(?:terms|words))?"
    r"|forbidden(?:\s+words)?|hindari(?:\s+kata)?|avoid(?:\s+(?:words|terms))?|kata\s+terlarang"
    r"|tidak\s+boleh\s+menyebut)\s*:\s*(.+)",
    re.I,
)
_PROHIBIT_FREE = re.compile(
    r"\b(?:jangan|dilarang|tidak\s+boleh|prohibited|do\s+not|don't|avoid|hindari)\b", re.I
)
_TERM_SPLIT = re.compile(r"\s*[,;/]\s*|\s+(?:dan|and)\s+", re.I)
_CTA = re.compile(r"^\s*(?:cta|call\s+to\s+action)\s*:\s*(.+?)\s*$", re.I)
_MONTHS = {
    "januari": 1, "january": 1, "jan": 1,
    "februari": 2, "february": 2, "feb": 2,
    "maret": 3, "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "mei": 5, "may": 5,
    "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7,
    "agustus": 8, "august": 8, "agu": 8, "agt": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "oktober": 10, "october": 10, "okt": 10, "oct": 10,
    "november": 11, "nov": 11, "nop": 11,
    "desember": 12, "december": 12, "des": 12, "dec": 12,
}
_MONTH_NAMES = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_DMY = re.compile(rf"\b(\d{{1,2}})\s+({_MONTH_NAMES})\.?\s+(\d{{4}})\b", re.I)
_DATE_MDY = re.compile(rf"\b({_MONTH_NAMES})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.I)
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_SLASH = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_FIELD_NAMES = (
    "min_clip_seconds", "max_clip_seconds", "hashtags", "mentions", "platforms",
    "source_urls", "prohibited_terms", "cta", "dates",
)
_DURATION_LABELS = {"min_clip_seconds": "minimum", "max_clip_seconds": "maksimum"}


def analyze_campaign_text(text: str) -> CampaignImportDraft:
    if not text or not text.strip():
        raise CampaignImportError("Teks campaign kosong")

    draft = CampaignImportDraft(
        raw_source_text=text, fields={name: ExtractedField() for name in _FIELD_NAMES}
    )
    if len(text) > MAX_IMPORT_CHARS:
        draft.raw_source_text = text[:MAX_IMPORT_CHARS]
        draft.truncated = True
        draft.warnings.append(
            f"Teks dipotong menjadi {MAX_IMPORT_CHARS:,} karakter pertama; bagian sisanya tidak dianalisis."
        )

    _extract_duration(draft)
    _extract_tags(draft)
    _extract_platforms(draft)
    _extract_urls(draft)
    _extract_prohibitions(draft)
    _extract_cta(draft)
    _extract_dates(draft)
    return draft


_MINUTE_UNITS = {"menit", "mnt", "minute", "minutes", "min"}


def _to_seconds(number: str, unit: str) -> float:
    value = float(number.replace(",", "."))
    return value * 60 if unit.lower() in _MINUTE_UNITS else value


def _extract_duration(draft: CampaignImportDraft) -> None:
    text = draft.raw_source_text
    # (min seconds | None, max seconds | None, quoted snippet)
    statements: list[tuple[float | None, float | None, str]] = []
    for match in _RANGE.finditer(text):
        unit = match.group(4)
        first_unit = match.group(2) or unit
        statements.append(
            (_to_seconds(match.group(1), first_unit), _to_seconds(match.group(3), unit), match.group(0))
        )
    for match in _MIN.finditer(text):
        statements.append((_to_seconds(match.group(1), match.group(2)), None, match.group(0)))
    for match in _MAX.finditer(text):
        statements.append((None, _to_seconds(match.group(1), match.group(2)), match.group(0)))

    for index, name in enumerate(_DURATION_LABELS):
        label = _DURATION_LABELS[name]
        claims = [(item[index], item[2]) for item in statements if item[index] is not None]
        draft.fields[name] = _resolve_bound(draft, label, claims)


def _resolve_bound(draft: CampaignImportDraft, label: str, claims: list[tuple[float, str]]) -> ExtractedField:
    if not claims:
        return ExtractedField()
    evidence = list(dict.fromkeys(snippet for _, snippet in claims))
    values = sorted({value for value, _ in claims})
    if len(values) > 1:
        shown = " vs ".join(f"{value:g}" for value in values)
        draft.unresolved_items.append(f"Durasi {label} bertentangan di teks ({shown} detik); pilih satu nilai.")
        return ExtractedField(status="needs_review", evidence=evidence, note="Pernyataan durasi bertentangan")
    value = values[0]
    if value > MAX_SUPPORTED_CLIP_SECONDS:
        note = f"Melebihi batas {MAX_SUPPORTED_CLIP_SECONDS:g} detik yang didukung ClipGen"
        draft.unresolved_items.append(f"Durasi {label} {value:g} detik: {note.lower()}.")
        return ExtractedField(status="needs_review", value=value, evidence=evidence, note=note)
    return ExtractedField(status="found", value=value, evidence=evidence)


def _list_field(values: list[str], evidence: list[str]) -> ExtractedField:
    if not values:
        return ExtractedField()
    return ExtractedField(status="found", value=values, evidence=evidence)


def _unique_ci(items: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for item in items:
        seen.setdefault(item.lower(), item)
    return list(seen.values())


def _extract_tags(draft: CampaignImportDraft) -> None:
    hashtags = _unique_ci([match.group(1) for match in _HASHTAG.finditer(draft.raw_source_text)])
    draft.fields["hashtags"] = _list_field(hashtags, [f"#{tag}" for tag in hashtags])
    mentions = _unique_ci([f"@{match.group(1)}" for match in _MENTION.finditer(draft.raw_source_text)])
    draft.fields["mentions"] = _list_field(mentions, list(mentions))


def _extract_platforms(draft: CampaignImportDraft) -> None:
    text = draft.raw_source_text
    hits: list[tuple[int, str, str]] = []  # (position, platform, quoted text)
    for platform, pattern in _PLATFORM_PATTERNS:
        match = pattern.search(text)
        if match:
            hits.append((match.start(), platform, match.group(0)))
    needs_review = False
    if not any(platform == "instagram_reels" for _, platform, _ in hits):
        plain = _PLAIN_INSTAGRAM.search(text)
        if plain:
            hits.append((plain.start(), "instagram_reels", plain.group(0)))
            needs_review = True
    if not hits:
        draft.fields["platforms"] = ExtractedField()
        return
    hits.sort()
    field = _list_field([platform for _, platform, _ in hits], [quoted for _, _, quoted in hits])
    if needs_review:
        field.status = "needs_review"
        field.note = "Teks hanya menyebut Instagram; ClipGen hanya mendukung Reels, pastikan itu benar"
        draft.unresolved_items.append("Platform Instagram disebut tanpa 'Reels'; konfirmasi formatnya.")
    draft.fields["platforms"] = field


def _extract_urls(draft: CampaignImportDraft) -> None:
    urls = _unique_ci([match.group(0).rstrip(".,;:!?)]}") for match in _URL.finditer(draft.raw_source_text)])
    draft.fields["source_urls"] = _list_field(urls, list(urls))


def _extract_prohibitions(draft: CampaignImportDraft) -> None:
    listed_lines: list[str] = []
    terms: list[str] = []
    free_lines: list[str] = []
    for raw_line in draft.raw_source_text.splitlines():
        line = raw_line.strip()
        listed = _PROHIBIT_LIST.search(line)
        if listed:
            parts = [part.strip(" .") for part in _TERM_SPLIT.split(listed.group(1))]
            terms.extend(part for part in parts if part)
            listed_lines.append(line)
        elif line and _PROHIBIT_FREE.search(line):
            free_lines.append(line)
    for line in free_lines:
        draft.unresolved_items.append(f"Larangan belum terstruktur, periksa manual: {line}")
    if terms:
        draft.fields["prohibited_terms"] = _list_field(_unique_ci(terms), listed_lines)
    elif free_lines:
        draft.fields["prohibited_terms"] = ExtractedField(
            status="needs_review",
            evidence=free_lines,
            note="Ada larangan di teks tetapi tanpa daftar kata yang jelas",
        )


def _extract_cta(draft: CampaignImportDraft) -> None:
    lines = []
    for raw_line in draft.raw_source_text.splitlines():
        if _CTA.match(raw_line):
            lines.append(raw_line.strip())
    values = _unique_ci([_CTA.match(line).group(1) for line in lines])
    if len(values) == 1:
        draft.fields["cta"] = ExtractedField(status="found", value=values[0], evidence=lines)
    elif values:
        draft.fields["cta"] = ExtractedField(
            status="needs_review", evidence=lines, note="Lebih dari satu CTA berbeda di teks"
        )
        draft.unresolved_items.append("Ada lebih dari satu CTA berbeda; pilih satu.")


def _valid_iso(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _extract_dates(draft: CampaignImportDraft) -> None:
    text = draft.raw_source_text
    found: list[tuple[int, str, str, bool]] = []  # (position, iso, quoted text, ambiguous)
    for match in _DATE_DMY.finditer(text):
        iso = _valid_iso(int(match.group(3)), _MONTHS[match.group(2).lower()], int(match.group(1)))
        if iso:
            found.append((match.start(), iso, match.group(0), False))
    for match in _DATE_MDY.finditer(text):
        iso = _valid_iso(int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2)))
        if iso:
            found.append((match.start(), iso, match.group(0), False))
    for match in _DATE_ISO.finditer(text):
        iso = _valid_iso(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.append((match.start(), iso, match.group(0), False))
    for match in _DATE_SLASH.finditer(text):
        first, second, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        # Day-first is assumed for Indonesian text; it is only trusted when the
        # numbers cannot be read the other way round.
        ambiguous = first <= 12 and second <= 12 and first != second
        day, month = (second, first) if first <= 12 < second else (first, second)
        iso = _valid_iso(year, month, day)
        if iso:
            found.append((match.start(), iso, match.group(0), ambiguous))
    if not found:
        return
    found.sort()
    ambiguous_snippets = [quoted for _, _, quoted, ambiguous in found if ambiguous]
    field = _list_field(
        list(dict.fromkeys(iso for _, iso, _, _ in found)),
        list(dict.fromkeys(quoted for _, _, quoted, _ in found)),
    )
    if ambiguous_snippets:
        field.status = "needs_review"
        field.note = "Tanggal numerik bisa dibaca hari/bulan atau bulan/hari; diasumsikan hari/bulan"
        draft.unresolved_items.append(
            f"Tanggal ambigu ({', '.join(ambiguous_snippets)}); konfirmasi hari dan bulannya."
        )
    draft.fields["dates"] = field
