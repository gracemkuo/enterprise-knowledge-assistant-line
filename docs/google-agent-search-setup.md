# Google Agent Search Setup

## Prerequisites

- A Google Cloud project with billing enabled
- A managed Google Workspace account
- Permission to create or configure an Agent Search app
- An approved Google Shared Drive or folder for POC documents

## Setup outline

1. Open Google Cloud **AI Applications / Agent Search**.
2. Create a data store with **Google Drive** as the source.
3. Select only the dedicated POC Shared Drive or approved folders.
4. Create a search app and attach the Drive data store.
5. Enable enterprise and generative answer features required by the Answer API.
6. Copy the Cloud project ID, location, and app/engine ID into `.env`.
7. Authenticate locally with a managed Workspace user:

   ```bash
   gcloud auth application-default login
   ```

8. Run the CLI test before configuring LINE:

   ```bash
   python -m enterprise_knowledge_assistant.cli "Ask a question with a known answer"
   ```

## Important identity limitation

Google Workspace data stores do not support search requests authenticated with
ordinary service-account credentials. The search must use a managed user from
the same Workspace organization as the connected data.

For this POC, run with one authorized tester's Application Default Credentials.
Do not treat that shared identity as a production access-control design.

## Recommended POC corpus

- 20–50 approved files
- One department or one consistent permission group
- Google Docs, Slides, and text-based PDFs first
- No HR, legal, financial, customer-sensitive, or regulated content
- A separate synthetic corpus for screenshots and public demos

## Troubleshooting

### 403 with service-account credentials

Re-authenticate with a managed Workspace user. Do not try to solve this by
granting the service account broader Drive permissions.

### Search returns unrelated documents

Confirm that the app is attached only to the intended POC data store and that
the selected Shared Drive/folder IDs are correct.

### No generated answer

Confirm that generative responses are enabled and first verify that standard
search finds the expected document.

