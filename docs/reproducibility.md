# Reproducibility and provenance

`scripts/engineering/inventory.py` is the canonical measurement tool. It reads a Git
path manifest and ASTs without importing strategy code. Complete signatures require
all parameters except self/cls and the return. LOC includes blank/comment lines.
Diagnostic counts and files containing diagnostics are reported separately.

```sh
git ls-files > /tmp/tracked.txt
python -m mypy --no-error-summary --no-pretty --no-color-output > /tmp/mypy.txt
python scripts/engineering/inventory.py --manifest /tmp/tracked.txt --mypy-output /tmp/mypy.txt --output /tmp/health.json
```

Historical candidate/config/report bytes stay immutable. The old autonomous_code_integrity_v1
certificate remains historical truth. A new active implementation manifest records
its hash/source hashes, transition reason, changed files, candidate pin, base commit,
regression evidence and current source hashes. It is the current source authority.
Never overwrite an old certificate to make current code appear historically certified.

The historical V2 prerequisite transition is `reports/engineering/etf-quant-v2-integrity.json`.
It appends the byte-pinned release-hotfix manifest, preserves the V1 candidate hash
and records synthetic/maintainer regression evidence. Its research status explicitly
records the former strict-PIT blocker; source integrity does not certify historical data.
The current transition is `reports/engineering/etf-quant-v2-build-integrity.json`,
which appends that immutable certificate. It records actual evidence-tier experiments,
one failed Validation, the authorized Development revision and V1 regression.
Candidate/protocol/data/code hashes resolve independently of Git delivery metadata.
Full private research artifacts and original freeze records remain externally hashed.

`config/engineering/documentation-map.json` classifies every Markdown file and maps
archived old paths to new locations with original hashes. Resolve historical metadata
through it without altering immutable artifacts. Archived instructions are historical.
The audit verifies active source and archive byte integrity.

Security scans omit sealed performance content and publish finding identifiers/counts.
Shadow checks use real namespace path/size/hash metadata before/after, without creating
business records. See the [remediation report](engineering/repository-health.md).
