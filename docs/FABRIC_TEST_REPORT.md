# Fabric executed test report

Executed 2026-10-06 on this host against the real Docker network, PostgreSQL and MinIO.

- Fabric 2.5.16; two organizations and peers, one Raft orderer; `nyayachannel`.
- Chaincode `nyayavault`, version 1.0, sequence 1; both organizations approved.
- Live gateway Health query returned HTTP 200 and connected=true.
- Eight existing custody events replayed and committed without replacing evidence.
- 24 HTTP integration assertions passed: authentication, role/case controls, encrypted upload/download, original/stored verification, custody transfer, modified candidate detection, immutable trusted hash, audit/dashboard consistency, logout and committed Fabric IDs.
- Four direct gateway/peer checks passed: all six new events match application hashes/IDs; duplicate replay returns original ID without changing evidence history; changed original fingerprint is rejected; unauthenticated gateway access is rejected.
- Three chaincode unit tests passed. Frontend production build and TypeScript validation passed.
- Browser login and System Status visibly show Hyperledger Fabric connected.

New synthetic evidence: `EVD-DOCKER-17febfd1` (`11ccbeae-d8f8-4033-bfbe-0886fa6b13a2`). Registration transaction: `8ae9e12e3cdf6520b5bc1b26d68f91fe32012ce9ec78d56d0a56ca323de55fac`.

Machine-readable reports: `fabric-test-results.json` and `fabric-peer-results.json`. Peer history is returned newest first; checks match by immutable event ID rather than relying on list order. The invalid proof test intentionally produces a rejected endorsement in gateway logs.

These checks validate a local academic deployment. Multi-host resilience, organization onboarding, production key management and automatic outbox recovery were not tested or implemented.
