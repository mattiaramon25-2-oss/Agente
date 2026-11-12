import { describe, expect, it, vi } from 'vitest';
import {
  ErroreApi,
  TESTO_BACKEND_SPENTO,
  type ApiBackend,
  type Chat,
  type ChatBreve,
  type FineTurno,
  type GestoriTurno,
  type Progetto,
  type RisultatoRicerca,
} from './api';
import { StatoApp } from './stato.svelte';

const ORA = '2026-11-11T10:00:00';

function chatVuota(id: number, progetto_id: number | null = null): Chat {
  return { id, titolo: 'Nuova chat', progetto_id, creata: ORA, aggiornata: ORA, messaggi: [] };
}

function progetto(id: number, nome = 'Progetto'): Progetto {
  return { id, nome, istruzioni: '', numero_chat: 0, creato: ORA, aggiornato: ORA };
}

function fine(over: Partial<FineTurno> = {}): FineTurno {
  return {
    risposta: 'Ciao!',
    strumenti: [],
    messaggio_utente_id: 10,
    messaggio_assistente_id: 11,
    titolo: 'Saluto',
    ...over,
  };
}

function apiFinta(over: Partial<ApiBackend> = {}): ApiBackend {
  const base = {
    salute: vi.fn(async () => ({ stato: 'ok', database: 'ok', agente: 'ok' })),
    elencaProgetti: vi.fn(async (): Promise<Progetto[]> => []),
    creaProgetto: vi.fn(async (nome: string) => progetto(1, nome)),
    aggiornaProgetto: vi.fn(async (id: number) => progetto(id)),
    cancellaProgetto: vi.fn(async () => {}),
    elencaChat: vi.fn(async (): Promise<ChatBreve[]> => []),
    creaChat: vi.fn(async (progetto_id: number | null) => chatVuota(5, progetto_id)),
    leggiChat: vi.fn(async (id: number) => chatVuota(id)),
    spostaChat: vi.fn(async (id: number, progetto_id: number | null) => ({ ...chatVuota(id, progetto_id) })),
    cancellaChat: vi.fn(async () => {}),
    cerca: vi.fn(async () => []),
    inviaMessaggio: vi.fn(async () => fine()),
  };
  return { ...base, ...over } as ApiBackend;
}

