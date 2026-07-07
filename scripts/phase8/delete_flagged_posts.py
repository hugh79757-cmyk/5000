#!/usr/bin/env python3
"""
Phase 8-3: Batch deletion of flagged off-topic posts.
Reads flagged_posts.yaml and moves flagged posts to backup directory.
"""

import os
import sys
import yaml
import shutil
import argparse
from datetime import datetime
from pathlib import Path

CUAP_ROOT = "/Users/twinssn/Projects/CUAP"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FLAGGED_FILE = os.path.join(SCRIPT_DIR, "flagged_posts.yaml")
BACKUP_DIR = os.path.join(SCRIPT_DIR, "deleted")
LOG_FILE = os.path.join(SCRIPT_DIR, "deletion_log.yaml")


def load_flagged_posts():
    """Load flagged posts from YAML file"""
    if not os.path.exists(FLAGGED_FILE):
        print(f"[ERROR] Flagged posts file not found: {FLAGGED_FILE}")
        sys.exit(1)
    
    with open(FLAGGED_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    return data.get('body_offtopic', [])


def create_backup_dir():
    """Create backup directory with timestamp"""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def delete_post(post, dry_run=True):
    """
    Move a flagged post to backup directory.
    Returns (success, backup_path)
    """
    blog = post.get('blog', '')
    slug = post.get('slug', '')
    path = post.get('path', '')
    
    if not path or not os.path.exists(path):
        return False, f"Path not found: {path}"
    
    # Create backup path: deleted/{blog}/{slug}_{timestamp}/
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_subdir = os.path.join(BACKUP_DIR, blog)
    backup_name = f"{slug}_{timestamp}"
    backup_path = os.path.join(backup_subdir, backup_name)
    
    if dry_run:
        print(f"  [DRY-RUN] Would move: {path}")
        print(f"  [DRY-RUN] To: {backup_path}")
        return True, backup_path
    
    try:
        # Create backup directory
        os.makedirs(backup_subdir, exist_ok=True)
        
        # Move the post directory
        shutil.move(path, backup_path)
        print(f"  [MOVED] {path}")
        print(f"  [MOVED] To: {backup_path}")
        return True, backup_path
        
    except Exception as e:
        print(f"  [ERROR] Failed to move {path}: {e}")
        return False, str(e)


def save_deletion_log(deletions, dry_run=True):
    """Save deletion log to YAML file"""
    if dry_run:
        print(f"\n[DRY-RUN] Would save deletion log to: {LOG_FILE}")
        return
    
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'total_deleted': len(deletions),
        'deletions': deletions
    }
    
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(log_data, f, allow_unicode=True, default_flow_style=False)
    
    print(f"\n[LOG] Deletion log saved to: {LOG_FILE}")


def main():
    parser = argparse.ArgumentParser(description="Phase 8-3: Batch deletion of flagged posts")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Dry run mode - no actual deletion (default)")
    parser.add_argument("--execute", action="store_true",
                        help="Actually delete posts (overrides --dry-run)")
    parser.add_argument("--blog", type=str, default=None,
                        help="Only delete posts from this blog")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of posts to delete")
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if dry_run:
        print("=" * 60)
        print("PHASE 8-3: BATCH DELETION (DRY-RUN MODE)")
        print("=" * 60)
        print("No posts will be deleted. Use --execute to actually delete.")
        print()
    else:
        print("=" * 60)
        print("PHASE 8-3: BATCH DELETION (EXECUTE MODE)")
        print("=" * 60)
        print("WARNING: This will actually delete posts!")
        print()
    
    # Load flagged posts
    flagged_posts = load_flagged_posts()
    
    if not flagged_posts:
        print("[INFO] No flagged posts to delete.")
        return
    
    # Filter by blog if specified
    if args.blog:
        flagged_posts = [p for p in flagged_posts if p.get('blog') == args.blog]
        print(f"[INFO] Filtered to blog: {args.blog}")
    
    # Apply limit if specified
    if args.limit:
        flagged_posts = flagged_posts[:args.limit]
        print(f"[INFO] Limited to {args.limit} posts")
    
    print(f"\n[INFO] Found {len(flagged_posts)} flagged posts to delete")
    print()
    
    # Create backup directory
    create_backup_dir()
    
    # Process each post
    deletions = []
    success_count = 0
    fail_count = 0
    
    for i, post in enumerate(flagged_posts, 1):
        blog = post.get('blog', '')
        slug = post.get('slug', '')
        title = post.get('title', '')
        reason = post.get('reason', '')
        
        print(f"[{i}/{len(flagged_posts)}] {blog}/{slug}")
        print(f"  Title: {title}")
        print(f"  Reason: {reason}")
        
        success, backup_path = delete_post(post, dry_run=dry_run)
        
        deletion_record = {
            'blog': blog,
            'slug': slug,
            'title': title,
            'reason': reason,
            'original_path': post.get('path', ''),
            'backup_path': backup_path,
            'success': success,
            'timestamp': datetime.now().isoformat()
        }
        deletions.append(deletion_record)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total posts processed: {len(flagged_posts)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {fail_count}")
    print()
    
    # Save deletion log
    save_deletion_log(deletions, dry_run=dry_run)
    
    if dry_run:
        print("\n[DRY-RUN] No posts were actually deleted.")
        print("Run with --execute to actually delete posts.")
    else:
        print("\n[EXECUTE] Posts have been moved to backup directory.")
        print(f"Backup location: {BACKUP_DIR}")


if __name__ == "__main__":
    main()
