<script lang="ts">
  import type { StatoApp } from '../lib/stato.svelte';

  let { stato }: { stato: StatoApp } = $props();

  let area = $state<HTMLTextAreaElement>();

  // Durante un turno, in qualsiasi chat, la casella resta modificabile ma l'invio è bloccato.
  const puoInviare = $derived(stato.bozza.trim().length > 0 && stato.turno === null);
  const turnoAltrove = $derived(stato.turno !== null && stato.turnoVisibile === null);

  // La casella si allarga con il testo fino a qualche riga: in Edge e Chrome con il CSS
  // (field-sizing), negli altri browser misurando il testo.
  const altezzaDaCss = typeof CSS !== 'undefined' && CSS.supports('field-sizing', 'content');
  $effect(() => {
    void stato.bozza;
    if (!area || altezzaDaCss) return;
    area.style.height = 'auto';
    area.style.height = `${area.scrollHeight}px`;
  });

  // Pronta a scrivere quando si apre una chat.
  $effect(() => {
    void stato.vista;
    area?.focus();
  });

  function invia(): void {
    if (puoInviare) void stato.invia();
  }

  function suTasto(e: KeyboardEvent): void {
    // Invio invia, Maiusc+Invio va a capo; durante la composizione (IME) Invio conferma la parola.
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      invia();
    }
  }
</script>

{#if turnoAltrove}
  <p class="nota" role="status">Sto ancora rispondendo in un'altra chat…</p>
{/if}
<form
  class="casella"
  onsubmit={(e) => {
    e.preventDefault();
    invia();
  }}
>
  <textarea
    bind:this={area}
    bind:value={stato.bozza}
    rows="1"
    placeholder="Scrivi con calma…"
    aria-label="Messaggio"
    data-test="casella"
    onkeydown={suTasto}
  ></textarea>
  <button type="submit" class="invia" disabled={!puoInviare} aria-label="Invia" data-test="invia">↑</button>
</form>

<style>
  .nota {
    margin: 0 0 8px;
    font-size: 13px;
    color: var(--testo-tenue);
    text-align: center;
  }

  .casella {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    padding: 10px 10px 10px 16px;
    border: 1px solid var(--linea-forte);
    border-radius: var(--raggio);
    background: var(--superficie);
    transition: border-color 0.15s;
  }

  .casella:focus-within {
    border-color: var(--bordo-fuoco);
  }

  textarea {
    flex: 1;
    field-sizing: content;
    min-height: 26px;
    max-height: 200px;
    padding: 3px 0;
    border: none;
    outline: none;
    resize: none;
    background: transparent;
    line-height: 1.5;
  }

  textarea::placeholder {
    color: var(--testo-lieve);
  }

  .invia {
    flex: none;
    width: 32px;
    height: 32px;
    border: none;
    border-radius: var(--raggio-piccolo);
    background: var(--accento);
    color: var(--su-accento);
    font-size: 17px;
    font-weight: 700;
    line-height: 1;
    transition: opacity 0.15s;
  }

  .invia:disabled {
    opacity: 0.35;
  }
</style>
