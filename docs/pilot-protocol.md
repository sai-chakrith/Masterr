# Pilot protocol (S5)

Draft for agreement by the team in week 5. It covers about 35 placement-prep juniors or
classmates. Every learner does every topic.

## Setup

1. Create one account per learner and list their user ids in learner-ids.txt.
2. Assign versions: each learner gets the new design on half the topics and the current
   design on the other half, chosen at random per learner.

   ```
   python -m scripts.pilot assign learner-ids.txt --seed <agreed seed> --out data/pilot-assignments.csv
   ```

3. Keep the assignment file with the pilot sheet. Do not flip a learner's topic after they start it.

## Per topic, per learner

| Step | What the learner does | In the app |
| --- | --- | --- |
| 1. Pre-test | Form A, 5 hidden questions, no feedback | "Pilot check-in test" before any other work on the topic |
| 2. Learn | Diagnostic, then tutoring or Borderline review, then retest | Normal roadmap |
| 3. Post-test | Form B, right after the topic ends (Mastered or Resolved) | "Pilot check-in test" |
| 4. Delayed test | Form A again, 1-2 weeks later | "Pilot check-in test" (opens after 7 days) |

The app enforces this order. Forms are never followed by answer feedback, hints or solutions,
and their questions never appear anywhere else.

## Survey (after the last topic)

Answer each on a 1-5 scale from "strongly disagree" to "strongly agree".

1. The score Mastrr showed matched how well I really knew each topic.
2. When Mastrr said I had mastered a topic, I trusted it.
3. I used "I don't know" only when I would otherwise have guessed blindly.

## Analysis (week 8)

```
python -m scripts.pilot_analysis --database-url <pilot database> --out docs/pilot-results
```

| Stage | Question | Pass when |
| --- | --- | --- |
| 1 | Does the score predict correctly? | Predicted and actual within about 5 points; learning curves fall smoothly |
| 2 | Do the labels hold up? | Mastered and Resolved groups score about 75%+ on the delayed test; Gap groups clearly lower |
| 3 | Do learners learn more? | New design ahead by 0.3-0.5 standard deviations in normalised gain |

Also track drop-off per version, "I don't know" usage, time per topic and the survey.

Reading the results: Stage 1 fails, fix tags or scoring first. Stage 2 fails, cut-offs or retest
are too loose. Stages 1-2 pass but Stage 3 does not, measurement is fine and tutoring is the
problem.

## Before the pilot can start

- The draft bank must be reviewed and approved; the app serves only approved questions.
- Supabase Auth must be configured for real accounts.
- Name the pilot group and dates now; recruiting takes longer than coding.
