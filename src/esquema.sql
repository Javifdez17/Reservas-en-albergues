CREATE TABLE IF NOT EXISTS albergues (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    camino VARCHAR(50) NOT NULL,
    concello VARCHAR(100) NOT NULL,
    prazas INT NOT NULL CHECK (prazas > 0),
    prezo NUMERIC(5, 2) NOT NULL CHECK (prezo >= 0)
);

CREATE TABLE IF NOT EXISTS peregrinos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    apelidos VARCHAR(150) NOT NULL,
    documento VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(150) NOT NULL UNIQUE,
    pais VARCHAR(50) NOT NULL,
    data_nacemento DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS reservas (
    id SERIAL PRIMARY KEY,
    albergue_id INT NOT NULL REFERENCES albergues(id) ON DELETE RESTRICT,
    peregrino_id INT NOT NULL REFERENCES peregrinos(id) ON DELETE RESTRICT,
    data_reserva DATE NOT NULL,
    data_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_peregrino_noite UNIQUE (peregrino_id, data_reserva)
);

CREATE INDEX IF NOT EXISTS idx_reservas_albergue_data ON reservas(albergue_id, data_reserva);

