#!/usr/bin/env python3
"""Minimal GitLab issue lifecycle client for a personal Codex skill."""

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
from typing import Any


class UserError(Exception):
    pass


@dataclass(frozen=True)
class Target:
    remote_name: str
    remote_url: str
    base_url: str
    project_path: str

    @property
    def api_base(self) -> str:
        return f"{self.base_url}/api/v4"

    @property
    def project_id(self) -> str:
        return urllib.parse.quote(self.project_path, safe="")

    @property
    def credential_key(self) -> str:
        identity = f"{self.base_url}|{self.project_path}".lower()
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        host = urllib.parse.urlsplit(self.base_url).netloc
        return f"CodexGitLabIssue:{host}:{digest}"


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
        base_url = f"https://{host}"
        project_path = path
    else:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https", "ssh", "git"} or not parsed.hostname:
            raise UserError(f"Unsupported Git remote URL for {name}")
        scheme = parsed.scheme if parsed.scheme in {"http", "https"} else "https"
        port = f":{parsed.port}" if parsed.port else ""
        base_url = f"{scheme}://{parsed.hostname}{port}"
        project_path = parsed.path.lstrip("/")
    if project_path.endswith(".git"):
        project_path = project_path[:-4]
    project_path = project_path.strip("/")
    if not project_path or "/" not in project_path:
        raise UserError(f"Cannot derive a GitLab project path from remote {name}")
    if api_base_override:
        override = api_base_override.rstrip("/")
        suffix = "/api/v4"
        base_url = override[: -len(suffix)] if override.endswith(suffix) else override
    return Target(name, original, base_url.rstrip("/"), project_path)


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
            url = run_git("remote", "get-url", name)
            candidates.append(parse_remote(name, url, api_base))
        except UserError as exc:
            errors.append(str(exc))
    unique: dict[tuple[str, str], Target] = {
        (candidate.base_url.lower(), candidate.project_path): candidate
        for candidate in candidates
    }
    if not unique:
        suffix = f": {'; '.join(errors)}" if errors else ""
        raise UserError("No supported GitLab project remote found" + suffix)
    if len(unique) > 1:
        choices = [f"{item.remote_name}={item.base_url}/{item.project_path}" for item in unique.values()]
        raise UserError("Multiple project remotes found; pass --remote. " + "; ".join(choices))
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
    credential.Comment = "Project-scoped GitLab token for Codex issue lifecycle"
    credential.CredentialBlobSize = len(blob)
    credential.CredentialBlob = ctypes.cast(blob_buffer, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = "gitlab-project-token"
    if not advapi32.CredWriteW(ctypes.byref(credential), 0):
        raise UserError(f"Credential Manager write failed: {ctypes.get_last_error()}")


def credential_read(key: str) -> str:
    advapi32 = require_windows()
    pointer = PCREDENTIALW()
    if not advapi32.CredReadW(key, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        raise UserError("No credential is registered for this GitLab project")
    try:
        credential = pointer.contents
        raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        token = raw.decode("utf-16-le")
        if not token:
            raise UserError("Stored credential is empty")
        return token
    finally:
        advapi32.CredFree(pointer)


class GitLabClient:
    def __init__(self, target: Target, token: str, ca_file: str | None):
        self.target = target
        self.token = token
        self.context = ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context()

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.target.api_base}{path}",
            data=body,
            method=method,
            headers={"PRIVATE-TOKEN": self.token, "Accept": "application/json", "Content-Type": "application/json"},
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
            raise UserError(f"GitLab API returned HTTP {exc.code}{detail}") from None
        except urllib.error.URLError as exc:
            raise UserError(f"GitLab API connection failed: {exc.reason}") from None

    def project(self) -> dict[str, Any]:
        return self.request("GET", f"/projects/{self.target.project_id}")

    def labels(self) -> set[str]:
        labels = self.request("GET", f"/projects/{self.target.project_id}/labels?per_page=100")
        return {str(item["name"]) for item in labels}

    def search_plan(self, plan_id: str) -> list[dict[str, Any]]:
        search = urllib.parse.quote(f"codex-plan:{plan_id}")
        return self.request("GET", f"/projects/{self.target.project_id}/issues?scope=all&state=all&search={search}&per_page=100")

    def create_issue(self, title: str, description: str, labels: list[str]) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title, "description": description}
        if labels:
            payload["labels"] = ",".join(labels)
        return self.request("POST", f"/projects/{self.target.project_id}/issues", payload)

    def get_issue(self, iid: int) -> dict[str, Any]:
        return self.request("GET", f"/projects/{self.target.project_id}/issues/{iid}")

    def update_issue(self, iid: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("PUT", f"/projects/{self.target.project_id}/issues/{iid}", payload)

    def add_note(self, iid: int, body: str) -> dict[str, Any]:
        return self.request("POST", f"/projects/{self.target.project_id}/issues/{iid}/notes", {"body": body})


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
    parent_iid: int | None = None,
    children: list[dict[str, Any]] | None = None,
    dependency_iids: dict[str, int] | None = None,
) -> str:
    lines = [f"Tracking ID: `{marker}`", "", "## Purpose", "", item["purpose"], ""]
    if parent_iid is not None:
        lines.extend([f"Parent: #{parent_iid}", ""])
    lines += bullet_section("In scope", item["in_scope"])
    lines += bullet_section("Out of scope", item["out_of_scope"])
    lines += bullet_section("Acceptance criteria", item["acceptance_criteria"], checklist=True)
    if item["dependencies"]:
        dependencies = [
            f"#{dependency_iids[key]} {key}" if dependency_iids and key in dependency_iids else key
            for key in item["dependencies"]
        ]
        lines += bullet_section("Dependencies", dependencies)
    if item["priority"]:
        lines.extend(["## Priority", "", str(item["priority"]), ""])
    if children is not None:
        lines.extend(["## Child issues", ""])
        if children:
            lines.extend(f"- [ ] #{child['iid']} {child['title']}" for child in children)
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


