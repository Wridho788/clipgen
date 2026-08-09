# System Architecture — Personal AI Video Assistant

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                         │
│  Upload UI → Job Status (polling) → Clip Preview → Export       │
│  State: Zustand (client/UI state) + TanStack Query (server state)│
└───────────────────────┬─────────────────────────────────────────┘
                         │ REST (JSON) + static file serving
┌───────────────────────▼─────────────────────────────────────────┐
│                      FastAPI Backend                             │
│  ┌───────────┐  ┌────────────┐  ┌───────────────────────────┐   │
│  │  API layer │→│ Job Service │→│  In-process Job Queue      │   │
│  │  (routes)  │  │ (orchestr.) │  │  (asyncio.Queue + worker) │   │
│  └───────────┘  └────────────┘  └──────────────┬────────────┘   │
│                                                  ▼                │
│                              ┌───────────────────────────────┐   │
│                              │  Processing Pipeline (stages) │   │
│                              │  0. download_youtube (optional)│   │
│                              │  1. extract_audio              │   │
│                              │  2. transcribe (faster-whisper)│   │
│                              │  3. detect_highlights           │   │
│                              │  4. cut_clips (frame asli)      │   │
│                              │  5. burn_subtitles (YouTube)    │   │
│                              │  6. generate_metadata (Ollama)  │   │
│                              └───────────────────────────────┘   │
│  SQLite (jobs, clips, metadata) │ Local filesystem (video files) │
└───────────────────────────────────────────────────────────────────┘
```

**Kenapa in-process queue, bukan Celery+Redis:** untuk 1 user yang menjalankan job satu-per-satu, menambah Redis+Celery hanya menambah moving parts tanpa manfaat nyata — ada risiko operasional (2 proses terpisah harus hidup) tanpa keuntungan throughput. `JobQueue` dibungkus dalam interface (`services/job_queue.py`) yang bisa diganti implementasinya ke Celery nanti kalau kebutuhan berubah jadi multi-user — ini yang saya maksud "scalable-by-design tapi proporsional".

---

## 2. Database Design (SQLite via SQLAlchemy)

### Tabel: `jobs`
| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID (str, PK) | ID job |
| source_type | str | `upload` \| `youtube_url` |
| source_path | str | path file lokal atau URL asal |
| source_name | str, nullable | nama file asli atau URL untuk ditampilkan di UI |
| source_duration_seconds | float, nullable | durasi media terdeteksi (untuk estimasi) |
| source_size_bytes | int, nullable | ukuran file sumber |
| processing_options | text, nullable | JSON min/max durasi, jumlah clip, dan bahasa metadata khusus job |
| parent_job_id | UUID, nullable | job asal bila job ini hasil retry |
| retry_count | int | urutan retry dari source yang sama |
| status | str | `pending`\|`downloading`\|`extracting`\|`transcribing`\|`detecting`\|`cutting`\|`subtitling`\|`generating_metadata`\|`done`\|`failed` |
| progress | int | 0–100 |
| error_message | str, nullable | isi kalau status=failed |
| warning_message | str, nullable | partial failure atau video tanpa highlight |
| transcript_json | text, nullable | hasil whisper (segments + timestamps) |
| stage_metrics_json | text, nullable | akumulasi durasi tiap tahap pipeline |
| stage_estimates_json | text, nullable | estimasi durasi tiap tahap untuk UI |
| processing_started_at | datetime, nullable | waktu tahap pertama dimulai |
| completed_at | datetime, nullable | waktu job terminal |
| created_at | datetime | |
| updated_at | datetime | |

### Tabel: `clips`
| Kolom | Tipe | Keterangan |
|---|---|---|
| id | UUID (str, PK) | |
| job_id | FK → jobs.id | |
| start_time | float | detik awal di video asal |
| end_time | float | detik akhir |
| highlight_score | float | skor heuristik (untuk debug/tuning) |
| file_path | str | path hasil potong dengan rasio/aspect asli; subtitle hanya untuk sumber YouTube |
| title | str, nullable | hasil AI metadata gen |
| caption | text, nullable | |
| hashtags | text, nullable | disimpan sebagai JSON array string |
| status | str | `processing`\|`ready`\|`failed` |
| created_at | datetime | |

**Kenapa SQLite, bukan Postgres:** single-writer, single-user, tidak ada concurrent write yang jadi masalah. SQLAlchemy ORM dipakai supaya migrasi ke Postgres nanti (kalau perlu) hanya ganti connection string, bukan rewrite query.

---

## 3. API Contract (REST)

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/api/videos/upload` | Upload file video, buat job baru → return `job_id` |
| POST | `/api/videos/youtube` | Buat job segera; download YouTube berjalan di worker |
| GET | `/api/videos/estimate` | Preview estimasi waktu pipeline berdasarkan durasi video |
| GET | `/api/jobs/{job_id}` | Status job + progress |
| GET | `/api/jobs` | List semua job (riwayat) |
| POST | `/api/jobs/{job_id}/cancel` | Batalkan job yang sedang berjalan |
| POST | `/api/jobs/{job_id}/retry` | Buat job baru dari source job terminal |
| GET | `/api/clips/job/{job_id}` | List clip hasil dari job tsb |
| GET | `/api/clips/job/{job_id}/archive` | Download seluruh clip siap sebagai ZIP |
| GET | `/api/clips/{clip_id}` | Detail 1 clip |
| GET | `/api/clips/{clip_id}/file` | Stream/download file video clip |
| PATCH | `/api/clips/{clip_id}` | Edit title/caption/hashtag manual (override AI) |
| POST | `/api/clips/{clip_id}/regenerate-metadata` | Buat ulang metadata dari transkrip tersimpan |
| DELETE | `/api/clips/{clip_id}` | Hapus clip |
| GET | `/api/system/metrics` | Aggregate queue, status job/clip, dan penggunaan storage |
| GET | `/api/system/release` | Metadata release v1.0.0, feature flags, defaults, dan known risks |
| GET | `/api/system/performance` | Baseline durasi job selesai dan rata-rata durasi stage |
| POST | `/api/system/maintenance/cleanup` | Jalankan cleanup temp/intermediate secara manual |

