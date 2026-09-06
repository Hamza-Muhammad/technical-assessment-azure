
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

_logger = logging.getLogger("retailfixit.model_registry")

BACKEND_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BACKEND_DIR / "models" / "vendor_uplift"
REGISTRY_PATH = BACKEND_DIR / "config" / "registry.json"


class SchemaHashMismatchError(RuntimeError):
    pass


def compute_schema_hash(features: list[str]) -> str:
    return hashlib.sha256(json.dumps(features).encode("utf-8")).hexdigest()


def resolve_version(alias: str = "production") -> str:
    registry = json.loads(REGISTRY_PATH.read_text())
    return registry["aliases"][alias]


class LoadedModel:
    def __init__(self, booster, feature_spec: dict, metadata: dict, version: str):
        self.booster = booster
        self.feature_spec = feature_spec
        self.metadata = metadata
        self.version = version


_model_cache: dict[str, LoadedModel] = {}


def load_model(version: str) -> LoadedModel:
    """Cached per version - a scoring run calls this once per candidate
    otherwise, and re-reading + re-hash-checking the same file on every
    call would dominate scoring latency for no benefit."""
    cached = _model_cache.get(version)
    if cached is not None:
        return cached

    import lightgbm as lgb

    version_dir = MODELS_DIR / version
    model_path = version_dir / "model.txt"
    model_bytes = model_path.read_bytes()
    _logger.info("ml_model_artifact_inspected", extra={"custom_dimensions": {
        "modelVersion": version,
        "modelPath": str(model_path),
        "modelSizeBytes": len(model_bytes),
        "modelSha256": hashlib.sha256(model_bytes).hexdigest(),
        "modelFirstLine": model_bytes.splitlines()[0].decode("utf-8", errors="replace") if model_bytes else "<empty>",
        "lightgbmVersion": getattr(lgb, "__version__", "unknown"),
    }})
    feature_spec = json.loads((version_dir / "feature_spec.json").read_text())
    metadata = json.loads((version_dir / "metadata.json").read_text())

    computed = compute_schema_hash(feature_spec["features"])
    if computed != feature_spec["schemaHash"]:
        raise SchemaHashMismatchError(
            f"vendor_uplift/{version}: feature_spec schema hash mismatch "
            f"(expected {feature_spec['schemaHash']}, computed {computed}). "
            "Refusing to load - this model version's serving features do "
            "not match what it was trained on."
        )

    booster = lgb.Booster(model_file=str(model_path))
    loaded = LoadedModel(booster, feature_spec, metadata, version)
    _model_cache[version] = loaded
    return loaded
