
from __future__ import annotations

import json
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
LOGS_DIR = BACKEND_DIR / "logs"

STATE_STORE_IMPL = os.environ.get("STATE_STORE_IMPL", "blob")


class _MemoryStore:
    """Seeded from data/jobs.json, matching api/state.py's local-dev
    behavior - used when running `func start` locally against a fresh
    in-process store (no FastAPI involved)."""

    def __init__(self) -> None:
        self.jobs: dict[str, dict] = {}
        self.score_factors: dict[str, dict] = {}
        self.assignments: dict[str, dict] = {}
        for job in json.loads((BACKEND_DIR / "data" / "jobs.json").read_text()):
            self.jobs[job["jobId"]] = job

    def put_job(self, job_id: str, job_event: dict) -> None:
        self.jobs[job_id] = job_event

    def get_job(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[dict]:
        return list(self.jobs.values())

    def put_score_factors(self, job_id: str, score_factors: dict) -> None:
        self.score_factors[job_id] = score_factors

    def get_score_factors(self, job_id: str) -> dict | None:
        return self.score_factors.get(job_id)

    def put_assignment(self, job_id: str, assignment: dict) -> None:
        self.assignments[job_id] = assignment

    def get_assignment(self, job_id: str) -> dict | None:
        return self.assignments.get(job_id)

    def read_audit(self, stream: str, job_id: str) -> list[dict]:
        path = LOGS_DIR / f"{stream}.jsonl"
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        return [line for line in lines if line.get("jobId") == job_id]


class _BlobStore:
    def __init__(self) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        account_name = os.environ["STORAGE_ACCOUNT_NAME"]
        client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=DefaultAzureCredential(),
        )
        self._state = client.get_container_client(os.environ.get("STATE_CONTAINER", "state"))
        self._audit = client.get_container_client(os.environ.get("AUDIT_CONTAINER", "audit"))

    def _get_json(self, blob_name: str) -> dict | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return json.loads(self._state.get_blob_client(blob_name).download_blob().readall())
        except ResourceNotFoundError:
            return None

    def _put_json(self, blob_name: str, obj: dict) -> None:
        self._state.get_blob_client(blob_name).upload_blob(
            json.dumps(obj, default=str).encode("utf-8"), overwrite=True
        )

    def put_job(self, job_id: str, job_event: dict) -> None:
        self._put_json(f"jobs/{job_id}.json", job_event)

    def get_job(self, job_id: str) -> dict | None:
        return self._get_json(f"jobs/{job_id}.json")

    def list_jobs(self) -> list[dict]:
        jobs = []
        for blob in self._state.list_blobs(name_starts_with="jobs/"):
            job = self._get_json(blob.name)
            if job is not None:
                jobs.append(job)
        return jobs

    def put_score_factors(self, job_id: str, score_factors: dict) -> None:
        self._put_json(f"scorefactors/{job_id}.json", score_factors)

    def get_score_factors(self, job_id: str) -> dict | None:
        return self._get_json(f"scorefactors/{job_id}.json")

    def put_assignment(self, job_id: str, assignment: dict) -> None:
        self._put_json(f"assignments/{job_id}.json", assignment)

    def get_assignment(self, job_id: str) -> dict | None:
        return self._get_json(f"assignments/{job_id}.json")

    def read_audit(self, stream: str, job_id: str) -> list[dict]:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            content = self._audit.get_blob_client(f"{stream}.jsonl").download_blob().readall().decode("utf-8")
        except ResourceNotFoundError:
            return []
        lines = [json.loads(line) for line in content.splitlines() if line.strip()]
        return [line for line in lines if line.get("jobId") == job_id]

    def append_audit(self, stream: str, record: dict) -> None:
        """Called from audit.py's blob branch only - append blobs are safe
        for concurrent writers across multiple Function App instances,
        which is exactly the property needed here."""
        from azure.core.exceptions import ResourceNotFoundError
        blob = self._audit.get_blob_client(f"{stream}.jsonl")
        line = (json.dumps(record, default=str) + "\n").encode("utf-8")
        try:
            blob.append_block(line)
        except ResourceNotFoundError:
            blob.create_append_blob()
            blob.append_block(line)


_store: _MemoryStore | _BlobStore | None = None


def _get_store() -> _MemoryStore | _BlobStore:
    global _store
    if _store is None:
        _store = _BlobStore() if STATE_STORE_IMPL == "blob" else _MemoryStore()
    return _store


def put_job(job_id: str, job_event: dict) -> None:
    _get_store().put_job(job_id, job_event)


def get_job(job_id: str) -> dict | None:
    return _get_store().get_job(job_id)


def list_jobs() -> list[dict]:
    return _get_store().list_jobs()


def put_score_factors(job_id: str, score_factors: dict) -> None:
    _get_store().put_score_factors(job_id, score_factors)


def get_score_factors(job_id: str) -> dict | None:
    return _get_store().get_score_factors(job_id)


def put_assignment(job_id: str, assignment: dict) -> None:
    _get_store().put_assignment(job_id, assignment)


def get_assignment(job_id: str) -> dict | None:
    return _get_store().get_assignment(job_id)


def read_audit(stream: str, job_id: str) -> list[dict]:
    return _get_store().read_audit(stream, job_id)


def append_audit(stream: str, record: dict) -> None:
    """Only meaningful against the blob backend - audit.py's memory
    branch writes logs/*.jsonl directly and never calls this."""
    _get_store().append_audit(stream, record)  # type: ignore[union-attr]