Semua response pakai Pydantic schema (`schemas.py`) — tipe di-share secara konseptual ke frontend lewat Zod schema yang strukturnya dicocokkan manual (karena tidak pakai codegen/OpenAPI client di versi minimal ini — ini salah satu area yang bisa ditingkatkan nanti, saya tandai sebagai TODO).

**Polling, bukan WebSocket [keputusan desain]:** progress job di-polling oleh TanStack Query tiap 2 detik selama status belum `done`/`failed`. WebSocket akan lebih real-time tapi menambah kompleksitas (koneksi persisten, reconnect logic) yang tidak sepadan untuk personal tool. Interface job status tetap dirancang agar gampang pindah ke WebSocket/SSE nanti.

---

## 4. UI Architecture (Next.js App Router)

```
/                     → daftar job (riwayat) + tombol upload baru
/upload               → form upload video (React Hook Form + Zod validation)
/jobs/[id]            → halaman progress job (polling status) → saat done, tampilkan daftar clip
/jobs/[id]/clips/[clipId] → preview clip + editor metadata + export
```

**State management split:**
- **Zustand** → UI state murni: modal terbuka/tutup, clip yang sedang dipilih untuk preview, filter/sort di daftar job. Tidak menyimpan data server.
- **TanStack Query** → semua data dari backend (jobs, clips, status polling). Cache, refetch, invalidation semua lewat sini — bukan disimpan manual di Zustand. Ini mencegah bug klasik "data di store jadi stale karena lupa sync manual".
- **React Hook Form + Zod** → form upload dan form edit metadata clip, validasi di client sebelum submit.

---

## 5. Processing Pipeline — Kontrak Antar Stage

Setiap stage adalah fungsi Python murni: `(input) -> output`, tidak menyimpan state sendiri, semua state disimpan lewat `JobService` ke DB. Ini penting supaya tiap stage bisa di-unit-test terpisah (lihat `tests/`).

```python
extract_audio(video_path) -> audio_path
transcribe(audio_path) -> list[Segment(start, end, text)]
detect_highlights(segments, audio_path) -> list[Highlight(start, end, score)]
cut_clip(video_path, start, end) -> raw_clip_path
burn_subtitles(raw_clip_path, segments) -> final_clip_path  # hanya sumber YouTube
generate_metadata(transcript_text, language="id" | "en") -> Metadata(title, caption, hashtags)
```

`cut_clip` tidak melakukan crop vertikal: upload lokal dan YouTube mempertahankan frame/aspect ratio sumber. Frontend menggunakan `stage_estimates` dan pengukuran tahap aktual untuk menampilkan ETA unggah, tahap aktif, serta sisa keseluruhan.

---

## 6. Known Limitations di Versi Minimal Ini (transparan, bukan disembunyikan)

- Job queue in-process → job `pending` bisa diantrekan ulang saat startup, tetapi job yang sudah berada di stage aktif ditandai `failed` agar tidak menggandakan clip secara diam-diam. Untuk resume tepat dari checkpoint terakhir tetap diperlukan queue persisten seperti Celery+Redis/RQ plus checkpoint per stage.
- Tidak ada auth sama sekali — endpoint terbuka. Untuk personal use di localhost ini oke, **jangan deploy ke internet publik tanpa menambah auth**.
- YouTube diproses lewat `yt-dlp` dengan retry dan client fallback. Ketersediaan dan aturan platform asal tetap perlu diperhatikan pengguna.
- ETA bersifat estimasi konservatif karena kecepatan jaringan, ukuran media, hardware, dan Whisper memengaruhi waktu aktual.
