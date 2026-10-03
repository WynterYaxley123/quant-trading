# Production constituent gaps — provenance-qualified final v3

This v3 preserves the measured v2 matrix and corrects its evidence language.
The fixed window has 57,996 L2 industry-days: 40,800 strict valid, 17,196
invalid. The sealed matrix SHA-256 is
`6fc016bd0965b31579dd20527c1118eb60153c4539c04d9b20f26beb0b975e91`.
The v2 reason counts remain the measured counts: membership-only without
market data 13,836, insufficient eligible constituents 2,130, unresolved
instrument 716, missing current bar 378, missing previous bar 136.

The stored instrument dates mark 14,281 invalid industry-days with at least
one member whose stored delist date precedes the session. This is a useful
**diagnostic association**, not proof that all those gaps are historically
expected: field-level listing/delisting provenance and publication timing
were not independently established. In particular, do not subtract 14,281
from the formal denominator or reclassify them as fully explained data loss.
The separate 524 stored-pre-list member-sessions carry the same caveat.
All members remain denominator-visible; 358 CDR `689009.SH` sessions are
numerator-ineligible. Nothing was filled, dropped or back-stamped.

The official targeted `601318.SH` repair moved curated window bars from
1,943,979 to 1,944,307 and strict valid industry-days from 40,799 to 40,800.
The remaining gap is **measured and unresolved by cause**; its legitimacy is
not established merely by a potentially unverified instrument date.
