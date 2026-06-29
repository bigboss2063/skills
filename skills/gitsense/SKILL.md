---
name: gitsense
description: "AI-powered open source contribution finder and repo radar — ported from GitSense (he-yufeng/GitSense). Discovers GitHub issues matching your skills, scores repo health, and predicts PR merge likelihood. All LLM ranking replaced by Agent native reasoning."
tags: [github, open-source, contribution, pr, radar, finder]
related_skills: []
---

# GitSense — Open Source Contribution Finder

> Ported from [he-yufeng/GitSense](https://github.com/he-yufeng/GitSense) (MIT license).
> The original `rank_with_llm()` call is **replaced by Agent native reasoning** — no external LLM API needed.

## Prerequisites

1. **`GITHUB_TOKEN`** environment variable (recommended — 30 req/min vs 10 without)
   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   ```
2. **`httpx`** Python package (for scripts)
   ```bash
   pip install httpx
   ```

## Quick Start

```bash
# From this skill's scripts directory:
cd skills/gitsense/scripts

# Or use the full path:
SKILL_DIR=/root/bigboss-skills/skills/gitsense/scripts
```

## Workflows

There are **4 workflows**, each mapping to one original GitSense subcommand:

---

### 1. `find` — Search all of GitHub for matching issues

**What it does**: Searches GitHub for open, unassigned issues matching the user's skills, then the Agent ranks them by fit.

**Steps**:
1. Call `fetch_candidates()` from `finder_data.py` to gather candidate issues
2. **Agent reasoning** (replaces `rank_with_llm()`): rank each candidate 1-10 by:
   - How well the issue title/body/labels match the user's skills
   - Whether the issue has enough context to start (body length, labels)
   - Complexity estimate from the issue description
3. For each top match, provide: score (1-10), 1-line reason, concrete approach hint
4. Present results sorted by score descending (top 8)

**Agent prompt pattern** (do this yourself — no external LLM call):

> You are an open source contribution advisor. The user has skills: {skills}. 
> Below are {N} candidate GitHub issues. For each, rate 1-10 how well it matches,
> give a one-line reason, and a concrete "how to start" hint.
> Return only the top 8, sorted by score descending.

**Example invocation**:
```bash
cd /root/bigboss-skills/skills/gitsense/scripts && python3 -c "
from finder_data import fetch_candidates
import json
candidates = fetch_candidates(
    skills=['python', 'llm', 'cuda'],
    min_stars=1000,
    max_results=20,
    updated_days=90,
    max_comments=10,
)
print(json.dumps(candidates, indent=2))
"
```

**Flags from original** (mapped to function args):
- `--skills` → `skills` (list[str], required)
- `--stars` → `min_stars` (int, default 100)
- `--labels` → `labels` (list[str], default [])
- `--limit` → `max_results` (int, default 20, then Agent picks top 8)
- `--updated-days` → `updated_days` (int, default 180)
- `--max-comments` → `max_comments` (int | None)
- `--include-assigned` → `include_assigned` (bool, default False)

---

### 2. `scan` — List open issues in a specific repo

**What it does**: Lists all open, unassigned issues in a target repo, optionally filtered by skills.

**Steps**:
1. Call `scan_repo_issues()` from `finder_data.py`
2. Display results in a table

**Example invocation**:
```bash
cd /root/bigboss-skills/skills/gitsense/scripts && python3 -c "
from finder_data import scan_repo_issues
import json
issues = scan_repo_issues(
    repo='vllm-project/vllm',
    skills=['python', 'cuda'],
    updated_days=90,
)
print(json.dumps(issues, indent=2))
"
```

**Flags**:
- `repo` (str, required) — `owner/name` format
- `skills` (list[str] | None) — filter issues mentioning these skills
- `updated_days` (int, default 180)
- `max_comments` (int | None)
- `max_results` (int, default 15)

---

### 3. `radar` — Score repo health from PR history

**What it does**: Analyzes a repo's recent PR activity — merge velocity, stale backlog, maintainer response time, external contributor ratio — and produces a 0-100 health score. **Pure deterministic heuristics, no LLM.**

**Steps**:
1. Call `analyze_repo()` from `radar.py` for each repo
2. Display the `RepoRadarReport` with score, recommendation, risk flags

**Example invocation** (single repo):
```bash
cd /root/bigboss-skills/skills/gitsense/scripts && python3 -c "
from radar import analyze_repo, render_markdown, render_json
report = analyze_repo('vllm-project/vllm', skills=['python', 'cuda'], days=90)
print(render_markdown([report]))
"
```

**Example invocation** (batch from file):
```bash
cd /root/bigboss-skills/skills/gitsense/scripts && python3 -c "
from radar import analyze_repo, load_target_repos, render_markdown
repos = load_target_repos('/path/to/targets.txt')
reports = [analyze_repo(r, skills=['python', 'agents'], days=90) for r in repos]
reports.sort(key=lambda r: r.score, reverse=True)
print(render_markdown(reports))
"
```

**Score interpretation**:
| Score | Recommendation | Meaning |
|-------|---------------|---------|
| 75-100 | **Go** | Active, responsive repo. Good to contribute. |
| 60-74 | **Watch** | Reasonable signals. Comment first, see response. |
| 45-59 | **Comment first** | Mixed signals. Open an issue/discussion first. |
| 0-44 | **Avoid for now** | Red flags (stale, slow, internal-only merges). |

**Flags**:
- `repo` (str, required) — `owner/name` format
- `skills` (list[str] | None) — for skill match signal
- `days` (int, default 90) — PR history window
- `stale_days` (int, default 14) — open PR age counted as stale
- `sample_size` (int, default 20) — merged PRs to sample for metrics

**Risk flags** (triage warnings):
- `no recent merges` — repo may be dormant
- `crowded stale PR queue` — backlog is large and old
- `slow merge time` > 45d median — patience required
- `slow maintainer response` > 21d — likely slow to review
- `mostly internal recent merges` — outsider contributions rarely land

---

### 4. `predict` — Predict whether a specific PR will merge

**What it does**: Scores a single open PR 0-100 on merge likelihood using public signals. **Pure deterministic heuristics, no LLM.**

**Steps**:
1. Parse the PR reference via `parse_pr_ref()` from `predictor.py`
2. Fetch PR data, reviews, files, and CI status via `github_client.py`
3. Call `analyze_pr()` from `predictor.py`
4. Display score + label + notes

**Example invocation**:
```bash
cd /root/bigboss-skills/skills/gitsense/scripts && python3 -c "
from predictor import parse_pr_ref, analyze_pr, derive_review_decision, files_touch_tests
from github_client import get_pull_request, get_pull_request_reviews, get_pull_request_files, get_commit_status_state

owner, repo, number = parse_pr_ref('vllm-project/vllm#36200')
pr = get_pull_request(owner, repo, number)
reviews = get_pull_request_reviews(owner, repo, number)
files = get_pull_request_files(owner, repo, number)
head_sha = (pr.get('head') or {}).get('sha') or ''
ci_state = get_commit_status_state(owner, repo, head_sha) if head_sha else ''

prediction = analyze_pr(
    pr,
    review_decision=derive_review_decision(reviews),
    ci_failing=(ci_state == 'failure'),
    touches_tests=files_touch_tests(files),
)
print(f'Score: {prediction.score}/100')
print(f'Label: {prediction.label}')
for note in prediction.notes:
    print(f'  • {note}')
"
```

**PR references accepted**:
- Full URL: `https://github.com/owner/repo/pull/123`
- Short form: `owner/repo#123`

**Score interpretation**:
| Score | Label |
|-------|-------|
| 70+ | **Likely to merge** |
| 45-69 | **Could go either way** |
| 25-44 | **Long shot** |
| 0-24 | **Unlikely as-is** |

---

## Architecture (what changed from original GitSense)

```
Original GitSense:                         This SKILL:
───────────────                            ────────────
github_client.py ──── httpx ──→ GitHub     github_client.py ──── httpx ──→ GitHub
finder.py ──── rank_with_llm() ──→ OpenAI  finder_data.py ──── NO rank_with_llm()
radar.py ──── pure heuristics  ✓           radar.py ──── same (no changes)
predictor.py ──── pure heuristics  ✓       predictor.py ──── same (no changes)
cli.py ──── Click + Rich UI                Agent dialogue ──── native rendering
```

**Key differences**:
1. `rank_with_llm()` (finder.py:103-185) is **deleted** — Agent uses its own reasoning
2. `openai` dependency is **removed** — no external LLM API required
3. `click` + `rich` CLI is **removed** — Agent handles I/O conversationally
4. `httpx` is **kept** — needed for GitHub REST API calls

## Troubleshooting

### Rate limiting
- Without `GITHUB_TOKEN`: 10 requests/minute
- With `GITHUB_TOKEN`: 30 requests/minute
- If you hit rate limits, the scripts will raise `httpx.HTTPStatusError`

### Missing httpx
```bash
pip install httpx
```

### Script import errors
Make sure you're running from `skills/gitsense/scripts/` so relative imports resolve:
```bash
cd /root/bigboss-skills/skills/gitsense/scripts && python3 -c "from radar import analyze_repo; ..."
```

## License

MIT — originally by Yufeng He (he-yufeng/GitSense). Ported with attribution.
