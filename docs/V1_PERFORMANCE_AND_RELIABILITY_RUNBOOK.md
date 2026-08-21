# ClipGen V1 — Performance and Reliability Runbook

## Status implementasi

Kode V1 sudah menerapkan jalur kerja yang aman untuk CPU dan deteksi GPU
otomatis. Validasi image Docker dan benchmark nyata perlu dijalankan sesudah
Docker Desktop aktif; jangan restart ketika ada job aktif.

| Area | Implementasi | Status |
| --- | --- | --- |
| Capability perangkat | Probe CTranslate2 CUDA + encode NVENC satu frame, lalu cache. Encoder FFmpeg yang sekadar tercantum tidak dianggap GPU. | Selesai di kode |
| Mode akselerasi | Tidak ada pemilih CPU/GPU. Semua job memakai `auto`; UI menampilkan label runtime sebenarnya. | Selesai di kode |
| Transkripsi | `word_timestamps` hanya aktif untuk subtitle, CPU thread dapat diatur, ETA diperbarui dari throughput aktual. | Selesai di kode |
| Render | Cut + reframe + style menjadi satu proses FFmpeg untuk output sosial; blur CPU memakai background resolusi lebih kecil; fallback CPU valid. | Selesai di kode |
| Progress | Progress ditimbang dari estimate tahap aktual, bukan band 30–49%; heartbeat untuk transkripsi dan FFmpeg. | Selesai di kode |
| Perencanaan klip | Jumlah kandidat dan panjang klip bersifat adaptif; bukan selalu lima klip atau 15 detik. | Selesai di kode |
| Observability | Halaman job memperlihatkan elapsed/ETA/device; endpoint performance mengelompokkan hasil per preset/style/subtitle; skrip benchmark JSON tersedia. | Selesai di kode |
| Smoke/benchmark Docker | Jalankan perintah validasi di bawah. | Menunggu runtime |

## Baseline masalah yang diperbaiki

Job `d1beb422-d982-4620-8f9b-34580372ffa7` adalah baseline:

- YouTube 37:12, AV1 720p, 301 MB.
- Download 4:16 dan ekstrak audio 0:19 — bukan bottleneck utama.
- Transkripsi CPU `tiny`, Beam 3, VAD: 83:18 (RTF 2,24), sekitar 2,99× ETA lama.
- Render 9:16 blur mencoba NVENC meski container tidak memiliki NVIDIA GPU,
  lalu mengulang di CPU.
- Persentase 48% berasal dari band statis transkripsi, bukan pekerjaan nyata.

Host yang diperiksa memiliki AMD Radeon Graphics 2 GB. Jalur ini **tidak**
kompatibel dengan CTranslate2 CUDA atau `h264_nvenc`; aplikasi harus dan akan
menampilkan `CPU` pada perangkat tersebut. Ini bukan error: CPU adalah fallback
yang didukung penuh.

## Kebijakan runtime V1

1. `WHISPER_DEVICE=auto` memilih CUDA hanya bila CTranslate2 melihat perangkat
   CUDA di dalam container. Jika tidak, transkripsi memakai CPU.
2. Render GPU dipilih hanya bila probe encode NVENC satu-frame berhasil. Jika
   FFmpeg memiliki encoder NVENC tetapi driver/perangkat tidak diekspos, render
   langsung memakai `libx264`; tidak ada retry GPU untuk setiap klip.
3. Label `Akselerasi` di status sistem dan halaman job menunjukkan kombinasi
   aktual (`CPU`, `GPU`, atau kombinasi transkripsi/render), bukan preferensi UI.
4. Untuk GPU V1 diperlukan GPU NVIDIA, driver WSL2/Docker yang sesuai,
   `gpus: all`, dan library CUDA/cuDNN di image. AMD/DirectML tidak dipaksa
   melalui jalur NVIDIA ini.

## Kebijakan klip dinamis

- `clip_count=0` berarti otomatis: kira-kira satu kandidat per delapan menit,
  minimum 1 dan maksimum 12. Permintaan eksplisit 1–12 tetap dihormati.
