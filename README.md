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

## Certification email

When an upload passes all 14 test cases, the server emails the partner's form details (name, company,
TJ user ID, phone, email) and the results to `aryan.singh@tripjack.com`. Set these environment variables
(Vercel: Project → Settings → Environment Variables, then redeploy):

| Variable | Example |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` (or `465` for SSL) |
| `SMTP_USER` | the sending mailbox |
| `SMTP_PASS` | its app password |
| `MAIL_FROM` | optional, defaults to `SMTP_USER` |
| `CERT_NOTIFY_TO` | optional, defaults to `aryan.singh@tripjack.com` |

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
| `audit_ui_server.py` | Local web server (folder upload, runs the validator) |
| `audit_ui/` | Web UI (HTML, CSS, JS) |
| `run.sh` | Starts the server |
| `api/upload_folder.py`, `vercel.json` | Vercel deployment |

Uploaded files are written to a temporary folder only for the check and deleted right after.