describe('StatoApp', () => {
  it('invia in una chat nuova crea la chat e salva il turno', async () => {
    const api = apiFinta({
      inviaMessaggio: vi.fn(async (_id: number, _t: string, g: GestoriTurno) => {
        g.suTesto('Ci');
        g.suStrumento({ nome: 'calcola', origine: 'mcp', argomenti: { espressione: '1+1' } });
        return fine({ strumenti: [{ nome: 'calcola', origine: 'mcp', argomenti: {} }] });
      }),
    });
    const stato = new StatoApp(api);
    stato.nuovaChat();
    stato.bozza = '  Ciao  ';
    await stato.invia();

    expect(api.creaChat).toHaveBeenCalledWith(null);
    expect(api.inviaMessaggio).toHaveBeenCalledWith(5, 'Ciao', expect.anything());
    expect(stato.turno).toBeNull();
    expect(stato.erroreTurno).toBeNull();
    expect(stato.bozza).toBe('');
    expect(stato.chatAperta?.titolo).toBe('Saluto');
    expect(stato.vista).toEqual({ tipo: 'chat', chatId: 5, progettoId: null });
    const [utente, assistente] = stato.chatAperta!.messaggi;
    expect(utente).toMatchObject({ id: 10, ruolo: 'utente', testo: 'Ciao' });
    expect(assistente).toMatchObject({ id: 11, ruolo: 'assistente', testo: 'Ciao!' });
    expect(assistente.strumenti).toHaveLength(1);
    expect(api.elencaProgetti).toHaveBeenCalled();
    expect(api.elencaChat).toHaveBeenCalledWith('nessuno');
  });

  it('durante il turno accumula testo e strumenti', async () => {
    let sblocca!: () => void;
    const api = apiFinta({
      inviaMessaggio: vi.fn(async (_id: number, _t: string, g: GestoriTurno) => {
        g.suTesto('Ci');
        g.suTesto('ao');
        g.suStrumento({ nome: 'ora', origine: 'mcp', argomenti: {} });
        await new Promise<void>((r) => (sblocca = r));
        return fine();
      }),
    });
    const stato = new StatoApp(api);
    stato.bozza = 'Ciao';
    const p = stato.invia();
    await vi.waitFor(() => expect(stato.turno?.testo).toBe('Ciao'));
    expect(stato.turno?.domanda).toBe('Ciao');
    expect(stato.turno?.strumenti).toHaveLength(1);
    sblocca();
    await p;
    expect(stato.turno).toBeNull();
  });

  it('riprova sulla stessa chat', async () => {
    const inviaMessaggio = vi
      .fn()
      .mockRejectedValueOnce(new ErroreApi('Agente spento.', 503))
      .mockResolvedValueOnce(fine());
    const api = apiFinta({ inviaMessaggio });
    const stato = new StatoApp(api);
    stato.bozza = 'Ciao';
    await stato.invia();
    expect(stato.erroreTurno?.testo).toBe('Agente spento.');
    // Un 503 con {"errore"} viene dal back-end, che quindi risponde: niente striscia.
    expect(stato.backendSpento).toBe(false);
    expect(stato.chatAperta?.id).toBe(5);
    expect(stato.bozza).toBe('Ciao');
    await stato.invia();
    expect(stato.erroreTurno).toBeNull();
    expect(api.creaChat).toHaveBeenCalledTimes(1);
    expect(inviaMessaggio.mock.calls[1][0]).toBe(5);
    expect(stato.chatAperta?.messaggi).toHaveLength(2);
  });

  it('ignora un secondo invio durante il turno', async () => {
    let sblocca!: () => void;
    const api = apiFinta({
      inviaMessaggio: vi.fn(async () => {
        await new Promise<void>((r) => (sblocca = r));
        return fine();
      }),
    });
    const stato = new StatoApp(api);
    stato.bozza = 'Uno';
    const p = stato.invia();
    await vi.waitFor(() => expect(stato.turno).not.toBeNull());
    stato.bozza = 'Due';
    await stato.invia();
    expect(api.inviaMessaggio).toHaveBeenCalledTimes(1);
    expect(stato.bozza).toBe('Due');
    sblocca();
    await p;
  });

  it('ignora la bozza vuota', async () => {
    const api = apiFinta();
    const stato = new StatoApp(api);
    stato.bozza = '   ';
    await stato.invia();
    expect(api.creaChat).not.toHaveBeenCalled();
    expect(stato.turno).toBeNull();
  });

  it('errore del turno rimette la bozza', async () => {
    const api = apiFinta({
      inviaMessaggio: vi.fn(async () => {
        throw new ErroreApi('Modello assente.', null);
      }),
    });
    const stato = new StatoApp(api);
    stato.bozza = 'Domanda';
    await stato.invia();
    expect(stato.turno).toBeNull();
    expect(stato.erroreTurno?.testo).toBe('Modello assente.');
    expect(stato.bozza).toBe('Domanda');
    expect(stato.backendSpento).toBe(false);
    expect(stato.chatAperta?.messaggi).toHaveLength(0);
  });

  it('back-end spento accende la striscia e controllaBackend la spegne', async () => {
    const api = apiFinta({
      creaChat: vi.fn(async () => {
        throw new ErroreApi(TESTO_BACKEND_SPENTO, null, true);
      }),
    });
    const stato = new StatoApp(api);
    stato.bozza = 'Ciao';
    await stato.invia();
    expect(stato.backendSpento).toBe(true);
    expect(stato.erroreTurno?.testo).toBe(TESTO_BACKEND_SPENTO);
    expect(stato.bozza).toBe('Ciao');
    await stato.controllaBackend();
    expect(stato.backendSpento).toBe(false);
  });

  it('controllaBackend lascia la striscia se il back-end non risponde', async () => {
    const api = apiFinta({
      salute: vi.fn(async () => {
        throw new ErroreApi(TESTO_BACKEND_SPENTO, null, true);
      }),
    });
    const stato = new StatoApp(api);
    stato.backendSpento = true;
    await stato.controllaBackend();
    expect(stato.backendSpento).toBe(true);
  });

  it('nuova chat dentro un progetto passa progetto_id', async () => {
    const api = apiFinta();
    const stato = new StatoApp(api);
    stato.nuovaChat(3);
    expect(stato.vista).toEqual({ tipo: 'chat', chatId: null, progettoId: 3 });
    stato.bozza = 'Ciao';
    await stato.invia();
    expect(api.creaChat).toHaveBeenCalledWith(3);
  });

  it('elimina la chat aperta torna a una chat vuota', async () => {
    const api = apiFinta();
    const stato = new StatoApp(api);
    await stato.apriChat(7);
    expect(stato.chatAperta?.id).toBe(7);
    await stato.eliminaChat(7);
    expect(api.cancellaChat).toHaveBeenCalledWith(7);
    expect(stato.chatAperta).toBeNull();
    expect(stato.vista).toEqual({ tipo: 'chat', chatId: null, progettoId: null });
  });

  it("errore di un'azione va negli avvisi", async () => {
    const api = apiFinta({
      cancellaChat: vi.fn(async () => {
        throw new ErroreApi('Un turno è in corso.', 409);
      }),
    });
    const stato = new StatoApp(api);
    await stato.apriChat(7);
    await stato.eliminaChat(7);
    expect(stato.avvisi).toHaveLength(1);
    expect(stato.avvisi[0].testo).toBe('Un turno è in corso.');
    expect(stato.chatAperta?.id).toBe(7);
    stato.chiudiAvviso(stato.avvisi[0].id);
    expect(stato.avvisi).toHaveLength(0);
  });

  it("ricerca sotto i 2 caratteri non chiama l'API", async () => {
    const api = apiFinta();
    const stato = new StatoApp(api);
    await stato.cerca('a');
    expect(api.cerca).not.toHaveBeenCalled();
    expect(stato.ricerca).toBeNull();
    await stato.cerca('ab');
    await stato.cerca(' ab ');
    expect(api.cerca).toHaveBeenLastCalledWith('ab');
    expect(stato.ricerca).toEqual({ q: 'ab', risultati: [] });
    await stato.cerca('');
    expect(stato.ricerca).toBeNull();
  });

  it('apriProgetto carica progetto e chat', async () => {
    const chat: ChatBreve = { id: 2, titolo: 'X', progetto_id: 4, creata: ORA, aggiornata: ORA };
    const api = apiFinta({
      elencaProgetti: vi.fn(async () => [progetto(4, 'Tesi')]),
      elencaChat: vi.fn(async (f?: number | 'nessuno') => (f === 4 ? [chat] : [])),
    });
    const stato = new StatoApp(api);
    await stato.carica();
    await stato.apriProgetto(4);
    expect(stato.vista).toEqual({ tipo: 'progetto', progettoId: 4 });
    expect(stato.progettoAperto?.nome).toBe('Tesi');
    expect(stato.chatDelProgetto).toEqual([chat]);
  });

  describe('turno legato alla sua chat', () => {
    function conDue(over: Partial<ApiBackend> = {}) {
      let sblocca!: () => void;
      const api = apiFinta({
        inviaMessaggio: vi.fn(async () => {
          await new Promise<void>((r) => (sblocca = r));
          return fine();
        }),
        ...over,
      });
      return { api, stato: new StatoApp(api), sblocca: () => sblocca() };
    }

    it("apro un'altra chat durante il turno: non si toccano i suoi messaggi", async () => {
      const { stato, sblocca } = conDue();
      await stato.apriChat(1);
      stato.bozza = 'Ciao';
      const p = stato.invia();
      await vi.waitFor(() => expect(stato.turno?.chatId).toBe(1));
      expect(stato.turnoVisibile).not.toBeNull();
      await stato.apriChat(2);
      expect(stato.turnoVisibile).toBeNull();
      sblocca();
      await p;
      expect(stato.chatAperta?.id).toBe(2);
      expect(stato.chatAperta?.messaggi).toHaveLength(0);
      expect(stato.turno).toBeNull();
    });

    it('riaprendo la chat prima di fine il turno si vede e i messaggi arrivano', async () => {
      const { stato, sblocca } = conDue();
      await stato.apriChat(1);
      stato.bozza = 'Ciao';
      const p = stato.invia();
      await vi.waitFor(() => expect(stato.turno).not.toBeNull());
      await stato.apriChat(2);
      await stato.apriChat(1);
      expect(stato.turnoVisibile?.domanda).toBe('Ciao');
      sblocca();
      await p;
      expect(stato.chatAperta?.id).toBe(1);
      expect(stato.chatAperta?.messaggi).toHaveLength(2);
    });

    it("chat nuova: se l'utente se ne va prima di creaChat non viene riportato indietro", async () => {
      let creata!: (c: Chat) => void;
      const { api, stato, sblocca } = conDue({
        creaChat: vi.fn(() => new Promise<Chat>((r) => (creata = r))),
      });
      stato.nuovaChat();
      stato.bozza = 'Ciao';
      const p = stato.invia();
      expect(stato.turnoVisibile).not.toBeNull();
      await stato.apriChat(2);
      expect(stato.turnoVisibile).toBeNull();
      creata(chatVuota(9));
      await vi.waitFor(() => expect(api.inviaMessaggio).toHaveBeenCalled());
      expect(stato.vista).toEqual({ tipo: 'chat', chatId: 2, progettoId: null });
      expect(stato.chatAperta?.id).toBe(2);
      expect(stato.turno?.chatId).toBe(9);
      sblocca();
      await p;
      expect(stato.chatAperta?.messaggi).toHaveLength(0);
    });

    it('errore dopo aver lasciato la chat: avviso e bozza corrente intatta', async () => {
      const { stato } = conDue({
        inviaMessaggio: vi.fn(async () => {
          await Promise.resolve();
          throw new ErroreApi('Modello assente.', null);
        }),
      });
      await stato.apriChat(1);
      stato.bozza = 'Ciao';
      const p = stato.invia();
      await stato.apriChat(2);
      stato.bozza = 'altro testo';
      await p;
      expect(stato.bozza).toBe('altro testo');
      expect(stato.erroreTurnoVisibile).toBeNull();
      expect(stato.avvisi.map((a) => a.testo)).toEqual(['Il messaggio non è stato inviato: Modello assente.']);
    });
  });

  it('eliminaProgetto con il progetto aperto riporta a una chat vuota', async () => {
    const api = apiFinta({ elencaProgetti: vi.fn(async () => [progetto(4)]) });
    const stato = new StatoApp(api);
    await stato.carica();
    await stato.apriProgetto(4);
    await stato.eliminaProgetto(4);
    expect(api.cancellaProgetto).toHaveBeenCalledWith(4);
    expect(stato.progettoAperto).toBeNull();
    expect(stato.vista).toEqual({ tipo: 'chat', chatId: null, progettoId: null });
  });

  it('eliminaProgetto con una chat del progetto aperta azzera la chat', async () => {
    const api = apiFinta({ leggiChat: vi.fn(async (id: number) => chatVuota(id, 4)) });
    const stato = new StatoApp(api);
    await stato.apriChat(7);
    await stato.eliminaProgetto(4);
    expect(stato.chatAperta).toBeNull();
    expect(stato.vista).toEqual({ tipo: 'chat', chatId: null, progettoId: null });
  });

  it('spostaChat aggiorna la chat aperta e la vista', async () => {
    const api = apiFinta();
    const stato = new StatoApp(api);
    await stato.apriChat(7);
    await stato.spostaChat(7, 3);
    expect(api.spostaChat).toHaveBeenCalledWith(7, 3);
    expect(stato.chatAperta?.progetto_id).toBe(3);
    expect(stato.vista).toEqual({ tipo: 'chat', chatId: 7, progettoId: 3 });
  });

  it('salvaProgetto aggiorna elenco e progetto aperto', async () => {
    const api = apiFinta({
      elencaProgetti: vi.fn(async () => [progetto(4, 'Vecchio')]),
      aggiornaProgetto: vi.fn(async (id: number) => ({ ...progetto(id, 'Nuovo'), istruzioni: 'x' })),
    });
    const stato = new StatoApp(api);
    await stato.carica();
    await stato.apriProgetto(4);
    await stato.salvaProgetto(4, { nome: 'Nuovo', istruzioni: 'x' });
    expect(api.aggiornaProgetto).toHaveBeenCalledWith(4, { nome: 'Nuovo', istruzioni: 'x' });
    expect(stato.progetti[0].nome).toBe('Nuovo');
    expect(stato.progettoAperto?.istruzioni).toBe('x');
  });

  it('una ricerca vecchia non sovrascrive quella nuova', async () => {
    const sblocchi: Array<() => void> = [];
    const api = apiFinta({
      cerca: vi.fn(
        (q: string) =>
          new Promise<RisultatoRicerca[]>((r) =>
            sblocchi.push(() => r([{ chat_id: 1, titolo: q, progetto_id: null, messaggio_id: 1, ruolo: 'utente', estratto: q }])),
          ),
      ),
    });
    const stato = new StatoApp(api);
    const uno = stato.cerca('ab');
    const due = stato.cerca('abc');
    sblocchi[1]();
    await due;
    sblocchi[0]();
    await uno;
    expect(stato.ricerca?.q).toBe('abc');
  });

  it('controllaBackend spegne la striscia anche con un errore del back-end raggiungibile', async () => {
    const api = apiFinta({
      salute: vi.fn(async () => {
        throw new ErroreApi('Database giù.', 500);
      }),
    });
    const stato = new StatoApp(api);
    stato.backendSpento = true;
    await stato.controllaBackend();
    expect(stato.backendSpento).toBe(false);
  });
});
