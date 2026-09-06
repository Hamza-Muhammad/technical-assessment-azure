"""
The framework-free scoring pipeline: score_job(job, vendors, config) ->
ScoreFactors (as a plain dict, matching contracts/models.py exactly).

Stage 1 eligibility -> Stage 2 rule score -> Stage 3 ML uplift (best
effort, degrades cleanly) -> Stage 4 blend + confidence -> gates ->
rationale. No Azure Functions/FastAPI/event-bus imports here - this
module is called identically from the local HTTP API, the Durable
activity, and every test.
"""
from __future__ import annotations

import time
import uuid
import logging
from datetime import datetime, timezone

from domain import blend, factor_builder, gates, rationale
from domain.derived import build_derived_features
from domain.eligibility import filter_eligible
from domain.model_registry import SchemaHashMismatchError, load_model, resolve_version
from domain.ml_uplift import score_vendor as ml_score_vendor
from domain.redact import redact_for_model
from domain.rule_score import rule_score
from domain.counterfactual import build_counterfactual

TOP_N = 5
_logger = logging.getLogger("retailfixit.scoring")


def _log(level: int, message: str, **dimensions) -> None:
    _logger.log(level, message, extra={"custom_dimensions": dimensions})


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expected_cost(job: dict, vendor: dict, final_score: float) -> tuple[float, float]:
    ntee = job["data"]["job"]["notToExceedUsd"]
    p50 = round(ntee * vendor["performance"]["costIndex"] * 0.55, 2)
    p90 = round(p50 * 1.4, 2)
    return p50, p90


