"""
Explainability layer, human-language half: template rationale (always
generated, zero dependencies) with an optional Azure OpenAI narration
layer behind ENABLE_LLM_NARRATION (default false - the demo must run
with zero API keys set). Every number the LLM writes must already exist
in factors[]; if it invents one, or the call fails for any reason, we
fall back to the template and set fallbackUsed=True. The LLM never
ranks, filters, or overrides anything - it only rephrases numbers that
were already computed deterministically.
"""
from __future__ import annotations

import os
import re


def build_template(rank: int, total: int, factors: list[dict]) -> str:
    positives = sorted((f for f in factors if f["contributionPct"] > 0), key=lambda f: -f["contributionPct"])[:3]
    negatives = sorted((f for f in factors if f["contributionPct"] < 0), key=lambda f: f["contributionPct"])[:2]

    text = f"Ranked #{rank} of {total} eligible."
    if positives:
        text += " Drivers: " + "; ".join(f["evidence"] for f in positives) + "."
    if negatives:
        text += " Detractors: " + "; ".join(f["evidence"] for f in negatives) + "."
    return text


def _extract_numbers(text: str) -> list[float]:
    return [float(m) for m in re.findall(r"-?\d+\.?\d*", text) if m not in ("", "-", ".")]


def groundedness_check(narrative: str, factors: list[dict], tolerance: float = 0.05) -> bool:
    """Every number in `narrative` must be traceable to a number already
    present in factors[] (evidence text, raw value, or contribution %)."""
    allowed: set[float] = set()
    for f in factors:
        allowed.update(_extract_numbers(f["evidence"]))
        if f.get("raw") is not None:
            allowed.add(round(float(f["raw"]), 4))
        allowed.add(round(abs(f["contributionPct"]), 1))

    for n in _extract_numbers(narrative):
        if not any(abs(n - a) < tolerance for a in allowed):
            return False
    return True


def _call_azure_openai(vendor_display_name: str, factors: list[dict], template: str) -> str:
    """Raises on any failure (missing keys, quota, timeout) - caller
    catches and falls back to the template. Import is local so the
    `openai` package is never required unless the flag is actually on."""
    from openai import AzureOpenAI

    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
    )
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

    factor_lines = "\n".join(f"- {f['id']}: {f['evidence']} (contribution {f['contributionPct']:+.1f}%)" for f in factors)
    prompt = (
        "Rewrite the following vendor-recommendation facts as 2-3 plain-English "
        "sentences for a dispatcher. Use ONLY the numbers given below - do not "
        "invent, round differently, or add any number not listed. No preamble.\n\n"
        f"Vendor: {vendor_display_name}\n"
        f"Facts:\n{factor_lines}\n\n"
        f"Baseline summary: {template}"
    )
    resp = client.chat.completions.create(
        model=deployment,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.2,
        timeout=2.0,
    )
    return resp.choices[0].message.content.strip()


def generate_rationale(rank: int, total: int, factors: list[dict], vendor_display_name: str, config: dict) -> dict:
    template = build_template(rank, total, factors)

    if not config["featureFlags"].get("ENABLE_LLM_NARRATION", False):
        return {
            "template": template,
            "narrative": None,
            "source": "TEMPLATE",
            "groundednessCheck": "SKIPPED",
            "fallbackUsed": False,
        }

    try:
        narrative = _call_azure_openai(vendor_display_name, factors, template)
    except Exception:
        return {
            "template": template,
            "narrative": None,
            "source": "TEMPLATE",
            "groundednessCheck": "SKIPPED",
            "fallbackUsed": True,
        }

    if groundedness_check(narrative, factors):
        return {
            "template": template,
            "narrative": narrative,
            "source": "LLM",
            "groundednessCheck": "PASSED",
            "fallbackUsed": False,
        }

    return {
        "template": template,
        "narrative": None,
        "source": "TEMPLATE",
        "groundednessCheck": "FAILED",
        "fallbackUsed": True,
    }
