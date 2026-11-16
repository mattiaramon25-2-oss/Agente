"""Avvio della chat con un doppio clic: i passi di avvio_chat, senza Docker e senza LM Studio."""

import io
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from assistente.configurazione import ErroreConfigurazione
from assistente.errori import ErroreAvvio
from assistente.lmstudio import ErroreServer
from avvio_chat import __main__ as principale
from avvio_chat import passi
from avvio_chat.passi import Esito, Impostazioni

ENV = {
    "LMSTUDIO_BASE_URL": "http://localhost:1234/v1",
    "LMSTUDIO_MODEL": "finto",
    "MCP_PORTA": "8765",
    "VARIANTE_CALCOLATRICE": "mcp",
    "VARIANTE_SCADENZE": "mcp",
    "AGENTE_PORTA": "8767",
    "BACKEND_PORTA": "8768",
    "POSTGRES_USER": "utente",
    "POSTGRES_PASSWORD": "segreta",
    "POSTGRES_DB": "dati",
}

DOCKER_INFO = ("docker", "info")
DOCKER_AVVIO = ("docker", "desktop", "start")
COMPOSE_PS = ("docker", "compose", "ps")
COMPOSE_UP = ("docker", "compose", "up")
COMPOSE_STOP = ("docker", "compose", "stop")

CARTELLA_PROGETTO = Path(__file__).resolve().parent.parent


class EseguiFinto:
    """Risponde ai comandi da un copione: per ogni inizio di comando una lista di esiti (l'ultimo si ripete)."""

    def __init__(self, copione):
        self.copione = {inizio: list(risposte) for inizio, risposte in copione.items()}
        self.comandi: list[list[str]] = []
        self.limiti: list[float] = []

    def __call__(self, comando, limite):
        self.comandi.append(list(comando))
        self.limiti.append(limite)
        for inizio, risposte in self.copione.items():
            if tuple(comando[: len(inizio)]) == inizio:
                risposta = risposte.pop(0) if len(risposte) > 1 else risposte[0]
                if isinstance(risposta, BaseException):
                    raise risposta
                return risposta
        raise AssertionError(f"comando non previsto dal copione: {comando}")

    def chiamati(self, inizio) -> int:
        return sum(1 for comando in self.comandi if tuple(comando[: len(inizio)]) == inizio)

    def con_inizio(self, inizio) -> list[list[str]]:
        return [comando for comando in self.comandi if tuple(comando[: len(inizio)]) == inizio]


class Tempo:
    """Orologio finto: `pausa` fa avanzare il tempo invece di aspettare."""

    def __init__(self):
        self.adesso = 0.0

    def orologio(self) -> float:
        return self.adesso

    def pausa(self, secondi: float) -> None:
        self.adesso += secondi


class Righe:
    """Raccoglie ciò che il programma scrive nella finestra."""

    def __init__(self):
        self.righe: list[str] = []

    def __call__(self, testo: str) -> None:
        self.righe.append(testo)

    @property
    def testo(self) -> str:
        return "\n".join(self.righe)


def in_sequenza(valori):
    """Una funzione che restituisce i valori uno alla volta; l'ultimo si ripete."""
    coda = list(valori)
    return lambda *argomenti, **opzioni: coda.pop(0) if len(coda) > 1 else coda[0]


def impostazioni(**cambi) -> Impostazioni:
    valori = dict(base_url="http://localhost:1234/v1", modello="finto", porta_agente=8767, porta_frontend=8780)
    return Impostazioni(**{**valori, **cambi})


def in_ascolto(porta: int, limite: float = 0.3) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", porta), timeout=limite):
            return True
    except OSError:
        return False


def porte_libere(quante: int) -> list[int]:
    """Porte libere e diverse tra loro, scelte dal sistema operativo."""
    prese = [socket.socket() for _ in range(quante)]
    try:
        for presa in prese:
            presa.bind(("127.0.0.1", 0))
        return [presa.getsockname()[1] for presa in prese]
    finally:
        for presa in prese:
            presa.close()


SALUTE_OK = {"stato": "ok", "database": "ok", "agente": "ok"}


# --- Nessuna libreria che Smart App Control può bloccare ---


