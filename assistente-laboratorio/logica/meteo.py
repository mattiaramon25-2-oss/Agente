"""Meteo attuale da Open-Meteo: lo strumento incapsula un servizio HTTP esterno (slide 27).

Due richieste: geocoding (nome → coordinate) e forecast (condizioni attuali). La città scelta
tra più corrispondenze viene dichiarata nel risultato, mai scelta in silenzio. Gli errori di
rete restano sempre distinti da «città non trovata», e nessun dato viene inventato.
"""

import httpx

from logica.errori import ErroreStrumento

URL_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
URL_FORECAST = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_METEO = 4.0  # due richieste da 4 s restano sotto i 10 s del ponte MCP
ALTERNATIVE_MASSIME = 4
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


def meteo_attuale(city: object, http: httpx.Client, timeout: float = TIMEOUT_METEO) -> dict:
    """Meteo attuale per `city`; solleva ErroreStrumento con un messaggio che distingue la causa."""
    if not isinstance(city, str) or not city.strip():
        raise ErroreStrumento("Indica il nome di una città.")
    nome_richiesto = city.strip()

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

    altre = [a for a in (_alternativa(r) for r in risultati[1:]) if a][:ALTERNATIVE_MASSIME]
    return {
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
