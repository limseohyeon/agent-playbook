#!/usr/bin/env python3
"""Minimal GitHub issue lifecycle client for a personal Codex skill."""

from __future__ import annotations

import argparse
import ctypes
import getpass
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_API_VERSION = "2026-03-10"


class UserError(Exception):
    pass


@dataclass(frozen=True)
class Target:
    remote_name: str
    remote_url: str
    web_base: str
    api_base: str
    owner: str
    repo: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def repo_api_path(self) -> str:
        owner = urllib.parse.quote(self.owner, safe="")
        repo = urllib.parse.quote(self.repo, safe="")
        return f"/repos/{owner}/{repo}"

    @property
    def credential_key(self) -> str:
        identity = f"{self.api_base}|{self.full_name}".lower()
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        host = urllib.parse.urlsplit(self.api_base).netloc
        return f"CodexGitHubIssue:{host}:{digest}"


def compact(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=True, separators=(",", ":")))


def run_git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise UserError(proc.stderr.strip() or "Git command failed")
    return proc.stdout.strip()


def parse_remote(name: str, url: str, api_base_override: str | None) -> Target:
    original = url
    if re.match(r"^[^/@:]+@[^/:]+:.+", url):
        user_host, path = url.split(":", 1)
        host = user_host.rsplit("@", 1)[-1]
        web_base = f"https://{host}"
        repo_path = path
    else:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https", "ssh", "git"} or not parsed.hostname:
            raise UserError(f"Unsupported Git remote URL for {name}")
        scheme = parsed.scheme if parsed.scheme in {"http", "https"} else "https"
        port = f":{parsed.port}" if parsed.port else ""
        host = parsed.hostname
        web_base = f"{scheme}://{host}{port}"
        repo_path = parsed.path.lstrip("/")
    if repo_path.endswith(".git"):
        repo_path = repo_path[:-4]
    parts = [part for part in repo_path.strip("/").split("/") if part]
    if len(parts) != 2:
        raise UserError(f"Cannot derive a GitHub owner/repository from remote {name}")
    if host.lower() == "github.com":
        api_base = api_base_override.rstrip("/") if api_base_override else "https://api.github.com"
    elif api_base_override:
        api_base = api_base_override.rstrip("/")
    else:
        raise UserError(f"Remote {name} is not github.com; pass --api-base for GitHub Enterprise Server")
    return Target(name, original, web_base.rstrip("/"), api_base, parts[0], parts[1])


def detect_target(remote: str | None, api_base: str | None) -> Target:
    names = run_git("remote").splitlines()
    if remote:
        if remote not in names:
            raise UserError(f"Git remote not found: {remote}")
        names = [remote]
    elif "origin" in names:
        names = ["origin"] + [name for name in names if name != "origin"]
    candidates: list[Target] = []
    errors: list[str] = []
    for name in names:
        try:
            candidates.append(parse_remote(name, run_git("remote", "get-url", name), api_base))
        except UserError as exc:
            errors.append(str(exc))
    unique: dict[tuple[str, str], Target] = {
        (candidate.api_base.lower(), candidate.full_name.lower()): candidate
        for candidate in candidates
    }
    if not unique:
        suffix = f": {'; '.join(errors)}" if errors else ""
        raise UserError("No supported GitHub repository remote found" + suffix)
    if len(unique) > 1:
        choices = [f"{item.remote_name}={item.web_base}/{item.full_name}" for item in unique.values()]
        raise UserError("Multiple GitHub repository remotes found; pass --remote. " + "; ".join(choices))
    return next(iter(unique.values()))


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


PCREDENTIALW = ctypes.POINTER(CREDENTIALW)
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


def require_windows() -> Any:
    if os.name != "nt":
        raise UserError("Windows Credential Manager is required")
    advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    advapi32.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(PCREDENTIALW)]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
    advapi32.CredWriteW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    advapi32.CredFree.restype = None
    return advapi32


