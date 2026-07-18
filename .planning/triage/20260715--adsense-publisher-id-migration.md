# AdSense Publisher ID Migration (`ca-pub-8772455780561463`)

## Summary

All Hugo blog sites across CUAP/RAP/SEAP/CAP/informationhot/STAP had their AdSense publisher ID standardized from `ca-pub-6677996696534146` → `ca-pub-8772455780561463`. SEAP senior-hugo additionally received the missing AdSense script tag in `extend-head.html`.

## Changes Applied

| Project | Sites | Files Changed | Change Type |
|---------|-------|---------------|-------------|
| **CUAP** | 10 sites (`appliance, baby, beauty, camping, fitness, health, interior, kitchen, laptop, pet`) | `config/_default/params.toml` (`clientID`), plus `layouts/partials/extend-head.html` (5 sites with hardcoded pub ID) | params.toml + layout |
| **RAP** | 5 sites (`rap-hugo`~`rap5-hugo`) | `adsense/*.html` (4 files) + `extend-head.html` | layout |
| **SEAP** | 1 site (`senior-hugo`) | `adsense/*.html` (3 files) + `extend-head.html` | layout + **AdSense script tag 추가** |
| **CAP** | 2 sites (`pick-hugo`, `rank-hugo`) | `baseof.html` + `adsense/*.html` (5 files) | layout |
| **informationhot** | 1 site | `extend-head.html` + `adsense*` (variants + `adsense/` dir) | layout |
| **STAP** | 1 site (`stock-hugo`) | `extend-head.html` + `single.html` | layout |

## Notable Details

- **SEAP senior-hugo**: `extend-head.html` had only Kakao SDK — the AdSense `<script>` tag was **missing entirely**. Added the standard async tag before Kakao SDK.
- **CUAP 5 sites** (appliance, baby, fitness, interior, laptop): Had the old pub ID **both** in `params.toml` (via config) **and** hardcoded in `extend-head.html`. Both were fixed.
- **RAP public/ dirs**: Contain old pub ID in built HTML — these are Hugo build artifacts, resolved on next `hugo` build.
- **informationhot-hugo**: Has multiple ad partial variants (`.html`, `.html.v1.5`, hyphen variants) — all updated.

## Scope Exclusions

- **ETAP** (37 tpembars.com sites): No AdSense — out of scope
- **ETAP tech-publisher** sites (techpawz, issue-techpawz, info.techpawz, biz.techpawz): Done in a prior session
- **GAP** / **funstaurant-hugo**: No AdSense at all — out of scope

## Verification

After fix, `grep -rl "ca-pub-6677996696534146" {all projects}/layouts/` returns **zero results** across all source files.
