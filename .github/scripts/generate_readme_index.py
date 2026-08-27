#!/usr/bin/env python3
"""Generate the repository file index below the README's ``## 목록`` heading."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPOSITORY_ROOT / "README.md"
INDEX_HEADING = "## 목록"
MARKDOWN_SUFFIXES = {".md", ".mdx", ".markdown"}
TRANSLATIONS_ROOT = Path("translations")
KOREAN_TRANSLATIONS_ROOT = TRANSLATIONS_ROOT / "ko"


def tracked_content_paths() -> list[Path]:
    """Return eligible Git-tracked files in deterministic path order."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    paths = []
    for raw_path in result.stdout.decode("utf-8", errors="surrogateescape").split("\0"):
        if not raw_path:
            continue
        path = Path(raw_path)
        if len(path.parts) < 2:
            continue
        if path.parts[0] == TRANSLATIONS_ROOT.name:
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: path.as_posix().casefold())


def frontmatter_fields(text: str) -> tuple[dict[str, str], str]:
    """Extract simple top-level YAML fields without requiring PyYAML."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        return {}, text

    fields: dict[str, str] = {}
    index = 1
    while index < closing_index:
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", lines[index])
        if not match:
            index += 1
            continue

        key, value = match.groups()
        if value in {"|", "|-", "|+", ">", ">-", ">+"}:
            block: list[str] = []
            index += 1
            while index < closing_index and (
                not lines[index].strip() or lines[index][:1].isspace()
            ):
                block.append(lines[index].strip())
                index += 1
            fields[key] = " ".join(part for part in block if part)
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        fields[key] = value
        index += 1

    body = "\n".join(lines[closing_index + 1 :])
    return fields, body


def first_markdown_heading(body: str) -> str | None:
    for line in body.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line.strip())
        if match:
            return match.group(1).strip()
    return None


def first_markdown_sentence(body: str) -> str | None:
    """Return the first prose line, ignoring headings and structural Markdown."""
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if (
            in_fence
            or not stripped
            or stripped.startswith(("#", "<!--", "- ", "* ", "+ ", "> "))
            or re.match(r"^\d+[.)]\s", stripped)
        ):
            continue
        return re.sub(r"\s+", " ", stripped)
    return None


def file_metadata(path: Path) -> tuple[str, str | None]:
    name = path.name
    description = None
    try:
        text = (REPOSITORY_ROOT / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return name, description

    fields, body = frontmatter_fields(text)
    if fields.get("name"):
        name = fields["name"]
    elif path.suffix.casefold() in MARKDOWN_SUFFIXES:
        name = first_markdown_heading(body) or name

    if fields.get("description"):
        description = fields["description"]
    elif path.suffix.casefold() in MARKDOWN_SUFFIXES:
        description = first_markdown_sentence(body)

    return normalize_inline(name), normalize_inline(description) if description else None


def korean_translation_metadata(path: Path) -> tuple[Path, str | None, bool] | None:
    """Return a paired Korean translation, its summary, and whether it is stale."""
    translation_path = KOREAN_TRANSLATIONS_ROOT / path
    absolute_path = REPOSITORY_ROOT / translation_path
    if not absolute_path.is_file():
        return None

    try:
        text = absolute_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return translation_path, None, True

    fields, body = frontmatter_fields(text)
    source_path = path.as_posix()
    if fields.get("translation_of") != source_path:
        raise SystemExit(
            f"{translation_path.as_posix()} must declare translation_of: {source_path}"
        )

    description = fields.get("description")
    if not description and path.suffix.casefold() in MARKDOWN_SUFFIXES:
        description = first_markdown_sentence(body)

    source_hash = normalized_file_hash(path)
    is_stale = fields.get("source_sha256") != source_hash
    normalized = normalize_inline(description) if description else None
    return translation_path, normalized, is_stale


def normalize_inline(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalized_file_hash(path: Path) -> str:
    """Hash content consistently across LF, CRLF, and CR checkouts."""
    content = (REPOSITORY_ROOT / path).read_bytes()
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def escape_link_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def render_index(paths: list[Path]) -> str:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        grouped[path.parts[0]].append(path)

    lines: list[str] = []
    for section in sorted(grouped, key=str.casefold):
        lines.extend((f"### {section}", ""))
        for path in grouped[section]:
            display_name, description = file_metadata(path)
            translation = korean_translation_metadata(path)
            repository_path = path.as_posix()
            displayed_path = repository_path.replace("`", "\\`")
            target = quote(repository_path, safe="/-._~")
            if translation:
                translation_path, korean_description, is_stale = translation
                description = korean_description or description
                translation_target = quote(translation_path.as_posix(), safe="/-._~")
                item = f"- **{escape_link_label(display_name)}**"
            else:
                item = f"- [{escape_link_label(display_name)}]({target})"
            if description:
                item += f" — {description}"
            if translation:
                item += f" ([원문]({target}) · [한국어]({translation_target}))"
                if is_stale:
                    item += " · **번역 검토 필요**"
            item += f" (`{displayed_path}`)"
            lines.append(item)
        lines.append("")
    return "\n".join(lines).rstrip()


def update_readme() -> bool:
    original = README_PATH.read_text(encoding="utf-8")
    heading_pattern = re.compile(rf"(?m)^{re.escape(INDEX_HEADING)}\s*$")
    match = heading_pattern.search(original)
    if not match:
        raise SystemExit(f"{README_PATH.name} does not contain the heading: {INDEX_HEADING}")

    prefix = original[: match.end()].rstrip()
    generated = render_index(tracked_content_paths())
    updated = f"{prefix}\n"
    if generated:
        updated += f"\n{generated}\n"

    if updated == original:
        return False
    README_PATH.write_text(updated, encoding="utf-8", newline="\n")
    return True


if __name__ == "__main__":
    changed = update_readme()
    print("README index updated." if changed else "README index is already current.")
