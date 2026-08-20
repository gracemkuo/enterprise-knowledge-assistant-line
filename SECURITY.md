# Security Policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Contact the
maintainer privately and include reproduction steps, affected components, and
potential impact.

## Data handling boundary

This repository must never contain production company documents, chat logs,
employee identifiers, Google Drive IDs, OAuth files, LINE credentials, or API
tokens. The public repository contains only reusable code and synthetic demo
content.

If a real secret is committed, revoke or rotate it immediately before removing
it from Git history.

