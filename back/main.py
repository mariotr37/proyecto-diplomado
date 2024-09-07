import base64
import datetime
import hashlib
import io

import bcrypt
import jwt
from flask import request, jsonify
from flask import send_file
from flask_cors import CORS
from flask import Flask
from flask import Flask, request, jsonify
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from Bd import BaseDeDatos
from RSAKeyGenerator import RSAKeyGenerator
from Token_ import token_required

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://localhost:8080"]}})
app.config['SECRET_KEY'] = 'test'

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    bd = BaseDeDatos()

    rsa_generator = RSAKeyGenerator()
    rsa_generator.generate_keys()
    private_key_pem = rsa_generator.get_private_key_pem()
    public_key_pem = rsa_generator.get_public_key_pem()

    name = data['nombre']
    telefono = data['telefono']
    email = data.get('email')
    password = data.get('password')
    password = generar_password_hash(password)

    if not name or not telefono or not password or not email:
        return jsonify({"error": "Llene todos los campos"}), 400

    if bd.verificar_correo_existente(email) is False:
        return jsonify({"error": "El correo ya esta en uso"}), 400

    respuesta = bd.guardar_usuario(nombre=name, telefono=telefono,
                                   email=email, password=password, public_key=public_key_pem)

    response = {
        "message": "Usuario guardado exitosamente",
        "name": name,
        "privateKey": private_key_pem,
        "respuesta": respuesta
    }

    return jsonify(response), 201


