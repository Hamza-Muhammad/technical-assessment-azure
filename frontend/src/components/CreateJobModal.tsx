import { type FormEvent, type ReactNode, useState } from "react";
import type { JobEventData, JobPriority, RiskTier, SlaSensitivity, TradeCategory } from "../types/contracts";
import { apiClient } from "../api/client";
import { MOCK_JOBS } from "../mocks";
import { Button } from "./ui/Button";

interface CreateJobModalProps {
  onCreated: (jobId: string) => void;
  onClose: () => void;
}

interface FormState {
  jobId: string;
  customerId: string;
  accountTier: string;
  siteId: string;
  lat: string;
  lon: string;
  addressRef: string;
  timezone: string;
  tradeCategory: TradeCategory;
  priority: JobPriority;
  requiresCertification: string;
  requiresEquipment: string;
  estimatedLabourHours: string;
  notToExceedUsd: string;
  isRecall: boolean;
  responseDueUtc: string;
  resolutionDueUtc: string;
  sensitivity: SlaSensitivity;
  breachPenaltyUsd: string;
  riskTier: RiskTier;
  safetyRisk: boolean;
  revenueAtRiskUsd: string;
  excludedVendorIds: string;
}

function localDateValue(value: string) {
  return value ? new Date(value).toISOString().slice(0, 16) : "";
}

function formFromData(jobId: string, data: JobEventData): FormState {
  return {
    jobId,
    customerId: data.customerId,
    accountTier: data.accountTier,
    siteId: data.site.siteId,
    lat: String(data.site.geo.lat),
    lon: String(data.site.geo.lon),
    addressRef: data.site.addressRef,
    timezone: data.site.timezone,
    tradeCategory: data.job.tradeCategory,
    priority: data.job.priority,
    requiresCertification: data.job.requiresCertification.join(", "),
    requiresEquipment: data.job.requiresEquipment.join(", "),
    estimatedLabourHours: String(data.job.estimatedLabourHours),
    notToExceedUsd: String(data.job.notToExceedUsd),
    isRecall: data.job.isRecall,
    responseDueUtc: localDateValue(data.sla.responseDueUtc),
    resolutionDueUtc: localDateValue(data.sla.resolutionDueUtc),
    sensitivity: data.sla.sensitivity,
    breachPenaltyUsd: String(data.sla.breachPenaltyUsd),
    riskTier: data.risk.riskTier,
    safetyRisk: data.risk.safetyRisk,
    revenueAtRiskUsd: String(data.risk.revenueAtRiskUsd),
    excludedVendorIds: data.dispatch.excludedVendorIds.join(", "),
  };
}

const sampleTemplates: { label: string; data: JobEventData }[] = [
  ...MOCK_JOBS.map((sample) => ({ label: sample.label, data: sample.data.job.data })),
  {
    label: "Sample 004 - P2 electrical service",
    data: {
      ...MOCK_JOBS[0].data.job.data,
      customerId: "CUST-SAMPLE-004",
      site: { ...MOCK_JOBS[0].data.job.data.site, siteId: "SITE-SAMPLE-004", geo: { lat: 41.9, lon: -87.8 } },
      job: { ...MOCK_JOBS[0].data.job.data.job, tradeCategory: "ELECTRICAL", priority: "P2", isRecall: false },
      risk: { ...MOCK_JOBS[0].data.job.data.risk, riskTier: "MEDIUM", safetyRisk: false },
    },
  },
  {
    label: "Sample 006 - P1 plumbing emergency",
    data: {
      ...MOCK_JOBS[1].data.job.data,
      customerId: "CUST-SAMPLE-006",
      site: { ...MOCK_JOBS[1].data.job.data.site, siteId: "SITE-SAMPLE-006", geo: { lat: 41.88, lon: -87.65 } },
      job: { ...MOCK_JOBS[1].data.job.data.job, tradeCategory: "PLUMBING", priority: "P1" },
    },
  },
];

function listValue(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function isoValue(value: string) {
  return value ? new Date(value).toISOString() : "";
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="text-xs font-semibold text-slate-600">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate-400">{hint}</span>}
    </label>
  );
}

const inputClass = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-200";

