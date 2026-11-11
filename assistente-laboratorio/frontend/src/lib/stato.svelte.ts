// Stato dell'app (Svelte 5, rune): progetti, chat, turno in corso, errori e ricerca.
// Riceve l'API del back-end come oggetto, così i test possono passarne una finta.

import {
  apiBackend,
  ErroreApi,
  type ApiBackend,
  type Chat,
  type ChatBreve,
  type Messaggio,
  type Progetto,
  type RisultatoRicerca,
  type Strumento,
} from './api';

export type Vista =
  | { tipo: 'chat'; chatId: number | null; progettoId: number | null }
  | { tipo: 'progetto'; progettoId: number };

export type Turno = { domanda: string; testo: string; strumenti: Strumento[] };
export type Avviso = { id: number; testo: string };

const LUNGHEZZA_MINIMA_RICERCA = 2;

export class StatoApp {
  progetti = $state<Progetto[]>([]);
  recenti = $state<ChatBreve[]>([]);
  vista = $state<Vista>({ tipo: 'chat', chatId: null, progettoId: null });
  chatAperta = $state<Chat | null>(null);
  progettoAperto = $state<Progetto | null>(null);
  chatDelProgetto = $state<ChatBreve[]>([]);
  turno = $state<Turno | null>(null);
  erroreTurno = $state<string | null>(null);
  bozza = $state('');
  backendSpento = $state(false);
  ricerca = $state<{ q: string; risultati: RisultatoRicerca[] } | null>(null);
  avvisi = $state<Avviso[]>([]);

  private api: ApiBackend;
  private prossimoAvviso = 1;
  private ultimaRicerca = 0;

  constructor(api: ApiBackend = apiBackend) {
    this.api = api;
  }

  // --- errori ---

  private notaBackend(e: unknown): void {
    if (e instanceof ErroreApi && e.backendSpento) this.backendSpento = true;
  }

  private avvisa(e: unknown): void {
    this.notaBackend(e);
    const testo = e instanceof Error ? e.message : 'Errore imprevisto.';
    this.avvisi.push({ id: this.prossimoAvviso++, testo });
  }

  chiudiAvviso(id: number): void {
    this.avvisi = this.avvisi.filter((a) => a.id !== id);
  }

  /** Esegue un'azione e trasforma l'eventuale errore in un avviso; true se è riuscita. */
  private async azione(f: () => Promise<void>): Promise<boolean> {
    try {
      await f();
      return true;
    } catch (e) {
      this.avvisa(e);
      return false;
    }
  }

  // --- caricamento ---

  async carica(): Promise<void> {
    await this.azione(async () => {
      const [progetti, recenti] = await Promise.all([this.api.elencaProgetti(), this.api.elencaChat('nessuno')]);
      this.progetti = progetti;
      this.recenti = recenti;
    });
  }

  /** Dopo un cambiamento: ricarica le liste e, se serve, la vista del progetto aperto. */
  private async ricarica(): Promise<void> {
    await this.carica();
    const id = this.progettoAperto?.id;
    if (id !== undefined && this.vista.tipo === 'progetto' && this.vista.progettoId === id) {
      await this.azione(async () => {
        this.chatDelProgetto = await this.api.elencaChat(id);
        this.progettoAperto = this.progetti.find((p) => p.id === id) ?? this.progettoAperto;
      });
    }
  }

  async controllaBackend(): Promise<void> {
    try {
      await this.api.salute();
      this.backendSpento = false;
    } catch (e) {
      this.notaBackend(e);
    }
  }

  // --- navigazione ---

  nuovaChat(progettoId?: number): void {
    this.chatAperta = null;
    this.erroreTurno = null;
    this.vista = { tipo: 'chat', chatId: null, progettoId: progettoId ?? null };
  }

  async apriChat(id: number): Promise<void> {
    await this.azione(async () => {
      const chat = await this.api.leggiChat(id);
      this.chatAperta = chat;
      this.erroreTurno = null;
      this.vista = { tipo: 'chat', chatId: chat.id, progettoId: chat.progetto_id };
    });
  }

