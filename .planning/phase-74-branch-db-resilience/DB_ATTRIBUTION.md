# Phase 74 Wave 2 - 26-DB Attribution Table

Generated: 26 `data/*.db` files attributed per RESEARCH.md Deliverable 1.

| # | DB file | Class | Where covered | Notes |
|---|---|---|---|---|
| 1 | `5000_content.db` | B | DB_TARGETS (backup) | DB_TARGETS 5000; legacy/secondary |
| 2 | `analytics.db` | C | DB_TARGETS (backup) | DB_TARGETS 5000; derived, drop+reinit safe |
| 3 | `car.db` | A | DB_TARGETS (backup) | DB_TARGETS 5000; re-collectable |
| 4 | `content.db` | B | DB_TARGETS (backup) | DB_TARGETS 5000; central ledger |
| 5 | `course.db` | A | DB_TARGETS (backup) | ADDED Wave2; DB_TARGETS 5000 |
| 6 | `cuap.db` | C | orphan (intentional exclusion, documented) | NOT backed: unused alias of curation.db |
| 7 | `cuap_entities.db` | C | class-C self-heal (intentional, not backed) | NOT backed: cuap_entity_linker.py bootstrap self-heals |
| 8 | `curation.db` | B | DB_TARGETS (backup) | DB_TARGETS 5000; CUAP ledger |
| 9 | `curation_cache.db` | C | orphan (intentional exclusion, documented) | NOT backed: cache, regenerable |
| 10 | `dashboard.db` | C | orphan (intentional exclusion, documented) | NOT backed: unused, data/dashboard/ uses other DBs |
| 11 | `festival.db` | A | DB_TARGETS (backup) | DB_TARGETS 5000 |
| 12 | `gap.db` | A | DB_TARGETS (backup) | ADDED Wave2; DB_TARGETS 5000 |
| 13 | `indexnow.db` | C | class-C self-heal (intentional, not backed) | NOT backed: SAP/data/indexnow.db backed instead; 5000/data/indexnow.db self-heals via init_db() |
| 14 | `ledger.db` | C | orphan (intentional exclusion, documented) | NOT backed: unused, content.db is real ledger |
| 15 | `mc_chains.db` | C | class-C self-heal (intentional, not backed) | NOT backed: regenerable if chain source retained (RESEARCH OQ) |
| 16 | `metrics.db` | C | class-C self-heal (intentional, not backed) | NOT backed: metrics.py bootstrap self-heals |
| 17 | `ops.db` | C | class-C self-heal (intentional, not backed) | NOT backed: ops_dashboard/db.py init_db() self-heals |
| 18 | `publish_ledger.db` | C | orphan (intentional exclusion, documented) | NOT backed: legacy; content.db holds live publish_ledger |
| 19 | `quality.db` | C | class-C self-heal (intentional, not backed) | NOT backed: quality_recorder.py bootstrap self-heals |
| 20 | `rap.db` | A | DB_TARGETS (backup) | DB_TARGETS 5000; self-bootstraps |
| 21 | `scanner.db` | C | DB_TARGETS (backup) | DB_TARGETS 5000; self-heal |
| 22 | `senior.db` | A | DB_TARGETS (backup) | ADDED Wave2; DB_TARGETS 5000 |
| 23 | `stap_content.db` | B | DB_TARGETS (backup) | DB_TARGETS 5000 (STAP path); class B ledger |
| 24 | `stock.db` | A | DB_TARGETS (backup) | DB_TARGETS 5000 (5000/data/stock.db metrics) |
| 25 | `travel-en.db` | A | DB_TARGETS (backup) | DB_TARGETS 5000; ETAP entity store |
| 26 | `wiki.db` | C | orphan (intentional exclusion, documented) | NOT backed: unused, no opener in repo |

## Summary

- Total `data/*.db`: **26**
- Backup list (DB_TARGETS): **14**
- Class-C self-heal (intentional, not backed): **6**
- Orphan (intentional exclusion, documented): **6**
- Class-A present: **8** (car.db, course.db, festival.db, gap.db, rap.db, senior.db, stock.db, travel-en.db)
- **Class-A unbacked: 0** (must be 0)

All 26 files are attributed. No class-A DB remains unbacked. self-heal/orphan exclusions
are intentional per RESEARCH.md D1/D5 (class-C regenerable, orphans unused).