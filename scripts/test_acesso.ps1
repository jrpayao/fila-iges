# scripts/test_acesso.ps1
# Testes de conectividade e leitura no SISREG-ES.
# Uso: pwsh -File scripts/test_acesso.ps1 -User "seu_user" -Pass "sua_senha"
# Variaveis SISREG_USER e SISREG_PASS no .env.local tambem sao aceitas como fallback.

param(
    [string]$User = $env:SISREG_USER,
    [string]$Pass = $env:SISREG_PASS,
    [string]$BaseUrl = "https://sisreg-es.saude.gov.br",
    [string]$Uf = "df",
    [string]$Municipio = "brasilia"
)

if (-not $User -or -not $Pass) {
    Write-Host "Forneca -User e -Pass, ou defina SISREG_USER/SISREG_PASS no env." -ForegroundColor Red
    exit 1
}

$Auth = "$User`:$Pass"
$IndiceMarcacao = "marcacao-ambulatorial-$Uf-$Municipio"
$IndiceSolicitacao = "solicitacao-ambulatorial-$Uf-$Municipio"
$IndiceHospitalar = "solicitacao-hospitalar-$Uf-$Municipio"

Write-Host "`n=== Teste 0: conectividade + auth ===" -ForegroundColor Cyan
& curl.exe -u $Auth -i "$BaseUrl/"

Write-Host "`n=== Teste 1: catalogo de indices visiveis ===" -ForegroundColor Cyan
& curl.exe -u $Auth "$BaseUrl/_cat/indices?v&s=index"

Write-Host "`n=== Teste 2: primeiro _search (size=1) em $IndiceSolicitacao ===" -ForegroundColor Cyan
& curl.exe -u $Auth "$BaseUrl/$IndiceSolicitacao/_search?size=1&pretty"

Write-Host "`n=== Teste 3: Top CIDs ultimos 10 dias em $IndiceSolicitacao ===" -ForegroundColor Cyan
& curl.exe -u $Auth -X POST "$BaseUrl/$IndiceSolicitacao/_search" `
    -H "Content-Type: application/json" `
    --data-binary "@scripts/queries/top_cids_ultimos_10d.json"
