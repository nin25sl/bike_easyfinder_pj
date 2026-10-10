from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from sqlalchemy import Engine, bindparam, text

from collection_worker.errors import ConfigurationError


def _schema(filename: str = "spot-candidate-v1.json") -> dict:
    candidates = [
        Path(__file__).resolve().parents[2] / "schemas" / filename,
        Path.cwd() / "schemas" / filename,
        Path("/app/schemas") / filename,
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
                           s.source_key, s.base_url collection_url, s.license_name, s.terms_url, s.attribution_text,
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


def resolved_documents(engine: Engine, run_id: str, status: str | None = None) -> list[dict[str, Any]]:
    statuses = [item.strip() for item in (status or "").split(",") if item.strip()]
    status_clause = " AND e.status IN :statuses" if statuses else ""
    statement = text(
        f"""
        SELECT DISTINCT e.id::text, e.entity_key, e.status, e.quality_score::float,
               r.region_code, r.name_ja region_name, r.dataset_version
        FROM resolved_spot_entities e
        JOIN administrative_regions r ON r.id=e.region_id
        JOIN spot_entity_memberships m ON m.entity_id=e.id
        JOIN field_observations o ON o.candidate_id=m.candidate_id
        JOIN collection_run_items i ON i.id=o.run_item_id
        WHERE i.run_id=:run_id AND e.merged_into_entity_id IS NULL{status_clause}
        ORDER BY 1
        """
    )
    if statuses:
        statement = statement.bindparams(bindparam("statuses", expanding=True))
    with engine.connect() as connection:
        entities = connection.execute(statement, {"run_id": run_id, "statuses": statuses}).mappings().all()
        documents = []
        for entity in entities:
            fields = connection.execute(text(
                """
                SELECT fs.field_name, fs.selection_score::float, fs.rule_version,
                       o.id::text observation_id, o.value, o.confidence::float,
                       o.source_url, o.source_record_id, o.retrieved_at,
                       s.source_key, s.source_type, s.license_status,
                       s.attribution_text
                FROM entity_field_selections fs
                JOIN field_observations o ON o.id=fs.observation_id
                JOIN collection_run_items i ON i.id=o.run_item_id
                JOIN source_registry s ON s.id=i.source_registry_id
                WHERE fs.entity_id=:entity_id ORDER BY fs.field_name
                """
            ), {"entity_id": entity["id"]}).mappings().all()
            members = connection.execute(text(
                """
                SELECT m.candidate_id::text, m.match_score::float, m.decision,
                       m.rule_version, m.evidence
                FROM spot_entity_memberships m WHERE m.entity_id=:entity_id
                ORDER BY m.candidate_id
                """
            ), {"entity_id": entity["id"]}).mappings().all()
            sources = connection.execute(text(
                """
                SELECT DISTINCT s.source_key, s.source_type, s.base_url collection_url,
                       s.license_name, s.terms_url, s.attribution_text,
                       o.source_url, o.source_record_id, o.license_status
                FROM spot_entity_memberships m
                JOIN field_observations o ON o.candidate_id=m.candidate_id
                JOIN collection_run_items i ON i.id=o.run_item_id
                JOIN source_registry s ON s.id=i.source_registry_id
                WHERE m.entity_id=:entity_id
                ORDER BY s.source_key, o.source_record_id
                """
            ), {"entity_id": entity["id"]}).mappings().all()
            document = {
                "schema_version": "resolved-spot-v1",
                "entity_id": entity["id"], "entity_key": entity["entity_key"],
                "status": entity["status"], "quality_score": entity["quality_score"],
                "region": {"code": entity["region_code"], "name": entity["region_name"], "dataset_version": entity["dataset_version"]},
                "selected_fields": {
                    field["field_name"]: {
                        **{key: value for key, value in dict(field).items() if key not in {"field_name", "retrieved_at"}},
                        "retrieved_at": field["retrieved_at"].isoformat(),
                    } for field in fields
                },
                "members": [dict(member) for member in members],
                "sources": [dict(source) for source in sources],
            }
            Draft202012Validator(_schema("resolved-spot-v1.json")).validate(document)
            documents.append(document)
    return documents


def export_run(
    engine: Engine, run_id: str, output_dir: Path, output_format: str,
    status: str | None = None, view: str = "candidate",
) -> list[Path]:
    if view not in {"candidate", "resolved"}:
        raise ConfigurationError("--view must be candidate or resolved")
    if view == "resolved":
        documents = resolved_documents(engine, run_id, status)
        target = output_dir / run_id
        target.mkdir(parents=True, exist_ok=True)
        if output_format == "jsonl":
            path = target / "resolved-spots.jsonl"
            path.write_text("".join(json.dumps(item, ensure_ascii=False, default=str) + "\n" for item in documents), encoding="utf-8")
            return [path]
        if output_format != "csv":
            raise ConfigurationError(f"Unsupported export format: {output_format}")
        entity_path = target / "resolved-spots.csv"
        fields_path = target / "resolved-field-sources.csv"
        attribution_path = target / "resolved-attributions.csv"
        _write_csv(entity_path, [{
            "entity_id": item["entity_id"], "entity_key": item["entity_key"],
            "status": item["status"], "quality_score": item["quality_score"],
            "region_code": item["region"]["code"],
        } for item in documents])
        _write_csv(fields_path, [{"entity_id": item["entity_id"], "field_name": name, **value}
                                 for item in documents for name, value in item["selected_fields"].items()])
        _write_csv(attribution_path, [
            {"entity_id": item["entity_id"], **source}
            for item in documents for source in item["sources"]
        ])
        return [entity_path, fields_path, attribution_path]
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