def score_job(
    job: dict,
    vendors: list[dict],
    config: dict,
    model_alias: str = "production",
    force_ml_unavailable: bool = False,
) -> dict:
    start = time.perf_counter()
    scoring_run_id = f"SCR-{uuid.uuid4().hex[:17].upper()}"
    job_id = job.get("jobId")
    _log(logging.INFO, "scoring_started", jobId=job_id, scoringRunId=scoring_run_id,
         vendorCount=len(vendors), modelAlias=model_alias, forceMlUnavailable=force_ml_unavailable)

    eligible, exclusions = filter_eligible(job, vendors)
    candidate_summary = {
        "vendorsInNetwork": len(vendors),
        "afterHardFilter": len(eligible),
        "exclusions": exclusions,
    }
    _log(logging.INFO, "eligibility_completed", jobId=job_id, scoringRunId=scoring_run_id,
         vendorCount=len(vendors), eligibleCount=len(eligible), exclusionCount=len(exclusions))

    model = None
    degraded_reason = None
    if force_ml_unavailable:
        degraded_reason = "ML_ENDPOINT_UNAVAILABLE"
        _log(logging.WARNING, "ml_scoring_disabled", jobId=job_id, scoringRunId=scoring_run_id,
             reason=degraded_reason)
    else:
        try:
            model_version = resolve_version(model_alias)
            _log(logging.INFO, "ml_model_load_started", jobId=job_id, scoringRunId=scoring_run_id,
                 modelAlias=model_alias, modelVersion=model_version)
            model = load_model(model_version)
            _log(logging.INFO, "ml_model_loaded", jobId=job_id, scoringRunId=scoring_run_id,
                 modelVersion=model.version, featureCount=len(model.feature_spec.get("features", [])))
        except (SchemaHashMismatchError, FileNotFoundError, KeyError) as exc:
            degraded_reason = f"ML_MODEL_LOAD_FAILED: {exc}"
            _log(logging.WARNING, "ml_model_load_degraded", jobId=job_id, scoringRunId=scoring_run_id,
                 errorType=type(exc).__name__, reason=degraded_reason)

    scoring_mode = "RULES_PLUS_ML" if model is not None else "RULES_ONLY"
    ml_trust_factor = config["mlTrustFactor"] if model is not None else 0.0

    if not eligible:
        _log(logging.WARNING, "scoring_completed_without_candidates", jobId=job_id,
             scoringRunId=scoring_run_id, scoringMode=scoring_mode, degradedReason=degraded_reason)
        return _empty_result(scoring_run_id, job, config, candidate_summary, scoring_mode, ml_trust_factor,
                              degraded_reason or "NO_ELIGIBLE_VENDORS", start)

    scored = []
    for vendor in eligible:
        vendor_start = time.perf_counter()
        vendor_id = vendor.get("vendorId")
        _log(logging.INFO, "vendor_scoring_started", jobId=job_id, scoringRunId=scoring_run_id,
             vendorId=vendor_id, mlEnabled=model is not None)
        rule_pts, distance_km = rule_score(job, vendor, config)
        derived = build_derived_features(job, vendor, distance_km)

        ml_pts = None
        shap_by_feature = None
        features = None
        if model is not None:
            features = redact_for_model(job, vendor, derived)
            try:
                ml_pts, shap_by_feature = ml_score_vendor(features, model)
            except Exception as exc:  # per-vendor ML failure still degrades gracefully
                ml_pts, shap_by_feature = None, None
                if degraded_reason is None:
                    degraded_reason = f"ML_INFERENCE_FAILED: {exc}"
                _logger.exception("ml_inference_failed", extra={"custom_dimensions": {
                    "jobId": job_id, "scoringRunId": scoring_run_id, "vendorId": vendor_id,
                    "errorType": type(exc).__name__, "reason": degraded_reason,
                }})
            else:
                _log(logging.INFO, "vendor_ml_score_completed", jobId=job_id, scoringRunId=scoring_run_id,
                     vendorId=vendor_id, mlScore=ml_pts)

        final_score, w = blend.blend_scores(rule_pts, ml_pts, ml_trust_factor, config)
        guardrail = config["afterHoursGuardrailPct"] if derived["isAfterHours"] else 0.0
        final_score = round(final_score + guardrail, 2)

        if shap_by_feature is not None:
            factors = factor_builder.build_ml_factors(shap_by_feature, features, vendor, config)
        else:
            factors = factor_builder.build_rule_only_factors(job, vendor, distance_km, derived["isAfterHours"], config)
        _log(logging.INFO, "vendor_explanation_completed", jobId=job_id, scoringRunId=scoring_run_id,
             vendorId=vendor_id, factorCount=len(factors))

        p50, p90 = _expected_cost(job, vendor, final_score)
        predictions = {
            "pSlaMet": {"value": round(0.5 * vendor["performance"]["slaHitRate"] + 0.5 * final_score / 100, 3)},
            "pFirstTimeFix": {"value": round(0.5 * vendor["performance"]["firstTimeFixRate"] + 0.5 * final_score / 100, 3)},
            "pAcceptWithin15m": {"value": round(vendor["performance"]["acceptanceRate"], 3)},
            "expectedCostUsd": {"p50": p50, "p90": p90},
        }

        scored.append({
            "vendor": vendor,
            "ruleScore": rule_pts,
            "mlScore": ml_pts,
            "finalScore": final_score,
            "factors": factors,
            "predictions": predictions,
        })
        _log(logging.INFO, "vendor_scoring_completed", jobId=job_id, scoringRunId=scoring_run_id,
             vendorId=vendor_id, ruleScore=rule_pts, mlScore=ml_pts, finalScore=final_score,
             durationMs=round((time.perf_counter() - vendor_start) * 1000, 1))

    # Confidence compares each vendor's rule score and ML score to the
    # *whole eligible candidate pool* for this job (percentile agreement),
    # so it needs the full population - computed in a second pass.
    rule_population = [s["ruleScore"] for s in scored]
    ml_population = [s["mlScore"] for s in scored if s["mlScore"] is not None]
    for s in scored:
        confidence = blend.compute_confidence(
            s["ruleScore"], s["mlScore"], scoring_mode, s["vendor"]["performance"]["dataSufficiency"],
            ml_trust_factor, rule_population, ml_population,
        )
        s["confidence"] = confidence
        s["confidenceBand"] = blend.confidence_band(confidence, config)

    scored.sort(key=lambda s: -s["finalScore"])
    top = scored[:TOP_N]
    score_list = [(s["vendor"]["vendorId"], s["finalScore"]) for s in top]

    ranked = []
    for i, s in enumerate(top):
        rank = i + 1

        automation_eligible, blocking_gates = gates.evaluate_gates(
            job=job,
            confidence_band=s["confidenceBand"],
        )

        rationale_block = rationale.generate_rationale(
            rank, len(eligible), s["factors"], s["vendor"]["displayName"], config
        )

        ranked.append({
            "rank": rank,
            "vendorId": s["vendor"]["vendorId"],
            "finalScore": s["finalScore"],
            "ruleScore": s["ruleScore"],
            "mlScore": s["mlScore"],
            "confidence": s["confidence"],
            "confidenceBand": s["confidenceBand"],
            "predictions": s["predictions"],
            "factors": s["factors"],
            "counterfactual": build_counterfactual(rank, score_list),
            "rationale": rationale_block,
            "automationEligible": automation_eligible,
            "blockingGates": blocking_gates,
        })

    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    _log(logging.INFO, "scoring_completed", jobId=job_id, scoringRunId=scoring_run_id,
         scoringMode=scoring_mode, modelVersion=model.version if model else None,
         eligibleCount=len(eligible), rankedCount=len(ranked), topVendorId=ranked[0]["vendorId"] if ranked else None,
         automationEligible=ranked[0]["automationEligible"] if ranked else None,
         degradedReason=degraded_reason, latencyMs=latency_ms)
    return {
        "scoringRunId": scoring_run_id,
        "jobId": job["jobId"],
        "generatedAtUtc": _now_iso(),
        "latencyMs": latency_ms,
        "binding": {
            "rulesetVersion": config["rulesetVersion"],
            "modelName": model.metadata["modelName"] if model else None,
            "modelVersion": model.version if model else None,
            "scoringMode": scoring_mode,
            "mlTrustFactor": ml_trust_factor,
            "degradedReason": degraded_reason,
        },
        "candidateSummary": candidate_summary,
        "ranked": ranked,
        "featureSnapshotUri": f"file://logs/features/{scoring_run_id}.json",
    }


def _empty_result(scoring_run_id, job, config, candidate_summary, scoring_mode, ml_trust_factor, degraded_reason, start):
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    return {
        "scoringRunId": scoring_run_id,
        "jobId": job["jobId"],
        "generatedAtUtc": _now_iso(),
        "latencyMs": latency_ms,
        "binding": {
            "rulesetVersion": config["rulesetVersion"],
            "modelName": None,
            "modelVersion": None,
            "scoringMode": scoring_mode,
            "mlTrustFactor": ml_trust_factor,
            "degradedReason": degraded_reason,
        },
        "candidateSummary": candidate_summary,
        "ranked": [],
        "featureSnapshotUri": f"file://logs/features/{scoring_run_id}.json",
    }
