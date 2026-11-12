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
import { inizioTesto } from './testo';

export type Vista =
  | { tipo: 'chat'; chatId: number | null; progettoId: number | null }
  | { tipo: 'progetto'; progettoId: number };

/** chatId è null finché una chat nuova non è stata creata sul back-end. */
export type Turno = { chatId: number | null; domanda: string; testo: string; strumenti: Strumento[] };
/** Un turno fallito: l'errore e la domanda (non salvata), legati alla chat del turno. */
export type ErroreTurno = { chatId: number | null; testo: string; domanda: string };
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
  /** Al massimo un errore per chat: resta finché in quella chat non parte un nuovo invio. */
  erroriTurno = $state<ErroreTurno[]>([]);
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

  /** Siamo nella vista di una chat nuova, non ancora creata sul back-end. */
  private get suChatNuova(): boolean {
    return this.chatAperta === null && this.vista.tipo === 'chat' && this.vista.chatId === null;
  }

  private èQuiLaChat(chatId: number | null): boolean {
    return chatId === null ? this.suChatNuova : this.chatAperta?.id === chatId;
  }

  /** Il turno in corso, solo se appartiene alla chat che l'utente ha davanti
   *  (o alla chat nuova che sta ancora creando e che non ha lasciato). */
  get turnoVisibile(): Turno | null {
    return this.turno && this.èQuiLaChat(this.turno.chatId) ? this.turno : null;
  }

  /** L'errore del turno fallito nella chat che l'utente ha davanti, se c'è. */
  get erroreTurnoVisibile(): ErroreTurno | null {
    return this.erroriTurno.find((e) => this.èQuiLaChat(e.chatId)) ?? null;
  }

  private togliErroreTurno(chatId: number | null): void {
    this.erroriTurno = this.erroriTurno.filter((e) => e.chatId !== chatId);
  }

  /** «Rimetti nella casella»: la domanda fallita in testa, prima del testo già scritto. */
  rimettiDomanda(): void {
    const errore = this.erroreTurnoVisibile;
    if (!errore) return;
    this.bozza = this.bozza.trim() ? `${errore.domanda}\n\n${this.bozza}` : errore.domanda;
  }

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
      // Un errore del back-end (non di rete) vuol dire che risponde.
      if (e instanceof ErroreApi && !e.backendSpento) this.backendSpento = false;
      else this.notaBackend(e);
    }
  }

  // --- navigazione ---

  nuovaChat(progettoId?: number): void {
    this.chatAperta = null;
    this.togliErroreTurno(null);
    this.vista = { tipo: 'chat', chatId: null, progettoId: progettoId ?? null };
  }

  async apriChat(id: number): Promise<void> {
    await this.azione(async () => {
      const chat = await this.api.leggiChat(id);
      this.chatAperta = chat;
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

    this.bozza = '';
    this.turno = { chatId: this.chatAperta?.id ?? null, domanda, testo: '', strumenti: [] };
    let chatId = this.turno.chatId;
    this.togliErroreTurno(chatId);
    let chatCreata = false;

    try {
      if (chatId === null) {
        const progettoId = this.vista.tipo === 'chat' ? this.vista.progettoId : null;
        const chat = await this.api.creaChat(progettoId);
        chatId = chat.id;
        chatCreata = true;
        if (this.turno) this.turno.chatId = chatId;
        // Se nel frattempo l'utente ha lasciato la chat nuova, non lo riporto indietro.
        if (this.suChatNuova) {
          this.chatAperta = chat;
          this.vista = { tipo: 'chat', chatId: chat.id, progettoId: chat.progetto_id };
        }
      }
      const esito = await this.api.inviaMessaggio(chatId, domanda, {
        suTesto: (pezzo) => {
          if (this.turno) this.turno.testo += pezzo;
        },
        suStrumento: (strumento) => {
          if (this.turno) this.turno.strumenti.push(strumento);
        },
      });
      // Il messaggio è salvato dal back-end; lo aggiungo solo se la sua chat è quella aperta.
      if (this.chatAperta && this.chatAperta.id === chatId) {
        const ora = new Date().toISOString();
        this.chatAperta.messaggi.push(
          { id: esito.messaggio_utente_id, ruolo: 'utente', testo: domanda, strumenti: null, creato: ora },
          { id: esito.messaggio_assistente_id, ruolo: 'assistente', testo: esito.risposta, strumenti: esito.strumenti, creato: ora },
        );
        this.chatAperta.titolo = esito.titolo;
      }
      this.turno = null;
    } catch (e) {
      const testo = e instanceof Error ? e.message : 'Errore imprevisto.';
      this.turno = null;
      this.notaBackend(e);
      // L'errore resta sempre nella chat del turno, con la domanda: chi ci torna lo ritrova.
      this.togliErroreTurno(chatId);
      this.erroriTurno.push({ chatId, testo, domanda });
      if (this.èQuiLaChat(chatId)) {
        // La domanda torna nella casella solo se è vuota: il testo scritto durante il turno non si tocca
        // (c'è «Rimetti nella casella»).
        if (!this.bozza.trim()) this.bozza = domanda;
      } else {
        this.avvisi.push({
          id: this.prossimoAvviso++,
          testo: `Il messaggio «${inizioTesto(domanda)}» non è stato inviato: ${testo}`,
        });
      }
      // Una chat creata da questo turno esiste sul back-end: compare nell'elenco per poterci tornare.
      if (chatCreata) await this.ricarica();
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
      const pulita = q.trim();
      const risultati = await this.api.cerca(pulita);
      if (richiesta === this.ultimaRicerca) this.ricerca = { q: pulita, risultati };
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
    this.togliErroreTurno(id);
    if (this.chatAperta?.id === id) this.nuovaChat();
    await this.ricarica();
  }

  async eliminaProgetto(id: number): Promise<void> {
    const riuscita = await this.azione(async () => {
      await this.api.cancellaProgetto(id);
    });
    if (!riuscita) return;
    const eraAperto =
      this.progettoAperto?.id === id ||
      this.chatAperta?.progetto_id === id ||
      (this.vista.tipo === 'progetto' && this.vista.progettoId === id);
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
      if (this.vista.tipo === 'chat' && this.vista.chatId === id) this.vista.progettoId = spostata.progetto_id;
    });
    if (riuscita) await this.ricarica();
  }
}
