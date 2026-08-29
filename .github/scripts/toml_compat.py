"""Load TOML mappings on Python 3.10+ without requiring tomli."""

from __future__ import annotations

import re

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None


class TomlError(ValueError):
    """Raised when a playbook TOML file cannot be parsed."""


def load_toml(text: str) -> dict[str, object]:
    if tomllib is not None:
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise TomlError(str(exc)) from exc
    return parse_basic_toml(text)


def parse_basic_toml(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    index = 0
    length = len(text)
    key_pattern = re.compile(r"([A-Za-z_][\w-]*)\s*=\s*")
    while index < length:
        while index < length and text[index] in " \t\r\n":
            index += 1
        if index >= length:
            break
        if text[index] == "#":
            newline = text.find("\n", index)
            index = length if newline < 0 else newline + 1
            continue
        match = key_pattern.match(text, index)
        if not match:
            raise TomlError(f"Unsupported TOML syntax at index {index}")
        key = match.group(1)
        index = match.end()
        if text.startswith('"""', index):
            end = text.find('"""', index + 3)
            if end < 0:
                raise TomlError(f"Unclosed triple-quoted string for {key}")
            data[key] = text[index + 3 : end]
            index = end + 3
            continue
        if index < length and text[index] == '"':
            end = index + 1
            while end < length and not (text[end] == '"' and text[end - 1] != "\\"):
                end += 1
            if end >= length:
                raise TomlError(f"Unclosed string for {key}")
            data[key] = text[index + 1 : end]
            index = end + 1
            continue
        raise TomlError(f"Unsupported TOML value for {key}")
    return data
