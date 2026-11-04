# Tripjack Certification V3 – Hotel

A local web tool that checks Hotel API V3 UAT test cases before they are submitted to Tripjack
for certification. Partners upload their test-case folder and get, for each of the 14
certification test cases, a PASS / FAIL result, a plain-language list of errors with how to fix
them, and a downloadable Excel (CSV) report.

## Run

Needs Python 3.10+ (standard library only, nothing to install).

```bash
./run.sh            # http://127.0.0.1:8765, opens the browser
./run.sh 9000       # another port
HOST=0.0.0.0 ./run.sh   # reachable from other machines on the network
```

Command-line check without the UI:

```bash
python3 validate_hotel_test_cases.py --root "/path/to/test cases"
python3 validate_hotel_test_cases.py --root "/path/to/test cases" --case "Test Case 4" --json-report report.json
```

## Deploy on Vercel

The repo deploys to Vercel as-is (Framework preset: **Other**, no build command):

- `/` serves `audit_ui/index.html` (see `vercel.json` rewrites).
- `api/upload_folder.py` runs the same upload handler as the local server as a Python function.
- Vercel limits a request body to about 4.5 MB, so very large test-case folders must be run locally with `./run.sh`.

## Sign in (Google / Microsoft)

Users sign in before they can upload. Sign-in is off until at least one client ID is set.

| Variable | Where to get it |
|---|---|
| `GOOGLE_CLIENT_ID` | Google Cloud Console → APIs & Services → Credentials → OAuth client ID → Web application. Authorised redirect URIs: `https://hotelcertification.vercel.app/` and `http://127.0.0.1:8765/` |
| `MICROSOFT_CLIENT_ID` | Azure portal → App registrations → New registration. Supported accounts: any organisation + personal Microsoft accounts. Platform **Web**, redirect URIs as above, and tick **ID tokens** under Implicit grant |
| `SESSION_SECRET` | Any long random string (e.g. `openssl rand -hex 32`). Required on Vercel |

The server checks each sign-in token against Google's / Microsoft's public keys, then sets a signed,
HttpOnly session cookie (12 hours). The signed-in email is used in the certification email.

## Certification email

After every upload (for now; the 14/14 condition is switched off) the server emails the partner's form details (name, company,
TJ user ID, phone, email) and the results (how many passed / failed) to `aryan.singh@tripjack.com` and `arun.bhati@tripjack.com`.

**Groundmail (simplest, free):** set `GROUNDMAIL_API_KEY` (starts with `gm_`). Without a verified domain it sends
from `noreply@mail.groundmail.dev` and only to the Groundmail account's own email, so sign up with the address
in `CERT_NOTIFY_TO`. Free plan: about 3,000 emails/month, 100/day.

**Google Apps Script (no SMTP, no DNS):** deploy `tools/apps_script_mailer.gs` as a web app from your Google
account (Execute as: Me, Access: Anyone) and set `CERT_WEBHOOK_URL` to its `/exec` URL. It emails from your
Gmail and logs each upload to a Google Sheet.

**Mailercloud:** set `MAILERCLOUD_API_KEY` and `MAIL_FROM` (a sender verified in Mailercloud);
optional `MAIL_FROM_NAME`.

**Or SMTP:** set these environment variables
(Vercel: Project → Settings → Environment Variables, then redeploy):

| Variable | Example |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` (or `465` for SSL) |
| `SMTP_USER` | the sending mailbox |
| `SMTP_PASS` | its app password |
| `MAIL_FROM` | optional, defaults to `SMTP_USER` |
| `CERT_NOTIFY_TO` | optional, comma-separated; defaults to `aryan.singh@tripjack.com,arun.bhati@tripjack.com` |

Without them the check still works, but no email is sent (`[cert-mail] SMTP not configured` in the logs).

## Expected upload

One sub-folder per test case (`Test Case 1` … `Test Case 14`), each with the request and
response JSON for Search, Detail, Review, Hold / Book (and Confirm Hold), Booking Detail, and
Cancel where applicable. ZIP files must be unzipped first.

- Every booking needs a Booking Detail request + response with the updated status.
- Cancel cases need a second Booking Detail showing `CANCELLED`.
- Test Case 14 must contain the Booking Detail response of every test booking showing `CANCELLED`.

## What is checked

correlationId, dates / nationality / currency, room setup, hotel ID chain, reviewHash, optionId,
room / price consistency, guests per room, PAN / passport, payment amount, the room and guest
requirement of each test case, booking status, cancellation of every test booking, and invalid
JSON (with line and column).

## Files

| File | Purpose |
|---|---|
| `validate_hotel_test_cases.py` | Validation engine and CLI |
| `auth.py` | Google / Microsoft sign-in and session cookies |
| `audit_ui_server.py` | Local web server (folder upload, runs the validator) |
| `audit_ui/` | Web UI (HTML, CSS, JS) |
| `run.sh` | Starts the server |
| `api/upload_folder.py`, `vercel.json` | Vercel deployment |

Uploaded files are written to a temporary folder only for the check and deleted right after.
