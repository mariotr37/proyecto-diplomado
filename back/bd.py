import os
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv


class BaseDeDatos:
    def __init__(self):
        # Cargar variables de entorno desde el archivo .env
        load_dotenv()

        # Leer variables de entorno
        self.host = os.getenv("DB_HOST")
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.database = os.getenv("DB_NAME")

        self.conn = None

    def conectar(self):
        """Establece la conexión a la base de datos."""
        if self.conn is None:
            try:
                self.conn = mysql.connector.connect(
                    host=self.host,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    port=3306,
                    charset='utf8mb4',
                    collation='utf8mb4_general_ci'
                )
                print("Conexión a la base de datos establecida exitosamente.")
            except mysql.connector.Error as e:
                print(f"Error conectando a la base de datos: {e}")
                raise

    def obtener_conexion(self):
        """Devuelve la conexión a la base de datos."""
        if self.conn is None:
            self.conectar()
        return self.conn

    def cerrar_conexion(self):
        """Cierra la conexión a la base de datos."""
        if self.conn is not None:
            self.conn.close()
            self.conn = None
            print("Conexión a la base de datos cerrada.")

    def guardar_usuario(self, nombre, telefono, email, password, public_key):
        """Guarda un usuario en la tabla 'usuario' con su nombre y public key."""
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor()

            # Inserta el usuario en la tabla 'usuario'
            sql = "INSERT INTO Usuario (Name, PublicKey, Telefono, Email, Password) VALUES (%s, %s, %s, %s, %s)"
            cursor.execute(sql, (nombre, public_key, telefono, email, password))

            # Confirma la transacción
            conn.commit()
            cursor.close()
            return "Usuario guardado exitosamente."

        except mysql.connector.Error as e:
            return f"Error guardando el usuario: {e}"

    def verificar_correo_existente(self, email):
        """Verifica si un correo electrónico ya existe en la tabla 'Usuarios'."""
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor()

            # Verificar si el correo ya existe
            sql = "SELECT COUNT(*) FROM Usuario WHERE Email = %s"
            cursor.execute(sql, (email,))
            result = cursor.fetchone()
            cursor.close()
            return result[0] == 0

        except mysql.connector.Error as e:
            print(f"Error verificando el correo: {e}")
            return False

    def obtener_usuario_por_email(self, email):
        """Obtiene un usuario de la base de datos por su email."""
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor(dictionary=True)

            sql = "SELECT * FROM Usuario WHERE Email = %s"
            cursor.execute(sql, (email,))
            user = cursor.fetchone()

            cursor.close()
            return user

        except mysql.connector.Error as e:
            print(f"Error al obtener el usuario: {e}")
            return None

    def obtener_lista_empleados(self):
        """Obtiene la lista de correos electrónicos de los empleados de la base de datos."""
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor(dictionary=True)

            sql = "SELECT email FROM Usuario"
            cursor.execute(sql)
            correos = cursor.fetchall()

            cursor.close()
            return correos

        except mysql.connector.Error as e:
            print(f"Error al obtener la lista de correos electrónicos: {e}")
            return []

    def obtener_usuario_por_id(self, id):
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor(dictionary=True)

            sql = "SELECT * FROM Usuario WHERE id = %s"
            cursor.execute(sql, (id,))
            usuario = cursor.fetchone()

            cursor.close()
        except mysql.connector.Error as e:
            print(f"Error al obtener el usuario: {e}")
            return None
        return usuario

    def guardar_archivo(self, filename, file_data, user_id, hash_sha256, correos_usuario):
        try:
            conn = self.obtener_conexion()
            cursor = conn.cursor(dictionary=True)

            sql = "INSERT INTO File (nombre_archivo, contenido_archivo, usuario_id, hash) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (filename, file_data, user_id, hash_sha256))
            archivo_id = cursor.lastrowid

            for correo_user in correos_usuario:
                sql_usuario = "SELECT id FROM Usuario WHERE email = %s"
                cursor.execute(sql_usuario, (correo_user,))
                result = cursor.fetchone()  # Obtiene el primer resultado

                if result:
                    usuario_id = result['id']  # Asume que 'usuario_id' es la primera columna en el resultado

                    # 2. Realizar la inserción en la tabla Firma
                    sql_firma = "INSERT INTO Firma (archivo_id, usuario_id, estado_firma) VALUES (%s, %s, %s)"
                    cursor.execute(sql_firma, (archivo_id, usuario_id, 0))

            conn.commit()
            cursor.close()

        except mysql.connector.Error as e:
            print(f"Error al obtener el usuario: {e}")
            return None

    def obtener_archivo_por_id(self, archivo_id):
        # Conectar a la base de datos y ejecutar la consulta
        conn = self.obtener_conexion()
        cursor = conn.cursor(dictionary=True)

        # Consultar el archivo por su ID
        sql = "SELECT nombre_archivo, contenido_archivo FROM File WHERE id = %s"
        cursor.execute(sql, (archivo_id,))

        # Obtener el resultado
        resultado = cursor.fetchone()
        print(type(resultado))
        cursor.close()
        conn.close()

        if resultado:
            return {
                "nombre_archivo": resultado["nombre_archivo"],
                "contenido_archivo": resultado["contenido_archivo"]
            }
        else:
            return None

# # Ejemplo de uso
# if __name__ == "__main__":
#     bd = BaseDeDatos()
#     bd.guardar_usuario("juan", "key")
#     bd.cerrar_conexion()
#     # Realizar operaciones con la base de datos...
