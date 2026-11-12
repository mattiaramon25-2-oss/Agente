<script lang="ts">
  import { applicaTema, leggiScelta, salvaScelta, temaEffettivo, type SceltaTema } from '../lib/tema';

  const OPZIONI: { valore: SceltaTema; etichetta: string }[] = [
    { valore: 'automatico', etichetta: 'Automatico' },
    { valore: 'chiaro', etichetta: 'Chiaro' },
    { valore: 'scuro', etichetta: 'Scuro' },
  ];

  const preferenza = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null;

  let scelta = $state<SceltaTema>(leggiScelta());
  let preferisceScuro = $state(preferenza?.matches ?? false);

  // «Automatico» segue il tema di Windows anche quando cambia con l'app aperta.
  $effect(() => {
    if (!preferenza) return;
    const suCambio = (e: MediaQueryListEvent) => (preferisceScuro = e.matches);
    preferenza.addEventListener('change', suCambio);
    return () => preferenza.removeEventListener('change', suCambio);
  });

  $effect(() => {
    applicaTema(temaEffettivo(scelta, preferisceScuro));
  });

  function scegli(valore: SceltaTema): void {
    scelta = valore;
    salvaScelta(valore);
  }
</script>

<div class="tema" role="group" aria-label="Tema">
  {#each OPZIONI as opzione, i (opzione.valore)}
    {#if i > 0}<span class="punto" aria-hidden="true">·</span>{/if}
    <button
      type="button"
      class:scelto={scelta === opzione.valore}
      aria-pressed={scelta === opzione.valore}
      onclick={() => scegli(opzione.valore)}>{opzione.etichetta}</button
    >
  {/each}
</div>

<style>
  .tema {
    display: flex;
    align-items: center;
    gap: 2px;
    font-size: 12px;
    color: var(--testo-lieve);
  }

  button {
    border: none;
    background: none;
    padding: 3px 6px;
    border-radius: var(--raggio-piccolo);
    color: var(--testo-lieve);
  }

  button:hover {
    color: var(--testo-tenue);
  }

  button.scelto {
    color: var(--testo);
    font-weight: 600;
  }
</style>
