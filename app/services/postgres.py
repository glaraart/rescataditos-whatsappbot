import psycopg2
import psycopg2.extras
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from app.config import settings

logger = logging.getLogger(__name__)


class PostgresService:
    """Simple psycopg2-based service implementing minimal methods used by MessageHandler.

    Methods:
      - insert_record(data, table_name)
      - search_phone_in_whatsapp_sheet(phone) -> list of messages
      - delete_records_optimized(phone, table_name)
      - check_animal_name_exists(nombre) -> id or None
    """

    def __init__(self):
        self.host = settings.HOST
        self.port = settings.PORT_DB
        self.dbname = settings.DBNAME
        self.user = settings.USER
        self.password = settings.PASSWORD

    def _connect(self):
        conn = psycopg2.connect(
            host=self.host,
            port=self.port or 5432,
            dbname=self.dbname,
            user=self.user,
            password=self.password,
            sslmode='require' if settings.ENVIRONMENT != 'development' else 'disable'
        )
        return conn

    def insert_record(self, data: Dict[str, Any], table_name: str) -> bool:
        """Insert a row into the given table_name mapping dict keys to columns."""
        try:
            conn = self._connect()
            cur = conn.cursor()

            # normalize keys and values
            keys = list(data.keys())
            cols = ','.join(keys)
            placeholders = ','.join(['%s'] * len(keys))
            values = [json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for v in data.values()]

            sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
            cur.execute(sql, values)
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error insertando en {table_name}: {e}")
            return False

    def search_phone_in_whatsapp_sheet(self, phone: str) -> Optional[List[Dict[str, Any]]]:
        """Return list of recent messages for phone from whatsapp_messages table.
        Includes regular messages and incomplete_request entries.
        Returns parsed message dicts with proper handling of incomplete requests.
        """
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            # Get all messages ordered by timestamp to maintain conversation flow
            sql = "SELECT messages FROM whatsapp_messages WHERE phone = %s AND timestamp >= CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'  - interval '5 minutes' ORDER BY timestamp ASC"
            cur.execute(sql, (phone,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            if not rows:
                return None
            
            all_messages = []
            
            # Process each row and parse JSON
            for row in rows:
                messages = row['messages']
                try:
                    # Try parsing as JSON
                    parsed = json.loads(messages)
                    if isinstance(parsed, list):
                        all_messages.extend(parsed)
                    else:
                        all_messages.append(parsed)
                except Exception:
                    # Fallback: treat as string or newline-separated
                    try:
                        for part in messages.split('\n'):
                            if part.strip():
                                try:
                                    all_messages.append(json.loads(part))
                                except Exception:
                                    # Plain text message
                                    all_messages.append({"type": "text", "text": {"body": part}})
                    except Exception:
                        # Last resort: treat entire thing as text
                        all_messages.append({"type": "text", "text": {"body": messages}})
            
            # Retornar en orden cronológico (más antiguo primero)
            return all_messages if all_messages else None

        except Exception as e:
            logger.error(f"Error buscando teléfono {phone} en Postgres: {e}")
            return None

    def delete_records_optimized(self, phone: str, table_name: str) -> bool:
        """Delete records matching phone in a simple way."""
        try:
            conn = self._connect()
            cur = conn.cursor()
            sql = f"DELETE FROM {table_name} WHERE phone = %s"
            cur.execute(sql, (phone,))
            deleted = cur.rowcount
            conn.commit()
            cur.close()
            conn.close()
            logger.info(f"Eliminados {deleted} registros del teléfono {phone} en {table_name}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando registros en Postgres: {e}")
            return False

    def check_animal_name_exists(self, nombre: str) -> Optional[int]:
        """Return animal id if exists (case-insensitive) else None"""
        try:
            conn = self._connect()
            cur = conn.cursor()
            sql = "SELECT id FROM animales WHERE lower(nombre) = lower(%s) LIMIT 1"
            cur.execute(sql, (nombre,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                return row[0]
            return None
        except Exception as e:
            logger.error(f"Error verificando animal por nombre {nombre}: {e}")
            return None
    
    def get_animal_by_name(self, nombre: str) -> Optional[int]:
        """Return animal id if exists (case-insensitive) and activo=true, else None"""
        try:
            conn = self._connect()
            cur = conn.cursor()
            sql = "SELECT id FROM animales WHERE lower(nombre) = lower(%s) AND activo = true order by fecha desc LIMIT 1"
            cur.execute(sql, (nombre,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                return row[0]
            return None
        except Exception as e:
            logger.error(f"Error obteniendo animal por nombre {nombre}: {e}")
            return None
    
    def get_last_inserted_id(self, table_name: str, id_column: str = "id") -> Optional[int]:
        """Get the last inserted ID from a table using currval"""
        try:
            conn = self._connect()
            cur = conn.cursor()
            # Construct sequence name (PostgreSQL naming convention: tablename_idcolumn_seq)
            sequence_name = f"{table_name}_{id_column}_seq"
            sql = f"SELECT currval('{sequence_name}')"
            cur.execute(sql)
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                return int(row[0])
            return None
        except Exception as e:
            logger.error(f"Error obteniendo último ID de {table_name}: {e}")
            return None
    
    def get_animales_activos_en_refugio(self) -> List[Dict[str, Any]]:
        """Get all active animals currently in refuge (estado_id = 1, ubicacion_id = 1)"""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            sql = """
                SELECT DISTINCT a.id, a.nombre, a.tipo_animal
                FROM animales a
                LEFT JOIN LATERAL (
                    SELECT estado_id, ubicacion_id
                    FROM eventos
                    WHERE animal_id = a.id
                    ORDER BY fecha DESC
                    LIMIT 1
                ) e ON true
                WHERE a.activo = true 
                  AND e.estado_id in(2,3
                  AND e.ubicacion_id = 1
                ORDER BY a.nombre
            """
            
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            # Convert RealDictRow to normal dict
            result = [dict(row) for row in rows]
            logger.info(f"Animales activos en refugio: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo animales activos en refugio: {e}")
            return []
    
    def get_dashboard_data(self) -> List[Dict[str, Any]]:
        """Ejecutar query del dashboard y retornar lista de registros"""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            sql = """
                SELECT
                  a.id AS animal_id,
                  a.nombre AS "Nombre",
                  e.estado_id AS "Estado ID",
                  COALESCE(s.nombre, 'Desconocido') AS "Estado",
                  COALESCE(u.nombre, 'Desconocido') AS "Ubicación",
                  a.fecha AS "Fecha Rescate",
                  e.fecha AS "Fecha Estado",
                  i.contenido AS "Contenido",
                  i.post_id AS "Post ID"
                FROM animales a
                LEFT JOIN LATERAL (
                  SELECT ubicacion_id, estado_id, fecha
                  FROM eventos
                  WHERE animal_id = a.id
                  ORDER BY fecha DESC
                  LIMIT 1
                ) e ON true
                LEFT JOIN estado s ON s.estado_id = e.estado_id
                LEFT JOIN ubicacion u ON u.id = e.ubicacion_id
                LEFT JOIN LATERAL (
                  SELECT contenido, post_id
                  FROM interaccion
                  WHERE animal_id = a.id
                  ORDER BY fecha DESC
                  LIMIT 1
                ) i ON true
                WHERE a.activo = true
                ORDER BY a.fecha DESC;
            """
            
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            # Convertir RealDictRow a dict normal
            result = [dict(row) for row in rows]
            logger.info(f"Dashboard data: {len(result)} registros obtenidos")
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo datos del dashboard: {e}")
            return []

    # ===== TRACKING MOVIMIENTO METHODS =====
    
    def get_all_active_animals(self) -> List[Dict[str, Any]]:
        """Get all active animals (activo=true)"""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = "SELECT id, nombre, tipo_animal FROM animales WHERE activo = true ORDER BY nombre"
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error obteniendo animales activos: {e}")
            return []
    
    def insert_tracking_movimiento(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert tracking_movimiento record and return ID"""
        try:
            conn = self._connect()
            cur = conn.cursor()
            
            sql = """
                INSERT INTO tracking_movimiento 
                (tipo, destino, responsable, fecha, observaciones)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """
            
            cur.execute(sql, (
                data.get('tipo'),
                data.get('destino'),
                data.get('responsable'),
                data.get('fecha'),
                data.get('observaciones')
            ))
            
            tracking_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"✅ Tracking insertado con ID: {tracking_id}")
            return tracking_id
            
        except Exception as e:
            logger.error(f"Error insertando tracking_movimiento: {e}")
            return None
    
    def insert_tracking_movimiento_animal(self, data: Dict[str, Any]) -> bool:
        """Insert tracking_movimiento_animales (N:N relationship)"""
        try:
            conn = self._connect()
            cur = conn.cursor()
            
            sql = """
                INSERT INTO tracking_movimiento_animales 
                (tracking_id, animal_id)
                VALUES (%s, %s)
            """
            
            cur.execute(sql, (
                data.get('tracking_id'),
                data.get('animal_id')
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error insertando tracking_movimiento_animal: {e}")
            return False
    
    def get_ultima_salida_parque(self) -> Optional[Dict[str, Any]]:
        """Get the most recent park outing (salida to parque) that hasn't returned yet"""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            sql = """
                SELECT * FROM tracking_movimiento
                WHERE destino = 'parque' 
                  AND tipo = 'salida'
                  AND NOT EXISTS (
                      SELECT 1 FROM tracking_movimiento t2
                      WHERE t2.destino = 'parque'
                        AND t2.tipo = 'regreso'
                        AND t2.fecha >= tracking_movimiento.fecha
                  )
                ORDER BY fecha DESC, hora_salida DESC
                LIMIT 1
            """
            
            cur.execute(sql)
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if row:
                return dict(row)
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo última salida al parque: {e}")
            return None
    
    def get_animales_de_salida(self, tracking_id: int) -> List[Dict[str, Any]]:
        """Get all animals that went on a specific outing"""
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            sql = """
                SELECT a.id, a.nombre, a.tipo_animal
                FROM animales a
                INNER JOIN tracking_movimiento_animales tma ON tma.animal_id = a.id
                WHERE tma.tracking_id = %s
                ORDER BY a.nombre
            """
            
            cur.execute(sql, (tracking_id,))
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error obteniendo animales de salida {tracking_id}: {e}")
            return []
