from flask import (
    Flask, jsonify, flash, request, redirect, url_for,
    render_template, send_file, send_from_directory, make_response,
    abort
    )
from werkzeug.utils import secure_filename
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
import os
import sys
import json
import math

#Errors :
from cryptography.exceptions import InvalidKey
from json.decoder import JSONDecodeError

UPLOAD_FOLDER = '/uploaded_files'
#ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'exe', 'ipynb', 'zip', 'tar', 'sh', ''}

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(32)  # Used for session.
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def save_config_file(config):
    token = ''
    if 'key' in config :
        b_token = bytes(config['token'], 'utf-8')
        token = encrypt(
                b_token.ljust(math.trunc(len(b_token) / 16) + 16, b'\00'), #.zfill(16),
                config['key'],
                config['iv']
            ).hex()

    data = {
        'salt' : config['salt'].hex(), #8*16=128
        'iv' : config['iv'].hex(), #8*16=128
        'token_encrypted' : token,
        'neo4j' : {
            'instance' : config['neo4j']['instance'],
            'login' : config['neo4j']['login'],
            'password_encrypted' : config['neo4j']['password'] #TO_REVIEW
            }
        }

    with open('/config/config.json', mode='wt') as config_file:
        json.dump(data, config_file)
    return None

def open_config_file(key=b""):
    data = {}
    with open('/config/config.json', mode='rt') as config_file:
        try:
            tempo = json.load(config_file)
        finally :
            pass

    token = ''
    if key :
        token = decrypt(bytes.fromhex(tempo['token_encrypted']), key, bytes.fromhex(tempo['iv'])).rstrip(b'\x00').decode('utf-8')

    return {
        'salt': bytes.fromhex(tempo['salt']),
        'iv': bytes.fromhex(tempo['iv']),
        'token': token, #TO_REMOVE
        'neo4j': {
            'instance': tempo['neo4j']['instance'],
            'login': tempo['neo4j']['login'],
            'password': tempo['neo4j']['password_encrypted']
            }
        }

#argon2 et aes config
if not(os.path.exists('/config/config.json')):
    save_config_file({
        'salt' : os.urandom(16), #8*16=128
        'iv' : os.urandom(16), #8*16=128
        'token' : '', #os.urandom(32).hex() #8*32=256
        'neo4j': {
            'instance': '',
            'login': '',
            'password': ''
        }
    })

config = open_config_file()

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

@app.route('/config.json', methods = ['GET', 'POST'])
def route_download_config():
    if ( (len(request.values) != 0) and ('password' in request.values) ):
        data = {}

        try :
            #password_b = bytes(request.values['password'], 'utf-8')
            #key = derive(password_b)
            tempo = open_config_file(config['key'])

            data = {
                'token' : tempo['token']
                }

        except KeyError:
            pass
        finally :
            pass

        #for dict_key in ['key', 'iv', 'salt', 'password_b', 'derived', 'encrypted_token', 'decrypted_token']:
        #    if dict_key in config :
        #        try :
        #            data[dict_key] = config[dict_key].hex()
        #        except KeyError:
        #            pass
        #        finally:
        #            pass

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
                save_config_file(config)
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
