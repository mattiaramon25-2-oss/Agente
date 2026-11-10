# Avvia il servizio HTTP dell'agente con Docker Compose, passando al container il fuso orario di Windows.
# Uso: .\avvia-agente.ps1   (Ctrl+C lo ferma; il servizio risponde su http://127.0.0.1:AGENTE_PORTA)
Set-Location -Path $PSScriptRoot

$env:FUSO_HOST_WINDOWS = (Get-TimeZone).Id
& docker compose up --build agente
exit $LASTEXITCODE
