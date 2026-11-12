<script lang="ts">
  import { tick } from 'svelte';
  import type { StatoApp } from '../lib/stato.svelte';
  import Casella from './Casella.svelte';
  import Messaggio from './Messaggio.svelte';

  let { stato }: { stato: StatoApp } = $props();

  const messaggi = $derived(stato.chatAperta?.messaggi ?? []);
  const turno = $derived(stato.turnoVisibile);
  const errore = $derived(stato.erroreTurnoVisibile);
  const vuota = $derived(messaggi.length === 0 && !turno && !errore);

  const progetto = $derived.by(() => {
    const id = stato.chatAperta?.progetto_id ?? (stato.vista.tipo === 'chat' ? stato.vista.progettoId : null);
    return id === null ? null : (stato.progetti.find((p) => p.id === id) ?? null);
  });
  const titolo = $derived(stato.chatAperta?.titolo ?? 'Nuova chat');

  // La domanda fallita è già nella casella? Se no, l'errore offre «Rimetti nella casella».
  const domandaInCasella = $derived(errore !== null && stato.bozza.includes(errore.domanda));

  // Scorrimento: segue la risposta che arriva, se chi legge è già in fondo.
  let scorrimento = $state<HTMLDivElement>();
  let seguiFondo = true;
  let ultimaChat: number | null | undefined = undefined;

  function suScorrimento(): void {
    if (!scorrimento) return;
    seguiFondo = scorrimento.scrollHeight - scorrimento.scrollTop - scorrimento.clientHeight < 80;
  }

  $effect(() => {
    void messaggi.length;
    void turno?.testo;
    void turno?.strumenti.length;
    void errore;
    const chatId = stato.chatAperta?.id ?? null;
    if (chatId !== ultimaChat) {
      ultimaChat = chatId;
      seguiFondo = true;
    }
    if (!seguiFondo) return;
    void tick().then(() => scorrimento?.scrollTo({ top: scorrimento.scrollHeight }));
  });
</script>

<section class="vista-chat" aria-label="Conversazione">
  <header class="percorso">
    {#if progetto}
      <button type="button" class="progetto" onclick={() => stato.apriProgetto(progetto.id)}>{progetto.nome}</button>
      <span class="separatore" aria-hidden="true">›</span>
    {/if}
    <span class="titolo">{titolo}</span>
  </header>

  {#if vuota}
    <div class="benvenuto">
      <div class="colonna">
        <h1>Di cosa hai bisogno oggi?</h1>
        <Casella {stato} />
      </div>
    </div>
  {:else}
    <div class="scorrimento" bind:this={scorrimento} onscroll={suScorrimento}>
      <div class="colonna messaggi">
        {#each messaggi as m (m.id)}
          <Messaggio ruolo={m.ruolo} testo={m.testo} strumenti={m.strumenti} />
        {/each}
        {#if turno}
          <Messaggio ruolo="utente" testo={turno.domanda} />
          <Messaggio ruolo="assistente" testo={turno.testo} strumenti={turno.strumenti} inCorso />
        {/if}
        {#if errore}
          <Messaggio ruolo="utente" testo={errore.domanda} nonSalvato />
          <div class="errore-turno" role="alert" data-test="errore-turno">
            <p>{errore.testo}</p>
            {#if domandaInCasella}
              <p class="suggerimento">Il messaggio è tornato nella casella: puoi inviarlo di nuovo.</p>
            {:else}
              <p class="suggerimento">
                Il messaggio non è stato salvato.
                <button type="button" class="rimetti" data-test="rimetti" onclick={() => stato.rimettiDomanda()}>
                  Rimetti nella casella
                </button>
              </p>
            {/if}
          </div>
        {/if}
      </div>
    </div>
    <div class="piede">
      <div class="colonna">
        <Casella {stato} />
      </div>
    </div>
  {/if}
</section>

<style>
  .vista-chat {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .progetto {
    flex: none;
    padding: 2px 6px;
    margin-left: -6px;
    border: none;
    border-radius: var(--raggio-piccolo);
    background: none;
    color: var(--testo-tenue);
  }

  .progetto:hover {
    background: var(--laterale);
    color: var(--testo);
  }

  .benvenuto {
    flex: 1;
    display: flex;
    align-items: center;
    padding-bottom: 12vh;
  }

  .benvenuto h1 {
    margin: 0 0 22px;
    text-align: center;
    font-size: 24px;
    font-weight: 400;
    color: var(--testo-tenue);
  }

  .scorrimento {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .messaggi {
    display: flex;
    flex-direction: column;
    gap: 22px;
    padding-top: 28px;
    padding-bottom: 28px;
  }

  .errore-turno {
    padding: 10px 14px;
    border: 1px solid var(--errore);
    border-left-width: 3px;
    border-radius: var(--raggio);
    background: var(--errore-fondo);
    font-size: 14px;
  }

  .errore-turno p {
    margin: 0;
  }

  .errore-turno .suggerimento {
    margin-top: 2px;
    font-size: 12px;
    color: var(--testo-tenue);
  }

  .rimetti {
    margin-left: 4px;
    padding: 0;
    border: none;
    background: none;
    color: var(--errore-testo);
    font-size: inherit;
    text-decoration: underline;
    cursor: pointer;
  }

  .piede {
    flex: none;
    padding: 4px 0 20px;
  }
</style>