def client_for(args: argparse.Namespace, target: Target) -> GitLabClient:
    return GitLabClient(target, credential_read(target.credential_key), args.ca_file)


def safe_target(target: Target) -> dict[str, Any]:
    return {
        "remote": target.remote_name,
        "base_url": target.base_url,
        "project_path": target.project_path,
        "credential_key": target.credential_key,
    }


def command_target(args: argparse.Namespace, target: Target) -> None:
    compact(safe_target(target))


def command_credential_set(args: argparse.Namespace, target: Target) -> None:
    token = getpass.getpass("GitLab project access token: ")
    credential_write(target.credential_key, token)
    compact({"credential": "stored", "project_path": target.project_path, "credential_key": target.credential_key})


def command_check(args: argparse.Namespace, target: Target) -> None:
    project = client_for(args, target).project()
    compact({"status": "ok", "id": project.get("id"), "path_with_namespace": project.get("path_with_namespace"), "web_url": project.get("web_url")})


def command_labels(args: argparse.Namespace, target: Target) -> None:
    labels = sorted(client_for(args, target).labels(), key=str.casefold)
    compact({"labels": labels})


def filter_labels(item: dict[str, Any], existing: set[str]) -> tuple[list[str], list[str]]:
    matched = [label for label in item["labels"] if label in existing]
    skipped = [label for label in item["labels"] if label not in existing]
    return matched, skipped


def command_dry_run(args: argparse.Namespace, target: Target) -> None:
    tree = validate_tree(read_stdin_json())
    compact({
        "target": {"base_url": target.base_url, "project_path": target.project_path},
        "plan_id": tree["plan_id"],
        "parent": {"title": tree["parent"]["title"], "labels": tree["parent"]["labels"]},
        "children": [{"key": child["key"], "title": child["title"], "labels": child["labels"]} for child in tree["children"]],
        "writes": 0,
    })


