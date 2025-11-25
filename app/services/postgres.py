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
      - insert_sheet_from_dict(data, table_name)
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

    def insert_sheet_from_dict(self, data: Dict[str, Any], table_name: str) -> bool:
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
        This mirrors SheetsService behaviour returning parsed message dicts.
        """
        try:
            conn = self._connect()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = "SELECT messages FROM whatsapp_messages WHERE phone = %s"
            cur.execute(sql, (phone,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            if not row:
                return None
            messages = row['messages']
            # messages may be stored as JSON array or newline-separated
            try:
                parsed = json.loads(messages)
                if isinstance(parsed, list):
                    return parsed
                else:
                    return [parsed]
            except Exception:
                # fallback split by newline
                out = []
                for part in messages.split('\n'):
                    try:
                        out.append(json.loads(part))
                    except Exception:
                        out.append(part)
                return out

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
