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

query_full_backup_first_file = """
MATCH (n:file)-[:in]->(:linked_instance)-[:in]->(dns:machine {dns:$name}) 
RETURN n.file_uuid as uuid, 
    n.creation_date as creation_date 
ORDER BY n.creation_date, n.file_uuid 
LIMIT 1
"""

query_next_backup = """
MATCH (n:file {file_uuid: $file_uuid})-[:in]->(:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MATCH (n_next:file)-[:in]->(:linked_instance)-[:in]->(dns) 
WHERE n_next.creation_date >= n.creation_date 
AND n_next.file_uuid <> n.file_uuid 
RETURN n_next.file_uuid as next_uuid, 
    n_next.creation_date as next, 
    n.creation_date as actual 
ORDER BY n_next.creation_date, n_next.file_uuid 
LIMIT 10
"""

query_startup = """
MERGE (dns:machine {dns:$name}) 
ON CREATE SET dns.creation_date= datetime() 
MERGE (li:linked_instance {instance_number:$instance_number})-[:in]->(dns) 
ON CREATE SET li.creation_date= datetime() 
MERGE (lt:log_type {name:'instance startup'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(li) 
"""

query_put_file = """
MERGE (dns:machine {dns:$name}) 
ON CREATE SET dns.creation_date= datetime() 
MERGE (li:linked_instance {instance_number:$instance_number})-[:in]->(dns) 
ON CREATE SET li.creation_date= datetime() 
MERGE (f:file {file_uuid: $file_uuid})-[:in]->(li) 
ON CREATE SET 
    f.creation_date= datetime(), 
    f.file= $file, 
    f.sha256 = $sha256 
MERGE (lt:log_type {name:'log file'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
"""

