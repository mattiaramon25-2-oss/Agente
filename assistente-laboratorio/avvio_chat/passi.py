"""I passi dell'avvio della chat nel browser: Docker, LM Studio, container, agente, back-end.

Ogni passo riceve come parametri ciò che tocca il mondo esterno (esecuzione dei comandi, richieste
HTTP, orologio, scrittura nella finestra): così i test li provano senza Docker e senza LM Studio.
Tutti gli errori sono ErroreAvvio, con un messaggio che dice che cosa sistemare.
"""

import shutil
import subprocess
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from assistente.avvio_server import CARTELLA_PROGETTO
from assistente.configurazione import carica_configurazione, leggi_porta, leggi_porta_agente
from assistente.errori import ErroreAvvio
from assistente.modello import verifica_server
from servizio_backend.configurazione import carica_configurazione_backend

ATTESA_DOCKER = 180.0
ATTESA_LMSTUDIO = 60.0
ATTESA_CONTAINER = 600.0  # la prima volta l'immagine della pagina va costruita
PORTA_FRONTEND_PREDEFINITA = 8780
CODICE_SCADUTO = 124

COMANDO_DOCKER_INFO = ["docker", "info", "--format", "{{.ServerVersion}}"]
COMANDO_DOCKER_AVVIO = ["docker", "desktop", "start"]
COMANDO_CONTAINER = ["docker", "compose", "up", "-d", "--wait", "database", "frontend"]


@dataclass(frozen=True)
class Impostazioni:
    base_url: str
    modello: str
    porta_mcp: int
    porta_agente: int
    porta_backend: int
    porta_frontend: int

    @property
    def url_agente(self) -> str:
        return f"http://127.0.0.1:{self.porta_agente}"

    @property
    def url_backend(self) -> str:
        return f"http://127.0.0.1:{self.porta_backend}"

    @property
    def url_chat(self) -> str:
        return f"http://127.0.0.1:{self.porta_frontend}"


def carica_impostazioni(env: Mapping[str, str]) -> Impostazioni:
    """Le stesse variabili che leggono l'agente e il back-end, più FRONTEND_PORTA (predefinita 8780)."""
    config = carica_configurazione(env)
    porta_agente = leggi_porta_agente(env, config)
    backend = carica_configurazione_backend(env)
    testo = (env.get("FRONTEND_PORTA") or "").strip() or str(PORTA_FRONTEND_PREDEFINITA)
    return Impostazioni(
        base_url=config.base_url,
        modello=config.modello,
        porta_mcp=config.porta_mcp,
        porta_agente=porta_agente,
        porta_backend=backend.porta,
        porta_frontend=leggi_porta("FRONTEND_PORTA", testo),
    )


@dataclass(frozen=True)
class Esito:
    codice: int
    uscita: str  # stdout e stderr insieme


Esegui = Callable[[list[str], float], Esito]
Scrivi = Callable[[str], None]


def esegui_comando(comando: list[str], limite: float) -> Esito:
    """Esegue `comando` nella cartella del progetto e aspetta al massimo `limite` secondi.

    L'uscita va in un file temporaneo e non in una pipe: `docker desktop start` e `lms server start`
    lasciano accesi programmi che terrebbero aperta la pipe, e la lettura non finirebbe mai.
    """
    with tempfile.TemporaryFile() as uscita:
        try:
            fatto = subprocess.run(
                comando, cwd=CARTELLA_PROGETTO, stdin=subprocess.DEVNULL, stdout=uscita, stderr=subprocess.STDOUT, timeout=limite
            )
        except subprocess.TimeoutExpired:
            return Esito(CODICE_SCADUTO, f"nessuna risposta entro {limite:g} secondi")
        uscita.seek(0)
        testo = uscita.read().decode("utf-8", errors="replace").replace("\r\n", "\n")
    return Esito(fatto.returncode, testo)


def _ultime_righe(testo: str, quante: int = 8) -> str:
    righe = [riga for riga in testo.splitlines() if riga.strip()]
    return "\n".join(righe[-quante:])


