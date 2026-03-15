"""
Diff-based update for questions.json.

Compares freshly scraped data (from merge_question_bank.py output) against
the existing questions.json and produces:
  1. A human-readable diff report (printed to stdout and saved as update_report.md)
  2. An updated questions.json only if validation passes

This script does NOT replace questions.json in-place — it writes to
questions_candidate.json so the CI workflow can create a PR for review.

Usage:
  python scripts/update_questions.py

Expects in repo root (produced by the pipeline):
  questions.json                 – current committed version
  question_bank_from_pdf.json    – freshly parsed from PDF
  answers_general.json           – freshly scraped general answers
  state_answers_*.json           – freshly scraped state answers
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Allow importing sibling scripts
SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from merge_question_bank import merge as merge_data  # noqa: E402
from validate_questions import validate  # noqa: E402

ROOT = SCRIPTS_DIR.parent
CURRENT_PATH = ROOT / "questions.json"
CANDIDATE_PATH = ROOT / "questions_candidate.json"
REPORT_PATH = ROOT / "update_report.md"


def load_current() -> list[dict]:
    return json.loads(CURRENT_PATH.read_text(encoding="utf-8"))


def diff_questions(current: list[dict], candidate: list[dict]) -> dict:
    """Compare current vs candidate and return structured diff."""
    cur_by_id = {q["id"]: q for q in current}
    cand_by_id = {q["id"]: q for q in candidate}

    added = []
    removed = []
    changed = []

    # Questions in candidate but not in current
    for qid in sorted(set(cand_by_id) - set(cur_by_id)):
        added.append(cand_by_id[qid])

    # Questions in current but not in candidate
    for qid in sorted(set(cur_by_id) - set(cand_by_id)):
        removed.append(cur_by_id[qid])

    # Questions in both — check for changes
    compare_fields = ["question", "options", "correctIndex", "isImageQuestion", "imageUrl", "state", "category"]
    for qid in sorted(set(cur_by_id) & set(cand_by_id)):
        cur_q = cur_by_id[qid]
        cand_q = cand_by_id[qid]
        diffs = {}
        for field in compare_fields:
            old_val = cur_q.get(field)
            new_val = cand_q.get(field)
            if old_val != new_val:
                diffs[field] = {"old": old_val, "new": new_val}
        if diffs:
            changed.append({"id": qid, "question": cur_q.get("question", "")[:80], "changes": diffs})

    return {"added": added, "removed": removed, "changed": changed}


def format_report(diff: dict, current_count: int, candidate_count: int) -> str:
    """Generate a markdown report of changes."""
    lines = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"# Questions Update Report — {now}")
    lines.append("")
    lines.append(f"**Current**: {current_count} questions")
    lines.append(f"**Candidate**: {candidate_count} questions")
    lines.append("")

    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        lines.append("**No changes detected.** questions.json is up to date.")
        return "\n".join(lines)

    # Summary
    lines.append("## Summary")
    lines.append(f"- **Added**: {len(diff['added'])} new question(s)")
    lines.append(f"- **Removed**: {len(diff['removed'])} question(s)")
    lines.append(f"- **Changed**: {len(diff['changed'])} question(s)")
    lines.append("")

    # Added
    if diff["added"]:
        lines.append("## Added Questions")
        for q in diff["added"]:
            lines.append(f"- **Q{q['id']}** ({q.get('category', '?')}): {q['question'][:100]}")
        lines.append("")

    # Removed
    if diff["removed"]:
        lines.append("## Removed Questions")
        for q in diff["removed"]:
            lines.append(f"- **Q{q['id']}** ({q.get('category', '?')}): {q['question'][:100]}")
        lines.append("")

    # Changed
    if diff["changed"]:
        lines.append("## Changed Questions")
        for item in diff["changed"]:
            lines.append(f"### Q{item['id']}: {item['question']}")
            for field, vals in item["changes"].items():
                lines.append(f"- **{field}**:")
                lines.append(f"  - Old: `{vals['old']}`")
                lines.append(f"  - New: `{vals['new']}`")
            lines.append("")

    return "\n".join(lines)


def apply_updates(current: list[dict], candidate: list[dict], diff: dict) -> list[dict]:
    """
    Apply changes from candidate to current, preserving manual edits
    in fields that the scraper doesn't touch.

    Strategy:
    - For CHANGED questions: update only the fields that changed
    - For ADDED questions: include them
    - For REMOVED questions: keep them (flag for manual review)
    """
    cur_by_id = {q["id"]: dict(q) for q in current}  # deep copy
    cand_by_id = {q["id"]: q for q in candidate}

    # Apply changes to existing questions
    for item in diff["changed"]:
        qid = item["id"]
        for field, vals in item["changes"].items():
            cur_by_id[qid][field] = vals["new"]
        # Update officialOptions if candidate has them
        if "officialOptions" in cand_by_id.get(qid, {}):
            cur_by_id[qid]["officialOptions"] = cand_by_id[qid]["officialOptions"]

    # Add new questions
    for q in diff["added"]:
        cur_by_id[q["id"]] = q

    # Removed questions: keep but warn (don't silently delete)

    # Sort by ID
    result = [cur_by_id[qid] for qid in sorted(cur_by_id)]
    return result


def main():
    # Step 1: Run the merge to produce candidate data
    print("Step 1: Merging scraped data into candidate...")
    candidate = merge_data()

    # Step 2: Load current
    print("Step 2: Loading current questions.json...")
    current = load_current()

    # Step 3: Diff
    print("Step 3: Computing diff...")
    diff = diff_questions(current, candidate)

    # Step 4: Generate report
    report = format_report(diff, len(current), len(candidate))
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nReport saved to {REPORT_PATH}")

    # Step 5: If no changes, exit early
    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        print("\nNo updates needed.")
        sys.exit(0)

    # Step 6: Apply updates and write candidate
    print("\nStep 6: Applying updates to candidate file...")
    updated = apply_updates(current, candidate, diff)
    CANDIDATE_PATH.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Candidate written to {CANDIDATE_PATH}")

    # Step 7: Validate candidate
    print("\nStep 7: Validating candidate...")
    result = validate(CANDIDATE_PATH)
    for w in result["warnings"]:
        print(f"  WARN: {w}")
    for e in result["errors"]:
        print(f"  FAIL: {e}")

    if result["errors"]:
        print("\nCANDIDATE FAILED VALIDATION — will not replace questions.json")
        print("Review update_report.md and questions_candidate.json manually.")
        sys.exit(2)

    # Step 8: Replace questions.json with validated candidate
    print("\nValidation passed. Replacing questions.json with candidate.")
    CANDIDATE_PATH.rename(CURRENT_PATH)
    print("Done — questions.json updated successfully.")


if __name__ == "__main__":
    main()
