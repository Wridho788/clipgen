import {
  CampaignBrief,
  CampaignConfigData,
  CampaignImportDraft,
  CampaignPlatform,
  ExtractedField,
  ExtractedFieldStatus,
} from "@/types/api";

/** Same limits as `CampaignBrief.min/max_clip_seconds` on the backend. */
export const MIN_ALLOWED_SECONDS = 5;
export const MAX_ALLOWED_SECONDS = 120;
export const IMPORT_TEXT_LIMIT = 20_000;

export const PLATFORM_OPTIONS: { value: CampaignPlatform; label: string }[] = [
  { value: "tiktok", label: "TikTok" },
  { value: "instagram_reels", label: "Instagram Reels" },
  { value: "youtube", label: "YouTube Shorts" },
  { value: "facebook", label: "Facebook" },
];

export const DEFAULT_RULES: CampaignBrief = {
  id: "custom",
  name: "Custom campaign",
  description: "",
  platforms: [],
  min_clip_seconds: 15,
  max_clip_seconds: 60,
  hook_required: true,
  hook_max_seconds: 3,
  preferred_hook_types: [],
  required_visuals: [],
  required_phrases: [],
  prohibited_terms: [],
  hashtags: [],
  mentions: [],
  cta: null,
  title_style: "curiosity_truthful",
  source_only: true,
  organic_only: false,
  avoid_misleading_edits: true,
  positive_brand_tone: false,
  allow_voiceover: false,
  retention_lock: false,
};

/** Rows of the review form that the importer can fill; used for badges and acknowledgement. */
export type ReviewRowId = "duration" | "platforms" | "hashtags" | "mentions" | "prohibited_terms" | "cta";

export interface ReviewRowMeta {
  status: ExtractedFieldStatus;
  evidence: string[];
  notes: string[];
}

/** Form values stay strings so people can type freely; they are validated on save. */
export interface CampaignFormState {
  name: string;
  objective: string;
  brief: string;
  targetAudience: string;
  platforms: CampaignPlatform[];
  minSeconds: string;
  maxSeconds: string;
  hashtags: string;
  mentions: string;
  requiredPhrases: string;
  prohibitedTerms: string;
  cta: string;
  softPreferences: string;
  rewardDetails: string;
}

export type CampaignFormErrors = Partial<Record<"name" | "duration", string>>;

export function emptyForm(): CampaignFormState {
  return {
    name: "",
    objective: "",
    brief: "",
    targetAudience: "",
    platforms: [],
    minSeconds: String(DEFAULT_RULES.min_clip_seconds),
    maxSeconds: String(DEFAULT_RULES.max_clip_seconds),
    hashtags: "",
    mentions: "",
    requiredPhrases: "",
    prohibitedTerms: "",
    cta: "",
    softPreferences: "",
    rewardDetails: "",
  };
}

/** Splits comma/semicolon/newline separated text, trimming and de-duplicating case-insensitively. */
export function splitList(text: string): string[] {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const raw of text.split(/[\n,;]+/)) {
    const item = raw.trim();
    if (!item || seen.has(item.toLowerCase())) continue;
    seen.add(item.toLowerCase());
    items.push(item);
  }
  return items;
}

function splitLines(text: string): string[] {
  return text.split("\n").map((line) => line.trim()).filter(Boolean);
}

function fieldNumber(field: ExtractedField | undefined): string | null {
  return typeof field?.value === "number" ? String(field.value) : null;
}

function fieldList(field: ExtractedField | undefined): string[] {
  return Array.isArray(field?.value) ? field.value : [];
}

/** First non-empty line, shortened to the backend's 120 character name limit. */
export function suggestCampaignName(rawText: string): string {
  const firstLine = rawText.split("\n").map((line) => line.trim()).find(Boolean) ?? "";
  return firstLine.replace(/^(campaign|nama campaign)\s*:\s*/i, "").slice(0, 120);
}

/**
 * Pre-fills the review form from an analysed draft. Only values the importer
 * actually extracted are used; conflicting fields (value `null`) stay at the
 * form default so the user has to choose.
 */
export function formFromDraft(draft: CampaignImportDraft): CampaignFormState {
  const form = emptyForm();
  const { fields } = draft;
  form.name = suggestCampaignName(draft.raw_source_text);
  form.minSeconds = fieldNumber(fields.min_clip_seconds) ?? form.minSeconds;
  form.maxSeconds = fieldNumber(fields.max_clip_seconds) ?? form.maxSeconds;
  form.platforms = fieldList(fields.platforms) as CampaignPlatform[];
  form.hashtags = fieldList(fields.hashtags).join(", ");
  form.mentions = fieldList(fields.mentions).join(", ");
  form.prohibitedTerms = fieldList(fields.prohibited_terms).join(", ");
  form.cta = typeof fields.cta.value === "string" ? fields.cta.value : "";
  return form;
}

