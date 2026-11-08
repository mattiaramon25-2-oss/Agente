"""Meteo con risposte HTTP simulate: nessuna rete, nessun modello."""

import httpx
import pytest

from logica.errori import ErroreStrumento
from logica.meteo import DESCRIZIONI_WMO, TIMEOUT_METEO, URL_FORECAST, URL_GEOCODING, meteo_attuale

UDINE = {"name": "Udine", "admin1": "Friuli Venezia Giulia", "country": "Italia", "latitude": 46.06, "longitude": 13.24}
CORRENTE = {"utc_offset_seconds": 3600, "current": {"time": "2026-11-08T10:15", "temperature_2m": 8.4,
                                                    "weather_code": 2, "wind_speed_10m": 12.0}}


def risposta(valore):
    """Da valore di prova a risposta HTTP: dict → JSON 200, int → stato senza corpo, str → testo 200."""
    if isinstance(valore, dict):
        return httpx.Response(200, json=valore)
    if isinstance(valore, int):
        return httpx.Response(valore, text="errore")
    return httpx.Response(200, text=valore)


def solleva(eccezione):
    return eccezione


def client(geo, forecast, richieste=None):
    def gestore(richiesta):
        if richieste is not None:
            richieste.append(richiesta)
        valore = geo if richiesta.url.host == "geocoding-api.open-meteo.com" else forecast
        if isinstance(valore, Exception):
            raise valore
        return risposta(valore)

    return httpx.Client(transport=httpx.MockTransport(gestore))


def test_costanti():
    assert URL_GEOCODING == "https://geocoding-api.open-meteo.com/v1/search"
    assert URL_FORECAST == "https://api.open-meteo.com/v1/forecast" and TIMEOUT_METEO == 4.0


def test_risultato():
    r = meteo_attuale("Udine", client(geo={"results": [UDINE]}, forecast=CORRENTE))
    assert r == {"citta": {"nome": "Udine", "regione": "Friuli Venezia Giulia", "paese": "Italia",
                           "latitudine": 46.06, "longitudine": 13.24},
                 "altre_corrispondenze": [], "temperatura": {"valore": 8.4, "unita": "°C"},
                 "vento": {"valore": 12.0, "unita": "km/h"}, "condizioni": DESCRIZIONI_WMO[2],
                 "ora_riferimento": "2026-11-08T10:15+01:00", "fonte": "Open-Meteo"}


def test_citta_ambigua():
    altre = [{"name": "Paris", "admin1": "Texas", "country": "Stati Uniti", "latitude": 33.6, "longitude": -95.5},
             {"name": "Paris", "country": "Stati Uniti", "latitude": 36.3, "longitude": -88.3}]
    prima = {**UDINE, "name": "Parigi", "admin1": "Île-de-France", "country": "Francia"}
    r = meteo_attuale("Paris", client(geo={"results": [prima, *altre]}, forecast=CORRENTE))
    assert r["citta"]["nome"] == "Parigi"
    assert r["altre_corrispondenze"] == ["Paris (Texas, Stati Uniti)", "Paris (Stati Uniti)"]


def test_al_massimo_quattro_alternative():
    risultati = [UDINE] + [{**UDINE, "admin1": f"Regione {i}"} for i in range(6)]
    assert len(meteo_attuale("Udine", client(geo={"results": risultati}, forecast=CORRENTE))["altre_corrispondenze"]) == 4


def test_parametri_della_richiesta():
    richieste = []
    meteo_attuale(" Forlì ", client(geo={"results": [UDINE]}, forecast=CORRENTE, richieste=richieste))
    geo, previsione = richieste
    assert dict(geo.url.params) == {"name": "Forlì", "count": "5", "language": "it", "format": "json"}
    assert dict(previsione.url.params) == {"latitude": "46.06", "longitude": "13.24",
                                           "current": "temperature_2m,weather_code,wind_speed_10m", "timezone": "auto"}


def test_scarto_negativo_e_mezz_ora():
    for secondi, atteso in ((-18000, "-05:00"), (19800, "+05:30"), (0, "+00:00")):
        corrente = {**CORRENTE, "utc_offset_seconds": secondi}
        r = meteo_attuale("Udine", client(geo={"results": [UDINE]}, forecast=corrente))
        assert r["ora_riferimento"] == "2026-11-08T10:15" + atteso


