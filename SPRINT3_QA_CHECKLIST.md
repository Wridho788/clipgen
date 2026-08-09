# Sprint 3 QA Checklist

Sprint 3 fokus pada testing, reliability, performance baseline, dan devops
validation sebelum masuk Sprint 4.

## Automated Validation

Jalankan dari project root:

```powershell
.\scripts\sprint3-validate.ps1
```

Yang dicek script:
- Docker Compose config valid
- Backend dan frontend container running
- `/health/ready`, `/api/system/metrics`, `/api/system/performance`
- Backend pytest di container
- Frontend lint dan production build
- Playwright browser E2E desktop + mobile
- Manual cleanup endpoint smoke test

Jika port frontend `3000` dipakai, default script memakai `3001`.

## Manual UAT

1. Buka frontend: `http://localhost:3001`
2. Upload video pendek 30-90 detik.
3. Pastikan upload progress dan ETA tampil.
4. Pastikan timeline menampilkan ETA per stage dan total.
5. Pastikan upload lokal tidak menampilkan stage subtitle/crop.
6. Pastikan hasil clip mempertahankan aspect ratio sumber.
7. Preview clip, edit metadata, copy caption, download clip, dan download semua.
8. Buat job YouTube dari video publik pendek.
9. Pastikan YouTube job masuk cepat ke status pending/downloading.
10. Pastikan YouTube job punya subtitle dan metadata sesuai bahasa yang dipilih.

## DevOps Checks

```powershell
docker ps
curl.exe http://localhost:8000/health/ready
curl.exe http://localhost:8000/api/system/metrics
curl.exe http://localhost:8000/api/system/performance
curl.exe -X POST http://localhost:8000/api/system/maintenance/cleanup
```

Pantau resource bila job video panjang:

```powershell
docker stats clipgen-backend clipgen-frontend
docker inspect clipgen-backend --format "ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}} FinishedAt={{.State.FinishedAt}}"
docker logs --tail 120 clipgen-backend
```

## Exit Criteria

- Backend pytest lulus.
- Frontend lint/build lulus.
- Playwright E2E lulus di desktop dan mobile.
- Docker backend/frontend healthy.
- Upload pendek selesai dan menghasilkan minimal satu clip atau warning kosong yang jelas.
- YouTube publik masuk queue dan memberi error yang jelas bila platform menolak.
- Tidak ada stage crop pada job baru.
- Metadata bahasa Indonesia/English sesuai pilihan.
- Performance baseline endpoint mengembalikan data untuk job selesai.

## Known Risk

Container pernah berhenti dengan exit `137`, tetapi Docker melaporkan
`OOMKilled=false` dan log FastAPI menunjukkan graceful shutdown. Root cause tetap
harus dipantau saat load test video panjang.