export function CreateJobModal({ onCreated, onClose }: CreateJobModalProps) {
  const [templateIndex, setTemplateIndex] = useState(0);
  const [form, setForm] = useState(() => formFromData("JOB-TEST-001", sampleTemplates[0].data));
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function update(name: keyof FormState, value: string | boolean) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function chooseTemplate(index: number) {
    setTemplateIndex(index);
    setForm(formFromData(`JOB-TEST-${String(index + 1).padStart(3, "0")}`, sampleTemplates[index].data));
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!form.customerId || !form.siteId || !form.tradeCategory) {
      setError("Customer, site, and trade category are required.");
      return;
    }
    const numbers = [form.lat, form.lon, form.estimatedLabourHours, form.notToExceedUsd, form.breachPenaltyUsd, form.revenueAtRiskUsd];
    if (numbers.some((value) => value === "" || !Number.isFinite(Number(value)))) {
      setError("Location and financial fields must contain valid numbers.");
      return;
    }
    if (!form.responseDueUtc || !form.resolutionDueUtc) {
      setError("Response and resolution due dates are required.");
      return;
    }
    setSubmitting(true);
    try {
      const data: JobEventData = {
        customerId: form.customerId,
        accountTier: form.accountTier,
        site: {
          siteId: form.siteId,
          geo: { lat: Number(form.lat), lon: Number(form.lon) },
          addressRef: form.addressRef,
          timezone: form.timezone,
        },
        job: {
          tradeCategory: form.tradeCategory,
          priority: form.priority,
          requiresCertification: listValue(form.requiresCertification),
          requiresEquipment: listValue(form.requiresEquipment),
          estimatedLabourHours: Number(form.estimatedLabourHours),
          notToExceedUsd: Number(form.notToExceedUsd),
          isRecall: form.isRecall,
        },
        sla: {
          responseDueUtc: isoValue(form.responseDueUtc),
          resolutionDueUtc: isoValue(form.resolutionDueUtc),
          sensitivity: form.sensitivity,
          breachPenaltyUsd: Number(form.breachPenaltyUsd),
        },
        risk: {
          riskTier: form.riskTier,
          safetyRisk: form.safetyRisk,
          revenueAtRiskUsd: Number(form.revenueAtRiskUsd),
        },
        dispatch: {
          excludedVendorIds: listValue(form.excludedVendorIds),
          allowAutoAssign: true,
        },
      };
      const response = await apiClient.createJob({ jobId: form.jobId.trim(), data });
      onCreated(response.jobId);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the job.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/45 px-4 py-8" role="dialog" aria-modal="true" aria-labelledby="create-job-title">
      <form onSubmit={submit} className="w-full max-w-4xl rounded-2xl bg-white shadow-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 px-6 py-5">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-widest text-violet-500">Intake</p>
            <h2 id="create-job-title" className="mt-1 text-xl font-bold text-slate-900">Create dispatch job</h2>
            <p className="mt-1 text-sm text-slate-500">The job will be queued and scored asynchronously by Azure Durable Functions.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-xl text-slate-400 hover:bg-slate-100" aria-label="Close">×</button>
        </div>

        <div className="grid gap-6 px-6 py-6 md:grid-cols-2">
          <section className="space-y-3 md:col-span-2 rounded-xl bg-violet-50 p-4">
            <div className="grid gap-3 md:grid-cols-[1fr_1fr]">
              <Field label="Sample job template">
                <select className={inputClass} value={templateIndex} onChange={(e) => chooseTemplate(Number(e.target.value))}>
                  {sampleTemplates.map((sample, index) => <option key={sample.label} value={index}>{sample.label}</option>)}
                </select>
              </Field>
              <Field label="Job ID" hint="Use a new ID for every test run so Durable starts a new instance.">
                <input className={inputClass} value={form.jobId} onChange={(e) => update("jobId", e.target.value)} required />
              </Field>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-bold text-slate-800">Customer and site</h3>
            <Field label="Customer ID"><input className={inputClass} value={form.customerId} onChange={(e) => update("customerId", e.target.value)} required /></Field>
            <Field label="Account tier"><input className={inputClass} value={form.accountTier} onChange={(e) => update("accountTier", e.target.value)} /></Field>
            <Field label="Site ID"><input className={inputClass} value={form.siteId} onChange={(e) => update("siteId", e.target.value)} required /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Latitude"><input className={inputClass} type="number" step="any" value={form.lat} onChange={(e) => update("lat", e.target.value)} required /></Field>
              <Field label="Longitude"><input className={inputClass} type="number" step="any" value={form.lon} onChange={(e) => update("lon", e.target.value)} required /></Field>
            </div>
            <Field label="Address reference" hint="Use a PII token, not a street address."><input className={inputClass} value={form.addressRef} onChange={(e) => update("addressRef", e.target.value)} required /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Timezone"><input className={inputClass} value={form.timezone} onChange={(e) => update("timezone", e.target.value)} required /></Field>
              <Field label="Trade category"><select className={inputClass} value={form.tradeCategory} onChange={(e) => update("tradeCategory", e.target.value as TradeCategory)} required>
                <option value="HVAC">HVAC</option>
                <option value="PLUMBING">Plumbing</option>
                <option value="ELECTRICAL">Electrical</option>
                <option value="REFRIGERATION">Refrigeration</option>
                <option value="ELEVATOR">Elevator</option>
              </select></Field>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-bold text-slate-800">Work and dispatch</h3>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Priority"><select className={inputClass} value={form.priority} onChange={(e) => update("priority", e.target.value)}><option>P1</option><option>P2</option><option>P3</option></select></Field>
              <Field label="Risk tier"><select className={inputClass} value={form.riskTier} onChange={(e) => update("riskTier", e.target.value)}><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select></Field>
            </div>
            <Field label="Required certifications" hint="Comma-separated codes"><input className={inputClass} value={form.requiresCertification} onChange={(e) => update("requiresCertification", e.target.value)} /></Field>
            <Field label="Required equipment" hint="Comma-separated codes"><input className={inputClass} value={form.requiresEquipment} onChange={(e) => update("requiresEquipment", e.target.value)} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Labour hours"><input className={inputClass} type="number" min="0" step="0.1" value={form.estimatedLabourHours} onChange={(e) => update("estimatedLabourHours", e.target.value)} required /></Field>
              <Field label="Not-to-exceed USD"><input className={inputClass} type="number" min="0" step="0.01" value={form.notToExceedUsd} onChange={(e) => update("notToExceedUsd", e.target.value)} required /></Field>
            </div>
            <Field label="Excluded vendor IDs" hint="Comma-separated IDs"><input className={inputClass} value={form.excludedVendorIds} onChange={(e) => update("excludedVendorIds", e.target.value)} /></Field>
            <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.isRecall} onChange={(e) => update("isRecall", e.target.checked)} /> Recall job</label>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-bold text-slate-800">SLA</h3>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Response due"><input className={inputClass} type="datetime-local" value={form.responseDueUtc} onChange={(e) => update("responseDueUtc", e.target.value)} required /></Field>
              <Field label="Resolution due"><input className={inputClass} type="datetime-local" value={form.resolutionDueUtc} onChange={(e) => update("resolutionDueUtc", e.target.value)} required /></Field>
            </div>
            <Field label="Sensitivity"><select className={inputClass} value={form.sensitivity} onChange={(e) => update("sensitivity", e.target.value)}><option>ROUTINE</option><option>ELEVATED</option><option>CRITICAL</option></select></Field>
            <Field label="Breach penalty USD"><input className={inputClass} type="number" min="0" step="0.01" value={form.breachPenaltyUsd} onChange={(e) => update("breachPenaltyUsd", e.target.value)} required /></Field>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-bold text-slate-800">Risk</h3>
            <Field label="Revenue at risk USD"><input className={inputClass} type="number" min="0" step="0.01" value={form.revenueAtRiskUsd} onChange={(e) => update("revenueAtRiskUsd", e.target.value)} required /></Field>
            <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={form.safetyRisk} onChange={(e) => update("safetyRisk", e.target.checked)} /> Safety risk present</label>
          </section>
        </div>

        {error && <p className="mx-6 mb-4 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        <div className="flex justify-end gap-3 border-t border-slate-200 px-6 py-4">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={submitting}>Create and score job</Button>
        </div>
      </form>
    </div>
  );
}
