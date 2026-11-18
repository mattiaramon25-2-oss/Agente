# Avvia l'assistente con Docker Compose passando al container il fuso orario di Windows.
# Uso: .\avvia.ps1
# -SenzaTty serve solo alla prova automatica, quando l'ingresso arriva da una pipe.
param([switch]$SenzaTty)

Set-Location -Path $PSScriptRoot

# Con l'agente della chat acceso in Docker, due server MCP scriverebbero insieme le note.
# Se Docker e' spento, l'elenco resta vuoto e si prosegue: sara' docker compose run a dirlo.
if (-not $SenzaTty) {
    $accesi = @()
    try {
        $accesi = @(& docker compose ps --status running --services 2>$null)
    } catch {
        $accesi = @()
    }
    if ($accesi -contains 'agente') {
        Write-Host "Attenzione: il container agente (la chat nel browser) risulta acceso."
        Write-Host "Le note in archivio/note.sqlite3 sono usate anche dall'agente della chat:"
        Write-Host "scriverle da due parti insieme rischia di rovinarle."
        # Domanda scritta a parte: con l'ingresso rediretto Read-Host legge la riga ma non mostra il prompt.
        Write-Host -NoNewline "Aprire comunque la CLI? (S/N) "
        $risposta = Read-Host
        if ($risposta -ne 'S') {
            exit 0
        }
    }
}

$fuso = (Get-TimeZone).Id
$argomenti = @('compose', 'run', '--rm')
if ($SenzaTty) {
    $argomenti += '-T'
}
$argomenti += @('-e', "FUSO_HOST_WINDOWS=$fuso", 'assistente')

& docker @argomenti
exit $LASTEXITCODE