def test_nessuna_libreria_bloccabile_dopo_l_import():
    """Su Windows Smart App Control può bloccare le DLL di psycopg: il launcher non deve caricarle."""
    codice = (
        "import sys, avvio_chat.__main__; "
        "print(sorted(m for m in ('psycopg', 'langchain_core', 'langchain_openai', 'httpx') if m in sys.modules))"
    )
    fatto = subprocess.run(
        [sys.executable, "-c", codice], cwd=CARTELLA_PROGETTO, capture_output=True, text=True, timeout=60
    )
    assert fatto.returncode == 0, fatto.stderr
    assert fatto.stdout.strip() == "[]"


# --- Impostazioni ---


def test_impostazioni_dal_env():
    imp = passi.carica_impostazioni(ENV)
    assert (imp.porta_agente, imp.porta_frontend) == (8767, 8780)
    assert imp.base_url == "http://localhost:1234/v1" and imp.modello == "finto"
    assert imp.url_chat == "http://127.0.0.1:8780"
    assert imp.url_salute == "http://127.0.0.1:8780/api/salute"
    assert passi.carica_impostazioni({**ENV, "FRONTEND_PORTA": "8790"}).url_chat == "http://127.0.0.1:8790"


def test_impostazioni_senza_password_del_database():
    with pytest.raises(ErroreConfigurazione) as errore:
        passi.carica_impostazioni({**ENV, "POSTGRES_PASSWORD": ""})
    assert "POSTGRES_PASSWORD" in str(errore.value)


def test_frontend_porta_non_valida():
    with pytest.raises(ErroreConfigurazione) as errore:
        passi.carica_impostazioni({**ENV, "FRONTEND_PORTA": "ottanta"})
    assert "FRONTEND_PORTA" in str(errore.value)


# --- Docker ---


def test_docker_acceso_non_avvia_niente():
    esegui = EseguiFinto({DOCKER_INFO: [Esito(0, "29.1.0")]})
    righe = Righe()
    passi.assicura_docker(esegui, righe)
    assert esegui.chiamati(DOCKER_AVVIO) == 0
    assert "[1/4] Docker: acceso" in righe.testo


def test_docker_spento_lo_avvia_e_aspetta():
    tempo = Tempo()
    esegui = EseguiFinto({DOCKER_INFO: [Esito(1, "errore"), Esito(1, "errore"), Esito(0, "29.1.0")], DOCKER_AVVIO: [Esito(0, "")]})
    righe = Righe()
    passi.assicura_docker(esegui, righe, pausa=tempo.pausa, orologio=tempo.orologio)
    assert esegui.chiamati(DOCKER_AVVIO) == 1
    assert ["docker", "desktop", "start"] in esegui.comandi
    assert esegui.chiamati(DOCKER_INFO) == 3
    assert "lo accendo" in righe.testo and "[1/4] Docker: acceso" in righe.testo


