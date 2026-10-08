# Numeric access isolation

Historical SWL1 V1/V2 isolation remains NOT_CERTIFIED; certified historically unseen
sessions=0. Their full-panel materialization cannot be retroactively undone. This
new architecture supplies only prospective infrastructure, without new training.

[numeric.py](../../research/evidence/numeric.py) checks admitted source/contract,
registered protocol/phase, distinct feature/return limits, full universe, maturity
permission and capability expiry BEFORE opening numerical source members. Trusted
authority transformation may decode C, Fortran and compressed NPZ/ZIP input; it
writes new physically bounded float64 NPY members. The worker never holds the
original ZIP/mmap/chunked/columnar descriptor. Unsupported input formats require an
explicit authority conversion and are denied by this adapter; no generic worker
raw-format reader exists. ZIP member count and total uncompressed size are bounded.

The manifest binds view/family/generation, protocol/source/data-contract hashes,
phase, authorized start/end, feature/return cutoffs, horizons, universe, creation,
content hash and authority receipt. Separate file sizes/hashes authenticate every
member before either numeric decode. Permitted content hash excludes changing
mother provenance; mother_snapshot_hash honestly records future-tail changes.
NaN/large positive/large negative/reordering/extreme features/inducing values in
forbidden rows do not alter permitted bytes or the worker's deterministic derived
hash. No model prediction or performance evaluation is run.

Closed leaf names reject absolute/relative traversal, alternate drives, UNC,
ZIP references and alternate streams. Realpath, symlink/reparse, hardlink,
noninherited descriptors and descriptor identity checks protect reads. Read-only
view mounts stop worker replacement; adversarial descriptor replacement is tested.
Python checks alone do not prevent arbitrary code from opening an accessible file.

The [Docker acceptance launcher](../../scripts/engineering/prospective-isolation.mjs)
builds a minimal worker image from the pinned independent developer image.
It runs nonroot, read-only rootfs, network none, dropped capabilities,
no-new-privileges, bounded memory/processes, with exactly /view and /policy read-only
mounts. It inspects actual Docker configuration before launch. The worker attempts
direct reads outside the firewall, network access and inherited-descriptor discovery.
Three real separate workers with positive/negative/NaN future tails produce the
same content and derived hashes and deny mother reads. No Docker socket or code
host mount enters the worker. Secrets remain authority-side.

LOGICAL_BOUNDARY=PASS_SYNTHETIC; PHYSICAL_VIEW_BOUNDARY=PASS_SYNTHETIC;
PROCESS_ISOLATION=PASS_LINUX_DOCKER_SYNTHETIC. Actual Windows junction rejection is
covered by the Node launcher tests locally and hosted Windows; Windows native
quantitative process isolation is NOT_ESTABLISHED. Docker daemon/host admin and
a compromised trusted authority are outside this threat boundary. Production
readiness remains blocked by rights/PIT/signature prerequisites.

[Architecture](prospective-evidence-architecture.md) ·
[Operations](prospective-evidence-operations.md)
