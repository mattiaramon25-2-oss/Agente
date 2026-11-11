<script lang="ts">
  import { onDestroy } from 'svelte';
  import type { StatoApp } from '../lib/stato.svelte';
  import MenuAzioni from './MenuAzioni.svelte';
  import RisultatiRicerca from './RisultatiRicerca.svelte';
  import SceltaTema from './SceltaTema.svelte';

  let { stato }: { stato: StatoApp } = $props();

  const ATTESA_RICERCA_MS = 300;

  let testoRicerca = $state('');
  let timerRicerca: ReturnType<typeof setTimeout> | undefined;
  let creaProgetto = $state(false);
  let nomeProgetto = $state('');

  const progettoAttivo = $derived(
    stato.vista.tipo === 'progetto' ? stato.vista.progettoId : (stato.chatAperta?.progetto_id ?? stato.vista.progettoId),
  );

  /** Da dentro un progetto, «Nuova chat» crea la chat in quel progetto. */
  function nuovaChat(): void {
    stato.nuovaChat(stato.vista.tipo === 'progetto' ? stato.vista.progettoId : undefined);
  }

  // La ricerca parte dopo una breve pausa nella scrittura; svuotando la casella tornano subito gli elenchi.
  function suRicerca(e: Event & { currentTarget: HTMLInputElement }): void {
    const q = e.currentTarget.value;
    clearTimeout(timerRicerca);
    if (q.trim().length < 2) {
      void stato.cerca(q);
      return;
    }
    timerRicerca = setTimeout(() => void stato.cerca(q), ATTESA_RICERCA_MS);
  }

  function tastoRicerca(e: KeyboardEvent): void {
    if (e.key === 'Escape' && testoRicerca) {
      testoRicerca = '';
      clearTimeout(timerRicerca);
      void stato.cerca('');
    }
  }

  async function confermaProgetto(): Promise<void> {
    const nome = nomeProgetto.trim();
    if (!nome) {
      creaProgetto = false;
      return;
    }
    const creato = await stato.creaProgetto(nome);
    if (creato) {
      creaProgetto = false;
      nomeProgetto = '';
      await stato.apriProgetto(creato.id);
    }
  }

  function tastoProgetto(e: KeyboardEvent): void {
    if (e.key === 'Enter') {
      e.preventDefault();
      void confermaProgetto();
    } else if (e.key === 'Escape') {
      creaProgetto = false;
      nomeProgetto = '';
    }
  }

  const prendiFuoco = (nodo: HTMLElement) => nodo.focus();

  onDestroy(() => clearTimeout(timerRicerca));
</script>

<nav class="laterale" aria-label="Chat e progetti">
  <button type="button" class="pulsante-principale nuova" data-test="nuova-chat" onclick={nuovaChat}>+ Nuova chat</button>

  <input
    type="search"
    class="cerca"
    placeholder="Cerca nelle chat"
    aria-label="Cerca nelle chat"
    data-test="ricerca"
    bind:value={testoRicerca}
    oninput={suRicerca}
    onkeydown={tastoRicerca}
  />

  <div class="elenchi">
    {#if stato.ricerca}
      <RisultatiRicerca {stato} q={stato.ricerca.q} risultati={stato.ricerca.risultati} />
    {:else}
      <section aria-labelledby="titolo-progetti">
        <div class="intestazione">
          <h2 id="titolo-progetti" class="etichetta-sezione">Progetti</h2>
          <button
            type="button"
            class="aggiungi"
            aria-label="Nuovo progetto"
            title="Nuovo progetto"
            onclick={() => (creaProgetto = true)}>+</button
          >
        </div>
        {#if creaProgetto}
          <input
            class="nome-progetto"
            placeholder="Nome del progetto"
            aria-label="Nome del nuovo progetto"
            bind:value={nomeProgetto}
            onkeydown={tastoProgetto}
            onblur={() => !nomeProgetto.trim() && (creaProgetto = false)}
            {@attach prendiFuoco}
          />
        {/if}
        {#each stato.progetti as progetto (progetto.id)}
          <div class="voce" class:attiva={progettoAttivo === progetto.id}>
            <button
              type="button"
              class="apri"
              data-test="progetto"
              aria-current={stato.vista.tipo === 'progetto' && stato.vista.progettoId === progetto.id ? 'page' : undefined}
              onclick={() => stato.apriProgetto(progetto.id)}>{progetto.nome}</button
            >
            <MenuAzioni {stato} {progetto} />
          </div>
        {:else}
          {#if !creaProgetto}<p class="vuoto">Nessun progetto.</p>{/if}
        {/each}
      </section>

      <section aria-labelledby="titolo-recenti">
        <div class="intestazione">
          <h2 id="titolo-recenti" class="etichetta-sezione">Recenti</h2>
        </div>
        {#each stato.recenti as chat (chat.id)}
          <div class="voce" class:aperta={stato.chatAperta?.id === chat.id}>
            <button
              type="button"
              class="apri"
              data-test="chat"
              aria-current={stato.chatAperta?.id === chat.id ? 'page' : undefined}
              onclick={() => stato.apriChat(chat.id)}>{chat.titolo}</button
            >
            <MenuAzioni {stato} {chat} />
          </div>
        {:else}
          <p class="vuoto">Nessuna chat.</p>
        {/each}
      </section>
    {/if}
  </div>

  <div class="piede">
    <SceltaTema />
  </div>
</nav>

<style>
  .laterale {
    flex: none;
    width: var(--larghezza-laterale);
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 16px 12px 12px;
    background: var(--laterale);
    border-right: 1px solid var(--linea);
  }

  .nuova {
    width: 100%;
  }

  .cerca,
  .nome-progetto {
    width: 100%;
    padding: 6px 10px;
    border: 1px solid var(--linea-forte);
    border-radius: var(--raggio-piccolo);
    background: var(--superficie);
    font-size: 14px;
    outline: none;
  }

  .cerca:focus,
  .nome-progetto:focus {
    border-color: var(--accento);
  }

  .cerca::placeholder,
  .nome-progetto::placeholder {
    color: var(--testo-lieve);
  }

  .nome-progetto {
    margin-bottom: 4px;
  }

  .elenchi {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 18px;
    margin: 4px -4px 0;
    padding: 0 4px;
  }

  .intestazione {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 24px;
    margin-bottom: 4px;
    padding-left: 9px;
  }

  .aggiungi {
    width: 24px;
    height: 24px;
    border: none;
    border-radius: 6px;
    background: none;
    color: var(--testo-lieve);
    font-size: 17px;
    line-height: 1;
  }

  .aggiungi:hover {
    background: var(--linea-forte);
    color: var(--testo);
  }

  .vuoto {
    margin: 0;
    padding: 2px 9px;
    font-size: 13px;
    color: var(--testo-lieve);
  }

  .piede {
    padding-top: 10px;
    border-top: 1px solid var(--linea);
  }
</style>
