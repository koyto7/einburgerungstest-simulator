"""
Validate questions.json for data quality.

Runs a suite of checks and exits with code 1 if any FAIL.
Warnings (WARN) do not cause failure but are reported.

Usage:
  python scripts/validate_questions.py [path/to/questions.json]
"""
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).parent.parent
DEFAULT_PATH = ROOT / "questions.json"

EXPECTED_TOTAL = 460
EXPECTED_GENERAL = 300
EXPECTED_STATES = 16
EXPECTED_PER_STATE = 10
EXPECTED_STATE_TOTAL = EXPECTED_STATES * EXPECTED_PER_STATE

KNOWN_STATES = [
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
    "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
    "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
    "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
]


def validate(path: Path, *, check_urls: bool = False) -> dict:
    """Run all validations. Returns {errors: [...], warnings: [...]}."""
    errors = []
    warnings = []
    data = json.loads(path.read_text(encoding="utf-8"))

    # --- 1. Total question count ---
    if len(data) != EXPECTED_TOTAL:
        errors.append(f"Expected {EXPECTED_TOTAL} questions, got {len(data)}")

    general = [q for q in data if q["category"] == "general"]
    state = [q for q in data if q["category"] == "state"]

    if len(general) != EXPECTED_GENERAL:
        errors.append(f"Expected {EXPECTED_GENERAL} general questions, got {len(general)}")
    if len(state) != EXPECTED_STATE_TOTAL:
        errors.append(f"Expected {EXPECTED_STATE_TOTAL} state questions, got {len(state)}")

    # --- 2. ID uniqueness and sequentiality ---
    ids = [q["id"] for q in data]
    if len(ids) != len(set(ids)):
        dupes = [i for i, c in Counter(ids).items() if c > 1]
        errors.append(f"Duplicate IDs: {dupes}")
    if sorted(ids) != list(range(1, len(data) + 1)):
        errors.append("IDs are not sequential 1..N")

    # --- 3. Every question has exactly 4 non-empty options ---
    for q in data:
        opts = q.get("options", [])
        if len(opts) != 4:
            errors.append(f"Q{q['id']}: has {len(opts)} options (expected 4)")
        for i, o in enumerate(opts):
            if not isinstance(o, str) or not o.strip():
                errors.append(f"Q{q['id']}: option[{i}] is empty or not a string")

    # --- 4. correctIndex is valid (0-3) for every question ---
    for q in data:
        ci = q.get("correctIndex")
        if ci is None:
            errors.append(f"Q{q['id']}: correctIndex is null (missing answer)")
        elif not isinstance(ci, int) or ci < 0 or ci > 3:
            errors.append(f"Q{q['id']}: correctIndex={ci} is invalid (expected 0-3)")

    # --- 5. State questions: correct states and distribution ---
    state_counts = Counter(q["state"] for q in state)
    for s in KNOWN_STATES:
        count = state_counts.get(s, 0)
        if count != EXPECTED_PER_STATE:
            errors.append(f"State '{s}': expected {EXPECTED_PER_STATE} questions, got {count}")
    unknown = set(state_counts.keys()) - set(KNOWN_STATES)
    if unknown:
        errors.append(f"Unknown states found: {unknown}")

    # --- 6. General questions have state=null ---
    bad_general = [q["id"] for q in general if q["state"] is not None]
    if bad_general:
        errors.append(f"General questions with non-null state: {bad_general}")

    # --- 7. Image questions have imageUrl ---
    image_qs = [q for q in data if q.get("isImageQuestion")]
    missing_img = [q["id"] for q in image_qs if not q.get("imageUrl")]
    if missing_img:
        errors.append(f"Image questions missing imageUrl: {missing_img}")

    # --- 8. No duplicate question text ---
    q_texts = [q["question"] for q in data]
    text_dupes = [t for t, c in Counter(q_texts).items() if c > 1]
    if text_dupes:
        warnings.append(f"Duplicate question texts ({len(text_dupes)}): {text_dupes[:3]}...")

    # --- 9. Required fields present ---
    required_fields = ["id", "number", "localNumber", "category", "question", "options", "isImageQuestion", "correctIndex"]
    for q in data:
        missing = [f for f in required_fields if f not in q]
        if missing:
            errors.append(f"Q{q.get('id', '?')}: missing fields {missing}")

    # --- 10. Optional: check image URLs are reachable ---
    if check_urls:
        for q in image_qs:
            url = q.get("imageUrl")
            if url:
                try:
                    req = urllib.request.Request(url, method="HEAD")
                    resp = urllib.request.urlopen(req, timeout=10)
                    if resp.status >= 400:
                        warnings.append(f"Q{q['id']}: imageUrl returned HTTP {resp.status}")
                except (urllib.error.URLError, OSError) as e:
                    warnings.append(f"Q{q['id']}: imageUrl unreachable: {e}")

    return {"errors": errors, "warnings": warnings}


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    check_urls = "--check-urls" in sys.argv

    if not path.exists():
        print(f"FAIL: {path} not found")
        sys.exit(1)

    result = validate(path, check_urls=check_urls)

    for w in result["warnings"]:
        print(f"  WARN: {w}")
    for e in result["errors"]:
        print(f"  FAIL: {e}")

    total_checks = 10
    failed = len(result["errors"])
    passed = total_checks - (1 if failed else 0)

    print()
    if failed:
        print(f"VALIDATION FAILED — {len(result['errors'])} error(s), {len(result['warnings'])} warning(s)")
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED — {len(result['warnings'])} warning(s)")
        sys.exit(0)


if __name__ == "__main__":
    main()
