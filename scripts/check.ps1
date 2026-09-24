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

    $wxml = Get-Content miniprogram/pages/mirror/index.wxml -Raw -Encoding utf8
    $wxml = $wxml -replace '<view class="mirror-page">', '<view xmlns:wx="urn:wx" class="mirror-page">'
    $wxml = $wxml -replace ' wx:else>', ' wx:else="true">'
    $wxml = $wxml -replace ' scroll-x enable-flex>', ' scroll-x="true" enable-flex="true">'
    $xml = New-Object System.Xml.XmlDocument
    $xml.LoadXml($wxml)

    docker compose --env-file .env.example -f compose.production.yml config --quiet
    Write-Output "All repository checks passed."
}
finally {
    Pop-Location
}
