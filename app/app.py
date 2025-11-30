#!/usr/local/bin/python
from flask import (
    Flask, jsonify, flash, request, redirect, url_for,
    render_template, send_file, send_from_directory, make_response,
    abort
    )
from werkzeug.utils import secure_filename

from neo4j import GraphDatabase, RoutingControl
from neo4j.exceptions import DriverError, Neo4jError

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

import os
import sys
import json
import math
import ssl
import uuid
from uuid import UUID
import hashlib

#Errors :
from cryptography.exceptions import InvalidKey
from json.decoder import JSONDecodeError

UPLOAD_FOLDER = '/uploaded_files'
#ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'exe', 'ipynb', 'zip', 'tar', 'sh', ''}

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(32)  # Used for session.
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

instance_number = os.urandom(32).hex()

query_startup = """
MERGE (dns:dns {name:$name}) 
ON CREATE SET dns.creation_date= datetime() 
MERGE (li:linked_instance {instance_number:$instance_number})-[:in]->(dns) 
ON CREATE SET li.creation_date= datetime() 
MERGE (lt:log_type {name:'instance startup'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(li) 
"""

query_file = """
MERGE (dns:dns {name:$name}) 
ON CREATE SET dns.creation_date= datetime() 
MERGE (li:linked_instance {instance_number:$instance_number})-[:in]->(dns) 
ON CREATE SET li.creation_date= datetime() 
MERGE (f:file {file_uuid: $file_uuid})-[:in]->(li) 
ON CREATE SET 
    f.creation_date= datetime(), 
    f.file= $file 
MERGE (lt:log_type {name:'log file'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
"""