def assicura_docker(
    esegui: Esegui,
    scrivi: Scrivi,
    *,
    attesa: float = ATTESA_DOCKER,
    pausa: Callable[[float], None] = time.sleep,
    orologio: Callable[[], float] = time.monotonic,
) -> None:
    """Se il motore di Docker non risponde, avvia Docker Desktop e aspetta che risponda."""
    try:
        if esegui(COMANDO_DOCKER_INFO, 20.0).codice != 0:
            scrivi("      Docker è spento: lo accendo, può volerci un minuto...")
            scadenza = orologio() + attesa
            esegui(COMANDO_DOCKER_AVVIO, attesa)
            while esegui(COMANDO_DOCKER_INFO, 20.0).codice != 0:
                if orologio() >= scadenza:
                    raise ErroreAvvio(
                        f"Docker Desktop non risponde dopo {attesa:g} secondi: aprilo a mano, aspetta che sia pronto e riprova."
                    )
                pausa(2.0)
    except FileNotFoundError:
        raise ErroreAvvio("Docker non è installato o non è nel PATH: installa Docker Desktop e riprova.") from None
    scrivi("[1/5] Docker: acceso")


def lmstudio_risponde(base_url: str, limite: float = 3.0) -> bool:
    """Vero se il server di LM Studio risponde a GET /models, qualunque sia l'elenco dei modelli."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=limite) as risposta:
            return risposta.status == 200
    except (OSError, ValueError):
        return False


def trova_lms() -> str | None:
    """Il comando `lms` di LM Studio: nel PATH, oppure nella cartella dove LM Studio lo installa."""
    nel_path = shutil.which("lms")
    if nel_path:
        return nel_path
    predefinito = Path.home() / ".lmstudio" / "bin" / "lms.exe"
    return str(predefinito) if predefinito.exists() else None


def assicura_lmstudio(
    imp: Impostazioni,
    esegui: Esegui,
    scrivi: Scrivi,
    *,
    risponde: Callable[[str], bool] = lmstudio_risponde,
    verifica: Callable[[str, str], None] = verifica_server,
    lms: Callable[[], str | None] = trova_lms,
    attesa: float = ATTESA_LMSTUDIO,
    pausa: Callable[[float], None] = time.sleep,
    orologio: Callable[[], float] = time.monotonic,
) -> None:
    """Se il server di LM Studio non risponde lo avvia con `lms server start`; poi controlla il modello.

    Il modello non lo sceglie questo programma: se quello del .env manca, l'errore è quello di sempre.
    """
    if not risponde(imp.base_url):
        aiuto = "apri LM Studio, attiva il server e riprova."
        programma = lms()
        if programma is None:
            raise ErroreAvvio(f"LM Studio non risponde su {imp.base_url} e il comando lms non c'è: {aiuto}")
        scrivi("      Il server di LM Studio è spento: lo accendo...")
        scadenza = orologio() + attesa
        try:
            esegui([programma, "server", "start"], attesa)
        except FileNotFoundError:
            raise ErroreAvvio(f"LM Studio non risponde su {imp.base_url} e il comando lms non parte: {aiuto}") from None
        while not risponde(imp.base_url):
            if orologio() >= scadenza:
                raise ErroreAvvio(f"LM Studio non risponde su {imp.base_url} dopo {attesa:g} secondi: {aiuto}")
            pausa(1.0)
    verifica(imp.base_url, imp.modello)
    scrivi(f"[2/5] LM Studio: risponde, modello {imp.modello} presente")


def assicura_container(esegui: Esegui, scrivi: Scrivi) -> None:
    """Accende i container del database e della pagina e aspetta che siano pronti."""
    scrivi("      Accendo database e pagina (la prima volta ci vuole qualche minuto)...")
    esito = esegui(COMANDO_CONTAINER, ATTESA_CONTAINER)
    if esito.codice != 0:
        raise ErroreAvvio(
            "docker compose up non è riuscito per database e frontend. Ultime righe:\n" + _ultime_righe(esito.uscita)
        )
    scrivi("[3/5] Database e pagina: accesi")
