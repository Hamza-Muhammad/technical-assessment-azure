
from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from contracts import models as m

OUT_PATH = Path(__file__).resolve().parent / "openapi.json"

# (path, method, summary, request_model, response_model, auth: "anonymous" | "function")
ROUTES: list[tuple[str, str, str, type | None, type | list, str]] = [
    ("/jobs", "post", "Create a job", m.JobCreateRequest, m.JobCreateResponse, "anonymous"),
    ("/jobs", "get", "List jobs", None, [m.JobListItem], "anonymous"),
    ("/jobs/{jobId}", "get", "Get a job", None, m.JobEvent, "anonymous"),
    ("/jobs/{jobId}/recommendation", "get", "Get a job's scoring recommendation", None, m.ScoreFactors, "anonymous"),
    ("/jobs/{jobId}/assignment", "post", "Accept or override the recommendation", m.AssignmentRequest, m.AssignmentResponse, "anonymous"),
    ("/jobs/{jobId}/completion", "post", "Record a job outcome (feeds the retraining loop)", m.JobCompletionRequest, m.JobCompletionResponse, "anonymous"),
    ("/jobs/{jobId}/audit", "get", "Get the full audit trail for a job", None, m.AuditResponse, "anonymous"),
    ("/vendors", "get", "List all vendors", None, [m.VendorProfile], "anonymous"),
    ("/jobs/{jobId}/replay", "post", "Re-publish JobCreated for an already-known job", None, m.JobCreateResponse, "anonymous"),
    ("/admin/seed", "post", "Seed and dispatch every fixture job in data/jobs.json", None, m.SeedResponse, "function"),
    ("/jobs/{jobId}/dispatch", "post", "Publish JobCreated for an already-known job (saga demo hook)", None, m.DispatchResponse, "function"),
    ("/jobs/{jobId}/orchestration", "get", "Get the Durable orchestration status for a job", None, m.OrchestrationStatusResponse, "function"),
    ("/jobs/{jobId}/vendor-response", "post", "Raise the saga's VendorResponse external event", m.VendorResponseBody, None, "anonymous"),
]

PATH_PARAM = {
    "name": "jobId", "in": "path", "required": True, "schema": {"type": "string"},
}


def _schema_ref(model_or_list, schemas: dict) -> dict:
    if isinstance(model_or_list, list):
        item_schema = _schema_ref(model_or_list[0], schemas)
        return {"type": "array", "items": item_schema}
    adapter = TypeAdapter(model_or_list)
    json_schema = adapter.json_schema(ref_template="#/components/schemas/{model}")
    defs = json_schema.pop("$defs", {})
    schemas.update(defs)
    name = model_or_list.__name__
    schemas[name] = json_schema
    return {"$ref": f"#/components/schemas/{name}"}


def build() -> dict:
    schemas: dict = {}
    paths: dict = {}

    for path, method, summary, req_model, resp_model, auth in ROUTES:
        operation = {"summary": summary}
        if "{jobId}" in path:
            operation["parameters"] = [dict(PATH_PARAM)]
        if req_model is not None:
            operation["requestBody"] = {
                "required": True,
                "content": {"application/json": {"schema": _schema_ref(req_model, schemas)}},
            }
        success_status = "202" if resp_model is None else ("201" if method == "post" and path in ("/jobs",) else "200")
        response_content = (
            {"description": "Accepted"} if resp_model is None
            else {
                "description": "Successful Response",
                "content": {"application/json": {"schema": _schema_ref(resp_model, schemas)}},
            }
        )
        operation["responses"] = {success_status: response_content}
        if auth == "function":
            operation["security"] = [{"functionKey": []}]
        else:
            operation["security"] = []
        paths.setdefault(path, {})[method] = operation

    return {
        "openapi": "3.1.0",
        "info": {"title": "RetailFixIt Vendor Dispatch API", "version": "2.0.0"},
        "servers": [{"url": "https://<functionAppName>.azurewebsites.net/api"}],
        "paths": paths,
        "components": {
            "schemas": schemas,
            "securitySchemes": {
                "functionKey": {"type": "apiKey", "in": "header", "name": "x-functions-key"},
            },
        },
    }


if __name__ == "__main__":
    spec = build()
    OUT_PATH.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
