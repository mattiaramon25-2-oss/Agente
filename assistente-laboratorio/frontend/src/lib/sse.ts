// Lettore incrementale del flusso SSE: riceve i byte a pezzi e restituisce gli eventi completi.
// Se il campo data non è JSON valido, aggiungi() lancia un'eccezione: chi chiama
// la tratta come flusso interrotto.

export type EventoSse = { evento: string; dati: unknown };

export class LettoreSse {
  private decodificatore = new TextDecoder('utf-8');
  private resto = '';

  aggiungi(pezzo: Uint8Array): EventoSse[] {
    this.resto += this.decodificatore.decode(pezzo, { stream: true });
    // Il separatore tra eventi è la riga vuota; \r\n si normalizza in \n.
    this.resto = this.resto.replace(/\r\n/g, '\n');
    const eventi: EventoSse[] = [];
    let indice = this.resto.indexOf('\n\n');
    while (indice !== -1) {
      const blocco = this.resto.slice(0, indice);
      this.resto = this.resto.slice(indice + 2);
      const evento = this.leggiBlocco(blocco);
      if (evento) eventi.push(evento);
      indice = this.resto.indexOf('\n\n');
    }
    return eventi;
  }

  fine(): void {
    // Svuota il decodificatore; un evento rimasto a metà non è completo e si scarta.
    this.decodificatore.decode();
    this.resto = '';
  }

  private leggiBlocco(blocco: string): EventoSse | null {
    let nome = 'message';
    const dati: string[] = [];
    for (const riga of blocco.split('\n')) {
      if (riga === '' || riga.startsWith(':')) continue;
      const due = riga.indexOf(':');
      const campo = due === -1 ? riga : riga.slice(0, due);
      let valore = due === -1 ? '' : riga.slice(due + 1);
      if (valore.startsWith(' ')) valore = valore.slice(1);
      if (campo === 'event') nome = valore;
      else if (campo === 'data') dati.push(valore);
    }
    if (dati.length === 0) return null;
    return { evento: nome, dati: JSON.parse(dati.join('\n')) };
  }
}
