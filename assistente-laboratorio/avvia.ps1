# Avvia l'assistente con Docker Compose passando al container il fuso orario di Windows.
# Uso: .\avvia.ps1
# -SenzaTty serve solo alla prova automatica, quando l'ingresso arriva da una pipe.
param([switch]$SenzaTty)

Set-Location -Path $PSScriptRoot

$fuso = (Get-TimeZone).Id
$argomenti = @('compose', 'run', '--rm')
if ($SenzaTty) {
    $argomenti += '-T'
}
$argomenti += @('-e', "FUSO_HOST_WINDOWS=$fuso", 'assistente')

& docker @argomenti
exit $LASTEXITCODE
