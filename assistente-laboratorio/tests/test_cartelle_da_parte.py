"""Spostamento temporaneo di logs/ e archivio/ dell'utente durante la prova Docker: mai perdere o nascondere dati."""

import shutil

import pytest

from tests.cartelle_da_parte import SUFFISSO_RISERVA, cartelle_da_parte


def prepara(base, nome, contenuto):
    cartella = base / nome
    cartella.mkdir()
    (cartella / "dato.txt").write_text(contenuto, encoding="utf-8")


def test_ripristina_e_cancella_quelle_create_durante_la_prova(tmp_path):
    prepara(tmp_path, "logs", "log dell'utente")
    with cartelle_da_parte(tmp_path, ("logs", "archivio")):
        assert not (tmp_path / "logs").exists()
        prepara(tmp_path, "logs", "log della prova")
        prepara(tmp_path, "archivio", "nota di prova")  # l'utente non aveva archivio/
    assert (tmp_path / "logs" / "dato.txt").read_text(encoding="utf-8") == "log dell'utente"
    assert not (tmp_path / "archivio").exists()
    assert not list(tmp_path.glob(f"*{SUFFISSO_RISERVA}"))


def test_ripristina_anche_se_la_prova_fallisce(tmp_path):
    prepara(tmp_path, "archivio", "note dell'utente")
    with pytest.raises(RuntimeError):
        with cartelle_da_parte(tmp_path, ("logs", "archivio")):
            prepara(tmp_path, "archivio", "nota di prova")
            raise RuntimeError("prova fallita")
    assert (tmp_path / "archivio" / "dato.txt").read_text(encoding="utf-8") == "note dell'utente"


def test_riserva_gia_presente_annulla_le_rinomine_fatte(tmp_path):
    prepara(tmp_path, "logs", "log dell'utente")
    prepara(tmp_path, "archivio", "note dell'utente")
    (tmp_path / f"archivio{SUFFISSO_RISERVA}").mkdir()  # avanzo di una prova interrotta
    with pytest.raises(RuntimeError, match="archivio"):
        with cartelle_da_parte(tmp_path, ("logs", "archivio")):
            pytest.fail("non deve entrare nella prova")
    assert (tmp_path / "logs" / "dato.txt").read_text(encoding="utf-8") == "log dell'utente"
    assert (tmp_path / "archivio" / "dato.txt").read_text(encoding="utf-8") == "note dell'utente"


def test_cancellazione_che_fallisce_non_blocca_il_ripristino(tmp_path, monkeypatch):
    prepara(tmp_path, "logs", "log dell'utente")
    prepara(tmp_path, "archivio", "note dell'utente")
    originale = shutil.rmtree

    def rmtree_bloccato(percorso, *argomenti, **opzioni):  # come un file tenuto aperto su Windows
        if opzioni.get("ignore_errors"):
            return None
        raise PermissionError("file in uso")

    monkeypatch.setattr("tests.cartelle_da_parte.shutil.rmtree", rmtree_bloccato)
    with cartelle_da_parte(tmp_path, ("logs", "archivio")):
        prepara(tmp_path, "logs", "log della prova")
        prepara(tmp_path, "archivio", "nota di prova")
    monkeypatch.setattr("tests.cartelle_da_parte.shutil.rmtree", originale)
    assert (tmp_path / "logs" / "dato.txt").read_text(encoding="utf-8") == "log dell'utente"
    assert (tmp_path / "archivio" / "dato.txt").read_text(encoding="utf-8") == "note dell'utente"


def test_riserva_ignorata_da_git():
    from pathlib import Path

    radice = Path(__file__).resolve().parent.parent
    assert f"*{SUFFISSO_RISERVA}/" in (radice / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert f"*{SUFFISSO_RISERVA}" in (radice / ".dockerignore").read_text(encoding="utf-8").splitlines()


def test_rinomina_che_fallisce_a_meta_ripristina_la_prima(tmp_path, monkeypatch):
    from pathlib import Path

    prepara(tmp_path, "logs", "log dell'utente")
    prepara(tmp_path, "archivio", "note dell'utente")
    originale = Path.rename

    def rename_bloccato(self, destinazione):
        if self.name == "archivio" and str(destinazione).endswith(SUFFISSO_RISERVA):
            raise PermissionError("file in uso")
        return originale(self, destinazione)

    monkeypatch.setattr(Path, "rename", rename_bloccato)
    with pytest.raises(PermissionError):
        with cartelle_da_parte(tmp_path, ("logs", "archivio")):
            pytest.fail("non deve entrare nella prova")
    monkeypatch.setattr(Path, "rename", originale)
    assert (tmp_path / "logs" / "dato.txt").read_text(encoding="utf-8") == "log dell'utente"
    assert (tmp_path / "archivio" / "dato.txt").read_text(encoding="utf-8") == "note dell'utente"
    assert not list(tmp_path.glob(f"*{SUFFISSO_RISERVA}"))


def test_residui_da_eliminare_ignorati_da_git():
    from pathlib import Path

    radice = Path(__file__).resolve().parent.parent
    assert "*.da-eliminare-*/" in (radice / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "*.da-eliminare-*" in (radice / ".dockerignore").read_text(encoding="utf-8").splitlines()


def test_residuo_non_eliminabile_segnalato(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("tests.cartelle_da_parte.shutil.rmtree", lambda percorso, **opzioni: None)  # non cancella nulla
    with cartelle_da_parte(tmp_path, ("logs",)):
        prepara(tmp_path, "logs", "log della prova")
    assert "non eliminata" in capsys.readouterr().err
