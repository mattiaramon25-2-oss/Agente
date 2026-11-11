import { afterEach, describe, expect, it } from 'vitest';
import {
  apiBackend,
  cancellaChat,
  cerca,
  creaChat,
  elencaChat,
  elencaProgetti,
  ErroreApi,
  impostaFetch,
  inviaMessaggio,
  type FineTurno,
  type Strumento,
} from './api';

type Chiamata = { url: string; init?: RequestInit };

function fetchFinto(risposta: () => Response | Promise<Response>) {
  const chiamate: Chiamata[] = [];
  impostaFetch(async (url, init) => {
    chiamate.push({ url: String(url), init });
    return risposta();
  });
  return chiamate;
}

const json = (corpo: unknown, stato = 200) =>
  new Response(JSON.stringify(corpo), { status: stato, headers: { 'Content-Type': 'application/json' } });

function flusso(pezzi: string[]) {
  const codifica = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controllore) {
        for (const pezzo of pezzi) controllore.enqueue(codifica.encode(pezzo));
        controllore.close();
      },
    }),
    { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
  );
}

const FINE = {
  risposta: 'Ciao mondo',
  strumenti: [],
  messaggio_utente_id: 1,
  messaggio_assistente_id: 2,
  titolo: 'Saluti',
};

const gestoriVuoti = { suTesto() {}, suStrumento() {} };

afterEach(() => impostaFetch(globalThis.fetch.bind(globalThis)));

