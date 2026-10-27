import type { ReactNode } from "react";

// A deliberately small Markdown subset. React escapes all content, including HTML.
function inline(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i}>{part.slice(2, -2)}</strong> : part);
}

export default function LessonText({ text }: { text: string }) {
  const blocks: { kind: "heading" | "paragraph" | "ul" | "ol"; lines: string[] }[] = [];
  let separate = true;
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line || /^Status: (draft|approved)\./.test(line)) { separate = true; continue; }
    const heading = line.match(/^(?:#{1,6}\s+(.+)|\*\*([^*]+)\*\*)$/);
    const bullet = line.match(/^[-*]\s+(.+)/);
    const numbered = line.match(/^\d+[.)]\s+(.+)/);
    const kind = heading ? "heading" : bullet ? "ul" : numbered ? "ol" : "paragraph";
    const value = heading ? heading[1] ?? heading[2] : bullet ? bullet[1] : numbered ? numbered[1] : line;
    const last = blocks[blocks.length - 1];
    if (!separate && last?.kind === kind && kind !== "heading") last.lines.push(value);
    else blocks.push({ kind, lines: [value] });
    separate = false;
  }
  return <div className="space-y-3 leading-7">{blocks.map((block, i) => {
    if (block.kind === "heading") return <h3 key={i} className="text-lg font-semibold">{inline(block.lines[0])}</h3>;
    if (block.kind === "ul") return <ul key={i} className="list-disc pl-5">{block.lines.map((line, j) => <li key={j}>{inline(line)}</li>)}</ul>;
    if (block.kind === "ol") return <ol key={i} className="list-decimal pl-5">{block.lines.map((line, j) => <li key={j}>{inline(line)}</li>)}</ol>;
    return <p key={i} className="whitespace-pre-wrap">{inline(block.lines.join("\n"))}</p>;
  })}</div>;
}
