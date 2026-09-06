const FILL_CLASSES: Record<string, string> = {
  violet: "bg-violet-500",
  slate: "bg-slate-400",
  emerald: "bg-emerald-500",
  amber: "bg-amber-500",
  rose: "bg-rose-500",
};

interface MeterBarProps {
  label: string;
  /** 0-1 */
  value: number;
  valueLabel: string;
  tone?: keyof typeof FILL_CLASSES;
  title?: string;
}

/** A single labeled inline meter — the atomic unit of the score breakdown display. */
export function MeterBar({ label, value, valueLabel, tone = "violet", title }: MeterBarProps) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2" title={title}>
      <span className="w-9 shrink-0 text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full ${FILL_CLASSES[tone]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-9 shrink-0 text-right text-xs font-semibold tabular-nums text-slate-600">{valueLabel}</span>
    </div>
  );
}
