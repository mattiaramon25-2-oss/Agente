<script lang="ts">
  import { untrack } from 'svelte';
  import { TESTO_BACKEND_SPENTO } from '../lib/api';
  import type { StatoApp } from '../lib/stato.svelte';

  let { stato }: { stato: StatoApp } = $props();

  const INTERVALLO_MS = 5000;
  let eraSpento = false;

  // Finché il back-end non risponde lo si interroga ogni 5 secondi;
  // quando torna, la striscia sparisce e gli elenchi si ricaricano.
  $effect(() => {
    if (!stato.backendSpento) {
      if (eraSpento) {
        eraSpento = false;
        untrack(() => void stato.carica());
      }
      return;
    }
    eraSpento = true;
    const id = setInterval(() => void stato.controllaBackend(), INTERVALLO_MS);
    return () => clearInterval(id);
  });
</script>

{#if stato.backendSpento}
  <div class="striscia" role="alert" data-test="striscia-backend">{TESTO_BACKEND_SPENTO}</div>
{/if}

<style>
  .striscia {
    flex: none;
    padding: 7px 16px;
    text-align: center;
    font-size: 13px;
    background: var(--errore-fondo);
    color: var(--errore-testo);
    border-bottom: 1px solid var(--errore);
  }
</style>
