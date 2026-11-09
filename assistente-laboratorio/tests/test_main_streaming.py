from assistente.__main__ import scrivi_pezzo


def test_scrivi_pezzo_senza_a_capo(capsys):
    scrivi_pezzo("Cia")
    scrivi_pezzo("o!")
    assert capsys.readouterr().out == "Ciao!"
