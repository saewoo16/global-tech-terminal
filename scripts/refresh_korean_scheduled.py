"""Narrow scheduled candidates; publication occurs only after full validation."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import kofia_official
from korean_session_gate import check
from update_korean_market import atomic_write

ROOT = Path(__file__).resolve().parents[1]

def substantive(value):
    if isinstance(value, dict):
        return {k:substantive(v) for k,v in value.items() if k not in {'updatedAt','metadataRetrievedAt','marketCapObservedAt'}}
    if isinstance(value, list): return [substantive(v) for v in value]
    return value

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=('etf','liquidity'), required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if not check(now):
        print('No confirmed completed Korean session today; unchanged.')
        return
    if args.kind == 'liquidity':
        target = ROOT/'data/korea-market.json'
        previous = json.loads(target.read_text())
        candidate = kofia_official.apply(previous,kofia_official.collect(now.isoformat()))
        if candidate != previous: atomic_write(candidate,target)
    else:
        target = ROOT/'data/korean_etf_charts.json'
        previous = json.loads(target.read_text())
        # Isolated same-directory candidate preserves existing-data fallback.
        with tempfile.TemporaryDirectory(dir=target.parent) as folder:
            candidate = Path(folder)/target.name
            candidate.write_text(json.dumps(previous,ensure_ascii=False))
            subprocess.run(['python',str(ROOT/'scripts/update_korean_etf_charts.py'),'--output',str(candidate)],check=True)
            new = json.loads(candidate.read_text())
            day = now.astimezone(__import__('korean_session_gate').KST).date().isoformat()
            if new.get('asOf') != day: raise ValueError('ETF candidate has no current session')
            if len(new.get('funds',[])) != len(previous['funds']): raise ValueError('ETF universe regression')
            # Timestamp-only recollection is not a data change.
            if substantive(previous) != substantive(new): os.replace(candidate,target)

if __name__ == '__main__': main()