describe('client API', () => {
  it('elenca progetti', async () => {
    const progetti = [{ id: 1, nome: 'A', istruzioni: '', numero_chat: 0, creato: 'x', aggiornato: 'y' }];
    const chiamate = fetchFinto(() => json(progetti));
    expect(await elencaProgetti()).toEqual(progetti);
    expect(chiamate[0].url).toBe('/api/progetti');
  });

  it('crea chat manda progetto_id', async () => {
    const chiamate = fetchFinto(() => json({ id: 5, messaggi: [] }, 201));
    await creaChat(3);
    expect(chiamate[0].url).toBe('/api/chat');
    expect(chiamate[0].init?.method).toBe('POST');
    expect(JSON.parse(String(chiamate[0].init?.body))).toEqual({ progetto_id: 3 });
    expect(new Headers(chiamate[0].init?.headers).get('Content-Type')).toBe('application/json');
  });

  it('elenca chat con filtro', async () => {
    const chiamate = fetchFinto(() => json([]));
    await elencaChat();
    await elencaChat(7);
    await elencaChat('nessuno');
    expect(chiamate.map((c) => c.url)).toEqual(['/api/chat', '/api/chat?progetto=7', '/api/chat?progetto=nessuno']);
  });

  it('cancella 204 senza corpo', async () => {
    const chiamate = fetchFinto(() => new Response(null, { status: 204 }));
    await expect(cancellaChat(4)).resolves.toBeUndefined();
    expect(chiamate[0].url).toBe('/api/chat/4');
    expect(chiamate[0].init?.method).toBe('DELETE');
  });

  it('errore 409 in italiano dal back-end', async () => {
    fetchFinto(() => json({ errore: 'La chat è occupata.' }, 409));
    const errore = await cancellaChat(4).catch((e) => e);
    expect(errore).toBeInstanceOf(ErroreApi);
    expect(errore.message).toBe('La chat è occupata.');
    expect(errore.stato).toBe(409);
    expect(errore.backendSpento).toBe(false);
  });

  it('502 HTML è back-end spento', async () => {
    fetchFinto(() => new Response('<html>Bad Gateway</html>', { status: 502 }));
    const errore = await elencaProgetti().catch((e) => e);
    expect(errore).toBeInstanceOf(ErroreApi);
    expect(errore.backendSpento).toBe(true);
    expect(errore.message).toBe('Il back-end non risponde: avvialo con python -m servizio_backend.');
  });

  it('errore di rete è back-end spento', async () => {
    impostaFetch(async () => {
      throw new TypeError('Failed to fetch');
    });
    const errore = await elencaProgetti().catch((e) => e);
    expect(errore).toBeInstanceOf(ErroreApi);
    expect(errore.backendSpento).toBe(true);
  });

  it('errore senza corpo del back-end è inatteso', async () => {
    fetchFinto(() => new Response('boom', { status: 500 }));
    const errore = await elencaProgetti().catch((e) => e);
    expect(errore.message).toBe('Errore inatteso del back-end (stato 500).');
    expect(errore.backendSpento).toBe(false);
  });

  it('cerca codifica la query', async () => {
    const chiamate = fetchFinto(() => json([]));
    await cerca('a b&c');
    expect(chiamate[0].url).toBe('/api/ricerca?q=a%20b%26c');
  });

  it('apiBackend raggruppa le funzioni', () => {
    expect(apiBackend.elencaProgetti).toBe(elencaProgetti);
    expect(apiBackend.inviaMessaggio).toBe(inviaMessaggio);
  });

  describe('inviaMessaggio', () => {
    const evento = (nome: string, dati: unknown) => `event: ${nome}\ndata: ${JSON.stringify(dati)}\n\n`;

    it('turno completo', async () => {
      const strumento: Strumento = { nome: 'orologio', origine: 'mcp', argomenti: {} };
      const testo = evento('testo', { pezzo: 'Ciao ' }) + evento('testo', { pezzo: 'mondo' });
      const chiamate = fetchFinto(() =>
        flusso([
          evento('strumento', strumento),
          testo.slice(0, 20),
          testo.slice(20) + evento('fine', FINE).slice(0, 15),
          evento('fine', FINE).slice(15),
        ]),
      );
      const visti: string[] = [];
      const fine: FineTurno = await inviaMessaggio(9, 'Ciao', {
        suStrumento: (s) => visti.push(`strumento:${s.nome}`),
        suTesto: (p) => visti.push(`testo:${p}`),
      });
      expect(visti).toEqual(['strumento:orologio', 'testo:Ciao ', 'testo:mondo']);
      expect(fine).toEqual(FINE);
      expect(chiamate[0].url).toBe('/api/chat/9/messaggi');
      expect(JSON.parse(String(chiamate[0].init?.body))).toEqual({ messaggio: 'Ciao' });
    });

    it('turno con evento errore', async () => {
      fetchFinto(() => flusso([evento('testo', { pezzo: 'Ci' }), evento('errore', { errore: 'Modello spento.' })]));
      const errore = await inviaMessaggio(9, 'x', gestoriVuoti).catch((e) => e);
      expect(errore).toBeInstanceOf(ErroreApi);
      expect(errore.message).toBe('Modello spento.');
      expect(errore.stato).toBeNull();
    });

    it('turno finito senza fine', async () => {
      fetchFinto(() => flusso([evento('testo', { pezzo: 'Ci' })]));
      const errore = await inviaMessaggio(9, 'x', gestoriVuoti).catch((e) => e);
      expect(errore).toBeInstanceOf(ErroreApi);
      expect(errore.message).toBe('La risposta si è interrotta: il messaggio non è stato salvato.');
    });

    it('JSON non valido nel flusso è un flusso interrotto', async () => {
      fetchFinto(() => flusso(['event: testo\ndata: {rotto\n\n']));
      const errore = await inviaMessaggio(9, 'x', gestoriVuoti).catch((e) => e);
      expect(errore).toBeInstanceOf(ErroreApi);
      expect(errore.message).toBe('La risposta si è interrotta: il messaggio non è stato salvato.');
    });

    it('409 prima del flusso segue le regole normali', async () => {
      fetchFinto(() => json({ errore: 'Chat occupata.' }, 409));
      const errore = await inviaMessaggio(9, 'x', gestoriVuoti).catch((e) => e);
      expect(errore.message).toBe('Chat occupata.');
      expect(errore.stato).toBe(409);
    });

    it('interrompere propaga AbortError', async () => {
      const controllore = new AbortController();
      impostaFetch(async () => {
        throw new DOMException('Interrotto', 'AbortError');
      });
      const errore = await inviaMessaggio(9, 'x', gestoriVuoti, controllore.signal).catch((e) => e);
      expect(errore).not.toBeInstanceOf(ErroreApi);
      expect(errore.name).toBe('AbortError');
    });
  });
});
