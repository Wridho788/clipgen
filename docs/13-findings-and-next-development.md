# 13 --- Temuan 2026-10-15 & Rencana Pengembangan Berikutnya

Dicatat dari sesi analisis 2026-10-15/16 (branch `overhaul/local-first-editor`,
commit dasar `1f2ed13`). Desain teknis rinci untuk offload GPU ada di
`docs/superpowers/specs/2026-10-15-gpu-transcription-offload-design.md`;
dokumen ini adalah ringkasan temuan, keputusan, dan urutan kerja.

## 1. Temuan A --- Kenapa 1 jam video bisa jadi 6 jam lebih transkrip

Bukan bug. Terukur pada job `d31a9105` (sumber 4911 s = 81,9 menit):

| Fakta | Nilai |
|---|---|
| CPU host | AMD Athlon Gold 3150U, **2 core fisik / 4 thread**, 15 W |
| GPU | AMD Radeon terintegrasi -> `cuda_device_count = 0`, selalu jatuh ke CPU |
| Model / beam / compute | `small` / 3 / int8 |
| CPU yang benar-benar dipakai worker | **2,13 dari 4 logis** (sampel `/proc` 20 s) |
| RTF terukur (18 menit pertama) | **7,5-13x** real-time |
| ETA yang ditampilkan app | **23 574 s = 6,55 jam** (= 4911 x 4,8, tabel `MODEL_CPU_TRANSCRIPTION_RTF`) |

Transkripsi ~94 % dari total waktu job (cropping 980 s, metadata 100 s). RTF
nyata lebih buruk dari tabel (4,8x); `docs/09` §4.1 sudah mencatat 9,6x untuk
`small` pada audio TV.

Faktor yang bisa dibedakan:

1. **Hardware** --- batas keras; tidak bisa dibenahi lewat config.
2. **Tanpa GPU CUDA** --- jalur GPU (`gpu_transcription_rtf = 0.35`, ~29 menit
   untuk 82 menit) tertutup di laptop ini.
3. **Thread** --- `WHISPER_CPU_THREADS=0` memilih core fisik; menaikkan ke 4
   paling +20 %.
4. **`beam_size = 3`** --- sudah kompromi, tidak diubah.
5. **Dugaan (belum diuji): decoding loop** --- `docs/09` §4.1 mencatat loop
   "balik balik balik ..." pada ketiga ukuran model, dan
   `transcribe.py:70` tidak mengatur `condition_on_previous_text`, sehingga
   temperature fallback dapat men-decode ulang window yang sama hingga 6x.
   Ini satu-satunya yang berbau inefisiensi, bukan batas hardware.

Batasan keputusan lama yang tetap berlaku (memori
`clipgen-transcription-language`): bahasa eksplisit `id` dan model `small`
dipilih pemilik demi keterbacaan; jangan diturunkan demi kecepatan tanpa
bertanya.

## 2. Temuan B --- Klip tidak ditonton: masalahnya distribusi, bukan kecepatan

Ekspor Facebook Reels 17 Sep - 15 Okt 2026 (28 reel):

- total **906 tayangan**, **median 6**; **23 dari 28** di bawah 10 tayangan;
- 3 klip menyumbang **80 %** tayangan; 25 sisanya rata-rata **7,4**;
- dua yang menembus (Laporpak part 1 dan 2: 333 dan 267 tayangan) punya
  retensi hanya ~14-16 % (9,7 s dan 8,4 s dari 61 s); part 3 jatuh ke 9;
- **halaman Facebook membawa peringatan konten tidak orisinal** (dikonfirmasi
  pemilik 2026-10-15).

Aturan ketiga platform (sumber sekunder; verifikasi ke halaman resmi sebelum
bergantung padanya):

| Platform | Yang ditindak |
|---|---|
| Facebook (Meta, Mar 2026) | menyambung klip orang lain; versi duplikat/diedit ringan; watermark/border tidak dihitung. Bertingkat: turun peredaran -> non-recommendable -> kehilangan monetisasi |
| YouTube | kebijakan *reused content* & *inauthentic content*; jangkauan channel agregator diturunkan; tangga peringatan -> suspensi 90 hari -> keluar YPP |
| TikTok (sejak 15 Sep 2025) | repost tanpa komentar; klip TV/film "walau logo diblur" |

Ketiganya punya **satu pengecualian yang sama**: komentar orisinal yang
berarti, modifikasi substansial, atau informasi/analisis baru.

Implikasi:

- 30+ klip itu **tidak memberi sinyal kualitas** tentang ClipGen; kanalnya
  tidak mengedarkan.
- Akun baru **tidak** menyelesaikan masalah (penyebab ikut pindah bersama
  konten; menghindari penegakan berisiko ke kedua akun). Periksa dulu
  Professional Dashboard / Account Status dan ajukan banding bila ada.
- Menyebar ke YouTube dan TikTok bukan diversifikasi: aturannya hampir sama.
- `visual_style: blur` pada ClipGen secara harfiah adalah pola yang disebut
  TikTok sebagai tidak orisinal.

