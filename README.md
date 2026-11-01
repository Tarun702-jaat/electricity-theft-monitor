# POWERGUARD GLOBAL — Electricity Theft Monitor & UHBVN Consumer Portal

A Streamlit application combining an electricity-theft monitoring prototype with a consumer-facing UHBVN information centre.

## Website sections

- **Overview:** high-level monitoring dashboard (demo/public-reference data unless connected to verified sources).
- **UHBVN Consumer Help:** plain-language guide to bills, meter readings, unit calculation, consumer complaints, contacts and official service links.
- **My Consumer Dashboard:** private prototype account, consumer-entered connection profile, manual bill history, optional bill attachments and consumption charts.
- **India Monitoring:** regional utility monitoring view.
- **Theft Detection:** rule/ML anomaly review. Flags are candidates for human review, not proof of theft.
- **Data Centre, News Intelligence and Reports:** existing monitoring and reporting functions.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Consumer dashboard — current status

The current dashboard is a **prototype**, not a live UHBVN account connection:
- It uses email/password prototype sign-in and stores passwords as salted PBKDF2-HMAC-SHA256 hashes. New accounts must complete email OTP verification before opening the dashboard.
- Consumers can enter their own connection label and bill figures and upload a bill copy.
- Consumers can mark bill records as paid, unpaid, disputed or unmarked, record a payment date, review totals and usage trends, and export their saved bill history as CSV.
- The dashboard compares recent saved bills, provides a simple clearly labelled next-bill planning estimate, and gives general electricity-saving suggestions based on recorded usage changes.
- The Consumer Help page includes a step-by-step bill-payment guide and a complaint-draft assistant that consumers can download and submit themselves through official UHBVN channels.
- Usage insights are calculated only from consumer-entered records; they are not live meter readings, official balances or tariff forecasts.
- It sends a 6-digit email OTP when SMTP is configured. The code expires after 5 minutes and is limited to 5 attempts. This verifies email ownership only; it does not verify a UHBVN consumer number or registered mobile.
- It does not automatically OCR uploaded bills.
- It must not be presented as an official UHBVN service or as displaying verified live account data.

The UHBVN Consumer Help page provides public guidance and links to official services. The official service links are opened in a separate browser tab. Account-specific transactions should be completed through UHBVN's official portals until an approved API integration is implemented.

## UHBVN live API integration

The user-facing live API connector cannot be safely completed from a statement that API access exists alone. The official API documentation is needed for the real base URL, authentication scheme, OTP flow, endpoint paths, response schemas, sandbox and permission scope. **Do not guess endpoint URLs or fabricate consumer data.**

See [UHBVN_API_INTEGRATION.md](UHBVN_API_INTEGRATION.md) for the integration checklist, data fields, secure OTP flow, deployment requirements and configuration placeholders.

Never commit API credentials, OTPs, private keys or real consumer records to this repository.

## Storage and production readiness

- The prototype stores data in local SQLite at `powerguard_data/consumer_portal.sqlite3` by default.
- Local filesystem persistence is not guaranteed on Streamlit Community Cloud.
- Do not collect real consumer bills or personal data from the public until the app uses a managed persistent database with per-user/connection authorization, private file storage, backups, secure sessions, access logging and a privacy/security review.
- Set `POWERGUARD_DATA_DIR` only to a persistent, access-controlled directory if using the prototype locally.
- Use a managed identity provider and row-level access controls for a production release.

## Official UHBVN services

The website's UHBVN Consumer Help page links to official UHBVN bill payment, Trust Reading, payment receipt and complaint services. Verify service availability and current terms on UHBVN's official website.


### Configure email OTP (required for account verification)

In Streamlit Community Cloud, open **App → Settings → Secrets** and add SMTP credentials from an email provider that permits SMTP access. Do not put credentials in source code or commit them to GitHub:

```toml
SMTP_HOST = "smtp.example.com"
SMTP_PORT = "587"
SMTP_USERNAME = "your-sender@example.com"
SMTP_PASSWORD = "provider-app-password"
SMTP_FROM = "POWERGUARD <your-sender@example.com>"
```

Use the provider's app password or SMTP credential, not your normal mailbox password. The owner must configure valid SMTP credentials before email OTP can be sent. Existing accounts will also need to verify their email the next time they sign in.

**UHBVN verification is separate:** real consumer/account and registered-mobile verification requires UHBVN's authorised API or official KYC/OTP process. Do not label an email OTP as UHBVN verification.