def command_create_tree(args: argparse.Namespace, target: Target) -> None:
    if args.confirm != "CREATE":
        raise UserError("create-tree requires --confirm CREATE after user approval")
    tree = validate_tree(read_stdin_json())
    client = client_for(args, target)
    existing = client.search_plan(tree["plan_id"])
    if existing:
        compact({"status": "duplicate", "plan_id": tree["plan_id"], "issues": [{"iid": item.get("iid"), "title": item.get("title"), "web_url": item.get("web_url")} for item in existing]})
        return
    existing_labels = client.labels()
    created: list[dict[str, Any]] = []
    skipped_labels: dict[str, list[str]] = {}
    try:
        parent_labels, parent_skipped = filter_labels(tree["parent"], existing_labels)
        if parent_skipped:
            skipped_labels["parent"] = parent_skipped
        parent_marker = f"codex-plan:{tree['plan_id']}:parent"
        parent_description = render_description(tree["parent"], parent_marker, children=[])
        parent = client.create_issue(tree["parent"]["title"], parent_description, parent_labels)
        parent_summary = {"kind": "parent", "iid": parent["iid"], "title": parent["title"], "web_url": parent["web_url"]}
        created.append(parent_summary)
        child_summaries: list[dict[str, Any]] = []
        for child in tree["children"]:
            labels, skipped = filter_labels(child, existing_labels)
            if skipped:
                skipped_labels[child["key"]] = skipped
            marker = f"codex-plan:{tree['plan_id']}:{child['key']}"
            description = render_description(child, marker, parent_iid=int(parent["iid"]))
            issue = client.create_issue(child["title"], description, labels)
            summary = {"kind": "child", "key": child["key"], "iid": issue["iid"], "title": issue["title"], "web_url": issue["web_url"]}
            created.append(summary)
            child_summaries.append(summary)
        iid_by_key = {child["key"]: int(child["iid"]) for child in child_summaries}
        for child, summary in zip(tree["children"], child_summaries, strict=True):
            marker = f"codex-plan:{tree['plan_id']}:{child['key']}"
            final_child_description = render_description(
                child,
                marker,
                parent_iid=int(parent["iid"]),
                dependency_iids=iid_by_key,
            )
            client.update_issue(int(summary["iid"]), {"description": final_child_description})
        final_parent_description = render_description(tree["parent"], parent_marker, children=child_summaries)
        client.update_issue(int(parent["iid"]), {"description": final_parent_description})
        compact({"status": "created", "plan_id": tree["plan_id"], "issues": created, "skipped_labels": skipped_labels})
    except UserError as exc:
        compact({"status": "partial_failure", "error": str(exc), "created": created})
        raise SystemExit(2)


def command_comment(args: argparse.Namespace, target: Target) -> None:
    if args.confirm != "UPDATE":
        raise UserError("comment requires --confirm UPDATE")
    note = client_for(args, target).add_note(args.issue, render_comment(read_stdin_json()))
    compact({"status": "commented", "issue_iid": args.issue, "note_id": note.get("id")})


def command_close(args: argparse.Namespace, target: Target) -> None:
    if args.confirm != "CLOSE":
        raise UserError("close requires --confirm CLOSE after user approval")
    client = client_for(args, target)
    issue = client.update_issue(args.issue, {"state_event": "close"})
    parent_updated = None
    description = str(issue.get("description") or "")
    parent_match = re.search(r"^Parent: #(\d+)\s*$", description, flags=re.MULTILINE)
    if parent_match:
        parent_iid = int(parent_match.group(1))
        parent = client.get_issue(parent_iid)
        parent_description = str(parent.get("description") or "")
        pattern = rf"^- \[ \] #{args.issue}(?=\s)"
        updated_description, count = re.subn(pattern, f"- [x] #{args.issue}", parent_description, count=1, flags=re.MULTILINE)
        if count:
            client.update_issue(parent_iid, {"description": updated_description})
            parent_updated = parent_iid
    compact({"status": issue.get("state"), "issue_iid": issue.get("iid"), "web_url": issue.get("web_url"), "parent_updated": parent_updated})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", help="Git remote name when more than one project remote exists")
    parser.add_argument("--api-base", help="Override GitLab base URL or API v4 base")
    parser.add_argument("--ca-file", help="Approved PEM CA bundle for internal TLS")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("target")
    subparsers.add_parser("credential-set")
    subparsers.add_parser("check")
    subparsers.add_parser("labels")
    subparsers.add_parser("dry-run")
    create = subparsers.add_parser("create-tree")
    create.add_argument("--confirm", required=True)
    comment = subparsers.add_parser("comment")
    comment.add_argument("--issue", required=True, type=int)
    comment.add_argument("--confirm", required=True)
    close = subparsers.add_parser("close")
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
