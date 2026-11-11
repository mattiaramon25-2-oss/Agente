"""Client HTTP del servizio dell'agente: apre un turno in streaming e legge gli eventi SSE."""

import json
from typing import Iterator

import httpx

from assistente.sse import leggi_sse

TEMPI = httpx.Timeout(connect=5, read=180, write=10, pool=5)
TEMPI_SALUTE = httpx.Timeout(2)


class AgenteNonDisponibile(Exception):
    """L'agente non può prendere in carico il turno; il messaggio è il motivo, in italiano."""


class AgenteInterrotto(Exception):
    """Il flusso dell'agente si è interrotto a turno già iniziato."""


class TurnoAgente:
    """Un turno aperto: la risposta in streaming, da consumare con `eventi()`."""

    def __init__(self, risposta: httpx.Response):
        self._risposta = risposta
        self._chiusa = False

    def eventi(self) -> Iterator[tuple[str, dict]]:
        try:
            yield from leggi_sse(self._risposta.iter_lines())
        except httpx.HTTPError as errore:
            raise AgenteInterrotto(f"Il collegamento con l'agente si è interrotto: {errore or type(errore).__name__}.") from errore
        except json.JSONDecodeError as errore:
            raise AgenteInterrotto("L'agente ha inviato un evento malformato.") from errore
        finally:
            self.chiudi()

    def chiudi(self) -> None:
        if not self._chiusa:
            self._chiusa = True
            self._risposta.close()


class ClientAgente:
    def __init__(self, url: str, client: httpx.Client | None = None):
        self.url = url.rstrip("/")
        self._client = client or httpx.Client(timeout=TEMPI)

    def salute(self) -> bool:
        try:
            return self._client.get(f"{self.url}/salute", timeout=TEMPI_SALUTE).status_code == 200
        except httpx.HTTPError:
            return False

    def apri_turno(self, messaggio: str, cronologia: list[dict], istruzioni: str) -> TurnoAgente:
        corpo = {"messaggio": messaggio, "cronologia": cronologia, "istruzioni": istruzioni}
        try:
            richiesta = self._client.build_request("POST", f"{self.url}/chat/stream", json=corpo, timeout=TEMPI)
            risposta = self._client.send(richiesta, stream=True)
        except httpx.HTTPError as errore:
            raise AgenteNonDisponibile(
                f"L'agente non risponde su {self.url}: avvialo con python -m servizio_agente."
            ) from errore
        if risposta.status_code != 200:
            try:
                risposta.read()
                if risposta.status_code == 409:
                    motivo = "L'agente sta già rispondendo a un'altra chat: riprova tra poco."
                else:
                    try:
                        motivo = risposta.json()["errore"]
                    except (ValueError, KeyError, TypeError):
                        motivo = f"L'agente ha risposto con lo stato {risposta.status_code}."
            except httpx.HTTPError:
                motivo = f"L'agente ha risposto con lo stato {risposta.status_code}."
            finally:
                risposta.close()
            raise AgenteNonDisponibile(motivo)
        return TurnoAgente(risposta)
