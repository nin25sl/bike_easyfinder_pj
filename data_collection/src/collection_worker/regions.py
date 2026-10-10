from __future__ import annotations

import json
import tempfile
import uuid
import zipfile
from datetime import date
from pathlib import Path
from typing import Iterable

import httpx
import pyogrio
from shapely import MultiPolygon
from shapely.geometry import mapping
from shapely.ops import unary_union
from sqlalchemy import Engine, text

from collection_worker.config import Settings
from collection_worker.contracts import Region
from collection_worker.errors import ConfigurationError
from collection_worker.logging import emit
from collection_worker.utils import validate_local_government_code

MAX_ARCHIVE_MEMBER_BYTES = 500 * 1024 * 1024
SHAPEFILE_COMPONENT_SUFFIXES = {
    ".cpg",
    ".dbf",
    ".prj",
    ".qix",
    ".sbn",
    ".sbx",
    ".shp",
    ".shx",
}


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    members = [member for member in archive.infolist() if not member.is_dir()]
    for member in members:
        target = (destination / member.filename).resolve()
        if root not in target.parents and target != root:
            raise ConfigurationError(f"Unsafe N03 archive path: {member.filename}")

    # The national N03 archive contains the same dataset in multiple formats.
    # Prefer the much smaller Shapefile representation and do not expand the
    # very large, redundant GeoJSON member.
    shapefiles = [member for member in members if Path(member.filename).suffix.lower() == ".shp"]
    if shapefiles:
        primary = Path(shapefiles[0].filename)
        selected = [
            member
            for member in members
            if Path(member.filename).parent == primary.parent
            and Path(member.filename).stem == primary.stem
            and Path(member.filename).suffix.lower() in SHAPEFILE_COMPONENT_SUFFIXES
        ]
    else:
        geojson = [member for member in members if Path(member.filename).suffix.lower() == ".geojson"]
        selected = geojson[:1]

    if not selected:
        raise ConfigurationError("N03 archive contains no supported GIS file")
    for member in selected:
        if member.file_size > MAX_ARCHIVE_MEMBER_BYTES:
            raise ConfigurationError(f"N03 archive member is too large: {member.filename}")
        archive.extract(member, destination)


def _as_multipolygon(geometry):
    if geometry.geom_type == "MultiPolygon":
        return geometry
    if geometry.geom_type == "Polygon":
        return MultiPolygon([geometry])
    polygons = [part for part in getattr(geometry, "geoms", []) if part.geom_type == "Polygon"]
    return MultiPolygon(polygons)


def _dataset_file(settings: Settings, input_path: Path | None) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    if input_path:
        if not input_path.exists():
            raise ConfigurationError(f"N03 input not found: {input_path}")
        if input_path.suffix.lower() == ".zip":
            temporary = tempfile.TemporaryDirectory(prefix="bike-n03-local-")
            with zipfile.ZipFile(input_path) as archive:
                _safe_extract(archive, Path(temporary.name))
            candidates = list(Path(temporary.name).rglob("*.shp")) + list(Path(temporary.name).rglob("*.geojson"))
            if not candidates:
                temporary.cleanup()
                raise ConfigurationError("N03 archive contains no supported GIS file")
            return candidates[0], temporary
        return input_path, None
    source = settings.sources.get("n03")
    if not source or not source.base_url:
        raise ConfigurationError("sources.n03.base_url is required")
    temporary = tempfile.TemporaryDirectory(prefix="bike-n03-")
    zip_path = Path(temporary.name) / "n03.zip"
    with httpx.stream("GET", source.base_url, timeout=source.request_timeout_seconds, follow_redirects=True) as response:
        response.raise_for_status()
        with zip_path.open("wb") as output:
            for chunk in response.iter_bytes():
                output.write(chunk)
    with zipfile.ZipFile(zip_path) as archive:
        _safe_extract(archive, Path(temporary.name))
    candidates = list(Path(temporary.name).rglob("*.shp")) + list(Path(temporary.name).rglob("*.geojson"))
    if not candidates:
        raise ConfigurationError("N03 archive contains no supported GIS file")
    return candidates[0], temporary