## 3. Kenapa tetap mengerjakan sisi kecepatan

Bukan untuk memproduksi lebih banyak klip. Produk harus berubah bentuk (klip
perlu ditambah sesuatu yang orisinal), dan tiap eksperimen format sekarang
memakan 6-13 jam. Kecepatan iterasi yang membuat eksperimen itu mungkin.

**Tidak** di-deploy ke hosting gratis: Vercel tak cocok untuk job panjang;
Render free tidur 15 menit; Fly.io tak punya free tier untuk pendaftar baru;
Railway kreditnya kecil. Intinya CPU gratis lebih lemah dari laptop ini, dan
arsitektur ClipGen (FFmpeg, SQLite, file 355 MB) memang local-first.

## 4. Keputusan pemilik (2026-10-16)

| Pertanyaan | Keputusan |
|---|---|
| Urutan | **Cache transkrip dulu**, baru offload GPU |
| Upload audio TV (pihak ketiga) ke akun Kaggle pribadi | **Boleh, tanpa syarat** (tanpa penghapusan otomatis / layar disclosure) |
| Pemicu jalur offload | **Otomatis bila ETA transkripsi > ambang** |

Keputusan penulis (belum disetujui pemilik, tandai bila tidak setuju):
spike 3 kali (WAV CPU / WAV Kaggle / Opus Kaggle); kuota habis -> job diparkir
+ tombol "jalankan di CPU", bukan fallback otomatis;
`condition_on_previous_text` hanya diukur; saklar global `offload_enabled`
default **mati** demi syarat opt-in `docs/02` §13.

## 5. Rencana pengembangan

Status: `todo` / `blocked` / `done`.

### Fase A --- Pakai ulang transkrip (lokal, gratis) --- `todo`

Terverifikasi: `retry_job` (`api/routes/jobs.py`) membuat `Job` baru dengan
`source_path` sama tetapi tidak menyalin `transcript_json`; tidak ada hash isi
file sumber.

- [ ] Kunci cache: hash isi sumber + `transcript_language` + ukuran model
- [ ] Lewati *extracting* dan *transcribing* bila transkrip valid ada
- [ ] Tetap lewatkan lewat `normalize_segments` (`timeline.py`) dan catat report
- [ ] Invalidasi saat file sumber diganti / bahasa / model berubah
- [ ] Tes di dalam container (lihat memori `clipgen-test-workflow`)

Hanya menolong sumber yang sudah pernah ditranskrip.

### Fase B --- Spike GPU di Kaggle --- `todo`, dijalankan pemilik

- [ ] Kit spike: notebook (faster-whisper `small`, `beam_size=3`,
      `language="id"`, float16) + skrip pembanding
- [ ] Tiga run: WAV CPU lokal, WAV Kaggle GPU, Opus Kaggle GPU
- [ ] Lulus bila 82 menit < 1 jam **dan** 3 cuplikan (satu dengan musik/tepuk
      tangan) dinilai pemilik setidaknya sama terbacanya dengan `small` lokal
- [ ] Ukur `condition_on_previous_text=False` vs default (laporan saja)

### Fase C --- Offload --- `blocked` oleh Fase B

- [ ] Ekspor audio Opus + manifest (`job_id`, durasi, bahasa, model, checksum)
- [ ] Impor `transcript.json` (bentuk `segments_to_json`), tolak bila checksum
      atau durasi tidak cocok
- [ ] Status "menunggu transkrip eksternal" tanpa merusak
      `_pipeline_progress`, proyeksi ETA, dan requeue saat startup
- [ ] Pemicu otomatis di atas ambang ETA + saklar `offload_enabled` (default mati)
- [ ] Tombol "jalankan di CPU" saat kuota habis
- [ ] Nanti: integrasi API Kaggle (`kernels push/poll/output`), via seam
      `TranscriptionProvider` (`docs/02` §12)

### Fase D --- Produk: lapisan orisinal --- `todo`, belum didesain

Perubahan produk yang membuka ketiga platform sekaligus: dari "potong +
caption" menjadi "potong + sesuatu yang menambah". Belum ada desain; mulai
dengan satu pertanyaan ke pemilik: apa yang muncul di kepala saat menonton
momen bagus yang **tidak** ada di klipnya sendiri (komentar, konteks, analisis,
reaksi)? Jawabannya menentukan fiturnya. Pertimbangkan juga mengganti
`visual_style: blur` sebagai default.

### Di luar kode --- tindakan pemilik

- [ ] Buka Professional Dashboard -> Account Status; cek label penalti pada
      reel yang hanya 5 tayangan; ajukan banding bila ada
- [ ] Pertimbangkan jeda mengunggah konten pihak ketiga murni sampai Fase D
- [ ] Verifikasi aturan ketiga platform ke halaman resmi

## 6. Pertanyaan terbuka

1. Nilai default ambang ETA untuk pemicu offload.
2. Apakah integrasi API Kaggle menyusul setelah jalur manual.
3. Bentuk "lapisan orisinal" (Fase D).
