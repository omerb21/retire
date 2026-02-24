from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path("app/services/llm_chat")


def scan_file(p: Path) -> list[str]:
    bad = []
    try:
        s = p.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{p}: cannot read as utf-8: {e}"]

    if "\t" in s:
        bad.append("contains TAB characters")
    if "\u00a0" in s:
        bad.append("contains NBSP (U+00A0)")

    # Optional: catch weird mixed indentation quickly
    for i, line in enumerate(s.splitlines(), start=1):
        if line.startswith(" ") and ("\t" in line[: len(line) - len(line.lstrip())]):
            bad.append(f"line {i}: mixed spaces and tabs in indentation")
            break

    return [f"{p}: {msg}" for msg in bad]


def main() -> int:
    errors: list[str] = []
    for p in ROOT.rglob("*.py"):
        errors.extend(scan_file(p))

    if errors:
        print("Whitespace issues found:")
        for e in errors:
            print(" -", e)
        return 1

    print("OK: no TAB/NBSP issues under", ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