def test_docker_che_non_parte():
    tempo = Tempo()
    esegui = EseguiFinto({DOCKER_INFO: [Esito(1, "errore")], DOCKER_AVVIO: [Esito(1, "riga inutile\nlicenza non accettata\n")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_docker(esegui, Righe(), pausa=tempo.pausa, orologio=tempo.orologio)
    assert "Docker Desktop non risponde" in str(errore.value) and "180" in str(errore.value)
    assert "docker desktop start" in str(errore.value) and "licenza non accettata" in str(errore.value)
    assert tempo.adesso >= passi.ATTESA_DOCKER


def test_docker_non_installato():
    esegui = EseguiFinto({DOCKER_INFO: [FileNotFoundError("docker")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_docker(esegui, Righe())
    assert "Docker non è installato" in str(errore.value)


# --- LM Studio ---


def test_lmstudio_acceso_non_chiama_lms():
    esegui = EseguiFinto({})
    verificati = []
    righe = Righe()
    passi.assicura_lmstudio(
        impostazioni(), esegui, righe, risponde=lambda url: True, verifica=lambda url, modello: verificati.append((url, modello)), lms=lambda: "lms"
    )
    assert esegui.comandi == []
    assert verificati == [("http://localhost:1234/v1", "finto")]
    assert "[2/4] LM Studio: risponde, modello finto presente" in righe.testo


def test_lmstudio_verifica_predefinita_senza_langchain():
    from assistente import lmstudio

    assert passi.assicura_lmstudio.__kwdefaults__["verifica"] is lmstudio.verifica_server
    assert passi.avvia_chat.__kwdefaults__["verifica"] is lmstudio.verifica_server


def test_lmstudio_spento_avvia_il_server():
    tempo = Tempo()
    esegui = EseguiFinto({("lms-finto",): [Esito(0, "")]})
    verificati = []
    righe = Righe()
    passi.assicura_lmstudio(
        impostazioni(),
        esegui,
        righe,
        risponde=in_sequenza([False, False, True]),
        verifica=lambda url, modello: verificati.append(modello),
        lms=lambda: "lms-finto",
        pausa=tempo.pausa,
        orologio=tempo.orologio,
    )
    assert esegui.comandi == [["lms-finto", "server", "start"]]
    assert verificati == ["finto"]
    assert "lo accendo" in righe.testo and "[2/4] LM Studio: risponde" in righe.testo


def test_lmstudio_spento_senza_lms():
    esegui = EseguiFinto({})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_lmstudio(impostazioni(), esegui, Righe(), risponde=lambda url: False, verifica=lambda *a: None, lms=lambda: None)
    assert "apri LM Studio" in str(errore.value) and "http://localhost:1234/v1" in str(errore.value)
    assert esegui.comandi == []


def test_lmstudio_che_non_parte():
    tempo = Tempo()
    esegui = EseguiFinto({("lms-finto",): [Esito(1, "porta 1234 occupata\n")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_lmstudio(
            impostazioni(), esegui, Righe(), risponde=lambda url: False, verifica=lambda *a: None, lms=lambda: "lms-finto",
            pausa=tempo.pausa, orologio=tempo.orologio,
        )
    assert "LM Studio non risponde" in str(errore.value) and "60" in str(errore.value)
    assert "lms server start" in str(errore.value) and "porta 1234 occupata" in str(errore.value)


def test_modello_mancante_non_tocca_lms():
    esegui = EseguiFinto({})

    def verifica(url, modello):
        raise ErroreServer("Il modello 'finto' non è disponibile su LM Studio.")

    with pytest.raises(ErroreServer) as errore:
        passi.assicura_lmstudio(impostazioni(), esegui, Righe(), risponde=lambda url: True, verifica=verifica, lms=lambda: "lms-finto")
    assert "non è disponibile" in str(errore.value)
    assert esegui.comandi == []


def test_lmstudio_risponde_falso_se_non_e_http():
    """Se sulla porta risponde qualcosa che non parla HTTP, niente traceback: semplicemente non è LM Studio."""
    with socket.socket() as ascolto:
        ascolto.bind(("127.0.0.1", 0))
        ascolto.listen()
        porta = ascolto.getsockname()[1]

        def rispondi():
            connessione, _ = ascolto.accept()
            with connessione:
                connessione.recv(1024)
                connessione.sendall(b"questo non e' HTTP\r\n\r\n")

        threading.Thread(target=rispondi, daemon=True).start()
        assert passi.lmstudio_risponde(f"http://127.0.0.1:{porta}/v1", limite=3.0) is False


# --- Container ---


def test_servizi_accesi_una_riga_per_servizio():
    esegui = EseguiFinto({COMPOSE_PS: [Esito(0, "agente\n\ndatabase\r\n  frontend  \n")]})
    assert passi.servizi_accesi(esegui) == {"agente", "database", "frontend"}
    assert esegui.comandi == [["docker", "compose", "ps", "--status", "running", "--services"]]


def test_servizi_accesi_compose_che_fallisce():
    esegui = EseguiFinto({COMPOSE_PS: [Esito(1, "no configuration file provided: not found\n")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.servizi_accesi(esegui)
    assert "docker compose ps" in str(errore.value) and "no configuration file" in str(errore.value)


def test_ricostruisci():
    esegui = EseguiFinto({COMPOSE_UP: [Esito(0, "")]})
    righe = Righe()
    passi.assicura_container(esegui, righe)
    passi.assicura_container(esegui, righe, ricostruisci=True)
    assert esegui.comandi == [
        ["docker", "compose", "up", "-d", "--wait"],
        ["docker", "compose", "up", "-d", "--wait", "--build"],
    ]
    assert esegui.limiti == [600.0, 600.0]
    assert "la prima volta" in righe.testo and "[3/4] Container: accesi" in righe.testo


def test_container_che_falliscono():
    esegui = EseguiFinto({COMPOSE_UP: [Esito(1, "riga inutile\ncontainer assistente-backend-1 is unhealthy\n")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_container(esegui, Righe())
    assert "docker compose up" in str(errore.value) and "is unhealthy" in str(errore.value)
    assert "servizio_agente" not in str(errore.value)


def test_ferma_servizi():
    esegui = EseguiFinto({COMPOSE_STOP: [Esito(0, "")]})
    passi.ferma_servizi(["backend", "agente"], esegui)
    assert esegui.comandi == [["docker", "compose", "stop", "backend", "agente"]]


def test_esegui_comando_vero():
    assert passi.esegui_comando([sys.executable, "-c", "print('ciao')"], 20.0) == Esito(0, "ciao\n")
    lento = passi.esegui_comando([sys.executable, "-c", "import time; time.sleep(5)"], 0.2)
    assert lento.codice == 124 and "0.2 secondi" in lento.uscita
    with pytest.raises(FileNotFoundError):
        passi.esegui_comando(["programma-che-non-esiste-di-sicuro"], 5.0)


def test_esegui_comando_nella_cartella_del_progetto():
    esito = passi.esegui_comando([sys.executable, "-c", "import os; print(os.getcwd())"], 20.0)
    assert Path(esito.uscita.strip()) == passi.CARTELLA_PROGETTO == CARTELLA_PROGETTO


def test_esegui_comando_non_aspetta_i_programmi_lasciati_accesi():
    """`docker desktop start` e `lms server start` lasciano acceso un programma che eredita l'uscita:
    leggendo da una pipe, il comando sembrerebbe finire solo quando quel programma si chiude."""
    codice = "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(6)']); print('avviato')"
    inizio = time.monotonic()
    esito = passi.esegui_comando([sys.executable, "-c", codice], 20.0)
    assert esito == Esito(0, "avviato\n")
    assert time.monotonic() - inizio < 4


# --- La chat risponde attraverso nginx ---


def test_leggi_salute_vera():
    corpo = json.dumps(SALUTE_OK).encode("utf-8")

    class Gestore(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200 if self.path == "/api/salute" else 404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def log_message(self, *argomenti):
            pass

    server = HTTPServer(("127.0.0.1", 0), Gestore)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        assert passi.leggi_salute(f"http://127.0.0.1:{server.server_port}/api/salute", 2.0) == SALUTE_OK
    finally:
        server.shutdown()
        server.server_close()


def test_salute_senza_nessuno_in_ascolto(porta):
    with pytest.raises(OSError):
        passi.leggi_salute(f"http://127.0.0.1:{porta}/api/salute", 0.5)


def test_attendi_chat_riprova_finche_tutto_ok():
    tempo = Tempo()
    righe = Righe()
    chiesti = []
    risposte = in_sequenza([OSError("502"), {"stato": "ok", "database": "ok", "agente": "non raggiungibile"}, SALUTE_OK])

    def salute(url, limite):
        chiesti.append(url)
        risposta = risposte()
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta

    passi.attendi_chat(impostazioni(), righe, salute=salute, pausa=tempo.pausa, orologio=tempo.orologio)
    assert chiesti == ["http://127.0.0.1:8780/api/salute"] * 3
    assert "[4/4] Chat: risponde (database ok, agente ok)" in righe.testo


def test_attendi_chat_database_che_non_risponde():
    tempo = Tempo()
    with pytest.raises(ErroreAvvio) as errore:
        passi.attendi_chat(
            impostazioni(), Righe(), salute=lambda url, limite: {"stato": "ok", "database": "non raggiungibile", "agente": "ok"},
            pausa=tempo.pausa, orologio=tempo.orologio,
        )
    assert "database" in str(errore.value) and "docker compose logs --tail 30 database" in str(errore.value)
    assert tempo.adesso >= passi.ATTESA_CHAT


# --- Il programma intero, con Docker, LM Studio e la chat finti ---


class IngressoInterrotto:
    """Come un Ctrl+C mentre il programma aspetta «esci»."""

    def __iter__(self):
        return self

    def __next__(self):
        raise KeyboardInterrupt


class IngressoVietato:
    """Il programma non deve mettersi ad aspettare: se legge, la prova fallisce."""

    def __iter__(self):
        raise AssertionError("il programma si è messo ad aspettare «esci»")


def scena(*, accesi: str = "", up: Esito = Esito(0, ""), salute=None):
    """Le dipendenze finte di un computer pronto: `accesi` è ciò che stampa `docker compose ps`."""
    tempo = Tempo()
    aperti: list[str] = []
    chiusure: list[list[str]] = []
    esegui = EseguiFinto(
        {DOCKER_INFO: [Esito(0, "29.1.0")], COMPOSE_PS: [Esito(0, accesi)], COMPOSE_UP: [up], COMPOSE_STOP: [Esito(0, "")]}
    )
    opzioni = dict(
        esegui=esegui,
        apri=aperti.append,
        risponde=lambda url: True,
        verifica=lambda url, modello: None,
        lms=lambda: None,
        pausa=tempo.pausa,
        orologio=tempo.orologio,
        salute=salute or (lambda url, limite: dict(SALUTE_OK)),
        alla_chiusura=chiusure.append,
    )
    return SimpleNamespace(imp=impostazioni(), esegui=esegui, aperti=aperti, chiusure=chiusure, righe=Righe(), opzioni=opzioni, tempo=tempo)


def test_avvio_completo_ed_esci():
    s = scena()
    codice = passi.avvia_chat(s.imp, io.StringIO("ciao\nESCI \n"), s.righe, **s.opzioni)
    assert codice == 0
    testo = s.righe.testo
    for passo in ("[1/4] Docker", "[2/4] LM Studio", "[3/4] Container: accesi", "[4/4] Chat: risponde (database ok, agente ok)"):
        assert passo in testo
    assert "La chat è accesa" in testo and "«esci»" in testo
    assert s.aperti == [s.imp.url_chat]
    assert s.esegui.comandi[-1] == ["docker", "compose", "stop", "backend", "agente"]
    assert s.esegui.chiamati(COMPOSE_STOP) == 1
    assert s.chiusure == [["docker", "compose", "stop", "backend", "agente"]]


def test_tutto_gia_acceso_apre_solo_il_browser():
    s = scena(accesi="agente\nbackend\n")
    codice = passi.avvia_chat(s.imp, IngressoVietato(), s.righe, **s.opzioni)
    assert codice == 0
    assert s.esegui.chiamati(COMPOSE_STOP) == 0
    assert s.chiusure == []
    assert s.aperti == [s.imp.url_chat]
    assert "già accesi" in s.righe.testo and "La chat è accesa" not in s.righe.testo


def test_agente_gia_acceso_si_ferma_solo_il_backend():
    s = scena(accesi="agente\ndatabase\n")
    assert passi.avvia_chat(s.imp, io.StringIO("esci\n"), s.righe, **s.opzioni) == 0
    assert s.esegui.con_inizio(COMPOSE_STOP) == [["docker", "compose", "stop", "backend"]]
    assert s.chiusure == [["docker", "compose", "stop", "backend"]]


def test_avvia_chat_ricostruisci():
    s = scena()
    passi.avvia_chat(s.imp, io.StringIO("esci\n"), s.righe, ricostruisci=True, **s.opzioni)
    assert s.esegui.con_inizio(COMPOSE_UP) == [["docker", "compose", "up", "-d", "--wait", "--build"]]
    s = scena()
    passi.avvia_chat(s.imp, io.StringIO("esci\n"), s.righe, **s.opzioni)
    assert s.esegui.con_inizio(COMPOSE_UP) == [["docker", "compose", "up", "-d", "--wait"]]


def test_chat_che_non_risponde_spegne_cio_che_ho_acceso():
    s = scena(salute=lambda url, limite: {"stato": "ok", "database": "ok", "agente": "non raggiungibile"})
    with pytest.raises(ErroreAvvio) as errore:
        passi.avvia_chat(s.imp, io.StringIO("esci\n"), s.righe, **s.opzioni)
    assert "agente" in str(errore.value) and "docker compose logs --tail 30 agente" in str(errore.value)
    assert s.esegui.con_inizio(COMPOSE_STOP) == [["docker", "compose", "stop", "backend", "agente"]]
    assert s.aperti == []
    assert s.tempo.adesso >= passi.ATTESA_CHAT


def test_chat_senza_backend_indica_i_log_del_backend():
    def salute(url, limite):
        raise OSError("HTTP Error 502: Bad Gateway")

    s = scena(salute=salute)
    with pytest.raises(ErroreAvvio) as errore:
        passi.avvia_chat(s.imp, io.StringIO("esci\n"), s.righe, **s.opzioni)
    assert "docker compose logs --tail 30 backend" in str(errore.value)
    assert "502" in str(errore.value)
    assert s.esegui.chiamati(COMPOSE_STOP) == 1
    assert s.aperti == []


@pytest.mark.parametrize(
    "uscita",
    [
        "Error response from daemon: Bind for 127.0.0.1:8767 failed: port is already allocated\n",
        "Error response from daemon: Ports are not available: exposing port TCP 127.0.0.1:8767 -> 0.0.0.0:0\n",
    ],
)
def test_porta_dell_agente_occupata(uscita):
    s = scena(up=Esito(1, uscita))
    with pytest.raises(ErroreAvvio) as errore:
        passi.avvia_chat(s.imp, IngressoVietato(), s.righe, **s.opzioni)
    assert "python -m servizio_agente" in str(errore.value)
    assert "8767" in str(errore.value)
    assert s.aperti == []


def test_porta_della_pagina_occupata_non_accusa_l_agente():
    s = scena(up=Esito(1, "Bind for 127.0.0.1:8780 failed: port is already allocated\n"))
    with pytest.raises(ErroreAvvio) as errore:
        passi.avvia_chat(s.imp, IngressoVietato(), s.righe, **s.opzioni)
    assert "port is already allocated" in str(errore.value) and "servizio_agente" not in str(errore.value)


@pytest.mark.parametrize("ingresso", [io.StringIO(""), IngressoInterrotto()], ids=["fine-input", "ctrl-c"])
def test_fine_input_e_ctrl_c_fermano_come_esci(ingresso):
    s = scena()
    assert passi.avvia_chat(s.imp, ingresso, s.righe, **s.opzioni) == 0
    assert s.esegui.con_inizio(COMPOSE_STOP) == [["docker", "compose", "stop", "backend", "agente"]]


def test_senza_browser():
    s = scena()
    assert passi.avvia_chat(s.imp, io.StringIO("esci\n"), s.righe, senza_browser=True, **s.opzioni) == 0
    assert s.aperti == []
    assert "Apro" not in s.righe.testo and s.imp.url_chat in s.righe.testo


# --- python -m avvio_chat ---


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setattr(principale, "dotenv_values", lambda *a, **k: {})  # niente .env reale
    for nome, valore in ENV.items():
        monkeypatch.setenv(nome, valore)
    monkeypatch.delenv("FRONTEND_PORTA", raising=False)


def test_main_senza_env_esce_con_1(ambiente, monkeypatch, capsys):
    for nome in ENV:
        monkeypatch.delenv(nome, raising=False)
    assert principale.main([], io.StringIO("")) == 1
    assert "Errore: Variabili d'ambiente mancanti" in capsys.readouterr().err


def test_main_riporta_gli_errori_di_avvio(ambiente, monkeypatch, capsys):
    def fallisce(*argomenti, **opzioni):
        raise ErroreAvvio("prova")

    monkeypatch.setattr(principale, "avvia_chat", fallisce)
    assert principale.main([], io.StringIO("")) == 1
    assert "Errore: prova" in capsys.readouterr().err


def test_main_riporta_gli_errori_del_server(ambiente, monkeypatch, capsys):
    def fallisce(*argomenti, **opzioni):
        raise ErroreServer("modello assente")

    monkeypatch.setattr(principale, "avvia_chat", fallisce)
    assert principale.main([], io.StringIO("")) == 1
    assert "Errore: modello assente" in capsys.readouterr().err


def test_main_errore_inatteso_senza_traceback(ambiente, monkeypatch, capsys):
    def guasto(*argomenti, **opzioni):
        raise RuntimeError("guasto")

    monkeypatch.setattr(principale, "avvia_chat", guasto)
    assert principale.main([], io.StringIO("")) == 1
    errore = capsys.readouterr().err
    assert "Errore inatteso: guasto" in errore and "Traceback" not in errore


def test_main_passa_senza_browser(ambiente, monkeypatch, capsys):
    ricevute = []

    def finta(imp, ingresso, scrivi, **opzioni):
        ricevute.append((imp.url_chat, opzioni))
        scrivi("riga di prova")
        return 0

    monkeypatch.setattr(principale, "avvia_chat", finta)
    assert principale.main(["--senza-browser"], io.StringIO("")) == 0
    assert principale.main([], io.StringIO("")) == 0
    assert [opzioni["senza_browser"] for _, opzioni in ricevute] == [True, False]
    assert ricevute[0][0] == "http://127.0.0.1:8780"
    assert "riga di prova" in capsys.readouterr().out


def test_main_passa_ricostruisci(ambiente, monkeypatch):
    ricevute = []
    monkeypatch.setattr(principale, "avvia_chat", lambda imp, ingresso, scrivi, **opzioni: ricevute.append(opzioni) or 0)
    assert principale.main(["--ricostruisci"], io.StringIO("")) == 0
    assert principale.main([], io.StringIO("")) == 0
    assert [opzioni["ricostruisci"] for opzioni in ricevute] == [True, False]


def test_main_ctrl_c_durante_l_avvio(ambiente, monkeypatch):
    def interrotto(*argomenti, **opzioni):
        raise KeyboardInterrupt

    monkeypatch.setattr(principale, "avvia_chat", interrotto)
    assert principale.main([], io.StringIO("")) == 0


def test_main_non_mette_la_password_nell_ambiente(monkeypatch):
    """Le impostazioni vengono dal .env, ma la password non deve passare ai programmi che restano accesi."""
    monkeypatch.setattr(principale, "dotenv_values", lambda *a, **k: {**ENV, "VUOTA": None})
    for nome in ENV:
        monkeypatch.delenv(nome, raising=False)
    ricevute = []
    monkeypatch.setattr(principale, "avvia_chat", lambda imp, ingresso, scrivi, **opzioni: ricevute.append(imp) or 0)
    assert principale.main([], io.StringIO("")) == 0
    assert ricevute[0].porta_agente == 8767
    assert "POSTGRES_PASSWORD" not in os.environ


def test_main_l_ambiente_vince_sul_file(monkeypatch):
    monkeypatch.setattr(principale, "dotenv_values", lambda *a, **k: {**ENV, "FRONTEND_PORTA": "8790"})
    for nome in ENV:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("FRONTEND_PORTA", "8791")
    ricevute = []
    monkeypatch.setattr(principale, "avvia_chat", lambda imp, ingresso, scrivi, **opzioni: ricevute.append(imp) or 0)
    assert principale.main([], io.StringIO("")) == 0
    assert ricevute[0].url_chat == "http://127.0.0.1:8791"


def test_il_programma_non_uccide_cio_che_lascia_acceso():
    """Browser, Docker Desktop e LM Studio può avviarli il programma, ma gli devono sopravvivere.

    Il programma vero (il blocco `if __name__ == "__main__"` di avvio_chat) avvia un processo finto, come
    avvierebbe quelli, ed esce. Il processo deve rispondere ancora: un Job Object con «chiudi tutto alla
    chiusura» in cui entra il programma lo ucciderebbe.
    """
    (porta,) = porte_libere(1)
    lasciato = [sys.executable, str(Path(__file__).parent / "servizio_salute_finto.py"), "--porta", str(porta), "--durata", "30"]
    codice = (
        "import runpy, socket, subprocess, sys, time\n"
        "import dotenv\n"
        "from avvio_chat import passi\n"
        "dotenv.dotenv_values = lambda *a, **k: {}\n"
        "dotenv.load_dotenv = lambda *a, **k: None\n"
        "def in_ascolto():\n"
        "    try:\n"
        f"        socket.create_connection(('127.0.0.1', {porta}), timeout=0.3).close()\n"
        "        return True\n"
        "    except OSError:\n"
        "        return False\n"
        "def finta(imp, ingresso, scrivi, **opzioni):\n"
        f"    subprocess.Popen({lasciato!r})\n"
        "    while not in_ascolto():\n"
        "        time.sleep(0.1)\n"
        "    return 0\n"
        "passi.avvia_chat = finta\n"
        "sys.argv = ['avvio_chat']\n"
        "runpy.run_module('avvio_chat', run_name='__main__')\n"
    )
    programma = subprocess.run([sys.executable, "-c", codice], cwd=CARTELLA_PROGETTO, env={**os.environ, **ENV}, timeout=60)
    assert programma.returncode == 0
    time.sleep(1.5)  # se qualcosa lo uccidesse alla fine del programma, a questo punto sarebbe già morto
    assert in_ascolto(porta), "il processo lasciato acceso è morto insieme al programma"


# --- Il file del doppio clic ---

FILE_CMD = CARTELLA_PROGETTO / "avvia-chat.cmd"


def test_cmd_solo_ascii_e_crlf():
    grezzo = FILE_CMD.read_bytes()
    assert all(byte < 128 for byte in grezzo)  # niente lettere accentate: cmd le rovinerebbe
    righe = grezzo.split(b"\n")
    assert righe[-1] == b""  # il file finisce con un a capo
    assert all(riga.endswith(b"\r") for riga in righe[:-1])


def test_cmd_lancia_il_modulo():
    testo = FILE_CMD.read_text(encoding="ascii")
    assert 'cd /d "%~dp0"' in testo  # funziona da qualunque cartella, anche con spazi nel percorso
    assert '".venv\\Scripts\\python.exe" -m avvio_chat %*' in testo


@pytest.mark.skipif(sys.platform != "win32", reason="file per Windows")
def test_cmd_senza_venv_spiega_ed_esce_con_1(tmp_path):
    cartella = tmp_path / "cartella con spazi"
    cartella.mkdir()
    shutil.copy(FILE_CMD, cartella / "avvia-chat.cmd")
    fatto = subprocess.run(
        ["cmd", "/c", str(cartella / "avvia-chat.cmd")], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30
    )
    assert fatto.returncode == 1
    assert "Manca l'ambiente virtuale .venv" in fatto.stdout and "AVVIO-RAPIDO.md" in fatto.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="file per Windows")
def test_cmd_dopo_un_errore_aspetta_un_tasto_e_conserva_il_codice(tmp_path):
    """Con un ambiente virtuale vero ma senza il progetto, Python esce con un errore: la finestra deve
    aspettare un tasto (qui l'ingresso è vuoto, quindi prosegue) e il file deve uscire con lo stesso codice."""
    cartella = tmp_path / "copia"
    (cartella / ".venv" / "Scripts").mkdir(parents=True)
    shutil.copy(FILE_CMD, cartella / "avvia-chat.cmd")
    ambiente_vero = Path(sys.executable).parent.parent
    shutil.copy(ambiente_vero / "pyvenv.cfg", cartella / ".venv" / "pyvenv.cfg")
    shutil.copy(sys.executable, cartella / ".venv" / "Scripts" / "python.exe")
    fatto = subprocess.run(
        ["cmd", "/c", str(cartella / "avvia-chat.cmd")], stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60
    )
    assert "No module named avvio_chat" in fatto.stderr  # l'errore di Python resta visibile nella finestra
    assert "Press any key" in fatto.stdout or "Premere un tasto" in fatto.stdout  # la pausa c'è stata
    assert fatto.returncode == 1  # e il codice del programma non va perso
