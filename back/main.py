import datetime
import hashlib
import io

import bcrypt
import jwt
from flask import Flask, send_file
from flask import request, jsonify
from flask_cors import CORS

from RSAKeyGenerator import RSAKeyGenerator
from Bd import BaseDeDatos
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
    user = bd.obtener_usuario_por_email(email)
    if not user:
        return jsonify({"error": "Correo o contraseña incorrectos"}), 401

    # Verificar la contraseña
    if not verificar_password_hash(password, user['Password'].encode('utf-8')):
        return jsonify({"error": "Correo o contraseña incorrectos"}), 401

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

    return jsonify(usuarios), 200

@app.route('/upload', methods=['POST'])
@token_required
def upload_file(current_user):
    bd = BaseDeDatos()

    if 'file' not in request.files:
        return jsonify({"error": "No se ha enviado ningún archivo"}), 400

    codigos_usuario_str = request.args.get('codigos_usuario')
    if not codigos_usuario_str:
        return jsonify({"error": "No se ha enviado ningún código de usuario"}), 400
    codigos_usuario = codigos_usuario_str.split(',')
    codigos_usuario = [codigo.strip() for codigo in codigos_usuario]  # Limpiar espacios

    file = request.files['file']

    # Verificar que el archivo no esté vacío
    if file.filename == '':
        return jsonify({"error": "El archivo está vacío"}), 400

    # Procesar el archivo (por ejemplo, guardarlo o almacenarlo en base de datos)
    file_data = file.read()
    hash_sha256 = hashlib.sha256(file_data).hexdigest()

    bd.guardar_archivo(file.filename, file_data, current_user['id'], hash_sha256, codigos_usuario)

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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
