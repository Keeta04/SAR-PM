# db_manager.py
"""
Módulo de gestión de la base de datos (Database Abstraction Layer).

Esta clase, DatabaseManager, encapsula toda la interacción con la base de datos MySQL.
La aplicación principal no ejecutará consultas SQL directamente, sino que llamará
a los métodos de esta clase.
"""

import mysql.connector
from mysql.connector import pooling, Error
from config_handler import decrypt_value


class DatabaseManager:
    """
    Gestiona todas las operaciones CRUD y la conexión con la base de datos MySQL.
    """

    def __init__(self, config, fernet):  # <--- AÑADIMOS fernet aquí
        """
        Inicializa el pool de conexiones a la base de datos.
        Args:
            config (ConfigParser): El objeto de configuración.
            fernet (Fernet): La instancia de Fernet para descifrar.
        """
        self.pool = None
        try:
            # --- AQUÍ ESTÁ LA CORRECCIÓN ---
            # 1. Obtenemos la contraseña (que puede estar cifrada)
            encrypted_pass = config['mysql']['password']
            # 2. La desciframos para obtener la contraseña real
            db_password = decrypt_value(fernet, encrypted_pass)

            self.pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="app_pool",
                pool_size=5,
                host=config['mysql']['host'],
                user=config['mysql']['user'],
                password=db_password,  # <--- Usamos la contraseña descifrada
                database=config['mysql']['database']
            )
            print("Pool de conexiones a MySQL creado exitosamente.")
        except Error as e:
            print(f"Error al crear el pool de conexiones a MySQL: {e}")
            raise e

    def _get_connection(self):
        """
        Obtiene una conexión del pool.
        """
        if self.pool is None:
            raise Error("El pool de conexiones no está disponible.")
        return self.pool.get_connection()

    def init_db(self):
        """
        Crea las tablas 'contactos', 'multas' y 'mensajes' si no existen.
        """
        # Sentencias SQL para crear cada tabla
        contactos_sql = """
            CREATE TABLE IF NOT EXISTS contactos (
                cedula_rif VARCHAR(20) PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                email VARCHAR(255) DEFAULT NULL UNIQUE,
                telefono VARCHAR(25) DEFAULT NULL UNIQUE,
                direccion TEXT
            )
        """
        multas_sql = """
            CREATE TABLE IF NOT EXISTS multas (
                expediente_nro VARCHAR(50) PRIMARY KEY,
                cedula_rif VARCHAR(20) NOT NULL,
                uc SMALLINT,
                bs DECIMAL(16, 2) DEFAULT 0.00,
                fecha_multa DATE,
                fecha_pago DATE DEFAULT NULL,
                multa_pendiente BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (cedula_rif) REFERENCES contactos(cedula_rif) ON DELETE CASCADE
            )
        """
        mensajes_sql = """
            CREATE TABLE IF NOT EXISTS mensajes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL UNIQUE,
                asunto_email TEXT,
                cuerpo_email TEXT,
                mensaje_whatsapp TEXT
            )
        """

        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(contactos_sql)
            cursor.execute(multas_sql)
            cursor.execute(mensajes_sql)
        db.close()
        print("Tablas de la BD verificadas/creadas.")

    # --- Métodos para Contactos ---

    def get_contacts(self, search_term, page, per_page):
        """
        Obtiene una lista paginada de contactos, con opción de búsqueda.
        """
        offset = (page - 1) * per_page
        base_query = "FROM contactos"
        search_clause = ""
        params = []

        if search_term:
            search_clause = " WHERE (cedula_rif LIKE %s OR cedula_rif LIKE %s)"
            params.extend([f"{search_term}%", f"%-{search_term}%"])

        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            count_query = f"SELECT COUNT(*) as total {base_query}{search_clause}"
            cursor.execute(count_query, tuple(params))
            total_contacts = cursor.fetchone()['total']

            select_query = f"SELECT * {base_query}{search_clause} ORDER BY nombre LIMIT %s OFFSET %s"
            final_params = params + [per_page, offset]
            cursor.execute(select_query, tuple(final_params))
            contactos = cursor.fetchall()
        db.close()

        return contactos, total_contacts

    def add_contact(self, cedula_rif, nombre, email, telefono, direccion):
        """
        Añade un nuevo contacto a la base de datos.
        """
        query = "INSERT INTO contactos (cedula_rif, nombre, email, telefono, direccion) VALUES (%s, %s, %s, %s, %s)"
        params = (cedula_rif, nombre, email or None,
                  telefono or None, direccion or None)
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, params)
            db.commit()
        db.close()

    def update_contact(self, cedula_rif, nombre, email, telefono, direccion):
        """
        Actualiza un contacto existente.
        """
        query = "UPDATE contactos SET nombre = %s, email = %s, telefono = %s, direccion = %s WHERE cedula_rif = %s"
        params = (nombre, email or None, telefono or None,
                  direccion or None, cedula_rif)
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, params)
            db.commit()
        db.close()

    def delete_contacts(self, cedulas_list):
        """
        Elimina uno o más contactos basado en su Cédula/RIF.
        """
        placeholders = ','.join(['%s'] * len(cedulas_list))
        query = f"DELETE FROM contactos WHERE cedula_rif IN ({placeholders})"
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, tuple(cedulas_list))
            db.commit()
        db.close()

    def get_all_contacts_for_export(self):
        """
        Obtiene todos los contactos para exportar a CSV.
        """
        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT cedula_rif, nombre, email, telefono, direccion FROM contactos ORDER BY nombre")
            contacts = cursor.fetchall()
        db.close()
        return contacts

    def import_contacts_from_list(self, contacts_to_add):
        """
        Importa una lista de contactos. Ignora duplicados.
        Devuelve el número de filas insertadas.
        """
        db = self._get_connection()
        with db.cursor() as cursor:
            query = "INSERT IGNORE INTO contactos (cedula_rif, nombre, email, telefono, direccion) VALUES (%s, %s, %s, %s, %s)"
            cursor.executemany(query, contacts_to_add)
            db.commit()
            rowcount = cursor.rowcount
        db.close()
        return rowcount

    # --- Métodos para Multas ---

    def get_fines_by_contact(self, cedula_rif):
        """
        Obtiene todas las multas (pagadas y pendientes) para un contacto específico.
        """
        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM multas WHERE cedula_rif = %s", (cedula_rif,))
            fines = cursor.fetchall()
        db.close()
        return fines

    def get_all_fines(self, year=None, month=None):
        """
        Obtiene todas las multas, con opción de filtrar por año y mes.
        """
        query = "SELECT * FROM multas"
        params = []
        if year is not None and month is not None:
            query += " WHERE YEAR(fecha_multa) = %s AND MONTH(fecha_multa) = %s"
            params.extend([year, month])
        query += " ORDER BY fecha_multa DESC"

        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(query, tuple(params))
            multas = cursor.fetchall()
        db.close()
        return multas

    # En db_manager.py, dentro de la clase DatabaseManager

    def get_fines_for_report(self, start_date=None, end_date=None, status='all', cedula_rif=None):
        """
        Obtiene una lista de multas para un reporte, basado en filtros avanzados.

        Args:
            start_date (str, opcional): Fecha de inicio en formato 'YYYY-MM-DD'.
            end_date (str, opcional): Fecha de fin en formato 'YYYY-MM-DD'.
            status (str, opcional): 'all', 'paid', or 'pending'.
            cedula_rif (str, opcional): Cédula o RIF específico del contacto.

        Returns:
            list: Una lista de diccionarios, donde cada uno es una multa.
        """
        query = "SELECT * FROM multas WHERE 1=1"
        params = []

        if start_date:
            query += " AND fecha_multa >= %s"
            params.append(start_date)

        if end_date:
            query += " AND fecha_multa <= %s"
            params.append(end_date)

        if status == 'pagada':
            query += " AND multa_pendiente = FALSE"
        elif status == 'pendiente':
            query += " AND multa_pendiente = TRUE"

        if cedula_rif and cedula_rif.strip():
            query += " AND cedula_rif = %s"
            params.append(cedula_rif.strip())

        query += " ORDER BY fecha_multa DESC"

        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(query, tuple(params))
            multas = cursor.fetchall()
        db.close()
        return multas

    def add_fine(self, expediente, cedula, uc, fecha_multa, es_pagada, monto_bs, fecha_pago):
        """
        Añade una nueva multa a la base de datos.
        """
        query = """
            INSERT INTO multas (expediente_nro, cedula_rif, uc, bs, fecha_multa, fecha_pago, multa_pendiente)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (expediente, cedula, uc, monto_bs,
                  fecha_multa, fecha_pago, not es_pagada)
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM contactos WHERE cedula_rif = %s", (cedula,))
            if cursor.fetchone()[0] == 0:
                raise ValueError(
                    f"El contacto con Cédula/RIF '{cedula}' no existe.")

            cursor.execute(query, params)
            db.commit()
        db.close()

    def update_fine_details(self, expediente, uc, fecha):
        """Actualiza los detalles (UC y fecha) de una multa existente."""
        db = self._get_connection()
        with db.cursor() as cursor:
            query = "UPDATE multas SET uc = %s, fecha_multa = %s WHERE expediente_nro = %s"
            cursor.execute(query, (uc, fecha, expediente))
            db.commit()
        db.close()

    def mark_fine_as_paid(self, expediente, monto, fecha):
        """
        Marca una multa como pagada, actualizando su estado, monto y fecha de pago.
        """
        query = "UPDATE multas SET multa_pendiente = FALSE, bs = %s, fecha_pago = %s WHERE expediente_nro = %s"
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, (monto, fecha, expediente))
            db.commit()
        db.close()

    def revert_fine_to_pending(self, expediente):
        """
        Revierte una multa a estado 'pendiente', borrando los detalles de pago.
        """
        query = "UPDATE multas SET multa_pendiente = TRUE, bs = 0.00, fecha_pago = NULL WHERE expediente_nro = %s"
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, (expediente,))
            db.commit()
        db.close()

    def delete_fines(self, expedientes_list):
        """
        Elimina una o más multas basado en su número de expediente.
        """
        placeholders = ','.join(['%s'] * len(expedientes_list))
        query = f"DELETE FROM multas WHERE expediente_nro IN ({placeholders})"
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, tuple(expedientes_list))
            db.commit()
        db.close()

    # --- Métodos para Mensajes y otros ---

    def get_fine_descriptions(self):
        """
        Obtiene una lista de todas las descripciones de multas únicas.
        """
        query = """
            SELECT DISTINCT SUBSTRING(expediente_nro, LOCATE(' ', expediente_nro) + 1)
            FROM multas
            WHERE expediente_nro LIKE '% %'
        """
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query)
            descriptions = [row[0] for row in cursor.fetchall() if row[0]]
        db.close()
        return descriptions

    def get_preset_messages(self):
        """
        Obtiene todos los mensajes predefinidos de la base de datos.
        """
        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute("SELECT id, nombre FROM mensajes ORDER BY nombre")
            messages = cursor.fetchall()
        db.close()
        return messages

    def get_message_details(self, message_id):
        """
        Obtiene los detalles completos de un mensaje predefinido por su ID.
        """
        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM mensajes WHERE id = %s", (message_id,))
            message = cursor.fetchone()
        db.close()
        return message

    def save_message(self, name, subject, email_body, whatsapp_msg):
        """
        Guarda un nuevo mensaje predefinido.
        """
        query = "INSERT INTO mensajes (nombre, asunto_email, cuerpo_email, mensaje_whatsapp) VALUES (%s, %s, %s, %s)"
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, (name, subject, email_body, whatsapp_msg))
            db.commit()
        db.close()

    # Y así sucesivamente para update_message, delete_message, import_multas, etc.
    # El patrón es el mismo: mover la lógica SQL a un método aquí.
    def update_message(self, message_id, name, subject, email_body, whatsapp_msg):
        """
        Actualiza un mensaje predefinido existente por su ID.
        """
        query = "UPDATE mensajes SET nombre = %s, asunto_email = %s, cuerpo_email = %s, mensaje_whatsapp = %s WHERE id = %s"
        params = (name, subject, email_body, whatsapp_msg, message_id)
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, params)
            db.commit()
        db.close()

    def delete_message(self, message_id):
        """
        Elimina un mensaje predefinido por su ID.
        """
        query = "DELETE FROM mensajes WHERE id = %s"
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute(query, (message_id,))
            db.commit()
        db.close()

    def get_all_contact_cedulas(self):
        """Obtiene un conjunto de todas las Cédulas/RIF de los contactos para una validación rápida."""
        db = self._get_connection()
        with db.cursor() as cursor:
            cursor.execute("SELECT cedula_rif FROM contactos")
            # Devolver un set es más eficiente para búsquedas (e.g., 'if cedula in cedulas_validas:')
            return {row[0] for row in cursor.fetchall()}
        # La conexión se cierra automáticamente si hay un error gracias al 'with'

    def import_fines_from_list(self, fines_list):
        """Inserta una lista de multas. Ignora duplicados y devuelve el número de filas insertadas."""
        db = self._get_connection()
        with db.cursor() as cursor:
            query = "INSERT IGNORE INTO multas (expediente_nro, cedula_rif, uc, bs, fecha_multa, fecha_pago, multa_pendiente) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.executemany(query, fines_list)
            db.commit()
            rowcount = cursor.rowcount
        db.close()
        return rowcount

    # En db_manager.py, REEMPLAZA el método get_pending_fines_for_contact por este:

    def get_pending_fines_count_for_contact(self, cedula_rif):
        """
        Obtiene únicamente el NÚMERO de multas pendientes para un contacto específico.
        """
        query = "SELECT COUNT(*) as count FROM multas WHERE cedula_rif = %s AND multa_pendiente = TRUE"
        db = self._get_connection()
        count = 0
        with db.cursor(dictionary=True) as cursor:
            cursor.execute(query, (cedula_rif,))
            result = cursor.fetchone()
            if result:
                count = result['count']
        db.close()
        return count

    def get_dashboard_stats(self):
        """
        Obtiene las estadísticas clave para el dashboard en una sola consulta.
        Devuelve un diccionario con el total de contactos, total de multas pendientes,
        y el monto total recaudado en el mes actual.
        """
        stats = {
            'total_contacts': 0,
            'pending_fines_count': 0,
            'revenue_current_month': 0.00
        }
        db = self._get_connection()
        with db.cursor(dictionary=True) as cursor:
            # Obtener total de contactos
            cursor.execute("SELECT COUNT(*) as total FROM contactos")
            result = cursor.fetchone()
            if result:
                stats['total_contacts'] = result['total']

            # Obtener multas pendientes
            cursor.execute(
                "SELECT COUNT(*) as total FROM multas WHERE multa_pendiente = TRUE")
            result = cursor.fetchone()
            if result:
                stats['pending_fines_count'] = result['total']

            # Obtener recaudación del mes actual (basado en fecha_pago)
            query_revenue = """
                SELECT SUM(bs) as total FROM multas 
                WHERE multa_pendiente = FALSE 
                AND YEAR(fecha_pago) = YEAR(CURDATE()) 
                AND MONTH(fecha_pago) = MONTH(CURDATE())
            """
            cursor.execute(query_revenue)
            result = cursor.fetchone()
            if result and result['total'] is not None:
                stats['revenue_current_month'] = float(result['total'])

        db.close()
        return stats
