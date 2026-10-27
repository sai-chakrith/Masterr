import type { GapStatus, Topic } from "./api";

// One place for the roadmap's states, colours and wording (C4).
export const STATUS: Record<GapStatus, { label: string; node: string; chip: string; blurb: string }> = {
  unassessed: {
    label: "Not assessed",
    node: "bg-slate-300 dark:bg-slate-600",
    chip: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
    blurb: "Take the diagnostic to find your starting point.",
  },
  gap: {
    label: "Gap",
    node: "bg-rose-500",
    chip: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
    blurb: "Practise this topic, then take the retest.",
  },
  borderline: {
    label: "Borderline",
    node: "bg-amber-400",
    chip: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
    blurb: "Close to the bar. Review the questions you missed, then take the retest.",
  },
  mastered: {
    label: "Mastered",
    node: "bg-emerald-500",
    chip: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
    blurb: "You passed the diagnostic above the mastery line.",
  },
  resolved: {
    label: "Resolved",
    node: "bg-teal-500",
    chip: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
    blurb: "You passed the retest. New independent answers can reopen it.",
  },
};

export function scoreLine(topic: Topic): string | null {
  if (topic.scoring_version !== "new") return null;
  if (topic.score_withheld) return "Score hidden until this test ends";
  if (topic.score === null) return "No answers yet";
  const plural = topic.answer_count === 1 ? "answer" : "answers";
  return `${Math.round(topic.score * 100)}% · based on ${topic.answer_count} ${plural}`;
}

export const DONT_KNOW_WORDING = "Only use this if you'd be guessing blindly. It won't help your score.";

export function sessionTitle(policy: string, stage: string | null): string {
  if (policy === "topic-retest-v1" || policy === "legacy-retest-v0") return "Retest";
  if (policy === "validation-form-v1") return `Check-in test (${stage ?? "pilot"})`;
  if (policy.includes("diagnostic")) return "Diagnostic";
  return "Practice";
}

export function resultText(result: string | undefined, decision: string | undefined): string {
  if (decision === "mastered") return "Diagnostic finished: Mastered.";
  if (decision === "borderline") return "Diagnostic finished: Borderline. Review your missed questions, then take the retest.";
  if (decision === "gap") return "Diagnostic finished: this topic is a Gap. Practise it, then take the retest.";
  switch (result) {
    case "independent_check_passed":
      return "Independent check passed.";
    case "later_check_passed":
      return "Review passed.";
    case "practice_needed":
      return "More practice is needed before the next independent check.";
    case "practice_completed":
      return "Practice complete.";
    case "retest_passed":
      return "Retest passed. The gap is resolved.";
    case "retest_practice_needed":
      return "Retest not passed yet. More practice will help before the next attempt.";
    case "validation_completed":
      return "Check-in test saved. Thank you. Results are not shown for these tests.";
    case "assisted_practice":
      return "Saved as assisted practice.";
    default:
      return "Session complete.";
  }
}
