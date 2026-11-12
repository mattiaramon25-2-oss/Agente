<script lang="ts">
  import type { Strumento } from '../lib/api';
  import { rigaStrumento } from '../lib/testo';

  let { strumento }: { strumento: Strumento } = $props();

  const testo = $derived(rigaStrumento(strumento));
</script>

<div class="riga" data-test="riga-strumento" title={testo}>{testo}</div>

<style>
  .riga {
    display: inline-block;
    max-width: 100%;
    padding: 2px 9px;
    border-radius: var(--raggio-piccolo);
    border: 1px solid var(--strumento-bordo);
    background: var(--strumento-fondo);
    color: var(--strumento-testo);
    font-size: 12px;
    font-family: var(--carattere-codice);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
