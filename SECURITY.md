# Security reporting

This simulation/Shadow repository has read-only local APIs and no broker/real-order
integration. Never include credentials, market datasets, runtime payloads or sealed
research performance in a public report.

Use the repository's private security reporting channel if available. Otherwise open
a minimal issue requesting private contact with the owner, without sensitive details
or exploit payloads. Provide affected commit/component and a synthetic reproduction
once private contact is established.

Native source/history scanning is defense-in-depth, not external certification.
Jupyter requires external authentication. APIs bind locally and validate exact origins,
paths, hashes, schemas and bounded artifacts. MIT covers source code, not market-data rights.
