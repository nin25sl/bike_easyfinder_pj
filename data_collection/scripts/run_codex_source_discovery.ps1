# Backward-compatible entry point. Use run_codex_spot_discovery.ps1 for new commands.
& (Join-Path $PSScriptRoot 'run_codex_spot_discovery.ps1') @args
exit $LASTEXITCODE
