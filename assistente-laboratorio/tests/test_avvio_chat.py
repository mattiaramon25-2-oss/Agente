"""Avvio della chat con un doppio clic: i passi di avvio_chat, senza Docker e senza LM Studio."""

import io
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
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
    esegui = EseguiFinto({DOCKER_INFO: [Esito(1, "errore")], DOCKER_AVVIO: [Esito(0, "")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_docker(esegui, Righe(), pausa=tempo.pausa, orologio=tempo.orologio)
    assert "Docker Desktop non risponde" in str(errore.value) and "180" in str(errore.value)
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
    esegui = EseguiFinto({("lms-finto",): [Esito(0, "")]})
    with pytest.raises(ErroreAvvio) as errore:
        passi.assicura_lmstudio(
            impostazioni(), esegui, Righe(), risponde=lambda url: False, verifica=lambda *a: None, lms=lambda: "lms-finto",
            pausa=tempo.pausa, orologio=tempo.orologio,
        )
    assert "LM Studio non risponde" in str(errore.value) and "60" in str(errore.value)


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
    monkeypatch.setattr(principale, "load_dotenv", lambda **k: None)  # niente .env reale
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
