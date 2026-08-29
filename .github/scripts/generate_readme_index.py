#!/usr/bin/env python3
"""Generate and validate the root README artifact index."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from toml_compat import TomlError, load_toml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPOSITORY_ROOT / "README.md"
INDEX_HEADING = "## 목록"
TRANSLATIONS_ROOT = Path("translations") / "ko"
ARTIFACT_CATEGORIES = ("agents", "prompts", "rules", "skills")
MARKDOWN_SUFFIXES = {".md", ".mdx", ".markdown"}


@dataclass(frozen=True)
class Artifact:
    category: str
    artifact_name: str
    source_path: Path
    translation_path: Path
    display_name: str
    description: str | None


def content_paths() -> set[Path]:
    """Return source and Korean-translation files, including untracked additions."""
    paths: set[Path] = set()
    for category in ARTIFACT_CATEGORIES:
        category_root = REPOSITORY_ROOT / category
        if category_root.is_dir():
            paths.update(
                path.relative_to(REPOSITORY_ROOT)
                for path in category_root.rglob("*")
                if path.is_file()
            )

        translated_root = REPOSITORY_ROOT / TRANSLATIONS_ROOT / category
        if translated_root.is_dir():
            paths.update(
                path.relative_to(REPOSITORY_ROOT)
                for path in translated_root.rglob("*")
                if path.is_file()
            )
    return paths


def normalized_file_hash(path: Path) -> str:
    content = (REPOSITORY_ROOT / path).read_bytes()
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def frontmatter_fields(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    try:
        closing = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        return {}, text

    fields: dict[str, str] = {}
    index = 1
    while index < closing:
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", lines[index])
        if not match:
            index += 1
            continue
        key, value = match.groups()
        if value in {"|", "|-", "|+", ">", ">-", ">+"}:
            block: list[str] = []
            index += 1
            while index < closing and (
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
    return fields, "\n".join(lines[closing + 1 :])


def toml_comment_metadata(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines()[:20]:
        match = re.match(r"^#\s*([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if match:
            fields[match.group(1)] = match.group(2)
    return fields


def first_markdown_heading(body: str) -> str | None:
    for line in body.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line.strip())
        if match:
            return match.group(1).strip()
    return None


def first_markdown_sentence(body: str) -> str | None:
    in_fence = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
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
    absolute = REPOSITORY_ROOT / path
    if path.suffix.casefold() == ".toml":
        try:
            data = load_toml(absolute.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, TomlError) as exc:
            raise SystemExit(f"Invalid TOML: {path.as_posix()}: {exc}") from exc
        name = str(data.get("name") or path.stem)
        description = data.get("description")
        return normalize_inline(name), normalize_inline(str(description)) if description else None

    text = absolute.read_text(encoding="utf-8")
    fields, body = frontmatter_fields(text)
    name = fields.get("name") or first_markdown_heading(body) or path.stem
    description = fields.get("description") or first_markdown_sentence(body)
    return normalize_inline(name), normalize_inline(description) if description else None


def translation_metadata(path: Path) -> dict[str, str]:
    text = (REPOSITORY_ROOT / path).read_text(encoding="utf-8")
    if path.suffix.casefold() == ".toml":
        return toml_comment_metadata(text)
    fields, _ = frontmatter_fields(text)
    return fields


def entrypoint_for(category: str, artifact_dir: Path, tracked: set[Path]) -> Path:
    direct_files = sorted(
        path
        for path in tracked
        if path.parent == artifact_dir and not path.name.startswith(".")
    )
    if category == "skills":
        expected = artifact_dir / "SKILL.md"
        if expected not in tracked:
            raise SystemExit(f"Missing skill entrypoint: {expected.as_posix()}")
        return expected

    if category == "agents":
        candidates = [path for path in direct_files if path.suffix.casefold() == ".toml"]
    else:
        candidates = [path for path in direct_files if path.suffix.casefold() in MARKDOWN_SUFFIXES]

    if len(candidates) != 1:
        raise SystemExit(
            f"{artifact_dir.as_posix()} must contain exactly one {category} entrypoint; "
            f"found {len(candidates)}"
        )
    return candidates[0]


def discover_artifacts(tracked: set[Path]) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for category in ARTIFACT_CATEGORIES:
        category_paths = sorted(path for path in tracked if path.parts[:1] == (category,))
        for path in category_paths:
            if len(path.parts) < 4 or path.parts[1] != "global":
                raise SystemExit(
                    f"Playbook paths must use {category}/global/<name>/...: {path.as_posix()}"
                )

        artifact_dirs = sorted(
            {Path(category, "global", path.parts[2]) for path in category_paths},
            key=lambda path: path.as_posix().casefold(),
        )
        for artifact_dir in artifact_dirs:
            source = entrypoint_for(category, artifact_dir, tracked)
            translated = TRANSLATIONS_ROOT / source
            if translated not in tracked or not (REPOSITORY_ROOT / translated).is_file():
                raise SystemExit(f"Missing Korean translation: {translated.as_posix()}")

            fields = translation_metadata(translated)
            expected_source = source.as_posix()
            if fields.get("translation_of") != expected_source:
                raise SystemExit(
                    f"{translated.as_posix()} must declare translation_of: {expected_source}"
                )
            expected_hash = normalized_file_hash(source)
            if fields.get("source_sha256") != expected_hash:
                raise SystemExit(
                    f"Stale Korean translation: {translated.as_posix()}\n"
                    f"Expected source_sha256: {expected_hash}"
                )

            display_name, description = file_metadata(source)
            _, translated_description = file_metadata(translated)
            artifacts.append(
                Artifact(
                    category=category,
                    artifact_name=artifact_dir.name,
                    source_path=source,
                    translation_path=translated,
                    display_name=display_name,
                    description=translated_description or description,
                )
            )
    return artifacts


def normalize_inline(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def escape_table_cell(value: str) -> str:
    return normalize_inline(value).replace("\\", "\\\\").replace("|", "\\|")


def render_index(artifacts: list[Artifact]) -> str:
    grouped: dict[str, list[Artifact]] = defaultdict(list)
    for artifact in artifacts:
        grouped[artifact.category].append(artifact)

    lines: list[str] = []
    for category in sorted(grouped, key=str.casefold):
        lines.extend(
            (
                f"### {category}",
                "",
                "| 이름 | 설명 | 문서 | 경로 |",
                "| --- | --- | --- | --- |",
            )
        )
        for artifact in sorted(
            grouped[category], key=lambda item: item.display_name.casefold()
        ):
            source = artifact.source_path.as_posix()
            translated = artifact.translation_path.as_posix()
            documents = (
                f"[en]({quote(source, safe='/-._~')})/"
                f"[kr]({quote(translated, safe='/-._~')})"
            )
            name = escape_table_cell(artifact.display_name)
            description = escape_table_cell(artifact.description or "")
            shown_path = escape_table_cell(source.replace("`", "\\`"))
            lines.append(
                f"| **{name}** | {description} | {documents} | `{shown_path}` |"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def updated_readme(artifacts: list[Artifact]) -> str:
    original = README_PATH.read_text(encoding="utf-8")
    match = re.search(rf"(?m)^{re.escape(INDEX_HEADING)}\s*$", original)
    if not match:
        raise SystemExit(f"{README_PATH.name} does not contain: {INDEX_HEADING}")
    prefix = original[: match.end()].rstrip()
    index = render_index(artifacts)
    return f"{prefix}\n" + (f"\n{index}\n" if index else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate translations and fail if README.md is not current.",
    )
    args = parser.parse_args()

    tracked = content_paths()
    artifacts = discover_artifacts(tracked)
    expected = updated_readme(artifacts)
    current = README_PATH.read_text(encoding="utf-8")

    if args.check:
        if current != expected:
            print(
                "README.md is not current. Run "
                "python .github/scripts/generate_readme_index.py and commit the result.",
                file=sys.stderr,
            )
            return 1
        print("Playbook structure, translations, and README index are valid.")
        return 0

    if current == expected:
        print("README index is already current.")
        return 0
    README_PATH.write_text(expected, encoding="utf-8", newline="\n")
    print("README index updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
