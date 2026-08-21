# Feedback dan Analisis Distribusi Clip — 21 Agustus 2026

## Feedback pengguna

Pengguna menyampaikan bahwa dari dua job terbaru, baru satu clip yang dipilih
untuk didistribusikan ke Facebook dan YouTube. Clip tersebut baru memperoleh satu
view di YouTube Shorts. Pengguna meminta feedback ini dicatat sebagai bahan
evaluasi produk dan workflow distribusi.

### Masukan tambahan: schedule dan publish ke platform

Setelah job selesai, pengguna ingin memilih satu atau beberapa clip, memilih
platform tujuan seperti Facebook dan YouTube, menentukan waktu publikasi, lalu
ClipGen mengunggah dan mempublikasikannya otomatis.

Rancangan awal:

- pilih clip → pilih akun/platform → edit title/caption/hashtag → pilih waktu
  dan timezone → `Schedule` atau `Post now`;
- status per target: draft, scheduled, uploading, published, failed, cancelled;
- simpan external post/video ID, URL, error, percobaan terakhir, dan waktu
  publikasi untuk audit serta retry idempoten;
- tahan file final sampai semua target selesai atau retention policy menghapusnya.

### Keputusan revisi: distribusi manual, bukan koneksi API platform

Karena akses akun YouTube/Meta memiliki banyak persyaratan, V1 memakai distribusi
manual. ClipGen tetap menyediakan paket siap pakai untuk setiap clip:

- preview video final dengan watermark wajib `@RidhoWahyu`;
- rekomendasi title YouTube, description YouTube, dan tags/hashtags YouTube;
- rekomendasi caption Facebook dan hashtags Facebook;
- tombol copy metadata serta download video;
- panduan singkat per platform tentang field yang perlu diisi dan urutan upload.

Hashtag dapat diambil dari metadata sumber YouTube (title, description, tags,
dan hashtag yang tersedia melalui extractor). Jika sumber tidak menyediakan
tag/hashtag, ClipGen harus menandainya sebagai fallback dan membuat saran dari
transcript—bukan menyatakan bahwa tag tersebut berasal dari channel sumber.

Mode otomatis tidak wajib menjalankan highlight detection. Pengguna dapat
memilih `skip highlights` untuk menghemat waktu dan menghasilkan clip default,
sementara metadata tetap menjadi fokus utama. Opsi ini tidak menghapus
context-aware clipping ketika pengguna memang memerlukannya.

## Executive Summary

- **Satu view belum cukup untuk menyimpulkan clip gagal.** Data yang tersedia
  baru satu clip dan satu angka view; belum ada impressions, retention,
  average view duration, swipe-away rate, likes, komentar, atau share.
- **Bottleneck terbesar saat ini adalah funnel seleksi dan kualitas, bukan
  reach.** Dua job menghasilkan 15 clip siap, tetapi hanya 1/15 (6,7%) yang
  diuji di platform. Empat belas clip belum memiliki data distribusi.
- **Ada risiko kualitas transcript/subtitle yang nyata.** Output dua job terbaru
  memuat sejumlah judul/caption yang tampak salah dengar atau terpotong. Ini
  dapat menurunkan kepercayaan penonton dan kualitas hook.
- **Jangan mengubah strategi berdasarkan satu view.** Perbaiki kualitas
  transcript terlebih dahulu, distribusikan beberapa clip, lalu kumpulkan metrik
  platform dalam format yang konsisten.

## Data dan definisi

Analisis lokal memakai dua job berstatus `done` terbaru pada database ClipGen:

| Job | Sumber | Durasi sumber | Clip siap | Waktu proses | Tahap dominan |
| --- | --- | ---: | ---: | ---: | --- |
| `404797dc-a110-4f67-b8c7-368890239e1a` | YouTube | 58,0 menit | 7 | 108,3 menit | Transkripsi 5.818,7 dtk |
| `52ac8dd7-cd21-4815-b33e-8469ae263d98` | YouTube | 66,3 menit | 8 | 146,6 menit | Transkripsi 8.206,4 dtk |
| **Total** | 2 job | — | **15** | — | — |

`Clip siap` berarti record clip berstatus `ready` di ClipGen, bukan clip yang
sudah dipublikasikan. Angka distribusi berasal dari laporan pengguna: 1 clip
diunggah ke Facebook dan YouTube, dengan 1 view yang terlihat di YouTube Shorts.
ClipGen belum menyimpan ID post/video atau metrik platform, sehingga angka
Facebook dan metrik YouTube lain belum dapat diverifikasi dari database lokal.

## Temuan utama

### 1. Reach belum bisa dinilai karena coverage distribusi masih sangat kecil

