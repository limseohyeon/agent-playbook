#!/usr/bin/env python3
"""Copy playbook artifacts into Codex or Cursor runtime homes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_GITHUB_SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
if str(_GITHUB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_GITHUB_SCRIPTS))

from toml_compat import TomlError, load_toml


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANAGER_SKILL = "agent-playbook-manager"
STAMP_FILENAME = ".playbook-stamp.json"
CODEX_ONLY_SKILL_FILES = {Path("agents") / "openai.yaml"}
SKIP_DIR_NAMES = {"__pycache__"}
CATEGORIES = ("agents", "skills", "rules", "prompts")


@dataclass(frozen=True)
class Artifact:
    category: str
    name: str
    source_dir: Path

    @property
    def source_key(self) -> str:
        return f"{self.category}/global/{self.name}"


@dataclass(frozen=True)
class PlannedCopy:
    runtime: str
    artifact: Artifact
    dest_root: Path
    dest_files: dict[str, bytes]
    stamp_path: Path
    note: str | None = None


def home() -> Path:
    return Path.home()


def cursor_install_root() -> Path:
    return home() / ".cursor" / "playbook-install"


def stamp_store(runtime: str) -> Path:
    if runtime == "codex":
        return home() / ".codex" / "playbook-install" / "stamps"
    return cursor_install_root() / "stamps"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def posix(path: Path) -> str:
    return path.as_posix()


def normalized_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def hash_payload(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(files):
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(normalized_bytes(files[relative]))
        digest.update(b"\0")
    return digest.hexdigest()


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
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
    body = "\n".join(lines[closing + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return fields, body


def entrypoint(artifact: Artifact) -> Path:
    if artifact.category == "skills":
        expected = artifact.source_dir / "SKILL.md"
        if not expected.is_file():
            raise SystemExit(f"Missing skill entrypoint: {posix(expected.relative_to(REPOSITORY_ROOT))}")
        return expected

    if artifact.category == "agents":
        candidates = sorted(
            path for path in artifact.source_dir.iterdir() if path.is_file() and path.suffix.casefold() == ".toml"
        )
    else:
        candidates = sorted(
            path
            for path in artifact.source_dir.iterdir()
            if path.is_file() and path.suffix.casefold() in {".md", ".mdx", ".markdown"}
        )
    if len(candidates) != 1:
        raise SystemExit(
            f"{artifact.source_key} must contain exactly one {artifact.category} entrypoint; "
            f"found {len(candidates)}"
        )
    return candidates[0]


def discover_artifacts() -> list[Artifact]:
    artifacts: list[Artifact] = []
    for category in CATEGORIES:
        root = REPOSITORY_ROOT / category / "global"
        if not root.is_dir():
            continue
        for source_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            artifact = Artifact(category=category, name=source_dir.name, source_dir=source_dir)
            entrypoint(artifact)
            artifacts.append(artifact)
    return artifacts


def select_artifacts(all_artifacts: list[Artifact], scope: str, names: list[str]) -> list[Artifact]:
    by_name = {artifact.name: artifact for artifact in all_artifacts}
    if names:
        missing = [name for name in names if name not in by_name]
        if missing:
            available = ", ".join(sorted(by_name)) or "(none)"
            raise SystemExit(f"Unknown artifact name(s): {', '.join(missing)}. Available: {available}")
        return [by_name[name] for name in names]
    if scope == "manager":
        manager = next(
            (
                artifact
                for artifact in all_artifacts
                if artifact.category == "skills" and artifact.name == MANAGER_SKILL
            ),
            None,
        )
        if manager is None:
            raise SystemExit(f"Missing default skill: {MANAGER_SKILL}")
        return [manager]
    return list(all_artifacts)


def iter_skill_files(source_dir: Path, runtime: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in source_dir.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIR_NAMES for part in path.relative_to(source_dir).parts):
            continue
        relative = path.relative_to(source_dir)
        if relative.name == STAMP_FILENAME:
            continue
        if runtime == "cursor" and relative in CODEX_ONLY_SKILL_FILES:
            continue
        files[posix(relative)] = path.read_bytes()
    if "SKILL.md" not in files:
        raise SystemExit(f"Missing SKILL.md in {posix(source_dir.relative_to(REPOSITORY_ROOT))}")
    return files


def cursor_agent_markdown(artifact: Artifact) -> bytes:
    try:
        data = load_toml(entrypoint(artifact).read_text(encoding="utf-8"))
    except TomlError as exc:
        raise SystemExit(f"Invalid agent TOML {artifact.name}: {exc}") from exc
    description = str(data.get("description") or "").strip()
    if not description:
        raise SystemExit(f"Agent {artifact.name} is missing description")
    instructions = str(data.get("developer_instructions") or "").strip()
    if not instructions:
        raise SystemExit(f"Agent {artifact.name} is missing developer_instructions")
    text = (
        "---\n"
        f"name: {artifact.name}\n"
        f"description: {yaml_quote(description)}\n"
        "---\n\n"
        f"{instructions}\n"
    )
    return text.encode("utf-8")


def cursor_rule_markdown(artifact: Artifact) -> bytes:
    fields, body = split_frontmatter(entrypoint(artifact).read_text(encoding="utf-8"))
    description = (fields.get("description") or "").strip()
    if not description:
        raise SystemExit(f"Rule {artifact.name} is missing description")
    body = body.lstrip("\n")
    if not body.endswith("\n"):
        body += "\n"
    text = (
        "---\n"
        f"description: {yaml_quote(description)}\n"
        "alwaysApply: true\n"
        "---\n\n"
        f"{body}"
    )
    return text.encode("utf-8")


def cursor_prompt_skill(artifact: Artifact) -> bytes:
    fields, body = split_frontmatter(entrypoint(artifact).read_text(encoding="utf-8"))
    description = (fields.get("description") or "").strip()
    if not description:
        raise SystemExit(f"Prompt {artifact.name} is missing description")
    body = body.lstrip("\n")
    if not body.endswith("\n"):
        body += "\n"
    text = (
        "---\n"
        f"name: {artifact.name}\n"
        f"description: {yaml_quote(description)}\n"
        "disable-model-invocation: true\n"
        "---\n\n"
        f"{body}"
    )
    return text.encode("utf-8")


def plan_copy(runtime: str, artifact: Artifact) -> PlannedCopy | str:
    if runtime == "codex":
        if artifact.category != "skills":
            return f"skip {runtime} {artifact.category}/{artifact.name}: Codex installer publishes skills only"
        dest_root = home() / ".codex" / "skills" / artifact.name
        dest_files = iter_skill_files(artifact.source_dir, runtime)
        stamp_path = dest_root / STAMP_FILENAME
        return PlannedCopy(runtime, artifact, dest_root, dest_files, stamp_path)

    if artifact.category == "skills":
        dest_root = home() / ".cursor" / "skills" / artifact.name
        dest_files = iter_skill_files(artifact.source_dir, runtime)
        return PlannedCopy(runtime, artifact, dest_root, dest_files, dest_root / STAMP_FILENAME)

    if artifact.category == "agents":
        dest_root = home() / ".cursor" / "agents"
        filename = f"{artifact.name}.md"
        dest_files = {filename: cursor_agent_markdown(artifact)}
        stamp_path = stamp_store(runtime) / f"{runtime}-agents-{artifact.name}.json"
        return PlannedCopy(runtime, artifact, dest_root, dest_files, stamp_path)

    if artifact.category == "rules":
        dest_root = cursor_install_root() / "rules"
        filename = f"{artifact.name}.mdc"
        dest_files = {filename: cursor_rule_markdown(artifact)}
        stamp_path = stamp_store(runtime) / f"{runtime}-rules-{artifact.name}.json"
        note = (
            "Staged only. Register this as a Cursor user rule (always apply). "
            f"Title: {artifact.name}"
        )
        return PlannedCopy(runtime, artifact, dest_root, dest_files, stamp_path, note=note)

    dest_root = home() / ".cursor" / "skills" / artifact.name
    dest_files = {"SKILL.md": cursor_prompt_skill(artifact)}
    return PlannedCopy(
        runtime,
        artifact,
        dest_root,
        dest_files,
        dest_root / STAMP_FILENAME,
        note="Installed prompt as an explicit-invoke Cursor skill",
    )


def read_stamp(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def existing_dest_files(plan: PlannedCopy) -> dict[str, bytes] | None:
    files: dict[str, bytes] = {}
    for relative in plan.dest_files:
        path = plan.dest_root / relative
        if path.is_file():
            files[relative] = path.read_bytes()
    if files or plan.stamp_path.is_file():
        return files
    return None


def dest_has_local_edits(plan: PlannedCopy, current: dict[str, bytes]) -> bool:
    stamp = read_stamp(plan.stamp_path)
    if stamp is None:
        return bool(current)
    if not current:
        return False
    return str(stamp.get("dest_sha256") or "") != hash_payload(current)


def write_stamp(plan: PlannedCopy, source_sha: str, dest_sha: str) -> None:
    payload = {
        "repository": str(REPOSITORY_ROOT),
        "runtime": plan.runtime,
        "category": plan.artifact.category,
        "name": plan.artifact.name,
        "source_path": plan.artifact.source_key,
        "source_sha256": source_sha,
        "dest_sha256": dest_sha,
        "dest_root": str(plan.dest_root),
        "dest_files": sorted(plan.dest_files),
        "installed_at": utc_now(),
    }
    plan.stamp_path.parent.mkdir(parents=True, exist_ok=True)
    plan.stamp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n")


def refresh_pending_rules() -> None:
    rules_dir = cursor_install_root() / "rules"
    pending = [
        {
            "title": path.stem,
            "content_path": str(path),
            "alwaysApply": True,
        }
        for path in sorted(rules_dir.glob("*.mdc"))
    ] if rules_dir.is_dir() else []
    path = cursor_install_root() / "pending-user-rules.json"
    if not pending:
        if path.is_file():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pending, indent=2) + "\n", encoding="utf-8", newline="\n")


def install_plan(plan: PlannedCopy, *, force: bool, dry_run: bool) -> str:
    source_sha = hash_payload(
        {
            posix(path.relative_to(plan.artifact.source_dir)): path.read_bytes()
            for path in plan.artifact.source_dir.rglob("*")
            if path.is_file()
        }
        if plan.artifact.category == "skills"
        else {posix(entrypoint(plan.artifact).relative_to(plan.artifact.source_dir)): entrypoint(plan.artifact).read_bytes()}
    )
    dest_sha = hash_payload(plan.dest_files)
    current = existing_dest_files(plan)
    if current is not None and dest_has_local_edits(plan, current) and not force:
        raise SystemExit(
            f"Refusing to overwrite modified {plan.runtime} {plan.artifact.category}/{plan.artifact.name} "
            f"at {plan.dest_root}. Re-run with --force to replace it."
        )

    action = "Would install" if dry_run else "Installed"
    if not dry_run:
        if plan.artifact.category == "skills" or (
            plan.runtime == "cursor" and plan.artifact.category == "prompts"
        ):
            if plan.dest_root.exists():
                shutil.rmtree(plan.dest_root)
        plan.dest_root.mkdir(parents=True, exist_ok=True)
        for relative, content in plan.dest_files.items():
            dest = plan.dest_root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
        write_stamp(plan, source_sha, dest_sha)

    message = f"{action} {plan.runtime} {plan.artifact.category}/{plan.artifact.name} -> {plan.dest_root}"
    if plan.note:
        message += f"\n  {plan.note}"
    return message


def uninstall_plan(plan: PlannedCopy, *, dry_run: bool) -> str:
    stamp = read_stamp(plan.stamp_path)
    dest_exists = existing_dest_files(plan) is not None
    if stamp is None and not dest_exists:
        return f"skip uninstall {plan.runtime} {plan.artifact.category}/{plan.artifact.name}: not installed"

    if dest_exists and stamp is None:
        raise SystemExit(
            f"Refusing to uninstall unstamped {plan.runtime} {plan.artifact.category}/{plan.artifact.name} "
            f"at {plan.dest_root}"
        )
    if stamp is not None and Path(str(stamp.get("repository") or "")) != REPOSITORY_ROOT:
        raise SystemExit(
            f"Refusing to uninstall {plan.artifact.name}: stamp repository does not match this playbook"
        )

    action = "Would uninstall" if dry_run else "Uninstalled"
    if not dry_run:
        if plan.artifact.category in {"skills", "prompts"} and plan.dest_root.is_dir():
            shutil.rmtree(plan.dest_root)
        else:
            for relative in plan.dest_files:
                path = plan.dest_root / relative
                if path.is_file():
                    path.unlink()
            if plan.stamp_path.is_file():
                plan.stamp_path.unlink()
    return f"{action} {plan.runtime} {plan.artifact.category}/{plan.artifact.name} from {plan.dest_root}"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", choices=("codex", "cursor", "all"), default="codex")
    parser.add_argument("--scope", choices=("manager", "all"), default="manager")
    parser.add_argument("--name", action="append", default=[], dest="names")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    runtimes = ["codex", "cursor"] if args.runtime == "all" else [args.runtime]
    selected = select_artifacts(discover_artifacts(), args.scope, args.names)
    messages: list[str] = []
    for runtime in runtimes:
        for artifact in selected:
            planned = plan_copy(runtime, artifact)
            if isinstance(planned, str):
                messages.append(planned)
                continue
            if args.uninstall:
                messages.append(uninstall_plan(planned, dry_run=args.dry_run))
            else:
                messages.append(install_plan(planned, force=args.force, dry_run=args.dry_run))

    if not args.dry_run:
        refresh_pending_rules()

    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
