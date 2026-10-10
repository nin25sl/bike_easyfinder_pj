収集成功している箇所としていない箇所を出すスクリプトをください。
# Spot data collection worker

The worker implements `spot-data-collection-basic-design-v1.md` as a local
Docker/PostGIS batch application.

## Quick start

```powershell
docker compose build
docker compose up -d db
docker compose run --rm migrate
docker compose run --rm worker python -m collection_worker regions sync --dataset-version latest
docker compose run --rm worker python -m collection_worker collect --region-code 40130 --sources osm_overpass,openai_web_discovery,manual_seed --mode initial --limit 100 --dry-run
```

Set `OPENAI_API_KEY` in the shell before selecting `openai_web_discovery`.
Never commit a real API key.

See `docs/bike_easyfinder_pj/Procedure/spot-data-collection-execution-procedure-v1.md`
for the full procedure.

## Bulk collection and resolution

The checked-in profiles provide a safe rollout boundary. Sources whose terms have
not been reviewed remain `pending_review` and cannot be selected by the worker.

```powershell
# Inspect the planned Fukuoka pilot without network or database writes
python -m collection_worker collect-all --profile fukuoka-pilot --region-group fukuoka --dry-run

# Run the approved P0 sources for Kyushu
python -m collection_worker collect-all --profile kyushu-p0 --region-group kyushu --mode initial

# Resume only incomplete child runs
python -m collection_worker batches resume <batch_id> --failed-only

# Export entity-resolved values and their selected sources
python -m collection_worker export --run-id <run_id> --view resolved --format jsonl
```

`osm_pbf` uses `config.extract_path` when supplied. Otherwise it downloads and
caches the configured Geofabrik extract with ETag, Last-Modified, and SHA-256
metadata. The source inventory is maintained in
`config/kyushu_source_inventory.yaml`.

Source-specific scripts under `scripts/sources/` are thin aliases for the same
CLI and do not contain collection logic.
