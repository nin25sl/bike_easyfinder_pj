from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import Engine, bindparam, text

from collection_worker.errors import ConfigurationError


def _schema() -> dict:
    candidates = [
        Path(__file__).resolve().parents[2] / "schemas" / "spot-candidate-v1.json",
        Path.cwd() / "schemas" / "spot-candidate-v1.json",
        Path("/app/schemas/spot-candidate-v1.json"),
    ]
    path = next((item for item in candidates if item.is_file()), None)
    if path is None:
        raise FileNotFoundError("SpotCandidate schema was not packaged")
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_documents(engine: Engine, run_id: str, status: str | None = None) -> list[dict[str, Any]]:
    statuses = [item.strip() for item in (status or "").split(",") if item.strip()]
    status_clause = " AND c.status IN :statuses" if statuses else ""
    statement = text(
        f"""
        SELECT DISTINCT c.id::text, c.status, c.display_name, c.address_text,
               ST_Y(c.location::geometry) AS latitude,
               ST_X(c.location::geometry) AS longitude,
               c.quality_score::float, r.region_code, r.name_ja AS region_name,
               r.region_kind, r.dataset_version
        FROM spot_candidates c
        JOIN administrative_regions r ON r.id=c.region_id
        JOIN field_observations o ON o.candidate_id=c.id
        JOIN collection_run_items i ON i.id=o.run_item_id
        WHERE i.run_id=:run_id{status_clause}
        ORDER BY 1
        """
    )
    if statuses:
        statement = statement.bindparams(bindparam("statuses", expanding=True))
    with engine.connect() as initial_connection:
        rows = initial_connection.execute(statement, {"run_id": run_id, "statuses": statuses}).mappings().all()
    documents = []
    with engine.connect() as connection:
        for row in rows:
            observations = connection.execute(
                text(
                    """
                    SELECT o.field_name, o.value, o.raw_label, o.extraction_method,
                           o.confidence::float, o.source_url, o.source_record_id,
                           o.observed_at, o.retrieved_at, o.verified_at,
                           o.license_status, o.evidence_excerpt,
                           s.source_key, s.license_name, s.terms_url, s.attribution_text,
                           s.raw_storage_policy
                    FROM field_observations o
                    JOIN collection_run_items i ON i.id=o.run_item_id
                    JOIN source_registry s ON s.id=i.source_registry_id
                    WHERE o.candidate_id=:candidate_id AND i.run_id=:run_id
                    ORDER BY o.field_name, s.source_key
                    """
                ), {"candidate_id": row["id"], "run_id": run_id}
            ).mappings().all()
            reviews = connection.execute(
                text("SELECT reason_code FROM review_tasks WHERE candidate_id=:id AND status='open' ORDER BY reason_code"),
                {"id": row["id"]},
            ).scalars().all()
            doc = {
                "schema_version": "spot-candidate-v1",
                "candidate_id": row["id"],
                "status": row["status"],
                "name": row["display_name"],
                "address": row["address_text"],
                "location": (
                    {"latitude": row["latitude"], "longitude": row["longitude"]}
                    if row["latitude"] is not None else None
                ),
                "region": {
                    "code": row["region_code"], "name": row["region_name"],
                    "kind": row["region_kind"], "dataset_version": row["dataset_version"],
                },
                "quality_score": row["quality_score"],
                "review_reasons": list(reviews),
                "observations": [
                    {
                        **{key: value for key, value in dict(item).items() if key not in {"observed_at", "retrieved_at", "verified_at"}},
                        "observed_at": item["observed_at"].isoformat() if item["observed_at"] else None,
                        "retrieved_at": item["retrieved_at"].isoformat(),
                        "verified_at": item["verified_at"].isoformat() if item["verified_at"] else None,
                    }
                    for item in observations
                ],
            }
            Draft202012Validator(_schema()).validate(doc)
            documents.append(doc)
    return documents


def export_run(engine: Engine, run_id: str, output_dir: Path, output_format: str, status: str | None = None) -> list[Path]:
    documents = candidate_documents(engine, run_id, status)
    target = output_dir / run_id
    target.mkdir(parents=True, exist_ok=True)
    if output_format == "jsonl":
        path = target / "candidates.jsonl"
        path.write_text("".join(json.dumps(item, ensure_ascii=False, default=str) + "\n" for item in documents), encoding="utf-8")
        return [path]
    if output_format != "csv":
        raise ConfigurationError(f"Unsupported export format: {output_format}")
    candidate_path = target / "candidates.csv"
    observation_path = target / "observations.csv"
    review_path = target / "reviews.csv"
    attribution_path = target / "attributions.csv"
    _write_csv(candidate_path, [
        {
            "candidate_id": d["candidate_id"], "status": d["status"], "name": d["name"],
            "address": d["address"], "latitude": (d["location"] or {}).get("latitude"),
            "longitude": (d["location"] or {}).get("longitude"), "region_code": d["region"]["code"],
            "quality_score": d["quality_score"],
        } for d in documents
    ])
    _write_csv(observation_path, [
        {"candidate_id": d["candidate_id"], **{k: json.dumps(v, ensure_ascii=False) if k == "value" else v for k, v in o.items()}}
        for d in documents for o in d["observations"]
    ])
    _write_csv(review_path, [
        {"candidate_id": d["candidate_id"], "reason_code": reason}
        for d in documents for reason in d["review_reasons"]
    ])
    attributions = {
        (o["source_key"], o.get("license_name"), o.get("terms_url"), o.get("attribution_text"))
        for d in documents for o in d["observations"]
    }
    _write_csv(attribution_path, [
        {"source_key": key, "license_name": license_name, "terms_url": terms_url, "attribution_text": attribution}
        for key, license_name, terms_url, attribution in sorted(attributions, key=lambda row: row[0])
    ])
    return [candidate_path, observation_path, attribution_path, review_path]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        if fieldnames:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
