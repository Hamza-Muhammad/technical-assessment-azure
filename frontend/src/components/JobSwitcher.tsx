import { MOCK_JOBS } from "../mocks";

interface JobSwitcherProps {
  jobId: string;
  onChange: (jobId: string) => void;
}

/**
 * Stand-in for whatever upstream queue/list would normally hand the dispatcher a jobId
 * to open (e.g. the manual-review queue). Demo-only affordance to move between the three
 * committed scenarios without a routing layer.
 */
export function JobSwitcher({ jobId, onChange }: JobSwitcherProps) {
  return (
    <label className="flex items-center gap-2 text-xs text-slate-500">
      <span className="font-medium">Sample job</span>
      <select
        value={jobId}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-300"
      >
        {MOCK_JOBS.map((j) => (
          <option key={j.jobId} value={j.jobId} title={j.description}>
            {j.label}
          </option>
        ))}
      </select>
    </label>
  );
}
