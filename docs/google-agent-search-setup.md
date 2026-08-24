# Google Agent Search Setup

## Prerequisites

- A Google Cloud project with billing enabled
- A Google account with access to the Cloud project
- Permission to create or configure an Agent Search app
- A private Cloud Storage bucket for synthetic POC documents

## Setup outline

1. Open Google Cloud **AI Applications / Agent Search**.
2. Create a private Cloud Storage bucket and upload supported synthetic files.
3. Create an unstructured data store with **Cloud Storage** as the source.
4. Create a search app and attach the Cloud Storage data store.
5. Enable enterprise and generative answer features required by the Answer API.
6. Copy the Cloud project ID, location, and app/engine ID into `.env`.
7. Authenticate locally with Application Default Credentials:

   ```bash
   gcloud auth application-default login
   ```

8. Run the CLI test before configuring LINE:

   ```bash
   python -m enterprise_knowledge_assistant.cli "Ask a question with a known answer"
   ```

## Runtime authentication

Local development uses the signed-in developer's Application Default
Credentials. Cloud Run should use a dedicated service account with only the
permissions required to call Agent Search and read configured secrets. Do not
download or commit a service-account key.

The Cloud Storage bucket name and data store ID are not runtime environment
variables: the Agent Search app is already connected to its data store. The
application only needs the project ID, location, and app/engine ID.

## Recommended POC corpus

- 20–50 approved files
- One department or one consistent permission group
- TXT, DOCX, PPTX, HTML, and text-based PDFs first
- No HR, legal, financial, customer-sensitive, or regulated content
- A separate synthetic corpus for screenshots and public demos

## Troubleshooting

### Import completed but no results

Open the data store's Documents page and wait until each document shows
`Indexed`. Uploading a file to the bucket does not make it immediately
searchable.

### Search returns unrelated documents

Confirm that the app is attached to the intended POC data store and that the
document URI points to the expected private bucket.

### Updated files do not appear

The POC uses one-time ingestion. Run Import/Refresh again, or introduce a
periodic connector or event-driven ingestion pipeline when freshness becomes a
product requirement.

### No generated answer

Confirm that generative responses are enabled and first verify that standard
search finds the expected document.
