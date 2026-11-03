import os
import json
import redis
import psycopg2
from dotenv import load_dotenv
load_dotenv()
def get_redis_client():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=6379,
        db=0,
        decode_responses=True
    )
def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=5432,
        user=os.getenv("POSTGRES_USER", "p1"),
        password=os.getenv("POSTGRES_PASSWORD", "cambiame"),
        dbname=os.getenv("POSTGRES_DB", "albergues")
    )
def inicializa_contadores_redis():
    """Calcula as prazas dispoñibles desde PostgreSQL e garda os contadores en Redis."""
    r = get_redis_client()
    conn = get_pg_connection()
    print("Inicializando contadores en Redis a partir de PostgreSQL...")
    with conn.cursor() as cur:
        cur.execute("""
            SELECT a.id, a.prazas, r.data_reserva, COUNT(r.id) as ocupadas
            FROM albergues a
            LEFT JOIN reservas r ON a.id = r.albergue_id
            GROUP BY a.id, a.prazas, r.data_reserva
        """)
        filas = cur.fetchall()
        pipe = r.pipeline()
        for albergue_id, prazas_totais, data_reserva, ocupadas in filas:
            if data_reserva is not None:
                libres = max(0, prazas_totais - ocupadas)
                clave = f"albergue:{albergue_id}:noite:{data_reserva}:prazas"
                pipe.set(clave, libres)
        pipe.execute()
    conn.close()
    print("Contadores de Redis inicializados correctamente.")
def reservar(albergue_id, noite, peregrino_id):
    """Realiza unha reserva de forma atómica evitando sobreventa.
    Se a clave non existe en Redis, inicialízaa ao total de prazas do albergue de forma segura.
    """
    r = get_redis_client()
    clave = f"albergue:{albergue_id}:noite:{noite}:prazas"
    # Comprobación defensiva se non existe a clave
    if not r.exists(clave):
        conn_temp = get_pg_connection()
        with conn_temp.cursor() as cur:
            cur.execute("SELECT prazas FROM albergues WHERE id = %s", (albergue_id,))
            row = cur.fetchone()
        conn_temp.close()
        if not row:
            return False, "O albergue non existe."
        prazas_totais = row[0]
        r.setnx(clave, prazas_totais)
    # 1. Operación atómica de desconto en memoria
    libres = r.decr(clave)
    if libres < 0:
        r.incr(clave)
        return False, "Sen prazas dispoñibles."
    # 2. Rexistro persistente en PostgreSQL
    conn = None
    try:
        conn = get_pg_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO reservas (albergue_id, peregrino_id, data_reserva)
                VALUES (%s, %s, %s)
            """, (albergue_id, peregrino_id, noite))
        conn.commit()
        return True, "Reserva confirmada con éxito."
    except Exception as e:
        if conn:
            conn.rollback()
        r.incr(clave)
        return False, f"Fallo na reserva (PostgreSQL): {e}"
    finally:
        if conn:
            conn.close()
def consultar_albergues_libres_cache(camino, noite, ttl=60):
    """Consulta albergues con prazas libres nun camiño usando Redis como caché (TTL en segundos)."""
    r = get_redis_client()
    clave_cache = f"cache:camino:{camino}:noite:{noite}"
    cached = r.get(clave_cache)
    if cached:
        return json.loads(cached), True
    conn = get_pg_connection()
    resultado = []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT a.id, a.nome, a.concello, a.prazas, a.prezo
            FROM albergues a
            WHERE a.camino = %s
        """, (camino,))
        albergues = cur.fetchall()
        for a_id, nome, concello, prazas, prezo in albergues:
            clave_prazas = f"albergue:{a_id}:noite:{noite}:prazas"
            prazas_libres_str = r.get(clave_prazas)
            libres = int(prazas_libres_str) if prazas_libres_str is not None else prazas
            if libres > 0:
                resultado.append({
                    "id": a_id,
                    "nome": nome,
                    "concello": concello,
                    "prazas_libres": libres,
                    "prezo": float(prezo)
                })
    conn.close()
    r.setex(clave_cache, ttl, json.dumps(resultado))
    return resultado, False
