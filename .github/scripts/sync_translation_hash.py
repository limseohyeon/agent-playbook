#!/usr/bin/env python3
"""Update translation linkage metadata after the translation is reviewed."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TRANSLATIONS_ROOT = REPOSITORY_ROOT / "translations" / "ko"


def normalized_hash(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def update_markdown(path: Path, source: str, digest: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SystemExit(f"Markdown translation needs YAML frontmatter: {path}")
    try:
        closing = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration as exc:
        raise SystemExit(f"Unclosed YAML frontmatter: {path}") from exc

    fields = {
        "translation_of": source,
        "source_sha256": digest,
    }
    for key, value in fields.items():
        pattern = re.compile(rf"^{re.escape(key)}:\s*.*$")
        for index in range(1, closing):
            if pattern.match(lines[index]):
                lines[index] = f"{key}: {value}"
                break
        else:
            lines.insert(1, f"{key}: {value}")
            closing += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def update_toml(path: Path, source: str, digest: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fields = {
        "translation_of": source,
        "source_sha256": digest,
    }
    insert_at = 0
    for key, value in fields.items():
        pattern = re.compile(rf"^#\s*{re.escape(key)}:\s*.*$")
        for index, line in enumerate(lines[:20]):
            if pattern.match(line):
                lines[index] = f"# {key}: {value}"
                break
        else:
            lines.insert(insert_at, f"# {key}: {value}")
            insert_at += 1
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="+", help="Repository-relative English source paths")
    args = parser.parse_args()

    for raw_source in args.source:
        relative = Path(raw_source)
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit(f"Source must be repository-relative: {raw_source}")
        source_path = REPOSITORY_ROOT / relative
        translated = TRANSLATIONS_ROOT / relative
        if not source_path.is_file():
            raise SystemExit(f"Missing source: {relative.as_posix()}")
        if not translated.is_file():
            raise SystemExit(f"Missing Korean translation: {translated.relative_to(REPOSITORY_ROOT)}")

        digest = normalized_hash(source_path)
        if translated.suffix.casefold() == ".toml":
            update_toml(translated, relative.as_posix(), digest)
        else:
            update_markdown(translated, relative.as_posix(), digest)
        print(f"Updated translation metadata: {translated.relative_to(REPOSITORY_ROOT)}")


if __name__ == "__main__":
    main()
