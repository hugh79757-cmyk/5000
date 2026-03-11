import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.content_store import init_db

if __name__ == "__main__":
    init_db()
    print("content.db initialized at data/content.db")
