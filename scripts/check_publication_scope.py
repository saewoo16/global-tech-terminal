#!/usr/bin/env python3
"""Reject out-of-scope working-tree changes before a bounded publication.

This is a write-boundary check, not a collector lock or source-freshness check.
The existing latest-main integration, complete validation and non-force push
remain mandatory. Read-only: this script never stages, deletes or rewrites data.
"""
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCOPES = {
    'company': frozenset({
        'data/market.json', 'data/coverage.json', 'data/coverage.csv',
        'data/regional_earnings_coverage.csv',
    }),
}


def validate_paths(paths, scope):
    if scope not in SCOPES:
        raise ValueError('Unknown publication scope: ' + scope)
    unexpected = sorted(set(paths) - SCOPES[scope])
    if unexpected:
        raise ValueError('Publication stopped: changes outside ' + scope +
                         ' scope: ' + ', '.join(unexpected))
    return sorted(set(paths))


def changed_paths(root, base):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args])
    # Resolve an actual commit before using it as the diff base. Both sides of
    # renames are checked because moving data out of its owner is also a write.
    sha = git('rev-parse', '--verify', base + '^{commit}').decode().strip()
    tracked = git('diff', '--name-only', '--no-renames', '-z', sha, '--')
    untracked = git('ls-files', '--others', '--exclude-standard', '-z')
    return {p.decode('utf-8') for p in (tracked + untracked).split(b'\0') if p}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', choices=sorted(SCOPES), required=True)
    parser.add_argument('--base', required=True)
    args = parser.parse_args()
    paths = validate_paths(changed_paths(ROOT, args.base), args.scope)
    print(f'Publication scope {args.scope}: {len(paths)} permitted changed files.')


if __name__ == '__main__':
    main()
