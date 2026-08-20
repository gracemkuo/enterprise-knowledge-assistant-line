# Public Repository Checklist

Complete this checklist before the first public push.

## Stakeholder approval

- [ ] Written approval to publish the reusable source code
- [ ] Decision on whether the company name may be mentioned
- [ ] Decision on whether screenshots or architecture details may be shown
- [ ] Confirmation of code ownership and the intended software license

## Sensitive-content review

- [ ] No `.env`, OAuth JSON, tokens, API keys, or LINE credentials
- [ ] No real Drive, file, folder, project, tenant, or Workspace IDs
- [ ] No company documents, recordings, transcripts, prompts, or chat logs
- [ ] No employee, customer, vendor, or project identifiers
- [ ] No real screenshots; recreate every screenshot with synthetic data
- [ ] No production URLs, domains, IP addresses, or infrastructure names
- [ ] No sensitive content anywhere in Git history

## Repository quality

- [ ] README explains the problem, architecture, setup, and limitations
- [ ] Synthetic demo data is clearly labeled
- [ ] Tests pass in a clean environment
- [ ] GitHub secret scanning and push protection are enabled
- [ ] Security reporting instructions are present
- [ ] License choice has been reviewed and added, if appropriate

## Final review

Clone the repository into a clean temporary directory and follow the README as
an external visitor would. Search the entire repository and Git history for
known company names, domains, emails, Drive IDs, and credential patterns before
changing repository visibility to public.

