import type { AssignmentResponse, OverrideReasonCode, VendorProfile } from "../types/contracts";
import { formatDateTime, titleCase } from "../lib/format";

interface ConfirmationBannerProps {
  response: AssignmentResponse;
  isOverride: boolean;
  reasonCode?: OverrideReasonCode;
  vendors: Record<string, VendorProfile>;
  onDismiss: () => void;
}

export function ConfirmationBanner({ response, isOverride, reasonCode, vendors, onDismiss }: ConfirmationBannerProps) {
  const vendorName = vendors[response.selectedVendorId]?.displayName ?? response.selectedVendorId;

  return (
    <div className="animate-rise-in rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex gap-3">
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-white">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
                clipRule="evenodd"
              />
            </svg>
          </span>
          <div>
            <p className="text-sm font-semibold text-emerald-900">
              {isOverride ? "Override confirmed" : "Recommendation accepted"} — {vendorName} assigned
            </p>
            <p className="mt-0.5 text-xs text-emerald-800">
              {titleCase(response.assignmentSource)} · {formatDateTime(response.assignedAtUtc)} · correlation {response.correlationId}
              {isOverride && (reasonCode ?? response.overrideReasonCode) && <> · reason: {reasonCode ?? response.overrideReasonCode}</>}
            </p>
          </div>
        </div>
        <button onClick={onDismiss} className="shrink-0 text-xs font-medium text-emerald-700 hover:text-emerald-900">
          Dismiss
        </button>
      </div>

    </div>
  );
}
