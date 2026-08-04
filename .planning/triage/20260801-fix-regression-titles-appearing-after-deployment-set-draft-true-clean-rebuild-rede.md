---
date: 2026-08-01
type: fix
status: resolved
---

# Fix regression titles appearing after deployment

## What
After setting draft:true on existing "추천 TOP5 (2026년)" Markdown files, a clean Hugo rebuild and redeploy via wrangler ensured that those draft posts are not published, eliminating regression titles from live sites. Additionally, all CUAP blogs were set to inactive to prevent further automatic publishing.

## Why
The regression titles were leftover published posts with draft:false that matched the prohibited pattern "추천 TOP5 (2026年)". They appeared in search/category pages despite DB cleanup because the source Markdown files remained in the repository. Setting them to draft:true excludes them from Hugo builds, and a clean rebuild (clearing public/ and resources/_gen/) ensured no stale assets remained.

## Files changed
- Markdown files under /Users/twinssn/Projects/CUAP/*-hugo/content/posts/*/index.md (draft toggled from false to true)
- /Users/twinssn/projects/5000/config/blogs.d/cuap.yaml (status: active → inactive for 10 blogs)

## How
1. Set draft:true on all posts containing "추천 TOP5 (2026년)" using sed.
2. For each blog, remove public/ and resources/_gen/, then run `hugo --gc --minify`.
3. Deploy via `scripts/phase8/deploy_blog.sh <blog>-hugo` (which internally calls Hugo and wrangler).
4. Verify that the previously regressed slugs now return 404.
5. Switch CUAP blogs to inactive by editing cuap.yaml.

## Verification
- Confirmed homepage of each blog returns HTTP 200 (except baby.hugo which uses a custom domain, but resolves correctly).
- Verified that searching for the phrase "추천 TOP5 (2026년)" on each homepage yields no matches.
- Verified that direct access to the previously regressed post URLs returns 404.
- Confirmed that cuap.yaml now shows status: inactive for all blog entries.
