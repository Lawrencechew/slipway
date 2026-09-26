# GitHub Rename Checklist (Owner-Only)

Use this checklist after reviewing local changes and before public release.

1. Rename GitHub repository slug from `pavedpath` to `slipway`.
2. Verify repository redirect works for old URLs.
3. Update README badge/link URLs from `.../pavedpath/...` to `.../slipway/...`.
4. Confirm Actions workflow path remains `.github/workflows/ci.yml` after rename.
5. Update local clone remotes if needed:
   - `git remote -v`
   - `git remote set-url origin <new-slipway-url>`
6. Re-run CI on first push to renamed repo and confirm green.
7. Set repository visibility to Public (if not already).
8. Create tag `v1.0.0` and publish release notes from `CHANGELOG.md` and `PUBLIC_V1_REPORT.md`.
