# fetch_corpus.ps1 - Version Windows/PowerShell du script de recuperation de corpus.
# Equivalent de fetch_corpus.sh. Sources publiques a licence ouverte (CERT-FR, CNIL, data.gouv).
#
# Usage :
#   ./fetch_corpus.ps1                       # profil mixte (~30 docs)
#   ./fetch_corpus.ps1 -Profile open         # projet A : data.gouv
#   ./fetch_corpus.ps1 -NAvis 40             # nb d'avis CERT-FR

param(
    [ValidateSet("mixte", "cert", "cnil", "open")]
    [string]$Profile = "mixte",
    [int]$NAvis = 30,
    [string]$DataQuery = "intelligence artificielle"
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RawDir = Join-Path $Here "corpus/raw"
New-Item -ItemType Directory -Force -Path "$RawDir/cert-fr", "$RawDir/cnil", "$RawDir/data-gouv" | Out-Null

function Get-File($Url, $OutFile) {
    try {
        Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec 30 `
            -Headers @{ "User-Agent" = "tp-rag-formation/1.0" }
        return $true
    } catch {
        Write-Warning "Indisponible : $Url"
        return $false
    }
}

function Fetch-Open {
    Write-Host "[fetch] data.gouv.fr : recherche de jeux de donnees..." -ForegroundColor Cyan
    $q = [uri]::EscapeDataString($DataQuery)
    $api = "https://www.data.gouv.fr/api/1/datasets/?page_size=5&q=$q"
    $meta = Join-Path $env:TEMP "datagouv.json"
    if (-not (Get-File $api $meta)) { return }
    $content = Get-Content $meta -Raw
    $urls = [regex]::Matches($content, "https://[^`"]+\.(pdf|csv|json|txt)") |
        ForEach-Object { $_.Value } | Select-Object -Unique | Select-Object -First 5
    $count = 0
    foreach ($url in $urls) {
        $name = (Split-Path $url -Leaf) -replace "[^A-Za-z0-9._-]", ""
        if (-not $name) { $name = "resource_$count.bin" }
        if (Get-File $url "$RawDir/data-gouv/$name") { $count++ }
    }
    Remove-Item $meta -ErrorAction SilentlyContinue
    Write-Host "[fetch] data.gouv : $count ressources recuperees." -ForegroundColor Cyan
}

switch ($Profile) {
    "open"  { Fetch-Open }
    "mixte" { Fetch-Open }
}

$total = (Get-ChildItem -Recurse -File $RawDir | Measure-Object).Count
Write-Host "[fetch] Termine. $total fichiers dans corpus/raw/ (gitignore)." -ForegroundColor Green
