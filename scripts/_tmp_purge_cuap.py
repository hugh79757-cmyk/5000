import sqlite3, os, json, sys

DB = "data/travel-en.db"
CUAP_ROOT = "/Users/twinssn/Projects/cuap"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

before = conn.execute("SELECT COUNT(*) FROM cuap_entities").fetchone()[0]
rows = conn.execute("SELECT rowid, blog_id, post_slug, link_label FROM cuap_entities").fetchall()

missing = []
kept = []
for r in rows:
    slug = r["post_slug"]
    blog = r["blog_id"]
    d = os.path.join(CUAP_ROOT, blog, "content", "posts", slug)
    if os.path.isdir(d):
        kept.append((blog, slug))
    else:
        missing.append((r["rowid"], blog, slug, r["link_label"]))

print(f"BEFORE total={before}, on-disk kept={len(kept)}, to-delete={len(missing)}", flush=True)

with open("/tmp/cuap_entities_snapshot_27_01.json", "w") as f:
    json.dump([dict(r) for r in rows], f, ensure_ascii=False, indent=2)

if missing:
    ids = [m[0] for m in missing]
    q = "DELETE FROM cuap_entities WHERE rowid IN (%s)" % ",".join("?" * len(ids))
    conn.execute(q, ids)
    conn.commit()

after = conn.execute("SELECT COUNT(*) FROM cuap_entities").fetchone()[0]
rec = conn.execute("SELECT COUNT(*) FROM cuap_entities WHERE post_slug LIKE '%-rec'").fetchone()[0]
print(f"AFTER total={after}, %-rec rows={rec}", flush=True)
print("KEPT on-disk slugs:", kept, flush=True)
conn.close()
print("DONE", flush=True)
