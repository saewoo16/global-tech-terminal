"""Bounded public verification. Never claim a queued/failed deployment succeeded."""
import argparse
import hashlib
import json
import time
from urllib.request import Request, urlopen


def verify(site, manifest, attempts=12, interval=10):
    expected = json.load(open(manifest, encoding='utf-8'))
    last = None
    for attempt in range(attempts):
        try:
            suffix = '?deployment=' + expected['commit'] + '&attempt=' + str(attempt)
            def fetch(path):
                with urlopen(Request(site.rstrip('/') + '/' + path + suffix, headers={'Cache-Control': 'no-cache'}), timeout=30) as response:
                    return response.read()
            actual = json.loads(fetch('deployment-version.json'))
            if actual != expected:
                raise ValueError('Public deployment manifest does not match the validated snapshot')
            if hashlib.sha256(fetch('index.html')).hexdigest() != expected['files']['index.html']:
                raise ValueError('Public index.html does not match the validated snapshot')
            print('Verified public deployment ' + expected['commit'])
            return
        except Exception as error:
            last = error
            if attempt + 1 < attempts:
                time.sleep(interval)
    raise RuntimeError(f'Public verification incomplete: {last}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--site', required=True)
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()
    verify(args.site, args.manifest)
