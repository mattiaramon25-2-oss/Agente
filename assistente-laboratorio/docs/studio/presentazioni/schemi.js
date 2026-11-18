/* Gli schemi del progetto, descritti una volta sola e disegnati in SVG nel browser.
   Nessuna libreria. Ogni <figure class="schema" data-schema="nome"> riceve il suo disegno.

   Due tipi di schema:
   - «flusso»: nodi su una griglia (colonna c, riga r), frecce con etichetta, gruppi tratteggiati;
   - «sequenza»: attori in colonna e messaggi numerati dall'alto in basso.

   Colori dei nodi (classi in stile.css): llm = chi ragiona, esegue = chi esegue gli strumenti,
   dati = dove restano i dati, attenzione = rifiuto, limite o testo non fidato,
   esterno = fuori dal progetto, evidenza = il punto da guardare.

   Per correggere uno schema si cambia la sua descrizione in SCHEMI, più sotto: l'atlante e le
   presentazioni si aggiornano insieme. */
(function () {
  'use strict';

  var contatore = 0;

  function esc(testo) {
    return String(testo).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function righe(valore) {
    if (valore === undefined || valore === null) return [];
    return Array.isArray(valore) ? valore : [valore];
  }

  function testa(id, larghezza, altezza, titolo) {
    return (
      '<svg class="sch" role="img" aria-label="' + esc(titolo) + '" viewBox="0 0 ' + larghezza + ' ' + altezza +
      '" width="' + larghezza + '" height="' + altezza + '" preserveAspectRatio="xMidYMid meet">' +
      '<defs>' +
      '<marker id="' + id + '-p" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path class="sch-punta" d="M0 0.6 10 5 0 9.4z"/></marker>' +
      '<marker id="' + id + '-e" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5.4" markerHeight="5.4" orient="auto-start-reverse"><path class="sch-punta evidenza" d="M0 0.6 10 5 0 9.4z"/></marker>' +
      '</defs>'
    );
  }

  /* Testo su più righe, centrato in (x, y). */
  function etichetta(x, y, valore, classe, spazio) {
    var r = righe(valore);
    if (!r.length) return '';
    var passo = 18;
    var primo = y - ((r.length - 1) * passo) / 2 + 5;
    var corpo = r.map(function (riga, i) {
      return '<tspan x="' + x + '" y="' + (primo + i * passo) + '">' + esc(riga) + '</tspan>';
    }).join('');
    return '<text class="' + classe + '" text-anchor="middle"' + (spazio ? ' data-spazio="' + Math.round(spazio) + '"' : '') + '>' + corpo + '</text>';
  }

  /* ───────────── Flusso ───────────── */

  function disegnaFlusso(d) {
    var g = d.griglia || {};
    var col = g.col || 180;
    var riga = g.riga || 84;
    var dx = g.dx === undefined ? 80 : g.dx;
    var dy = g.dy === undefined ? 44 : g.dy;
    var m = g.margine === undefined ? 28 : g.margine;
    var alto = g.alto || 0;
    var id = 'sch' + (++contatore);

    function larg(i) { return Array.isArray(col) ? col[Math.min(i, col.length - 1)] : col; }
    function alt(i) { return Array.isArray(riga) ? riga[Math.min(i, riga.length - 1)] : riga; }
    function inizio(k, misura, passo) {
      var intero = Math.floor(k);
      var v = 0;
      for (var i = 0; i < intero; i++) v += misura(i) + passo;
      return v + (k - intero) * (misura(intero) + passo);
    }
    function X(c) { return m + inizio(c, larg, dx); }
    function Y(r) { return m + alto + inizio(r, alt, dy); }
    function cella(o) {
      var lc = o.lc || 1;
      var ar = o.ar || 1;
      var x = X(o.c);
      var y = Y(o.r);
      var w = X(o.c + lc - 1) + larg(Math.floor(o.c + lc - 1)) - x;
      var h = Y(o.r + ar - 1) + alt(Math.floor(o.r + ar - 1)) - y;
      return { x: x, y: y, w: w, h: h };
    }

    var forme = {};
    var larghezza = 0;
    var altezza = 0;

    var nodi = (d.nodi || []).map(function (n) {
      var b = cella(n);
      if (n.l) { b.x += (b.w - n.l) / 2; b.w = n.l; }
      if (n.a) { b.y += (b.h - n.a) / 2; b.h = n.a; }
      b.cx = b.x + b.w / 2;
      b.cy = b.y + b.h / 2;
      forme[n.id] = b;
      larghezza = Math.max(larghezza, b.x + b.w);
      altezza = Math.max(altezza, b.y + b.h);
      return { n: n, b: b };
    });

    var gruppi = (d.gruppi || []).map(function (gr) {
      var b = cella(gr);
      var bordo = gr.bordo === undefined ? 14 : gr.bordo;
      var sopra = gr.t ? 30 : bordo;
      b = { x: b.x - bordo, y: b.y - sopra, w: b.w + bordo * 2, h: b.h + sopra + bordo };
      b.cx = b.x + b.w / 2;
      b.cy = b.y + b.h / 2;
      if (gr.id) forme[gr.id] = b;
      larghezza = Math.max(larghezza, b.x + b.w);
      altezza = Math.max(altezza, b.y + b.h);
      return { g: gr, b: b };
    });

    larghezza = Math.round(larghezza + m);
    altezza = Math.round(altezza + m);

    function comune(a0, a1, b0, b1) {
      var basso = Math.max(a0, b0);
      var altoMax = Math.min(a1, b1);
      return altoMax - basso > 6 ? (basso + altoMax) / 2 : null;
    }

    function lato(b, quale, scarto) {
      var s = scarto || 0;
      if (quale === 'dx') return [b.x + b.w, b.cy + s];
      if (quale === 'sx') return [b.x, b.cy + s];
      if (quale === 'su') return [b.cx + s, b.y];
      return [b.cx + s, b.y + b.h];
    }

    function percorso(f) {
      var a = forme[f.da];
      var b = forme[f.a];
      if (!a || !b) throw new Error('Schema: freccia verso un nodo che non esiste: ' + f.da + ' → ' + f.a);
      var yc = comune(a.y, a.y + a.h, b.y, b.y + b.h);
      var xc = comune(a.x, a.x + a.w, b.x, b.x + b.w);
      var via = f.via || (yc !== null ? 'h' : xc !== null ? 'v' : 'hvh');
      var sd = f.sd || 0;
      var sa = f.sa === undefined ? sd : f.sa;
      var destra = b.cx >= a.cx;
      var sotto = b.cy >= a.cy;
      var p1, p4, mezzo;
      if (via === 'h') {
        var y = yc === null ? a.cy : yc;
        return [[destra ? a.x + a.w : a.x, y + sd], [destra ? b.x : b.x + b.w, y + sa]];
      }
      if (via === 'v') {
        var x = xc === null ? a.cx : xc;
        return [[x + sd, sotto ? a.y + a.h : a.y], [x + sa, sotto ? b.y : b.y + b.h]];
      }
      if (via === 'retta') {
        return [lato(a, destra ? 'dx' : 'sx', sd), lato(b, destra ? 'sx' : 'dx', sa)];
      }
      if (via === 'hv') {
        p1 = lato(a, f.esce || (destra ? 'dx' : 'sx'), sd);
        p4 = lato(b, f.entra || (p1[1] <= b.cy ? 'su' : 'giu'), f.sa || 0);
        return [p1, [p4[0], p1[1]], p4];
      }
      if (via === 'vh') {
        p1 = lato(a, f.esce || (sotto ? 'giu' : 'su'), sd);
        p4 = lato(b, f.entra || (p1[0] <= b.cx ? 'sx' : 'dx'), f.sa || 0);
        return [p1, [p1[0], p4[1]], p4];
      }
      if (via === 'vhv') {
        p1 = lato(a, f.esce || (sotto ? 'giu' : 'su'), sd);
        p4 = lato(b, f.entra || (sotto ? 'su' : 'giu'), f.sa || 0);
        if (f.giro) mezzo = (f.esce === 'giu' ? Math.max(p1[1], p4[1]) + f.giro : Math.min(p1[1], p4[1]) - f.giro);
        else mezzo = (p1[1] + p4[1]) / 2 + (f.my || 0);
        return [p1, [p1[0], mezzo], [p4[0], mezzo], p4];
      }
      p1 = lato(a, f.esce || (destra ? 'dx' : 'sx'), sd);
      p4 = lato(b, f.entra || (destra ? 'sx' : 'dx'), f.sa || 0);
      mezzo = (p1[0] + p4[0]) / 2 + (f.mx || 0);
      return [p1, [mezzo, p1[1]], [mezzo, p4[1]], p4];
    }

    var svg = testa(id, larghezza, altezza, d.titolo);

    gruppi.forEach(function (o) {
      svg += '<rect class="sch-gruppo" x="' + o.b.x + '" y="' + o.b.y + '" width="' + o.b.w + '" height="' + o.b.h + '" rx="16"/>';
      if (o.g.t) svg += '<text class="sch-gruppo-t" x="' + (o.b.x + 14) + '" y="' + (o.b.y + 20) + '">' + esc(o.g.t) + '</text>';
    });

    var etichette = '';
    (d.frecce || []).forEach(function (f) {
      var punti = percorso(f);
      var classe = 'sch-freccia' + (f.stile ? ' ' + f.stile : '');
      var punta = f.stile && f.stile.indexOf('evidenza') >= 0 ? id + '-e' : id + '-p';
      var dati = 'M' + punti.map(function (p) { return p[0] + ' ' + p[1]; }).join('L');
      svg += '<path class="' + classe + '" d="' + dati + '"' +
        (f.punta === false ? '' : ' marker-end="url(#' + punta + ')"') +
        (f.doppia ? ' marker-start="url(#' + punta + ')"' : '') + '/>';
      if (f.e === undefined) return;
      var scelto = f.seg;
      if (scelto === undefined) {
        var massimo = -1;
        for (var i = 0; i < punti.length - 1; i++) {
          var lunghezza = Math.abs(punti[i + 1][0] - punti[i][0]) + Math.abs(punti[i + 1][1] - punti[i][1]);
          if (lunghezza > massimo) { massimo = lunghezza; scelto = i; }
        }
      }
      var pos = f.pos === undefined ? 0.5 : f.pos;
      var da = punti[scelto];
      var a = punti[scelto + 1];
      var sposta = f.de || [0, 0];
      etichette += etichetta(
        Math.round(da[0] + (a[0] - da[0]) * pos + sposta[0]),
        Math.round(da[1] + (a[1] - da[1]) * pos + sposta[1]),
        f.e,
        'sch-etichetta' + (f.stile && f.stile.indexOf('evidenza') >= 0 ? ' evidenza' : '')
      );
    });

    nodi.forEach(function (o) {
      var n = o.n;
      var b = o.b;
      var forma = n.forma || 'rett';
      svg += '<g class="sch-nodo ' + (n.stile || '') + '" data-id="' + esc(n.id) + '">';
      if (forma === 'cilindro') {
        var ry = 9;
        svg += '<path class="sch-forma" d="M' + b.x + ' ' + (b.y + ry) + 'A' + b.w / 2 + ' ' + ry + ' 0 0 1 ' + (b.x + b.w) + ' ' + (b.y + ry) +
          'V' + (b.y + b.h - ry) + 'A' + b.w / 2 + ' ' + ry + ' 0 0 1 ' + b.x + ' ' + (b.y + b.h - ry) + 'Z"/>' +
          '<path class="sch-tratto" d="M' + b.x + ' ' + (b.y + ry) + 'A' + b.w / 2 + ' ' + ry + ' 0 0 0 ' + (b.x + b.w) + ' ' + (b.y + ry) + '"/>';
      } else {
        var raggio = forma === 'pillola' ? Math.min(b.w, b.h) / 2 : 11;
        svg += '<rect class="sch-forma" x="' + b.x + '" y="' + b.y + '" width="' + b.w + '" height="' + b.h + '" rx="' + raggio + '"/>';
      }
      if (forma === 'tabella') {
        svg += '<path class="sch-tratto" d="M' + b.x + ' ' + (b.y + 38) + 'H' + (b.x + b.w) + '"/>' +
          '<text class="sch-t" text-anchor="middle" x="' + b.cx + '" y="' + (b.y + 25) + '">' + esc(n.t) + '</text>';
        (n.righe || []).forEach(function (r, i) {
          var yr = b.y + 38 + 24 + i * 25;
          svg += '<text class="sch-mono" x="' + (b.x + 16) + '" y="' + yr + '">' + esc(r[0]) + '</text>';
          if (r[1]) svg += '<text class="sch-s" text-anchor="end" x="' + (b.x + b.w - 16) + '" y="' + yr + '">' + esc(r[1]) + '</text>';
        });
      } else {
        var sotto = righe(n.s);
        var altoTitolo = n.t ? 23 : 0;
        var totale = altoTitolo + sotto.length * 19;
        var su = b.cy - totale / 2 + (forma === 'cilindro' ? 6 : 0);
        if (n.t) svg += '<text class="sch-t" text-anchor="middle" x="' + b.cx + '" y="' + (su + 17) + '">' + esc(n.t) + '</text>';
        sotto.forEach(function (r, i) {
          if (r === '') return;
          svg += '<text class="sch-s' + (n.mono ? ' sch-mono' : '') + '" text-anchor="middle" x="' + b.cx + '" y="' + (su + altoTitolo + i * 19 + 15) + '">' + esc(r) + '</text>';
        });
      }
      svg += '</g>';
    });

    return svg + etichette + '</svg>';
  }

  /* ───────────── Sequenza ───────────── */

  function disegnaSequenza(d) {
    var col = d.colonna || 220;
    var passo = d.passo || 40;
    var m = 20;
    var numeri = 36;
    var id = 'sch' + (++contatore);
    var conSotto = d.attori.some(function (a) { return a.s; });
    var altoTesta = conSotto ? 58 : 44;
    var largoTesta = col - 34;
    var x = {};
    d.attori.forEach(function (a, i) { x[a.id] = m + numeri + col / 2 + i * col; });
    var larghezza = m * 2 + numeri + col * d.attori.length;

    var y = m + altoTesta + 14;
    var corpo = '';
    var numero = 0;
    d.passi.forEach(function (p) {
      if (p.sep) {
        y += 38;
        corpo += '<path class="sch-riga" d="M' + (m + numeri) + ' ' + (y - 14) + 'H' + (larghezza - m) + '"/>' +
          '<text class="sch-sep" text-anchor="middle" x="' + ((m + numeri + larghezza - m) / 2) + '" y="' + (y - 9) + '">' + esc(p.sep) + '</text>';
        return;
      }
      numero += 1;
      var testo = righe(p.nota || p.e);
      var yr;
      if (p.nota) {
        var altoNota = testo.length * 19 + 16;
        var centro = p.tra ? (x[p.tra[0]] + x[p.tra[1]]) / 2 : x[p.su];
        var largoNota = p.l || (p.tra ? Math.abs(x[p.tra[1]] - x[p.tra[0]]) + col - 60 : col - 22);
        y += 12;
        yr = y + altoNota / 2;
        corpo += '<g class="sch-nodo ' + (p.stile || 'piano') + '" data-id="nota-' + numero + '">' +
          '<rect class="sch-forma" x="' + (centro - largoNota / 2) + '" y="' + y + '" width="' + largoNota + '" height="' + altoNota + '" rx="9"/>' +
          testo.map(function (r, i) {
            return '<text text-anchor="middle" x="' + centro + '" y="' + (y + 8 + i * 19 + 15) + '">' + esc(r) + '</text>';
          }).join('') + '</g>';
        y += altoNota + 6;
      } else {
        y += Math.max(passo, testo.length * 18 + 22);
        yr = y;
        var da = x[p.da];
        var a = x[p.a];
        if (da === undefined || a === undefined) throw new Error('Schema: attore sconosciuto in ' + p.da + ' → ' + p.a);
        var evidenza = p.stile && p.stile.indexOf('evidenza') >= 0;
        corpo += '<path class="sch-freccia' + (p.ritorno ? ' tratteggio' : '') + (p.stile ? ' ' + p.stile : '') + '" d="M' + da + ' ' + y + 'H' + (a > da ? a - 2 : a + 2) +
          '" marker-end="url(#' + id + (evidenza ? '-e' : '-p') + ')"/>';
        var primo = y - 9 - (testo.length - 1) * 18;
        corpo += '<text class="sch-etichetta' + (evidenza ? ' evidenza' : '') + '" text-anchor="middle" data-spazio="' + Math.round(Math.abs(a - da) - 14) + '">' +
          testo.map(function (r, i) {
            return '<tspan x="' + (da + a) / 2 + '" y="' + (primo + i * 18) + '">' + esc(r) + '</tspan>';
          }).join('') + '</text>';
      }
      corpo += '<circle class="sch-cerchio" cx="' + (m + 13) + '" cy="' + yr + '" r="12"/>' +
        '<text class="sch-numero" text-anchor="middle" x="' + (m + 13) + '" y="' + (yr + 4.5) + '">' + numero + '</text>';
    });
    var altezza = Math.round(y + 22 + m);

    var svg = testa(id, larghezza, altezza, d.titolo);
    d.attori.forEach(function (a) {
      svg += '<path class="sch-vita" d="M' + x[a.id] + ' ' + (m + altoTesta) + 'V' + (altezza - m) + '"/>';
    });
    svg += corpo;
    d.attori.forEach(function (a) {
      var cx = x[a.id];
      var su = m + (altoTesta - (a.s ? 42 : 23)) / 2;
      svg += '<g class="sch-nodo ' + (a.stile || '') + '" data-id="' + esc(a.id) + '">' +
        '<rect class="sch-forma" x="' + (cx - largoTesta / 2) + '" y="' + m + '" width="' + largoTesta + '" height="' + altoTesta + '" rx="11"/>' +
        '<text class="sch-t" text-anchor="middle" x="' + cx + '" y="' + (su + 17) + '">' + esc(a.t) + '</text>' +
        (a.s ? '<text class="sch-s" text-anchor="middle" x="' + cx + '" y="' + (su + 38) + '">' + esc(a.s) + '</text>' : '') +
        '</g>';
    });
    return svg + '</svg>';
  }

  /* ───────────── Le descrizioni ───────────── */

  var SCHEMI = {};

  SCHEMI.sistema = {
    tipo: 'flusso',
    titolo: 'Tutto il sistema oggi: il browser parla con nginx, nginx con il back-end, il back-end con PostgreSQL e con l\'agente; l\'agente con LM Studio e con il server MCP',
    griglia: { col: 174, riga: 88, dx: 116, dy: 46 },
    gruppi: [{ id: 'agenti', c: 3, r: 1, ar: 2, t: 'un solo agente' }],
    nodi: [
      { id: 'pg', c: 2, r: 0, t: 'PostgreSQL', s: ['container database', ':5432'], forma: 'cilindro', stile: 'dati' },
      { id: 'browser', c: 0, r: 1, t: 'Browser', s: ['la chat, installata', 'come app'] },
      { id: 'nginx', c: 1, r: 1, t: 'nginx', s: ['container frontend', ':8780'] },
      { id: 'backend', c: 2, r: 1, t: 'Back-end', s: ['container backend', 'nessuna porta'] },
      { id: 'agente', c: 3, r: 1, t: 'Servizio agente', s: ['container agente', ':8767'] },
      { id: 'lm', c: 4, r: 1, t: 'LM Studio', s: ['sul computer', ':1234'], stile: 'llm esterno' },
      { id: 'cli', c: 3, r: 2, t: 'Terminale', s: ['python -m assistente'] },
      { id: 'mcp', c: 4, r: 2, t: 'Server MCP', s: ['10 strumenti', ':8765'], stile: 'esegue' },
      { id: 'note', c: 3, r: 3, t: 'note.sqlite3', s: ['cartella archivio/'], forma: 'cilindro', stile: 'dati' },
      { id: 'meteo', c: 4, r: 3, t: 'Open-Meteo', s: ['su Internet'], stile: 'esterno' }
    ],
    frecce: [
      { da: 'browser', a: 'nginx', e: 'HTTP' },
      { da: 'nginx', a: 'backend', e: '/api' },
      { da: 'backend', a: 'pg', e: 'SQL' },
      { da: 'backend', a: 'agente', e: ['/chat/stream', '(SSE)'] },
      { da: 'agenti', a: 'lm', e: ['API', 'OpenAI'] },
      { da: 'agenti', a: 'mcp', e: 'MCP' },
      { da: 'mcp', a: 'meteo', sd: 34, e: 'HTTPS' },
      { da: 'mcp', a: 'note', via: 'vhv', sd: -40 }
    ]
  };

  SCHEMI.terminale = {
    tipo: 'flusso',
    titolo: 'L\'assistente da terminale: un processo che parla con LM Studio, con il server MCP e, solo nella variante fastapi, con il servizio delle scadenze',
    griglia: { col: [84, 214, 214, 200], riga: 84, dx: 112, dy: 30 },
    nodi: [
      { id: 'tu', c: 0, r: 1, t: 'Tu', forma: 'pillola', a: 52 },
      { id: 'ass', c: 1, r: 0, ar: 3, t: 'Assistente', s: ['python -m assistente', '', 'terminale', 'grafo LangGraph', 'client MCP'] },
      { id: 'lm', c: 2, r: 0, t: 'LM Studio', s: ['sul computer · :1234/v1'], stile: 'llm esterno' },
      { id: 'mcp', c: 2, r: 1, t: 'Server MCP', s: ['10 strumenti', ':MCP_PORTA/mcp'], stile: 'esegue' },
      { id: 'api', c: 2, r: 2, t: 'Servizio FastAPI', s: ['solo variante fastapi', ':API_PORTA'], stile: 'esegue' },
      { id: 'note', c: 3, r: 0, t: 'archivio/', s: ['note.sqlite3'], forma: 'cilindro', stile: 'dati' },
      { id: 'meteo', c: 3, r: 1, t: 'Open-Meteo', s: ['su Internet'], stile: 'esterno' },
      { id: 'risorse', c: 3, r: 2, t: 'risorse/', s: ['catalogo, festività'], forma: 'cilindro', stile: 'dati' }
    ],
    frecce: [
      { da: 'tu', a: 'ass', doppia: true },
      { da: 'ass', a: 'lm', e: 'API OpenAI' },
      { da: 'ass', a: 'mcp', e: 'MCP' },
      { da: 'ass', a: 'api', e: 'HTTP GET', stile: 'tratteggio' },
      { da: 'mcp', a: 'meteo', e: 'HTTPS' },
      { da: 'mcp', a: 'note', via: 'hvh', sd: -22, sa: 0, e: 'note' },
      { da: 'mcp', a: 'risorse', via: 'hvh', sd: 22, sa: -18 },
      { da: 'api', a: 'risorse', sd: 18 }
    ]
  };

  SCHEMI['grafo-base'] = {
    tipo: 'flusso',
    titolo: 'Il grafo della lezione 4: dopo il nodo modello una sola decisione porta a fine, strumenti o limite',
    griglia: { col: [110, 190, 200, 110], riga: 84, dx: 136, dy: 40 },
    nodi: [
      { id: 'start', c: 0, r: 0, t: 'START', forma: 'pillola', a: 50 },
      { id: 'modello', c: 1, r: 0, t: 'modello', s: ['chiama LM Studio'], stile: 'llm' },
      { id: 'end', c: 3, r: 0, t: 'END', forma: 'pillola', a: 50 },
      { id: 'strumenti', c: 2, r: 1, t: 'strumenti', s: ['controlla ed esegue'], stile: 'esegue' },
      { id: 'limite', c: 2, r: 2, t: 'limite', s: ['chiude e si scusa'], stile: 'attenzione' }
    ],
    frecce: [
      { da: 'start', a: 'modello' },
      { da: 'modello', a: 'end', e: 'nessuna richiesta' },
      { da: 'modello', a: 'strumenti', via: 'vh', sd: -10, sa: 18, e: 'richieste, giri < 3' },
      { da: 'strumenti', a: 'modello', via: 'hv', sd: -18, sa: 26, e: 'ToolMessage' },
      { da: 'modello', a: 'limite', via: 'vh', sd: -46, e: 'richieste, giri ≥ 3' },
      { da: 'limite', a: 'end', via: 'hv' }
    ]
  };

  SCHEMI.grafo = {
    tipo: 'flusso',
    titolo: 'Il grafo di oggi: il router decide se la domanda è in ambito; poi il nodo modello decide tra fine, strumenti e limite',
    griglia: { col: [110, 190, 190, 200, 110], riga: 84, dx: 122, dy: 40 },
    nodi: [
      { id: 'rifiuto', c: 2, r: 0, t: 'rifiuto', s: ['testo fisso', 'di ambito.json'], stile: 'attenzione' },
      { id: 'start', c: 0, r: 1, t: 'START', forma: 'pillola', a: 50 },
      { id: 'router', c: 1, r: 1, t: 'router', s: ['decide l\'ambito', 'LLM senza strumenti'], stile: 'llm' },
      { id: 'modello', c: 2, r: 1, t: 'modello', s: ['chiama LM Studio'], stile: 'llm' },
      { id: 'end', c: 4, r: 1, t: 'END', forma: 'pillola', a: 50 },
      { id: 'strumenti', c: 3, r: 2, t: 'strumenti', s: ['controlla ed esegue'], stile: 'esegue' },
      { id: 'limite', c: 3, r: 3, t: 'limite', s: ['chiude e si scusa'], stile: 'attenzione' }
    ],
    frecce: [
      { da: 'start', a: 'router' },
      { da: 'router', a: 'modello', e: 'conversazione' },
      { da: 'router', a: 'rifiuto', via: 'vh', e: 'fuori_ambito' },
      { da: 'rifiuto', a: 'end', via: 'hv' },
      { da: 'modello', a: 'end', e: 'nessuna richiesta' },
      { da: 'modello', a: 'strumenti', via: 'vh', sd: -10, sa: 18, e: 'richieste, giri < 3' },
      { da: 'strumenti', a: 'modello', via: 'hv', sd: -18, sa: 26, e: 'ToolMessage' },
      { da: 'modello', a: 'limite', via: 'vh', sd: -46, e: 'richieste, giri ≥ 3' },
      { da: 'limite', a: 'end', via: 'hv' }
    ]
  };

  SCHEMI['tool-calling'] = {
    tipo: 'sequenza',
    titolo: 'Tool calling: il modello chiede uno strumento, il programma lo controlla e lo esegue, poi rimanda il risultato con lo stesso identificativo',
    colonna: 252,
    attori: [
      { id: 'tu', t: 'Tu' },
      { id: 'prog', t: 'Il programma', s: 'grafo LangGraph' },
      { id: 'mod', t: 'Il modello', s: 'LM Studio', stile: 'llm' },
      { id: 'str', t: 'Lo strumento', s: 'ora_corrente', stile: 'esegue' }
    ],
    passi: [
      { da: 'tu', a: 'prog', e: '«che ore sono a Tokyo?»' },
      { da: 'prog', a: 'mod', e: 'domanda + elenco degli strumenti' },
      { da: 'mod', a: 'prog', e: ['richiesta: ora_corrente,', 'fuso Asia/Tokyo, id c1'], ritorno: true, stile: 'evidenza' },
      { su: 'prog', nota: ['controlla nome', 'e argomenti'] },
      { da: 'prog', a: 'str', e: 'esegue la chiamata', stile: 'evidenza' },
      { da: 'str', a: 'prog', e: 'risultato in JSON', ritorno: true },
      { da: 'prog', a: 'mod', e: ['ToolMessage', 'con lo stesso id c1'] },
      { da: 'mod', a: 'prog', e: '«A Tokyo sono le 05:13.»', ritorno: true },
      { da: 'prog', a: 'tu', e: 'riga dello strumento + risposta', ritorno: true }
    ]
  };

  SCHEMI['viaggio-mcp'] = {
    tipo: 'sequenza',
    titolo: 'Il viaggio di «che ore sono a Tokyo?»: due giri del modello e, in mezzo, la chiamata al server MCP attraverso il ponte',
    colonna: 238,
    attori: [
      { id: 'term', t: 'Terminale' },
      { id: 'grafo', t: 'Grafo', s: 'modello · strumenti' },
      { id: 'lm', t: 'LM Studio', stile: 'llm', s: 'il modello' },
      { id: 'ponte', t: 'Ponte MCP', s: 'client_mcp.py' },
      { id: 'server', t: 'Server MCP', s: 'un altro processo', stile: 'esegue' }
    ],
    passi: [
      { da: 'term', a: 'grafo', e: '«che ore sono a Tokyo?»' },
      { da: 'grafo', a: 'lm', e: '1° giro: domanda + strumenti' },
      { da: 'lm', a: 'grafo', e: 'chiede ora_corrente', ritorno: true },
      { da: 'grafo', a: 'ponte', e: 'controlla gli argomenti, poi chiama (al massimo 10 s)' },
      { da: 'ponte', a: 'server', e: 'POST /mcp · tools/call' },
      { su: 'server', nota: 'logica/orologio.py', stile: 'esegue' },
      { da: 'server', a: 'ponte', e: 'risultato in JSON', ritorno: true },
      { da: 'ponte', a: 'grafo', e: 'risultato come testo JSON', ritorno: true },
      { su: 'grafo', nota: ['ToolMessage, stesso id', '+ riga nel log'] },
      { da: 'grafo', a: 'lm', e: '2° giro: con il risultato' },
      { da: 'lm', a: 'grafo', e: '«A Tokyo sono le 05:13.»', ritorno: true },
      { da: 'grafo', a: 'term', e: 'riga strumento + risposta', ritorno: true }
    ]
  };

  SCHEMI.varianti = {
    tipo: 'flusso',
    titolo: 'Tre modi di collegare uno strumento: via MCP, come funzione locale, via servizio FastAPI. Tutti arrivano alla stessa logica',
    griglia: { col: [190, 224, 214, 170], riga: 84, dx: 132, dy: 34 },
    nodi: [
      { id: 'nodo', c: 0, r: 1, t: 'Nodo strumenti', s: ['del grafo'] },
      { id: 'ponte', c: 1, r: 0, t: 'Ponte MCP', s: ['client_mcp.py', 'tutti e 10 gli strumenti'] },
      { id: 'locale', c: 1, r: 1, t: '@tool locale', s: ['calcolatrice_locale.py', 'solo calcola'] },
      { id: 'wrapper', c: 1, r: 2, t: 'Wrapper HTTP', s: ['wrapper_scadenze.py', 'solo calcola_scadenza'] },
      { id: 'server', c: 2, r: 0, t: 'Server MCP', s: ['un altro processo'], stile: 'esegue' },
      { id: 'api', c: 2, r: 2, t: 'Servizio FastAPI', s: ['un altro processo', 'GET /scadenza'], stile: 'esegue' },
      { id: 'logica', c: 3, r: 0, ar: 3, t: 'logica/', s: ['il calcolo,', 'scritto', 'una volta sola'], stile: 'esegue' }
    ],
    frecce: [
      { da: 'nodo', a: 'ponte', via: 'vh', e: 'origine=mcp' },
      { da: 'nodo', a: 'locale', e: 'origine=locale' },
      { da: 'nodo', a: 'wrapper', via: 'vh', e: 'origine=fastapi' },
      { da: 'ponte', a: 'server', e: 'MCP' },
      { da: 'wrapper', a: 'api', e: 'HTTP GET' },
      { da: 'server', a: 'logica' },
      { da: 'locale', a: 'logica', e: 'nessuna rete, nessun altro processo' },
      { da: 'api', a: 'logica' }
    ]
  };

  (function () {
    var nodi = [];
    var frecce = [];
    var i;
    [2, 4.5, 7].forEach(function (r, k) {
      nodi.push({ id: 'a' + k, c: 0, r: r, t: 'app ' + (k + 1) });
      nodi.push({ id: 'b' + k, c: 3, r: r, t: 'app ' + (k + 1) });
    });
    for (i = 0; i < 10; i++) {
      nodi.push({ id: 's' + i, c: 1, r: i, stile: 'esegue' });
      nodi.push({ id: 't' + i, c: 5, r: i, stile: 'esegue' });
    }
    nodi.push({ id: 'mcp', c: 4, r: 3, ar: 4, t: 'MCP', s: ['uno standard'], stile: 'esegue' });
    for (var k = 0; k < 3; k++) {
      for (i = 0; i < 10; i++) frecce.push({ da: 'a' + k, a: 's' + i, via: 'retta', punta: false, stile: 'sottile' });
      frecce.push({ da: 'b' + k, a: 'mcp', via: 'retta', punta: false });
    }
    for (i = 0; i < 10; i++) frecce.push({ da: 'mcp', a: 't' + i, via: 'retta', punta: false });
    SCHEMI['n-per-m'] = {
      tipo: 'flusso',
      titolo: 'Tre app e dieci servizi: senza standard servono 30 collegamenti, con MCP ne bastano 13',
      griglia: { col: [104, 110, 40, 104, 130, 110], riga: 27, dx: 92, dy: 9, alto: 30 },
      gruppi: [
        { c: 0, r: 0, lc: 2, ar: 10, t: 'Senza standard: 3 × 10 = 30 collegamenti' },
        { c: 3, r: 0, lc: 3, ar: 10, t: 'Con MCP: 3 + 10 = 13 collegamenti' }
      ],
      nodi: nodi,
      frecce: frecce
    };
  })();

  SCHEMI.processi = {
    tipo: 'flusso',
    titolo: 'Chi avvia chi: tu apri LM Studio e la chat da terminale, e accendi i quattro container con un solo comando; la chat da terminale e il servizio dell\'agente avviano e spengono da soli il server MCP, ciascuno il suo',
    griglia: { col: [84, 262, 224], riga: 70, dx: 128, dy: 14 },
    nodi: [
      { id: 'tu', c: 0, r: 0, ar: 6, t: 'Tu', forma: 'pillola' },
      { id: 'lm', c: 1, r: 0, t: 'LM Studio', s: ['lo apri a mano · :1234'], stile: 'llm esterno' },
      { id: 'cli', c: 1, r: 1, t: 'Chat da terminale', s: ['python -m assistente'] },
      { id: 'ag', c: 1, r: 2, t: 'Servizio dell\'agente', s: ['container agente', ':8767'] },
      { id: 'be', c: 1, r: 3, t: 'Back-end delle chat', s: ['container backend', 'nessuna porta'] },
      { id: 'db', c: 1, r: 4, t: 'Database', s: ['container database', ':5432'], stile: 'dati' },
      { id: 'fe', c: 1, r: 5, t: 'Chat nel browser', s: ['container frontend', ':8780'] },
      { id: 'api', c: 2, r: 0, t: 'Servizio FastAPI', s: ['solo variante fastapi', ':8766'], stile: 'esegue' },
      { id: 'mcp1', c: 2, r: 1, t: 'Server MCP', s: [':8765'], stile: 'esegue' },
      { id: 'mcp2', c: 2, r: 2, t: 'Server MCP', s: ['uno suo, nel container'], stile: 'esegue' }
    ],
    frecce: [
      { da: 'tu', a: 'lm' },
      { da: 'tu', a: 'cli' },
      { da: 'tu', a: 'ag' },
      { da: 'tu', a: 'be' },
      { da: 'tu', a: 'db' },
      { da: 'tu', a: 'fe' },
      { da: 'cli', a: 'mcp1', sd: 10, e: ['avvia e', 'spegne'] },
      { da: 'cli', a: 'api', via: 'hvh', sd: -16, sa: -4, stile: 'tratteggio' },
      { da: 'ag', a: 'mcp2', sd: 10, e: ['avvia e', 'spegne'] },
      { da: 'ag', a: 'api', via: 'hvh', sd: -16, sa: 18, mx: 36, stile: 'tratteggio' }
    ]
  };

  SCHEMI.avvio = {
    tipo: 'flusso',
    titolo: 'L\'ordine dell\'avvio: prima i controlli che costano poco, poi i processi figli, infine la chat',
    griglia: { col: 222, riga: 84, dx: 58, dy: 50 },
    nodi: [
      { id: 'n1', c: 0, r: 0, t: '1 · Console in UTF-8', s: ['pipe e file su Windows'] },
      { id: 'n2', c: 1, r: 0, t: '2 · Configurazione', s: ['.env: gli errori', 'tutti insieme'] },
      { id: 'n3', c: 2, r: 0, t: '3 · Log e ambito', s: ['logs/assistente.log', 'risorse/ambito.json'] },
      { id: 'n4', c: 3, r: 0, t: '4 · LM Studio', s: ['risponde? il modello', 'è nell\'elenco?'], stile: 'llm' },
      { id: 'n5', c: 3, r: 1, t: '5 · Fuso dell\'utente', s: ['tre posti, poi UTC'] },
      { id: 'n6', c: 2, r: 1, t: '6 · Processi figli', s: ['server MCP, FastAPI:', 'pronti entro 10 s'], stile: 'esegue' },
      { id: 'n7', c: 1, r: 1, t: '7 · Modello e grafo', s: ['crea_agente'] },
      { id: 'n8', c: 0, r: 1, t: '8 · Chat', s: ['un turno alla volta'] }
    ],
    frecce: [
      { da: 'n1', a: 'n2' }, { da: 'n2', a: 'n3' }, { da: 'n3', a: 'n4' }, { da: 'n4', a: 'n5' },
      { da: 'n5', a: 'n6' }, { da: 'n6', a: 'n7' }, { da: 'n7', a: 'n8' }
    ]
  };

  SCHEMI['turno-chat'] = {
    tipo: 'sequenza',
    titolo: 'Un turno della chat nel browser: gli eventi arrivano a pezzi, il salvataggio avviene una volta sola, dopo la risposta completa',
    colonna: 238,
    attori: [
      { id: 'br', t: 'Browser', s: 'la chat' },
      { id: 'ng', t: 'nginx', s: 'container frontend' },
      { id: 'be', t: 'Back-end', s: 'servizio_backend' },
      { id: 'ag', t: 'Agente', s: 'servizio_agente', stile: 'llm' },
      { id: 'pg', t: 'PostgreSQL', s: 'container database', stile: 'dati' }
    ],
    passi: [
      { da: 'br', a: 'ng', e: 'POST /api/chat/{id}/messaggi' },
      { da: 'ng', a: 'be', e: '/chat/{id}/messaggi' },
      { da: 'be', a: 'pg', e: 'legge la cronologia e le istruzioni del progetto' },
      { da: 'be', a: 'ag', e: 'POST /chat/stream' },
      { da: 'ag', a: 'be', e: 'eventi strumento e testo', ritorno: true },
      { da: 'be', a: 'br', e: 'gli stessi eventi, subito: la risposta compare a pezzi', ritorno: true },
      { da: 'ag', a: 'be', e: 'fine: risposta completa', ritorno: true },
      { da: 'be', a: 'pg', e: 'salva il turno in una sola transazione', stile: 'evidenza' },
      { da: 'be', a: 'br', e: 'fine: risposta definitiva, titolo della chat', ritorno: true }
    ]
  };

  SCHEMI.tabelle = {
    tipo: 'flusso',
    titolo: 'Le tre tabelle di PostgreSQL: una chat può stare in un progetto, un messaggio sta sempre in una chat',
    griglia: { col: 306, riga: 204, dx: 112, dy: 0 },
    nodi: [
      { id: 'progetti', c: 0, r: 0, forma: 'tabella', stile: 'dati', t: 'progetti', righe: [['id', 'chiave'], ['nome', 'non vuoto'], ['istruzioni', 'anche vuote'], ['creato', 'data e ora'], ['aggiornato', 'data e ora']] },
      { id: 'chat', c: 1, r: 0, forma: 'tabella', stile: 'dati', t: 'chat', righe: [['id', 'chiave'], ['progetto_id', 'può mancare'], ['titolo', 'può mancare'], ['cronologia', 'jsonb, per l\'agente'], ['creata', 'data e ora'], ['aggiornata', 'data e ora']] },
      { id: 'messaggi', c: 2, r: 0, forma: 'tabella', stile: 'dati', t: 'messaggi', righe: [['id', 'chiave'], ['chat_id', 'obbligatorio'], ['ruolo', 'utente | assistente'], ['testo', 'da mostrare e cercare'], ['strumenti', 'jsonb'], ['creato', 'data e ora']] }
    ],
    frecce: [
      { da: 'chat', a: 'progetti', e: 'progetto_id' },
      { da: 'messaggi', a: 'chat', e: 'chat_id' }
    ]
  };

  SCHEMI.log = {
    tipo: 'flusso',
    titolo: 'Ogni processo scrive il suo file di log: per seguire una chiamata si incrociano i file',
    griglia: { col: 228, riga: 84, dx: 72, dy: 46, alto: 34 },
    nodi: [
      { id: 'be', c: 0, r: 0, t: 'Back-end', s: ['servizio_backend'] },
      { id: 'ag', c: 1, r: 0, t: 'Assistente', s: ['o servizio dell\'agente'] },
      { id: 'mcp', c: 2, r: 0, t: 'Server MCP', s: ['10 strumenti'], stile: 'esegue' },
      { id: 'api', c: 3, r: 0, t: 'Servizio FastAPI', s: ['solo variante fastapi'], stile: 'esegue' },
      { id: 'lbe', c: 0, r: 1, t: 'servizio_backend.log', s: ['richieste e turni,', 'mai il testo'], forma: 'cilindro', stile: 'dati' },
      { id: 'lag', c: 1, r: 1, t: 'assistente.log', s: ['router, nodi, chiamate', 'con origine ed esito'], forma: 'cilindro', stile: 'dati' },
      { id: 'lmcp', c: 2, r: 1, t: 'server_mcp.log', s: ['chiamate ricevute,', 'modifiche alle note'], forma: 'cilindro', stile: 'dati' },
      { id: 'lapi', c: 3, r: 1, t: 'servizio_api.log', s: ['richieste a /scadenza'], forma: 'cilindro', stile: 'dati' }
    ],
    frecce: [
      { da: 'be', a: 'ag', e: 'HTTP' },
      { da: 'ag', a: 'mcp', e: 'MCP' },
      { da: 'ag', a: 'api', via: 'vhv', esce: 'su', entra: 'su', giro: 26, stile: 'tratteggio', e: 'HTTP' },
      { da: 'be', a: 'lbe' }, { da: 'ag', a: 'lag' }, { da: 'mcp', a: 'lmcp' }, { da: 'api', a: 'lapi' }
    ]
  };

  SCHEMI.diagnosi = {
    tipo: 'flusso',
    titolo: 'La diagnosi per livelli: si parte dal basso, dalla configurazione, e il modello si sospetta per ultimo',
    griglia: { col: [156, 700], riga: 54, dx: 54, dy: 8 },
    nodi: [
      { id: 'l7', c: 1, r: 0, t: '7 · Il modello', s: ['risponde senza chiamare lo strumento'], stile: 'llm' },
      { id: 'l6', c: 1, r: 1, t: '6 · Archivio delle note', s: ['«Archivio delle note non accessibile»'], stile: 'dati' },
      { id: 'l5', c: 1, r: 2, t: '5 · Rete, solo per il meteo', s: ['«Servizio meteo non disponibile»'], stile: 'esterno' },
      { id: 'l4', c: 1, r: 3, t: '4 · Servizio FastAPI, solo con fastapi', s: ['«Servizio scadenze non raggiungibile»'], stile: 'esegue' },
      { id: 'l3', c: 1, r: 4, t: '3 · Server MCP', s: ['«Porta … già in uso» · «Il server MCP non è partito»'], stile: 'esegue' },
      { id: 'l2', c: 1, r: 5, t: '2 · LM Studio', s: ['«Impossibile raggiungere LM Studio all\'indirizzo …»'], stile: 'llm esterno' },
      { id: 'l1', c: 1, r: 6, t: '1 · Configurazione', s: ['«Variabili d\'ambiente mancanti: …»'] },
      { id: 'fine', c: 0, r: 0, t: 'per ultimo', forma: 'pillola', a: 44 },
      { id: 'inizio', c: 0, r: 6, t: 'parti da qui', forma: 'pillola', a: 44, stile: 'evidenza' }
    ],
    frecce: [
      { da: 'inizio', a: 'fine', e: ['dal basso', 'verso l\'alto'] }
    ]
  };

  SCHEMI.test = {
    tipo: 'flusso',
    titolo: 'Quattro tipi di verifica: i test automatici girano sempre, le prove reali solo se le chiedi',
    griglia: { col: 264, riga: 150, dx: 38, dy: 0, alto: 30 },
    gruppi: [
      { c: 0, r: 0, t: 'girano sempre' },
      { c: 1, r: 0, lc: 3, t: 'solo se le chiedi: altrimenti risultano skipped' }
    ],
    nodi: [
      { id: 'auto', c: 0, r: 0, t: 'Test automatici', s: ['python -m pytest', '', 'modello finto, niente rete:', 'il codice fa la cosa giusta,', 'dato un copione del modello?'] },
      { id: 'lm', c: 1, r: 0, t: 'Prove con LM Studio', s: ['--lmstudio -m lmstudio', '', 'il modello vero', 'chiama davvero', 'lo strumento?'], stile: 'llm' },
      { id: 'docker', c: 2, r: 0, t: 'Prove con Docker', s: ['--docker -m docker', '', 'container, fuso, volumi:', 'funziona anche lì?'] },
      { id: 'browser', c: 3, r: 0, t: 'Prove nel browser', s: ['Playwright con Chromium', '', 'la chat regge', 'in un browser vero?'] }
    ],
    frecce: []
  };

  SCHEMI.dati = {
    tipo: 'flusso',
    titolo: 'Dove vive ogni dato e quanto dura: memoria, SQLite, PostgreSQL, file',
    griglia: { col: [310, 320], riga: 66, dx: 262, dy: 16 },
    nodi: [
      { id: 'd0', c: 0, r: 0, t: 'Cronologia del terminale', s: ['la tiene il programma, in una lista'] },
      { id: 'd1', c: 0, r: 1, t: 'Note', s: ['add_note, list_notes, delete_note'] },
      { id: 'd2', c: 0, r: 2, t: 'Progetti, chat e messaggi', s: ['li salva il back-end'] },
      { id: 'd3', c: 0, r: 3, t: 'Log', s: ['una riga per ogni chiamata'] },
      { id: 'd4', c: 0, r: 4, t: 'Catalogo, festività, ambito', s: ['letti all\'avvio o al primo uso'] },
      { id: 'p0', c: 1, r: 0, t: 'Memoria del processo', s: ['niente su disco'], stile: 'esterno' },
      { id: 'p1', c: 1, r: 1, t: 'archivio/note.sqlite3', s: ['SQLite, fuori da Git'], forma: 'cilindro', stile: 'dati' },
      { id: 'p2', c: 1, r: 2, t: 'PostgreSQL', s: ['volume Docker dati_postgres'], forma: 'cilindro', stile: 'dati' },
      { id: 'p3', c: 1, r: 3, t: 'logs/', s: ['quattro file, fuori da Git'], forma: 'cilindro', stile: 'dati' },
      { id: 'p4', c: 1, r: 4, t: 'risorse/', s: ['tre file JSON, in Git'], forma: 'cilindro', stile: 'dati' }
    ],
    frecce: [
      { da: 'd0', a: 'p0', e: 'si perde all\'uscita' },
      { da: 'd1', a: 'p1', e: 'restano tra le sessioni' },
      { da: 'd2', a: 'p2', e: 'restano dopo il riavvio' },
      { da: 'd3', a: 'p3', e: 'si accumulano' },
      { da: 'p4', a: 'd4', e: 'sola lettura' }
    ]
  };

  SCHEMI.lezioni = {
    tipo: 'flusso',
    titolo: 'La storia del progetto dal 2 al 12 novembre: lezione 4, lezione 5 e i quattro step fatti della lezione 6',
    griglia: { col: [128, 222, 222, 222, 222], riga: 78, dx: 44, dy: 26 },
    nodi: [
      { id: 'z4', c: 0, r: 0, t: 'Lezione 4', forma: 'pillola', a: 48, stile: 'evidenza' },
      { id: 'z5', c: 0, r: 1, t: 'Lezione 5', forma: 'pillola', a: 48, stile: 'evidenza' },
      { id: 'z6', c: 0, r: 2, t: 'Lezione 6', forma: 'pillola', a: 48, stile: 'evidenza' },
      { id: 'a1', c: 1, r: 0, t: '2 nov', s: ['assistente di base:', 'grafo, orologio, Docker'] },
      { id: 'b1', c: 1, r: 1, t: '3 nov', s: ['convertitore via MCP'] },
      { id: 'b2', c: 2, r: 1, t: '8 nov', s: ['sette passi,', 'dieci strumenti'] },
      { id: 'b3', c: 3, r: 1, t: '8–9 nov', s: ['revisione finale:', 'nove correzioni'] },
      { id: 'b4', c: 4, r: 1, t: '9 nov', s: ['unione in main'] },
      { id: 'c1', c: 1, r: 2, t: '9 nov · step 1', s: ['router e streaming'] },
      { id: 'c2', c: 2, r: 2, t: '10 nov · step 6', s: ['agente come servizio,', 'anche in Docker'] },
      { id: 'c3', c: 3, r: 2, t: '11 nov · step 7', s: ['back-end con', 'PostgreSQL'] },
      { id: 'c4', c: 4, r: 2, t: '12 nov · step 8', s: ['chat nel browser,', 'installabile come app'] }
    ],
    frecce: [
      { da: 'z4', a: 'a1' },
      { da: 'z5', a: 'b1' }, { da: 'b1', a: 'b2' }, { da: 'b2', a: 'b3' }, { da: 'b3', a: 'b4' },
      { da: 'z6', a: 'c1' }, { da: 'c1', a: 'c2' }, { da: 'c2', a: 'c3' }, { da: 'c3', a: 'c4' }
    ]
  };

  SCHEMI['markdown-sicuro'] = {
    tipo: 'flusso',
    titolo: 'Il testo del modello non è fidato: prima di entrare nella pagina passa da marked e da DOMPurify, e nginx aggiunge la CSP',
    griglia: { col: 214, riga: 84, dx: 116, dy: 40 },
    nodi: [
      { id: 'testo', c: 0, r: 0, t: 'Testo del modello', s: ['non fidato'], stile: 'attenzione' },
      { id: 'marked', c: 1, r: 0, t: 'marked', s: ['da Markdown a HTML'] },
      { id: 'purify', c: 2, r: 0, t: 'DOMPurify', s: ['solo i tag ammessi'], stile: 'evidenza' },
      { id: 'pagina', c: 3, r: 0, t: 'Pagina', s: ['l\'unico {@html}', 'del progetto'] },
      { id: 'csp', c: 3, r: 1, t: 'CSP di nginx', s: ['niente richieste', 'ad altri siti'], stile: 'evidenza' }
    ],
    frecce: [
      { da: 'testo', a: 'marked', e: 'Markdown' },
      { da: 'marked', a: 'purify', e: 'HTML grezzo' },
      { da: 'purify', a: 'pagina', e: 'HTML pulito' },
      { da: 'csp', a: 'pagina' }
    ]
  };

  /* ───────────── Disegno nella pagina ───────────── */

  function disegna(nome) {
    var d = SCHEMI[nome];
    if (!d) throw new Error('Schema «' + nome + '» non trovato in schemi.js');
    return d.tipo === 'sequenza' ? disegnaSequenza(d) : disegnaFlusso(d);
  }

  function disegnaSchemi(radice) {
    var figure = (radice || document).querySelectorAll('figure[data-schema]');
    Array.prototype.forEach.call(figure, function (figura) {
      if (figura.querySelector('svg')) return;
      try {
        figura.insertAdjacentHTML('afterbegin', disegna(figura.dataset.schema));
      } catch (errore) {
        figura.insertAdjacentHTML('afterbegin', '<p><strong>' + esc(errore.message) + '</strong></p>');
        if (window.console) window.console.error(errore.message);
      }
    });
  }

  window.SCHEMI = SCHEMI;
  window.disegnaSchemi = disegnaSchemi;

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { disegnaSchemi(document); });
  else disegnaSchemi(document);
})();
