from pymongo import MongoClient
"""Xerador de datos de proba para a rede de albergues Camiño Aberto (ficticia).

ESQUELETO DO P1. Xa funciona: xera albergues e mostra un resumo. O resto
das funcións están marcadas con TODO e, mentres non as completes, avisan
e devolven unha lista baleira para que o script se poida executar desde o
primeiro día.

Exemplos (desde a raíz do proxecto):
  python -m src.xera_datos --sen-carga                    # só xerar e mostrar
  python -m src.xera_datos --albergues 60 --semente 7 --sen-carga
  python -m src.xera_datos                                 # xerar e cargar (cando estea feito)
"""
import argparse
import random
from datetime import date, timedelta
import random
import os
from dotenv import load_dotenv
load_dotenv()



from faker import Faker

# ------------------------------------------------------------------ catálogos
# Concellos galegos de cada camiño, en orde de etapas. Podes engadir máis.
CAMIÑOS = {
    "Francés":   ["Pedrafita do Cebreiro", "Triacastela", "Samos", "Sarria", "Portomarín",
                  "Palas de Rei", "Melide", "Arzúa", "O Pino"],
    "Portugués": ["Tui", "O Porriño", "Redondela", "Pontevedra", "Caldas de Reis", "Padrón", "Teo"],
    "Norte":     ["Ribadeo", "Lourenzá", "Mondoñedo", "Abadín", "Vilalba", "Guitiriz", "Sobrado"],
    "Primitivo": ["A Fonsagrada", "Castroverde", "Lugo", "Friol", "Melide"],
    "Inglés":    ["Ferrol", "Neda", "Pontedeume", "Betanzos", "Abegondo", "Ordes"],
}
NOMES_ALBERGUE = ["Vieiras", "Pedra Miúda", "O Cruceiro", "A Ponte Vella", "Bordón", "A Cabaciña",
                  "Fonte Vella", "Os Carballos", "A Estrela", "Camiño Real", "Casa do Peregrino",
                  "A Xesta", "O Muíño", "Santa Mariña", "O Hórreo", "A Lareira", "Sete Fontes"]


def pendente(nome):
    print(f"  [pendente] {nome}() aínda non está feita")
    return []


# ------------------------------------------------------------------ xeración
def xera_albergues(n, rng):
    """EXEMPLO RESOLTO: úsao como modelo para o resto de funcións.

    Devolve unha lista de dicionarios, un por albergue. Todo o azar sae de `rng`
    (un random.Random), non do módulo `random` directamente: así a semente controla
    o resultado.
    """
    albergues = []
    for i in range(1, n + 1):
        camino = rng.choice(list(CAMIÑOS))
        concello = rng.choice(CAMIÑOS[camino])
        albergues.append({
            "id": i,
            "nome": f"Albergue {rng.choice(NOMES_ALBERGUE)} ({concello})",
            "camino": camino,
            "concello": concello,
            "prazas": rng.randint(8, 60),
            "prezo": float(rng.randint(10, 22)),
        })
    return albergues


def xera_peregrinos(n, rng, fake):
    """Devolve `n` peregrinos reproducibles con documento e email únicos."""
    peregrinos = []
    paises = ["España", "Portugal", "Francia", "Alemaña", "Italia", "Reino Unido", "Estados Unidos"]
    letras_nif = "TRWAGMYFPDXBNJZSQVHLCKE"

    for i in range(1, n + 1):
        dias_vida = rng.randint(18 * 365, 75 * 365)
        nacemento = date(2027, 1, 1) - timedelta(days=dias_vida)

        num_doc = 10000000 + i
        letra = letras_nif[num_doc % 23]
        documento = f"{num_doc}{letra}"

        email = f"peregrino_{i}_{fake.user_name()}@caminoaberto.gal"

        peregrinos.append({
            "id": i,
            "nome": fake.first_name(),
            "apelidos": f"{fake.last_name()} {fake.last_name()}",
            "documento": documento,
            "email": email,
            "pais": rng.choice(paises),
            "data_nacemento": nacemento,
        })
    return peregrinos



def xera_reservas(n, albergues, peregrinos, desde, dias, rng):
    """Devolve ata `n` reservas cumprindo:
    - Non superar as prazas do albergue esa noite.
    - Un peregrino non pode ter dúas reservas na mesma noite.
    """
    reservas = []
    prazas_map = {a["id"]: a["prazas"] for a in albergues}
    albergue_ids = [a["id"] for a in albergues]
    peregrino_ids = [p["id"] for p in peregrinos]

    ocupacion = {}           
    peregrino_noite = set()   

    intentos = 0
    max_intentos = n * 50
    reserva_id = 1

    while len(reservas) < n and intentos < max_intentos:
        intentos += 1
        a_id = rng.choice(albergue_ids)
        p_id = rng.choice(peregrino_ids)
        dia_offset = rng.randint(0, dias - 1)
        data_reserva = desde + timedelta(days=dia_offset)

        if (p_id, data_reserva) in peregrino_noite:
            continue

        ocup_actual = ocupacion.get((a_id, data_reserva), 0)
        if ocup_actual >= prazas_map[a_id]:
            continue

        ocupacion[(a_id, data_reserva)] = ocup_actual + 1
        peregrino_noite.add((p_id, data_reserva))

        reservas.append({
            "id": reserva_id,
            "albergue_id": a_id,
            "peregrino_id": p_id,
            "data_reserva": data_reserva,
        })
        reserva_id += 1

    return reservas


