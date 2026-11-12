<script lang="ts">
  import { onDestroy } from 'svelte';
  import { TESTO_BACKEND_SPENTO } from '../lib/api';
  import type { StatoApp } from '../lib/stato.svelte';

  let { stato }: { stato: StatoApp } = $props();

  const DURATA_MS = 8000;
  const timer = new Map<number, ReturnType<typeof setTimeout>>();

  // Ogni avviso si chiude da solo dopo qualche secondo.
  $effect(() => {
    for (const avviso of stato.avvisi) {
      if (timer.has(avviso.id)) continue;
      const id = avviso.id;
      timer.set(id, setTimeout(() => chiudi(id), DURATA_MS));
    }
  });

  function chiudi(id: number): void {
    clearTimeout(timer.get(id));
    timer.delete(id);
    stato.chiudiAvviso(id);
  }

  onDestroy(() => timer.forEach((t) => clearTimeout(t)));

  // «Back-end spento» lo dice già la striscia in cima: qui non si ripete.
  const visibili = $derived(stato.avvisi.filter((a) => a.testo !== TESTO_BACKEND_SPENTO));
</script>

{#if visibili.length > 0}
  <div class="avvisi">
    {#each visibili as avviso (avviso.id)}
      <div class="avviso" role="alert">
        <span>{avviso.testo}</span>
        <button type="button" class="chiudi" aria-label="Chiudi l'avviso" onclick={() => chiudi(avviso.id)}>×</button>
      </div>
    {/each}
  </div>
{/if}

<style>
  .avvisi {
    position: fixed;
    right: 20px;
    bottom: 20px;
    z-index: 20;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: min(380px, calc(100vw - 40px));
  }

  .avviso {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 12px 10px 14px;
    border-radius: var(--raggio);
    border: 1px solid var(--errore);
    border-left-width: 3px;
    background: var(--errore-fondo);
    color: var(--testo);
    font-size: 14px;
    box-shadow: var(--ombra);
    animation: entra 0.18s ease-out;
  }

  .avviso span {
    flex: 1;
  }

  .chiudi {
    flex: none;
    border: none;
    background: none;
    padding: 0 6px;
    border-radius: var(--raggio-piccolo);
    color: var(--errore-testo);
    font-size: 18px;
    line-height: 1.2;
  }

  @keyframes entra {
    from {
      opacity: 0;
      transform: translateY(6px);
    }
  }
</style>
