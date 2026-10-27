# Hands-on demo walkthrough — 27 October 2026

Follow-up: D1–D4 below have implementation fixes: persisted completion results,
expanded Divisibility notes, safe lesson formatting, and more varied practice with
actionable hints. Regression checks and the production build pass. The six audit
defects are also repaired. Later live-demo screenshots and recorded Groq usage are
linked in [the completion record](completion-2026-10-27.md). The original offline
walkthrough below remains historical evidence, not a description of current defects.

This was a browser-operated learner demonstration against application revision
`35deead`, not a rerun of the synthetic Playwright suite. The launcher created a
fresh isolated sample database, with the Divisibility goal preselected and no
pre-seeded diagnostic mistakes. Normal content files and the normal database were
not changed. The browser used the real pages and API; no responses were mocked,
answer keys inspected, or results injected during this walkthrough.

AI mode was **offline** throughout. No live Groq or hosted-auth claim follows
from this demonstration. All records, sample publication statuses, answers and
scores are demonstration data, never real learner or review evidence.

## What I actually did

1. Started `python -m scripts.demo serve --sample-content --topic divisibility`.
2. Signed in through the password-style local token field without displaying
   the token. Confirmed the sample-content and offline-AI banner.
3. Read the prerequisite roadmap and chose its Divisibility diagnostic action.
4. Submitted one deliberate wrong answer and seven "I don't know" answers.
   The completed diagnostic correctly showed **0/8** and **Gap**.
5. Opened tutoring through Understand my mistakes. Both panels appeared, with
   fallback source labels. The personal part listed three unknown answers first.
6. Continued into practice. Requested a hint on the first question, then solved
   all ten displayed missing-digit questions. The completion screen showed **10/10**.
7. Returned to the roadmap and opened the topic teaching page. Continued practice,
   solving eight further displayed questions. The adaptive block ended early at
   **8/8** and the roadmap offered an independent retest.
8. Completed all ten retest questions without hints, using arithmetic from the
   visible question text. Correctness feedback was withheld between these typed
   answers. The final screen showed **10/10**, **Retest passed**, and **resolved**.
9. Opened History and reopened the retest. This exposed the result-display defect
   described below.
10. Started a three-question, one-minute Divisibility timed test. Solved the three
    visible questions; it showed **3/3** only after completion. Reloading preserved
    the timed-test result and explanations.
11. Opened Account and the reviewer console, without approving, withdrawing or
    deleting anything. The console's default Draft queue was empty because this
    explicitly labelled demo fixture uses sample publications.
12. Signed out. Confirmed the login page and that Tutor remained unavailable while
    signed out. Signed back in and left the browser on the learner roadmap.

Total: **39 answer submissions** across five completed activities: diagnostic,
two practice blocks, retest and timed practice. The roadmap finally showed
Divisibility **Resolved**, a **93% estimated** score based on **35 scored answers**,
and **Review Oct 30** in its accessible topic description. The hinted answer and
three timed answers do not contribute to that running estimate. These are observed
sample-session values, not learning-effectiveness measurements.

## Issues encountered during the actual demo

### D1 — completed results disappear when reopened from History

Confirmed on the passed retest. Immediately after submission the page showed
"Retest passed. The gap is resolved." and "10 of 10 correct". Reopening that exact
session from History showed only "Session complete." The saved topic still showed
Resolved on the roadmap, so this is a result presentation/retrieval defect, not
loss of the underlying mastery state.

`frontend/app/session/[id]/page.tsx` renders result and counts from the transient
`finished` submission response. On a fresh page visit that state is empty, while
GET session does not provide the completion result needed by that screen. Persisted
evidence and attempts should drive the same result view after reload. Preserve
the validation forms' feedback restrictions when implementing this.

Evidence: [original retest result](demo-evidence-2026-10-27/03-retest-passed.png)
and [same session reopened](demo-evidence-2026-10-27/04-reopened-result-missing.png).

### D2 — lesson coverage does not match the diagnostic/retest coverage

The displayed Divisibility notes explicitly omit the rule for 11 and cover simple
tests/missing digits. Yet this diagnostic asked about divisibility by 11 and
counting unions/coprime integers. The retest additionally included arithmetic
series, factorial trailing zeros and products of consecutive integers. The
personal fallback displayed correct stored answers but no methods for those gaps.

Because the tutor must ground its methods in the notes, enabling Groq alone will
not repair the missing teaching material. Map every assessed question method to
reviewed lesson coverage, expand the notes, or narrow the assessment scope.

### D3 — lesson presentation looks like source text

The learner panel displayed literal Markdown headings such as `# Divisibility`
and "Status: draft. Original material for human review." inside a long unformatted
text block. The banner already communicates sample status, but source metadata
and raw Markdown make the lesson feel unfinished. Render supported headings and
paragraphs safely and keep authoring metadata outside the learner lesson body.
Do not remove the demo banner or imply actual human approval.

Evidence: [topic lesson](demo-evidence-2026-10-27/01-tutor.png).

### D4 — practice variety and hints are weak in this path

All 18 practice questions in this run were variations of the same missing-final-
digit format with divisors 6 or 9. The requested hint was only "Use the divisibility
rule for the stated divisor." This does not prepare the learner for the much
broader retest methods described in D2. The displayed timed explanations likewise
stated the unique digit without showing the actual condition checks.

Broaden reviewed practice by method/facet and write actionable hints and worked
solutions. This is an observation of this run, not a claim that every possible
sample selection has the same composition.

## Evidence and limits

- [Practice completion](demo-evidence-2026-10-27/02-practice-complete.png)
- [Timed-test result](demo-evidence-2026-10-27/05-timed-practice.png)
- [Final resolved roadmap](demo-evidence-2026-10-27/06-resolved-roadmap.png)

Screenshots were captured from the actual demo browser. They show sample data.
The final roadmap screenshot is scrolled below the demo banner; that banner
remained present at the top of the page.

The six defects in [the earlier audit](application-audit-2026-10-27.md) remain
unfixed. The first-goal race was not retested here because the recording launcher
preselects a goal. This walkthrough did not wait until October 30 to execute the
future review, nor test hosted signup, real email, live Groq, account deletion,
multi-user production concurrency or a physical mobile device. No video file was
recorded; the deliverable is the exercised demo, screenshots and these observations.

The demo was left running on `http://127.0.0.1:3001` with the isolated sample
learner signed in. Stop its own child processes using:

```powershell
.venv/Scripts/python.exe -m scripts.demo stop
```
