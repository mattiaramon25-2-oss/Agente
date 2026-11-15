"""Avvio della chat con un doppio clic: i passi di avvio_chat, senza Docker e senza LM Studio."""

import ctypes
import io
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace

import pytest

from assistente import avvio_server
from assistente.configurazione import ErroreConfigurazione
from assistente.errori import ErroreAvvio
from assistente.modello import ErroreServer
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
COMPOSE = ("docker", "compose")


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
    valori = dict(
        base_url="http://localhost:1234/v1", modello="finto", porta_mcp=8765, porta_agente=8767, porta_backend=8768, porta_frontend=8780
    )
    return Impostazioni(**{**valori, **cambi})


# --- Impostazioni ---


def test_impostazioni_dal_env():
    imp = passi.carica_impostazioni(ENV)
    assert (imp.porta_mcp, imp.porta_agente, imp.porta_backend, imp.porta_frontend) == (8765, 8767, 8768, 8780)
    assert imp.base_url == "http://localhost:1234/v1" and imp.modello == "finto"
    assert imp.url_agente == "http://127.0.0.1:8767"
    assert imp.url_backend == "http://127.0.0.1:8768"
    assert imp.url_chat == "http://127.0.0.1:8780"
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
    assert "[1/5] Docker: acceso" in righe.testo


def test_docker_spento_lo_avvia_e_aspetta():
    tempo = Tempo()
    esegui = EseguiFinto({DOCKER_INFO: [Esito(1, "errore"), Esito(1, "errore"), Esito(0, "29.1.0")], DOCKER_AVVIO: [Esito(0, "")]})
    righe = Righe()
    passi.assicura_docker(esegui, righe, pausa=tempo.pausa, orologio=tempo.orologio)
    assert esegui.chiamati(DOCKER_AVVIO) == 1
    assert ["docker", "desktop", "start"] in esegui.comandi
    assert esegui.chiamati(DOCKER_INFO) == 3
    assert "lo accendo" in righe.testo and "[1/5] Docker: acceso" in righe.testo


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
    assert "[2/5] LM Studio: risponde, modello finto presente" in righe.testo


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
    assert "lo accendo" in righe.testo and "[2/5] LM Studio: risponde" in righe.testo


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


# --- Container ---


def test_container_usa_wait_e_attesa_lunga():
    esegui = EseguiFinto({COMPOSE: [Esito(0, "")]})
    righe = Righe()
    passi.assicura_container(esegui, righe)
    assert esegui.comandi == [["docker", "compose", "up", "-d", "--wait", "database", "frontend"]]
    assert esegui.limiti == [600.0]
    assert "la prima volta" in righe.testo and "[3/5] Database e pagina: accesi" in righe.testo