def xera_fichas(albergues, rng, fake):
    """Devolve unha ficha por albergue con estrutura variable para MongoDB."""
    fichas = []
    servizos_comuns = ["cociña", "lavadora", "wifi", "almorzo", "calefacción", "taquillas"]

    for a in albergues:
        es_privado = (a["id"] % 2 == 0)

        if not es_privado:
            ficha = {
                "albergue_id": a["id"],
                "nome": a["nome"],
                "camino": a["camino"],
                "concello": a["concello"],
                "servizos": rng.sample(servizos_comuns, rng.randint(2, 3)),
                "horario": {
                    "apertura": f"{rng.randint(12, 14)}:00",
                    "peche": "22:00"
                },
                "titularidade": "Xunta de Galicia"
            }
        else:
            ficha = {
                "albergue_id": a["id"],
                "nome": a["nome"],
                "camino": a["camino"],
                "concello": a["concello"],
                "servizos": rng.sample(servizos_comuns, rng.randint(4, 6)),
                "horario": {
                    "apertura": f"{rng.randint(10, 12)}:00",
                    "peche": f"{rng.randint(22, 23)}:30"
                },
                "titularidade": "Privada",
                "contacto": {
                    "telefono": f"+34 98{rng.randint(1,8)} {rng.randint(100,999)} {rng.randint(100,999)}",
                    "web": f"https://albergue{a['id']}.gal"
                },
                "admite_cans": rng.choice([True, False]),
                "idiomas": ["galego", "castelán", rng.choice(["inglés", "francés", "alemán"])],
                "opinions": [
                    {"autor": fake.first_name(), "nota": rng.randint(3, 5), "texto": "Moi limpo e acolledor."},
                    {"autor": fake.first_name(), "nota": rng.randint(4, 5), "texto": "Trato excelente no camiño."}
                ]
            }
            if rng.choice([True, False]):
                ficha["bicicletas"] = {"garaxe": True, "prazas": rng.randint(4, 15)}

        fichas.append(ficha)
    return fichas


# ------------------------------------------------------------------ carga
def carga_postgres(albergues, peregrinos, reservas):
    """TODO: crea as táboas (ou usa un script SQL de inicio) e insire os datos."""
    pendente("carga_postgres")


def carga_mongo(fichas):
    """Insire as fichas na colección de MongoDB."""
    mongo_user = os.getenv("MONGO_USER", "p1")
    mongo_pass = os.getenv("MONGO_PASSWORD", "cambiame")
    mongo_host = os.getenv("MONGO_HOST", "localhost")
    mongo_db = os.getenv("MONGO_DB", "albergues")

    client = MongoClient(
        host=mongo_host,
        port=27017,
        username=mongo_user,
        password=mongo_pass,
        authSource="admin"
    )
    db = client[mongo_db]
    db.fichas.drop()  
    if fichas:
        db.fichas.insert_many(fichas)
    client.close()
    print(f"  [MongoDB] Cargadas {len(fichas)} fichas na colección 'fichas'.")


# ------------------------------------------------------------------ main
def mostra(titulo, filas, cantas=2):
    print(f"\n{titulo}: {len(filas)}")
    for f in filas[:cantas]:
        print(f"  {f}")


def main():
    ap = argparse.ArgumentParser(description="Xera e carga datos de proba de Camiño Aberto")
    ap.add_argument("--albergues", type=int, default=40)
    ap.add_argument("--peregrinos", type=int, default=1500)
    ap.add_argument("--reservas", type=int, default=5000)
    ap.add_argument("--semente", type=int, default=42, help="mesma semente → mesmos datos")
    ap.add_argument("--desde", type=date.fromisoformat, default=date(2027, 5, 1),
                    help="primeira noite da tempada (AAAA-MM-DD)")
    ap.add_argument("--dias", type=int, default=30, help="número de noites da tempada")
    ap.add_argument("--sen-carga", action="store_true", help="xera e mostra, pero non carga nada")
    args = ap.parse_args()

    rng = random.Random(args.semente)
    fake = Faker("es_ES")
    Faker.seed(args.semente)
    # TODO: Faker tamén ten a súa propia semente. Sen ela, os nomes cambian en cada execución.

    print(f"Semente {args.semente} · tempada {args.desde} + {args.dias} noites")
    albergues = xera_albergues(args.albergues, rng)
    peregrinos = xera_peregrinos(args.peregrinos, rng, fake)
    reservas = xera_reservas(args.reservas, albergues, peregrinos, args.desde, args.dias, rng)
    fichas = xera_fichas(albergues, rng, fake)

    mostra("Albergues", albergues)
    mostra("Peregrinos", peregrinos)
    mostra("Reservas", reservas)
    mostra("Fichas", fichas, 1)

    if not args.sen_carga:
        carga_postgres(albergues, peregrinos, reservas)
        carga_mongo(fichas)


if __name__ == "__main__":
    main()
