from flask import (
    Flask, jsonify, flash, request, redirect, url_for,
    render_template, send_file, send_from_directory, make_response,
    abort
    )
from werkzeug.utils import secure_filename
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.exceptions import InvalidKey
import os
import sys
import json

UPLOAD_FOLDER = '/uploaded_files'
#ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'exe', 'ipynb', 'zip', 'tar', 'sh', ''}

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(32)  # Used for session.
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def save_config():
    data = {}
    data['salt'] = config['salt'].hex() #8*16=128
    data['iv'] = config['iv'].hex() #8*16=128
    #config['token'] = os.urandom(32).hex() #8*32=256

    config_file = open('/config/config.json', mode='wt')
    json.dump(config, config_file)
    config_file.close()



#argon2 et aes config
if not(os.path.exists('/config/config.json')):
    config = {}
    config['salt'] = os.urandom(16).hex() #8*16=128
    config['iv'] = os.urandom(16).hex() #8*16=128
    config['token'] = "" #os.urandom(32).hex() #8*32=256
    config_file = open('/config/config.json', mode='wt')
    json.dump(config, config_file)
    config_file.close()

config_file = open('/config/config.json', mode='rt')
config = json.load(config_file)
config_file.close()

config['salt'] = bytes.fromhex(config['salt'])
config['iv'] = bytes.fromhex(config['iv'])
#config['token'] = "" #TO_REMOVE

def derive(password): #b"my great password"
    kdf = Argon2id(
        salt=config['salt'],
        length=32,
        iterations=1,
        lanes=4,
        memory_cost=64 * 1024,
        ad=None,
        secret=None
    )
    return kdf.derive(password) #key

def verify(password, key): #b"my great password"
    kdf = Argon2id(
        salt=config['salt'],
        length=32,
        iterations=1,
        lanes=4,
        memory_cost=64 * 1024,
        ad=None,
        secret=None
    )
    test = False
    try :
        kdf.verify(password, key)
        test = True
    except InvalidKey:
        test = False
    return test

def encrypt(message, key, iv): #b"a secret message"
    cypher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cypher.encryptor()
    return encryptor.update(message) + encryptor.finalize() #encrypted_message

def decrypt(encrypted_message, key, iv):
    cypher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cypher.decryptor()
    return decryptor.update(encrypted_message) + decryptor.finalize() #message

@app.route('/', methods=['GET'])
def route_upload_file_get():
    if (config['token'] != "") :
        return render_template('simple_uploader.html', title='Upload file')
    else :
        if ('key' in config) :
            return render_template('ask_token.html', title='Ask token')
        else :
            return render_template('ask_password.html', title='Ask password')

@app.route('/config', methods = ['GET', 'POST'])
def route_download_config():
    if ( (len(request.values) != 0) and ('password' in request.values) ):
        data = {}
        if 'password' in config :
            data['password'] = config['password']
        #data['token'] = config['token']
        #data['token'] = b"a secret message".hex() ... 8*16
        #data['token'] = b"tempo".zfill(16).hex()
        data['token'] = config['token']
        data['sizeof_token'] = sys.getsizeof(config['token'])

        config['password_b'] = bytes(request.values['password'], 'utf-8')
        try :
            config['derived'] = derive(config['password_b'])
        finally :
            pass

        try :
            #config['encrypted_token'] = encrypt(bytes(config['token'],'utf-8'), config['derived'], config['iv'])
            config['encrypted_token'] = encrypt(b"tempo".zfill(16), config['derived'], config['iv'])
        finally :
            pass

        try :
            config['decrypted_token'] = decrypt(config['encrypted_token'], config['derived'], config['iv'])
        finally :
            pass

        #if 'key' in config:
        #    data['verify'] = verify(bytes(config['password'], 'utf-8'), config['key'])
        #    data['verify'] = verify(bytes(config['password'], 'utf-8'), config['key'])
        #    data['verify_empty_pwd'] = verify(b"", config['key'])
        #    data['verify_wrong_pwd'] = verify(b"pas le bon password", config['key'])

        for dict_key in ['key', 'iv', 'salt', 'password_b', 'derived', 'encrypted_token', 'decrypted_token']:
            if dict_key in config :
                try :
                    data[dict_key] = config[dict_key].hex()
                finally:
                    pass

        return jsonify(data)

    else:
        return render_template('ask_password.html', title='Ask password')


@app.route('/<name>', methods = ['GET'])
def route_download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name, as_attachment=True, download_name=name)

@app.route('/', methods=['POST'])
def route_upload_file_post():
    if (config['token'] != "") :
        if ( (len(request.values) != 0) and ('token' in request.values) ):
            if (request.values['token'] != config['token']) :
                return render_template('simple_uploader.html', title='Upload file - wrong token')

            else :
                if ('file' in request.files) :
                    file = request.files['file']
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    return render_template('simple_uploader.html', title='Upload file')

                else :
                    return render_template('simple_uploader.html', title='Upload file')

        else :
            return render_template('simple_uploader.html', title='Upload file')

    else :
        if ('key' in config):
            #if ( (len(request.values) != 0) and ('token' in request.values) and (request.values['token'] != "") ):
            if ( 'token' in request.values ):
                config['token'] = request.values['token']
                return render_template('simple_uploader.html', title='Upload file')
            else:
                return render_template('ask_token.html', title='Ask token')
        else :
            if ( (len(request.values) != 0) and ('password' in request.values) and (request.values['password'] != "") ):
                config['key'] = derive(bytes(request.values['password'], 'utf-8'))
                return render_template('ask_token.html', title='Ask token')

            else:
                return render_template('ask_password.html', title='Ask password')

if __name__ == "__main__":
    app.run(host='0.0.0.0:443') #debug=True, ssl_context="adhoc", ... to_review !!!