export function formFromConfig(name: string, config: CampaignConfigData): CampaignFormState {
  const { rules } = config;
  return {
    name,
    objective: config.objective,
    brief: config.brief,
    targetAudience: config.target_audience,
    platforms: config.platforms.length > 0 ? config.platforms : rules.platforms,
    minSeconds: String(rules.min_clip_seconds),
    maxSeconds: String(rules.max_clip_seconds),
    hashtags: rules.hashtags.join(", "),
    mentions: rules.mentions.join(", "),
    requiredPhrases: rules.required_phrases.join(", "),
    prohibitedTerms: rules.prohibited_terms.join(", "),
    cta: rules.cta ?? "",
    softPreferences: config.soft_preferences.join("\n"),
    rewardDetails: config.reward_details ?? "",
  };
}

export function validateForm(form: CampaignFormState): CampaignFormErrors {
  const errors: CampaignFormErrors = {};
  if (!form.name.trim()) errors.name = "Nama campaign wajib diisi.";
  else if (form.name.trim().length > 120) errors.name = "Nama campaign maksimal 120 karakter.";

  const min = Number(form.minSeconds);
  const max = Number(form.maxSeconds);
  if (form.minSeconds.trim() === "" || form.maxSeconds.trim() === "" || Number.isNaN(min) || Number.isNaN(max)) {
    errors.duration = "Isi durasi minimum dan maksimum dalam detik.";
  } else if (min < MIN_ALLOWED_SECONDS || max > MAX_ALLOWED_SECONDS) {
    errors.duration = `Durasi harus antara ${MIN_ALLOWED_SECONDS} dan ${MAX_ALLOWED_SECONDS} detik (batas ClipGen).`;
  } else if (min > max) {
    errors.duration = "Durasi minimum tidak boleh lebih besar dari maksimum.";
  }
  return errors;
}

/**
 * Builds the config to save. `base` carries over rules the form does not
 * edit (hook, source_only, ...) so an edit never resets them to defaults.
 */
export function formToConfig(
  form: CampaignFormState,
  base?: CampaignConfigData,
  unresolvedItems: string[] = base?.unresolved_items ?? [],
): CampaignConfigData {
  const rules: CampaignBrief = {
    ...(base?.rules ?? DEFAULT_RULES),
    platforms: form.platforms,
    min_clip_seconds: Number(form.minSeconds),
    max_clip_seconds: Number(form.maxSeconds),
    hashtags: splitList(form.hashtags).map((tag) => tag.replace(/^#/, "")),
    mentions: splitList(form.mentions),
    required_phrases: splitList(form.requiredPhrases),
    prohibited_terms: splitList(form.prohibitedTerms),
    cta: form.cta.trim() || null,
  };
  return {
    schema_version: 1,
    objective: form.objective.trim(),
    brief: form.brief.trim(),
    target_audience: form.targetAudience.trim(),
    platforms: form.platforms,
    rules,
    soft_preferences: splitLines(form.softPreferences),
    reward_details: form.rewardDetails.trim() || null,
    unresolved_items: unresolvedItems,
  };
}

const STATUS_RANK: Record<ExtractedFieldStatus, number> = { found: 0, not_provided: 1, needs_review: 2 };

function combine(parts: (ExtractedField | undefined)[]): ReviewRowMeta {
  const present = parts.filter((part): part is ExtractedField => Boolean(part));
  const status = present.reduce<ExtractedFieldStatus>(
    (worst, part) => (STATUS_RANK[part.status] > STATUS_RANK[worst] ? part.status : worst),
    "not_provided",
  );
  // "found" on one bound and "not_provided" on the other is still a found row.
  const anyFound = present.some((part) => part.status === "found");
  const resolved: ExtractedFieldStatus = status === "needs_review" ? "needs_review" : anyFound ? "found" : "not_provided";
  return {
    status: resolved,
    evidence: Array.from(new Set(present.flatMap((part) => part.evidence))),
    notes: Array.from(new Set(present.map((part) => part.note).filter((note): note is string => Boolean(note)))),
  };
}

export function reviewRows(draft: CampaignImportDraft): Record<ReviewRowId, ReviewRowMeta> {
  const { fields } = draft;
  return {
    duration: combine([fields.min_clip_seconds, fields.max_clip_seconds]),
    platforms: combine([fields.platforms]),
    hashtags: combine([fields.hashtags]),
    mentions: combine([fields.mentions]),
    prohibited_terms: combine([fields.prohibited_terms]),
    cta: combine([fields.cta]),
  };
}

/** Rows the user must look at before saving: anything ambiguous or conflicting. */
export function rowsNeedingReview(rows: Record<ReviewRowId, ReviewRowMeta>): ReviewRowId[] {
  return (Object.keys(rows) as ReviewRowId[]).filter((id) => rows[id].status === "needs_review");
}
