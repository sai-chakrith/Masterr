import Link from "next/link";
import type { Roadmap } from "@/lib/api";

type RouteNode = Roadmap["nodes"][number];

const NODE_WIDTH = 250;
const NODE_HEIGHT = 118;
const COLUMN_GAP = 74;
const ROW_GAP = 22;
const PADDING = 24;

function statusColor(status: string) {
  if (status === "mastered" || status === "resolved") return { fill: "#ecfdf5", stroke: "#059669", text: "#065f46" };
  if (status === "gap") return { fill: "#fff1f2", stroke: "#e11d48", text: "#9f1239" };
  if (status === "borderline") return { fill: "#fffbeb", stroke: "#d97706", text: "#92400e" };
  return { fill: "#f8fafc", stroke: "#64748b", text: "#334155" };
}

function statusLabel(status: string) {
  return status === "unassessed" ? "Not checked yet" : status[0].toUpperCase() + status.slice(1);
}

function shortDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function SkillRouteGraph({ nodes }: { nodes: RouteNode[] }) {
  const byId = new Map(nodes.map((node) => [node.skill_id, node]));
  const depthById = new Map<string, number>();

  // API route nodes are returned in prerequisite order. Each topic is placed in
  // the next column after its deepest prerequisite, keeping the drawing stable.
  for (const node of nodes) {
    const prerequisiteDepths = node.prerequisites
      .map((id) => depthById.get(id))
      .filter((depth): depth is number => depth !== undefined);
    depthById.set(node.skill_id, prerequisiteDepths.length ? Math.max(...prerequisiteDepths) + 1 : 0);
  }

  const columns = new Map<number, RouteNode[]>();
  for (const node of nodes) {
    const depth = depthById.get(node.skill_id) ?? 0;
    columns.set(depth, [...(columns.get(depth) ?? []), node]);
  }

  const positions = new Map<string, { x: number; y: number }>();
  for (const [depth, column] of columns) {
    column.forEach((node, row) => positions.set(node.skill_id, {
      x: PADDING + depth * (NODE_WIDTH + COLUMN_GAP),
      y: PADDING + row * (NODE_HEIGHT + ROW_GAP),
    }));
  }

  const maxDepth = Math.max(0, ...columns.keys());
  const maxRows = Math.max(1, ...[...columns.values()].map((column) => column.length));
  const width = PADDING * 2 + maxDepth * (NODE_WIDTH + COLUMN_GAP) + NODE_WIDTH;
  const height = PADDING * 2 + maxRows * NODE_HEIGHT + (maxRows - 1) * ROW_GAP;
  const edges = nodes.flatMap((node) => node.prerequisites.flatMap((prerequisiteId) => {
    const source = positions.get(prerequisiteId);
    const target = positions.get(node.skill_id);
    if (!source || !target || !byId.has(prerequisiteId)) return [];
    const x1 = source.x + NODE_WIDTH;
    const y1 = source.y + NODE_HEIGHT / 2;
    const x2 = target.x;
    const y2 = target.y + NODE_HEIGHT / 2;
    const bend = Math.max(24, (x2 - x1) / 2);
    return [{ id: `${prerequisiteId}-${node.skill_id}`, path: `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}` }];
  }));

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 p-2 dark:border-slate-800 dark:bg-slate-950" role="region" aria-label="Prerequisite graph for your study route">
      <div className="relative" style={{ width, height }}>
        <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} className="absolute inset-0" aria-hidden="true">
          <defs>
            <marker id="route-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
          </defs>
          <g fill="none" stroke="#94a3b8" strokeWidth="2" markerEnd="url(#route-arrow)">
            {edges.map((edge) => <path key={edge.id} d={edge.path} />)}
          </g>
        </svg>
        {nodes.map((node) => {
          const position = positions.get(node.skill_id);
          if (!position) return null;
          const color = statusColor(node.status);
          const details = [
            node.score === null ? "No score yet" : `${Math.round(node.score * 100)}% estimated`,
            `Based on ${node.answer_count} answers`,
            node.next_review_at ? `Review ${shortDate(node.next_review_at)}` : null,
          ].filter(Boolean).join(" · ");
          return (
            <Link
              key={node.skill_id}
              href={`/learn/${encodeURIComponent(node.skill_id)}`}
              aria-label={`${node.title}. ${statusLabel(node.status)}. ${details}. Practice target ${Math.round(node.mastery_bar * 100)} percent.`}
              className="absolute z-10 block overflow-hidden rounded-xl border-2 bg-white p-3 text-left shadow-sm outline-none transition hover:shadow-md focus-visible:ring-4 focus-visible:ring-sky-500 dark:bg-slate-900"
              style={{ left: position.x, top: position.y, width: NODE_WIDTH, height: NODE_HEIGHT, borderColor: color.stroke, color: "inherit" }}
            >
              <span className="block truncate text-sm font-semibold">{node.title}</span>
              <span className="mt-1 block text-xs font-medium" style={{ color: color.text }}>{statusLabel(node.status)}</span>
              <span className="mt-1 block truncate text-[11px] text-slate-600 dark:text-slate-300">{details}</span>
              <span className="mt-1 block text-[11px] text-slate-500">Target {Math.round(node.mastery_bar * 100)}%{!node.available ? " · Content in review" : " · Open topic"}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
