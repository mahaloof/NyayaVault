# Gemini case assistant

The assistant answers questions and summarizes explicitly selected fictional evidence, with exact source quotations and links back to the evidence record. It is an optional assistance layer. It does not determine guilt, authenticate allegations, modify evidence, or generate blockchain transactions.

## Encryption and processing

1. An authenticated administrator, investigator or forensic officer selects an authorized case and up to four evidence files. Viewer accounts cannot use the assistant because they cannot download original content.
2. The backend checks case membership and every evidence-to-case association before reading storage.
3. It decrypts selected originals, checks AES-GCM authentication and compares SHA-256 with the immutable registered fingerprint. Any failure blocks the request.
4. Text extraction happens locally. No persistent plaintext files, searchable plaintext index or answer history are saved. PDF input uses process pipes. OCR page images use a private temporary directory in Docker’s `/dev/shm` shared memory, cleaned on success or failure; no disk-backed fallback is permitted. Process memory and OS swap are outside this application's secure-erasure guarantees.
5. Only the question and bounded excerpts with temporary source IDs are sent over HTTPS to Google's Gemini API. Encryption keys, credentials, original files, database records and custody history are not sent.
6. The backend divides excerpts into exact passages of at most 800 characters. Gemini selects request-local passage IDs from a constrained schema; the backend rejects unknown IDs and inserts the original passage text as each quotation. Source IDs and verbatim quotes are then validated before an answer is accepted. A valid quote does not prove the model's interpretation is correct: reviewers must check every claim.
7. The append-only audit records request, attempted disclosure, completion/failure, selected evidence IDs and original hashes, without questions, excerpts or answers. These are application audit entries, not Fabric proof events.

## Supported evidence and limits

- UTF-8 `.txt`, PDFs (typed or scanned), PNG and JPEG document photos, up to 10 MiB each; at most four files per request. Images are limited to 16 megapixels.
- PDFs: first 20 pages only, with original page numbers in citations. Pages without usable selectable text use local Tesseract OCR. Enable “Scan every PDF page” for pages mixing typed text with scanned notes. Page omissions and uncertain OCR are reported.
- Printed English OCR is supported. Handwriting and other languages are not reliable in this version. Low-confidence words trigger a warning; high confidence does not guarantee correctness. DOCX, audio and video are unsupported.
- At most 6,000 characters per file, shared across readable pages. Long files use the first three 1,500-character chunks for summaries, or three keyword-ranked chunks for questions. The full selected excerpts are available below the answer. This is bounded excerpt retrieval, not semantic/vector RAG or an exhaustive case search.
- Two simultaneous requests per backend process and five requests per user per minute. These are demo safeguards, not distributed rate limiting or a billing cap.
- Provider requests time out after 60 seconds; oversized, malformed, blocked, unfinished or unverifiably cited answers are rejected. There are no tools, web searches, automatic retries or cloud file uploads.
- The API is disabled until configured. A missing key or quota failure does not prevent uploads, integrity checks or custody transfers.

## Google API privacy and cost

Use only fictional training records with this demo integration. Each request requires confirmation that the selected records are fictional and may be sent to Google. This is an attestation, not automated detection of sensitive data.

Google's unpaid-service terms permit use of submitted content and responses for product improvement. Paid services have different data-use terms, but should still be assessed before any real evidence is processed. Free quotas, model availability and pricing depend on the Google project and can change. An API key does not guarantee free use; check the project's billing and quota settings.