def credential_write(key: str, token: str) -> None:
    if not token.strip():
        raise UserError("Token cannot be empty")
    advapi32 = require_windows()
    blob = token.encode("utf-16-le")
    blob_buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
    credential = CREDENTIALW()
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = key
    credential.Comment = "Repository-scoped GitHub token for Codex issue lifecycle"
    credential.CredentialBlobSize = len(blob)
    credential.CredentialBlob = ctypes.cast(blob_buffer, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = "github-fine-grained-token"
    if not advapi32.CredWriteW(ctypes.byref(credential), 0):
        raise UserError(f"Credential Manager write failed: {ctypes.get_last_error()}")


def credential_read(key: str) -> str:
    advapi32 = require_windows()
    pointer = PCREDENTIALW()
    if not advapi32.CredReadW(key, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        raise UserError("No credential is registered for this GitHub repository")
    try:
        credential = pointer.contents
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        token = raw.decode("utf-16-le")
        if not token:
            raise UserError("Stored credential is empty")
        return token
    finally:
        advapi32.CredFree(pointer)


class GitHubClient:
    def __init__(self, target: Target, token: str, ca_file: str | None, api_version: str):
        self.target = target
        self.token = token
        self.api_version = api_version
        self.context = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.target.api_base}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "codex-github-issue-lifecycle",
                "X-GitHub-Api-Version": self.api_version,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20, context=self.context) as response:
                data = response.read()
                return json.loads(data.decode("utf-8")) if data else None
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                parsed = json.loads(exc.read().decode("utf-8", errors="replace"))
                message = parsed.get("message") if isinstance(parsed, dict) else None
                detail = f": {message}" if message is not None else ""
            except Exception:
                pass
            raise UserError(f"GitHub API returned HTTP {exc.code}{detail}") from None
        except urllib.error.URLError as exc:
            raise UserError(f"GitHub API connection failed: {exc.reason}") from None

    def paginate(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        separator = "&" if "?" in path else "?"
        while True:
            batch = self.request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise UserError("GitHub API returned an unexpected paginated response")
            items.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 100:
                return items
            page += 1

    def repository(self) -> dict[str, Any]:
        return self.request("GET", self.target.repo_api_path)

    def labels(self) -> set[str]:
        labels = self.paginate(f"{self.target.repo_api_path}/labels")
        return {str(item["name"]) for item in labels}

    def search_plan(self, plan_id: str) -> list[dict[str, Any]]:
        marker = f"codex-plan:{plan_id}:"
        issues = self.paginate(f"{self.target.repo_api_path}/issues?state=all&sort=created&direction=desc")
        return [
            issue for issue in issues
            if "pull_request" not in issue and marker in str(issue.get("body") or "")
        ]

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str],
        parent_issue_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        if parent_issue_id is not None:
            payload["parent_issue_id"] = parent_issue_id
        return self.request("POST", f"{self.target.repo_api_path}/issues", payload)

    def get_issue(self, number: int) -> dict[str, Any]:
        return self.request("GET", f"{self.target.repo_api_path}/issues/{number}")

    def update_issue(self, number: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PATCH", f"{self.target.repo_api_path}/issues/{number}", payload)

    def add_comment(self, number: int, body: str) -> dict[str, Any]:
        return self.request("POST", f"{self.target.repo_api_path}/issues/{number}/comments", {"body": body})

    def add_dependency(self, number: int, blocking_issue_id: int) -> dict[str, Any]:
        return self.request(
            "POST",
            f"{self.target.repo_api_path}/issues/{number}/dependencies/blocked_by",
            {"issue_id": blocking_issue_id},
        )


def read_stdin_json() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise UserError(f"Invalid JSON input: {exc.msg}") from None
    if not isinstance(value, dict):
        raise UserError("JSON input must be an object")
    return value


def string_list(item: dict[str, Any], field: str) -> list[str]:
    value = item.get(field, [])
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(entry, str) or not entry.strip() for entry in value):
        raise UserError(f"{field} must be a list of non-empty strings")
    return [entry.strip() for entry in value]


def optional_string(item: dict[str, Any], field: str) -> str | None:
    value = item.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise UserError(f"{field} must be a non-empty string or null")
    return value.strip()


def validate_item(item: Any, child: bool) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise UserError("Every issue item must be an object")
    required = ["title", "purpose", "acceptance_criteria"] + (["key"] if child else [])
    for field in required:
        expected = list if field == "acceptance_criteria" else str
        if not isinstance(item.get(field), expected) or not item.get(field):
            raise UserError(f"Missing or invalid field: {field}")
    normalized = {
        "title": str(item["title"]).strip(),
        "purpose": str(item["purpose"]).strip(),
        "in_scope": string_list(item, "in_scope"),
        "out_of_scope": string_list(item, "out_of_scope"),
        "acceptance_criteria": string_list(item, "acceptance_criteria"),
        "dependencies": string_list(item, "dependencies"),
        "labels": string_list(item, "labels"),
        "priority": item.get("priority"),
        "template": optional_string(item, "template"),
        "body": optional_string(item, "body"),
    }
    if child:
        normalized["key"] = str(item["key"]).strip()
    if normalized["priority"] is not None and not isinstance(normalized["priority"], str):
        raise UserError("priority must be a string or null")
    return normalized


