#!/usr/bin/env python3
"""Prepare a bounded connector publication plan; never call GitHub or write repo files.

The byte ceiling is a local review/transport budget, NOT a claimed GitHub API limit.
Existing large-file blob transport is retained. All mutations retain normal approvals.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

DEFAULT_INLINE_BUDGET = 1024 * 1024


def prepare(root, paths, expected_head, base_tree, inline_budget=DEFAULT_INLINE_BUDGET):
    if not all(re.fullmatch(r'[0-9a-f]{40}', value) for value in (expected_head, base_tree)):
        raise ValueError('Expected head and base tree must be verified full Git SHAs')
    if inline_budget < 1024:
        raise ValueError('Inline budget must be at least 1024 bytes')
    root = Path(root).resolve()
    entries, blobs, manifest = [], [], []
    seen = set()
    for name in paths:
        path = PurePosixPath(name)
        if (name in seen or path.is_absolute() or '..' in path.parts or
                str(path) != name or '.git' in path.parts):
            raise ValueError(f'Unsafe or duplicate path: {name}')
        seen.add(name)
        source = root.joinpath(*path.parts)
        if source.is_symlink() or not source.resolve().is_relative_to(root) or not source.is_file():
            raise ValueError(f'Not a regular in-repository file: {name}')
        raw = source.read_bytes()
        try:
            content = raw.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            content = None
        if content is not None and '\x00' in content:
            content = None
        mode = '100755' if source.stat().st_mode & 0o111 else '100644'
        item = {'path': name, 'mode': mode, 'type': 'blob', 'content': content}
        # Count the complete encoded tree entry array, not characters/source bytes.
        payload_size = len(json.dumps(entries + [item], ensure_ascii=False).encode('utf-8'))
        git_sha = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        manifest.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'gitBlobSha': git_sha})
        if content is not None and payload_size <= inline_budget:
            entries.append(item)
        else:
            blobs.append({'path': name, 'mode': mode, 'type': 'blob', 'expectedBlobSha': git_sha,
                          'bytes': len(raw), 'reason': 'non-UTF-8 or binary: preserve exact bytes via existing blob transport' if content is None else 'outside local inline request budget'})
    if not manifest:
        raise ValueError('Explicit nonempty file list required')
    return {'repository': 'saewoo16/global-tech-terminal', 'expectedHead': expected_head,
            'baseTree': base_tree, 'inlineBudgetBytes': inline_budget,
            'inlineEntries': entries, 'separateBlobFiles': blobs, 'manifest': manifest,
            'notice': 'Preparation only. Retain required approvals, latest-head validation, CAS, tests and Pages verification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--expected-head', required=True)
    parser.add_argument('--base-tree', required=True)
    parser.add_argument('--inline-budget-bytes', type=int, default=DEFAULT_INLINE_BUDGET)
    parser.add_argument('paths', nargs='+')
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.paths, args.expected_head, args.base_tree,
                             args.inline_budget_bytes), ensure_ascii=False))


if __name__ == '__main__':
    main()
