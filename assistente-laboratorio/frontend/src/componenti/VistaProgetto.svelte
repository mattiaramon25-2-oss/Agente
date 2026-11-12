<script lang="ts">
  import type { Progetto } from '../lib/api';
  import type { StatoApp } from '../lib/stato.svelte';
  import MenuAzioni from './MenuAzioni.svelte';

  let { stato, progetto }: { stato: StatoApp; progetto: Progetto } = $props();

  // Copie modificabili di nome e istruzioni, riprese dal progetto quando se ne apre un altro.
  let nome = $state('');
  let istruzioni = $state('');
  let idMostrato: number | null = null;
  let salvate = $state(false);
  let pulsanteNuova: HTMLButtonElement;

  $effect(() => {
    if (progetto.id === idMostrato) return;
    idMostrato = progetto.id;
    nome = progetto.nome;
    istruzioni = progetto.istruzioni;
    salvate = false;
  });

  const istruzioniCambiate = $derived(istruzioni !== progetto.istruzioni);

  async function salvaNome(): Promise<void> {
    const pulito = nome.trim();
    if (!pulito) {
      nome = progetto.nome;
      return;
    }
    if (pulito !== progetto.nome) await stato.salvaProgetto(progetto.id, { nome: pulito });
    nome = progetto.nome;
  }

  function tastoNome(e: KeyboardEvent & { currentTarget: HTMLInputElement }): void {
    if (e.key === 'Enter') {
      e.preventDefault();
      e.currentTarget.blur();
    } else if (e.key === 'Escape') {
      nome = progetto.nome;
      e.currentTarget.blur();
    }
  }

  async function salvaIstruzioni(): Promise<void> {
    await stato.salvaProgetto(progetto.id, { istruzioni });
    salvate = istruzioni === progetto.istruzioni;
  }

  const formatoData = new Intl.DateTimeFormat('it-IT', { day: 'numeric', month: 'short' });
  const data = (iso: string) => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? '' : formatoData.format(d);
  };
</script>

<section class="vista-progetto" aria-label="Progetto">
  <header class="percorso">
    <span>Progetti</span>
    <span class="separatore" aria-hidden="true">›</span>
    <span class="titolo">{progetto.nome}</span>
  </header>

  <div class="scorrimento">
    <div class="colonna contenuto">
      <input
        class="nome"
        aria-label="Nome del progetto"
        bind:value={nome}
        onblur={salvaNome}
        onkeydown={tastoNome}
      />

      <div class="blocco">
        <label class="etichetta-sezione" for="istruzioni-progetto">Istruzioni</label>
        <textarea
          id="istruzioni-progetto"
          rows="6"
          placeholder="Come deve rispondere l'assistente nelle chat di questo progetto?"
          data-test="istruzioni"
          bind:value={istruzioni}
          oninput={() => (salvate = false)}
        ></textarea>
        <div class="azioni">
          {#if salvate && !istruzioniCambiate}<span class="salvate" role="status">Salvate</span>{/if}
          <button
            type="button"
            class="pulsante-tenue"
            data-test="salva-istruzioni"
            disabled={!istruzioniCambiate}
            onclick={salvaIstruzioni}>Salva</button
          >
        </div>
      </div>

      <div class="blocco">
        <div class="intestazione">
          <h2 class="etichetta-sezione">Chat</h2>
          <button
            type="button"
            class="pulsante-tenue"
            bind:this={pulsanteNuova}
            onclick={() => stato.nuovaChat(progetto.id)}
            >Nuova chat in questo progetto</button
          >
        </div>
        <div class="elenco">
          {#each stato.chatDelProgetto as chat (chat.id)}
            <div class="voce">
              <button type="button" class="apri" data-test="chat" onclick={() => stato.apriChat(chat.id)}>
                <span class="testo-chat">{chat.titolo}</span>
                <span class="data">{data(chat.aggiornata)}</span>
              </button>
              <MenuAzioni {stato} {chat} quandoRimossa={() => pulsanteNuova?.focus()} />
            </div>
          {:else}
            <p class="vuoto">Ancora nessuna chat in questo progetto.</p>
          {/each}
        </div>
      </div>
    </div>
  </div>
</section>

<style>
  .vista-progetto {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .scorrimento {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .contenuto {
    display: flex;
    flex-direction: column;
    gap: 28px;
    padding-top: 32px;
    padding-bottom: 40px;
  }

  .nome {
    width: 100%;
    padding: 4px 8px;
    margin-left: -9px;
    border: 1px solid transparent;
    border-radius: var(--raggio-piccolo);
    background: transparent;
    font-size: 24px;
    font-weight: 500;
    outline: none;
  }

  .nome:hover {
    border-color: var(--linea-forte);
  }

  .nome:focus {
    border-color: var(--bordo-fuoco);
    background: var(--superficie);
  }

  .blocco {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  textarea {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid var(--linea-forte);
    border-radius: var(--raggio);
    background: var(--superficie);
    line-height: 1.5;
    resize: vertical;
    outline: none;
  }

  textarea:focus {
    border-color: var(--bordo-fuoco);
  }

  textarea::placeholder {
    color: var(--testo-lieve);
  }

  .azioni {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
  }

  .salvate {
    font-size: 13px;
    color: var(--testo-tenue);
  }

  .intestazione {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .elenco {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .apri {
    display: flex;
    gap: 12px;
  }

  .testo-chat {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .data {
    flex: none;
    font-size: 12px;
    color: var(--testo-lieve);
  }

  .vuoto {
    margin: 0;
    font-size: 14px;
    color: var(--testo-lieve);
  }
</style>
