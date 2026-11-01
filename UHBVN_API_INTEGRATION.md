# UHBVN Consumer Portal — live integration checklist

This repository currently provides a Streamlit consumer-information guide and a personal dashboard for records entered by the consumer. It does **not** yet retrieve private UHBVN records or send/verify OTPs.

## What is already in the website

- UHBVN Consumer Help: bill terminology, meter-unit calculator, complaint guidance, consumer contacts and official service links.
- My Consumer Dashboard: account-based prototype sign-in, connection profile, manually saved bill rows, optional bill-file storage and usage/bill charts.
- Existing POWERGUARD theft-monitoring, data upload, reports and monitoring pages remain separate.

## Required before live UHBVN data can be enabled

An assertion that API access exists is not enough to safely implement the connector. The integration needs the official API contract and a test credential issued for this application. Do not commit credentials or send them in chat.

Ask the UHBVN API administrator for:

1. Base URL for the approved production and sandbox environments.
2. Authentication method (OAuth2 client credentials, signed request, API key, mTLS, or other documented method).
3. OTP request and OTP verification endpoint specifications, including rate limits, expiry, retry limits and whether OTP is sent only to the mobile already registered against the consumer account.
4. Consumer/account verification endpoint and the exact identifier required (for example, K-number/account number).
5. Read-only endpoints and response schemas for consumer profile, connection/meter details, current bill, bill history, meter-reading history, payment history/receipts, complaints and outage notices.
6. Pagination, date filters, error codes, API quotas, data-retention rules and permission to display/cache each field.
7. A sandbox account and test cases for valid, invalid, expired OTP; mismatched account; multiple connections; missing bill; and API outage.

## Required application flow

1. Consumer enters registered mobile number and the UHBVN account identifier.
2. Server requests an OTP using the official endpoint. Never send OTP from browser JavaScript or log it.
3. Consumer enters the OTP. Server verifies it with UHBVN.
4. Server creates a short-lived authenticated session only after successful verification and account-ownership confirmation.
5. Server fetches only the verified account's permitted records. Every request must be authorized server-side; never trust a consumer ID supplied by the browser.
6. Display source, last-updated time and any missing/unavailable fields. Do not invent readings, bill amounts, payment status or outage information.
7. Log security events without storing OTPs, access tokens, full mobile numbers or unnecessary personal data.

## Data sections to expose after API approval

- Consumer identity and contact details (mask mobile number by default).
- Connection details: account/K-number (mask by default), meter number (mask by default), category, sanctioned load, subdivision/division and connection status.
- Current bill: bill number, billing period, previous/current reading, reading date, units, meter multiplier, energy/fixed charges, adjustments, taxes/duty, arrears, credits, total, due date and payment status.
- Bill history and downloadable official bill copies, if the API permits.
- Meter readings: register type (kWh/kVAh), reading value, date, reading source (actual/estimated/consumer-submitted), meter status and history.
- Payments: transaction/reference, date, amount, status and receipt, subject to API permissions.
- Complaints: complaint ID, category, status, timestamps and official response.
- Outages/notices: area, affected period, status, published time and source.

## Deployment and security requirements

- Keep credentials in Streamlit Secrets or the hosting platform's secret manager; never in Git, source code, query strings or client-side code.
- Use HTTPS, secure cookies/session handling, CSRF protection where applicable, strict session expiry, rate limiting, OTP attempt limits and generic login errors.
- Use a managed persistent database with per-user/connection authorization and row-level access controls. Do not rely on local SQLite for public production use on ephemeral hosting.
- Do not store OTPs. Minimize or avoid storing API responses; use only an approved short cache lifetime.
- Restrict bill downloads to the authenticated owner and use private object storage if files must be retained.
- Add audit logging, backup/restore, dependency updates, security testing and a privacy notice before public launch.
- Do not automate login to, scrape, or bypass protections on UHBVN consumer websites. Use only the approved API.

## Configuration template (names are illustrative, not actual UHBVN endpoint paths)

Store these values in the hosting secret manager after receiving the official specification:

- `UHBVN_API_BASE_URL`
- `UHBVN_CLIENT_ID`
- `UHBVN_CLIENT_SECRET` (or the credential type UHBVN specifies)
- `UHBVN_OTP_REQUEST_PATH`
- `UHBVN_OTP_VERIFY_PATH`
- `UHBVN_CONSUMER_PROFILE_PATH`
- `UHBVN_BILL_CURRENT_PATH`
- `UHBVN_BILL_HISTORY_PATH`
- `UHBVN_METER_READINGS_PATH`
- `UHBVN_PAYMENT_HISTORY_PATH`
- `UHBVN_COMPLAINTS_PATH`
- `UHBVN_OUTAGES_PATH`

The path names above are placeholders. Do not configure or call them until they are matched to the actual UHBVN API documentation.

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app can be used as a public-information site and a manual-record prototype before live API credentials and schemas are configured. Label manual/demo data clearly so consumers do not mistake it for official live account data.
