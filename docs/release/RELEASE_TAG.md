# Release Tag — Mythos Aegis v0.4.0

Run these commands from the repo root after all CI checks pass.

---

## Pre-tag checklist

- [ ] `git status` is clean (no uncommitted changes)
- [ ] All three CI workflows pass on `main` (CI, Docker, Security)
- [ ] `pytest --cov=app --cov-fail-under=80` passes locally
- [ ] `cd apps/admin && npm run build` succeeds
- [ ] `./scripts/verify.sh --security` passes (Linux/macOS) or `.\scripts\verify.ps1 -Security` (Windows)
- [ ] `.env` is NOT committed (`.gitignore` confirms)
- [ ] `CHANGELOG.md` is up to date

---

## Tag and push

```bash
# Annotated tag — includes tagger identity and message in git log
git tag -a v0.4.0 -m "Mythos Aegis v0.4.0 — Multi-tenant AI SaaS platform

- RAG, Vision, Agent, Billing, Workflow
- Next.js 15 admin console with 10 console routes
- 926 tests, 89% coverage, mypy + ruff clean
- JWT RBAC, CORS, rate limiting, non-root Docker
- docs/DEMO.md: 15-minute demo walkthrough"

# Verify the tag
git show v0.4.0 --stat

# Push tag to remote
git push origin v0.4.0

# Push branch (if not already pushed)
git push origin main
```

---

## After tagging

```bash
# Confirm tag is on remote
git ls-remote --tags origin

# Build the release image
docker build -t mythos-aegis:0.4.0 -t mythos-aegis:latest .

# Smoke-test the image
docker run --rm --entrypoint whoami mythos-aegis:0.4.0
# Expected: appuser
```

---

## GitHub release (optional)

```bash
# Using GitHub CLI
gh release create v0.4.0 \
  --title "Mythos Aegis v0.4.0" \
  --notes-file docs/release/RELEASE_NOTES.md \
  --latest
```

---

## If you need to retag

```bash
# Delete local tag and recreate
git tag -d v0.4.0
git push origin :refs/tags/v0.4.0   # delete remote tag
# Then re-run the tag command above
```
