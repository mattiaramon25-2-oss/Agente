"""I passi dell'avvio della chat nel browser: Docker, LM Studio, container, la chat che risponde.

Ogni passo riceve come parametri ciò che tocca il mondo esterno (esecuzione dei comandi, richieste
HTTP, orologio, scrittura nella finestra): così i test li provano senza Docker e senza LM Studio.
Tutti gli errori sono ErroreAvvio, con un messaggio che dice che cosa sistemare.

Solo libreria standard (più i moduli di configurazione, che non importano altro): su Windows Smart
App Control può bloccare le DLL di psycopg, e il launcher deve partire lo stesso. Agente e back-end
girano nei container, quindi qui non servono né psycopg né langchain né httpx.
"""

import http.client
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, TextIO

from assistente.configurazione import carica_configurazione, leggi_porta, leggi_porta_agente
from assistente.errori import ErroreAvvio
from assistente.lmstudio import verifica_server
from avvio_chat.console import installa_chiusura_console
from servizio_backend.configurazione import leggi_valori_backend

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent

ATTESA_DOCKER = 180.0
ATTESA_LMSTUDIO = 60.0
ATTESA_CONTAINER = 600.0  # la prima volta le immagini vanno costruite
ATTESA_CHAT = 90.0  # l'agente deve scoprire gli strumenti MCP
LIMITE_COMPOSE = 120.0  # docker compose ps e docker compose stop
LIMITE_SALUTE = 5.0
PORTA_FRONTEND_PREDEFINITA = 8780
CODICE_SCADUTO = 124

COMANDO_DOCKER_INFO = ["docker", "info", "--format", "{{.ServerVersion}}"]
COMANDO_DOCKER_AVVIO = ["docker", "desktop", "start"]
COMANDO_SERVIZI_ACCESI = ["docker", "compose", "ps", "--status", "running", "--services"]
COMANDO_CONTAINER = ["docker", "compose", "up", "-d", "--wait"]
COMANDO_FERMA = ["docker", "compose", "stop"]

# I servizi che il launcher spegne se li ha accesi lui; database e pagina restano accesi.
SERVIZI_DELLA_CHAT = ("agente", "backend")
PORTA_OCCUPATA = ("port is already allocated", "ports are not available")


@dataclass(frozen=True)
class Impostazioni:
    base_url: str
    modello: str
    porta_agente: int
    porta_frontend: int

    @property
    def url_chat(self) -> str:
        return f"http://127.0.0.1:{self.porta_frontend}"

    @property
    def url_salute(self) -> str:
        """Lo stato del back-end attraverso nginx, cioè lo stesso percorso che usa la pagina."""
        return self.url_chat + "/api/salute"