query_get_file = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:dns {name:$name}) 
MERGE (lt:log_type {name:'access file'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
RETURN f.file as file 
ORDER BY f.creation_date DESC 
LIMIT 2
"""

query_get_file_type = """
MATCH (ft:file_type)<-[:is]-(f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:dns {name:$name}) 
MERGE (lt:log_type {name:'access file type'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
RETURN f.file as file, ft.name as file_type, ft.ext as type_ext, ft.precision as type_precision 
ORDER BY f.creation_date DESC 
LIMIT 2
"""

def save_config_file(config):
    token = ''
    neo4j_password = ''

    if 'key' in config :
        b_token = bytes(config['token'], 'utf-8')
        token = encrypt(
                b_token.ljust(math.trunc(len(b_token) / 16) + 16, b'\00'), #.zfill(16),
                config['key'],
                config['iv']
            ).hex()

        if (config['neo4j']['password'] != ""):
            b_neo4j_password = bytes(config['neo4j']['password'], 'utf-8')
            neo4j_password = encrypt(
                    b_neo4j_password.ljust(math.trunc(len(b_neo4j_password) / 16) + 16, b'\00'),
                    config['key'],
                    config['iv']
                ).hex()

    data = {
        'salt' : config['salt'].hex(),
        'iv' : config['iv'].hex(),
        'token_encrypted' : token,
        'neo4j' : {
            'instance' : config['neo4j']['instance'],
            'login' : config['neo4j']['login'],
            'password_encrypted' : neo4j_password,
            'scheme': config['neo4j']['scheme'],
            'port': config['neo4j']['port']
            }
        }

    with open('/config/config.json', mode='wt') as config_file:
        json.dump(data, config_file, indent=4)
    return None

def open_config_file(key=b""):
    data = {}
    with open('/config/config.json', mode='rt') as config_file:
        try:
            tempo = json.load(config_file)
        finally :
            pass

    token = ''
    password = ''
    if key :
        token = decrypt(
                bytes.fromhex(tempo['token_encrypted']),
                key,
                bytes.fromhex(tempo['iv'])
            ).rstrip(b'\x00').decode('utf-8')

        if (tempo['neo4j']['password_encrypted'] != '') :
            password = decrypt(
                    bytes.fromhex(tempo['neo4j']['password_encrypted']),
                    key,
                    bytes.fromhex(tempo['iv'])
                ).rstrip(b'\x00').decode('utf-8')

    return {
        'salt': bytes.fromhex(tempo['salt']),
        'iv': bytes.fromhex(tempo['iv']),
        'token': token, #TO_REMOVE
        'neo4j': {
            'instance': tempo['neo4j']['instance'],
            'login': tempo['neo4j']['login'],
            'password': password,
            'scheme': tempo['neo4j']['scheme'],
            'port': tempo['neo4j']['port']
            }
        }

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

def digest(uuid, digest_name):
    data = {'uuid': uuid}
    with open(app.config["UPLOAD_FOLDER"] + '/' + uuid, 'rb') as f:
        digest = hashlib.file_digest(f, digest_name)
        data[digest_name] = digest.hexdigest()
        return data
    return data

@app.route('/<uuid1>/<uuid2>/diff', methods = ['GET'])
def file_diff(uuid1, uuid2):
    read_block_size = 512
    data = {'uuid1': uuid1, 'uuid2': uuid2, 'identical' : False}
    with open(app.config["UPLOAD_FOLDER"] + '/' + uuid1, 'rb') as f1:
        with open(app.config["UPLOAD_FOLDER"] + '/' + uuid2, 'rb') as f2 :
            __end__ = False
            data['identical'] = True
            while not(__end__):
                data1 = f1.read(read_block_size)
                data2 = f2.read(read_block_size)
                if (len(data1) == 0):
                    __end__ = True
                elif (data1 == data2):
                    pass
                else :
                    data['identical'] = False
                    __end__ = True
            return jsonify(data)
    return jsonify(data)

@app.route('/<uuid>/sha256', methods = ['GET'])
def file_sha256(uuid):
    return jsonify(digest(uuid, "sha256"))

@app.route('/<uuid>/sha512', methods = ['GET'])
def file_sha512(uuid):
    return jsonify(digest(uuid, "sha512"))

@app.route('/<uuid>/type', methods = ['GET'])
def file_type(uuid):
    data = {'uuid': uuid}
    results = config['driver'].execute_query(
        query_get_file_type,
        name= os.environ['INSTANCE_DNS'],
        instance_number= instance_number,
        file_uuid= uuid
    )

    for result in results.records:
        data_line = result.data()
        data['type_precision'] = data_line['type_precision']
        data['type_ext'] = data_line['type_ext']
        data['file_type'] = data_line['file_type']
        break

    #app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return jsonify(data)

@app.route('/<uuid>', methods = ['GET'])
def route_download_file(uuid):
    try :
        __uuid = UUID(uuid, version=1)
    except TypeError:
        abort(404)
    except ValueError:
        abort(404)

    file_name = neo4_get_file(config, str(__uuid))
    return send_from_directory(app.config["UPLOAD_FOLDER"], uuid, as_attachment=True, download_name=file_name)

def is_ready(config):
    return (('key' in config)
        and ('neo4j' in config)
        and ('token' in config) and (config['token'] != "")
        and ('instance' in config['neo4j']) and (config['neo4j']['instance'] != '')
    )

def is_wait_for_neo4j_credential(config):
    return (('neo4j' in config)
        and ('key' in config)
        and ('token' in config) and (config['token'] != "")
        and ('instance' in config['neo4j']) and (config['neo4j']['instance'] == '')
    )

def is_wait_for_token(config):
    return (('key' in config)
        and ('token' in config)
        and (config['token'] == "")
    )

def is_wait_for_password(config):
    return ( ('key' not in config) )

def verify_post_neo4j_credential(request):
    return (
        (len(request.values) != 0)
        and ('instance' in request.values)
        and (request.values['instance'] != "")
        and ('login' in request.values)
        and (request.values['login'] != "")
        and ('password' in request.values)
        and (request.values['password'] != "")
    )

def verify_post_file(request):
    return ((len(request.files) != 0) and ('file' in request.files)
        and (len(request.values) != 0)
        and ('token' in request.values)
    )

def neo4_log_file(config, file, file_uuid):
    results = config['driver'].execute_query(
        query_file,
        name= os.environ['INSTANCE_DNS'],
        instance_number= instance_number,
        file= file,
        file_uuid= file_uuid
    ).summary
    app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return True

def neo4_get_file(config, file_uuid):
    results = config['driver'].execute_query(
        query_get_file,
        name= os.environ['INSTANCE_DNS'],
        instance_number= instance_number,
        file_uuid= file_uuid
    )

    for result in results.records:
        data = result.data()
        break #TO_REVIEW

    #app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return data['file']

def neo4j_connection(config):
    app.logger.info("set config file : %s", config['neo4j']['instance'])
    uri = f"{config['neo4j']['scheme']}://{config['neo4j']['instance']}:{config['neo4j']['port']}"
    config['driver'] = GraphDatabase.driver(uri, auth=(config['neo4j']['login'], config['neo4j']['password']))
    results = config['driver'].execute_query(
        query_startup,
        name= os.environ['INSTANCE_DNS'],
        instance_number= instance_number
    ).summary
    app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return True

@app.route('/hooks/<id>', methods=['GET', 'POST'])
def route_hook(id):
    data = {'ok': 'ok'}
    app.logger.info("hook : %s", id)
    return jsonify(data)


def install_config(config):
    query = ""
    with open("/app/cypher/file_types.cypher", 'rt') as f :
        query = f.read()

    if (len(query) == 0):
        return False

    results = config['driver'].execute_query(
        query
    ).summary

    app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return True

@app.route('/', methods=['GET', 'POST'])
def route_upload_file_get():
    if is_ready(config) : #is_ready
        if ( verify_post_file(request) and (request.values['token'] == config['token'] ) ): #verify_post_file
            file = request.files['file']
            filename = secure_filename(file.filename)
            try :
                file_uuid = str(uuid.uuid1())
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_uuid))
                archive_cmd = "/usr/bin/sudo /scripts/chown_archive.sh %s" % (file_uuid)
                logs = os.system(archive_cmd)
                app.logger.info("summary : %s", archive_cmd)
                neo4_log_file(config, filename, file_uuid)
                return render_template('simple_uploader.html', title='Upload file')
            except PermissionError:
                return render_template('simple_uploader.html', title='Upload file - permission error')

        elif (request.method == 'POST'):
            if ('token' not in request.values):
                return render_template('simple_uploader.html', title='Upload file - missing token')

            elif (('token' in request.values) and (request.values['token'] != config['token'])):
                return render_template('simple_uploader.html', title='Upload file - wrong token')

            elif ('file' not in request.files):
                return render_template('simple_uploader.html', title='Upload file - missing file')

            else :
                return render_template('simple_uploader.html', title='Upload file - errors in information')

        else :
            return render_template('simple_uploader.html', title='Upload file')

    elif is_wait_for_neo4j_credential(config): #is_wait_for_neo4j_credential
        if verify_post_neo4j_credential(request): #verify_post_neo4j_credential
            config['neo4j']['instance'] = request.values['instance']
            config['neo4j']['login'] = request.values['login']
            config['neo4j']['password'] = request.values['password']
            save_config_file(config)

            if neo4j_connection(config):
                if install_config(config):
                    return render_template('simple_uploader.html', title='Upload file - database connected')
                else :
                    return render_template('simple_uploader.html', title='Upload file - database configuration failed')
            else :
                return render_template('simple_uploader.html', title='Upload file - connection failed')

        elif (request.method == 'POST'):
            return render_template('ask_neo4j_password.html', title='Ask Neo4J credential - errors in information')

        else :
            return render_template('ask_neo4j_password.html', title='Ask Neo4J credential')

    elif is_wait_for_token(config) : #is_wait_for_token
        if ( (len(request.values) != 0) and ('token' in request.values) and (request.values['token'] != "") ):
            config['token'] = request.values['token']
            save_config_file(config)
            return render_template('ask_neo4j_password.html', title='Ask Neo4J credential')

        elif (request.method == 'POST'):
            return render_template('ask_token.html', title='Ask token - empty token')

        else:
            return render_template('ask_token.html', title='Ask token')

    elif is_wait_for_password(config): #is_wait_for_password
        if ( (len(request.values) != 0) and ('password' in request.values) and (request.values['password'] != "") ):
            config['key'] = derive(bytes(request.values['password'], 'utf-8'))

            if (config['neo4j']['instance'] != ''): #conf.json file already exists at boot
                tempo = open_config_file(config['key'])
                config['token'] = tempo['token']
                config['neo4j']['password'] = tempo['neo4j']['password']

                if neo4j_connection(config):
                    if install_config(config):
                        return render_template('simple_uploader.html', title='Upload file - database connected')
                    else :
                        return render_template('simple_uploader.html', title='Upload file - database configuration failed')

                else :
                    return render_template('simple_uploader.html', title='Upload file - connection failed')

            else :
                return render_template('ask_token.html', title='Ask token')

        elif (request.method == 'POST'):
            return render_template('ask_password.html', title='Ask password - empty password not allowed')

        else :
            return render_template('ask_password.html', title='Ask password')

    else : #strange case
        return render_template('ask_password.html', title='Ask password - should not happen')

#argon2 et aes config
if not(os.path.exists('/config/config.json')):
    save_config_file({
        'salt' : os.urandom(16), #8*16=128
        'iv' : os.urandom(16), #8*16=128
        'token' : '', #os.urandom(32).hex() #8*32=256
        'neo4j': {
            'instance': '',
            'login': '',
            'password': '',
            'scheme': 'neo4j+s',
            'port': '7687'
        }
    })

config = open_config_file()
config['driver'] = None

#this part is for flask server config not used used by gunicorn
if __name__ == "__main__":
    try :
        dns_name = os.environ['INSTANCE_DNS']
        print("dns_name : %s" % (dns_name))
        logs = os.system("/usr/bin/sudo /scripts/gen_certs.sh %s" % (dns_name))
    finally:
        print(logs)

    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain("/certs/fullchain.pem", "/certs/privkey.pem")
    except FileNotFoundError:
        app.run(host='0.0.0.0', port='443') #debug=True
        app.logger.info("!!! no certs found !!!", instance_number)
    else:
        app.run(host='0.0.0.0', port='443', ssl_context=context) #debug=True
    finally :
        app.logger.info("instance name : %s", instance_number)
