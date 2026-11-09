"""Meteo attuale da Open-Meteo: lo strumento incapsula un servizio HTTP esterno (slide 27).

Due richieste: geocoding (nome → coordinate) e forecast (condizioni attuali). La città scelta
tra più corrispondenze viene dichiarata nel risultato, mai scelta in silenzio. Gli errori di
rete restano sempre distinti da «città non trovata», e nessun dato viene inventato.
"""

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as TempoScaduto

import httpx

from logica.errori import ErroreStrumento

URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
URL_FORECAST = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_METEO = 4.0  # per fase di httpx (connessione, lettura...): non limita la durata totale
# Scadenza totale dello strumento, sotto i 10 s del ponte MCP: così l'errore arriva dal meteo e non dal ponte.
# Copre anche la risoluzione DNS, che in httpx non ha un timeout proprio.
TEMPO_TOTALE = 8.0
ALTERNATIVE_MASSIME = 4
LUNGHEZZA_MASSIMA_CITTA = 200
FONTE = "Open-Meteo"

SCHEMA_CITY = {"type": "string", "description": "Nome della città, per esempio Udine"}

# Codici meteo WMO usati da Open-Meteo, in italiano.
DESCRIZIONI_WMO = {
    0: "sereno",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "coperto",
    45: "nebbia",
    48: "nebbia con brina",
    51: "pioviggine leggera",
    53: "pioviggine moderata",
    55: "pioviggine intensa",
    56: "pioviggine gelata leggera",
    57: "pioviggine gelata intensa",
    61: "pioggia leggera",
    63: "pioggia moderata",
    65: "pioggia forte",
    66: "pioggia gelata leggera",
    67: "pioggia gelata forte",
    71: "neve leggera",
    73: "neve moderata",
    75: "neve forte",
    77: "granelli di neve",
    80: "rovesci di pioggia leggeri",
    81: "rovesci di pioggia moderati",
    82: "rovesci di pioggia violenti",
    85: "rovesci di neve leggeri",
    86: "rovesci di neve forti",
    95: "temporale",
    96: "temporale con grandine leggera",
    99: "temporale con grandine forte",
}


def _non_valida(dettaglio: str) -> ErroreStrumento:
    return ErroreStrumento(f"Risposta non valida dal servizio meteo: {dettaglio}.")


def _descrivi(errore: Exception) -> str:
    return f"{type(errore).__name__}: {errore}" if str(errore) else type(errore).__name__


def _richiedi(http: httpx.Client, url: str, params: dict, timeout: float) -> dict:
    """GET con gli errori tradotti: timeout e rete distinti da una risposta non valida."""
    try:
        risposta = http.get(url, params=params, timeout=timeout)
    except httpx.TimeoutException:
        raise ErroreStrumento(f"Servizio meteo: nessuna risposta entro {timeout:g} secondi.") from None
    except httpx.TransportError as errore:
        raise ErroreStrumento(f"Servizio meteo non disponibile: {_descrivi(errore)}") from None
    if risposta.status_code >= 500:
        raise ErroreStrumento(f"Servizio meteo non disponibile: HTTP {risposta.status_code}")
    if risposta.status_code != 200:
        raise _non_valida(f"HTTP {risposta.status_code}")
    try:
        dati = risposta.json()
    except ValueError:
        raise _non_valida("JSON non valido") from None
    if not isinstance(dati, dict):
        raise _non_valida("JSON inatteso")
    return dati


def _numero(valore: object, campo: str) -> float:
    if isinstance(valore, bool) or not isinstance(valore, (int, float)):
        raise _non_valida(f"campo '{campo}' mancante o non numerico")
    return valore


def _testo(valore: object) -> str | None:
    return valore if isinstance(valore, str) and valore else None


