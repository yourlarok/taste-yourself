$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    py -3.11 -m ruff check server/app server/tests workers/fashn_vton/app.py scripts/preflight.py
    py -3.11 -m pytest -q server/tests

    Get-ChildItem miniprogram -Recurse -Filter *.js | ForEach-Object {
        node --check $_.FullName
    }

    node -e "JSON.parse(require('fs').readFileSync('project.config.json','utf8')); JSON.parse(require('fs').readFileSync('miniprogram/app.json','utf8'))"

    $escapedOperators = Get-ChildItem miniprogram -Recurse -Filter *.wxml |
        Select-String -SimpleMatch '&amp;&amp;'
    if ($escapedOperators) {
        throw 'Escaped logical operators are not allowed in WXML.'
    }

    docker compose --env-file .env.example -f compose.production.yml config --quiet
    Write-Output "All repository checks passed."
}
finally {
    Pop-Location
}
