$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

function Assert-NativeCommand([string]$label) {
    if ($LASTEXITCODE -ne 0) {
        throw "$label failed with exit code $LASTEXITCODE."
    }
}

Push-Location $repoRoot
try {
    py -3.11 -m ruff check server/app server/tests workers/fashn_vton/app.py scripts/preflight.py
    Assert-NativeCommand "Ruff"
    py -3.11 -m pytest -q server/tests
    Assert-NativeCommand "Pytest"

    Get-ChildItem miniprogram -Recurse -Filter *.js | ForEach-Object {
        node --check $_.FullName
        Assert-NativeCommand "JavaScript syntax check for $($_.FullName)"
    }

    node -e "JSON.parse(require('fs').readFileSync('project.config.json','utf8')); JSON.parse(require('fs').readFileSync('miniprogram/app.json','utf8'))"
    Assert-NativeCommand "Project JSON check"

    $escapedOperators = Get-ChildItem miniprogram -Recurse -Filter *.wxml |
        Select-String -SimpleMatch '&amp;&amp;'
    if ($escapedOperators) {
        throw 'Escaped logical operators are not allowed in WXML.'
    }

    docker compose --env-file .env.example -f compose.production.yml config --quiet
    Assert-NativeCommand "Docker Compose validation"
    Write-Output "All repository checks passed."
}
finally {
    Pop-Location
}
