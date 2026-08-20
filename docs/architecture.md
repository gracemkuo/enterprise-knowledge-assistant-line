# Architecture Decision — Managed Search POC

## Context

The company already stores source material in Google Workspace. The first goal
is to validate knowledge-base question answering through LINE, not to build a
custom retrieval platform.

## Decision

Use LINE Messaging API for the interface, a small FastAPI webhook service for
orchestration, and Google Agent Search connected to a dedicated Google Drive
scope for retrieval and generated answers.

## Data flow

1. An allowlisted tester sends a text message to the LINE Official Account.
2. LINE posts a signed webhook event to `/callback`.
3. The service verifies the signature and checks the LINE user allowlist.
4. The question is sent to Agent Search using managed Workspace user
   credentials.
5. Agent Search searches the configured Drive content and returns an answer
   with source metadata.
6. The service sends the answer and up to three source links to LINE.

## Key trade-offs

### Managed Agent Search instead of custom RAG

Benefits:

- Faster path to validating user value
- No vector database, chunk synchronization, or deletion pipeline
- Google Drive remains the source of truth

Costs:

- Less control over chunking, retrieval, and reranking
- Workspace search has identity and product constraints
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
- All POC testers are authorized to view the entire selected Drive corpus.
- Real documents and conversation logs are never stored in this repository.
- Application logs contain error types, not questions, answers, or documents.

These assumptions are not sufficient for a multi-department rollout. That
version requires account linking and per-user Workspace access enforcement.

