"""Prova reale con Docker: collegamento a LM Studio dal container e fuso dell'utente corretto.

Si attiva solo con: python -m pytest --docker -m docker -v -s
Richiede Docker Desktop e LM Studio accesi, e il file .env.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest
from tzlocal.windows_tz import win_tz

from tests.cartelle_da_parte import cartelle_da_parte

pytestmark = pytest.mark.docker

CARTELLA = Path(__file__).resolve().parent.parent
INGRESSO = "Che ore sono?\nesci\n"
TIMEOUT = 300


def esegui(comando: list[str], ingresso: str = INGRESSO) -> subprocess.CompletedProcess:
    risultato = subprocess.run(
        comando,
        cwd=CARTELLA,
        input=ingresso,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT,
    )
    print(f"\n$ {' '.join(comando)}\n{risultato.stdout}\n{risultato.stderr}")
    return risultato


@pytest.fixture(scope="module", autouse=True)
def immagine():
    subprocess.run(["docker", "compose", "build"], cwd=CARTELLA, check=True, timeout=900)


def fuso_di_windows() -> str:
    uscita = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "(Get-TimeZone).Id"],
        capture_output=True, text=True, check=True,
    )
    return uscita.stdout.strip()


def test_avvio_con_lo_script():
    atteso = win_tz[fuso_di_windows()]
    r = esegui(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "avvia.ps1", "-SenzaTty"])
    assert r.returncode == 0
    assert f"Fuso orario: {atteso} (host Windows)" in r.stdout
    assert "[ora_corrente · mcp:" in r.stdout
    assert "Arrivederci." in r.stdout
    assert "ripiego" not in r.stdout


def test_avvio_senza_lo_script_usa_fuso_orario():
    r = esegui(["docker", "compose", "run", "--rm", "-T", "assistente"])
    assert r.returncode == 0
    assert "(FUSO_ORARIO)" in r.stdout
    assert "Arrivederci." in r.stdout


def test_convertitore_in_docker():
    log_assistente = CARTELLA / "logs" / "assistente.log"
    log_server = CARTELLA / "logs" / "server_mcp.log"
    prima = {p: (p.stat().st_size if p.exists() else 0) for p in (log_assistente, log_server)}
    r = esegui(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "avvia.ps1", "-SenzaTty"],
        ingresso="Quanti metri sono 2,5 km?\nesci\n",
    )
    assert r.returncode == 0
    assert "converti_unita (mcp)" in r.stdout and "[converti_unita · mcp:" in r.stdout
    for percorso, inizio in prima.items():
        with open(percorso, "rb") as file:
            file.seek(inizio)
            assert "tool=converti_unita" in file.read().decode("utf-8", errors="replace"), percorso


IMMAGINE = "assistente-laboratorio-assistente"  # nome dato da Compose al servizio «assistente»
VARIANTI = {"VARIANTE_SCADENZE": "fastapi", "API_PORTA": "8766", "VARIANTE_CALCOLATRICE": "locale"}


# Valori come in un .env normale (tutto mcp): le varianti arrivano solo dai -e, come nel comando del README.
ENV_COME_DA_DOTENV = {"MCP_PORTA": "8765", "VARIANTE_CALCOLATRICE": "mcp", "VARIANTE_SCADENZE": "mcp"}


def cartelle_dell_utente_da_parte():
    """Sposta logs/ e archivio/ dell'utente (prima esecuzione) e li ripristina sempre: vedi tests/cartelle_da_parte.py."""
    return cartelle_da_parte(CARTELLA, ("logs", "archivio"))