def _region_rows(frame, dataset_version: str, valid_from: date) -> Iterable[dict]:
    required = {"N03_001", "N03_004", "N03_007", "geometry"}
    missing = required - set(frame.columns)
    if missing:
        raise ConfigurationError(f"N03 is missing columns: {sorted(missing)}")
    frame = frame.to_crs(4326)
    municipalities: list[dict] = []
    for code, group in frame.dropna(subset=["N03_007"]).groupby("N03_007"):
        code = str(code).zfill(5)[:5]
        municipality = str(group.iloc[0]["N03_004"])
        designated = str(group.iloc[0].get("N03_003") or "").strip()
        geometry = _as_multipolygon(unary_union(group.geometry.tolist()))
        parent = f"{code[:4]}0" if designated else code[:2]
        municipalities.append(
            {
                "region_code": code,
                "region_kind": "ward" if designated else "municipality",
                "name_ja": municipality,
                "prefecture_code": code[:2],
                "parent_region_code": parent,
                "geometry": geometry,
                "dataset_version": dataset_version,
                "valid_from": valid_from,
            }
        )
    yield from municipalities

    for prefecture_code in sorted({row["prefecture_code"] for row in municipalities}):
        children = [row for row in municipalities if row["prefecture_code"] == prefecture_code]
        matched = frame[frame["N03_007"].astype(str).str.startswith(prefecture_code)]
        prefecture_name = str(matched.iloc[0]["N03_001"])
        yield {
            "region_code": prefecture_code,
            "region_kind": "prefecture",
            "name_ja": prefecture_name,
            "prefecture_code": prefecture_code,
            "parent_region_code": None,
            "geometry": _as_multipolygon(unary_union([row["geometry"] for row in children])),
            "dataset_version": dataset_version,
            "valid_from": valid_from,
        }

    designated_names: dict[str, str] = {}
    for _, row in frame.iterrows():
        code = str(row.get("N03_007") or "").zfill(5)[:5]
        name = str(row.get("N03_003") or "").strip()
        if code and name:
            designated_names[f"{code[:4]}0"] = name
    for parent_code, name in designated_names.items():
        wards = [row for row in municipalities if row["parent_region_code"] == parent_code]
        if wards:
            yield {
                "region_code": parent_code,
                "region_kind": "designated_city",
                "name_ja": name,
                "prefecture_code": parent_code[:2],
                "parent_region_code": parent_code[:2],
                "geometry": _as_multipolygon(unary_union([row["geometry"] for row in wards])),
                "dataset_version": dataset_version,
                "valid_from": valid_from,
            }


def sync_regions(
    engine: Engine,
    settings: Settings,
    dataset_version: str = "latest",
    input_path: Path | None = None,
) -> int:
    source = settings.sources["n03"]
    configured_version = str(source.config.get("dataset_version", "N03-unknown"))
    version = configured_version if dataset_version == "latest" else dataset_version
    valid_from = date.fromisoformat(str(source.config.get("valid_from", "2023-01-01")))
    data_file, temporary = _dataset_file(settings, input_path)
    try:
        read_options = {"encoding": "CP932"} if data_file.suffix.lower() == ".shp" else {}
        frame = pyogrio.read_dataframe(data_file, **read_options)
        rows = list(_region_rows(frame, version, valid_from))
        source_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "source:n03"))
        statement = text(
            """
            INSERT INTO administrative_regions (
                id, region_code, region_kind, name_ja, prefecture_code,
                parent_region_code, geometry, dataset_version, valid_from,
                source_registry_id, is_current
            ) VALUES (
                :id, :region_code, :region_kind, :name_ja, :prefecture_code,
                :parent_region_code,
                ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geometry), 4326)),
                :dataset_version, :valid_from, :source_registry_id, true
            )
            ON CONFLICT (region_code, dataset_version) DO UPDATE SET
                region_kind=EXCLUDED.region_kind,
                name_ja=EXCLUDED.name_ja,
                prefecture_code=EXCLUDED.prefecture_code,
                parent_region_code=EXCLUDED.parent_region_code,
                geometry=EXCLUDED.geometry,
                valid_from=EXCLUDED.valid_from,
                source_registry_id=EXCLUDED.source_registry_id,
                is_current=true
            """
        )
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE administrative_regions SET is_current=false WHERE dataset_version <> :version"),
                {"version": version},
            )
            for row in rows:
                connection.execute(
                    statement,
                    {
                        **{key: value for key, value in row.items() if key != "geometry"},
                        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"region:{version}:{row['region_code']}")),
                        "geometry": json.dumps(mapping(row["geometry"])),
                        "source_registry_id": source_id,
                    },
                )
        emit("regions_synced", dataset_version=version, count=len(rows))
        return len(rows)
    finally:
        if temporary:
            temporary.cleanup()


def resolve_region(engine: Engine, code: str) -> Region:
    normalized = validate_local_government_code(code)
    query = text(
        """
        SELECT id::text, region_code, region_kind, name_ja, prefecture_code,
               parent_region_code, dataset_version, ST_AsBinary(geometry) AS geometry_wkb,
               ST_XMin(Box2D(geometry)) AS min_x,
               ST_YMin(Box2D(geometry)) AS min_y,
               ST_XMax(Box2D(geometry)) AS max_x,
               ST_YMax(Box2D(geometry)) AS max_y
        FROM administrative_regions
        WHERE region_code=:code AND is_current
        ORDER BY valid_from DESC
        LIMIT 1
        """
    )
    with engine.connect() as connection:
        row = connection.execute(query, {"code": normalized}).mappings().first()
    if not row:
        raise ConfigurationError(f"Current administrative region not found: {normalized}")
    return Region(
        id=row["id"],
        region_code=row["region_code"],
        region_kind=row["region_kind"],
        name_ja=row["name_ja"],
        prefecture_code=row["prefecture_code"],
        parent_region_code=row["parent_region_code"],
        dataset_version=row["dataset_version"],
        bbox=(row["min_x"], row["min_y"], row["max_x"], row["max_y"]),
        geometry_wkb=bytes(row["geometry_wkb"]),
    )
