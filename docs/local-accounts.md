# Login redesign and local accounts

The login screen uses a forest-green/ivory desktop split layout and a compact
mobile form. It includes account creation, password confirmation, visibility
controls, busy/error states and seven-day persistence. The learning navigation
is hidden on login. Developer-token access is a collapsed secondary option.

## Backend connection

When local development is explicitly enabled, the browser calls FastAPI through
the same-origin Next.js proxy:

- `POST /v1/auth/signup`: username, password and optional `remember`.
- `POST /v1/auth/login`: the same fields; validates actual stored credentials.
- `POST /v1/auth/logout`: revokes the current cookie session.

Signup creates a unique learner subject with no reviewer grants. Goals and
learning records are owned by that subject. No shared demo identity is used for
normal username accounts. The frontend verifies `/v1/me/account` before redirecting.

Passwords use a random 16-byte salt and scrypt (`N=32768`, `r=8`, `p=3`). Random
32-byte session secrets are delivered in an HttpOnly, SameSite=Strict cookie;
only SHA-256 verifiers are stored in the database. HTTPS requests set Secure.
Local storage contains a non-secret UI marker, not the session credential.
Expiry and logout are enforced by the server. Missing usernames perform the same
password-hash work; failed logins use the same message. Auth requests have
database-backed username/IP limits, and cross-site browser origins are rejected.
Credential/session tables are excluded from data exports and deleted with the
account. PostgreSQL migration restricts browser-role access to these tables.

The additive migration is `c6e1f892a470`. Existing installations must run
`python -m alembic upgrade head`. API startup never changes schema automatically.
The local database was backed up and migrated during implementation.

## Boundaries

These username accounts are for the loopback development app. Hosted mode keeps
Supabase email/password, confirmation, refresh and recovery. Local auth endpoints
return 404 in hosted mode. This change does not provision Supabase or enable local
accounts in production. Local password reset and email verification are not
implemented. A configured hosted-auth integration still requires a live hosted run.

## Verification

Focused backend checks cover correct/incorrect credentials, password storage,
cookie properties, server-side revocation, expiry, case normalization, duplicate
usernames, throttling, two-account goal isolation, private exports and deletion.
SQLite migration round trips and PostgreSQL offline SQL checks pass.

Real Chromium tests on desktop and Pixel 7 emulation create an account, reject
mismatched passwords, save a goal, sign out, reject a wrong password, sign back in
and recover the saved goal. Screenshots are generated at `output/login-ui/`.
The existing learning journey and audit browser checks also pass.

Final verification: **221 backend tests passed** with one existing Starlette/httpx
deprecation warning; the production frontend build and TypeScript checks passed.
Across the existing-suite run and the corrected login-selector rerun, **13 browser
checks passed**, with three desktop-only/mobile exclusions retained. The initial
login test selector also matched Next.js's route announcer; it was narrowed to
the form's error element. The backend throttle test now fixes its bucket clock
to avoid crossing a minute boundary during the suite.

The running preview is at `http://127.0.0.1:3002/login`, connected to the updated
API on port 8001 and the migrated normal local database. No account or password
has been preconfigured for the user; choose Create account. Backend readiness
returned HTTP 200. This preview keeps provider calls disabled.

Security references: [Python hashlib](https://docs.python.org/3/library/hashlib.html)
and [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
