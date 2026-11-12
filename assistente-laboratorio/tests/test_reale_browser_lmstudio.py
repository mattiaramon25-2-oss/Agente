"""Prova reale dello step 8: la chat nel browser con LM Studio, agente vero, back-end, PostgreSQL di prova e nginx.

Si attiva solo con: python -m pytest --lmstudio --docker tests/test_reale_browser_lmstudio.py -v -s
Serve Chromium: python -m playwright install chromium
"""

import time

import pytest
from playwright.sync_api import expect, sync_playwright

from assistente.varianti import origini, parametri
from servizio_agente.app import crea_app as crea_app_agente
from servizio_backend.app import crea_app as crea_app_backend
from servizio_backend.archivio import ArchivioPostgres
from servizio_backend.client_agente import ClientAgente
from tests.frontend_prova import Servito, frontend_di_prova
from tests.postgres_prova import database_di_prova
from tests.reale import ambiente_reale

pytestmark = [pytest.mark.lmstudio, pytest.mark.docker]

ATTESA_STRUMENTO = 300000
ATTESA_RISPOSTA = 300000
DOMANDA = "Quanto fa (3+4)*2?"


@pytest.fixture(scope="module")
def url_chat():
    with ambiente_reale() as (grafo, fuso_utente, strumenti), database_di_prova() as db:
        agente = Servito(crea_app_agente(grafo, fuso=fuso_utente, modello="reale", origini=origini(strumenti), parametri=parametri(strumenti)))
        agente.avvia()
        archivio = ArchivioPostgres(db.dsn)
        archivio.prepara()
        backend = Servito(crea_app_backend(archivio, ClientAgente(f"http://127.0.0.1:{agente.porta}")))
        backend.avvia()
        try:
            with frontend_di_prova(backend.porta) as url:
                yield url
        finally:
            backend.ferma()
            agente.ferma()


def test_calcolo_dal_browser_con_testo_a_pezzi(url_chat):
    with sync_playwright() as p:
        p.selectors.set_test_id_attribute("data-test")
        browser = p.chromium.launch(headless=True)
        try:
            pagina = browser.new_context().new_page()
            pagina.goto(url_chat)
            pagina.get_by_test_id("casella").fill(DOMANDA)
            pagina.get_by_test_id("invia").click()

            riga = pagina.get_by_test_id("riga-strumento").first
            expect(riga).to_be_visible(timeout=ATTESA_STRUMENTO)
            assert "calcola" in riga.inner_text()
            print("\n  riga strumento:", riga.inner_text())

            # Istantanee del testo dell'assistente finché il messaggio è in corso (aria-busy).
            istantanee: list[str] = []
            fine = time.monotonic() + ATTESA_RISPOSTA / 1000
            terminato = False
            while time.monotonic() < fine:
                stato = pagina.evaluate(
                    """() => {
                        const m = [...document.querySelectorAll('[data-test="messaggio-assistente"]')].pop();
                        return m ? {testo: m.textContent, inCorso: m.getAttribute('aria-busy') === 'true'} : null;
                    }"""
                )
                if stato:
                    testo = stato["testo"].strip()
                    if testo and (not istantanee or istantanee[-1] != testo):
                        istantanee.append(testo)
                    if not stato["inCorso"] and testo:
                        terminato = True
                        break
                time.sleep(0.1)
            assert terminato, f"il turno non è finito entro il tempo: {istantanee}"

            print(f"  istantanee distinte del testo: {len(istantanee)}")
            for i in (0, len(istantanee) // 2, -1):
                print(f"    [{i}] {istantanee[i]!r}")
            risposta = pagina.get_by_test_id("messaggio-assistente").last.inner_text()
            print("  risposta finale:", risposta)
            assert "14" in risposta
            assert len(istantanee) >= 2, f"il testo non è comparso a pezzi: {istantanee}"
        finally:
            browser.close()
