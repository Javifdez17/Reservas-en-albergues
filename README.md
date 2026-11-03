# P1 · Reservas de albergues do Camiño

Práctica de Big Data Aplicado (UD1).  
**Autores:** Javier Sánchez  y Marco Vázquez.

---

## 1. Arquitectura del sistema *(Marco Vázquez)*

Montamos la infraestructura con Docker Compose (`compose.yaml`) usando tres bases de datos:

| Sistema | Versión | Qué guarda | Por qué |
|---|---|---|---|
| **PostgreSQL** | `17` | Albergues, peregrinos y reservas | Relaciones, claves foráneas y evitar duplicados con transacciones ACID. |
| **Redis** | `7.4` | Plazas libres por noche y caché | Operaciones atómicas (`DECR`/`INCR`) en memoria para evitar sobreventa. Persistencia activada con AOF. |
| **MongoDB** | `8.0` | Fichas de los albergues | Esquema flexible para guardar datos que varían entre albergues. |

---

## 2. Cómo arrancar y generar datos *(Javier Sánchez)*

### 1. Infraestructura y entorno
```bash
# 1. Configurar variables y levantar contenedores
cp .env.example .env
docker compose up -d

# 2. Entorno virtual y dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Generador de datos (`src/xera_datos.py`)
El generador es parametrizable mediante argumentos por línea de comandos:
* `--albergues`: Número de albergues a generar (por defecto `40`).
* `--peregrinos`: Número de peregrinos con documento y correo únicos (por defecto `1500`).
* `--reservas`: Número de reservas históricas iniciales a generar (por defecto `5000`).
* `--semente`: Semilla pseudoaleatoria para garantizar reproducibilidad exacta (por defecto `42`).
* `--desde`: Fecha inicial de la temporada en formato `AAAA-MM-DD` (por defecto `2027-05-01`).
* `--dias`: Duración en noches de la temporada (por defecto `30`).
* `--sen-carga`: Modo seco (genera los datos en memoria y los muestra por consola sin tocar las bases de datos).

**Comando de carga inicial en bases de datos (PostgreSQL y MongoDB):**
```bash
python -m src.xera_datos --albergues 40 --peregrinos 1500 --reservas 5000 --semente 42
```

### 3. Comprobación de reproducibilidad
Para garantizar que la misma semilla genere exactamente los mismos datos en cualquier momento (independientemente del día en que se ejecute), se fijó `Faker.seed(semente)` y se calcularon las fechas de nacimiento a partir de una fecha fija con `rng`, evitando la variación temporal de `fake.date_of_birth()`.

Se puede verificar ejecutando dos veces con la misma semilla y comparando la salida:
```bash
python -m src.xera_datos --sen-carga --semente 7 > a.txt
python -m src.xera_datos --sen-carga --semente 7 > b.txt
diff a.txt b.txt && echo "PROBA SUPERADA: Os datos son 100% reproducibles"
rm a.txt b.txt
```

---

## 3. Decisiones tomadas *(Marco Vázquez)*

- **Claves en Redis:**
  - Plazas: `albergue:{id}:noite:{fecha}:prazas` (entero).
  - Caché: `cache:camino:{camino}:noite:{fecha}` (JSON).
- **TTL de la caché:** **60 segundos**. Tiempo suficiente para quitarle carga a PostgreSQL sin arriesgarnos a mostrar plazas desactualizadas mucho tiempo.
- **Fichas en MongoDB:**
  - Los **públicos** tienen lo básico: servicios estándar, horarios y titularidad (Xunta/Concello).
  - Los **privados** añaden campos opcionales: teléfono, web, si admiten perros, garaje de bicis, idiomas y una lista de opiniones.

---

## 4. Prueba de sobreventa *(Marco Vázquez)*

En `app.py` lanzamos 30 reservas a la vez con hilos (`ThreadPoolExecutor`) contra un albergue que solo tiene 3 plazas disponibles esa noche. 

Redis descuenta con `decr` de forma atómica; si baja de 0 se hace `incr` y se rechaza. Si hay plaza, se mete en Postgres.

Resultado del test:
```text
Prazas dispoñibles: 3
Lanzando 30 solicitudes de reserva simultáneas (threads)...