- Detektor memilih kandidat berdasarkan konteks humor, emosi, payoff, tension,
  pertanyaan, dan energi audio. Kandidat lemah boleh menghasilkan lebih sedikit
  output daripada target; tidak ada kewajiban membuat lima klip.
- Default bawah durasi adalah 10 detik dan batas atas 60 detik. Ini bukan
  panjang tetap: momen 30 atau 60 detik dapat dipertahankan bila konteksnya
  lebih baik. API tetap menerima batas 5–120 detik untuk use case khusus.
- Preset TikTok/Reels/Shorts, square, dan landscape serta blur/crop/zoom/split
  memberi format yang relevan untuk platform tanpa hard-code tren harian.
  Integrasi tren live membutuhkan sumber data platform dan bukan bagian dari
  V1 lokal ini.

## Konfigurasi penting

Nilai berikut ada di [`.env.example`](../.env.example) dan diteruskan Compose.

```dotenv
WHISPER_DEVICE=auto
WHISPER_CPU_THREADS=0
CPU_TRANSCRIPTION_RTF=1.75
GPU_TRANSCRIPTION_RTF=0.35
RENDER_ACCELERATION=auto
JOB_HEARTBEAT_INTERVAL_SECONDS=30
HIGHLIGHT_TOP_N=0
```

`JOB_HEARTBEAT_INTERVAL_SECONDS` hanya cadence pembaruan UI/database. Render
atau transkripsi yang butuh 30–60 detik antar-sinyal tetap valid dan tidak
dianggap gagal hanya karena lambat.

## Validasi rilis

Jalankan setelah tidak ada job aktif:

```powershell
docker compose up -d --build
docker compose exec backend pytest -q
Invoke-RestMethod http://localhost:8000/api/system/release | ConvertTo-Json -Depth 6
Invoke-RestMethod http://localhost:8000/api/system/performance?limit=30 | ConvertTo-Json -Depth 8
docker stats --no-stream
```

Hasil `/api/system/release` pada komputer saat ini harus berlabel `CPU` dan
`nvenc_runtime_usable: false`; itu adalah hasil yang benar untuk perangkat
tanpa NVIDIA yang diteruskan ke container.

## Benchmark berulang

Untuk sebuah job lengkap, simpan sampel stage, ETA, heartbeat, runtime, dan RTF:

```powershell
.\scripts\benchmark-job.ps1 -JobId <job-id> -PollSeconds 30
```

Skrip menulis JSON ke `benchmark-results/`. Bandingkan `transcription_rtf`,
`stage_metrics.cropping`, dan deviasi ETA dari beberapa run dengan sumber dan
opsi yang sama. Jangan menaikkan jumlah worker atau mengaktifkan parallel
render sebelum benchmark membuktikan total waktu membaik pada CPU tersedia.

## Bersihkan storage dengan aman

Pada dashboard, gunakan panel **Bersihkan storage** hanya setelah semua job
berstatus terminal. Endpoint menolak tindakan ini jika ada job yang masih
aktif atau menunggu.

- **Ke Recycle Bin** memindahkan source video, hasil clip, file sementara, dan
  riwayat job ke `backend/storage/.recycle-bin/<timestamp>/`. Sebuah snapshot
  SQLite dibuat sebelum riwayat job dihapus. Mode ini tidak membebaskan ruang
  disk sampai recycle bin dikosongkan secara permanen.
- **Hapus permanen** menghapus aset, riwayat job, dan seluruh isi Recycle Bin
  ClipGen. UI meminta teks konfirmasi `HAPUS PERMANEN`.

Folder recycle internal dipakai karena backend berjalan di container Linux dan
tidak dapat memindahkan bind-mounted file secara andal ke Windows Recycle Bin.

## Go / no-go V1

Go apabila CPU-only job tidak pernah menulis `NVENC render failed`, subtitle
nonaktif tidak menghasilkan word timestamp, heartbeat tetap diperbarui, dan
benchmark dapat direkam. No-go bila label GPU muncul tanpa CUDA/NVENC yang
benar-benar usable, ETA tetap menggunakan band statis, atau fallback encoder
gagal karena opsi NVENC terbawa ke `libx264`.
