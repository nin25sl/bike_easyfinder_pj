[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{2}(\d{3})?$')]
    [string]$RegionCode,

    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$RegionName,

    [ValidateRange(1, 100)]
    [int]$Limit = 30,

    [string[]]$Themes = @(
        'scenic viewpoints', 'coasts', 'mountains', 'hot springs', 'cafes',
        'restaurants', 'roadside stations', 'historic sites', 'tourist facilities',
        'motorcycle parking'
    )
)

$ErrorActionPreference = 'Stop'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = $utf8NoBom
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$templatePath = Join-Path $repoRoot 'data_collection\prompts\codex-spot-discovery-v1.md'
$pendingDir = Join-Path $repoRoot 'data_collection\seeds\codex_pending'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$outputPath = Join-Path $pendingDir "$RegionCode-$timestamp.jsonl"

$codexCommand = Get-Command codex.cmd -ErrorAction SilentlyContinue
if (-not $codexCommand) {
    throw 'codex.cmd was not found. Install Codex CLI and check PATH.'
}

& $codexCommand.Source login status
if ($LASTEXITCODE -ne 0) {
    throw 'Codex is not authenticated. Run: codex.cmd login'
}

New-Item -ItemType Directory -Path $pendingDir -Force | Out-Null

$prompt = Get-Content -Raw -Encoding UTF8 $templatePath
$prompt = $prompt.Replace('{{REGION_CODE}}', $RegionCode)
$prompt = $prompt.Replace('{{REGION_NAME}}', $RegionName)
$prompt = $prompt.Replace('{{LIMIT}}', [string]$Limit)
$prompt = $prompt.Replace('{{THEMES}}', ($Themes -join ', '))

$prompt | & $codexCommand.Source --search exec `
    --sandbox read-only `
    --cd $repoRoot `
    --output-last-message $outputPath `
    -

if ($LASTEXITCODE -ne 0) {
    throw "Codex failed with exit code: $LASTEXITCODE"
}

$lineNumber = 0
$validCount = 0
foreach ($line in Get-Content -Encoding UTF8 $outputPath) {
    $lineNumber += 1
    if ([string]::IsNullOrWhiteSpace($line)) {
        throw "Output line $lineNumber is empty: $outputPath"
    }

    try {
        $candidate = $line | ConvertFrom-Json
    }
    catch {
        throw "Output line $lineNumber is not valid JSON: $outputPath"
    }

    foreach ($required in @('source_record_id', 'source_url', 'region_code', 'name', 'license_status', 'review_status', 'discovered_by')) {
        if ($null -eq $candidate.$required -or [string]::IsNullOrWhiteSpace([string]$candidate.$required)) {
            throw "Output line $lineNumber is missing required field '$required': $outputPath"
        }
    }

    $sourceUri = $null
    if (-not [Uri]::TryCreate([string]$candidate.source_url, [UriKind]::Absolute, [ref]$sourceUri) -or
        $sourceUri.Scheme -notin @('http', 'https')) {
        throw "Output line $lineNumber has an invalid source_url: $outputPath"
    }
    if ([string]$candidate.region_code -ne $RegionCode) {
        throw "Output line $lineNumber has an unexpected region_code: $outputPath"
    }
    if ([string]$candidate.source_record_id -ne [string]$candidate.source_url) {
        throw "Output line $lineNumber has different source_record_id and source_url values: $outputPath"
    }
    if ([string]$candidate.license_status -ne 'unknown' -or [string]$candidate.review_status -ne 'pending') {
        throw "Output line $lineNumber is not marked as pending review: $outputPath"
    }
    foreach ($textField in @('name', 'address', 'source_title', 'evidence_note')) {
        if ([string]$candidate.$textField -match '\?{3,}') {
            throw "Output line $lineNumber appears to contain garbled text in '$textField': $outputPath"
        }
    }

    $validCount += 1
}

if ($validCount -eq 0) {
    throw "Codex returned no candidates: $outputPath"
}

Write-Host "Codex candidate file: $outputPath"
Write-Host "Validated candidate count: $validCount"
Write-Host 'Review every URL, region, and license before importing candidates into the Worker.'
