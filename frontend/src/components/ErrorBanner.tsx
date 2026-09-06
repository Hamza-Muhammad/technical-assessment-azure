import { Button } from "./ui/Button";

export function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-5">
      <div>
        <p className="text-sm font-semibold text-rose-900">Couldn't load this job</p>
        <p className="mt-0.5 text-xs text-rose-700">{message}</p>
      </div>
      <Button variant="secondary" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