def carica_impostazioni(env: Mapping[str, str]) -> Impostazioni:
    """Controlla le stesse variabili dell'agente e del back-end, più FRONTEND_PORTA (predefinita 8780).

    Agente e back-end le leggono da soli nei container: qui si controllano prima di accenderli, così
    un .env incompleto si scopre subito e con il messaggio della configurazione.
    """
    config = carica_configurazione(env)
    porta_agente = leggi_porta_agente(env, config)
    leggi_valori_backend(env)
    testo = (env.get("FRONTEND_PORTA") or "").strip() or str(PORTA_FRONTEND_PREDEFINITA)
    return Impostazioni(
        base_url=config.base_url,
        modello=config.modello,
        porta_agente=porta_agente,
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


def _uscita_del_comando(nome: str, esito: Esito) -> str:
    """Per i messaggi d'errore: che cosa ha risposto il comando di avvio, se non è andato a buon fine."""
    if esito.codice == 0 or not esito.uscita.strip():
        return ""
    return f"\nIl comando {nome} ha risposto:\n{_ultime_righe(esito.uscita)}"


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
            avvio = esegui(COMANDO_DOCKER_AVVIO, attesa)
            while esegui(COMANDO_DOCKER_INFO, 20.0).codice != 0:
                if orologio() >= scadenza:
                    raise ErroreAvvio(
                        f"Docker Desktop non risponde dopo {attesa:g} secondi: aprilo a mano, aspetta che sia pronto e riprova."
                        + _uscita_del_comando("docker desktop start", avvio)
                    )
                pausa(2.0)
    except FileNotFoundError:
        raise ErroreAvvio("Docker non è installato o non è nel PATH: installa Docker Desktop e riprova.") from None
    scrivi("[1/4] Docker: acceso")


def lmstudio_risponde(base_url: str, limite: float = 3.0) -> bool:
    """Vero se il server di LM Studio risponde a GET /models, qualunque sia l'elenco dei modelli."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/models", timeout=limite) as risposta:
            return risposta.status == 200
    except (OSError, ValueError, http.client.HTTPException):  # anche una risposta che non è HTTP
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
            avvio = esegui([programma, "server", "start"], attesa)
        except FileNotFoundError:
            raise ErroreAvvio(f"LM Studio non risponde su {imp.base_url} e il comando lms non parte: {aiuto}") from None
        while not risponde(imp.base_url):
            if orologio() >= scadenza:
                raise ErroreAvvio(
                    f"LM Studio non risponde su {imp.base_url} dopo {attesa:g} secondi: {aiuto}"
                    + _uscita_del_comando("lms server start", avvio)
                )
            pausa(1.0)
    verifica(imp.base_url, imp.modello)
    scrivi(f"[2/4] LM Studio: risponde, modello {imp.modello} presente")


def servizi_accesi(esegui: Esegui) -> set[str]:
    """I servizi di Compose in esecuzione: `docker compose ps` ne stampa uno per riga."""
    esito = esegui(COMANDO_SERVIZI_ACCESI, LIMITE_COMPOSE)
    if esito.codice != 0:
        raise ErroreAvvio("docker compose ps non è riuscito. Ultime righe:\n" + _ultime_righe(esito.uscita))
    return {riga.strip() for riga in esito.uscita.splitlines() if riga.strip()}


def assicura_container(esegui: Esegui, scrivi: Scrivi, *, ricostruisci: bool = False, porta_agente: int | None = None) -> None:
    """Accende i quattro container (database, agente, back-end, pagina) e aspetta che siano pronti.

    Con `ricostruisci` le immagini si ricostruiscono: serve dopo un aggiornamento del codice. Se
    Compose dice che la porta dell'agente (`porta_agente`) è occupata, il messaggio dice perché di solito lo è.
    """
    scrivi("      Accendo i container (la prima volta ci vuole qualche minuto)...")
    esito = esegui(COMANDO_CONTAINER + (["--build"] if ricostruisci else []), ATTESA_CONTAINER)
    if esito.codice != 0:
        messaggio = "docker compose up non è riuscito. Ultime righe:\n" + _ultime_righe(esito.uscita)
        occupata = any(frase in esito.uscita.lower() for frase in PORTA_OCCUPATA)
        if occupata and porta_agente is not None and re.search(rf":{porta_agente}\b", esito.uscita):
            messaggio += (
                f"\nLa porta {porta_agente} (AGENTE_PORTA) è occupata: probabilmente c'è ancora un agente acceso "
                "fuori da Docker (python -m servizio_agente). Chiudilo e riprova."
            )
        raise ErroreAvvio(messaggio)
    scrivi("[3/4] Container: accesi")


def leggi_salute(url: str, limite: float) -> dict:
    """GET `url` e la risposta JSON, che deve essere un oggetto."""
    with urllib.request.urlopen(url, timeout=limite) as risposta:
        dati = json.load(risposta)
    if not isinstance(dati, dict):
        raise ValueError(f"risposta inattesa da {url}: {dati!r}")
    return dati


def _log(servizio: str) -> str:
    return f"docker compose logs --tail 30 {servizio}"


def _chat_che_non_risponde(imp: Impostazioni, attesa: float, dati: dict | None, errore: Exception | None) -> str:
    """Che cosa manca, dopo l'attesa, e il comando per leggerne il log."""
    inizio = f"La chat non risponde del tutto dopo {attesa:g} secondi ({imp.url_salute}): "
    if dati is None or dati.get("stato") != "ok":
        motivo = f"{errore}" if dati is None else f"risposta {dati!r}"
        return inizio + f"il back-end non è pronto ({motivo}). Per leggerne il log: {_log('backend')}"
    mancanti = [nome for nome in ("database", "agente") if dati.get(nome) != "ok"]
    dettagli = ", ".join(f"{nome} {dati.get(nome)}" for nome in mancanti)
    comandi = " e ".join(_log(nome) for nome in mancanti)
    return inizio + f"{dettagli}. Per leggerne il log: {comandi}"


def attendi_chat(
    imp: Impostazioni,
    scrivi: Scrivi,
    *,
    salute: Callable[[str, float], dict] = leggi_salute,
    attesa: float = ATTESA_CHAT,
    pausa: Callable[[float], None] = time.sleep,
    orologio: Callable[[], float] = time.monotonic,
) -> None:
    """Aspetta che /api/salute, attraverso nginx, dica `stato`, `database` e `agente` tutti "ok"."""
    scadenza = orologio() + attesa
    while True:
        dati, errore = None, None
        try:
            dati = salute(imp.url_salute, LIMITE_SALUTE)
        except (OSError, ValueError, http.client.HTTPException) as eccezione:  # anche il 502 di nginx
            errore = eccezione
        if isinstance(dati, dict) and all(dati.get(nome) == "ok" for nome in ("stato", "database", "agente")):
            scrivi("[4/4] Chat: risponde (database ok, agente ok)")
            return
        if orologio() >= scadenza:
            raise ErroreAvvio(_chat_che_non_risponde(imp, attesa, dati if isinstance(dati, dict) else None, errore))
        pausa(1.0)


def ferma_servizi(servizi: list[str], esegui: Esegui) -> None:
    """`docker compose stop` dei servizi indicati: i container restano, pronti per la prossima volta."""
    comando = COMANDO_FERMA + list(servizi)
    esito = esegui(comando, LIMITE_COMPOSE)
    if esito.codice != 0:
        raise ErroreAvvio(
            "docker compose stop non è riuscito. Ultime righe:\n"
            + _ultime_righe(esito.uscita)
            + f"\nPer fermarli a mano: {' '.join(comando)}"
        )


def avvia_chat(
    imp: Impostazioni,
    ingresso: TextIO,
    scrivi: Scrivi,
    *,
    esegui: Esegui = esegui_comando,
    apri: Callable[[str], object] = webbrowser.open,
    senza_browser: bool = False,
    ricostruisci: bool = False,
    risponde: Callable[[str], bool] = lmstudio_risponde,
    verifica: Callable[[str, str], None] = verifica_server,
    lms: Callable[[], str | None] = trova_lms,
    pausa: Callable[[float], None] = time.sleep,
    orologio: Callable[[], float] = time.monotonic,
    salute: Callable[[str, float], dict] = leggi_salute,
    alla_chiusura: Callable[[list[str]], None] = installa_chiusura_console,
) -> int:
    """Accende ciò che manca, apre la chat nel browser e aspetta «esci»; poi ferma solo ciò che ha acceso."""
    scrivi("Assistente del laboratorio · avvio della chat")
    assicura_docker(esegui, scrivi, pausa=pausa, orologio=orologio)
    assicura_lmstudio(imp, esegui, scrivi, risponde=risponde, verifica=verifica, lms=lms, pausa=pausa, orologio=orologio)
    prima = servizi_accesi(esegui)
    # Prima il back-end, poi l'agente da cui dipende.
    accesi_da_me = [servizio for servizio in reversed(SERVIZI_DELLA_CHAT) if servizio not in prima]
    assicura_container(esegui, scrivi, ricostruisci=ricostruisci, porta_agente=imp.porta_agente)
    try:
        if accesi_da_me:
            alla_chiusura(COMANDO_FERMA + accesi_da_me)  # anche chiudendo la finestra con la X
        attendi_chat(imp, scrivi, salute=salute, pausa=pausa, orologio=orologio)
        if senza_browser:
            scrivi(f"La chat risponde su {imp.url_chat} (browser non aperto).")
        else:
            scrivi(f"Apro {imp.url_chat}")
            apri(imp.url_chat)
        if not accesi_da_me:
            scrivi("Agente e back-end erano già accesi: non li ho accesi io, quindi restano accesi.")
            return 0
        scrivi("La chat è accesa. Per spegnerla scrivi «esci» e premi Invio, oppure chiudi questa finestra.")
        try:
            for riga in ingresso:
                if riga.strip().lower() == "esci":
                    break
        except KeyboardInterrupt:
            pass
    finally:
        if accesi_da_me:
            scrivi(f"Fermo ciò che ho acceso ({', '.join(accesi_da_me)})...")
            ferma_servizi(accesi_da_me, esegui)
    scrivi("Fermato. Database e pagina restano accesi in Docker: per fermarli, docker compose stop.")
    return 0
