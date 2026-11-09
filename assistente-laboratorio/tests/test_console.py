"""Ingresso e uscita rediretti su Windows: UTF-8 invece di cp1252, BOM tolto, nessun crash con emoji."""

import io

from assistente.console import configura_flussi


def flusso(dati: bytes = b"") -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(dati), encoding="cp1252")  # come una pipe su Windows: non è un terminale


def test_ingresso_da_pipe_in_utf8_senza_bom():
    ingresso, uscita = flusso(b"\xef\xbb\xbfesci\nRicordami il caff\xc3\xa8\n"), flusso()
    configura_flussi(ingresso, uscita)
    assert ingresso.readline() == "esci\n"
    assert ingresso.readline() == "Ricordami il caffè\n"


def test_uscita_rediretta_non_va_in_crash_con_emoji():
    ingresso, uscita = flusso(), flusso()
    configura_flussi(ingresso, uscita)
    uscita.write("Assistente: fatto 🙂 ≈ 2\n")
    uscita.flush()
    scritto = uscita.buffer.getvalue().decode("utf-8").replace("\r\n", "\n")  # a capo di Windows
    assert scritto == "Assistente: fatto 🙂 ≈ 2\n"


def test_terminale_interattivo_lasciato_com_e():
    class Terminale(io.StringIO):
        def isatty(self):
            return True

        def reconfigure(self, **opzioni):
            raise AssertionError("un terminale interattivo non va riconfigurato")

    configura_flussi(Terminale(), Terminale())
