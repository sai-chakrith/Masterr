# Record a local Mastrr demo

The normal database intentionally contains unpublished drafts. The recording
launcher creates a new database under ignored `.demo/`, prepares clearly marked
sample content and starts both the API and frontend on loopback. It never
changes source approvals or `data/local.db`. This is a demonstration, not a
published learner service or independent content review.

## Start

Install the locked Python/frontend dependencies first, then run from the project:

```powershell
.venv/Scripts/python.exe -m scripts.demo serve --sample-content --topic divisibility --seed-mistakes
```

Open `http://127.0.0.1:3001`. Paste the **local demo token** from the file named
in the launcher's output into the password-style local sign-in field. The Groq
key is never printed and is never the sign-in token. The API uses port 8880 and
the frontend has its own `.next-demo` build folder. Existing local apps can stay
on ports 8000/3000. Press Ctrl+C in the launcher to stop its two child processes.
You can also run `.venv/Scripts/python.exe -m scripts.demo stop` from another
terminal. It requests shutdown through the isolated folder; it never kills a
process merely by a reused port or PID.

Every run creates a fresh database. Omit `--seed-mistakes` to record a sample
diagnostic yourself. Including it completes a sample diagnostic with "I don't
know" answers, so you can start recording at personal tutoring. These are
prepared demonstration attempts, not real learner results.

## Enable live Groq

Revoke any key that was pasted into chat. Save its replacement in the private
root `.env` file as `GROQ_API_KEY=...`, or set it in your backend process
environment. Do not commit the file or put the key in a frontend variable.

The local parser loads plain `KEY=value` entries without executing shell syntax.
Existing process settings take precedence, including an explicitly empty key.
Local API startup also loads this file when `LOCAL_DEVELOPMENT=1`; hosted
deployments continue to use their secret store. Malformed entries report line
numbers, never their values.

Run the launcher with **explicit live mode**:

```powershell
.venv/Scripts/python.exe -m scripts.demo serve --sample-content --live --topic divisibility --seed-mistakes
```

The key stays in the API's environment and is removed from the frontend child's
environment. Without `--live`, the demo forces an empty provider key and uses
labelled fallback text even if a key exists locally. A banner labels the entire
application as a sample demo and distinguishes configured AI from offline mode.
The individual tutor parts always identify their actual source.

With that server running, use another terminal:

```powershell
.venv/Scripts/python.exe -m scripts.demo check-live
```

The check requires real AI output for both parts, then both caches and no new
provider calls on reopening. It prints only generation/cache flags and recorded
usage. It fails on fallback; it never invents a successful provider response.
An HTTP 401 usually means invalid credentials, 429 means the provider refused
the request due to its limits, and 400 means the request needs inspection.
Only numeric HTTP status is retained, never provider error text or headers.

## Suggested recording sequence

1. Keep the demo banner visible. Explain that content and learner records are samples.
2. Show the selected goal and roadmap.
3. Open Tutor, select the prepared topic, and generate the lesson and personal part.
4. Show the actual source labels. With live AI, mention that final-answer checking
   does not validate every reasoning step.
5. Reopen tutoring to demonstrate cached parts, then continue to practice.
6. Briefly show timed practice, history and the reviewer console.

Do not expose the root `.env`, provider dashboard keys, or token file while
recording. Hosted signup, public deployment, human content approval and measured
learning effectiveness remain separate launch tasks.