def test_container_che_falliscono():
    esegui = EseguiFinto({COMPOSE: [Esito(1, "riga inutile\nBind for 127.0.0.1:8780 failed: port is already allocated\n")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_container(esegui, Righe())
    assert "docker compose up" in str(errore.value) and "port is already allocated" in str(errore.value)


def test_esegui_comando_vero():
    assert passi.esegui_comando([sys.executable, "-c", "print('ciao')"], 20.0) == Esito(0, "ciao\n")
    lento = passi.esegui_comando([sys.executable, "-c", "import time; time.sleep(5)"], 0.2)
    assert lento.codice == 124 and "0.2 secondi" in lento.uscita
    with pytest.raises(FileNotFoundError):
        passi.esegui_comando(["programma-che-non-esiste-di-sicuro"], 5.0)


# --- Servizi: avvio, riuso, arresto ---


def comando_finto(porta: int) -> list[str]:
    return [sys.executable, str(Path(__file__).parent / "servizio_salute_finto.py"), "--porta", str(porta)]


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


@contextmanager
def servizio_esterno(porta: int):
    """Un servizio finto acceso da qualcun altro: avvio_chat non lo deve né avviare né spegnere."""
    processo = subprocess.Popen(comando_finto(porta), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        scadenza = time.monotonic() + 15
        while True:
            try:
                passi.leggi_salute(f"http://127.0.0.1:{porta}", 1.0)
                break
            except Exception:
                assert time.monotonic() < scadenza and processo.poll() is None, "il servizio finto non è partito"
                time.sleep(0.1)
        yield processo
    finally:
        processo.kill()
        processo.wait()


def test_servizio_avviato_e_spento(porta, tmp_path, popen_registrati):
    righe = Righe()
    with passi.servizio("servizio finto", comando_finto(porta), porta, "PORTA_FINTA", tmp_path / "s.log", righe) as avviato:
        assert avviato is True
        assert passi.leggi_salute(f"http://127.0.0.1:{porta}", 2.0) == {"stato": "ok"}
    assert len(popen_registrati) == 1 and popen_registrati[0].poll() is not None  # nessun processo orfano
    assert avvio_server.porta_libera(porta)
    assert "Avvio il servizio finto" in righe.testo


def test_servizio_gia_acceso_non_si_tocca(porta, tmp_path, popen_registrati):
    with servizio_esterno(porta) as esterno:
        prima = len(popen_registrati)
        righe = Righe()
        with passi.servizio("servizio finto", comando_finto(porta), porta, "PORTA_FINTA", tmp_path / "s.log", righe) as avviato:
            assert avviato is False
        assert len(popen_registrati) == prima  # nessun processo nuovo
        assert esterno.poll() is None
        assert passi.leggi_salute(f"http://127.0.0.1:{porta}", 2.0) == {"stato": "ok"}
        assert righe.righe == []


def test_servizio_che_non_parte(porta, tmp_path):
    comando = [sys.executable, "-c", "print('Errore: prova'); raise SystemExit(1)"]
    with pytest.raises(ErroreAvvio) as errore:
        with passi.servizio("servizio finto", comando, porta, "PORTA_FINTA", tmp_path / "s.log", Righe()):
            pass
    assert "non è partito" in str(errore.value) and "Errore: prova" in str(errore.value)


def test_salute_senza_nessuno_in_ascolto(porta):
    with pytest.raises(Exception):
        passi.leggi_salute(f"http://127.0.0.1:{porta}", 0.5)


# --- Il programma intero, con agente e back-end finti ---


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


@pytest.fixture
def scena(tmp_path):
    """Impostazioni con quattro porte libere e le dipendenze finte di un computer già pronto."""
    mcp, agente, backend, frontend = porte_libere(4)
    imp = impostazioni(porta_mcp=mcp, porta_agente=agente, porta_backend=backend, porta_frontend=frontend)
    aperti: list[str] = []
    righe = Righe()
    opzioni = dict(
        esegui=EseguiFinto({DOCKER_INFO: [Esito(0, "29.1.0")], COMPOSE: [Esito(0, "")]}),
        apri=aperti.append,
        comando_agente=comando_finto(agente),
        comando_backend=comando_finto(backend),
        cartella_log=tmp_path,
        risponde=lambda url: True,
        verifica=lambda url, modello: None,
    )
    return SimpleNamespace(imp=imp, aperti=aperti, righe=righe, opzioni=opzioni, cartella=tmp_path)


def test_avvio_completo_ed_esci(scena, popen_registrati):
    codice = passi.avvia_chat(scena.imp, io.StringIO("ciao\nESCI \n"), scena.righe, **scena.opzioni)
    assert codice == 0
    testo = scena.righe.testo
    for passo in ("[1/5] Docker", "[2/5] LM Studio", "[3/5] Database e pagina", "[4/5] Agente: pronto su", "[5/5] Back-end: pronto su"):
        assert passo in testo
    assert "La chat è accesa" in testo and "«esci»" in testo
    assert scena.aperti == [scena.imp.url_chat]
    assert len(popen_registrati) == 2 and all(p.poll() is not None for p in popen_registrati)  # nessun processo orfano
    assert (scena.cartella / "avvio_agente.log").exists() and (scena.cartella / "avvio_backend.log").exists()


def test_arresto_in_ordine_inverso(scena, popen_registrati, monkeypatch):
    fermati = []
    ferma_vera = avvio_server.ferma

    def ferma(processo, *argomenti, **opzioni):
        fermati.append(processo.pid)
        return ferma_vera(processo, *argomenti, **opzioni)

    monkeypatch.setattr(avvio_server, "ferma", ferma)
    passi.avvia_chat(scena.imp, io.StringIO("esci\n"), scena.righe, **scena.opzioni)
    agente, backend = popen_registrati
    assert fermati == [backend.pid, agente.pid]


def test_fine_input_spegne_come_esci(scena, popen_registrati):
    assert passi.avvia_chat(scena.imp, io.StringIO(""), scena.righe, **scena.opzioni) == 0
    assert len(popen_registrati) == 2 and all(p.poll() is not None for p in popen_registrati)


def test_ctrl_c_spegne_tutto(scena, popen_registrati):
    assert passi.avvia_chat(scena.imp, IngressoInterrotto(), scena.righe, **scena.opzioni) == 0
    assert len(popen_registrati) == 2 and all(p.poll() is not None for p in popen_registrati)


def test_tutto_gia_acceso_apre_solo_il_browser(scena, popen_registrati):
    with servizio_esterno(scena.imp.porta_agente) as agente, servizio_esterno(scena.imp.porta_backend) as backend:
        prima = len(popen_registrati)
        codice = passi.avvia_chat(scena.imp, IngressoVietato(), scena.righe, **scena.opzioni)
        assert codice == 0
        assert len(popen_registrati) == prima  # non ha avviato niente
        assert scena.aperti == [scena.imp.url_chat]
        assert "già acceso" in scena.righe.testo and "La chat è accesa" not in scena.righe.testo
        assert agente.poll() is None and backend.poll() is None  # e non ha spento niente
        assert passi.leggi_salute(scena.imp.url_backend, 2.0) == {"stato": "ok"}


def test_agente_gia_acceso_si_spegne_solo_il_backend(scena, popen_registrati):
    with servizio_esterno(scena.imp.porta_agente) as agente:
        prima = len(popen_registrati)
        assert passi.avvia_chat(scena.imp, io.StringIO("esci\n"), scena.righe, **scena.opzioni) == 0
        nuovi = popen_registrati[prima:]
        assert len(nuovi) == 1 and nuovi[0].poll() is not None  # il back-end, avviato e spento da noi
        assert agente.poll() is None and passi.leggi_salute(scena.imp.url_agente, 2.0) == {"stato": "ok"}
        assert "[4/5] Agente: già acceso" in scena.righe.testo and "[5/5] Back-end: pronto" in scena.righe.testo


def test_senza_browser(scena, popen_registrati):
    assert passi.avvia_chat(scena.imp, io.StringIO("esci\n"), scena.righe, senza_browser=True, **scena.opzioni) == 0
    assert scena.aperti == []
    assert "Apro" not in scena.righe.testo and scena.imp.url_chat in scena.righe.testo


def test_porta_mcp_occupata_dice_di_chiudere_il_terminale(scena, popen_registrati):
    with socket.socket() as occupante:
        occupante.bind(("127.0.0.1", scena.imp.porta_mcp))
        occupante.listen()
        with pytest.raises(ErroreAvvio) as errore:
            passi.avvia_chat(scena.imp, io.StringIO("esci\n"), scena.righe, **scena.opzioni)
    assert "chat da terminale" in str(errore.value) and "MCP_PORTA" in str(errore.value)
    assert popen_registrati == []
    assert scena.aperti == []


def test_backend_che_non_parte_spegne_l_agente(scena, popen_registrati):
    scena.opzioni["comando_backend"] = [sys.executable, "-c", "print('Errore: database spento'); raise SystemExit(1)"]
    with pytest.raises(ErroreAvvio) as errore:
        passi.avvia_chat(scena.imp, io.StringIO("esci\n"), scena.righe, **scena.opzioni)
    assert "back-end delle chat non è partito" in str(errore.value) and "database spento" in str(errore.value)
    assert all(p.poll() is not None for p in popen_registrati)  # anche l'agente, già avviato, è stato spento
    assert scena.aperti == []


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


def test_main_ctrl_c_durante_l_avvio(ambiente, monkeypatch):
    def interrotto(*argomenti, **opzioni):
        raise KeyboardInterrupt

    monkeypatch.setattr(principale, "avvia_chat", interrotto)
    assert principale.main([], io.StringIO("")) == 0


# --- Chiusura: i servizi si spengono, il resto resta acceso ---


def attendi(condizione, secondi: float, messaggio: str) -> None:
    scadenza = time.monotonic() + secondi
    while not condizione():
        assert time.monotonic() < scadenza, messaggio
        time.sleep(0.2)


@pytest.mark.skipif(sys.platform != "win32", reason="la console di Windows")
def test_chiudere_la_finestra_spegne_i_servizi(tmp_path):
    """La X della finestra non passa da «esci»: Windows avvisa i processi attaccati alla console e li chiude.

    Il servizio parte come nel programma vero (passi.servizio, quindi processo_in_attesa) dentro una console
    classica nascosta; poi la console riceve WM_CLOSE, cioè quello che manda il pulsante X.
    """
    (porta,) = porte_libere(1)
    titolo = f"prova-avvio-chat-{os.getpid()}-{porta}"
    codice = (
        "import ctypes, sys, time\n"
        "from pathlib import Path\n"
        "from avvio_chat import passi\n"
        f"ctypes.windll.kernel32.SetConsoleTitleW({titolo!r})\n"
        f"comando = {comando_finto(porta) + ['--durata', '60']!r}\n"
        f"with passi.servizio('servizio finto', comando, {porta}, 'PORTA_FINTA', Path({str(tmp_path / 's.log')!r}), print):\n"
        "    time.sleep(120)\n"
    )
    nascosta = subprocess.STARTUPINFO()
    nascosta.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    nascosta.wShowWindow = 0  # SW_HIDE: la finestra esiste ma non compare sullo schermo
    console = subprocess.Popen(["conhost.exe", sys.executable, "-c", codice], cwd=FILE_CMD.parent, startupinfo=nascosta)
    try:
        attendi(lambda: passi._in_ascolto(porta), 30, "il servizio non è partito")
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.restype = wintypes.HWND
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        attendi(lambda: bool(user32.FindWindowW(None, titolo)), 10, "la finestra della console non si trova")
        assert user32.PostMessageW(user32.FindWindowW(None, titolo), 0x0010, 0, 0)  # WM_CLOSE
        attendi(lambda: not passi._in_ascolto(porta), 15, "il servizio è rimasto acceso dopo la chiusura della finestra")
    finally:
        try:
            console.wait(10)
        except subprocess.TimeoutExpired:
            console.kill()


def test_il_programma_non_uccide_cio_che_lascia_acceso():
    """Browser, Docker Desktop e LM Studio può avviarli il programma, ma gli devono sopravvivere.

    Il programma vero (il blocco `if __name__ == "__main__"` di avvio_chat) avvia un processo finto, come
    avvierebbe quelli, ed esce. Il processo deve rispondere ancora: un Job Object con «chiudi tutto alla
    chiusura» in cui entra il programma lo ucciderebbe.
    """
    (porta,) = porte_libere(1)
    lasciato = comando_finto(porta) + ["--durata", "30"]  # si spegne da solo: nessun orfano dopo la prova
    codice = (
        "import runpy, subprocess, sys, time\n"
        "import dotenv\n"
        "from avvio_chat import passi\n"
        "dotenv.dotenv_values = lambda *a, **k: {}\n"
        "dotenv.load_dotenv = lambda *a, **k: None\n"
        "def finta(imp, ingresso, scrivi, **opzioni):\n"
        f"    subprocess.Popen({lasciato!r})\n"
        f"    while not passi._in_ascolto({porta}):\n"
        "        time.sleep(0.1)\n"
        "    return 0\n"
        "passi.avvia_chat = finta\n"
        "sys.argv = ['avvio_chat']\n"
        "runpy.run_module('avvio_chat', run_name='__main__')\n"
    )
    programma = subprocess.run([sys.executable, "-c", codice], cwd=FILE_CMD.parent, env={**os.environ, **ENV}, timeout=60)
    assert programma.returncode == 0
    time.sleep(1.5)  # se qualcosa lo uccidesse alla fine del programma, a questo punto sarebbe già morto
    assert passi._in_ascolto(porta), "il processo lasciato acceso è morto insieme al programma"


def test_main_non_mette_la_password_nell_ambiente(monkeypatch):
    """Le impostazioni vengono dal .env, ma la password non deve passare ai programmi che restano accesi."""
    monkeypatch.setattr(principale, "dotenv_values", lambda *a, **k: {**ENV, "VUOTA": None})
    for nome in ENV:
        monkeypatch.delenv(nome, raising=False)
    ricevute = []
    monkeypatch.setattr(principale, "avvia_chat", lambda imp, ingresso, scrivi, **opzioni: ricevute.append(imp) or 0)
    assert principale.main([], io.StringIO("")) == 0
    assert ricevute[0].porta_backend == 8768
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


def test_esegui_comando_non_aspetta_i_programmi_lasciati_accesi():
    """`docker desktop start` e `lms server start` lasciano acceso un programma che eredita l'uscita:
    leggendo da una pipe, il comando sembrerebbe finire solo quando quel programma si chiude."""
    codice = "import subprocess, sys; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(6)']); print('avviato')"
    inizio = time.monotonic()
    esito = passi.esegui_comando([sys.executable, "-c", codice], 20.0)
    assert esito == Esito(0, "avviato\n")
    assert time.monotonic() - inizio < 4


# --- Il file del doppio clic ---

FILE_CMD = Path(__file__).resolve().parent.parent / "avvia-chat.cmd"


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
