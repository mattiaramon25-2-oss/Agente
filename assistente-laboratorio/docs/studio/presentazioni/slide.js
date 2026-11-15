/* Navigazione delle presentazioni e scelta del tema.
   Nessuna libreria. Va caricato nella <head>: il tema si applica prima che la pagina si veda.

   Tasti nelle presentazioni:
     →  Spazio  PagGiù   slide successiva        ←  PagSu   slide precedente
     Home / Fine         prima / ultima slide
     N  note «Da dire a voce»      E  tutte le slide in elenco
     F  schermo intero             T  tema chiaro / scuro
*/
(function () {
  'use strict';

  var CHIAVE_TEMA = 'presentazioni-tema';
  var LARGHEZZA = 1280;
  var ALTEZZA = 720;
  var radice = document.documentElement;

  /* ───── Tema ───── */

  function leggi(chiave) {
    try {
      return window.localStorage.getItem(chiave);
    } catch (errore) {
      return null;
    }
  }

  function scrivi(chiave, valore) {
    try {
      window.localStorage.setItem(chiave, valore);
    } catch (errore) {
      /* Navigazione privata o archivio bloccato: il tema vale solo per questa pagina. */
    }
  }

  var temaSalvato = leggi(CHIAVE_TEMA);
  if (temaSalvato === 'chiaro' || temaSalvato === 'scuro') {
    radice.dataset.tema = temaSalvato;
  }

  function temaAttuale() {
    if (radice.dataset.tema) return radice.dataset.tema;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'scuro' : 'chiaro';
  }

  function cambiaTema() {
    var nuovo = temaAttuale() === 'scuro' ? 'chiaro' : 'scuro';
    radice.dataset.tema = nuovo;
    scrivi(CHIAVE_TEMA, nuovo);
  }

  /* ───── Presentazione ───── */

  function crea(tag, classe, testo) {
    var elemento = document.createElement(tag);
    if (classe) elemento.className = classe;
    if (testo) elemento.textContent = testo;
    return elemento;
  }

  function pulsante(azione, testo, titolo, classe) {
    var b = crea('button', classe || '', testo);
    b.type = 'button';
    b.dataset.azione = azione;
    b.title = titolo;
    b.setAttribute('aria-label', titolo);
    return b;
  }

  function avviaMazzo() {
    var corpo = document.body;
    var slide = Array.prototype.slice.call(document.querySelectorAll('body > section.slide'));
    if (!slide.length) return;
    var totale = slide.length;
    var corrente = 1;

    var cornici = slide.map(function (sezione, i) {
      var cornice = crea('div', 'cornice');
      var tela = crea('div', 'tela');
      sezione.parentNode.insertBefore(cornice, sezione);
      tela.appendChild(sezione);
      cornice.appendChild(tela);
      var nota = sezione.querySelector('aside.note');
      if (nota) cornice.appendChild(nota);
      sezione.dataset.n = String(i + 1);
      sezione.dataset.tot = String(totale);
      cornice.dataset.n = String(i + 1);
      return cornice;
    });

    var barra = crea('nav', 'barra');
    barra.setAttribute('aria-label', 'Comandi della presentazione');
    var indice = crea('a', '', 'Indice');
    indice.href = 'index.html';
    indice.title = 'Tutte le presentazioni';
    var nome = crea('span', 'nome', document.title.split(' · ')[0]);
    var bNote = pulsante('note', 'Note', 'Note da dire a voce (N)');
    var bElenco = pulsante('elenco', 'Elenco', 'Tutte le slide in elenco (E)');
    var bIntero = pulsante('intero', 'Schermo intero', 'Schermo intero (F)');
    var bTema = pulsante('tema', 'Tema', 'Tema chiaro o scuro (T)');
    var bIndietro = pulsante('indietro', '‹', 'Slide precedente (←)', 'freccia');
    var contatore = crea('span', 'contatore');
    var bAvanti = pulsante('avanti', '›', 'Slide successiva (→)', 'freccia');
    [indice, nome, crea('span', 'spazio'), bNote, bElenco, bIntero, bTema, bIndietro, contatore, bAvanti].forEach(function (e) {
      barra.appendChild(e);
    });
    var avanzamento = crea('div', 'avanzamento');
    var riempimento = crea('span');
    avanzamento.appendChild(riempimento);
    corpo.appendChild(avanzamento);
    corpo.appendChild(barra);
    corpo.classList.add('pronto');

    function ridimensiona() {
      var elenco = corpo.classList.contains('elenco');
      var tela = (elenco ? cornici[0] : cornici[corrente - 1]).querySelector('.tela');
      var scala = Math.min(tela.clientWidth / LARGHEZZA, tela.clientHeight / ALTEZZA);
      if (scala > 0) corpo.style.setProperty('--scala', String(scala));
    }

    function vai(n, senzaIndirizzo) {
      corrente = Math.max(1, Math.min(totale, Math.round(Number(n)) || 1));
      cornici.forEach(function (c, i) {
        c.classList.toggle('attiva', i === corrente - 1);
      });
      contatore.textContent = corrente + ' / ' + totale;
      riempimento.style.width = (totale > 1 ? ((corrente - 1) / (totale - 1)) * 100 : 100) + '%';
      bIndietro.disabled = corrente === 1;
      bAvanti.disabled = corrente === totale;
      if (!senzaIndirizzo && window.history && window.history.replaceState) {
        try {
          window.history.replaceState(null, '', '#' + corrente);
        } catch (errore) {
          /* Alcuni browser non lo permettono su file://: la slide cambia lo stesso. */
        }
      }
      ridimensiona();
    }

    function alterna(classe, bottone) {
      var attivo = corpo.classList.toggle(classe);
      bottone.setAttribute('aria-pressed', attivo ? 'true' : 'false');
      return attivo;
    }

    function note() {
      alterna('con-note', bNote);
      ridimensiona();
    }

    function elenco() {
      var attivo = alterna('elenco', bElenco);
      ridimensiona();
      if (attivo) cornici[corrente - 1].scrollIntoView({ block: 'center' });
      else window.scrollTo(0, 0);
    }

    function schermoIntero() {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (radice.requestFullscreen) radice.requestFullscreen();
    }

    var azioni = {
      avanti: function () { vai(corrente + 1); },
      indietro: function () { vai(corrente - 1); },
      note: note,
      elenco: elenco,
      intero: schermoIntero,
      tema: cambiaTema
    };

    barra.addEventListener('click', function (evento) {
      var b = evento.target.closest('button[data-azione]');
      if (b && azioni[b.dataset.azione]) azioni[b.dataset.azione]();
    });

    cornici.forEach(function (cornice) {
      cornice.addEventListener('click', function (evento) {
        if (!corpo.classList.contains('elenco') || evento.target.closest('aside.note, a')) return;
        vai(cornice.dataset.n);
        elenco();
      });
    });

    document.addEventListener('keydown', function (evento) {
      if (evento.ctrlKey || evento.altKey || evento.metaKey) return;
      var tasto = evento.key;
      var lettera = tasto.length === 1 ? tasto.toLowerCase() : '';
      if (lettera === 'n') return note();
      if (lettera === 'e') return elenco();
      if (lettera === 'f') return schermoIntero();
      if (lettera === 't') return cambiaTema();
      if (corpo.classList.contains('elenco')) return;
      var mossa = null;
      if (tasto === 'ArrowRight' || tasto === 'PageDown' || tasto === ' ' || tasto === 'ArrowDown') mossa = corrente + 1;
      else if (tasto === 'ArrowLeft' || tasto === 'PageUp' || tasto === 'ArrowUp') mossa = corrente - 1;
      else if (tasto === 'Home') mossa = 1;
      else if (tasto === 'End') mossa = totale;
      if (mossa === null) return;
      evento.preventDefault();
      vai(mossa);
    });

    /* Scorrimento con il dito, per tablet e telefono. */
    var inizioX = null;
    document.addEventListener('touchstart', function (evento) {
      inizioX = evento.touches.length === 1 ? evento.touches[0].clientX : null;
    }, { passive: true });
    document.addEventListener('touchend', function (evento) {
      if (inizioX === null || corpo.classList.contains('elenco')) return;
      var dx = evento.changedTouches[0].clientX - inizioX;
      if (Math.abs(dx) > 60) vai(corrente + (dx < 0 ? 1 : -1));
      inizioX = null;
    }, { passive: true });

    document.addEventListener('fullscreenchange', function () {
      corpo.classList.toggle('intero', Boolean(document.fullscreenElement));
      ridimensiona();
    });
    window.addEventListener('resize', ridimensiona);
    window.addEventListener('hashchange', function () {
      vai(window.location.hash.slice(1), true);
    });

    window.mazzo = {
      vai: vai,
      get totale() { return totale; },
      get corrente() { return corrente; }
    };

    vai(window.location.hash.slice(1) || 1, true);
  }

  function avvia() {
    Array.prototype.forEach.call(document.querySelectorAll('.testata [data-azione="tema"]'), function (b) {
      b.addEventListener('click', cambiaTema);
    });
    if (document.body.classList.contains('mazzo')) avviaMazzo();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', avvia);
  else avvia();
})();
