# 14 --- Integrasi Gemini (Google AI Studio, free tier)

Dokumen ini menjelaskan integrasi Gemini di ClipGen: apa yang dipanggil,
bagaimana cara kerja di free tier, dan apa yang sudah terukur (bukan
asumsi). Ditulis 2026-11-18.

Kode: `backend/app/core/pipeline/gemini_client.py` (klien bersama),
`backend/app/core/pipeline/metadata_gen.py` (pemanggilan dari pipeline),
`backend/app/config.py` (setting).

---

## 1. Ringkasan

Gemini dipakai sebagai **provider generasi metadata** ClipGen. ClipGen
memotong video panjang menjadi klip pendek; setiap klip butuh tiga hal
agar bisa langsung diunggah ke media sosial:

| Field | Contoh | Dipakai untuk |
|---|---|---|
| `title` | "Yuk Simpan Tips Ini!" | Judul unggahan |
| `caption` | 30-50 kata deskripsi + ajakan interaksi | Deskripsi unggahan |
| `hashtags` | 5-7 tag tanpa `#` | Hashtag unggahan |

Provider dipilih lewat satu setting, `METADATA_PROVIDER`:

| Nilai | Provider | Keterangan |
|---|---|---|
| `ollama` | Ollama lokal (`gemma3:4b`) | Default lama. Jalan tanpa internet, tapi butuh RAM dan model terunduh. |
| `gemini` | Gemini Developer API | Gratis, cepat, kualitas metadata lebih baik. Butuh key. |

Ollama tetap dipertahankan: kalau key habis kuota atau internet mati,
ClipGen tidak kehilangan kemampuan generates metadata sama sekali.

---

## 2. Konfigurasi

