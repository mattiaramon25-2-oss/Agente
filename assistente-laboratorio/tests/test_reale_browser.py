"""Evidenza dello step 8: la chat nel browser, con container nginx vero, back-end vero, PostgreSQL di prova e agente finto.

Si attiva solo con: python -m pytest --docker tests/test_reale_browser.py -v -s
Serve Chromium: python -m playwright install chromium
"""

import json
import socket
import threading
import time

import psycopg
import pytest
import uvicorn
from langchain_core.messages import AIMessage, SystemMessage
from playwright.sync_api import expect, sync_playwright

from assistente.ambito import Ambito
from assistente.grafo import crea_grafo
from assistente.router import DecisioneRouter
from servizio_agente.app import crea_app as crea_app_agente
from servizio_backend.app import crea_app as crea_app_backend
from servizio_backend.archivio import ArchivioPostgres
from servizio_backend.client_agente import ClientAgente
from tests.finti import ModelloFinto, RouterFinto, chiamata, strumento_finto
from tests.frontend_prova import frontend_di_prova
from tests.postgres_prova import database_di_prova, svuota

pytestmark = pytest.mark.docker

ATTESA = 30000
DOMANDA = "Quanto fa (3+4)*2?"


def _porta_libera() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Servito:
    """Un'app servita da uvicorn in un thread su una porta fissa: si può fermare e riavviare sulla stessa porta."""

    def __init__(self, app):
        self.app = app
        self.porta = _porta_libera()
        self.server: uvicorn.Server | None = None
        self.filo: threading.Thread | None = None

    def avvia(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", port=self.porta, log_level="warning"))
        self.filo = threading.Thread(target=self.server.run, daemon=True)
        self.filo.start()
        fine = time.monotonic() + 30
        while not self.server.started and time.monotonic() < fine:
            time.sleep(0.05)
        assert self.server.started, "il server non è partito"

    def ferma(self) -> None:
        if self.server is not None:
            self.server.should_exit = True
            self.filo.join(timeout=15)
            self.server = None


class Ambiente:
    def __init__(self, url, modello, router, agente, backend, dsn):
        self.url = url
        self.modello = modello
        self.router = router
        self.agente = agente
        self.backend = backend
        self.dsn = dsn

    def prepara(self, *risposte_modello: AIMessage, turni: int = 4) -> None:
        """Riparte da zero: archivio vuoto, risposte del modello e del router preparate, chiamate azzerate."""
        svuota(self.dsn)
        self.modello.risposte = list(risposte_modello)
        self.modello.chiamate.clear()
        self.router.risposte = [DecisioneRouter(categoria="conversazione", motivo="ok") for _ in range(turni)]


def _calcolo() -> list[AIMessage]:
    return [chiamata("calcola", {"espressione": "(3+4)*2"}), AIMessage("Il risultato è **14**.")]


@pytest.fixture(scope="module")
def ambiente():
    modello = ModelloFinto([])
    router = RouterFinto([])
    grafo = crea_grafo(
        modello,
        [strumento_finto(json.dumps({"risultato": 14}), nome="calcola")],
        router,
        Ambito(("calcoli",), ("poesie",), "Prova un altro provider."),
    )
    agente = Servito(crea_app_agente(grafo, fuso="Europe/Rome", modello="finto", origini={}, parametri={}))
    with database_di_prova() as db:
        archivio = ArchivioPostgres(db.dsn)
        archivio.prepara()
        agente.avvia()
        backend = Servito(crea_app_backend(archivio, ClientAgente(f"http://127.0.0.1:{agente.porta}")))
        backend.avvia()
        try:
            with frontend_di_prova(backend.porta) as url:
                yield Ambiente(url, modello, router, agente, backend, db.dsn)
        finally:
            backend.ferma()
            agente.ferma()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        p.selectors.set_test_id_attribute("data-test")
        b = p.chromium.launch(headless=True)
        try:
            yield b
        finally:
            b.close()


@pytest.fixture
def pagina(browser, ambiente):
    contesto = browser.new_context()
    contesto.set_default_timeout(ATTESA)
    p = contesto.new_page()
    p.goto(ambiente.url)
    yield p
    contesto.close()


def _invia(pagina, testo: str) -> None:
    pagina.get_by_test_id("casella").fill(testo)
    pagina.get_by_test_id("invia").click()


def test_conversazione_completa(ambiente, pagina):
    ambiente.prepara(*_calcolo())
    pagina.reload()
    _invia(pagina, DOMANDA)
    expect(pagina.get_by_test_id("riga-strumento")).to_be_visible(timeout=ATTESA)
    risposta = pagina.get_by_test_id("messaggio-assistente").last
    expect(risposta.locator("strong")).to_have_text("14", timeout=ATTESA)
    assert risposta.locator("strong").inner_html() == "14"
    expect(pagina.get_by_test_id("chat").first).to_have_text(DOMANDA, timeout=ATTESA)
    print("\n  riga strumento:", pagina.get_by_test_id("riga-strumento").first.inner_text())
    print("  risposta:", risposta.inner_text())

    pagina.reload()
    expect(pagina.get_by_test_id("chat").first).to_have_text(DOMANDA, timeout=ATTESA)
    pagina.get_by_test_id("chat").first.click()
    expect(pagina.get_by_test_id("messaggio-utente")).to_have_count(1, timeout=ATTESA)
    expect(pagina.get_by_test_id("messaggio-assistente")).to_have_count(1, timeout=ATTESA)
    expect(pagina.get_by_test_id("messaggio-utente")).to_have_text(DOMANDA)
    expect(pagina.get_by_test_id("messaggio-assistente").locator("strong")).to_have_text("14")
    print("  dopo il ricaricamento la chat c'è, con i due messaggi")


def test_progetto_con_istruzioni(ambiente, pagina):
    ambiente.prepara(AIMessage("Va bene."))
    pagina.reload()
    pagina.get_by_label("Nuovo progetto", exact=True).click()
    pagina.get_by_placeholder("Nome del progetto").fill("Inglese")
    pagina.get_by_placeholder("Nome del progetto").press("Enter")
    istruzioni = pagina.get_by_test_id("istruzioni")
    expect(istruzioni).to_be_visible(timeout=ATTESA)
    istruzioni.fill("Rispondi sempre in inglese.")
    pagina.get_by_test_id("salva-istruzioni").click()
    expect(pagina.get_by_role("status")).to_have_text("Salvate", timeout=ATTESA)
    pagina.get_by_role("button", name="Nuova chat in questo progetto").click()
    _invia(pagina, "Ciao")
    expect(pagina.get_by_test_id("messaggio-assistente").last).to_contain_text("Va bene.", timeout=ATTESA)

    prima = ambiente.modello.chiamate[0][0]
    print("\n  messaggio di sistema ricevuto dall'agente finto, in coda:", repr(prima.content[-80:]))
    assert isinstance(prima, SystemMessage)
    assert prima.content.endswith("Rispondi sempre in inglese.")


def test_ricerca_e_eliminazione(ambiente, pagina):
    ambiente.prepara(*_calcolo())
    pagina.reload()
    _invia(pagina, DOMANDA)
    expect(pagina.get_by_test_id("messaggio-assistente").last.locator("strong")).to_have_text("14", timeout=ATTESA)
    expect(pagina.get_by_test_id("chat").first).to_have_text(DOMANDA, timeout=ATTESA)

    pagina.get_by_test_id("ricerca").fill("14")
    expect(pagina.get_by_test_id("risultato").first).to_be_visible(timeout=ATTESA)
    print("\n  risultati della ricerca «14»:", pagina.get_by_test_id("risultato").count())
    pagina.get_by_test_id("ricerca").fill("")
    expect(pagina.get_by_test_id("chat").first).to_be_visible(timeout=ATTESA)

    riga = pagina.locator(".voce", has=pagina.get_by_test_id("chat")).first
    riga.hover()
    riga.get_by_test_id("menu").click()
    pagina.get_by_test_id("elimina").click()
    pagina.get_by_test_id("conferma").click()
    expect(pagina.get_by_test_id("chat")).to_have_count(0, timeout=ATTESA)
    pagina.reload()
    expect(pagina.get_by_text("Nessuna chat.")).to_be_visible(timeout=ATTESA)
    with psycopg.connect(ambiente.dsn) as c:
        assert c.execute("SELECT count(*) FROM chat").fetchone()[0] == 0


def test_errore_agente_spento(ambiente, pagina):
    ambiente.prepara()
    pagina.reload()
    ambiente.agente.ferma()
    try:
        _invia(pagina, "Ciao, ci sei?")
        errore = pagina.get_by_test_id("errore-turno")
        expect(errore).to_be_visible(timeout=ATTESA)
        expect(errore).to_contain_text("non risponde")
        print("\n  errore mostrato:", errore.inner_text())
        expect(pagina.get_by_test_id("casella")).to_have_value("Ciao, ci sei?", timeout=ATTESA)
    finally:
        ambiente.agente.avvia()


def test_striscia_back_end_spento(ambiente, pagina):
    ambiente.prepara()
    pagina.reload()
    ambiente.backend.ferma()
    try:
        pagina.reload()
        striscia = pagina.get_by_test_id("striscia-backend")
        expect(striscia).to_be_visible(timeout=ATTESA)
        expect(striscia).to_have_text("Il back-end non risponde: avvialo con python -m servizio_backend.")
        print("\n  striscia:", striscia.inner_text())
    finally:
        ambiente.backend.avvia()
    inizio = time.monotonic()
    expect(pagina.get_by_test_id("striscia-backend")).to_be_hidden(timeout=15000)
    print(f"  striscia sparita dopo {time.monotonic() - inizio:.1f} s dal riavvio")


def test_installabile(ambiente, pagina):
    risposta = pagina.request.get(f"{ambiente.url}/manifest.webmanifest")
    assert risposta.status == 200
    manifest = risposta.json()
    print("\n  manifest:", {k: manifest.get(k) for k in ("name", "display", "start_url")})
    assert manifest["name"]
    pronto = pagina.evaluate("navigator.serviceWorker.ready.then(r => r.active ? r.active.state : 'nessuno')")
    print("  service worker:", pronto)
    assert pronto in ("activating", "activated")
