# Application test and flaw review — 27 October 2026

Audited application revision: `67708a7`. This review changes tests and documentation,
not application behaviour. Six defects were reproduced. The application is suitable
for a clearly labelled local demonstration, but these defects should be resolved
before a learner pilot. Passing the existing tests did not establish release readiness.

## Verification performed

- Existing real-pytest suite: **211 passed**, one existing Starlette/httpx warning.
- Next.js production build, including TypeScript validation: **passed**.
- Existing Chromium desktop/mobile suite: **6 passed, 1 failed, 1 intentionally
  skipped**. The failed desktop learning journey stalled immediately after saving
  the first goal. Mobile here means Pixel 7 browser emulation, not a physical phone.
- Four additional backend probes: **four confirmed failures** when run with
  `--runxfail`. Normal runs label them strict expected failures, not passes.
- Two additional desktop browser probes: **two confirmed expected failures**.
  The first deliberately schedules a late goal response; the second drops a save
  response only after the real backend accepted it. Both fail at the intended
  assertion, not setup. Playwright's summary calls expected failures "passed";
  that does not mean the application behaviours passed.

All tests used isolated synthetic data and test identities. No exposed provider
credential was saved or used. Hosted Supabase auth, production PostgreSQL,
deployment, real Groq response quality and real learner outcomes were not tested.

## QA-5 — P1: saving a goal can leave the roadmap blank

Location: `frontend/app/page.tsx`, `load` and `saveGoal` (lines 33–70).

Changing target checkboxes changes the `load` callback and launches another effect
read. Saving the goal launches another read. These reads can complete out of order:
an older response containing no goal calls `setGoal(null)` after the saved-goal
response has populated the page. The roadmap requires both `goal` and `roadmap`,
so its next-step button and route disappear despite a successful save.

Evidence: the existing desktop journey failed waiting for Start after HTTP 200
from PUT goal. A controlled browser reproduction showed Recommended next step,
then released the older null-goal response and confirmed that section disappeared.
A page reload is a workaround.

Fix: separate editable form state from initial loading; cancel or ignore outdated
loads with a generation counter/cleanup. A completed save must invalidate pending
older reads. Retain the slow-response browser test.

## QA-1 — P1: independent-test scores leak through other endpoints

Location: `backend/personalisation.py` lines 189, 278 and 319; compare the
withholding guard in `backend/learning.py` around line 845.

During an unfinished retest, submit correctly hides `correct` and gaps hides the
score. However, roadmap and teaching expose the current mastery estimate. Polling
these endpoints after each answer reveals the change in score and therefore
whether an answer helped or hurt it. These are ordinary learner endpoints.

Evidence: after one synthetic correct answer in a ten-question retest, the session
was still active and gaps returned no score, but roadmap and teaching both returned
`0.6224593312018546`. The intended `(None, None)` assertion failed.

Fix: apply the same active-assessment withholding policy to every learner-facing
projection of scores, including teaching-plan selection and any derived signals.

## QA-2 — P2: independent MCQ tests give immediate teaching feedback

Location: `backend/learning.py` lines 590–599.

The misconception-feedback branch excludes validation forms but includes
verification/retest and review sessions. A wrong option can therefore return its
misconception description, correction and occurrence count before the independent
test finishes. The session page displays this information immediately. Besides
revealing an error, the correction can coach subsequent related questions.

Evidence: first wrong option in a ten-question MCQ retest returned
`session_complete: false`, no `correct` field, but a `misconception_feedback`
object advising the learner to check digit sums against 9.

Fix: withhold this feedback during independent forms; release eligible feedback
only after completion, preserving the validation forms' stricter restrictions.

## QA-3 — P1: an in-flight request can recreate deleted account data

Location: `backend/api.py` lines 124–131 and `backend/learning.py` lines 132–139.

The deletion-tombstone check, rate limiting and registration happen in separate
transactions. A request can pass the tombstone check, pause while another request
deletes the account, and then resume registration and save new data. Registration
does not recheck the tombstone under a shared deletion/identity lock.

Evidence: a deterministic interleaving deleted the account after the goal request's
tombstone check and before registration. The goal request then returned HTTP 200;
both Learner and LearnerGoal existed again alongside DeletedIdentity. Expected
behaviour was HTTP 403 and no recreated rows. Subsequent fresh requests are still
blocked by the tombstone; this is an in-flight race, not general deletion bypass.

Fix: serialize authentication-to-registration/write with deletion and recheck the
tombstone inside that critical section. Consider an identity lock that survives
removing the Learner row; locking only that deleted row is insufficient.

## QA-6 — P2: retry after a lost submission response gets HTTP 409

Location: `frontend/app/session/[id]/page.tsx` lines 58–65;
`backend/learning.py` lines 480–493.

The client retains an idempotency key but rebuilds the payload, including a newly
measured `duration_ms`, on each click. The backend hashes that duration. When it
commits a submission but the response is lost, pressing Submit again reuses the
key with different content and fails with an idempotency conflict. The user is
told to retry, but retries cannot resolve that state.

Evidence: the browser test forwarded the first request to the real API, verified
HTTP 200, then discarded its response. The retry returned HTTP 409 instead of
replaying HTTP 200. Reloading the session is a workaround, since the answer was
actually saved.

Fix: retain the complete first submission payload with its key until the outcome
is resolved. Do not weaken the server's protection against changed submissions.

## QA-4 — P2: mixed practice silently omits requested topics

Location: `backend/timed_practice.py` lines 31–46.

Round-robin selection checks only the total number of questions. If one requested
topic has no fresh reviewed practice questions, the other pool can fill the entire
test. The stored `skill_ids` still lists the unavailable topic.

Evidence: requesting four questions across divisibility and integer-properties
after withdrawing the latter's items created a test successfully. Its declared
topics contained both; its actual question topics contained only divisibility.

Fix: require at least one selectable family per requested topic before filling
the remaining slots, accounting for family overlap, or explicitly ask the learner
to change the selection. Fail without reserving families when coverage is absent.

## Reproduce and track the findings

Backend reproductions (run from the project root):

```powershell
.venv/Scripts/python.exe -m pytest tests/test_known_regressions.py --runxfail -q --tb=short
```

This currently produces four assertion failures by design. Remove the respective
strict `xfail` markers only after fixing and verifying each defect.

Browser reproductions require the same production build settings as the existing
browser suite. Run inside `frontend/`, with Node on PATH:

```powershell
$env:NEXT_PUBLIC_LOCAL_DEVELOPMENT='1'
$env:MASTRR_API_ORIGIN='http://127.0.0.1:8765'
npm run build
npx playwright test known-regressions --project=desktop
```

Each browser reproduction is explicitly marked as a known expected failure.
Remove `test.fail` when its fix is ready; an unexpected pass currently fails the
suite so a repaired defect cannot remain quietly masked. The existing full
learning journey remains unmasked and currently fails intermittently at QA-5.

Recommended repair order: QA-5 (first-run usability), QA-1/QA-2 (assessment
integrity), QA-3 (deletion semantics), QA-6 (network recovery), QA-4 (topic coverage).
Run all normal tests and the relevant probes after each fix, then repeat the full
desktop/mobile journey. A separate hosted integration run remains necessary.