  async apriProgetto(id: number): Promise<void> {
    await this.azione(async () => {
      const chat = await this.api.elencaChat(id);
      const progetto = this.progetti.find((p) => p.id === id);
      if (!progetto) throw new Error('Progetto non trovato.');
      this.chatDelProgetto = chat;
      this.progettoAperto = progetto;
      this.chatAperta = null;
      this.vista = { tipo: 'progetto', progettoId: id };
    });
  }

  // --- turno ---

  async invia(): Promise<void> {
    const domanda = this.bozza.trim();
    if (!domanda || this.turno) return;

    this.erroreTurno = null;
    this.bozza = '';
    this.turno = { domanda, testo: '', strumenti: [] };

    try {
      if (!this.chatAperta) {
        const progettoId = this.vista.tipo === 'chat' ? this.vista.progettoId : null;
        const chat = await this.api.creaChat(progettoId);
        this.chatAperta = chat;
        this.vista = { tipo: 'chat', chatId: chat.id, progettoId: chat.progetto_id };
      }
      const chat = this.chatAperta;
      const esito = await this.api.inviaMessaggio(chat.id, domanda, {
        suTesto: (pezzo) => {
          if (this.turno) this.turno.testo += pezzo;
        },
        suStrumento: (strumento) => {
          if (this.turno) this.turno.strumenti.push(strumento);
        },
      });
      const ora = new Date().toISOString();
      const utente: Messaggio = {
        id: esito.messaggio_utente_id,
        ruolo: 'utente',
        testo: domanda,
        strumenti: null,
        creato: ora,
      };
      const assistente: Messaggio = {
        id: esito.messaggio_assistente_id,
        ruolo: 'assistente',
        testo: esito.risposta,
        strumenti: esito.strumenti,
        creato: ora,
      };
      chat.messaggi.push(utente, assistente);
      chat.titolo = esito.titolo;
      this.turno = null;
    } catch (e) {
      this.turno = null;
      this.erroreTurno = e instanceof Error ? e.message : 'Errore imprevisto.';
      this.bozza = domanda;
      this.notaBackend(e);
      return;
    }
    await this.ricarica();
  }

  // --- ricerca ---

  async cerca(q: string): Promise<void> {
    const richiesta = ++this.ultimaRicerca;
    if (q.trim().length < LUNGHEZZA_MINIMA_RICERCA) {
      this.ricerca = null;
      return;
    }
    try {
      const risultati = await this.api.cerca(q);
      if (richiesta === this.ultimaRicerca) this.ricerca = { q, risultati };
    } catch (e) {
      if (richiesta === this.ultimaRicerca) this.avvisa(e);
    }
  }

  // --- progetti e chat ---

  async creaProgetto(nome: string): Promise<Progetto | null> {
    let creato: Progetto | null = null;
    const riuscita = await this.azione(async () => {
      creato = await this.api.creaProgetto(nome, '');
    });
    if (riuscita) await this.carica();
    return creato;
  }

  async salvaProgetto(id: number, campi: { nome?: string; istruzioni?: string }): Promise<void> {
    await this.azione(async () => {
      const aggiornato = await this.api.aggiornaProgetto(id, campi);
      this.progetti = this.progetti.map((p) => (p.id === id ? aggiornato : p));
      if (this.progettoAperto?.id === id) this.progettoAperto = aggiornato;
    });
  }

  async eliminaChat(id: number): Promise<void> {
    const riuscita = await this.azione(async () => {
      await this.api.cancellaChat(id);
    });
    if (!riuscita) return;
    if (this.chatAperta?.id === id) this.nuovaChat();
    await this.ricarica();
  }

  async eliminaProgetto(id: number): Promise<void> {
    const riuscita = await this.azione(async () => {
      await this.api.cancellaProgetto(id);
    });
    if (!riuscita) return;
    const eraAperto =
      this.progettoAperto?.id === id || this.chatAperta?.progetto_id === id || this.vista.tipo === 'progetto' && this.vista.progettoId === id;
    if (eraAperto) {
      this.progettoAperto = null;
      this.chatDelProgetto = [];
      this.nuovaChat();
    }
    await this.ricarica();
  }

  async spostaChat(id: number, progettoId: number | null): Promise<void> {
    const riuscita = await this.azione(async () => {
      const spostata = await this.api.spostaChat(id, progettoId);
      if (this.chatAperta?.id === id) this.chatAperta.progetto_id = spostata.progetto_id;
    });
    if (riuscita) await this.ricarica();
  }
}