Buat key di [Google AI Studio](https://aistudio.google.com/apikey), lalu
isi `.env` di root repo (file ini **tidak** masuk git):

```dotenv
METADATA_PROVIDER=gemini
GEMINI_API_KEY=<key-mu>
GEMINI_MODEL_CHAIN=gemini-3.8-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite
```

| Setting | Default | Arti |
|---|---|---|
| `GEMINI_API_KEY` | kosong | Key API Studio. Wajib diisi; tidak pernah masuk log atau URL. |
| `GEMINI_MODEL_CHAIN` | 3 model (lihat di atas) | Model yang dicoba **berurutan**. |
| `GEMINI_TIMEOUT_SECONDS` | 30 | Batas waktu per permintaan. |
| `GEMINI_MAX_ATTEMPTS_PER_MODEL` | 2 | Percobaan per model sebelum pindah ke model berikutnya. |
| `GEMINI_RETRY_BACKOFF_SECONDS` | 1.5 | Basis jeda exponential backoff antar percobaan. |

> **Key jangan pernah masuk git.** `.env` sudah masuk `.gitignore` (baris
> `.env` dan `.env.*` di `.gitignore`). File `.env.example` hanya berisi
> placeholder kosong. Kalau key pernah bocor (mis. terpakai di commit atau
> tersebar di chat), revoke di AI Studio lalu buat yang baru.

---

## 3. Cara kerja: model chain + backoff

Kode lama memanggil satu model yang tetap (`gemini-3.8-flash`). Di free
tier, satu model tetap **tidak bisa diandalkan**, karena tiga hal terjadi
bersamaan:

1. **Kuota per menit per model.**-after ~19 permintaan/menit pada satu
   model, API menjawab `429`.
2. **`503 UNAVAILABLE` saat model sibuk.** Model populer sering menjawab
   "high demand" tanpa alasan lain.
3. **Tidak ada header `Retry-After`.** Client tidak tahu kapan harus
   mencoba lagi; harus memilih sendiri.

Karena kuota dihitung **per model**, pindah ke model lain bukan ulangan
yang sama, tapi kesempatan kedua yang benar-benar berbeda. Klien
(`gemini_client.py`) karena itu bekerja dua hal:

```
untuk model di chain:            # gemini-3.8-flash, gemini-3.5-flash-lite, ...
    untuk attempt 1..N:           # N = GEMINI_MAX_ATTEMPTS_PER_MODEL
        panggil generateContent
        200 + teks   -> selesai, kembalikan
        429 / 5xx    -> tunggu backoff, coba lagi di model yang sama
        404 / 4xx    -> jangan diulang, langsung ke model berikutnya
    model habis -> lanjut ke model berikutnya
semua model gagal -> GeminiError
```

Detail yang penting:

- **Backoff exponential.** Jeda = `1.5s`, `3s`, `6s`, ... Karena free tier
  tidak mengirim `Retry-After`, angka ini pilihan kita sendiri.
- **404 tidak diulang.** Model yang sudah tidak tersedia untuk key itu
  tidak akan kembali dengan mencoba lagi; mengulang hanya membuang kuota.
- **Kegagalan total tidak menjatuhkan job.** `generate_metadata()`
  sudah punya fallback: kalau provider gagal, ClipGen memakai judul dari
  kalimat pertama transkrip, bukan menggagalkan seluruh pipeline.
- **Key hanya di header.** `x-goog-api-key`, tidak pernah di URL, tidak
  pernah ditulis ke log atau pesan error. Ada tes yang menjaga hal ini.

---

## 4. Prompt danCampaign brief

Prompt disusun di `metadata_gen.py` dan ada dua Bahasa:

- **Indonesia (default):** diminta karena konten sumbernya TV Indonesia.
- **English:** dipakai kalau `metadata_language=en`.

Prompt meminta JSON dengan nilai `responseMimeType: "application/json"`,
jadi Gemini menjawab JSON murni --- bukan teks yang harus diparse.
`responseMimeType` sudah tersedia di free tier dan diverifikasi bekerja
pada model-model di chain.

Jika job punya campaign brief, instruksinya ditambahkan ke prompt:
gaya judul, CTA yang wajib ada, hashtag wajib, dan **kata yang dilarang**.
Prompt juga meminta model agar **tidak menambah klaim atau konteks yang
tidak ada di transkrip** --- penting, karena metadata yang mengarang isi
video akan menyesatkan.

---

## 5. Yang terukur (bukan asumsi)

Diuji langsung ke API dengan key free tier pada 2026-11-18.

### 5.1 Model mana yang bisa dipakai

| Model | Hasil | Catatan |
|---|---|---|
| `gemini-3.8-flash` | ⚠️ Accept-sekali | Balas `503 UNAVAILABLE` sebagian besar; sisanya `200`. Model terkuat di chain, tapi tidak stabil di free tier. |
| `gemini-3.5-flash-lite` | ✅ Stabil | `200` konsisten; JSON mode valid. |
| `gemini-3.1-flash-lite` | ✅ Stabil | `200` konsisten. |
| `gemini-2.5-flash`, `2.0-flash` | ❌ `404` | "no longer available to new users". |
| `gemini-flash-latest` | ⚠️ `503` | Alias yang menunjuk ke model sibuk. |

### 5.2 Batas kuota

- **~19 permintaan/menit** per model. Permintaan ke-20 dijawab `429`.
- **Kuota terhitung per model.** Setelah `429` pada `gemini-3.5-flash-lite`,
  `gemini-3.8-flash` tetap melayani 8 permintaan berturut-turut tanpa
  `429`. Chain 3 model berarti kapasitas efektif sekitar 3×.
- **Tidak ada header `Retry-After`** pada respons `429`.

### 5.3 Bukti chain bekerja

Pemanggilan nyata ke pipeline ClipGen (`generate_metadata`) dengan model
pertama sedang `503`:

```
Calling Gemini (chain: gemini-3.8-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite)
Gemini model gemini-3.8-flash exhausted; trying the next model
Gemini gemini-3.5-flash-lite answered on attempt 1
Gemini answered with gemini-3.5-flash-lite after 2 attempt(s)
```

Hasil metadata yang dihasilkan:

- **Judul:** "Kebiasaan Baik Sederhana yang Sering Diabaikan Ora"
- **Caption:** "Selamat datang di talkshow sore ini! Kita membahas tentang kebiasaan baik yang sering diabaikan tapi hasilnya sangat luar biasa kalau dilakukan secara konsisten dalam waktu singkat."
- **Hashtag:** `talkshow`, `kebiasaanbaik`, `konsistensi`, `inspirasisore`, `motivasi`, `pengenbisa`

Dengan model tunggal yang lama, pemanggilan ini **gagal**.

---

## 6. Deteksi kesehatan

`GET /health/ready` melaporkan status provider:

```json
{
  "status": "ok",
  "database": true,
  "ollama": true,
  "gemini": true,
  "metadata_provider": "gemini",
  "metadata_configured": true
}
```

Pengecekan memakai endpoint model (`GET /v1beta/models/{model}`), bukan
`generateContent`, jadi **tidak memakai kuota generate**. Ini penting:
mengecek key tidak boleh memakan kuota yang dipakai job.

`metadata_configured` berarti "provider benar-benar bisa dipakai", bukan
sekadar "key terisi". Key yang kadaluwarsa atau model yang tidak boleh
dipanggil akan terdeteksi di sini.

---

## 7. Di UI

- **Metadata tiap klip** (judul, caption, hashtag) ditampilkan di kartu
  klip.
- **Tombol "Buat ulang dengan AI"** memanggil
  `POST /api/clips/{clip_id}/regenerate-metadata`, yang menjalankan ulang
  provider AI atas transkrip yang tersimpan.
- Endpoint ini **tidak menyentuh caption**. Koreksi caption manual tidak
  hilang saat metadata dibuat ulang.

---

## 8. Batasan yang diketahui

1. **Free tier tidak dijamin.** `429`/`503` adalah kondisi normal, bukan
   kondisi galat. Chain + backoff membuat masalah ini jarang terlihat,
   tapi tidak menghilangkannya. Untuk pemakaian harian yang berat, perlu
   key berbayar.
2. **Tanpa caching.** Metadata untuk klip yang sama akan meminta API lagi
   setiap kali tombol ditekan. Untuk tahap berikutnya, hash transkrip →
   metadata bisa di-cache di database.
3. **Kualitas metadata tidak dievaluasi.** Belum ada ukuran apakah judul
   hasil Gemini benar-benar lebih baik dari Ollama atau dari template
   bawaan. Ini yang paling perlu diukur berikutnya.
4. **Metadata bisa terlalu panjang untuk judul.** `title` dipotong ke 50
   karakter dan `caption` ke 200 di `_parse_response`, jadi hasil Gemini
   yang panjang terpotong, bukan gagal.

---

## 9. Rujukan file

| File | Isi |
|---|---|
| `backend/app/core/pipeline/gemini_client.py` | Klien Gemini: model chain, backoff, pengecekan koneksi. |
| `backend/app/core/pipeline/metadata_gen.py` | Prompt, pemilihan provider, parsing JSON, fallback. |
| `backend/app/config.py` | Setting `gemini_*`. |
| `backend/app/main.py` | Laporan kesehatan di `/health/ready`. |
| `backend/tests/test_gemini_client.py` | Tes chain, retry, 404, key di header, JSON mode. |
| `frontend/src/components/ClipCard.tsx` | Tombol "Buat ulang dengan AI". |