def validate_tree(payload: dict[str, Any]) -> dict[str, Any]:
    plan_id = payload.get("plan_id")
    if not isinstance(plan_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,79}", plan_id):
        raise UserError("plan_id must be 3-80 characters using letters, numbers, dot, underscore, or hyphen")
    parent = validate_item(payload.get("parent"), child=False)
    raw_children = payload.get("children")
    if not isinstance(raw_children, list) or not raw_children:
        raise UserError("children must contain at least one item")
    children = [validate_item(item, child=True) for item in raw_children]
    keys = [item["key"] for item in children]
    if len(set(keys)) != len(keys):
        raise UserError("Child keys must be unique")
    known = set(keys)
    for item in children:
        unknown = set(item["dependencies"]) - known
        if unknown:
            raise UserError(f"Unknown dependencies for {item['key']}: {', '.join(sorted(unknown))}")
        if item["key"] in item["dependencies"]:
            raise UserError(f"Child {item['key']} cannot depend on itself")
    return {"plan_id": plan_id, "parent": parent, "children": children}


def bullet_section(title: str, values: list[str], checklist: bool = False) -> list[str]:
    lines = [f"## {title}", ""]
    if values:
        prefix = "- [ ] " if checklist else "- "
        lines.extend(prefix + value for value in values)
    else:
        lines.append("- None")
    lines.append("")
    return lines


def render_description(
    item: dict[str, Any],
    marker: str,
    parent_number: int | None = None,
    children: list[dict[str, Any]] | None = None,
    dependency_numbers: dict[str, int] | None = None,
) -> str:
    if item["body"] is not None:
        lines = [item["body"].rstrip(), "", f"<!-- Tracking ID: {marker} -->", ""]
        if parent_number is not None:
            lines.extend([f"Parent: #{parent_number}", ""])
        if item["dependencies"]:
            dependencies = [
                f"#{dependency_numbers[key]} {key}" if dependency_numbers and key in dependency_numbers else key
                for key in item["dependencies"]
            ]
            lines += bullet_section("Dependencies", dependencies)
        if children is not None:
            lines.extend(["## Child issues", ""])
            if children:
                lines.extend(f"- [ ] #{child['number']} {child['title']}" for child in children)
            else:
                lines.append("- Pending issue creation")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    lines = [f"Tracking ID: `{marker}`", "", "## Purpose", "", item["purpose"], ""]
    if parent_number is not None:
        lines.extend([f"Parent: #{parent_number}", ""])
    lines += bullet_section("In scope", item["in_scope"])
    lines += bullet_section("Out of scope", item["out_of_scope"])
    lines += bullet_section("Acceptance criteria", item["acceptance_criteria"], checklist=True)
    if item["dependencies"]:
        dependencies = [
            f"#{dependency_numbers[key]} {key}" if dependency_numbers and key in dependency_numbers else key
            for key in item["dependencies"]
        ]
        lines += bullet_section("Dependencies", dependencies)
    if item["priority"]:
        lines.extend(["## Priority", "", str(item["priority"]), ""])
    if children is not None:
        lines.extend(["## Child issues", ""])
        if children:
            lines.extend(f"- [ ] #{child['number']} {child['title']}" for child in children)
        else:
            lines.append("- Pending issue creation")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_comment(payload: dict[str, Any]) -> str:
    completed = string_list(payload, "completed")
    verification = string_list(payload, "verification")
    blockers = string_list(payload, "blockers")
    next_step = payload.get("next_step")
    if not isinstance(next_step, str) or not next_step.strip():
        raise UserError("next_step must be a non-empty string")
    lines = ["## Agent progress", ""]
    lines += bullet_section("Completed", completed)
    lines += bullet_section("Verification", verification)
    lines += bullet_section("Blockers", blockers)
    lines.extend(["## Next step", "", next_step.strip()])
    return "\n".join(lines).rstrip() + "\n"


def client_for(args: argparse.Namespace, target: Target) -> GitHubClient:
    return GitHubClient(target, credential_read(target.credential_key), args.ca_file, args.api_version)


def safe_target(target: Target) -> dict[str, Any]:
    return {
        "remote": target.remote_name,
        "web_base": target.web_base,
        "api_base": target.api_base,
        "repository": target.full_name,
        "credential_key": target.credential_key,
    }


def command_target(args: argparse.Namespace, target: Target) -> None:
    compact(safe_target(target))