Rasio clip yang diuji baru **1 dari 15 (6,7%)**. Empat belas clip belum punya
kesempatan menghasilkan data. Satu view pada satu Short adalah sinyal observasi
awal, bukan pembanding performa atau bukti bahwa algoritma, judul, atau format
tertentu tidak bekerja.

Implikasinya: keputusan berikutnya seharusnya bukan mengganti seluruh strategi,
melainkan menjalankan sampel distribusi yang lebih besar dan tercatat.

### 2. Kualitas transcript berpotensi menghambat click-through dan retention

Kedua job menggunakan subtitle word-level. Pemeriksaan transcript menunjukkan
sejumlah token tidak natural dan beberapa timestamp kata tidak valid atau terlalu
panjang. Karena metadata dan caption dibuat dari transcript, kesalahan ini dapat
merambat ke judul, hook, dan teks layar.

Ollama bukan sumber timestamp atau pengenalan audio. Ollama hanya menghasilkan
metadata setelah transcript tersedia; ia dapat mempercantik atau mengulang
kesalahan transcript, tetapi tidak memperbaiki sumbernya.

### 3. Biaya produksi masih berat sebelum clip sempat diuji

Transkripsi memakan sekitar 5.819 detik dari 6.499 detik waktu terukur pada job
pertama dan 8.206 detik dari 8.797 detik pada job kedua. Artinya sekitar 90%+
waktu pipeline terserap sebelum distribusi. Ini menjelaskan mengapa eksperimen
content masih sedikit, tetapi tidak menjelaskan satu view secara kausal.

## Rekomendasi operasional

1. **Buat quality gate sebelum upload.** Preview setiap clip 10–20 detik pertama,
   cek transcript, timing karaoke, hook, dan crop. Jangan distribusikan clip
   dengan token garbled atau highlight yang terlambat.
2. **Naikkan kualitas transcript untuk subtitle.** Uji model Whisper `base`
   dengan bahasa `id` untuk konten Indonesia. Model `tiny` tetap dapat dipakai
   untuk eksperimen cepat, tetapi jangan jadikan default kualitas akhir sebelum
   akurasi diterima.
3. **Perbaiki timestamp word-level.** Validasi durasi kata, clamp ke batas
   segmen, dan lakukan smoothing/interpolasi hanya pada timestamp yang rusak.
   Untuk kebutuhan presisi tinggi, evaluasi forced alignment seperti WhisperX.
4. **Distribusikan sampel yang cukup.** Gunakan beberapa clip terbaik dari kedua
   job, bukan hanya satu, dan pertahankan catatan platform, waktu publikasi,
   judul, hook, format, dan durasi.
5. **Tambahkan pengukuran distribusi.** Minimal catat per platform: impressions
   atau shown-in-feed, views, average view duration, retention/completion,
   likes, comments, shares, dan waktu sejak publikasi.

## Hipotesis yang belum dapat dibuktikan

- Satu view dapat disebabkan oleh distribusi yang belum berjalan, waktu publikasi,
  visibility/privacy, judul/hook, kualitas opening, atau memang minat audiens.
  Tanpa impressions dan retention, penyebabnya tidak dapat dipisahkan.
- Facebook belum dapat dibandingkan karena tidak ada angka view/reach yang
  dilaporkan atau diimpor ke ClipGen.
- Belum ada dasar untuk menentukan platform mana yang lebih cocok; sampelnya
  baru satu clip lintas platform.

## Rencana pengukuran berikutnya

Untuk setiap clip yang dipublikasikan, simpan satu baris tracking:

`clip_id | job_id | platform | published_at | title | hook | duration | format | impressions | views | avg_view_duration | completion_rate | likes | comments | shares`

Setelah beberapa clip terkumpul, bandingkan retention dan completion rate per
hook, durasi, style, dan platform. View total dipakai sebagai hasil akhir, bukan
satu-satunya indikator. Feedback ini dapat menjadi dasar milestone berikutnya:
**subtitle quality gate + distribution tracking**.

## Status revisi V1

Implementasi awal untuk keputusan distribusi manual sudah ditambahkan:

- setiap clip ready mengembalikan paket YouTube/Facebook yang dapat dicopy;
- paket YouTube memisahkan title, description, dan tags, sedangkan Facebook
  menyediakan caption + hashtag;
- hashtag video YouTube diambil dari `yt-dlp .info.json` bila tersedia, lalu
  diberi label fallback bila metadata sumber tidak ada;
- watermark `@RidhoWahyu` dibakar ke file hasil export (bukan sekadar overlay UI);
- mode automatic memiliki pilihan untuk melewati analisis highlight dan memakai
  default clip window. Metadata tetap boleh aktif, sehingga transkripsi masih
  dijalankan bila diperlukan untuk kualitas caption.

Asumsi watermark saat ini: posisi kanan bawah, opacity 0,78, dengan latar gelap
transparan. Nilai ini dapat diubah melalui `WATERMARK_*` di environment.
