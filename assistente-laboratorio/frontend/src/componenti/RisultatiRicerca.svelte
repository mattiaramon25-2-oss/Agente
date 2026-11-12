<script lang="ts">
  import type { RisultatoRicerca } from '../lib/api';
  import type { StatoApp } from '../lib/stato.svelte';
  import { partiEvidenziate } from '../lib/testo';

  type Props = { stato: StatoApp; q: string; risultati: RisultatoRicerca[] };
  let { stato, q, risultati }: Props = $props();

  const nomeRuolo = (ruolo: string) => (ruolo === 'utente' ? 'Tu' : 'Assistente');
</script>

<section class="risultati" aria-label="Risultati della ricerca">
  <h2 class="etichetta-sezione">Risultati</h2>
  {#each risultati as r (r.messaggio_id)}
    <button type="button" class="risultato" data-test="risultato" onclick={() => stato.apriChat(r.chat_id)}>
      <span class="titolo">{r.titolo}</span>
      <span class="estratto"
        ><span class="ruolo">{nomeRuolo(r.ruolo)}:</span>
        <!-- Solo testo: le occorrenze stanno nelle parti di indice dispari. -->{#each partiEvidenziate(r.estratto, q) as parte, i (i)}{#if i % 2 === 1}<mark>{parte}</mark>{:else}{parte}{/if}{/each}</span
      >
    </button>
  {:else}
    <p class="vuoto">Nessun risultato.</p>
  {/each}
</section>

<style>
  .risultati {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .etichetta-sezione {
    margin-bottom: 6px;
  }

  .risultato {
    display: flex;
    flex-direction: column;
    gap: 2px;
    width: 100%;
    padding: 7px 9px;
    border: none;
    border-radius: var(--raggio-piccolo);
    background: none;
    text-align: left;
  }

  .risultato:hover {
    background: var(--linea);
  }

  .titolo {
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .estratto {
    font-size: 12px;
    line-height: 1.45;
    color: var(--testo-tenue);
    overflow-wrap: anywhere;
  }

  .ruolo {
    color: var(--testo-lieve);
  }

  /* Evidenziatura calda e neutra: il verde acqua resta alla chat aperta. */
  mark {
    background: var(--evidenziato);
    color: inherit;
    border-radius: var(--raggio-piccolo);
    padding: 0 2px;
  }

  .vuoto {
    margin: 0;
    padding: 4px 9px;
    font-size: 13px;
    color: var(--testo-lieve);
  }
</style>
