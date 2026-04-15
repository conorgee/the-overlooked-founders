import { programWeeks } from "../../data/program-weeks";

export function ProgressTracker() {
  const completed = programWeeks.filter((w) => w.status === "completed").length;
  const total = programWeeks.length;
  const percent = Math.round((completed / total) * 100);

  return (
    <div className="mb-12">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs uppercase tracking-[0.15em] text-text-muted">
          Programme Progress
        </span>
        <span className="text-xs uppercase tracking-[0.15em] text-white font-medium">
          {completed}/{total} weeks
        </span>
      </div>
      <div className="h-px bg-white/10 overflow-hidden">
        <div
          className="h-full bg-white transition-all duration-700"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