def command_credential_set(args: argparse.Namespace, target: Target) -> None:
    token = getpass.getpass("GitHub fine-grained personal access token: ")
    credential_write(target.credential_key, token)
    compact({"credential": "stored", "repository": target.full_name, "credential_key": target.credential_key})


def command_check(args: argparse.Namespace, target: Target) -> None:
    repository = client_for(args, target).repository()
    compact({
        "status": "ok",
        "id": repository.get("id"),
        "full_name": repository.get("full_name"),
        "html_url": repository.get("html_url"),
        "has_issues": repository.get("has_issues"),
    })


def command_labels(args: argparse.Namespace, target: Target) -> None:
    labels = sorted(client_for(args, target).labels(), key=str.casefold)
    compact({"labels": labels})


def discover_issue_templates() -> list[dict[str, str]]:
    root = Path(run_git("rev-parse", "--show-toplevel"))
    directory = root / ".github" / "ISSUE_TEMPLATE"
    if not directory.is_dir():
        return []
    templates: list[dict[str, str]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
        if not path.is_file() or path.name.casefold() == "config.yml":
            continue
        suffix = path.suffix.casefold()
        if suffix not in {".md", ".yml", ".yaml"}:
            continue
        templates.append({
            "path": path.relative_to(root).as_posix(),
            "format": "markdown" if suffix == ".md" else "issue-form",
        })
    return templates


def command_templates(args: argparse.Namespace, target: Target) -> None:
    compact({"templates": discover_issue_templates()})


def apply_template_policy(tree: dict[str, Any]) -> dict[str, Any]:
    templates = discover_issue_templates()
    if not templates:
        for item in [tree["parent"], *tree["children"]]:
            if item["template"] is not None or item["body"] is not None:
                raise UserError("template and body must be omitted when the repository has no issue templates")
        return tree

    paths = {item["path"] for item in templates}
    sole_template = next(iter(paths)) if len(paths) == 1 else None
    for item in [tree["parent"], *tree["children"]]:
        if item["template"] is None:
            if sole_template is None:
                raise UserError("Multiple issue templates exist; select a template for every parent and child item")
            item["template"] = sole_template
        if item["template"] not in paths:
            raise UserError(f"Issue template not found: {item['template']}")
        if item["body"] is None:
            raise UserError(f"body is required when using issue template: {item['template']}")
    return tree


def filter_labels(item: dict[str, Any], existing: set[str]) -> tuple[list[str], list[str]]:
    matched = [label for label in item["labels"] if label in existing]
    skipped = [label for label in item["labels"] if label not in existing]
    return matched, skipped


def command_dry_run(args: argparse.Namespace, target: Target) -> None:
    tree = apply_template_policy(validate_tree(read_stdin_json()))
    compact({
        "target": {"web_base": target.web_base, "repository": target.full_name},
        "plan_id": tree["plan_id"],
        "parent": tree["parent"],
        "children": tree["children"],
        "writes": 0,
    })


def command_create_tree(args: argparse.Namespace, target: Target) -> None:
    if args.confirm != "CREATE":
        raise UserError("create-tree requires --confirm CREATE after user approval")
    tree = apply_template_policy(validate_tree(read_stdin_json()))
    client = client_for(args, target)
    existing = client.search_plan(tree["plan_id"])
    if existing:
        compact({
            "status": "duplicate",
            "plan_id": tree["plan_id"],
            "issues": [
                {"number": item.get("number"), "title": item.get("title"), "html_url": item.get("html_url")}
                for item in existing
            ],
        })
        return
    existing_labels = client.labels()
    created: list[dict[str, Any]] = []
    skipped_labels: dict[str, list[str]] = {}
    try:
        parent_labels, parent_skipped = filter_labels(tree["parent"], existing_labels)
        if parent_skipped:
            skipped_labels["parent"] = parent_skipped
        parent_marker = f"codex-plan:{tree['plan_id']}:parent"
        parent_body = render_description(tree["parent"], parent_marker, children=[])
        parent = client.create_issue(tree["parent"]["title"], parent_body, parent_labels)
        parent_summary = {
            "kind": "parent",
            "id": parent["id"],
            "number": parent["number"],
            "title": parent["title"],
            "html_url": parent["html_url"],
        }
        created.append(parent_summary)
        child_summaries: list[dict[str, Any]] = []
        for child in tree["children"]:
            labels, skipped = filter_labels(child, existing_labels)
            if skipped:
                skipped_labels[child["key"]] = skipped
            marker = f"codex-plan:{tree['plan_id']}:{child['key']}"
            body = render_description(child, marker, parent_number=int(parent["number"]))
            issue = client.create_issue(
                child["title"],
                body,
                labels,
                parent_issue_id=int(parent["id"]),
            )
            summary = {
                "kind": "child",
                "key": child["key"],
                "id": issue["id"],
                "number": issue["number"],
                "title": issue["title"],
                "html_url": issue["html_url"],
            }
            created.append(summary)
            child_summaries.append(summary)
        number_by_key = {child["key"]: int(child["number"]) for child in child_summaries}
        id_by_key = {child["key"]: int(child["id"]) for child in child_summaries}
        for child, summary in zip(tree["children"], child_summaries, strict=True):
            marker = f"codex-plan:{tree['plan_id']}:{child['key']}"
            final_body = render_description(
                child,
                marker,
                parent_number=int(parent["number"]),
                dependency_numbers=number_by_key,
            )
            client.update_issue(int(summary["number"]), {"body": final_body})
            for dependency_key in child["dependencies"]:
                client.add_dependency(int(summary["number"]), id_by_key[dependency_key])
        final_parent_body = render_description(tree["parent"], parent_marker, children=child_summaries)
        client.update_issue(int(parent["number"]), {"body": final_parent_body})
        public_issues = [
            {key: item[key] for key in ("kind", "number", "title", "html_url")}
            for item in created
        ]
        compact({
            "status": "created",
            "plan_id": tree["plan_id"],
            "issues": public_issues,
            "skipped_labels": skipped_labels,
        })
    except (UserError, KeyError, TypeError, ValueError) as exc:
        public_created = [
            {key: item.get(key) for key in ("kind", "number", "title", "html_url")}
            for item in created
        ]
        compact({"status": "partial_failure", "error": str(exc), "created": public_created})
        raise SystemExit(2)


def command_comment(args: argparse.Namespace, target: Target) -> None:
    if args.confirm != "UPDATE":
        raise UserError("comment requires --confirm UPDATE")
    comment = client_for(args, target).add_comment(args.issue, render_comment(read_stdin_json()))
    compact({"status": "commented", "issue_number": args.issue, "comment_id": comment.get("id")})


def command_close(args: argparse.Namespace, target: Target) -> None:
    if args.confirm != "CLOSE":
        raise UserError("close requires --confirm CLOSE after user approval")
    client = client_for(args, target)
    issue = client.update_issue(args.issue, {"state": "closed", "state_reason": "completed"})
    parent_updated = None
    body = str(issue.get("body") or "")
    parent_match = re.search(r"^Parent: #(\d+)\s*$", body, flags=re.MULTILINE)
    if parent_match:
        parent_number = int(parent_match.group(1))
        parent = client.get_issue(parent_number)
        parent_body = str(parent.get("body") or "")
        pattern = rf"^- \[ \] #{args.issue}(?=\s)"
        updated_body, count = re.subn(pattern, f"- [x] #{args.issue}", parent_body, count=1, flags=re.MULTILINE)
        if count:
            client.update_issue(parent_number, {"body": updated_body})
            parent_updated = parent_number
    compact({
        "status": issue.get("state"),
        "issue_number": issue.get("number"),
        "html_url": issue.get("html_url"),
        "parent_updated": parent_updated,
    })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def command_parser(name: str) -> argparse.ArgumentParser:
        command = subparsers.add_parser(name)
        command.add_argument("--remote", help="Git remote name when more than one GitHub repository remote exists")
        command.add_argument("--api-base", help="GitHub Enterprise Server REST API root, such as https://host/api/v3")
        command.add_argument("--api-version", default=DEFAULT_API_VERSION, help="GitHub REST API version header")
        command.add_argument("--ca-file", help="Approved PEM CA bundle for internal TLS")
        return command

    command_parser("target")
    command_parser("credential-set")
    command_parser("check")
    command_parser("labels")
    command_parser("templates")
    command_parser("dry-run")
    create = command_parser("create-tree")
    create.add_argument("--confirm", required=True)
    comment = command_parser("comment")
    comment.add_argument("--issue", required=True, type=int)
    comment.add_argument("--confirm", required=True)
    close = command_parser("close")
    close.add_argument("--issue", required=True, type=int)
    close.add_argument("--confirm", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        target = detect_target(args.remote, args.api_base)
        commands = {
            "target": command_target,
            "credential-set": command_credential_set,
            "check": command_check,
            "labels": command_labels,
            "templates": command_templates,
            "dry-run": command_dry_run,
            "create-tree": command_create_tree,
            "comment": command_comment,
            "close": command_close,
        }
        commands[args.command](args, target)
        return 0
    except UserError as exc:
        compact({"status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