- [Gemini API terms](https://ai.google.dev/gemini-api/terms)
- [Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [API keys](https://aistudio.google.com/apikey)
- [GenerateContent API](https://ai.google.dev/api/generate-content)

## Configure without exposing the key

Create a Google AI Studio key for your own project. Enter it only in the local, Git-ignored environment file, never in chat, source code or frontend variables.

For the existing Mac deployment, edit the project root `.env`. For an existing portable Windows deployment, edit `.env.portable`. Preserve all existing encryption keys, database passwords and settings. Add or update:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=YOUR_LOCAL_KEY
AI_MODEL=gemini-3.5-flash-lite
```

Choose a model enabled for your Google project; the model ID is configurable. The default is listed with a free tier on Google's current pricing page; project eligibility and quotas still apply.

For the existing Mac deployment, rebuild only application services:

```bash
bash scripts/docker.sh -f docker-compose.yml -f docker-compose.fabric.yml -f docker-compose.network.yml up -d --build backend frontend
```

For an already initialized portable deployment, from the project root:

```powershell
docker compose --project-name nyayavault-portable --env-file .env.portable -f docker-compose.portable.yml up -d --build backend frontend
```

Fresh portable installations: follow WINDOWS_START_HERE.md first, then configure the generated `.env.portable` and rebuild application services as above. No Fabric reset or data migration is needed. Do not delete Docker volumes or regenerate existing keys.

The backend image includes Poppler, Pillow and Tesseract with English data. Run PDF/image reading in Docker (including Docker Desktop on Windows); the reader requires Linux shared memory. Each reader process is limited to 20 seconds and each document to a 90-second processing budget. The API key stays on the backend; no UI reveals it. Disable AI by setting `AI_PROVIDER=disabled` and recreating the backend.

Open **Case assistant**, select a case and files, choose a summary or question, and confirm external processing. Review the answer and its quotes. Questions such as “What amount is recorded?” can be tested against the fictional invoice records.

## Validation and remaining checks

Automated tests use an isolated database, random test encryption keys, fictional files and mocked Gemini responses. They cover permissions, case isolation, explicit disclosure confirmation, original/custody preservation, corrupted ciphertext, invalid citations, missing configuration, extraction behavior and provider errors. Mocked responses do not prove live Gemini quality or connectivity.

Live Google requests, Docker application rebuilds, real PDF extraction and a browser question with citations passed after the local API key was configured. See [live results](ai-live-results.json). No AI output is represented as a real Fabric commit.

## Executed validation — 15 October 2026

- Backend: 34 tests passed, including 12 assistant tests and 22 existing workflow tests.
- Frontend: TypeScript check and optimized Next.js production build passed.
- Unit tests mock Gemini. Separate live checks sent only synthetic text and the verified fictional NV-0142-EMAIL demo record.
- Docker backend/frontend rebuilds passed. Real Poppler extraction passed. Live summary and question API calls passed, followed by a cited answer in the browser.
- Preservation digests match for all 5 users, 9 cases, 38 memberships, 17 evidence records/ciphertexts, 70 custody events, 70 transaction records and the encryption key. AI audit entries were appended.
- No new Fabric evidence transactions were created by AI; the existing network remains connected.
- No schema migration or changes to existing evidence, encryption keys, identities or Fabric ledgers were performed.

## Response-format fix — 16 October 2026

Gemini sometimes added an unsupported `source` field to citations when only JSON mode was requested. The backend now sends the same JSON Schema used for local validation, including allowed source IDs, required fields and claim/citation limits. Strict validation and exact quotation checks remain enabled.

- All 14 assistant tests passed, including regression coverage for the outgoing schema and rejection of unexpected citation fields.
- The rebuilt backend successfully summarized all three NV-2026-0308 warehouse files through the running application API: six claims, with every quotation verified against its supplied excerpt. Fabric remained connected. See [warehouse results](ai-warehouse-fix-results.json).
- One earlier live attempt was rejected for a non-verbatim citation; a subsequent request passed. Structured output constrains format, not factual accuracy or quotation fidelity. Invalid quotations continue to block the entire answer; users may retry or narrow their question.
- Before/after preservation snapshots matched for users, cases, memberships, evidence records/ciphertexts, custody history, transaction records and the encryption key. Only the backend service was replaced; no ledger reset or data migration was performed.


## Citation reliability fix — 16 October 2026

The response-format fix above did not eliminate non-verbatim quotations. Gemini now returns passage references instead of writing quotations. Each reference maps to an exact slice of the selected evidence, and the backend supplies the quotation and its source ID. This removes copying mistakes without fuzzy matching, accepting paraphrases as quotations, or weakening case permissions. Unknown IDs and unsupported response fields remain blocked. The public API and citation display are unchanged.

All 24 assistant tests passed, including exact whitespace preservation, passage size boundaries, unknown-reference rejection, permissions, tampering and original-record preservation. A separate live Gemini check passed using the three fictional warehouse files. Quotation accuracy does not establish that the model's interpretation is correct; claims still require human review.

The rebuilt running backend passed two further warehouse summary API requests (six and five claims), with every quotation verified. One separate application request received a temporary upstream Gemini service error; it produced no answer. See [repeat results](ai-passage-repeat-results.json). Before/after preservation snapshots matched for users, cases, memberships, evidence/ciphertexts, custody records, transaction records and the encryption key. Fabric stayed connected. Only the backend service was recreated.

## Read paper documents and scans

1. Upload a PDF, PNG or JPEG through the usual Evidence vault workflow and assign it to the correct case.
2. Open Case assistant and select that case and the document. Choose a summary or ask a question.
3. For a PDF page containing both selectable text and photographed notes, enable **Scan every PDF page**. Otherwise pages with usable text use direct extraction, and scanned pages use OCR automatically.
4. Confirm external processing only for fictional demonstration records. OCR runs locally; Gemini receives selected extracted text, not the document image.
5. Review the page number and quotation beneath each answer. Expand the supplied excerpts to inspect the extracted text. Follow the evidence link to access the original document under the existing permissions.

OCR quotations reproduce the extracted text, which may differ from the original image. Uncertain pages are flagged; blank/unreadable pages and page-count limits are disclosed. This release does not provide reliable handwriting recognition or non-English OCR. It does not store a persistent OCR index or modify original evidence, encryption keys, or ledger entries. Temporary shared-memory images are removed when extraction returns or raises an error; abrupt process termination and OS swap remain outside secure-erasure guarantees.

## OCR validation — 16 October 2026

35 assistant/document tests passed in Docker, including real two-page scanned PDF, PNG/JPEG, selectable PDF, blank-page handling, page citations through the authorized API, and temporary-file cleanup. The existing 22 workflow tests also passed. TypeScript and the frontend production build passed. A live Gemini request answered from the synthetic scanned document and correctly cited page 2. Backend and frontend were rebuilt and deployed; Fabric remained connected. Before/after preservation snapshots matched. See [validation results](ocr-validation-results.json). Tests used isolated or synthetic records and did not add demonstration evidence to the live ledger.
