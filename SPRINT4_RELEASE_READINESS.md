# Sprint 4 Release Readiness

Sprint 4 turns ClipGen from a tested build into a local MVP release package.

## Scope Completed

### Mandatory

- Root `README.md` with quick start, validation, backup, storage, and limitations.
- `RELEASE_NOTES.md` for v1.0.0.
- `RELEASE_CHECKLIST.md` for demo/use readiness.
- Backend/frontend package versions set to `1.0.0`.
- Backend release endpoint: `GET /api/system/release`.
- Release validation script: `scripts/release-validate.ps1`.
- Storage backup script: `scripts/backup-storage.ps1`.
- Release package export script: `scripts/export-release-package.ps1`.
- Docs updated with Sprint 3/4 validation and operational endpoints.

### High

- Dashboard release/status strip: version, worker state, queue, storage.
- Backend release feature flags expose crop/subtitle behavior clearly.
- Next.js runtime upgraded to `14.2.35`.
- Docker Compose gets `APP_VERSION` default.
- Release validation checks docs, versions, backend release contract, and full QA.

### Medium

- Performance baseline endpoint documented for release diagnostics.
- Backup/export guidance documented.
- Known risks documented in README, release notes, and release endpoint.
- CI includes Playwright E2E.

### Low

- UI release polish: compact operational status on dashboard.
- Docs index links added in root README.
- Release artifacts are ignored via `.gitignore`.

## Frontend Readiness

- Dashboard supports upload/YouTube intake, job filters, and system status.
- Job page supports progress timeline, ETA, preview, metadata edit, and downloads.
- Output player no longer assumes vertical crop.
- Playwright coverage:
  - YouTube job creation with English metadata.
  - Upload result page without crop/subtitle stage.
  - Metadata editing.
  - Desktop and mobile projects.

## Backend Readiness

- Job recovery, metrics, performance, release, and cleanup endpoints are available.
- Contract tests cover estimates, system metrics, performance, and release metadata.
- YouTube downloader has retry/fallback and user-safe messages.
- Storage maintenance cleans old temp/intermediate artifacts.

## DevOps Readiness

- Docker Compose can build and run backend/frontend.
- Validation scripts:

```powershell
.\scripts\sprint3-validate.ps1
.\scripts\release-validate.ps1
```

- Backup script:

```powershell
.\scripts\backup-storage.ps1
```

- Package export script:

```powershell
.\scripts\export-release-package.ps1
```

## Remaining Risks

- Long videos still need manual resource observation.
- Active in-process jobs are retryable but not checkpoint-resumable.
- YouTube behavior may change externally.
- No authentication; keep this release local/private.

## Recommendation

ClipGen is ready to be treated as local MVP v1.0.0 after one final manual UAT
with a short local upload and one public YouTube URL.
