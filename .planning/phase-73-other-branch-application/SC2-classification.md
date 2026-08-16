# Phase 73 SC-2 — G3 Refuted + TAP N/A Classification

## G3 "wrangler token leak" premise: REFUTED

The G3 hypothesis claimed a `CLOUDFLARE_API_TOKEN` leak to the grandchild
wrangler process during STAP/TAP subprocess execution. Re-verification shows
this does not occur:

Evidence (grep/read):
1. `shared/subprocess_runner.py:98` —
   `"os.environ.pop('CLOUDFLARE_API_TOKEN', None)"` runs inside the child
   runner script (before `fn(cfg)` is invoked), stripping the token
   in-process.
2. `STAP/shared/publisher.py:297` — `subprocess.run([_WRANGLER_BIN, "pages", "deploy", ...])`
   passes **no `env=`** argument, so the grandchild wrangler inherits the
   already-stripped `os.environ` from the child runner. No token reaches it.
3. `grep env= STAP/shared/publisher.py` → 0 lines with `env=` near the
   wrangler call, confirming inheritance of the stripped environment.

Conclusion: G3 premise is false; no token leak for STAP/TAP via this path.

## TAP classification: N/A (Blogger.com only)

TAP publishes to Blogger.com via XML-RPC / Blogger API. It has no local Hugo
build, no wrangler, and no Pages deploy.

Evidence:
- `sed -n '602,720p' TAP/app.py | grep -c "wrangler\|hugo\|pages deploy"` → **0**
  (run_publish, lines 602–720, contains no Hugo/wrangler/Pages-deploy refs).

Conclusion: Phase 72 Hugo / frontmatter / THUMBNAIL / deploy checks are
**N/A** for TAP. Do not apply Hugo-frontmatter fixes to TAP.
