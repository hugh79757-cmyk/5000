---
name: gate-integrity
description: Use when a quality gate reports a pass rate, before trusting it
---

# Gate Integrity

A reported pass rate is a claim, not a fact. Before trusting any quality gate
("94% pass", "all checks green", "X/Y passed"), verify the number was produced
honestly. A pass rate is only meaningful if the criteria that define "pass" are
themselves honest and unchanging.

> Top principle: Verify first whether the checker is measuring truth or merely
> its own internal consistency. A gate that passes only because its own
> comparison inputs happen to be empty/equal is not validating reality — it is
> confirming self-consistency.

> Key sentence: A 94% pass rate is trustworthy only if the criteria that define
> "pass" are honest — a high number earned by weakening the bar is not a pass,
> it is theater. Never lower the threshold to make the gate look good.

## When to use

- A pipeline, test suite, audit, or review reports a pass/fail rate.
- A "green" status is used as justification for shipping, merging, or closing.
- You are about to report or act on a gate result.

## Steps

1. **Read the gate definition.** Find the actual rule that decides pass vs. fail.
   What exactly is being checked? A number with no readable criterion is not a
   gate — it is a slogan.

2. **Verify the population.** How many items were in scope, and were any
   excluded, skipped, or silently dropped before counting? The denominator
   matters as much as the numerator.

3. **Check for reclassification.** Confirm failing items were not relabeled
   ("partial", "known issue", "N/A") to keep them out of the fail bucket.
   Reclassification that shrinks the fail set is the most common way gates lie.

4. **Confirm the threshold was not lowered.** The pass bar must be the same one
   agreed before the run. A threshold changed after the fact to lift the rate is
   invalid — restore the original bar and re-measure.

5. **Report the honest rate with its criteria.** State the pass rate together
   with the exact criterion and population used, so the reader can judge it.
   If the criteria were weakened, say so explicitly rather than reporting a
   prettier number.

6. **Watch for empty-value matches.** A check that compares two values can pass
   simply because both sides are empty/null/None — e.g. an `og:image` gate that
   passes when `expected == actual == None` (C08 style). That is not a real
   pass: it is "both missing, therefore equal." Treat empty-vs-empty equality as
   an unknown, not a success, unless the gate explicitly exists to assert
   absence.

## Rule

Do not lower the gate threshold to improve the reported pass rate. If the bar
must change, change it openly before the next run and re-state it; never
retro-fit a lower bar onto an existing result.

A threshold raised by +10 is also not a "pass" — it is a relaxed review
standard. If a gate loosens its bar and the rate rises, label it "review
relaxed," not "pass improved." The pass/fail meaning is unchanged; only the
compared baseline moved.

If a measured value differs between two reports, separate the cause before
trusting either number: was it a content change (the thing under test moved),
or a calculator/method change (the measuring tool moved)? Example: a gate
reports 488/408 in one run and 430/400 in another, or a Hugo JSON-LD gate shows
359 — if the extraction method changed between runs, the two numbers are not
comparable and must not be trended together. State which one moved.

## R23 Lock
- Code: `shared/publishers/deploy.py:58` — `deploy_site` checks `approval_status` before Hugo/wrangler. If not APPROVED, returns False without build/deploy. Skill references this file:line, prose does not duplicate logic.

## 절차 규칙 (2026-08-21)
- 게이트가 막으면 예외를 파기 전에 커밋 범위부터 좁힌다.
- 대상 값이 부재일 때의 반환값을 규칙마다 확인하고 부재는 통과가 아니라 해당없음으로 집계한다.
- 소스 파일에서 렌더 결과(광고·어필리에이트·메타)를 판정하지 않는다.
