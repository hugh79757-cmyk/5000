---
date: 2026-08-01
---

# What
- CUAP blogs were left active, causing unnecessary processing and potential noise in logs.

# Why
- Needed to reduce system load and focus on active pipelines; leaving them active could waste resources and generate redundant data.

# How
- Edited `/Users/twinssn/Projects/5000/config/blogs.d/cuap.yaml` and set `status: inactive` for each blog entry under the `blogs:` list.

# Validation
- Verified that the scheduler logs show no CUAP blog activity after the change.
- Confirmed that no new posts appear in the CUAP blogs' public endpoints.

# Risks
- If any downstream process or monitoring expects those blogs to be active, they may need to be re‑activated.
- Manual reactivation will be required if the blogs are needed again in the future.