@pytest.mark.parametrize("geo, forecast, frammento", [
    ({"generationtime_ms": 0.1}, CORRENTE, "Città non trovata: 'Atlantide'"),
    ({"results": []}, CORRENTE, "Città non trovata"),
    (httpx.ConnectError("no rete"), CORRENTE, "Servizio meteo non disponibile: ConnectError"),
    (503, CORRENTE, "Servizio meteo non disponibile"),
    (httpx.ReadTimeout("lento"), CORRENTE, "nessuna risposta entro 4 secondi"),
    ({"results": [UDINE]}, httpx.ConnectTimeout("lento"), "nessuna risposta entro 4 secondi"),
    ({"results": [UDINE]}, "non json", "Risposta non valida"),
    ({"results": [UDINE]}, 404, "Risposta non valida"),
    ({"results": [UDINE]}, {"utc_offset_seconds": 3600}, "Risposta non valida"),
    ({"results": [UDINE]}, {**CORRENTE, "current": {**CORRENTE["current"], "temperature_2m": None}}, "Risposta non valida"),
    ({"results": [{"name": "Udine"}]}, CORRENTE, "Risposta non valida"),
    ({"results": "non lista"}, CORRENTE, "Risposta non valida"),
])
def test_errori(geo, forecast, frammento):
    citta = "Atlantide" if frammento.startswith("Città non trovata: 'Atlantide'") else "Udine"
    with pytest.raises(ErroreStrumento, match=frammento) as errore:
        meteo_attuale(citta, client(geo=geo, forecast=forecast))
    if "non disponibile" in frammento or "nessuna risposta" in frammento:
        assert "Città non trovata" not in str(errore.value)


@pytest.mark.parametrize("city", ["", "   ", None, 3])
def test_citta_non_valida(city):
    richieste = []
    with pytest.raises(ErroreStrumento, match="Indica il nome di una città"):
        meteo_attuale(city, client(geo={"results": [UDINE]}, forecast=CORRENTE, richieste=richieste))
    assert richieste == []


def test_codice_sconosciuto():
    corrente = {**CORRENTE, "current": {**CORRENTE["current"], "weather_code": 1234}}
    r = meteo_attuale("Udine", client(geo={"results": [UDINE]}, forecast=corrente))
    assert r["condizioni"] == "condizioni non classificate (codice 1234)"


def test_tabella_wmo_completa():
    codici = {0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}
    assert set(DESCRIZIONI_WMO) == codici and all(isinstance(v, str) and v for v in DESCRIZIONI_WMO.values())


def test_alternative_identiche_alla_scelta_escluse():
    """Open-Meteo può restituire più voci con lo stesso nome, regione e paese: non sono un'ambiguità."""
    doppione = {**UDINE, "latitude": 46.1, "longitude": 13.2}
    altra = {"name": "Udine", "admin1": "Karnali Province", "country": "Nepal", "latitude": 28.9, "longitude": 81.8}
    r = meteo_attuale("Udine", client(geo={"results": [UDINE, doppione, altra]}, forecast=CORRENTE))
    assert r["altre_corrispondenze"] == ["Udine (Karnali Province, Nepal)"]


def test_scadenza_totale_anche_con_risposte_lente():
    """Il timeout di httpx vale per fase: serve una scadenza totale, o il ponte MCP scade per primo."""
    import time

    def lento(richiesta):
        time.sleep(0.5)
        return httpx.Response(200, json={"results": [UDINE]})

    inizio = time.monotonic()
    with pytest.raises(ErroreStrumento, match="Servizio meteo: nessuna risposta entro 0.3 secondi"):
        meteo_attuale("Udine", httpx.Client(transport=httpx.MockTransport(lento)), tempo_totale=0.3)
    assert time.monotonic() - inizio < 0.45


def test_tempo_totale_predefinito_sotto_il_ponte():
    from assistente.client_mcp import TIMEOUT_CHIAMATA
    from logica.meteo import TEMPO_TOTALE

    assert TEMPO_TOTALE == 8.0 and TEMPO_TOTALE < TIMEOUT_CHIAMATA


def test_solo_omonimi_tra_le_alternative():
    """Il geocoding restituisce anche ricerche approssimate (Forlini, Forlimpopoli): non sono ambiguità."""
    forli = {**UDINE, "name": "Forlì", "admin1": "Emilia-Romagna"}
    simili = [{**UDINE, "name": n, "admin1": "x"} for n in ("Forlini", "Forlimpopoli")]
    omonimo = {**UDINE, "name": "forlì", "admin1": "Altrove", "country": "Italia"}
    r = meteo_attuale("Forlì", client(geo={"results": [forli, *simili, omonimo]}, forecast=CORRENTE))
    assert r["altre_corrispondenze"] == ["forlì (Altrove, Italia)"] and "nota" not in r


def test_nome_diverso_da_quello_chiesto_dichiarato():
    pordenone = {**UDINE, "name": "Pordenone"}
    r = meteo_attuale("Pordenon", client(geo={"results": [pordenone]}, forecast=CORRENTE))
    assert r["nota"] == "Nessuna località chiamata esattamente 'Pordenon': scelta 'Pordenone'."


def test_omonimi_della_citta_scelta_contano_anche_se_tradotta():
    parigi = {**UDINE, "name": "Parigi", "admin1": "Île-de-France", "country": "Francia"}
    texas = {"name": "Paris", "admin1": "Texas", "country": "Stati Uniti", "latitude": 33.6, "longitude": -95.5}
    r = meteo_attuale("Paris", client(geo={"results": [parigi, texas]}, forecast=CORRENTE))
    assert r["altre_corrispondenze"] == ["Paris (Texas, Stati Uniti)"]
    assert r["nota"] == "Nessuna località chiamata esattamente 'Paris': scelta 'Parigi'."
