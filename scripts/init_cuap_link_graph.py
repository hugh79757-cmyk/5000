"""init_cuap_link_graph.py — CROSS_GRAPH 데이터를 cuap_link_graph 테이블에 주입.

실행: python3 scripts/init_cuap_link_graph.py
"""
import sqlite3

from shared.cuap_entity_linker import CROSS_GRAPH, init_cuap_tables, _get_db, DB_PATH


def main():
    init_cuap_tables()
    conn = _get_db()
    try:
        for blog_id, connections in CROSS_GRAPH.items():
            for target in connections.get("primary", []):
                conn.execute(
                    "INSERT OR IGNORE INTO cuap_link_graph "
                    "(source_blog, target_blog, link_type, weight) VALUES (?, ?, 'primary', 100)",
                    (blog_id, target),
                )
            for target in connections.get("secondary", []):
                conn.execute(
                    "INSERT OR IGNORE INTO cuap_link_graph "
                    "(source_blog, target_blog, link_type, weight) VALUES (?, ?, 'secondary', 50)",
                    (blog_id, target),
                )
            for target in connections.get("use_cases", []):
                conn.execute(
                    "INSERT OR IGNORE INTO cuap_link_graph "
                    "(source_blog, target_blog, link_type, weight) VALUES (?, ?, 'use_cases', 30)",
                    (blog_id, target),
                )
        conn.commit()
    finally:
        conn.close()
    print("cuap_link_graph initialized")


if __name__ == "__main__":
    main()
