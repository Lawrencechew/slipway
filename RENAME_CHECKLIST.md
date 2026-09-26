# GitHub Rename Checklist (Completed)

Completed actions:

1. Renamed GitHub repository slug from `pavedpath` to `slipway`.
2. Verified repository redirect from old URLs.
3. Updated README badge/link URLs from `.../pavedpath/...` to `.../slipway/...`.
4. Confirmed Actions workflow path remains `.github/workflows/ci.yml`.
5. Updated local clone remote:
   - `git remote -v`
   - `git remote set-url origin https://github.com/Lawrencechew/slipway.git`
6. Re-ran CI on the renamed repository and verified green.
7. Set repository visibility to Public.

Remaining owner release step:

- Create tag `v1.0.0` and publish release notes from `CHANGELOG.md` and `PUBLIC_V1_REPORT.md`.
