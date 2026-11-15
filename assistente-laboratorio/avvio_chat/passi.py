"""I passi dell'avvio della chat nel browser: Docker, LM Studio, container, agente, back-end.

Ogni passo riceve come parametri ciò che tocca il mondo esterno (esecuzione dei comandi, richieste
HTTP, orologio, scrittura nella finestra): così i test li provano senza Docker e senza LM Studio.
Tutti gli errori sono ErroreAvvio, con un messaggio che dice che cosa sistemare.
"""

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import webbrowser
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping, TextIO

from assistente.avvio_server import CARTELLA_PROGETTO, processo_in_attesa
from assistente.configurazione import carica_configurazione, leggi_porta, leggi_porta_agente
from assistente.errori import ErroreAvvio
from assistente.modello import verifica_server
from assistente.registro import CARTELLA_LOG
from servizio_backend.configurazione import carica_configurazione_backend

ATTESA_DOCKER = 180.0
ATTESA_LMSTUDIO = 60.0
ATTESA_CONTAINER = 600.0  # la prima volta l'immagine della pagina va costruita
ATTESA_SERVIZIO = 60.0
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


def leggi_salute(url: str, limite: float) -> dict:
    """GET <url>/salute: restituisce la risposta solo se dice `"stato": "ok"`, altrimenti solleva."""
    with urllib.request.urlopen(url + "/salute", timeout=limite) as risposta:
        dati = json.load(risposta)
    if not isinstance(dati, dict) or dati.get("stato") != "ok":
        raise ValueError(f"risposta inattesa da {url}/salute: {dati!r}")
    return dati


def _in_ascolto(porta: int, limite: float = 0.3) -> bool:
    """Vero se qualcuno accetta connessioni sulla porta. Su Windows una porta chiusa risponde solo
    dopo un paio di secondi: con questo controllo breve non li si aspetta a ogni tentativo."""
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=limite):
            return True
    except OSError:
        return False


def _risponde(porta: int, salute: Callable[[str, float], dict]) -> bool:
    if not _in_ascolto(porta):
        return False
    try:
        salute(f"http://127.0.0.1:{porta}", 2.0)
    except Exception:
        return False
    return True


@contextmanager
def servizio(
    descrizione: str,
    comando: list[str],
    porta: int,
    variabile_porta: str,
    log: Path,
    scrivi: Scrivi,
    *,
    salute: Callable[[str, float], dict] = leggi_salute,
    attesa: float = ATTESA_SERVIZIO,
) -> Iterator[bool]:
    """Un servizio HTTP con /salute: se risponde già non lo tocca, altrimenti lo avvia e all'uscita lo spegne.

    Restituisce True solo se l'ha avviato questa funzione: ciò che era già acceso resta acceso.
    """
    if _risponde(porta, salute):
        yield False
        return

    def pronto(limite: float) -> dict:
        if not _in_ascolto(porta):
            raise ConnectionError(f"nessuno in ascolto sulla porta {porta}")
        return salute(f"http://127.0.0.1:{porta}", limite)

    scrivi(f"      Avvio il {descrizione}...")
    with processo_in_attesa(
        comando, porta, log, pronto, descrizione=descrizione, variabile_porta=variabile_porta, attesa=attesa
    ):
        yield True


def avvia_chat(
    imp: Impostazioni,
    ingresso: TextIO,
    scrivi: Scrivi,
    *,
    esegui: Esegui = esegui_comando,
    apri: Callable[[str], object] = webbrowser.open,
    comando_agente: list[str] | None = None,
    comando_backend: list[str] | None = None,
    cartella_log: Path = CARTELLA_LOG,
    senza_browser: bool = False,
    risponde: Callable[[str], bool] = lmstudio_risponde,
    verifica: Callable[[str, str], None] = verifica_server,
    lms: Callable[[], str | None] = trova_lms,
    pausa: Callable[[float], None] = time.sleep,
    orologio: Callable[[], float] = time.monotonic,
    salute: Callable[[str, float], dict] = leggi_salute,
) -> int:
    """Accende ciò che manca, apre la chat nel browser e aspetta «esci»; poi spegne solo ciò che ha avviato."""
    scrivi("Assistente del laboratorio · avvio della chat")
    assicura_docker(esegui, scrivi, pausa=pausa, orologio=orologio)
    assicura_lmstudio(imp, esegui, scrivi, risponde=risponde, verifica=verifica, lms=lms, pausa=pausa, orologio=orologio)
    assicura_container(esegui, scrivi)
    with ExitStack() as pila:  # all'uscita spegne in ordine inverso: prima il back-end, poi l'agente
        if _in_ascolto(imp.porta_mcp) and not _risponde(imp.porta_agente, salute):
            raise ErroreAvvio(
                f"La porta {imp.porta_mcp} (MCP_PORTA) è occupata ma il servizio dell'agente è spento: "
                "probabilmente è aperta la chat da terminale (python -m assistente). Chiudila e riprova."
            )
        agente_avviato = pila.enter_context(
            servizio(
                "servizio dell'agente",
                comando_agente or [sys.executable, "-m", "servizio_agente"],
                imp.porta_agente,
                "AGENTE_PORTA",
                cartella_log / "avvio_agente.log",
                scrivi,
                salute=salute,
            )
        )
        scrivi(f"[4/5] Agente: {'pronto su' if agente_avviato else 'già acceso su'} {imp.url_agente}")
        backend_avviato = pila.enter_context(
            servizio(
                "back-end delle chat",
                comando_backend or [sys.executable, "-m", "servizio_backend"],
                imp.porta_backend,
                "BACKEND_PORTA",
                cartella_log / "avvio_backend.log",
                scrivi,
                salute=salute,
            )
        )
        scrivi(f"[5/5] Back-end: {'pronto su' if backend_avviato else 'già acceso su'} {imp.url_backend}")
        if senza_browser:
            scrivi(f"La chat risponde su {imp.url_chat} (browser non aperto).")
        else:
            scrivi(f"Apro {imp.url_chat}")
            apri(imp.url_chat)
        if not (agente_avviato or backend_avviato):
            scrivi("Agente e back-end erano già accesi: non li ho avviati io, quindi restano accesi.")
            return 0
        scrivi("La chat è accesa. Per spegnerla scrivi «esci» e premi Invio, oppure chiudi questa finestra.")
        try:
            for riga in ingresso:
                if riga.strip().lower() == "esci":
                    break
        except KeyboardInterrupt:
            pass
        scrivi("Spengo ciò che ho avviato...")
    scrivi("Spento. Database e pagina restano accesi in Docker: per fermarli, docker compose stop.")
    return 0
