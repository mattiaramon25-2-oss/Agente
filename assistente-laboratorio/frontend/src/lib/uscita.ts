// Mentre una risposta arriva, chiudere o ricaricare la pagina interromperebbe il turno
// (e il messaggio non verrebbe salvato): il browser chiede conferma.

function chiediConferma(evento: BeforeUnloadEvent): void {
  evento.preventDefault();
  // Per i browser che guardano ancora returnValue invece di preventDefault.
  evento.returnValue = '';
}

/** Attiva la richiesta di conferma; la funzione restituita la toglie. */
export function proteggiUscita(finestra: Window): () => void {
  finestra.addEventListener('beforeunload', chiediConferma);
  return () => finestra.removeEventListener('beforeunload', chiediConferma);
}
