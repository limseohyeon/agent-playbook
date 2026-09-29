#!/usr/bin/env python3
"""Copy playbook artifacts into the Codex runtime home."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_GITHUB_SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
if str(_GITHUB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_GITHUB_SCRIPTS))

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MANAGER_SKILL = "agent-playbook-manager"
STAMP_FILENAME = ".playbook-stamp.json"
CODEX_RULES_STATE_FILENAME = "codex-rules.json"
MANAGED_RULES_START = "<!-- agent-playbook:managed-rules:start -->"
MANAGED_RULES_END = "<!-- agent-playbook:managed-rules:end -->"
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


@dataclass(frozen=True)
class CodexRulesState:
    repository: str
    rules: dict[str, dict[str, str]]
    managed_sha256: str


def home() -> Path:
    return Path.home()


def stamp_store() -> Path:
    return home() / ".codex" / "playbook-install" / "stamps"


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


def hash_text(text: str) -> str:
    return hashlib.sha256(normalized_bytes(text.encode("utf-8"))).hexdigest()


def repository_revision() -> tuple[str | None, bool | None]:
    try:
        commit = subprocess.run(
            ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(REPOSITORY_ROOT), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return commit, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        temporary.write_text(text, encoding="utf-8", newline="\n")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


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


def codex_agents_path() -> Path:
    return home() / ".codex" / "AGENTS.md"


def codex_rules_state_path() -> Path:
    return stamp_store() / CODEX_RULES_STATE_FILENAME


def rule_body(artifact: Artifact) -> str:
    _, body = split_frontmatter(entrypoint(artifact).read_text(encoding="utf-8"))
    body = body.strip()
    if not body:
        raise SystemExit(f"Rule {artifact.name} has no instruction body")
    return body + "\n"


def managed_rules_text(artifacts: list[Artifact]) -> str:
    sections = [
        MANAGED_RULES_START,
        "<!-- Generated from D:\\agent-playbook. Edit the repository source, not this block. -->",
    ]
    for artifact in sorted(artifacts, key=lambda item: item.name.casefold()):
        sections.extend(
            (
                f"<!-- source: {artifact.source_key} -->",
                rule_body(artifact).rstrip(),
            )
        )
    sections.append(MANAGED_RULES_END)
    return "\n\n".join(sections) + "\n"


def split_managed_rules(text: str) -> tuple[str, str | None, str]:
    start = text.find(MANAGED_RULES_START)
    end = text.find(MANAGED_RULES_END)
    if start == -1 and end == -1:
        return text, None, ""
    if start == -1 or end == -1 or end < start:
        raise SystemExit(
            f"Malformed agent-playbook rule block in {codex_agents_path()}. "
            "Repair the markers before continuing."
        )
    end += len(MANAGED_RULES_END)
    if text.find(MANAGED_RULES_START, start + len(MANAGED_RULES_START)) != -1:
        raise SystemExit(f"Multiple agent-playbook rule blocks found in {codex_agents_path()}")
    if text.find(MANAGED_RULES_END, end) != -1:
        raise SystemExit(f"Multiple agent-playbook rule blocks found in {codex_agents_path()}")
    managed = text[start:end]
    if end < len(text) and text[end] == "\n":
        end += 1
    return text[:start], managed, text[end:]


def read_codex_rules_state() -> CodexRulesState | None:
    path = codex_rules_state_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        repository = data.get("repository")
        rules = data.get("rules")
        managed_sha = data.get("managed_sha256")
        if (
            not isinstance(repository, str)
            or not isinstance(rules, dict)
            or not isinstance(managed_sha, str)
        ):
            return None
        normalized: dict[str, dict[str, str]] = {}
        for name, metadata in rules.items():
            if not isinstance(name, str) or not isinstance(metadata, dict):
                return None
            normalized[name] = {str(key): str(value) for key, value in metadata.items()}
        return CodexRulesState(repository, normalized, managed_sha)
    except (OSError, json.JSONDecodeError):
        return None


def write_codex_rules_state(artifacts: list[Artifact], managed: str) -> None:
    commit, dirty = repository_revision()
    payload = {
        "repository": str(REPOSITORY_ROOT),
        "runtime": "codex",
        "category": "rules",
        "rules": {
            artifact.name: {
                "source_path": artifact.source_key,
                "source_sha256": hash_text(entrypoint(artifact).read_text(encoding="utf-8")),
            }
            for artifact in sorted(artifacts, key=lambda item: item.name.casefold())
        },
        "managed_sha256": hash_text(managed.rstrip() + "\n"),
        "repository_commit": commit,
        "repository_dirty": dirty,
        "installed_at": utc_now(),
    }
    atomic_write_text(codex_rules_state_path(), json.dumps(payload, indent=2) + "\n")


def compose_agents_text(
    original: str,
    managed: str | None,
    *,
    selected_for_first_install: list[Artifact],
) -> str:
    before, existing, after = split_managed_rules(original)
    if existing is None:
        stripped = original.strip()
        selected_bodies = {rule_body(artifact).strip() for artifact in selected_for_first_install}
        if stripped and stripped in selected_bodies:
            before = ""
            after = ""
        elif stripped:
            before = original.rstrip() + "\n\n"
            after = ""
        else:
            before = ""
            after = ""
    else:
        before = before.rstrip()
        after = after.lstrip("\n")
        before = before + ("\n\n" if before else "")
        after = ("\n" + after if after else "")

    if managed is None:
        return (before + after).strip() + ("\n" if (before + after).strip() else "")
    return before + managed + after


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


def iter_skill_files(source_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for path in source_dir.rglob("*"):
        if not path.is_file() or any(part in SKIP_DIR_NAMES for part in path.relative_to(source_dir).parts):
            continue
        relative = path.relative_to(source_dir)
        if relative.name == STAMP_FILENAME:
            continue
        files[posix(relative)] = path.read_bytes()
    if "SKILL.md" not in files:
        raise SystemExit(f"Missing SKILL.md in {posix(source_dir.relative_to(REPOSITORY_ROOT))}")
    return files


def plan_copy(artifact: Artifact) -> PlannedCopy | str:
    if artifact.category != "skills":
        return f"skip codex {artifact.category}/{artifact.name}: Codex installer publishes skills only"
    dest_root = home() / ".codex" / "skills" / artifact.name
    dest_files = iter_skill_files(artifact.source_dir)
    stamp_path = dest_root / STAMP_FILENAME
    return PlannedCopy("codex", artifact, dest_root, dest_files, stamp_path)


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
    owns_directory = plan.artifact.category == "skills"
    if owns_directory and plan.dest_root.is_dir():
        for path in plan.dest_root.rglob("*"):
            if path.is_file() and path != plan.stamp_path:
                files[posix(path.relative_to(plan.dest_root))] = path.read_bytes()
    else:
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
    commit, dirty = repository_revision()
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
        "repository_commit": commit,
        "repository_dirty": dirty,
        "installed_at": utc_now(),
    }
    atomic_write_text(plan.stamp_path, json.dumps(payload, indent=2) + "\n")


def replace_directory(destination: Path, files: dict[str, bytes]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staging = destination.with_name(f".{destination.name}.staging-{token}")
    backup = destination.with_name(f".{destination.name}.backup-{token}")
    try:
        staging.mkdir()
        for relative, content in files.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        if destination.exists():
            destination.rename(backup)
        staging.rename(destination)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if not destination.exists() and backup.exists():
            backup.rename(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def install_plan(plan: PlannedCopy, *, force: bool, dry_run: bool) -> str:
    source_sha = source_hash_for_plan(plan)
    dest_sha = hash_payload(plan.dest_files)
    current = existing_dest_files(plan)
    if current is not None and dest_has_local_edits(plan, current) and not force:
        raise SystemExit(
            f"Refusing to overwrite modified {plan.runtime} {plan.artifact.category}/{plan.artifact.name} "
            f"at {plan.dest_root}. Re-run with --force to replace it."
        )

    action = "Would install" if dry_run else "Installed"
    if not dry_run:
        if plan.artifact.category == "skills":
            replace_directory(plan.dest_root, plan.dest_files)
        else:
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


def uninstall_plan(plan: PlannedCopy, *, force: bool, dry_run: bool) -> str:
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
    current = existing_dest_files(plan)
    if current is not None and dest_has_local_edits(plan, current) and not force:
        raise SystemExit(
            f"Refusing to uninstall modified {plan.runtime} {plan.artifact.category}/{plan.artifact.name} "
            f"at {plan.dest_root}. Re-run with --force only after reviewing it."
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


def validate_codex_rule_state(
    agents_text: str,
    state: CodexRulesState | None,
    *,
    force: bool,
) -> None:
    _, managed, _ = split_managed_rules(agents_text)
    if state is None:
        if managed is not None and not force:
            raise SystemExit(
                f"Refusing to replace an untracked agent-playbook rule block in {codex_agents_path()}. "
                "Re-run with --force only after reviewing it."
            )
        return
    if Path(state.repository) != REPOSITORY_ROOT:
        raise SystemExit(
            f"Refusing to manage Codex rules installed by another repository: {state.repository}"
        )
    if managed is None:
        if state.rules and not force:
            raise SystemExit(
                f"The managed rule block recorded in {codex_rules_state_path()} is missing from "
                f"{codex_agents_path()}. Re-run with --force only after reviewing the file."
            )
        return
    current_sha = hash_text(managed.rstrip() + "\n")
    if current_sha != state.managed_sha256 and not force:
        raise SystemExit(
            f"Refusing to overwrite a modified managed rule block in {codex_agents_path()}. "
            "Re-run with --force only after reviewing the changes."
        )


def sync_codex_rules(
    selected: list[Artifact],
    all_artifacts: list[Artifact],
    *,
    uninstall: bool,
    force: bool,
    dry_run: bool,
) -> list[str]:
    if not selected:
        return []
    available = {
        artifact.name: artifact for artifact in all_artifacts if artifact.category == "rules"
    }
    state = read_codex_rules_state()
    installed_names = set(state.rules if state else {})
    selected_names = {artifact.name for artifact in selected}
    target_names = (
        installed_names - selected_names if uninstall else installed_names | selected_names
    )
    missing = sorted(name for name in target_names if name not in available)
    if missing:
        raise SystemExit(
            "Installed rule source is missing from the repository: " + ", ".join(missing)
        )

    agents_path = codex_agents_path()
    original = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else ""
    validate_codex_rule_state(original, state, force=force)
    target_artifacts = [available[name] for name in sorted(target_names)]
    managed = managed_rules_text(target_artifacts) if target_artifacts else None
    updated = compose_agents_text(
        original,
        managed,
        selected_for_first_install=selected if state is None else [],
    )

    verb = "uninstall" if uninstall else "install"
    messages = [
        f"Would {verb} codex rules/{artifact.name} in {agents_path}"
        for artifact in selected
    ]
    if dry_run:
        return messages

    state_path = codex_rules_state_path()
    atomic_write_text(agents_path, updated)
    try:
        if target_artifacts and managed is not None:
            write_codex_rules_state(target_artifacts, managed)
        elif state_path.is_file():
            state_path.unlink()
    except Exception:
        atomic_write_text(agents_path, original)
        raise
    completed = "Uninstalled" if uninstall else "Installed"
    return [
        f"{completed} codex rules/{artifact.name} in {agents_path}"
        for artifact in selected
    ]


def source_hash_for_plan(plan: PlannedCopy) -> str:
    if plan.artifact.category == "skills":
        files = {
            posix(path.relative_to(plan.artifact.source_dir)): path.read_bytes()
            for path in plan.artifact.source_dir.rglob("*")
            if path.is_file()
            and not any(
                part in SKIP_DIR_NAMES
                for part in path.relative_to(plan.artifact.source_dir).parts
            )
            and path.name != STAMP_FILENAME
        }
    else:
        source = entrypoint(plan.artifact)
        files = {posix(source.relative_to(plan.artifact.source_dir)): source.read_bytes()}
    return hash_payload(files)


def copy_install_status(plan: PlannedCopy) -> str:
    current = existing_dest_files(plan)
    if current is None:
        return "not installed"
    stamp = read_stamp(plan.stamp_path)
    if stamp is None:
        return "unmanaged destination"
    if dest_has_local_edits(plan, current):
        return "modified destination"
    if str(stamp.get("source_sha256") or "") != source_hash_for_plan(plan):
        return "update available"
    return "installed"


def codex_rule_status(artifact: Artifact) -> str:
    state = read_codex_rules_state()
    agents_path = codex_agents_path()
    text = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else ""
    _, managed, _ = split_managed_rules(text)
    if state is None:
        return "unmanaged destination" if managed is not None else "not installed"
    if artifact.name not in state.rules:
        return "not installed"
    if managed is None or hash_text(managed.rstrip() + "\n") != state.managed_sha256:
        return "modified destination"
    recorded = state.rules[artifact.name].get("source_sha256", "")
    current = hash_text(entrypoint(artifact).read_text(encoding="utf-8"))
    return "installed" if recorded == current else "update available"


def inventory(artifacts: list[Artifact]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for artifact in artifacts:
        if artifact.category == "rules":
            status = codex_rule_status(artifact)
        else:
            planned = plan_copy(artifact)
            if isinstance(planned, str):
                continue
            status = copy_install_status(planned)
        records.append(
            {
                "runtime": "codex",
                "category": artifact.category,
                "name": artifact.name,
                "status": status,
                "source": artifact.source_key,
            }
        )
    return records


def print_inventory(records: list[dict[str, str]], *, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(records, indent=2))
        return
    for record in records:
        print(
            f"{record['runtime']} {record['category']}/{record['name']}: "
            f"{record['status']}"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("manager", "all"), default="manager")
    parser.add_argument("--name", action="append", default=[], dest="names")
    parser.add_argument("--force", action="store_true")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--uninstall", action="store_true")
    action.add_argument("--list", action="store_true", dest="list_available")
    action.add_argument("--status", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    all_artifacts = discover_artifacts()
    if args.list_available or args.status:
        selected = (
            select_artifacts(all_artifacts, "all", args.names)
            if args.names
            else all_artifacts
        )
        records = inventory(selected)
        if args.status:
            records = [record for record in records if record["status"] != "not installed"]
        print_inventory(records, output_format=args.format)
        return 0

    selected = select_artifacts(all_artifacts, args.scope, args.names)
    messages: list[str] = []
    selected_rules = [artifact for artifact in selected if artifact.category == "rules"]
    messages.extend(
        sync_codex_rules(
            selected_rules,
            all_artifacts,
            uninstall=args.uninstall,
            force=args.force,
            dry_run=args.dry_run,
        )
    )
    for artifact in (item for item in selected if item.category != "rules"):
        planned = plan_copy(artifact)
        if isinstance(planned, str):
            messages.append(planned)
            continue
        if args.uninstall:
            messages.append(uninstall_plan(planned, force=args.force, dry_run=args.dry_run))
        else:
            messages.append(install_plan(planned, force=args.force, dry_run=args.dry_run))

    for message in messages:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
