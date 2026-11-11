// Client tipizzato del back-end delle chat (raggiunto su /api, con proxy di Vite o di nginx).
// Gli errori diventano sempre ErroreApi con un testo in italiano pronto da mostrare.

import { LettoreSse } from './sse';

export type Strumento = { nome: string; origine: string; argomenti: Record<string, unknown> };

export type Progetto = {
  id: number;
  nome: string;
  istruzioni: string;
  numero_chat: number;
  creato: string;
  aggiornato: string;
};

export type ChatBreve = {
  id: number;
  titolo: string;
  progetto_id: number | null;
  creata: string;
  aggiornata: string;
};

export type Messaggio = {
  id: number;
  ruolo: 'utente' | 'assistente';
  testo: string;
  strumenti: Strumento[] | null;
  creato: string;
};

export type Chat = ChatBreve & { messaggi: Messaggio[] };

export type RisultatoRicerca = {
  chat_id: number;
  titolo: string;
  progetto_id: number | null;
  messaggio_id: number;
  ruolo: string;
  estratto: string;
};

export type FineTurno = {
  risposta: string;
  strumenti: Strumento[];
  messaggio_utente_id: number;
  messaggio_assistente_id: number;
  titolo: string;
};

export type GestoriTurno = {
  suTesto(pezzo: string): void;
  suStrumento(strumento: Strumento): void;
};

export const TESTO_BACKEND_SPENTO = 'Il back-end non risponde: avvialo con python -m servizio_backend.';
export const TESTO_INTERRUZIONE = 'La risposta si è interrotta: il messaggio non è stato salvato.';

export class ErroreApi extends Error {
  stato: number | null;
  backendSpento: boolean;

  constructor(messaggio: string, stato: number | null = null, backendSpento = false) {
    super(messaggio);
    this.name = 'ErroreApi';
    this.stato = stato;
    this.backendSpento = backendSpento;
  }
}

type FunzioneFetch = (input: string, init?: RequestInit) => Promise<Response>;

const BASE = '/api';
let funzioneFetch: FunzioneFetch = (input, init) => fetch(input, init);

/** Sostituisce il fetch (nei test). */
export function impostaFetch(f: FunzioneFetch): void {
  funzioneFetch = f;
}

const èInterruzione = (e: unknown) => e instanceof Error && e.name === 'AbortError';

async function chiama(percorso: string, init?: RequestInit): Promise<Response> {
  let risposta: Response;
  try {
    risposta = await funzioneFetch(BASE + percorso, init);
  } catch (e) {
    if (èInterruzione(e)) throw e;
    throw new ErroreApi(TESTO_BACKEND_SPENTO, null, true);
  }
  if (!risposta.ok) throw await erroreDaRisposta(risposta);
  return risposta;
}

async function erroreDaRisposta(risposta: Response): Promise<ErroreApi> {
  const stato = risposta.status;
  let corpo: unknown = null;
  try {
    corpo = JSON.parse(await risposta.text());
  } catch {
    corpo = null;
  }
  if (corpo && typeof corpo === 'object' && typeof (corpo as { errore?: unknown }).errore === 'string') {
    return new ErroreApi((corpo as { errore: string }).errore, stato);
  }
  if (stato === 502 || stato === 503 || stato === 504) {
    return new ErroreApi(TESTO_BACKEND_SPENTO, stato, true);
  }
  return new ErroreApi(`Errore inatteso del back-end (stato ${stato}).`, stato);
}

const conCorpo = (metodo: string, corpo: unknown): RequestInit => ({
  method: metodo,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(corpo),
});

async function leggiJson<T>(percorso: string, init?: RequestInit): Promise<T> {
  const risposta = await chiama(percorso, init);
  return (await risposta.json()) as T;
}

async function eseguiSenzaCorpo(percorso: string, init: RequestInit): Promise<void> {
  await chiama(percorso, init);
}

export function salute(): Promise<{ stato: string; database: string; agente: string }> {
  return leggiJson('/salute');
}

export function elencaProgetti(): Promise<Progetto[]> {
  return leggiJson('/progetti');
}

export function creaProgetto(nome: string, istruzioni: string): Promise<Progetto> {
  return leggiJson('/progetti', conCorpo('POST', { nome, istruzioni }));
}

export function aggiornaProgetto(id: number, campi: { nome?: string; istruzioni?: string }): Promise<Progetto> {
  return leggiJson(`/progetti/${id}`, conCorpo('PATCH', campi));
}

export function cancellaProgetto(id: number): Promise<void> {
  return eseguiSenzaCorpo(`/progetti/${id}`, { method: 'DELETE' });
}

export function elencaChat(filtro?: number | 'nessuno'): Promise<ChatBreve[]> {
  const query = filtro === undefined ? '' : `?progetto=${filtro}`;
  return leggiJson(`/chat${query}`);
}

export function creaChat(progetto_id: number | null): Promise<Chat> {
  return leggiJson('/chat', conCorpo('POST', { progetto_id }));
}

export function leggiChat(id: number): Promise<Chat> {
  return leggiJson(`/chat/${id}`);
}

export function spostaChat(id: number, progetto_id: number | null): Promise<ChatBreve> {
  return leggiJson(`/chat/${id}`, conCorpo('PATCH', { progetto_id }));
}

export function cancellaChat(id: number): Promise<void> {
  return eseguiSenzaCorpo(`/chat/${id}`, { method: 'DELETE' });
}

export function cerca(q: string): Promise<RisultatoRicerca[]> {
  return leggiJson(`/ricerca?q=${encodeURIComponent(q)}`);
}

/** Un turno di conversazione in streaming: risolve con la FineTurno, altrimenti rifiuta. */
export async function inviaMessaggio(
  chatId: number,
  testo: string,
  gestori: GestoriTurno,
  segnale?: AbortSignal,
): Promise<FineTurno> {
  const risposta = await chiama(`/chat/${chatId}/messaggi`, { ...conCorpo('POST', { messaggio: testo }), signal: segnale });
  if (!risposta.body) throw new ErroreApi(TESTO_INTERRUZIONE);
  const lettore = risposta.body.getReader();
  const sse = new LettoreSse();
  try {
    for (;;) {
      let letto: ReadableStreamReadResult<Uint8Array>;
      try {
        letto = await lettore.read();
      } catch (e) {
        if (èInterruzione(e)) throw e;
        throw new ErroreApi(TESTO_INTERRUZIONE);
      }
      if (letto.done) break;
      let eventi;
      try {
        eventi = sse.aggiungi(letto.value);
      } catch {
        throw new ErroreApi(TESTO_INTERRUZIONE);
      }
      for (const { evento, dati } of eventi) {
        const corpo = (dati ?? {}) as Record<string, unknown>;
        if (evento === 'testo') gestori.suTesto(String(corpo.pezzo ?? ''));
        else if (evento === 'strumento') gestori.suStrumento(dati as Strumento);
        else if (evento === 'fine') return dati as FineTurno;
        else if (evento === 'errore') throw new ErroreApi(String(corpo.errore ?? TESTO_INTERRUZIONE), null);
      }
    }
    sse.fine();
    throw new ErroreApi(TESTO_INTERRUZIONE);
  } finally {
    // Rilascia il flusso in ogni caso; l'errore di cancel non interessa.
    lettore.cancel().catch(() => {});
  }
}

export const apiBackend = {
  salute,
  elencaProgetti,
  creaProgetto,
  aggiornaProgetto,
  cancellaProgetto,
  elencaChat,
  creaChat,
  leggiChat,
  spostaChat,
  cancellaChat,
  cerca,
  inviaMessaggio,
};

export type ApiBackend = typeof apiBackend;
