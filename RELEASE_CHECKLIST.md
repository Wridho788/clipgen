# Release Checklist

Use this checklist before demoing or using ClipGen v1.0.0 as the local MVP.

## Mandatory

- [ ] Docker Desktop is running.
- [ ] Ollama is running or metadata fallback is acceptable.
- [ ] `ollama list` includes the configured model, default `gemma3:4b`.
- [ ] `.env.example` has been reviewed for local overrides.
- [ ] `docker compose config --quiet` passes.
- [ ] Backend and frontend containers are healthy.
- [ ] `curl.exe http://localhost:8000/health/ready` returns `status=ok`.
- [ ] `curl.exe http://localhost:8000/api/system/release` returns version `1.0.0`.
- [ ] `.\scripts\release-validate.ps1 -SkipPlaywrightInstall` passes.
- [ ] Storage has been backed up if existing clips/jobs matter.

## Product UAT

- [ ] Upload a short local video and verify upload ETA.
- [ ] Confirm local-upload pipeline has no crop/subtitle stage.
- [ ] Confirm local-upload output keeps source aspect ratio.
- [ ] Preview a generated clip.
- [ ] Edit title/caption/hashtags.
- [ ] Copy caption.
- [ ] Download one clip.
- [ ] Download all ready clips as ZIP.
- [ ] Create a YouTube job from a public URL.
- [ ] Confirm YouTube job starts quickly and enters downloading/processing state.
- [ ] Confirm metadata language Indonesia and English can be selected.

## DevOps

- [ ] Check `docker ps`.
- [ ] Check `curl.exe http://localhost:8000/api/system/metrics`.
- [ ] Check `curl.exe http://localhost:8000/api/system/performance`.
- [ ] Run manual cleanup smoke:

```powershell
curl.exe -X POST http://localhost:8000/api/system/maintenance/cleanup
```

- [ ] For long videos, monitor resources:

```powershell
docker stats clipgen-backend clipgen-frontend
```

## Backup

```powershell
.\scripts\backup-storage.ps1
```

Backup output is written under `release-artifacts/backups/`.

## Export Package

```powershell
.\scripts\export-release-package.ps1
```

Release package output is written under `release-artifacts/`.

## Release Decision

- [ ] Ship as local MVP v1.0.0.
- [ ] Defer auth/cloud/multi-user/persistent queue to a later sprint.
