"""Fail if a real secret (password, API key, private key) is committed to the repository.

Run:  python scripts/secret_scan.py          (exit code 1 = something found)
Checks files tracked by Git (or every file when Git is not available). Example files may
contain empty values or obvious placeholders like CHANGE_ME.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', 'node_modules', '.next', '.venv', 'venv', '__pycache__', 'private_uploads', 'test-results',
             'playwright-report'}
SKIP_SUFFIX = {'.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.docx', '.woff', '.woff2', '.lock', '.dump', '.gz'}
PLACEHOLDER = re.compile(r'^(|change[_-]?me.*|example.*|your[_-].*|xxx+|\*+|<.*>|\$[{(].*|ci_.*|local.*|replace.*|dummy.*|test.*|'
                         r'placeholder.*|none|null|false|no|yes|outbox|smtp\.gmail\.com|5\d\d|\d{1,5})$', re.I)
RULES = [
    ('private key', re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
    ('AWS access key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('Google API key', re.compile(r'\bAIza[0-9A-Za-z_\-]{35}\b')),
    ('GitHub token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{36,}\b')),
    ('OpenAI/Anthropic style key', re.compile(r'\bsk-(?:ant-)?[A-Za-z0-9_\-]{24,}\b')),
    ('Slack token', re.compile(r'\bxox[baprs]-[A-Za-z0-9-]{10,}\b')),
]
ASSIGN = re.compile(r'^\s*(?:export\s+)?([A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE_KEY)[A-Z0-9_]*)\s*[=:]\s*["\']?([^"\'\s#]*)')


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
        return [ROOT / p for p in out.decode().split('\0') if p]
    except Exception:  # noqa: BLE001 - no git: walk the folder
        found = []
        for base, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            found += [Path(base) / f for f in files]
        return found


def scan(paths: list[Path]) -> list[str]:
    problems = []
    for path in paths:
        if path.suffix.lower() in SKIP_SUFFIX or any(part in SKIP_DIRS for part in path.parts) or not path.is_file():
            continue
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        if path.name.endswith('.local') or path.name in {'.env', '.phase3-fresh.env'}:
            problems.append(f'{rel}: private settings file is committed (it must stay only on your PC)')
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        is_code = path.suffix in {'.py', '.ts', '.tsx', '.js', '.mjs'}
        for number, line in enumerate(text.splitlines(), 1):
            for name, rule in RULES:
                if rule.search(line):
                    problems.append(f'{rel}:{number}: looks like a {name}')
            match = ASSIGN.match(line)
            if match and not is_code and not PLACEHOLDER.match(match.group(2)):
                problems.append(f'{rel}:{number}: {match.group(1)} has a real-looking value')
    return problems


def main() -> int:
    problems = scan(tracked_files())
    for problem in problems:
        print('SECRET?', problem)
    print('Secret scan:', 'FAILED' if problems else 'clean')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
