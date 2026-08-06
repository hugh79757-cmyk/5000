# stash 후속 큐 (2026-08-07)

## 보관 정책
- stash@{0}, stash@{1}은 **drop하지 않음** (보류분·미완성 WIP 포함, 현행 코드와 충돌 가능).
- 대신 diff를 아래 아카이브에 보존:
  - `data/stash-archive/stash-0-fd016b3a3.diff`
  - `data/stash-archive/stash-1-c0df11b38.diff`

## stash@{0} (fd016b3a3) 보류분
- `pipelines/curation/pipeline.py`: `_improve_readability` / `_improve_readability_preserving_structure` 신규 추가(+151). 적용 시 신규 기능 삽입 → 별도 검토 후 결정.
- `pipelines/curation/keywords.py`: 키워드 교체(갤럭시→갤럭시북/그램 변형 등) 및 fitness/pet 키워드 추가. 현재 키워드 풀(e28f9e1d7 이후)과 정합성 확인 필요.
- `pipelines/car/pipeline.py`: source_id에 uuid 기반 고유접미사 추가. duplicate_source_id 방지 목적이나, 현행 source_id 정책과 충돌 여부 확인 필요.
- `pipelines/travel/*`, `pipelines/stock/*`, `pipelines/senior/*`, `pipelines/rap/pipeline.py`, `shared/publisher.py`: multi-pipeline WIP. 각 파이프라인 최신 상태와 대조 필요.

## stash@{1} (c0df11b38) 보류분
- `pipelines/travel/writer.py`: H2/H3 탐지를 마크다운 `#`에서 HTML `<h2`/`<h3`으로 변경, 이미지 삽입을 `![]()`에서 `<figure class="wp-block-image"><img>`로 변경, `_validate_and_retry`에 메타응답/중복도입부 감지 추가. 여행 파이프라인 현행 구조와 정합성 확인 필요.
- `scripts/phase8/delete_flagged_posts.py`: rollback_deletions() 추가.
- `pipelines/curation/pipeline.py`: CATEGORY_FILTERS 반려동물/뷰티/화장품 관련 확장.

## stash@{1} 적용 금지 항목 (이번 실증과 충돌)
- `dispatcher.py`: `wrangler deploy --config wrangler.toml` → `wrangler deploy` 변경은 **적용 금지**. 이번 작업 3-3에서 `--config`로 Workers 3건(camping/health/pet) 정상 배포 확인됨(assets 업로드 포함).
- `AGENTS.md`: wrangler `--config` + `[assets]` 버그 문서화는 **현재 사실과 다름**. 이번 배포에서 `--config` 사용 시 assets 정상 처리됨. 문서 갱신 시 이 점을 반영하거나 해당 문서 제거 필요.

## 폐기 대상 (아카이브 완료, drop은 보류)
- stash@{0}: `data/cooldown.json`, `data/failure_count.json` (stale 데이터)
- stash@{1}: `scripts/phase8/flagged_posts.yaml` (구경로 `/Users/twinssn/Projects/CUAP/...`, 현재 구조와 불일치)

## 참고
- stash@{0} 유효/참고: `.planning/triage/INDEX.md`(+1), `STATE.md`(+1 Phase 52 완료 표시)