def _scarto(secondi: object) -> str:
    if isinstance(secondi, bool) or not isinstance(secondi, int):
        raise _non_valida("campo 'utc_offset_seconds' mancante")
    segno = "+" if secondi >= 0 else "-"
    ore, minuti = divmod(abs(secondi) // 60, 60)
    return f"{segno}{ore:02d}:{minuti:02d}"


def _alternativa(corrispondenza: object) -> str | None:
    if not isinstance(corrispondenza, dict) or not _testo(corrispondenza.get("name")):
        return None
    dettagli = [d for d in (_testo(corrispondenza.get("admin1")), _testo(corrispondenza.get("country"))) if d]
    nome = corrispondenza["name"]
    return f"{nome} ({', '.join(dettagli)})" if dettagli else nome


def meteo_attuale(
    city: object, http: httpx.Client, timeout: float = TIMEOUT_METEO, tempo_totale: float = TEMPO_TOTALE
) -> dict:
    """Meteo attuale per `city`, entro `tempo_totale` secondi; solleva ErroreStrumento distinguendo la causa."""
    esecutore = ThreadPoolExecutor(max_workers=1)
    try:
        return esecutore.submit(_meteo, city, http, timeout).result(timeout=tempo_totale)
    except TempoScaduto:
        # La richiesta in corso finisce da sola nel thread di lavoro; il risultato viene scartato.
        raise ErroreStrumento(f"Servizio meteo: nessuna risposta entro {tempo_totale:g} secondi.") from None
    finally:
        esecutore.shutdown(wait=False)


def _meteo(city: object, http: httpx.Client, timeout: float) -> dict:
    if not isinstance(city, str) or not city.strip():
        raise ErroreStrumento("Indica il nome di una città.")
    nome_richiesto = city.strip()
    try:
        nome_richiesto.encode("utf-8")
        valido = len(nome_richiesto) <= LUNGHEZZA_MASSIMA_CITTA
    except UnicodeEncodeError:
        valido = False
    if not valido:
        raise ErroreStrumento(
            f"Nome della città non valido: al massimo {LUNGHEZZA_MASSIMA_CITTA} caratteri, senza caratteri non validi."
        )

    geo = _richiedi(http, URL_GEOCODING, {"name": nome_richiesto, "count": 5, "language": "it", "format": "json"}, timeout)
    risultati = geo.get("results")
    if risultati is None or risultati == []:
        raise ErroreStrumento(f"Città non trovata: '{nome_richiesto}'.")
    if not isinstance(risultati, list) or not isinstance(risultati[0], dict):
        raise _non_valida("elenco delle città inatteso")
    scelta = risultati[0]
    nome = _testo(scelta.get("name"))
    if nome is None:
        raise _non_valida("città senza nome")
    latitudine = _numero(scelta.get("latitude"), "latitude")
    longitudine = _numero(scelta.get("longitude"), "longitude")

    previsione = _richiedi(
        http,
        URL_FORECAST,
        {
            "latitude": latitudine,
            "longitude": longitudine,
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "timezone": "auto",
        },
        timeout,
    )
    attuale = previsione.get("current")
    if not isinstance(attuale, dict):
        raise _non_valida("campo 'current' mancante")
    ora = attuale.get("time")
    if not isinstance(ora, str) or not ora:
        raise _non_valida("campo 'time' mancante")
    temperatura = _numero(attuale.get("temperature_2m"), "temperature_2m")
    vento = _numero(attuale.get("wind_speed_10m"), "wind_speed_10m")
    codice = attuale.get("weather_code")
    if isinstance(codice, bool) or not isinstance(codice, int):
        raise _non_valida("campo 'weather_code' mancante")

    # Alternative: solo omonimi del nome chiesto o di quello scelto (il geocoding aggiunge ricerche
    # approssimate, come Forlini per Forlì, che non sono ambiguità). Voci con la stessa etichetta della
    # città scelta (stesso nome, regione e paese) non sono un'ambiguità.
    nomi_validi = {nome_richiesto.casefold(), nome.casefold()}
    etichetta_scelta = _alternativa(scelta)
    altre = []
    for corrispondenza in risultati[1:]:
        etichetta = _alternativa(corrispondenza)
        if not etichetta or corrispondenza["name"].casefold() not in nomi_validi:
            continue
        if etichetta != etichetta_scelta and etichetta not in altre:
            altre.append(etichetta)
    altre = altre[:ALTERNATIVE_MASSIME]
    risultato = {
        "citta": {
            "nome": nome,
            "regione": _testo(scelta.get("admin1")),
            "paese": _testo(scelta.get("country")),
            "latitudine": latitudine,
            "longitudine": longitudine,
        },
        "altre_corrispondenze": altre,
        "temperatura": {"valore": temperatura, "unita": "°C"},
        "vento": {"valore": vento, "unita": "km/h"},
        "condizioni": DESCRIZIONI_WMO.get(codice, f"condizioni non classificate (codice {codice})"),
        "ora_riferimento": ora + _scarto(previsione.get("utc_offset_seconds")),
        "fonte": FONTE,
    }
    if nome.casefold() != nome_richiesto.casefold():  # sostituzione dichiarata, mai silenziosa
        risultato["nota"] = f"Nessuna località chiamata esattamente '{nome_richiesto}': scelta '{nome}'."
    return risultato
