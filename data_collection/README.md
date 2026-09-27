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
