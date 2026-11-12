"""Tests the whole AI system: asks Claude each question and checks the answer.

This is an "eval": a fixed set of questions with known right answers, run after
every change, so you can prove the AI is accurate before anyone relies on it.

It runs Claude Code in non-interactive mode (claude -p), which uses your Claude
plan, so there is no extra charge. It takes a few minutes.

  python evals/run_evals.py            run all questions
  python evals/run_evals.py live-count run one question by id
"""
import json, subprocess, sys, time
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
questions = json.loads((PROJECT / "evals" / "questions.json").read_text())
only = set(sys.argv[1:])

def check(answer, q):
    a = answer.lower()
    missing = [group for group in q.get("must_include_any", []) if not any(x.lower() in a for x in group)]
    forbidden = [x for x in q.get("must_not_include", []) if x.lower() in a]
    return not missing and not forbidden, missing, forbidden

rows, passed = [], 0
for q in questions:
    if only and q["id"] not in only:
        continue
    start = time.time()
    try:
        out = subprocess.run(["claude", "-p", q["question"], "--allowedTools", "mcp__rollout"],
                             cwd=PROJECT, capture_output=True, text=True, timeout=300)
        answer = out.stdout.strip() or out.stderr.strip()
    except FileNotFoundError:
        sys.exit("Claude Code is not installed or not on your PATH. See README step 1.")
    except subprocess.TimeoutExpired:
        answer = "(timed out)"
    ok, missing, forbidden = check(answer, q)
    passed += ok
    secs = time.time() - start
    print(f"{'PASS' if ok else 'FAIL'}  {q['id']:<18} {secs:5.0f}s")
    if not ok:
        print(f"      missing one of: {missing}  forbidden found: {forbidden}")
    rows.append((q, ok, answer, secs))

total = len(rows)
print(f"\nScore: {passed}/{total} ({100 * passed / max(total, 1):.0f}%)")

report = [f"# Eval results, {datetime.now():%Y-%m-%d %H:%M}", "", f"Score: **{passed}/{total}**", "",
          "| Question | Result | Seconds |", "|---|---|---|"]
report += [f"| {q['question']} | {'Pass' if ok else 'Fail'} | {s:.0f} |" for q, ok, _, s in rows]
report += ["", "## Answers", ""]
for q, ok, ans, _ in rows:
    report += [f"### {q['id']} ({'pass' if ok else 'fail'})", "", f"**Q:** {q['question']}", "", ans, ""]
(PROJECT / "evals" / "results.md").write_text("\n".join(report))
print("Full answers saved to evals/results.md")
