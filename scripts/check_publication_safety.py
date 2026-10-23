#!/usr/bin/env python3
"""Fail closed unless Git blobs match a locally approved public-file manifest.

This checks the index/commits, rather than trusting working files or .gitignore.
It does not remove material already hosted on GitHub or make claims about caches.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

MANIFEST = '.publication-allowlist.json'
SEALED = 'publication-allowlist.approved.json'
PRIVATE_PREFIXES = ('analysis/', 'input/', 'output/', 'data/raw/', 'data/processed/',
                    'outputs/private/', 'docs/private/', 'reports/private/',
                    'docs/analysis-audits/', 'app/decision-review/',
                    'scripts/commercial-review/')
PRIVATE_NAMES = ('docs/RESUME_EVIDENCE_2026-10.md', 'docs/REPRODUCE_INTEGRATED_ANALYSIS.md',
                 'reports/commercial_review.xlsx', 'scripts/commercial-review/commercial_inputs.json',
                 'scripts/commercial-review/commercial_workbook_qa.json')

def git(*args, text=False):
    return subprocess.check_output(['git', *args], text=text)

def denied(path):
    return (path.startswith(PRIVATE_PREFIXES) or path in PRIVATE_NAMES
            or path.endswith(('.icloud', '.sqlite', '.sqlite3', '.db', '.pbix'))
            or ('/.env' in '/' + path and not path.endswith('.env.example'))
            or path.lower().endswith(('.xlsx', '.xls', '.xlsm', '.xlsb')) and not path.startswith(('data/sample/', 'outputs/sample/')))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-hooks', action='store_true', help='Install local hooks from an already reviewed manifest')
    parser.add_argument('--pre-push', action='store_true', help='Read Git pre-push ref updates from stdin')
    parser.add_argument('--working-tree', action='store_true', help='Check reviewed working-file bytes; does not stage anything')
    args = parser.parse_args()
    root = Path(git('rev-parse', '--show-toplevel', text=True).strip())
    os.chdir(root)
    manifest_bytes = (root / MANIFEST).read_bytes()
    approved = json.loads(manifest_bytes)
    allow = approved['files']
    gitdir = Path(git('rev-parse', '--absolute-git-dir', text=True).strip())
    seal = gitdir / SEALED
    if args.install_hooks:
        for hook in ['pre-commit', 'pre-push']:
            legacy = gitdir / 'hooks' / hook
            if legacy.exists():
                raise SystemExit('Existing custom hook must be integrated explicitly: ' + str(legacy))
        seal.write_bytes(manifest_bytes)
        subprocess.check_call(['git', 'config', '--local', 'core.hooksPath', '.githooks'])
        print('Installed reviewed-manifest commit/push checks. No files were staged or committed.')
        return
    if not seal.exists() or seal.read_bytes() != manifest_bytes:
        raise SystemExit('BLOCKED: public-file manifest differs from the locally approved version. Review changes before installing a new approval.')
    problems = []
    def check(path, mode, content, historical_tree=False):
        if denied(path):
            problems.append(path + ': private path or file type')
        elif mode not in ('100644', '100755'):
            problems.append(path + ': links/submodules require separate review')
        elif path == MANIFEST:
            if content != manifest_bytes:
                problems.append(path + ': staged/committed approval manifest differs from reviewed bytes')
        else:
            digest = hashlib.sha256(content).hexdigest()
            permitted = allow.get(path, [])
            if isinstance(permitted, str):
                permitted = [permitted]
            if historical_tree:
                reviewed_history = approved.get('historical_versions', {}).get(path, [])
                if isinstance(reviewed_history, str):
                    reviewed_history = [reviewed_history]
                permitted = permitted + reviewed_history
            if digest not in permitted:
                problems.append(path + ': file/version has not been approved for public release')
    checked = 0
    if args.working_tree:
        for path in sorted(allow):
            p = root / path
            if not p.is_file():
                problems.append(path + ': approved file missing from working tree')
            else:
                check(path, '100755' if p.stat().st_mode & 0o111 else '100644', p.read_bytes())
            checked += 1
    elif args.pre_push:
        commits = set()
        for line in sys.stdin:
            local_ref, local_sha, remote_ref, remote_sha = line.strip().split()
            if set(local_sha) == {'0'}:
                continue
            revision = local_sha if set(remote_sha) == {'0'} else remote_sha + '..' + local_sha
            commits.update(git('rev-list', revision, text=True).splitlines())
        for commit in sorted(commits):
            tree = git('rev-parse', commit + '^{tree}', text=True).strip()
            historical_tree = tree in approved.get('reviewed_history_trees', [])
            for entry in git('ls-tree', '-r', '-z', commit).split(b'\0'):
                if not entry:
                    continue
                metadata, raw_path = entry.split(b'\t', 1)
                mode, kind, obj = metadata.decode().split()
                path = raw_path.decode('utf-8', 'surrogateescape')
                check(path, mode, git('cat-file', 'blob', obj) if kind == 'blob' else b'', historical_tree=historical_tree)
                checked += 1
    else:
        for entry in git('ls-files', '--stage', '-z').split(b'\0'):
            if not entry:
                continue
            metadata, raw_path = entry.split(b'\t', 1)
            mode, obj, stage = metadata.decode().split()
            path = raw_path.decode('utf-8', 'surrogateescape')
            if stage != '0':
                problems.append(path + ': unresolved index stage')
                continue
            check(path, mode, git('cat-file', 'blob', obj) if mode != '160000' else b'')
            checked += 1
    if problems:
        print('BLOCKED: publication review required. No sensitive file content is printed.', file=sys.stderr)
        for problem in sorted(set(problems))[:40]:
            print(' - ' + problem, file=sys.stderr)
        if len(set(problems)) > 40:
            print('Additional unapproved paths: ' + str(len(set(problems))-40), file=sys.stderr)
        raise SystemExit(1)
    print('PASS: ' + str(checked) + ' Git/working-file versions match the approved public manifest.')

if __name__ == '__main__':
    main()
