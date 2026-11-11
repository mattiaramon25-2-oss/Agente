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


def test_sse_separatori_unicode_non_spezzano_l_evento():
    import httpx

    dati = {"risposta": "a\u2028b\u2029c\x85d è"}
    testo = formatta_sse("fine", dati)
    assert "\u2028" not in testo and "\u2029" not in testo and "\x85" not in testo
    assert "è" in testo
    assert list(leggi_sse(testo.splitlines())) == [("fine", dati)]
    risposta = httpx.Response(200, content=testo.encode("utf-8"))
    assert list(leggi_sse(risposta.iter_lines())) == [("fine", dati)]