--- RESULTADOS DA PROBA ---
Reservas aceptadas: 3 (Esperado: 3)
Reservas rexeitadas: 27 (Esperado: 27)
Prazas restantes en Redis: 0 (Esperado: 0)
Reservas rexistradas en PostgreSQL: 3 (Esperado: 3)
>> DEMOSTRACIÓN EXITOSA: NON HOUBO SOBREVENTA <<
```

---

## 5. Copias de seguridad y restauración *(Javier Sánchez)*

Se implementó el script `src/copia.sh` que automatiza tanto el volcado como la restauración íntegra de PostgreSQL y MongoDB con fecha y hora.

### Funcionamiento de `src/copia.sh`
* **Copia:** Crea un subdirectorio con timestamp en `copias/YYYYMMDD_HHMMSS/`.
  * Vuelca PostgreSQL mediante `pg_dump` directo al contenedor (`postgres_YYYYMMDD_HHMMSS.sql`).
  * Vuelca MongoDB mediante `mongodump` con formato binario empaquetado `--archive` (`mongo_YYYYMMDD_HHMMSS.archive`).
* **Restauración:** Admite el parámetro `--restaurar <carpeta>`, detectando los ficheros y utilizando `psql` para PostgreSQL y `mongorestore --drop` para MongoDB.

### Prueba de pérdida y restauración documentada
```bash
# 1. Generar la copia de seguridad:
./src/copia.sh

# 2. Simular pérdida catastrófica de datos (borrado de tablas y colecciones):
docker exec ca_postgres psql -U p1 -d albergues -c "DROP TABLE reservas, peregrinos, albergues CASCADE;"
docker exec ca_mongo mongosh -u p1 -p cambiame --authenticationDatabase admin --eval "use albergues; db.dropDatabase();"

# 3. Restaurar la última copia creada:
ULTIMA_COPIA=$(ls -td copias/* | head -1)
./src/copia.sh --restaurar "$ULTIMA_COPIA"

# 4. Comprobación de recuperación de registros:
docker exec ca_postgres psql -U p1 -d albergues -c "SELECT COUNT(*) FROM albergues; SELECT COUNT(*) FROM reservas;"
docker exec ca_mongo mongosh -u p1 -p cambiame --authenticationDatabase admin --eval "use albergues; db.fichas.countDocuments();"
```
Tras la restauración, se verificó que el recuento de albergues, peregrinos, reservas y documentos en MongoDB coincide exactamente con el estado original previo al desastre.

---

## 6. Mediciones de rendimiento *(Marco Vázquez)*

### Comparativa de 1.000 consultas (`python -m src.medicions`)

| Sistema | Tiempo total | Media por consulta |
|---|---|---|
| **PostgreSQL** | 0.5043 s | 0.504 ms |
| **Redis** | 0.2551 s | 0.255 ms |

Redis fue el doble de rápido (2.0x), con la ventaja añadida de que responde desde RAM sin cargar la base de datos relacional.

### Consumo de recursos (`docker stats --no-stream`)

| Contenedor | CPU % | Memoria usada |
|---|---|---|
| `ca_postgres` | 0.43% | 37.18 MiB |
| `ca_redis` | 0.40% | 4.48 MiB |
| `ca_mongo` | 0.71% | 205.70 MiB |

---

## 7. Uso de IA

- **Marco Vázquez:** Usé IA para estructurar el test de concurrencia con hilos en `app.py`, corregir un problema con las secuencias de IDs en Postgres y montar el script de mediciones de tiempo. Todo el código fue probado y revisado en local.
- **Javier Fernández:** Usé IA para diseñar el algoritmo de generación de reservas, estructurar la inserción en bloques mediante `execute_values` de `psycopg2` para acelerar la carga en PostgreSQL, y preparar la lógica de restauración con control de errores en `src/copia.sh`. Todo el código fue validado y testeado en local.Asi como tambien la use para solucionar un problema de desincronizacion de las ramas del proyecto.