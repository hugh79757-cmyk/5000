---
phase: 52
plan: 4
subsystem: Blowfish single.html standardization
tags: [blowfish, hugo, adsense, h2-split, single-html]
dependency_graph:
  requires: [52-1, 52-2, 52-3]
  provides: [standardized-single-html]
  affects: [CUAP, STAP, TAP, kuta-hugo, biz-techpawz-hugo, issue-techpawz-hugo]
tech_stack:
  added: []
  patterns: [h2-split-ad-injection]
key_files:
  created: []
  modified:
    - CUAP/{beauty,kitchen,baby,camping,fitness,health,interior,appliance,laptop}-hugo/layouts/_default/single.html
    - kuta-hugo/layouts/_default/single.html
    - biz.techpawz-hugo/layouts/_default/single.html
    - STAP/{finance,dividend,etf,sector,ipo}-hugo/layouts/_default/single.html
    - TAP/{travel,travel1,travel2,travel3,travel4}-hugo/layouts/_default/single.html
    - issue-techpawz-hugo/layouts/_default/single.html
decisions:
  - "pet-hugo already clean (no Description lead) — skipped"
  - "STAP blogs: removed static header in-article ad, replaced with H2-split dynamic injection"
  - "TAP blogs: kept header in-article ad, added H2-split dynamic injection in content div"
  - "issue-techpawz-hugo: removed static content-div in-article ad, replaced with H2-split"
metrics:
  duration: "2m 33s"
  completed: "2026-07-28"
  tasks_completed: 2
  files_modified: 22
---

# Phase 52 Plan 4: single.html 정비 (23개 블로그) Summary

Remove Description lead from 11 Blowfish blogs + add H2 split in-article ad injection to 11 blogs.

## Sub-task 4-1: Description lead 제거 (11개)

Removed `{{ with .Description }}<p class="lead">{{ . }}</p>{{ end }}` from `layouts/_default/single.html`.

**Blogs modified (11):**
| Blog | Repo | Commit |
|------|------|--------|
| beauty-hugo | CUAP/beauty-hugo | 8769377 |
| kitchen-hugo | CUAP/kitchen-hugo | 95812a3 |
| baby-hugo | CUAP/baby-hugo | b18e981 |
| camping-hugo | CUAP/camping-hugo | ca297a7 |
| fitness-hugo | CUAP/fitness-hugo | 2415355 |
| health-hugo | CUAP/health-hugo | 002ea2f |
| interior-hugo | CUAP/interior-hugo | 32ca0f6 |
| appliance-hugo | CUAP/appliance-hugo | 3de3f15 |
| laptop-hugo | CUAP/laptop-hugo | 4864f89 |
| kuta-hugo | kuta-hugo | 025d2b4 |
| biz.techpawz-hugo | biz.techpawz-hugo | 5f5797d |

**Skipped:** pet-hugo (no Description lead line present — already clean)

## Sub-task 4-2: H2 분할 인젝션 추가 (11개)

Added H2-based in-article ad injection to `layouts/_default/single.html`. Replaces raw `{{ .Content }}` / `{{ .Content | safeHTML }}` with split logic that injects ads based on content structure.

**Ad injection rules:**
- H2 exists + < 800 chars → 2 injections (after lead + after 1st H2)
- H2 exists + >= 800 chars → 3 injections (after lead + after 1st H2 + after 3rd H2)
- No H2 → 1 injection (after lead)

**Blogs modified (11):**
| Blog | Repo | Commit |
|------|------|--------|
| finance-hugo | STAP/finance-hugo | f88577b |
| dividend-hugo | STAP/dividend-hugo | 6f6a0a0 |
| etf-hugo | STAP/etf-hugo | f0bbc79 |
| sector-hugo | STAP/sector-hugo | d3a023c |
| ipo-hugo | STAP/ipo-hugo | d0cce7b |
| travel-hugo | TAP/travel-hugo | ecac41b |
| travel1-hugo | TAP/travel1-hugo | 868fde0 |
| travel2-hugo | TAP/travel2-hugo | a67539f |
| travel3-hugo | TAP/travel3-hugo | 14e2ce9 |
| travel4-hugo | TAP/travel4-hugo | 2fefbd0 |
| issue-techpawz-hugo | issue-techpawz-hugo | 7350789 |

**Structural changes per blog group:**
- **STAP 5:** Removed static `adsense/in-article.html` from header, added H2 split in content div
- **TAP 5:** Kept header `adsense/in-article.html`, added H2 split in content div
- **issue-techpawz-hugo:** Removed static `adsense/in-article.html` from content div, added H2 split

## Deviations from Plan

### Auto-fixed Issues

None — plan executed as written.

### Skipped Blogs

- **pet-hugo** (4-1): Description lead was already absent. Plan listed 12 blogs for 4-1, only 11 needed modification.

## Known Stubs

None.

## Threat Flags

None — no new security-relevant surface introduced.

## Self-Check: PASSED

- [✅] 11 blogs had Description lead removed (verified via grep)
- [✅] 11 blogs have H2 split logic (verified via grep for `h2parts`)
- [✅] All 22 commits exist in respective repos
- [✅] No old `{{ .Content }}` patterns remain in modified blogs
