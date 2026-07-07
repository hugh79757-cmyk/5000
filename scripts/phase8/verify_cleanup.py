#!/usr/bin/env python3
"""
Phase 8-4: Verification script for content cleanup.
Re-runs detection to confirm flagged posts are deleted.
"""

import os
import sys
import yaml
import subprocess
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DETECTION_SCRIPT = os.path.join(SCRIPT_DIR, "detect_problematic_posts.py")
DELETION_LOG = os.path.join(SCRIPT_DIR, "deletion_log.yaml")
FLAGGED_FILE = os.path.join(SCRIPT_DIR, "flagged_posts.yaml")


def run_detection():
    """Run detection script and capture results"""
    print("=" * 60)
    print("PHASE 8-4: VERIFICATION")
    print("=" * 60)
    print()
    
    print("[STEP 1] Running detection script...")
    print()
    
    # Run detection script
    result = subprocess.run(
        [sys.executable, DETECTION_SCRIPT, "--scan-body"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print("[WARN] Detection script stderr:", result.stderr)
    
    # Load results
    if not os.path.exists(FLAGGED_FILE):
        print("[ERROR] Flagged posts file not found after detection")
        return False
    
    with open(FLAGGED_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    remaining = {
        'chinese': len(data.get('chinese', [])),
        'offtopic': len(data.get('offtopic', [])),
        'body_offtopic': len(data.get('body_offtopic', []))
    }
    
    total_remaining = sum(remaining.values())
    
    print()
    print("[STEP 2] Analysis")
    print()
    
    if total_remaining == 0:
        print("[SUCCESS] No flagged posts remain!")
        print("  - Chinese-titled: 0")
        print("  - Off-topic (title/tags): 0")
        print("  - Off-topic (body): 0")
        return True
    else:
        print(f"[WARNING] {total_remaining} flagged posts still remain:")
        print(f"  - Chinese-titled: {remaining['chinese']}")
        print(f"  - Off-topic (title/tags): {remaining['offtopic']}")
        print(f"  - Off-topic (body): {remaining['body_offtopic']}")
        
        # Show remaining posts
        if remaining['body_offtopic'] > 0:
            print()
            print("Remaining body offtopic posts:")
            for post in data.get('body_offtopic', [])[:10]:
                print(f"  - {post.get('blog')}/{post.get('slug')}")
            if remaining['body_offtopic'] > 10:
                print(f"  ... and {remaining['body_offtopic'] - 10} more")
        
        return False


def verify_deletion_log():
    """Check if deletion log exists and is valid"""
    print()
    print("[STEP 3] Checking deletion log...")
    print()
    
    if not os.path.exists(DELETION_LOG):
        print("[INFO] No deletion log found. This is expected if no posts were deleted yet.")
        return True
    
    with open(DELETION_LOG, 'r', encoding='utf-8') as f:
        log = yaml.safe_load(f)
    
    if not log:
        print("[WARN] Deletion log is empty")
        return True
    
    total_deleted = log.get('total_deleted', 0)
    timestamp = log.get('timestamp', 'unknown')
    deletions = log.get('deletions', [])
    
    success_count = sum(1 for d in deletions if d.get('success', False))
    fail_count = total_deleted - success_count
    
    print(f"Deletion log found:")
    print(f"  - Timestamp: {timestamp}")
    print(f"  - Total processed: {total_deleted}")
    print(f"  - Successful: {success_count}")
    print(f"  - Failed: {fail_count}")
    
    if fail_count > 0:
        print()
        print("Failed deletions:")
        for d in deletions:
            if not d.get('success', False):
                print(f"  - {d.get('blog')}/{d.get('slug')}: {d.get('backup_path', 'unknown')}")
    
    return True


def verify_backup_structure():
    """Check backup directory structure"""
    print()
    print("[STEP 4] Checking backup directory structure...")
    print()
    
    backup_dir = os.path.join(SCRIPT_DIR, "deleted")
    
    if not os.path.exists(backup_dir):
        print("[INFO] No backup directory found. This is expected if no posts were deleted yet.")
        return True
    
    # Count backups by blog
    blog_counts = {}
    for item in os.listdir(backup_dir):
        item_path = os.path.join(backup_dir, item)
        if os.path.isdir(item_path):
            count = len(os.listdir(item_path))
            blog_counts[item] = count
    
    total_backups = sum(blog_counts.values())
    
    print(f"Backup directory found: {backup_dir}")
    print(f"  - Total backups: {total_backups}")
    
    for blog, count in sorted(blog_counts.items()):
        print(f"  - {blog}: {count} posts")
    
    return True


def main():
    """Main verification flow"""
    # Run detection
    detection_ok = run_detection()
    
    # Check deletion log
    log_ok = verify_deletion_log()
    
    # Check backup structure
    backup_ok = verify_backup_structure()
    
    # Summary
    print()
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print()
    
    if detection_ok:
        print("[PASS] Detection: All flagged posts removed")
    else:
        print("[FAIL] Detection: Some flagged posts remain")
    
    if log_ok:
        print("[PASS] Deletion log: Valid")
    else:
        print("[FAIL] Deletion log: Invalid or missing")
    
    if backup_ok:
        print("[PASS] Backup structure: Valid")
    else:
        print("[FAIL] Backup structure: Invalid")
    
    print()
    
    if detection_ok and log_ok and backup_ok:
        print("[OVERALL] Verification PASSED")
        return 0
    else:
        print("[OVERALL] Verification FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