def compose_con_varianti(ingresso: str, *comando_nel_container: str) -> subprocess.CompletedProcess:
    fuso = fuso_di_windows()
    comando = ["docker", "compose", "run", "--rm", "-T", "-e", f"FUSO_HOST_WINDOWS={fuso}"]
    for nome, valore in VARIANTI.items():
        comando += ["-e", f"{nome}={valore}"]
    comando += ["assistente", *comando_nel_container]
    risultato = subprocess.run(
        comando, cwd=CARTELLA, input=ingresso, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=TIMEOUT, env={**os.environ, **ENV_COME_DA_DOTENV},
    )
    print(f"\n$ {' '.join(comando)}\n{risultato.stdout}\n{risultato.stderr}")
    return risultato


def test_varianti_in_docker():
    """Varianti fastapi e locale nel container e meteo con la rete del container (prima esecuzione, senza logs/)."""
    with cartelle_dell_utente_da_parte():
        r = compose_con_varianti(
            "Se parto il 23 dicembre 2026, quando scadono 3 giorni lavorativi?\n"
            "Che tempo fa a Udine?\n"
            "Ricordami di provare Docker\n"
            "esci\n"
        )
        assert r.returncode == 0
        assert "calcola_scadenza (fastapi)" in r.stdout and "calcola (locale)" in r.stdout
        assert "[calcola_scadenza · fastapi:" in r.stdout and "[get_weather · mcp:" in r.stdout
        assert "endpoint=/scadenza" in (CARTELLA / "logs" / "servizio_api.log").read_text(encoding="utf-8")
        log_server = (CARTELLA / "logs" / "server_mcp.log").read_text(encoding="utf-8")
        assert "tool=get_weather" in log_server and "esito=ok" in log_server
        # La richiesta di nota dipende dal modello: si osserva e si riporta, la persistenza la prova il test sotto.
        chiamata = "[add_note · mcp:" in r.stdout and "operazione=aggiunta" in log_server
        print(f"  osservazione: il modello ha chiamato davvero add_note: {chiamata}")


def test_note_persistono_nel_volume():
    """Una nota scritta dentro un container resta sull'host e si rilegge da un container nuovo."""
    scrivi = "from logica.note import ArchivioNote; print(ArchivioNote().aggiungi('nota scritta nel container')['id'])"
    leggi = "from logica.note import ArchivioNote; print([n['testo'] for n in ArchivioNote().elenca()['note']])"
    with cartelle_dell_utente_da_parte():
        primo = compose_con_varianti("", "python", "-c", scrivi)
        assert primo.returncode == 0 and primo.stdout.strip().endswith("1")
        assert (CARTELLA / "archivio" / "note.sqlite3").exists()  # sull'host, tramite il volume
        secondo = compose_con_varianti("", "python", "-c", leggi)  # container nuovo, stesso archivio
        assert secondo.returncode == 0 and "nota scritta nel container" in secondo.stdout


def test_meteo_senza_rete_nel_container():
    """Container senza interfaccia di rete: lo strumento del meteo (chiamato direttamente, senza server MCP)
    risponde subito «Servizio meteo non disponibile», distinto da «Città non trovata».

    Non copre il caso «rete presente ma Internet assente», in cui scatta la scadenza totale di 8 s:
    quella è verificata dai test automatici (tests/test_meteo.py).
    """
    codice = (
        "import httpx, time; from logica.meteo import meteo_attuale; from logica.errori import ErroreStrumento\n"
        "inizio = time.monotonic()\n"
        "try:\n    meteo_attuale('Udine', httpx.Client())\n    print('INATTESO: risposta ricevuta')\n"
        "except ErroreStrumento as e:\n    print('ERRORE:', e)\n"
        "print('DURATA:', round(time.monotonic() - inizio, 1))\n"
    )
    inizio = time.monotonic()
    r = esegui(["docker", "run", "--rm", "--network", "none", IMMAGINE, "python", "-c", codice], ingresso="")
    assert r.returncode == 0
    assert "ERRORE: Servizio meteo" in r.stdout and "Città non trovata" not in r.stdout
    durata = float(r.stdout.split("DURATA:")[1].split()[0])
    assert durata <= 8.5 and time.monotonic() - inizio < 60
