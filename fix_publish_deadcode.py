#!/usr/bin/env python3
"""curation/pipeline.py 의 publish 구간 dead-code / 잘못된 인덴트 수정.

BEFORE (버그): _record_failure + return 이 if 바깥 → 항상 실패 반환, 이후 전부 dead
AFTER (정상):  실패 시에만 기록/return, 성공 시 아래 로직으로 계속 진행
"""
import re, shutil, datetime, sys

FP = "pipelines/curation/pipeline.py"
src = open(FP, encoding="utf-8").read()

BUGGY = (
    '    result = publish(blog_id, title, body_md, category="추천", tags=tags_str, thumbnail_url=thumbnail_url, is_draft=is_draft)\n'
    '    if not result or not result.get("success"):\n'
    '        logger.error(f"[{blog_id}] 발행 실패: {title}")\n'
    '    _record_failure(blog_id, "publish_error", f"Hugo 발행 실패: {title}", keyword)\n'
    '    return {"success": False, "reason": "publish_error"}\n'
)

FIXED = (
    '    result = publish(blog_id, title, body_md, category="추천", tags=tags_str, thumbnail_url=thumbnail_url, is_draft=is_draft)\n'
    '    if not result or not result.get("success"):\n'
    '        logger.error(f"[{blog_id}] 발행 실패: {title}")\n'
    '        _record_failure(blog_id, "publish_error", f"Hugo 발행 실패: {title}", keyword)\n'
    '        return {"success": False, "reason": "publish_error"}\n'
)

if BUGGY not in src:
    print("[SKIP] 예상한 버그 패턴을 못 찾음. 파일이 이미 수정됐거나 공백이 다릅니다.")
    print("       수동 확인: grep -n 'publish_error' " + FP)
    sys.exit(1)

ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
shutil.copy(FP, f"{FP}.bak_{ts}")
src = src.replace(BUGGY, FIXED, 1)
open(FP, "w", encoding="utf-8").write(src)

# 구문 검증
import ast
ast.parse(src)
print(f"[OK] 수정 완료. 백업: {FP}.bak_{ts}")
print("     이제 성공 시 _record_products / 엔티티 등록 / success=True 반환이 정상 도달합니다.")
