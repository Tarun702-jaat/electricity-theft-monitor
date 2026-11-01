# electricity-theft-monitor
Smart electricity theft detection dashboard built with Streamlit for monitoring suspicious meter readings and generating reports.

## Personal Consumer Dashboard (prototype)

The **My Consumer Dashboard** page adds account-based sign-in, a consumer connection profile, manually entered bill records, optional PDF/JPG/PNG bill attachments (5 MB maximum), and personal consumption/bill-history charts.

### Prototype storage and privacy

- Passwords are stored as salted PBKDF2-HMAC-SHA256 hashes; plaintext passwords are not stored.
- Consumer profile and bill queries are scoped to the signed-in account.
- The prototype stores records and uploaded attachments in a local SQLite file at `powerguard_data/consumer_portal.sqlite3` by default.
- Set the `POWERGUARD_DATA_DIR` environment variable to a persistent, access-controlled directory before deployment if the hosting platform supports one.
- **Streamlit Community Cloud local files are not guaranteed to persist across restarts/redeployments.** This SQLite implementation is a demonstration, not a production-grade store for real consumer bills. Do not invite the public to upload sensitive bills until a managed persistent database, private file storage, backups, transport security, access controls, and a privacy review are in place.
- Ask users not to enter full utility account numbers, Aadhaar numbers, OTPs, passwords, or other unnecessary personal information. Redact personal details and QR/barcodes from bill attachments.
- The portal does not connect to UHBVN/DHBVN private systems, perform payments, or retrieve live meter readings. Users enter their own bill figures. Attachments are stored for download and are **not automatically OCR-scanned**.
- Email verification and password reset are not implemented in this prototype.

For a production release, migrate authentication to a managed identity provider and store per-user records in a persistent database with row-level security; use private object storage for bill files. Only integrate live utility data through an authorized UHBVN/DHBVN API.
