from servizio_backend.testi import TITOLO_PREDEFINITO, estratto, titolo_da


def test_titolo_predefinito():
    assert TITOLO_PREDEFINITO == "Nuova chat"


def test_titolo_comprime_gli_spazi():
    assert titolo_da("  ciao   mondo ") == "ciao mondo"


def test_titolo_lungo_taglia_su_uno_spazio():
    domanda = " ".join(["abcdefghi"] * 10)  # 99 caratteri
    titolo = titolo_da(domanda)
    assert len(titolo) <= 61
    assert titolo.endswith("…")
    assert not titolo.endswith(" …")
    assert domanda.startswith(titolo[:-1])


def test_titolo_parola_unica_lunga_taglia_a_60():
    assert titolo_da("x" * 100) == "x" * 60 + "…"


def test_titolo_di_60_caratteri_non_si_taglia():
    assert titolo_da("y" * 60) == "y" * 60


def test_estratto_centrato_con_puntini():
    testo = "a" * 200 + "Gatto" + "b" * 200
    risultato = estratto(testo, "gatto")
    assert "Gatto" in risultato
    assert risultato.startswith("…") and risultato.endswith("…")
    assert len(risultato) == 82


def test_estratto_testo_corto_intero():
    assert estratto("il gatto", "GATTO") == "il gatto"


def test_estratto_vicino_all_inizio_senza_puntini_a_sinistra():
    risultato = estratto("Gatto" + "b" * 300, "gatto")
    assert risultato.startswith("Gatto")
    assert risultato.endswith("…")
    assert len(risultato) == 81
