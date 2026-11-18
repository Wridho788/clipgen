# 11 --- Campaign Workflow: Analisa & TODO Pengerjaan

Turunan dari `clipgen-campaign-uiux-milestones.md`, sudah dicocokkan dengan
repository (branch `overhaul/local-first-editor`, commit `1f2ed13`,
2026-10-12). Status: `existing` / `partial` / `missing`.

## 1. Analisa singkat

Dokumen milestone menyebut dirinya "belum diaudit". Kenyataannya banyak
fondasi yang sudah ada dari overhaul (`08`–`10`). Gap utamanya ada di
**entitas Campaign, import copy-paste, versioning, dan ranking yang sadar
campaign**, bukan di editor atau export.

| Area | Status | Kondisi di repo |
|---|---|---|
| M0 Audit & baseline | `existing` | `08-repository-audit.md`, `09-baseline-report.md`, `10-implementation-notes.md`. Belum ada bagian khusus untuk campaign. |
| Campaign brief | `partial` | `CampaignBrief` (`backend/app/schemas.py:15`) berisi aturan datar tanpa pembagian hard/soft, tanpa `type`, `raw_source_text`, `objective`, `audience`, `reward_details`, atau `unresolved_items`. |
| Preset campaign | `partial` | 2 preset hardcoded dan **diduplikasi** di `backend/app/services/campaign_briefs.py` dan `frontend/src/lib/campaigns.ts`. |
| Import copy-paste + parsing | `missing` | Belum ada endpoint, parser, ataupun UI. |
| Persistensi campaign | `missing` | Belum ada tabel. Brief hanya ikut tersimpan di `jobs.processing_options`. |
| Snapshot per job | `partial` | Snapshot sudah ada secara implisit karena brief disalin ke job, tapi belum ada `campaign_id` atau nomor versi. |
| Pipeline campaign-aware | `partial` | Hanya min/max durasi brief yang mempersempit window (`job_service.py:338`). Ranking `transcript-boundary-v1` belum memakai brief/topik. |
| Compliance | `partial` | `campaign_compliance.py` deterministik: `pass` / `review_required` / `blocked`. Belum ada status `unknown`. API masih mengirim `score` dalam persen. |
| Editorial quality | `partial` | Ada signals + explanation + rank di `clips.analysis_json`, tapi belum ada relevansi terhadap campaign. |
| Generated Clips review | `partial` | `CandidateReview.tsx`, `ClipCard.tsx`, dan halaman job sudah ada. Belum ada pemisahan visual compliance vs editorial maupun rationale campaign. |
| Editor | `existing` (sebagian besar) | Trim, caption, framing 9:16, autosave, undo/redo, conflict 409. Belum ada: timeline multi-track, inspector campaign, rekomendasi AI preview/apply. |
| Export & validasi | `partial` | Validasi render + atomic publish sudah ada. Belum ada: gate compliance sebelum export, cek disk space, riwayat export. |
| Dashboard | `partial` | `page.tsx` berisi upload + daftar job. Belum ada campaign terakhir, riwayat export, maupun empty state onboarding. |
| Design tokens | `missing` | `tailwind.config.js` belum punya `extend`. Warna masih hardcoded (slate/violet) dan dark mode memakai class. |
| LLM lokal | `existing` | Ollama `gemma3:4b` opsional untuk metadata. Bisa dipakai ulang untuk parsing dengan validasi schema. |

### Konflik antara dokumen dan repo yang perlu diputuskan

1. **Data model.** Dokumen mengusulkan `SourceVideo`, `ClippingJob`,
   `ClipCandidate`, dan `ClipProject` sebagai entitas terpisah. Repo sudah
   memutuskan untuk *memperluas `jobs`/`clips`* (`08` §4). Usulan: hanya
   tambah `campaigns` + `campaign_configurations`. `ClippingJob` = `jobs`;
   `ClipCandidate`/`ClipProject` = `clips`.
2. **Status compliance.** Dokumen memakai `pass / fail / needs review /
   unknown`, sedangkan repo memakai `pass / review_required / blocked`.
   Usulan: tambah `unknown`, mapping UI `blocked` → "Gagal", dan biarkan
   nilai API tetap kompatibel.
3. **Batas schema.** `max_clip_seconds` dibatasi `le=120`. Campaign hasil
   import bisa minta durasi lebih panjang, jadi batas ini perlu ditinjau.
