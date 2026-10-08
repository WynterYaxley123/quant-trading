# Source admission contract

Admission is performance-blind. The closed
[source schema](../../config/research/data-source-admission-schema.json) and
[implementation](../../research/evidence/source_admission.py) bind source generation,
contract, taxonomy, membership, kind, tier and revision hashes. Taxonomy, official
price series and reconstructed industry returns are distinct kinds.

Lifecycle vocabulary: SOURCE_UNREVIEWED, SOURCE_METADATA_VERIFIED,
SOURCE_RIGHTS_VERIFIED, SOURCE_PIT_VERIFIED, SOURCE_ADMITTED, SOURCE_REJECTED,
SOURCE_BLOCKED. Missing metadata stays unreviewed; missing rights blocks admission;
rights without PIT stays rights-verified and cannot serve a numeric view. Admission
requires all protocol factual conditions, not a historical performance threshold.

Every synthetic proof has an authority HMAC, issuer/purpose/scope and exact source
binding. A boolean verified, wrong issuer, different generation or performance
claim is rejected. Production authority construction fails with
SIGNATURE_AUTHORITY_NOT_ESTABLISHED. Ephemeral HMACs test authentication, not legal
permission or production institutional identity. Never persist the authority secret
in Git, worker policy, view manifest or API. Production identity/admission remains
a separately reviewed prerequisite, not an operator-editable verified flag.

Canonical tiers retain existing meanings: A strict contemporary availability;
B verified effective-dated reconstruction; C reconstruction with provenance;
D excluded/unsupported. Stronger future proof creates a new generation; it does
not upgrade old V1/V2 evidence. Effective time alone cannot satisfy Tier A.

Observation receipts separately bind published/observed/finalized times, source,
taxonomy, membership, contract, immutable snapshot, rights, cutoff and revision.
Incomplete suspension/delisting/full-constituent coverage is FACT_NOT_FINALIZED.
No file mtime or ingestion watermark becomes a publication-time witness.

Revision categories are membership, adjusted_close, delisting, calendar, symbol,
coverage. FACT_SNAPSHOT_IMMUTABLE → FACT_REVISION_DETECTED →
FACT_REVISION_QUARANTINED → SOURCE_TRANSITION_REQUIRED. Preserve every original;
new source generations require new factual admission. No silent substitution.

[Feasibility](../research/swl1-data-first-feasibility.md) ·
[Architecture](prospective-evidence-architecture.md)
