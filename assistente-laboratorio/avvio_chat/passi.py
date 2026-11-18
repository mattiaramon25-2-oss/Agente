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
import sys
import tempfile
import time
import urllib.error
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
STATI_DI_NGINX = (502, 504)  # le risposte di nginx quando il back-end non c'è o non risponde
SUGGERIMENTO_RICOSTRUISCI = "Se hai appena aggiornato il codice: avvia-chat.cmd --ricostruisci"


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


def _ferma_i_figli(comando: list[str]) -> bool:
    """Vero per `docker compose up`: alla scadenza va chiuso tutto l'albero dei processi.

    `docker compose` è docker.exe più il plugin docker-compose.exe: chiudendo solo il primo, il
    plugin andrebbe avanti e accenderebbe i container dopo che il launcher ha rinunciato. Gli altri
    comandi restano come sono: `docker desktop start` e `lms server start` lasciano accesi i loro
    programmi, e un `docker compose stop` rimasto a metà è meglio che finisca.
    """
    return list(comando[:3]) == COMANDO_CONTAINER[:3]


def _termina(processo: subprocess.Popen, con_i_figli: bool) -> None:
    """Chiude il comando; con `con_i_figli` anche i processi che ha avviato."""
    if con_i_figli and sys.platform == "win32":
        try:  # taskkill /T percorre l'albero a partire dal padre: va chiamato finché il padre è vivo
            subprocess.run(
                ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30.0,
            )
        except (OSError, subprocess.SubprocessError):
            pass  # resta la chiusura del solo comando, qui sotto
    processo.kill()
    processo.wait()


def esegui_comando(comando: list[str], limite: float, *, con_i_figli: bool | None = None) -> Esito:
    """Esegue `comando` nella cartella del progetto e aspetta al massimo `limite` secondi.

    L'uscita va in un file temporaneo e non in una pipe: `docker desktop start` e `lms server start`
    lasciano accesi programmi che terrebbero aperta la pipe, e la lettura non finirebbe mai.

    Alla scadenza il comando viene chiuso e l'esito conserva ciò che aveva scritto, seguito da
    «nessuna risposta entro N secondi». Con `con_i_figli` si chiudono anche i processi che il comando
    ha avviato; se non è indicato, vale solo per `docker compose up` (vedi `_ferma_i_figli`).
    """
    if con_i_figli is None:
        con_i_figli = _ferma_i_figli(comando)
    scaduto = False
    with tempfile.TemporaryFile() as uscita:
        processo = subprocess.Popen(
            comando, cwd=CARTELLA_PROGETTO, stdin=subprocess.DEVNULL, stdout=uscita, stderr=subprocess.STDOUT
        )
        try:
            processo.wait(timeout=limite)
        except subprocess.TimeoutExpired:
            scaduto = True
            _termina(processo, con_i_figli)
        except BaseException:  # un Ctrl+C: come con subprocess.run, il comando non resta lì senza nessuno che lo aspetta
            _termina(processo, con_i_figli)
            raise
        uscita.seek(0)
        testo = uscita.read().decode("utf-8", errors="replace").replace("\r\n", "\n")
    if scaduto:
        righe = [testo.rstrip("\n"), f"nessuna risposta entro {limite:g} secondi"]
        return Esito(CODICE_SCADUTO, "\n".join(riga for riga in righe if riga))
    return Esito(processo.returncode, testo)


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


def _errore_del_backend(errore: Exception | None) -> str | None:
    """Se a rispondere con un errore è stato il back-end, che cosa ha detto: «HTTP 503: Il database non risponde…».

    502 e 504 non contano: li risponde nginx quando il back-end non c'è o non risponde. Gli altri
    5xx sono del back-end: `/salute` risponde 503, con il motivo nel corpo, se non raggiunge il database.
    """
    if not isinstance(errore, urllib.error.HTTPError) or errore.code < 500 or errore.code in STATI_DI_NGINX:
        return None
    try:
        corpo = json.loads(errore.read().decode("utf-8", errors="replace"))
    except (OSError, ValueError):
        corpo = None
    motivo = corpo.get("errore") if isinstance(corpo, dict) else None
    return f"HTTP {errore.code}: {motivo}" if motivo else f"HTTP {errore.code}"