query_get_file = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (lt:log_type {name:'access file'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
RETURN f.file as file 
ORDER BY f.creation_date DESC 
LIMIT 2
"""

query_get_file_type = """
MATCH (ft:file_type)<-[:is]-(f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (lt:log_type {name:'access file type'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
RETURN f.file as file, ft.name as file_type, ft.ext as type_ext, ft.precision as type_precision 
ORDER BY f.creation_date DESC 
LIMIT 2
"""

query_get_file_infos = """
MATCH (ft:file_type)<-[:is]-(f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MATCH (su:system_user)<-[:owner]-(f)-[:mode]->(m:mode)
MATCH (proj:location)<-[:from]-(f)-[:in]->(loc:location)
RETURN f.file as file_name, 
    ft.name as file_type, 
    ft.ext as type_ext, 
    ft.precision as type_precision, 
    loc.location as location, 
    proj.location as proj, 
    m.numeric as mode, 
    su.name as user 
ORDER BY f.creation_date DESC 
LIMIT 2
"""

query_post_file_type = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}), 
(ft:file_type {name: $file_type}) 
MERGE (ft)<-[:is]-(f)
"""

query_post_file_location = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (loc:location {location: $location}) 
ON CREATE SET loc.creation_date= datetime() 
MERGE (loc)<-[:in]-(f)
"""

query_hooks = """
MATCH (li:linked_instance {instance_number: $instance_number}) 
MERGE (lt:log_type {name: "hook"}) 
ON CREATE SET lt.creation_date= datetime() 
MERGE (hook:hook {name: $hook_name}) 
ON CREATE SET hook.creation_date= datetime() 
MERGE (ip:ip {name: $ip}) 
ON CREATE SET ip.creation_date= datetime() 
CREATE (ip)<-[:from]-(log:log {creation_date: datetime(), data: $data})-[:is]->(lt) 
CREATE (li)<-[:log]-(log)-[:from]->(hook)
"""

query_logs = """
MATCH (li:linked_instance {instance_number: $instance_number}) 
MERGE (lt:log_type {name: "logs"}) 
ON CREATE SET lt.creation_date= datetime() 
MERGE (ip:ip {name: $ip}) 
ON CREATE SET ip.creation_date= datetime() 
CREATE (ip)<-[:from]-(log:log {creation_date: datetime(), data: $data})-[:is]->(lt) 
CREATE (li)<-[:log]-(log)
RETURN ip.status as status
"""

query_post_file_infos = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (loc:location {location: $location}) 
ON CREATE SET loc.creation_date= datetime() 
MERGE (pwd:location {location: $pwd}) 
ON CREATE SET pwd.creation_date= datetime() 
MERGE (machine:machine {name: $machine}) 
ON CREATE SET machine.creation_date= datetime() 
MERGE (user:system_user {name: $user, machine: $machine}) 
ON CREATE SET user.creation_date= datetime() 
MERGE (owner:system_user {name: $owner, machine: $machine}) 
ON CREATE SET owner.creation_date= datetime() 
MERGE (mode:mode {mode: $mode}) 
ON CREATE SET mode.creation_date= datetime() 
MERGE (loc)<-[:in]-(f) 
MERGE (mode)<-[:mode]-(f) 
MERGE (owner)<-[:owner]-(f) 
MERGE (user)<-[:by]-(f) 
MERGE (pwd)<-[:from]-(f) 
MERGE (machine)<-[:in]-(owner) 
MERGE (machine)<-[:in]-(user) 
SET f.size = $size
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
    with open(app.config["UPLOAD_FOLDER"] + '/' + uuid, 'rb') as f:
        digest = hashlib.file_digest(f, digest_name)
        return digest.hexdigest()
    return ""

@app.route('/<uuid1>/<uuid2>/diff', methods = ['GET'])
def route_file_diff(uuid1, uuid2):
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
def route_file_sha256(uuid):
    data = {'uuid': uuid}
    data['sha256'] = digest(uuid, "sha256")
    return jsonify(data)

@app.route('/<uuid>/sha512', methods = ['GET'])
def route_file_sha512(uuid):
    data = {'uuid': uuid}
    data['sha512'] = digest(uuid, "sha512")
    return jsonify(data)

@app.route('/<uuid>/type', methods = ['POST'])
def route_file_post_type(uuid):
    data = {'uuid': uuid}

    if ((len(request.values) != 0) and ('file_type' in request.values) and (request.values['file_type'] != "")
        and ('token' in request.values) and (request.values['token'] == config['token'])):
        results = config['driver'].execute_query(
            query_post_file_type,
            name= os.environ['INSTANCE_DNS'],
            instance_number= instance_number,
            file_uuid= uuid,
            file_type= request.values['file_type']
        ).summary

        data['result_available_after'] = results.result_available_after
        app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    else :
        app.logger.info("No file_type")

    return jsonify(data)

@app.route('/<uuid>/location', methods = ['POST'])
def route_file_post_location(uuid):
    data = {'uuid': uuid}

    if ((len(request.values) != 0) and ('location' in request.values) and (request.values['location'] != "")
        and ('token' in request.values) and (request.values['token'] == config['token'])):
        results = config['driver'].execute_query(
            query_post_file_location,
            name= os.environ['INSTANCE_DNS'],
            instance_number= instance_number,
            file_uuid= uuid,
            location= request.values['location']
        ).summary

        data['result_available_after'] = results.result_available_after
        app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    else :
        app.logger.info("No location")

    return jsonify(data)

@app.route('/<uuid>/type', methods = ['GET'])
def route_file_get_type(uuid):
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

@app.route('/full_backup_first_file', methods = ['POST'])
def route_file_get_full_backup_first_file():
    data = {}
    if ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):
        results = config['driver'].execute_query(
            query_full_backup_first_file,
            name= os.environ['INSTANCE_DNS'],
            instance_number= instance_number
        )

        for result in results.records:
            data_line = result.data()
            data['uuid'] = data_line['uuid']
            #data['next'] = data_line['next']
            #data['actual'] = data_line['actual']
            break

    #app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return jsonify(data)

@app.route('/<uuid>/next_backup', methods = ['POST'])
def route_file_get_next_backup(uuid):
    data = {'uuid': uuid}
    if ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):

        results = config['driver'].execute_query(
            query_next_backup,
            name= os.environ['INSTANCE_DNS'],
            instance_number= instance_number,
            file_uuid= uuid
        )

        for result in results.records:
            data_line = result.data()
            data['next_uuid'] = data_line['next_uuid']
            #data['next'] = data_line['next']
            #data['actual'] = data_line['actual']
            break

        #app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
        return jsonify(data)

@app.route('/<uuid>/infos', methods = ['POST'])
def route_file_post_infos(uuid):
    data = {'uuid': uuid}

    if ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):
        if ((len(request.values) != 0) and ('location' in request.values) and (request.values['location'] != "")):
            results = config['driver'].execute_query(
                query_post_file_infos,
                name= os.environ['INSTANCE_DNS'],
                instance_number= instance_number,
                file_uuid= uuid,
                owner= request.values['owner'],
                mode= request.values['mode'],
                user= request.values['user'],
                pwd= request.values['pwd'],
                size= request.values['size'],
                location= request.values['location'],
                machine= request.values['machine']
            ).summary

            data['result_available_after'] = results.result_available_after
            app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)

        else :
            results = config['driver'].execute_query(
                query_get_file_infos,
                name= os.environ['INSTANCE_DNS'],
                instance_number= instance_number,
                file_uuid= uuid
            )

            for result in results.records:
                data_line = result.data()
                data['file_name'] = data_line['file_name']
                data['type_precision'] = data_line['type_precision']
                data['type_ext'] = data_line['type_ext']
                data['file_type'] = data_line['file_type']
                data['location'] = data_line['location']
                data['proj'] = data_line['proj']
                data['mode'] = data_line['mode']
                data['user'] = data_line['user']
                break

    else :
        data["error"] = "no token"

    return jsonify(data)

@app.route('/<uuid>/execute_query', methods = ['POST'])
def route_execute_query(uuid):
    app.logger.info("here")
    try :
        __uuid = UUID(uuid, version=1)
    except TypeError:
        abort(404)
    except ValueError:
        abort(404)

    data = {}
    if ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):
        file_name = neo4_get_file(config, str(__uuid))

        query = ""
        with open(app.config["UPLOAD_FOLDER"] + '/' + str(__uuid), 'rt') as f :
            query = f.read()

        if (len(query) == 0):
            data['error'] == 'not found'
            return jsonify(data)

        data['records'], summary, data['keys'] = config['driver'].execute_query(
            query
        )

        app.logger.info("summary : %s ms", summary.result_available_after)
        app.logger.info("keys : %s", data['keys'])
        #app.logger.info("summary : %s ms", data['records'].summary.result_available_after)
        return jsonify(data)

    elif ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):
        app.logger.info("token error")
        data['error'] == 'token error'
        return jsonify(data)

    abort(404)
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

def neo4_log_file(config, file, file_uuid, sha256):
    results = config['driver'].execute_query(
        query_put_file,
        name= os.environ['INSTANCE_DNS'],
        instance_number= instance_number,
        file= file,
        file_uuid= file_uuid,
        sha256=sha256
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

@app.route('/<hook_name>/hooks', methods=['GET', 'POST'])
def route_hooks(hook_name):
    data = {'hook_name': hook_name}
    received_data = "not a json"
    if (request.is_json):
        received_data =  ", ".join(request.json)
    #data['len(request)'] = len(request.values)
    #for value in request.values:
    #    data[value] = request.values[value]
    app.logger.info("hook : %s - %s", hook_name, ", ".join(request.values))
    results = config['driver'].execute_query(
        query_hooks,
        name= os.environ['INSTANCE_DNS'],
        instance_number= instance_number,
        hook_name= hook_name,
        ip= request.remote_addr,
        #data= ", ".join(request.values)
        data=received_data
    ).summary
    return jsonify(data)

def logging(request):
    if (('driver' not in config) or (('driver' in config) and (config['driver'] == None))) :
        return True

    results = config['driver'].execute_query(
        query_logs,
        name= os.environ['INSTANCE_DNS'],
        instance_number= instance_number,
        ip= request.remote_addr,
        data= ", ".join(request.values)
    )

    for result in results.records:
        data = result.data()
        if (('status' in data) and (data['status'] == 'banned')) :
            return False
    return True

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
    if not(logging(request)):
        abort(404)

    if is_ready(config) : #is_ready
        if ( verify_post_file(request) and (request.values['token'] == config['token'] ) ): #verify_post_file
            file = request.files['file']
            filename = secure_filename(file.filename)
            try :
                data = {}
                file_uuid = str(uuid.uuid1())
                data['uuid'] = file_uuid
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_uuid))
                archive_cmd = "/usr/bin/sudo /scripts/chown_archive.sh %s" % (file_uuid)
                logs = os.system(archive_cmd)
                data['sha256'] = digest(data['uuid'], "sha256")
                app.logger.info("summary : %s", archive_cmd)
                neo4_log_file(config, filename, file_uuid, data['sha256'])
                #return render_template('simple_uploader.html', title='Upload file')
                return jsonify(data)

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
        app.run(host='::', port='443') #debug=True
        #app.run(host='0.0.0.0', port='443') #debug=True
        app.logger.info("!!! no certs found !!!", instance_number)
    else:
        app.run(host='::', port='443', ssl_context=context) #debug=True
        #app.run(host='0.0.0.0', port='443', ssl_context=context) #debug=True
    finally :
        app.logger.info("instance name : %s", instance_number)
