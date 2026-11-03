import concurrent.futures
from datetime import date
from src.redis_service import (
    inicializa_contadores_redis,
    reservar,
    consultar_albergues_libres_cache,
    get_redis_client,
    get_pg_connection
)

def test_sobreventa():
    print("\n" + "="*60)
    print("INICIANDO PROBA DE PREVENCIÓN DE SOBREVENTA (CONCORRENCIA)")
    print("="*60)

    r = get_redis_client()
    albergue_id = 1
    noite_proba = date(2027, 6, 1)
    clave = f"albergue:{albergue_id}:noite:{noite_proba}:prazas"

    prazas_iniciais = 3
    r.set(clave, prazas_iniciais)

    conn = get_pg_connection()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM reservas WHERE albergue_id = %s AND data_reserva = %s", (albergue_id, noite_proba))
        conn.commit()
        cur.execute("SELECT id FROM peregrinos LIMIT 30;")
        peregrinos = [row[0] for row in cur.fetchall()]
    conn.close()

    print(f"Prazas dispoñibles: {prazas_iniciais}")
    print(f"Lanzando {len(peregrinos)} solicitudes de reserva simultáneas (threads)...")

    exitos = 0
    rexeitadas = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futuros = [
            executor.submit(reservar, albergue_id, noite_proba, p_id)
            for p_id in peregrinos
        ]
        for f in concurrent.futures.as_completed(futuros):
            ok, msg = f.result()
            if ok:
                exitos += 1
            else:
                rexeitadas += 1

    prazas_finais = int(r.get(clave))

    conn = get_pg_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM reservas WHERE albergue_id = %s AND data_reserva = %s", (albergue_id, noite_proba))
        reservas_en_pg = cur.fetchone()[0]
    conn.close()

    print(f"\n--- RESULTADOS DA PROBA ---")
    print(f"Reservas aceptadas: {exitos} (Esperado: {prazas_iniciais})")
    print(f"Reservas rexeitadas: {rexeitadas} (Esperado: {len(peregrinos) - prazas_iniciais})")
    print(f"Prazas restantes en Redis: {prazas_finais} (Esperado: 0)")
    print(f"Reservas rexistradas en PostgreSQL: {reservas_en_pg} (Esperado: {prazas_iniciais})")

    if exitos == prazas_iniciais and prazas_finais == 0 and reservas_en_pg == prazas_iniciais:
        print(">> DEMOSTRACIÓN EXITOSA: NON HOUBO SOBREVENTA <<\n")
    else:
        print(">> ERRO NA CONCORRENCIA <<\n")

def test_cache():
    print("\n" + "="*60)
    print("INICIANDO PROBA DE CACHÉ CON TTL")
    print("="*60)
    camino = "Francés"
    noite = date(2027, 5, 1)

    datos, desde_cache = consultar_albergues_libres_cache(camino, noite, ttl=10)
    print(f"1ª Consulta -> Obtido de caché: {desde_cache} (Debe ser False). Albergues atopados: {len(datos)}")

    datos2, desde_cache2 = consultar_albergues_libres_cache(camino, noite, ttl=10)
    print(f"2ª Consulta -> Obtido de caché: {desde_cache2} (Debe ser True). Albergues atopados: {len(datos2)}")

def main():
    inicializa_contadores_redis()
    test_sobreventa()
    test_cache()

if __name__ == "__main__":
    main()
