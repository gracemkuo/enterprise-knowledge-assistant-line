# Architecture Decision — Managed Search POC

## Context

The target customer stores source material in Google Workspace, but the
portfolio developer does not have a managed Workspace tenant. The first goal is
to validate knowledge-base question answering through LINE without borrowing a
customer account or exposing company data.

## Decision

Use LINE Messaging API for the interface, a small FastAPI webhook service for
orchestration, and Google Agent Search connected to a private Cloud Storage
bucket containing synthetic documents. Keep the retrieval boundary replaceable
so a customer deployment can use Google Workspace or another ingestion source.

## Data flow

1. An allowlisted tester sends a text message to the LINE Official Account.
2. LINE posts a signed webhook event to `/callback`.
3. The service verifies the signature and checks the LINE user allowlist.
4. The question is sent to Agent Search using Google Cloud credentials.
5. Agent Search searches the indexed Cloud Storage documents and returns an answer
   with source metadata.
6. The service sends the answer and up to three source links to LINE.

## Key trade-offs

### Managed Agent Search instead of custom RAG

Benefits:

- Faster path to validating user value
- No vector database, chunk synchronization, or deletion pipeline
- No paid Workspace tenant is required for the portfolio POC
- Cloud Run can use a dedicated service account

Costs:

- Less control over chunking, retrieval, and reranking
- One-time imports do not provide automatic freshness
- Continued dependency on Google Cloud pricing and APIs

### Synchronous webhook for the POC

Benefits:

- Minimal components
- Easy local debugging

Costs:

- Long searches can delay the LINE reply
- No durable retries

Revisit this after the POC. A production version should acknowledge the webhook
quickly, enqueue the query, and deliver the completed answer with a LINE push
message.

## Security assumptions

- Only explicitly allowlisted LINE IDs can use the POC.
- All POC testers are authorized to view the entire selected demo corpus.
- Real documents and conversation logs are never stored in this repository.
- Application logs contain error types, not questions, answers, or documents.

These assumptions are not sufficient for a multi-department rollout. A
Workspace-based customer version requires account linking and per-user access
enforcement; an ingestion-based version requires document ACL metadata and
retrieval-time filtering.
