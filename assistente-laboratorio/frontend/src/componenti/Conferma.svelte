<script lang="ts">
  import { onMount } from 'svelte';

  type Props = {
    titolo: string;
    messaggio: string;
    etichetta?: string;
    onconferma: () => void;
    onannulla: () => void;
  };

  let { titolo, messaggio, etichetta = 'Elimina', onconferma, onannulla }: Props = $props();

  const id = $props.id();
  let dialogo: HTMLDialogElement;
  let annulla: HTMLButtonElement;
  let confermato = false;

  // Finestra modale vera: Esc annulla e il fuoco parte dal pulsante sicuro.
  onMount(() => {
    dialogo.showModal();
    annulla.focus();
  });

  function conferma(): void {
    confermato = true;
    dialogo.close();
  }

  function suChiusura(): void {
    if (confermato) onconferma();
    else onannulla();
  }
</script>

<dialog bind:this={dialogo} aria-labelledby="{id}-titolo" aria-describedby="{id}-messaggio" onclose={suChiusura}>
  <h2 id="{id}-titolo">{titolo}</h2>
  <p id="{id}-messaggio">{messaggio}</p>
  <div class="azioni">
    <button type="button" class="pulsante-tenue" bind:this={annulla} onclick={() => dialogo.close()}>Annulla</button>
    <button type="button" class="pulsante-pericolo" data-test="conferma" onclick={conferma}>{etichetta}</button>
  </div>
</dialog>

<style>
  dialog {
    width: min(400px, calc(100vw - 40px));
    padding: 22px 24px 18px;
    border: 1px solid var(--linea-forte);
    border-radius: 12px;
    background: var(--fondo);
    color: var(--testo);
    box-shadow: var(--ombra);
  }

  dialog::backdrop {
    background: var(--velo);
  }

  h2 {
    margin: 0 0 8px;
    font-size: 16px;
    font-weight: 600;
  }

  p {
    margin: 0 0 20px;
    color: var(--testo-tenue);
    font-size: 14px;
  }

  .azioni {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
