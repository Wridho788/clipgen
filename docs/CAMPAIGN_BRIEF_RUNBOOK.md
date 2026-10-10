# Campaign Brief Runbook

Dokumen ini menjelaskan cara memakai guideline campaign di ClipGen. Brief dipilih
saat membuat job, lalu ikut disimpan pada `processing_options` dan dipakai untuk
metadata, paket distribusi, serta pemeriksaan kepatuhan clip.

## Preset yang tersedia

### YAVA Happy Health Podcast

- Durasi target: 60–90 detik.
- Hook wajib muncul pada 3 detik pertama; kandidat hook: humor, emosi,
  kontroversi, atau payoff.
- YA'Bar harus terlihat jelas dan natural.
- CTA: klik keranjang kuning.
- Hashtag: `#YAVA #HappyHealth #YABar #energiONterus #GulaLontar #enakDANsehat`.
- Hindari kata `diet`, `gendut`, `gemuk`, `kurus`, dan body-shaming.
- Konten harus bersumber dari podcast dan tidak boleh diedit menyesatkan.

### Rumah Ningrat — Rumah di Luar Nalar

- Durasi target: 15–120 detik.
- Hook wajib muncul pada 3 detik pertama.
- Frasa “Rumah di Luar Nalar” harus muncul di narasi utama.
- Tone harus positif terhadap founder dan value Rumah Ningrat.
- Hashtag: `#rumahningrat #ibnutrusmigroup #rumahsubidi #untukhiduplebihbaik`.
- Mention akun brand sesuai brief.
- Organic-only: tidak memakai ads, boosting, view bot, atau views suntikan.
- Konten harus organik, bersumber dari materi asli, dan tidak menyesatkan.

## Alur operasional

1. Buka **Studio klip** dan pilih **Campaign brief**.
2. Pilih preset yang sesuai atau **Bebas memilih aturan campaign** untuk job umum.
3. Pilih format export dan style visual.
4. Jalankan job. Brief dikirim bersama file/upload atau URL YouTube.
5. Setelah clip siap, buka kartu clip dan review:
   - title, caption, dan hashtag;
   - metadata YouTube dan Facebook;
   - checklist platform;
   - status compliance (`pass`, `review_required`, atau `blocked`).
6. Untuk aturan visual seperti product placement, hook 3 detik, dan keranjang
   kuning, lakukan review manual sebelum upload karena sistem belum bisa
   memastikan isi setiap frame secara penuh.

## Menambah preset baru

1. Tambahkan `CampaignBrief` ke `backend/app/services/campaign_briefs.py`.
2. Tambahkan preset yang sama ke `frontend/src/lib/campaigns.ts` agar UI tetap
   responsif saat memilih campaign.
3. Isi sekurangnya: durasi, hook, hashtag, CTA, mention, kata terlarang,
   required phrase/visual, serta aturan organic/source-only.
4. Tambahkan test compliance di `backend/tests/test_campaign_compliance.py`.
5. Jalankan test backend, TypeScript check, dan build frontend sebelum deploy.

## Acceptance checklist v1

- Brief ikut tersimpan pada job baru.
- Metadata mengikuti CTA, hashtag, title style, dan kata terlarang.
- Paket distribusi menampilkan copy siap pakai untuk YouTube dan Facebook.
- Compliance tidak memblokir hanya karena sinyal visual yang memang perlu
  pemeriksaan manusia; sinyal tersebut ditandai `review_required`.
- Preset tidak mengubah mode akselerasi secara manual; runtime tetap memilih
  CPU/GPU yang kompatibel dan menampilkan label perangkat aktif.
