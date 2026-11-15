# POWERGUARD deployment

## Current application
The repository currently contains a Streamlit application (app.py), not the separate Flask rewrite discussed in planning. This deployment configuration publishes the existing application first so the project can have an independent Render URL without replacing its current functionality.

## Deploy on Render Free
1. Sign in to Render using the GitHub account that owns this repository.
2. Choose New + → Blueprint.
3. Select Tarun702-jaat/electricity-theft-monitor.
4. Render detects render.yaml. Review the service named powerguard-public.
5. Select the Free instance plan and apply.
6. Wait for the build and open the generated *.onrender.com address.

The application listens on Render's supplied PORT and exposes Streamlit's health endpoint at /_stcore/health.

## Connect a purchased domain
After the Render service exists:
1. Open the service Settings → Custom Domains.
2. Add the exact domain purchased by the owner (for example, powerguard.in).
3. Follow the DNS records Render displays. DNS values must be copied from the live Render dashboard; do not guess them.
4. Verify the domain in Render and wait for managed HTTPS provisioning.

The domain must first be purchased and its registrar account controlled by the project owner. This repository change does not purchase a domain or create the Render service.

## Important production limitations
- The existing app is Streamlit, so this is a first public deployment of the current app, not yet a separate Flask-based public/admin/consumer architecture.
- Render Free services can sleep when idle and have limited resources.
- Do not use local SQLite or local filesystem storage on an ephemeral free web service for important or real consumer data. Use a managed persistent database and secure object storage before handling real records.
- Do not upload real UHBVN consumer records until authentication, authorization, privacy controls, backups, and security review are complete.
- Configure email/OTP credentials only as Render environment variables. Never commit secrets to Git.