def _chat_che_non_risponde(imp: Impostazioni, attesa: float, dati: dict | None, errore: Exception | None) -> str:
    """Che cosa manca, dopo l'attesa, e il comando per leggerne il log."""
    inizio = f"La chat non risponde del tutto dopo {attesa:g} secondi ({imp.url_salute}): "
    del_backend = _errore_del_backend(errore) if dati is None else None
    if del_backend is not None:
        return inizio + (
            f"database non raggiungibile (il back-end risponde {del_backend}). "
            f"Per leggerne il log: {_log('database')} e {_log('backend')}"
        )
    if dati is None or dati.get("stato") != "ok":
        motivo = f"{errore}" if dati is None else f"risposta {dati!r}"
        # Un'immagine del front-end rimasta allo step 8 inoltra /api all'host: 502 anche col back-end acceso.
        return inizio + (
            f"il back-end non è pronto ({motivo}). Per leggerne il log: {_log('backend')}. "
            f"{SUGGERIMENTO_RICOSTRUISCI}"
        )
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
        except (OSError, ValueError, http.client.HTTPException) as eccezione:  # anche il 502 di nginx e il 503 del back-end
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


def _avvisa(scrivi: Scrivi, testo: str) -> None:
    """Una riga che informa soltanto: se la finestra non si può più scrivere, lo spegnimento va avanti."""
    try:
        scrivi(testo)
    except (OSError, ValueError):
        pass


def ferma_cio_che_ho_acceso(servizi: list[str], esegui: Esegui, scrivi: Scrivi) -> None:
    """Ferma i servizi accesi dal launcher; un Ctrl+C durante lo spegnimento non lo lascia a metà.

    Su Windows il Ctrl+C arriva anche a `docker compose stop`, che si interrompe: per questo si
    riprova una volta, con un comando nuovo. Se anche quello viene interrotto è un errore, con il
    comando da dare a mano: non un «Interrotto.» con i container ancora accesi.
    """
    try:
        _avvisa(scrivi, f"Fermo ciò che ho acceso ({', '.join(servizi)})...")
        ferma_servizi(servizi, esegui)
    except KeyboardInterrupt:
        try:
            _avvisa(scrivi, "      Sto ancora fermando i container: aspetta qualche secondo...")
            ferma_servizi(servizi, esegui)
        except KeyboardInterrupt:
            raise ErroreAvvio(
                f"Lo spegnimento è stato interrotto: i container accesi da questa finestra ({', '.join(servizi)}) "
                f"possono essere ancora accesi.\nPer fermarli a mano: {' '.join(COMANDO_FERMA + list(servizi))}"
            ) from None


def _ferma_dopo_un_errore(servizi: list[str], esegui: Esegui, scrivi: Scrivi) -> str | None:
    """Lo spegnimento dopo un errore: se non riesce, non deve prendere il posto dell'errore che c'è già.

    Restituisce la riga da aggiungere a quell'errore, con il comando da dare a mano; None se i servizi sono fermi.
    """
    try:
        ferma_cio_che_ho_acceso(servizi, esegui, scrivi)
    except Exception:  # qualunque cosa sia andata storta nello spegnimento, conta l'errore di prima
        return f"Inoltre non sono riuscito a fermare {', '.join(servizi)}: per fermarli a mano, {' '.join(COMANDO_FERMA + list(servizi))}"
    return None


def descrivi_errore(errore: BaseException) -> str:
    """Un errore non previsto, in una riga che dice sempre qualcosa: il messaggio e il tipo, o solo il tipo."""
    messaggio, tipo = str(errore).strip(), type(errore).__name__
    return f"{messaggio} ({tipo})" if messaggio else tipo


def _errore_di_prima(errore: BaseException) -> str:
    if isinstance(errore, KeyboardInterrupt):
        return "Interrotto."
    return str(errore) if isinstance(errore, ErroreAvvio) else descrivi_errore(errore)


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
    try:
        if accesi_da_me:
            # Prima di `up`, la fase più lunga: vale anche chiudendo la finestra con la X mentre i container partono.
            alla_chiusura(COMANDO_FERMA + accesi_da_me)
        assicura_container(esegui, scrivi, ricostruisci=ricostruisci, porta_agente=imp.porta_agente)
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
    except BaseException as errore:
        # Anche dopo un `up` fallito a metà o un Ctrl+C: ciò che ho acceso non resta acceso di nascosto.
        non_fermati = _ferma_dopo_un_errore(accesi_da_me, esegui, scrivi) if accesi_da_me else None
        if non_fermati is None:
            raise
        raise ErroreAvvio(f"{_errore_di_prima(errore)}\n{non_fermati}") from None
    ferma_cio_che_ho_acceso(accesi_da_me, esegui, scrivi)
    scrivi("Fermato. Database e pagina restano accesi in Docker: per fermarli, docker compose stop.")
    return 0
