<script lang="ts">
  import type { Strumento } from '../lib/api';
  import { rendiMarkdown } from '../lib/markdown';
  import RigaStrumento from './RigaStrumento.svelte';

  type Props = {
    ruolo: 'utente' | 'assistente';
    testo: string;
    strumenti?: Strumento[] | null;
    /** La risposta sta ancora arrivando. */
    inCorso?: boolean;
    /** La domanda di un turno fallito: non è stata salvata. */
    nonSalvato?: boolean;
  };

  let { ruolo, testo, strumenti = null, inCorso = false, nonSalvato = false }: Props = $props();
</script>

{#if ruolo === 'utente'}
  <div class="utente" class:non-salvato={nonSalvato} data-test="messaggio-utente">
    <div class="riquadro">{testo}</div>
    {#if nonSalvato}<span class="nota">non salvato</span>{/if}
  </div>
{:else}
  <div class="assistente" class:in-corso={inCorso} aria-busy={inCorso} data-test="messaggio-assistente">
    {#if strumenti && strumenti.length > 0}
      <div class="strumenti">
        {#each strumenti as strumento, i (i)}
          <RigaStrumento {strumento} />
        {/each}
      </div>
    {/if}
    {#if testo}
      <!-- Unico punto in cui il testo del modello entra come HTML: ripulito da rendiMarkdown. -->
      <div class="markdown">{@html rendiMarkdown(testo)}</div>
    {:else if inCorso}
      <span class="attesa" aria-label="Sto rispondendo"></span>
    {/if}
  </div>
{/if}

<style>
  .utente {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
  }

  .riquadro {
    max-width: 78%;
    padding: 9px 14px;
    border-radius: var(--raggio);
    background: var(--riquadro-utente);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .non-salvato .riquadro {
    opacity: 0.65;
  }

  .nota {
    font-size: 11px;
    color: var(--testo-lieve);
  }

  .assistente {
    max-width: 100%;
    overflow-wrap: anywhere;
  }

  .strumenti {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    margin-bottom: 8px;
  }

  /* Il cursore discreto in fondo al testo che sta arrivando. */
  .in-corso .markdown > :global(:last-child)::after {
    content: '▍';
    margin-left: 1px;
    opacity: 0.4;
    animation: lampeggia 1s steps(2) infinite;
  }

  .attesa {
    display: inline-block;
    width: 8px;
    height: 8px;
    margin: 8px 0;
    border-radius: 50%;
    background: var(--testo-lieve);
    animation: respira 1.4s ease-in-out infinite;
  }

  @keyframes lampeggia {
    50% {
      opacity: 0;
    }
  }

  @keyframes respira {
    0%,
    100% {
      opacity: 0.25;
    }
    50% {
      opacity: 0.9;
    }
  }
</style>
