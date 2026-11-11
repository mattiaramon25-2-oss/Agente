<script lang="ts">
  import { tick } from 'svelte';
  import type { ChatBreve, Progetto } from '../lib/api';
  import type { StatoApp } from '../lib/stato.svelte';
  import Conferma from './Conferma.svelte';

  /** Menu «…» di una chat (Sposta, Elimina) o di un progetto (Elimina). */
  type Props = { stato: StatoApp; chat?: ChatBreve; progetto?: Progetto };
  let { stato, chat, progetto }: Props = $props();

  const LARGHEZZA = 210;
  const MARGINE = 8;

  let aperto = $state(false);
  let pannello = $state<'azioni' | 'sposta'>('azioni');
  let chiedeConferma = $state(false);
  let posizione = $state({ top: 0, left: 0 });
  let pulsante: HTMLButtonElement;
  let menu = $state<HTMLDivElement>();

  const nome = $derived(chat?.titolo ?? progetto?.nome ?? '');
  const destinazioni = $derived(stato.progetti.filter((p) => p.id !== chat?.progetto_id));

  const conferma = $derived(
    chat
      ? { titolo: 'Eliminare la chat?', messaggio: `«${chat.titolo}» verrà eliminata definitivamente.` }
      : {
          titolo: 'Eliminare il progetto?',
          messaggio: `«${progetto?.nome ?? ''}» verrà eliminato definitivamente insieme alle sue chat${
            progetto && progetto.numero_chat > 0 ? ` (${progetto.numero_chat})` : ''
          }.`,
        },
  );

  async function apri(): Promise<void> {
    const r = pulsante.getBoundingClientRect();
    const left = Math.max(MARGINE, Math.min(r.right - LARGHEZZA, innerWidth - LARGHEZZA - MARGINE));
    posizione = { top: r.bottom + 4, left };
    pannello = 'azioni';
    aperto = true;
    await mettiAFuoco();
  }

  /** Dopo ogni cambio di pannello: tiene il menu dentro la finestra e dà il fuoco alla prima voce. */
  async function mettiAFuoco(): Promise<void> {
    await tick();
    if (!menu) return;
    const altezza = menu.offsetHeight;
    if (posizione.top + altezza > innerHeight - MARGINE) {
      const sopra = pulsante.getBoundingClientRect().top - altezza - 4;
      posizione.top = Math.max(MARGINE, sopra);
    }
    menu.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus();
  }

  function chiudi(ridaiFuoco = true): void {
    aperto = false;
    if (ridaiFuoco) pulsante.focus();
  }

  async function mostraSposta(): Promise<void> {
    pannello = 'sposta';
    await mettiAFuoco();
  }

  async function sposta(progettoId: number | null): Promise<void> {
    chiudi();
    if (chat) await stato.spostaChat(chat.id, progettoId);
  }

  function elimina(): void {
    chiudi();
    chiedeConferma = true;
  }

  async function eliminaConfermato(): Promise<void> {
    chiedeConferma = false;
    if (chat) await stato.eliminaChat(chat.id);
    else if (progetto) await stato.eliminaProgetto(progetto.id);
  }

  function suPuntatore(e: PointerEvent): void {
    const bersaglio = e.target as Node;
    if (aperto && !menu?.contains(bersaglio) && !pulsante.contains(bersaglio)) chiudi(false);
  }

  function suTasto(e: KeyboardEvent): void {
    if (!aperto || !menu) return;
    if (e.key === 'Escape') {
      e.preventDefault();
      chiudi();
      return;
    }
    if (e.key === 'Tab') {
      chiudi(false);
      return;
    }
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const voci = [...menu.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')];
    const attuale = voci.indexOf(document.activeElement as HTMLButtonElement);
    const passo = e.key === 'ArrowDown' ? 1 : -1;
    voci[(attuale + passo + voci.length) % voci.length]?.focus();
  }
</script>

<svelte:window onpointerdown={suPuntatore} onkeydown={suTasto} onresize={() => aperto && chiudi(false)} />

<button
  type="button"
  class="tre-punti"
  class:visibile={aperto}
  bind:this={pulsante}
  aria-label="Azioni per {nome}"
  aria-haspopup="menu"
  aria-expanded={aperto}
  data-test="menu"
  onclick={() => (aperto ? chiudi() : apri())}>…</button
>

{#if aperto}
  <div
    class="menu"
    role="menu"
    tabindex="-1"
    aria-label="Azioni per {nome}"
    bind:this={menu}
    style:top="{posizione.top}px"
    style:left="{posizione.left}px"
    style:width="{LARGHEZZA}px"
  >
    {#if pannello === 'azioni'}
      {#if chat}
        <button type="button" role="menuitem" onclick={mostraSposta}>Sposta in progetto…</button>
      {/if}
      <button type="button" role="menuitem" class="pericolo" data-test="elimina" onclick={elimina}>Elimina</button>
    {:else}
      <p class="intestazione">Sposta in</p>
      {#if chat?.progetto_id !== null}
        <button type="button" role="menuitem" onclick={() => sposta(null)}>Nessun progetto</button>
      {/if}
      {#each destinazioni as p (p.id)}
        <button type="button" role="menuitem" onclick={() => sposta(p.id)}>{p.nome}</button>
      {/each}
      {#if destinazioni.length === 0 && chat?.progetto_id === null}
        <p class="vuoto">Ancora nessun progetto.</p>
      {/if}
    {/if}
  </div>
{/if}

{#if chiedeConferma}
  <Conferma
    titolo={conferma.titolo}
    messaggio={conferma.messaggio}
    onconferma={eliminaConfermato}
    onannulla={() => (chiedeConferma = false)}
  />
{/if}

<style>
  .tre-punti {
    flex: none;
    width: 26px;
    height: 26px;
    border: none;
    border-radius: 6px;
    background: none;
    color: var(--testo-tenue);
    line-height: 1;
    letter-spacing: 0.05em;
    opacity: 0;
    transition: opacity 0.12s;
  }

  .tre-punti:hover {
    background: var(--linea-forte);
  }

  /* Compare al passaggio del mouse sulla riga, con il fuoco o a menu aperto. */
  :global(.voce:hover) > .tre-punti,
  :global(.voce:focus-within) > .tre-punti,
  .tre-punti.visibile {
    opacity: 1;
  }

  .menu {
    position: fixed;
    z-index: 30;
    display: flex;
    flex-direction: column;
    max-height: min(320px, calc(100vh - 16px));
    overflow-y: auto;
    padding: 5px;
    border: 1px solid var(--linea-forte);
    border-radius: var(--raggio);
    background: var(--superficie);
    box-shadow: var(--ombra);
  }

  .menu button {
    border: none;
    background: none;
    padding: 6px 10px;
    border-radius: 6px;
    text-align: left;
    font-size: 14px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .menu button:hover,
  .menu button:focus-visible {
    background: var(--laterale);
    outline: none;
  }

  .menu .pericolo {
    color: var(--errore-testo);
  }

  .intestazione,
  .vuoto {
    margin: 0;
    padding: 4px 10px;
    font-size: 12px;
    color: var(--testo-lieve);
  }
</style>