4. **Bahasa UI.** UI saat ini berbahasa Indonesia. Label di dokumen
   (`Found`, `Needs review`, ...) perlu diterjemahkan secara konsisten.

## 2. Keputusan sebelum mulai (blocker)

Status keputusan (2026-10-12): D3 dan D6 dijawab pemilik. D1, D2, D4, D5
dikerjakan memakai **usulan** di bawah (belum disetujui eksplisit; D1/D4/D5
sudah dipakai oleh M3 backend, ubah jika tidak setuju). D2 belum dipakai.

- [~] D1. Mapping data model (konflik #1): hanya tambah `campaigns` +
      `campaign_configurations`. *Usulan, dipakai M3.*
- [~] D2. Set status compliance: tambah `unknown`, UI memetakan `blocked` →
      "Gagal". *Usulan, belum dikerjakan (M4).*
- [x] D3. Parser MVP: **deterministik saja**. Ollama ditunda; tidak ada
      ekstraksi LLM di M2.
- [~] D4. Campaign diedit saat job berjalan: job tetap memakai versi yang
      dikunci saat dibuat. *Usulan, dipakai M3.*
- [~] D5. Preset hardcoded di-seed sebagai campaign `custom` lewat migrasi 003
      (`preset-<id>`); `campaigns.ts` dihapus saat UI M3. *Usulan, seed sudah ada.*
- [x] D6. Riwayat export: **tabel riwayat export** (bukan hanya export
      terakhir). Masuk ke M7 (migrasi `004`).

## 3. TODO per milestone

### M0 — Addendum audit (kecil)
- [x] Tambah bagian "Campaign scope" di `08-repository-audit.md` (§5).
- [ ] Kumpulkan 5–10 contoh teks campaign asli dari situs Clipper Campaign
      sebagai fixture (lengkap, minim, ambigu, kontradiktif, tidak terstruktur):
      `backend/tests/fixtures/campaigns/*.txt`.
- [ ] Jalankan baseline: pytest di container, ruff, lint, tsc, Playwright (lihat memory/test workflow).

### M1 — Product flow & UX foundation
- [ ] Tulis user flow final: Import → Review → Pilih Video → Generate → Review Klip → Edit → Validasi → Export.
- [x] Rancang navigasi/route baru (AppShell: rail kiri Proyek/Campaign):
      `/` (dashboard), `/campaigns`, `/campaigns/new` (import), `/campaigns/[id]`,
      `/jobs/[id]` (generated clips, sudah ada), editor (sudah ada di halaman job).
- [ ] Wireframe 5 layar: Dashboard, Import Campaign, Campaign Detail, Generated Clips, Clip Workspace.
- [x] Design tokens di `tailwind.config.js` + CSS variables di `globals.css` (lihat `12-design-system.md`)
      (`#111318`, `#20232B`, `#8B5CF6`, `#22D3EE`; font Inter/Geist). Migrasikan warna hardcoded secara bertahap.
- [ ] Inventaris komponen & state: loading, empty, success, partial, error untuk tiap layar.
- [~] Cek kontras (WCAG AA) dan focus state untuk token baru: dipilih berdasarkan rasio kontras dan focus ring 2px; audit otomatis belum.

### M2 — Import & normalisasi campaign (P0)
Backend
- [~] Schema baru `CampaignConfiguration` (Pydantic): ada sebagai `CampaignConfigData` (M3, `rules` = `CampaignBrief`); hasil impor memakai `CampaignImportDraft` + `ExtractedField` (status found/needs_review/not_provided + evidence). Pemisahan hard/soft di UI review belum. `objective`, `brief`,
      `target_audience`, `platforms`, `hard_constraints`, `soft_preferences`,
      `reward_details?`, `unresolved_items`, `raw_source_text`. Setiap field
      hasil ekstraksi punya `status`: `found` / `needs_review` / `not_provided`, plus `evidence` (kutipan teks sumber).
- [ ] Adapter: `CampaignConfiguration.hard_constraints` → `CampaignBrief`, supaya compliance/metadata yang ada tetap jalan.
- [x] `services/campaign_import.py`: parser deterministik (durasi, hashtag, mention, platform, URL, tanggal, kata terlarang, CTA).
- [-] ~~(Opsional, D3) Ekstraksi via Ollama~~ — ditunda (D3: deterministik saja). Field tidak pernah diisi tanpa evidence.
- [x] Deteksi konflik (durasi bertentangan, durasi > 120 detik, tanggal numerik ambigu, Instagram tanpa Reels, CTA ganda) → `unresolved_items`.
- [x] Batas input: teks kosong → 422, > 20.000 karakter → dipotong + peringatan, payload > 500.000 karakter → 422.
- [x] Instruksi di dalam teks tempelan tidak mengubah schema/perilaku (`test_instructions_inside_the_pasted_text_are_data_not_commands`).
- [x] Endpoint `POST /api/campaigns/analyze` (tanpa menyimpan, hanya mengembalikan draft).

Frontend
- [ ] Halaman Import: textarea besar, tombol "Analisa Campaign", state loading/error.
- [ ] Hasil dikelompokkan per topik dengan badge Ditemukan / Perlu review / Tidak ada; semua field bisa diedit.
- [ ] Hard constraint vs soft preference dipisah dan bisa dipindah oleh user.
- [ ] Tombol "Konfirmasi & Simpan" diblokir selama masih ada item `needs_review` yang penting dan belum dikonfirmasi.

Tes
- [~] Unit parser: sudah dengan teks sintetis (`tests/test_campaign_import.py`); fixture dari situs asli menunggu M0.
- [x] Tes "tidak menebak": semua field `not_provided` bila teks tidak menyebutnya.
- [ ] Playwright: tempel → analisa → edit → simpan → buka lagi.

### M3 — Persistensi & versioning (P0)
- [x] Migrasi `003`: tabel `campaigns` (`id`, `name`, `type` reward/custom,
      `source` manual_import/user_created, `source_name`, `source_url?`,
      `status`, timestamps) dan `campaign_configurations` (`campaign_id`,
      `version`, `config_json`, `raw_source_text`, `user_confirmed_at`, `created_at`). Konfigurasi bersifat immutable; edit = versi baru.
- [x] Migrasi: `jobs.campaign_id` + `jobs.campaign_configuration_version` (nullable, di migrasi 003). Job lama tetap memakai brief yang tertanam di `processing_options`.
- [~] Seed 2 preset lama sebagai campaign (D5): backend selesai (`preset-<id>`); hapus duplikasi frontend (`campaigns.ts`) menunggu UI.
- [x] API CRUD: list, get (+ versi), create, update (= versi baru), duplicate, archive/unarchive (`/api/campaigns`).
- [x] Pembuatan job (`/upload`, `/youtube`) menerima `campaign_id` (+ `campaign_configuration_version`) dan tetap menyimpan snapshot brief di job; retry mempertahankan link bila brief tidak diganti.
- [ ] (UI, belum) Halaman Campaign Detail: brief, hard/soft, reward/submission, teks mentah, field yang belum terverifikasi, versi, dan riwayat perubahan.
- [x] Tes backend: `test_campaigns.py`, `test_campaign_api.py`, `test_migrations.py` (versi baru saat edit, versi terkunci, duplicate, archive, scoping owner, migrasi + seed). Restart persistence = data di SQLite; belum ada uji restart end-to-end.

### M4 — Pipeline campaign-aware (P0)
- [ ] Teruskan konfigurasi campaign ke `generate_candidates` (`services/candidates.py`).
- [ ] Algoritma baru `transcript-campaign-v1`: tambah signal `campaign_relevance`
      (kecocokan topik/kata kunci brief, `required_phrases`) dan penalti untuk `prohibited_terms`. Jangan ubah `transcript-boundary-v1`; versi lama tetap tersedia.
- [ ] Simpan di `clips.analysis_json`: `editorial` (signals/rank/explanation) dan `campaign` (relevansi + rationale + versi konfigurasi), terpisah.
- [ ] Compliance dihitung per kandidat saat generate (bukan hanya saat metadata), lalu disimpan sebagai findings.
- [ ] Tambah status `unknown`; hapus `score` persen dari API, ganti dengan hitungan `{pass, fail, review, unknown}`.
- [ ] Tes: video yang sama dengan 2 campaign berbeda menghasilkan ranking berbeda; tidak ada kandidat yang cocok; durasi di luar constraint; rationale selalu ada.
- [ ] Perbarui `docs/eval/README.md` untuk algoritma baru.

### M5 — Generated Clips & Campaign Assistant
P0
- [ ] Kartu kandidat: preview 9:16, durasi, rentang waktu sumber, cuplikan transcript, rationale.
- [ ] Dua panel terpisah: "Kepatuhan campaign" (pass/gagal/perlu review/unknown) dan "Kualitas editorial" (penjelasan, tanpa persen).
- [ ] Aksi: Edit, Regenerate, Tolak (dengan alasan, sudah ada), Export.
- [ ] State: tidak ada kandidat, hasil parsial, job gagal, job panjang + cancel.

P1
- [ ] Sort/filter (compliance, rank, durasi).
- [ ] Panel Campaign Assistant: findings + rekomendasi hook/pacing dengan rentang waktu, dan cek safe-area subtitle.
- [ ] Rekomendasi bisa Preview → Apply → Undo / Dismiss lewat edit model yang ada (tidak pernah mengubah edit diam-diam).

### M6 — Editor (sebagian besar sudah ada)
- [x] Audit gap terhadap §5E: preview besar + inspector kanan sudah ada; pipeline diciutkan saat job selesai dan rail klip dikecilkan supaya editor naik. Timeline multi-track belum ada.
- [x] Inspector kanan: tab "Campaign" berisi aturan aktif + findings untuk clip ini (`CampaignPanel.tsx`), dikelompokkan Gagal / Perlu review / Belum bisa dicek / Lolos, tanpa persen.
- [~] Re-evaluasi compliance setelah trim/caption diubah: durasi dihitung langsung dari draft (sebelum autosave); cek lain ikut diperbarui backend saat autosave. Frasa wajib masih diuji terhadap transcript penuh, belum terhadap rentang trim.
- [ ] (P1) Timeline track video/subtitle/audio, hanya jika didukung tanpa rewrite.
- [ ] Pastikan indikator unsaved/autosave konsisten dengan layout baru.

### M7 — Export & validasi akhir (P0)
- [ ] Checklist pre-export: jalankan compliance pada edit tersimpan. `fail` → konfirmasi eksplisit; `unknown`/`review` → tampil sebagai peringatan, bukan pass.
- [ ] Cek ruang disk sebelum render (error `DISK_SPACE_LOW` di `core/errors.py`).
- [ ] Hubungkan output dengan campaign + versi (`render_report_json`).
- [ ] (D6, disetujui) Tabel riwayat export (migrasi `004`) + daftar riwayat di UI.
- [ ] Tes: export gagal tidak pernah tampil sukses, cancel, disk penuh, dan rule unknown tetap berstatus warning.

### M8 — Reliability, usability, beta
- [ ] Perluas `scripts/e2e_real.py`: import campaign → job → kandidat → edit → export.
- [ ] Playwright real-backend dengan campaign.
- [ ] Uji teks campaign lengkap/minim/ambigu/kontradiktif/tak terstruktur dari fixture asli.
- [ ] Sesi usability end-to-end (2–3 user), catat temuan, dan prioritaskan berdasarkan dampak.
- [ ] Update `CAMPAIGN_BRIEF_RUNBOOK.md` (alur import menggantikan "tambah preset di kode"), `README.md`, dan known limitations.
- [ ] Audit copy UI: tidak ada klaim soal eligibility, viralitas, atau reward.

## 4. Urutan kerja yang disarankan

1. D1–D6 → M0 addendum + fixture campaign.
2. M1 cukup untuk flow + tokens + wireframe Import/Detail (jangan menunggu semua layar).
3. **M3 (tabel & API) sebelum UI M2**, karena halaman import butuh endpoint simpan.
   Parser M2 (backend murni) bisa dikerjakan paralel.
4. M2 UI → M4 → M5 (P0) → M7 → M6 (inspector) → M8.
5. Item P1 (Assistant apply/undo, filter, timeline track, template) setelah alur P0 berjalan end-to-end.

## 5. Definition of Done (per milestone)

Mengacu pada dokumen §10, ditambah gate repo yang sudah ada: pytest di
container, ruff, `tsc`, lint, build, Playwright (mocked), dan untuk
M4/M7/M8 juga `scripts/e2e_real.py`. Hasil dicatat di
`10-implementation-notes.md`.
