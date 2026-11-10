-- Schema delle chat. Si esegue a ogni avvio del back-end: tutto con IF NOT EXISTS, nessuna migrazione.

CREATE TABLE IF NOT EXISTS progetti (
    id         integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome       text NOT NULL CHECK (nome <> ''),
    istruzioni text NOT NULL DEFAULT '',
    creato     timestamptz NOT NULL DEFAULT now(),
    aggiornato timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    progetto_id integer REFERENCES progetti (id) ON DELETE CASCADE,
    titolo      text,
    cronologia  jsonb NOT NULL DEFAULT '[]'::jsonb,
    creata      timestamptz NOT NULL DEFAULT now(),
    aggiornata  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messaggi (
    id        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chat_id   integer NOT NULL REFERENCES chat (id) ON DELETE CASCADE,
    ruolo     text NOT NULL CHECK (ruolo IN ('utente', 'assistente')),
    testo     text NOT NULL,
    strumenti jsonb,
    creato    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS chat_progetto_id ON chat (progetto_id);
CREATE INDEX IF NOT EXISTS messaggi_chat_id_id ON messaggi (chat_id, id);
