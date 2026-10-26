# Personalised learning pilot protocol

Draft for agreement before recruitment. It covers about 35 placement-prep learners. Every
learner receives both practice conditions across the selected topics. The same new scoring
policy must be used in both conditions so the practice comparison is not confounded by the
scoring upgrade.

## Setup

1. Create one account per learner and list their user ids in learner-ids.txt.
2. After agreeing the pilot topic list and reviewing the content, assign the same scoring
   version to all pilot topics and split each learner's topics between personalised and fixed
   practice using the independent strategy assignment:

   ```
   python -m scripts.pilot assign-practice learner-ids.txt --skills <topic-ids...> \
     --seed <agreed seed> --scoring-version new --out data/pilot-practice-assignments.csv
   ```

3. Keep the assignment file with the pilot sheet. Do not flip a learner's topic after they start it.

## Per topic, per learner

| Step | What the learner does | In the app |
| --- | --- | --- |
| 1. Pre-test | Form A, 5 hidden questions, no feedback | "Pilot check-in test" before any other work on the topic |
| 2. Learn | Diagnostic, then tutoring or Borderline review, then retest | Normal roadmap |
| 3. Post-test | Form B, right after the topic ends (Mastered or Resolved) | "Pilot check-in test" |
| 4. Delayed test | Form A again, 2 weeks later | "Pilot check-in test" (opens after 14 days) |

The app enforces test order. Forms are never followed by answer feedback, hints or solutions,
and their questions never appear anywhere else.

## Survey (after the last topic)

Answer each on a 1-5 scale from "strongly disagree" to "strongly agree".

1. The score Mastrr showed matched how well I really knew each topic.
2. When Mastrr said I had mastered a topic, I trusted it.
3. I used "I don't know" only when I would otherwise have guessed blindly.

## Analysis (during and after the pilot)

```
python -m scripts.pilot_analysis --database-url <pilot database> --out docs/pilot-results
python -m scripts.personalisation_analysis --database-url <pilot database> --out docs/personalisation-results
```

| Stage | Question | Pass when |
| --- | --- | --- |
| 1 | Does the score predict correctly? | Predicted and actual within about 5 points; learning curves fall smoothly |
| 2 | Do the labels hold up? | Mastered and Resolved groups score about 75%+ on the delayed test; Gap groups clearly lower |
| 3 | Do learners learn more? | Personalised topics ahead of fixed topics by the pre-agreed effect target in normalised gain |

Also track drop-off per version, "I don't know" usage, time per topic and the survey.

The personalisation report groups Form A/Form B gain by the independently assigned practice
strategy and pairs conditions within each learner. It is a descriptive estimate; with about
35 learners, do not treat the target effect or a p-value as guaranteed evidence. Report the
number of complete learner-topic pairs, delayed scores, practice answers and minutes for each
condition, plus missingness and assignment balance. Agree the effect threshold and analysis
before looking at pilot outcomes.

Reading the results: Stage 1 fails, fix tags or scoring first. Stage 2 fails, cut-offs or retest
are too loose. Stages 1-2 pass but Stage 3 does not, measurement is fine and tutoring is the
problem.

## Before the pilot can start

- The draft bank must be reviewed and approved; the app serves only approved questions.
- Export the full review sheet with `scripts.question_bank export`, edit and validate content
  with `apply-content`, then record each human approval using `apply-review` and its reviewer/date.
- The ten pilot topics are now in the curriculum: Number Systems (`integer-properties`),
  Percentages, Profit & Loss, Simple Interest, Compound Interest, Ratio & Proportion,
  Averages, Mixtures & Alligations, Partnership, and Time & Work. The nine new topics have
  generated draft assessment pools; the existing Number Systems pool is reused. All ten have
  generated practice drafts and tagged draft distractors; 40 misconception definitions are
  available for review. None of this content is approved yet. Review question options with
  `scripts.question_bank export` and misconception copy with `scripts.misconception_review export`
  before running this protocol. `assign-practice` defaults to these ten topics when `--skills`
  is omitted. Its report still needs an end-to-end dry run against the reviewed bank and roster.
  The existing scoring analysis remains for the earlier scoring-version pilot.
- Supabase Auth must be configured for real accounts.
- Name the pilot group and dates now; recruiting takes longer than coding.