@app.route('/inicio_sesion', methods=['POST'])
def login():
    data = request.get_json()
    bd = BaseDeDatos()

    email = data['email']
    password = data['password']

    if not email or not password:
        return jsonify({"error": "Llene todos los campos"}), 400

    # Verificar si el usuario existe en la base de datos
    print(f"Correo a buscar {email}")
    user = bd.obtener_usuario_por_email(email)
    print(user)
    if not user:
        return jsonify({"error": "Correo o contraseña incorrectos 1"}), 401

    # Verificar la contraseña
    if not verificar_password_hash(password, user['Password'].encode('utf-8')):
        return jsonify({"error": "Correo o contraseña incorrectos 2"}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({'token': token, 'message': 'Inicio de sesión exitoso'}), 200


@app.route('/lista_usuarios', methods=['GET'])
@token_required
def lista_usuarios(current_user):
    bd = BaseDeDatos()
    usuarios = bd.obtener_lista_empleados()

    emails_str = ','.join([email['email'] for email in usuarios])
    result = {'email': emails_str}

    return jsonify(result), 200


@app.route('/lista_archivos_firmar', methods=['GET'])
@token_required
def lista_archivos_firmar(current_user):
    bd = BaseDeDatos()
    files = bd.obtener_archivos_por_usuario_y_estado(current_user['id'])


    return jsonify(files), 200


@app.route('/upload', methods=['POST'])
@token_required
def upload_file(current_user):
    bd = BaseDeDatos()

    if 'file' not in request.files:
        return jsonify({"error": "No se ha enviado ningún archivo"}), 400

    codigos_usuario_str = request.args.get('codigos_usuario')
    if not codigos_usuario_str:
        return jsonify({"error": "No se ha enviado ningún código de usuario"}), 400
    correos_usuario = codigos_usuario_str.split(',')
    correos_usuario = [codigo.strip() for codigo in correos_usuario]  # Limpiar espacios

    file = request.files['file']

    # Verificar que el archivo no esté vacío
    if file.filename == '':
        return jsonify({"error": "El archivo está vacío"}), 400

    # Procesar el archivo (por ejemplo, guardarlo o almacenarlo en base de datos)
    file_data = file.read()
    hash_sha256 = hashlib.sha256(file_data).hexdigest()

    bd.guardar_archivo(file.filename, file_data, current_user['id'], hash_sha256, correos_usuario)

    return jsonify({"message": "Archivo recibido exitosamente", "filename": file.filename}), 200



@app.route('/download', methods=['GET'])
@token_required
def descargar_archivo(current_user):
    bd = BaseDeDatos()
    data = request.get_json()

    archivo_id = data['archivo_id']

    # Obtener el archivo desde la base de datos usando el ID
    archivo = bd.obtener_archivo_por_id(archivo_id)

    if archivo is None:
        return jsonify({"error": "Archivo no encontrado"}), 404

    # Crear un archivo en memoria (usando io.BytesIO)
    file_data = io.BytesIO(archivo['contenido_archivo'])
    file_data.seek(0)

    # Enviar el archivo usando send_file de Flask
    return send_file(
        file_data,
        as_attachment=True,
        download_name=archivo['nombre_archivo']  # Nombre del archivo a descargar
    )


@app.route('/firmar_archivo', methods=['POST'])
@token_required
def firmar_archivo(current_user):
    bd = BaseDeDatos()
    hash_file = request.args.get('hash_file')

    if 'privateKey' not in request.files:
        return jsonify({'message': 'Se requiere el archivo .pem con la llave privada y el ID de usuario'}), 400

        # Obtener la llave privada del archivo .pem y el usuario_id del formulario
    private_key_pem = request.files['privateKey'].read().decode("utf-8")
    private_key_pem = formatear_llave_privada(private_key_pem)
    usuario_id = current_user['id']

    # Obtener la llave pública desde la base de datos
    result = bd.obtener_llave_publica(usuario_id)

    if not result:
        return jsonify({'message': 'No se encontró la llave pública para el usuario proporcionado'}), 404

    try:
        # Cargar las llaves
        private_key = cargar_llave_privada(private_key_pem.encode('utf-8'))
        public_key = cargar_llave_publica(result["PublicKey"])

        firma = firmar_mensaje(private_key, hash_file.encode('utf-8'))
        # Verificar la firma con la llave pública
        if verificar_firma(public_key, hash_file.encode("utf-8"), firma):
            print("ish")
            bd = BaseDeDatos()
            bd.actualizar_firma(usuario_id, hash_file, firma_a_base64(firma))
            return jsonify({'message': 'Las llaves corresponden. La firma es válida.'})
        else:
            return jsonify({'message': 'Las llaves NO corresponden.'}), 400

    except Exception as e:
        return jsonify({'message': 'Error al procesar las llaves.', 'error': str(e)}), 500


###########################################################
###########################################################

# Almacenar el hash con salt
def generar_password_hash(password):
    # Generar la salt y crear el hash
    hash_con_salt = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    return hash_con_salt


# Verificar la contraseña
def verificar_password_hash(password, hash_almacenado):
    # Verificar si la contraseña coincide con el hash almacenado
    return bcrypt.checkpw(password.encode('utf-8'), hash_almacenado)

# Cargar la llave pública desde el texto plano
def cargar_llave_publica(public_key_text):
    return serialization.load_pem_public_key(
        public_key_text.encode('utf-8'),  # Convertir texto plano a bytes
        backend=default_backend()
    )

# Cargar la llave privada desde el archivo .pem
def cargar_llave_privada(private_key_pem):
    return serialization.load_pem_private_key(
        private_key_pem,
        password=None,  # Si la clave tiene contraseña, manejarla aquí
        backend=default_backend()
    )

# Verificar la firma usando la llave pública
def verificar_firma(public_key, mensaje, firma):
    try:
        public_key.verify(
            firma,
            mensaje,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception as e:
        print(f"Error al verificar: {e}")
        return False

# Convertir la firma (bytes) a una cadena en Base64
def firma_a_base64(firma):
    return base64.b64encode(firma).decode('utf-8')

# Convertir de Base64 a bytes (cuando necesites verificar la firma)
def base64_a_firma(firma_base64):
    return base64.b64decode(firma_base64)

def formatear_llave_privada(private_key_string):
    # Eliminar cualquier espacio o salto de línea innecesario
    private_key_string = private_key_string.replace('\\n', '').replace('\n', '').strip()
    private_key_string = private_key_string.replace('-----BEGIN RSA PRIVATE KEY-----', '').replace('-----END RSA PRIVATE KEY-----', '').strip()

    # Reinsertar los saltos de línea cada 64 caracteres
    formatted_key = "-----BEGIN RSA PRIVATE KEY-----\n"
    for i in range(0, len(private_key_string), 64):
        formatted_key += private_key_string[i:i + 64] + '\n'
    formatted_key += "-----END RSA PRIVATE KEY-----\n"

    return formatted_key
# Firmar un mensaje simple con la llave privada
def firmar_mensaje(private_key, mensaje):
    try:
        firma = private_key.sign(
            mensaje,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
    except Exception as e:
        print(f"Error al verificar: {e}")

    return firma

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
