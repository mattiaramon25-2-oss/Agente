<script lang="ts">
  import { onMount } from 'svelte';
  import { StatoApp } from './lib/stato.svelte';
  import Avvisi from './componenti/Avvisi.svelte';
  import BarraLaterale from './componenti/BarraLaterale.svelte';
  import StrisciaBackend from './componenti/StrisciaBackend.svelte';
  import VistaChat from './componenti/VistaChat.svelte';
  import VistaProgetto from './componenti/VistaProgetto.svelte';

  const stato = new StatoApp();

  onMount(() => {
    void stato.carica();
  });
</script>

<div class="app">
  <StrisciaBackend {stato} />
  <div class="finestra">
    <BarraLaterale {stato} />
    <main class="centrale">
      {#if stato.vista.tipo === 'progetto' && stato.progettoAperto}
        <VistaProgetto {stato} progetto={stato.progettoAperto} />
      {:else}
        <VistaChat {stato} />
      {/if}
    </main>
  </div>
  <Avvisi {stato} />
</div>

<style>
  .app {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .finestra {
    flex: 1;
    display: flex;
    min-height: 0;
  }

  .centrale {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }
</style>
