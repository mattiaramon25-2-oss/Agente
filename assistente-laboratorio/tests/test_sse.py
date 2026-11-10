from assistente.sse import formatta_sse, leggi_sse


def test_sse_andata_e_ritorno():
    eventi = [("testo", {"pezzo": "riga 1\nriga 2 è 🙂"}), ("fine", {"risposta": "ok"})]
    testo = "".join(formatta_sse(e, d) for e, d in eventi)
    assert list(leggi_sse(testo.splitlines())) == eventi


def test_sse_ignora_commenti():
    assert list(leggi_sse([": ping", "event: testo", 'data: {"pezzo": "a"}', ""])) == [("testo", {"pezzo": "a"})]


def test_sse_righe_con_a_capo_evento_predefinito_ed_evento_incompleto():
    righe = ['data: {"a": 1}\n', "\n", "event: fine\n", 'data: {"b": 2}\n']
    assert list(leggi_sse(righe)) == [("message", {"a": 1})]
