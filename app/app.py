#!/usr/local/bin/python
from flask import (
    Flask, jsonify, flash, request, redirect, url_for,
    render_template, send_file, send_from_directory, make_response,
    abort, Response
    )
from werkzeug.utils import secure_filename

from neo4j import GraphDatabase, RoutingControl
from neo4j.exceptions import DriverError, Neo4jError

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from fido2.webauthn import PublicKeyCredentialRpEntity, PublicKeyCredentialUserEntity, AttestedCredentialData
from fido2.server import Fido2Server
import fido2.features

import os
import sys
import json
import math
import ssl
#from ssl import Purpose
from uuid import uuid4
import hashlib
import base64
import logging
import requests

import string
import random

#Errors :
from cryptography.exceptions import InvalidKey
from json.decoder import JSONDecodeError

UPLOAD_FOLDER = '/uploaded_files'
#ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'exe', 'ipynb', 'zip', 'tar', 'sh', ''}

app = Flask(__name__, static_url_path="/static/", static_folder="/app/static/")
app.secret_key = os.urandom(32)  # Used for session.
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['NPM_FOLDER'] = '/npm'
app.config['FIDO2_SERVER'] = None
app.config['INSTANCE_NUMBER'] = os.urandom(32).hex()
app.config['INSTANCE_VERSION'] = os.environ['INSTANCE_VERSION']
app.config['INSTANCE_CONFIG'] = None
app.config['NEO4J_DRIVER'] = None
app.logger.setLevel(logging.INFO)

#fido2.features.webauthn_json_mapping.enabled = True #TO_REMOVE

query_data = """
MATCH (n1)-[r]->(n2) 
WHERE ( elementId(n1) = $node_id 
   OR   elementId(n2) = $node_id ) 
RETURN 
    type(r) as rel_type, 
    elementId(n1) as source, 
    type(r) as target, 
    type(r) as value, 
    coalesce(n1.name, "no name") as name_n1, 
    labels(n1) as label_n1, 
    type(r) as name_n2, 
    [type(r)] as label_n2 
LIMIT 20
UNION
MATCH (n1)-[r]->(n2) 
WHERE ( elementId(n1) = $node_id 
   OR   elementId(n2) = $node_id ) 
RETURN 
    type(r) as rel_type, 
    type(r) as source, 
    elementId(n2) as target, 
    type(r) as value, 
    type(r) as name_n1, 
    [type(r)] as label_n1, 
    coalesce(n2.name, "no name") as name_n2, 
    labels(n2) as label_n2 
LIMIT 20
"""

query_url = """
MATCH (n:link|web_page)
RETURN n.url as url, n.name as name
ORDER BY n.creation_date DESC
"""

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

query_sha256_oldest_file = """
MATCH (f:file {sha256: $sha256})-[:in]->(:linked_instance)-[:in]->(dns:machine {dns:$name})
RETURN f.file_uuid as uuid
ORDER BY f.creation_date ASC
LIMIT 1
"""

query_startup = """
MERGE (dns:machine {dns:$name}) 
ON CREATE SET dns.creation_date= datetime() 
MERGE (li:linked_instance {instance_number:$instance_number, instance_version:$instance_version})-[:in]->(dns) 
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

query_same_file = """
MATCH (f_identique:file {file_uuid: $uuid_identique})-[:in]->(:linked_instance)-[:in]->(:machine {dns:$name})
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(:linked_instance)-[:in]->(:machine {dns:$name})
CREATE (f)-[:same_as]->(f_identique)
"""

query_get_location = """
MATCH (loc:location {name: $location})<-[:in]-(content:file|location) 
RETURN content
"""

query_get_file = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (lt:log_type {name:'access file'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
RETURN f.name as file 
ORDER BY f.creation_date DESC 
LIMIT 1
"""

query_get_file_type = """
MATCH (ft:file_type)<-[:is]-(f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (lt:log_type {name:'access file type'}) 
ON CREATE SET lt.creation_date= datetime() 
CREATE (lt)<-[:is]-(l:log {creation_date:datetime()})-[:log]->(f) 
RETURN f.name as file, ft.name as file_type, ft.ext as type_ext, ft.precision as type_precision 
ORDER BY f.creation_date DESC 
LIMIT 2
"""

query_get_file_infos = """
MATCH (ft:file_type)<-[:is]-(f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MATCH (su:system_user)<-[:owner]-(f)-[:mode]->(m:mode) 
MATCH (proj:location)<-[:from]-(f)-[:in]->(loc:location) 
RETURN f.name as file_name, 
    ft.name as file_type, 
    ft.ext as type_ext, 
    ft.precision as type_precision, 
    loc.name as location, 
    proj.name as proj, 
    m.numeric as mode, 
    su.name as user 
ORDER BY f.creation_date DESC 
LIMIT 2
"""

query_banned_ip = """
MERGE (dns:machine {dns:$dns}) 
ON CREATE SET 
    dns.creation_date = datetime() 
MERGE (ip:ip {name: $ip}) 
ON CREATE SET 
    ip.creation_date = datetime(), 
    ip.status = "banned" 
ON MATCH SET 
    ip.status = coalesce( ip.status, "banned") 
MERGE (ip)-[:log_try_sni {sni:$to_dns}]->(dns)
"""

query_post_file_type = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}), 
(ft:file_type {name: $file_type}) 
MERGE (ft)<-[:is]-(f)
"""

query_post_file_location = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (loc:location {name: $location}) 
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
RETURN hook.logger as logger
"""

query_upload_token = """
MATCH (li:linked_instance {instance_number: $instance_number})-[:in]->(dns:machine {dns: $dns}) 
MATCH (ck:cookie {session_name: $session_name}) 
MATCH (ip:ip {name: $ip}) 
MERGE (t:upload_token {token: $upload_token}) 
ON CREATE SET t.creation_date= datetime(), t.state = 'validation' 
MERGE (li)<-[:for]-(t) 
MERGE (ck)<-[:from]-(t) 
MERGE (t)-[:for]->(ip) 
RETURN t.token as token
"""

query_token_register = """
MATCH (li:linked_instance {instance_number: $instance_number})-[:in]->(dns:machine {dns: $dns}) 
MATCH (li)<-[:to]-(ck:cookie {session_name: $session_name})-[:from]->(ip:ip {name: $ip}) 
MATCH (p:personne) 
MERGE (t:token) 
SET 
    ck.last_date= datetime(), 
    t.creation_date= datetime(), 
    t.state= 'challenge', 
    t.challenge = $challenge, 
    t.user_verification = $user_verification
"""

query_token_register_complete = """
MATCH (li:linked_instance {instance_number: $instance_number})-[:in]->(dns:machine {dns: $dns}) 
MATCH (li)<-[:to]-(ck:cookie {session_name: $session_name})-[:from]->(ip:ip {name: $ip}) 
MATCH (p:personne) 
MATCH (t:token) 
SET 
    ck.last_date= datetime(), 
    t.state='valid', 
    t.complete_date = datetime(), 
    t.credential_data = $credential_data
"""

query_token_auth = """
MATCH (li:linked_instance {instance_number: $instance_number})-[:in]->(dns:machine {dns: $dns}) 
MATCH (li)<-[:to]-(ck:cookie {session_name: $session_name})-[:from]->(ip:ip {name: $ip}) 
MATCH (p:personne) 
MATCH (t:token) 
SET 
    ck.last_date= datetime(), 
    ck.auth_challenge_date= datetime(), 
    ck.session_state= 'challenge', 
    ck.challenge = $challenge, 
    ck.user_verification = $user_verification
"""

query_token_auth_complete = """
MATCH (li:linked_instance {instance_number: $instance_number})-[:in]->(dns:machine {dns: $dns}) 
MATCH (li)<-[:to]-(ck:cookie {session_name: $session_name})-[:from]->(ip:ip {name: $ip}) 
MATCH (p:personne) 
MATCH (t:token) 
SET 
    ck.last_date= datetime(), 
    ck.auth_complete= datetime(), 
    ck.session_state= 'valid'
"""

query_set_cookie = """
MATCH (li:linked_instance {instance_number: $instance_number})-[:in]->(dns:machine {dns: $dns}) 
MATCH (ip:ip {name: $ip})
MERGE (ck:cookie {session_name: $session_name}) 
ON CREATE SET 
    ck.creation_date= datetime(), 
    ck.last_date= datetime(), 
    ck.session_state= 'opening' 
ON MATCH SET ck.last_date= datetime() 
MERGE (li)<-[:to]-(ck) 
MERGE (ck)-[:from]->(ip) 
"""

query_session_check = """
MATCH (li:linked_instance {instance_number: $instance_number})-[:in]->(dns:machine {dns: $dns}) 
OPTIONAL MATCH (t:token) 
OPTIONAL MATCH (p:personne) 
MERGE (ip:ip {name: $ip}) 
ON CREATE SET ip.creation_date= datetime() 
WITH ip, t, p, dns 
OPTIONAL MATCH (li)<-[:to]-(ck:cookie {session_name: $session_name})-[:from]->(ip) 
OPTIONAL MATCH (ip)<-[:for]-(ut:upload_token {token: $upload_token})-[:for]->(li_ut:linked_instance)-[:in]->(dns) 
WITH ip, ck, t, p, dns, ut 
OPTIONAL MATCH (ip)<-[:for]-(ut2:upload_token)
WITH ip, ck, t, p, dns, ut, count(ut2) as nb_upload_token 
RETURN 
    ip.status as ip_status, 
    ck.session_state as session_state, 
    ck.session_name as session_name, 
    ck.challenge as session_challenge, 
    ck.user_verification as session_user_verification, 
    t.challenge as token_challenge, 
    t.state as token_state, 
    t.credential_data as token_credential_data, 
    coalesce(t.user_verification, 'discouraged') as token_user_verification, 
    coalesce(t.authenticator_attachment, 'cross-platform') as token_authenticator_attachment, 
    p.user_id as user_id, 
    p.mail as user_name, 
    p.prenom as user_display_name, 
    dns.dns as dest_ut, 
    ip.name as source_ut, 
    ut.token as upload_token, 
    coalesce(ut.state, "no_token") as ut_state, 
    nb_upload_token
"""

query_post_file_infos = """
MATCH (f:file {file_uuid: $file_uuid})-[:in]->(li:linked_instance)-[:in]->(dns:machine {dns:$name}) 
MERGE (loc:location {name: $location}) 
ON CREATE SET loc.creation_date= datetime() 
MERGE (pwd:location {name: $pwd}) 
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

def is_ready(config):
    return (('key' in config)
        and ('neo4j' in config)
        and ('instance' in config['neo4j'])
        and (config['neo4j']['instance'] != '')
    )

def is_wait_for_neo4j_credential(config):
    return (('neo4j' in config)
        and ('key' in config)
        and ('instance' in config['neo4j'])
        and (config['neo4j']['instance'] == '')
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

def gen_rand(length = 64):
    chars = string.ascii_uppercase + string.ascii_lowercase + string.digits #to_review
    return ''.join(random.choice(chars) for _ in range(length))

def save_config_file(config):
    token = ''
    neo4j_password = ''

    if 'key' in config :
        b_token = bytes(config['token'], 'utf-8')
        token = encrypt(
                b_token.ljust(math.trunc(len(b_token) / 16) * 16 + 16, b'\00'), #.zfill(16),
                config['key'],
                config['iv']
            ).hex()

        if (config['neo4j']['password'] != ""):
            b_neo4j_password = bytes(config['neo4j']['password'], 'utf-8')
            neo4j_password = encrypt(
                    b_neo4j_password.ljust(math.trunc(len(b_neo4j_password) / 16) * 16 + 16, b'\00'),
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

def derive(config, password): #b"my great password"
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

def verify(config, password, key): #b"my great password"
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
    with open(app.config["UPLOAD_FOLDER"] + '/' + str(uuid), 'rb') as f:
        digest = hashlib.file_digest(f, digest_name)
        return digest.hexdigest()
    return ""

def neo4j_connection(config):
    app.logger.info("set config file : %s", config['neo4j']['instance'])
    uri = f"{config['neo4j']['scheme']}://{config['neo4j']['instance']}:{config['neo4j']['port']}"
    app.config['NEO4J_DRIVER'] = GraphDatabase.driver(uri, auth=(config['neo4j']['login'], config['neo4j']['password']))
    results = app.config['NEO4J_DRIVER'].execute_query(
        query_startup,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        instance_version= app.config['INSTANCE_VERSION']
    ).summary
    app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return True

def upload_file(request):
    uuid= uuid4()
    file = request.files['file']
    data = {
        'file_uuid': str(uuid),
        'file': secure_filename(file.filename),
        'name': os.environ['INSTANCE_DNS'],
        'instance_number': app.config['INSTANCE_NUMBER']
    }

    archive_cmd = "/usr/bin/sudo /scripts/chown_archive.sh %s" % (data['file_uuid'])
    app.logger.info("summary : %s", archive_cmd)

    file.save(os.path.join(app.config['UPLOAD_FOLDER'], data['file_uuid'] ))
    logs = os.system(archive_cmd)

    data['sha256'] = digest(uuid, "sha256")
    sha256_identique = sha256_oldest_file(data['sha256'])

    records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(query_put_file, parameters_ = data)
    app.logger.info("summary : %s - %s ms", summary.counters.nodes_created, summary.result_available_after)

    if (('uuid' in sha256_identique) and ( file_diff(data['file_uuid'], sha256_identique['uuid'])) ):
        data['uuid_identique']= sha256_identique['uuid']

        records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(query_same_file, parameters_ = data)
        app.logger.info("same_file - summary : %s - %s ms", summary.counters.nodes_created, summary.result_available_after)

    return data

def neo4j_get_file(config, file_uuid):
    records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(
        query_get_file,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        file_uuid= file_uuid
    )

    data = ""
    app.logger.info("summary : %s - %s ms", summary.counters.nodes_created, summary.result_available_after)
    for result in records:
        row = result.data()
        app.logger.info("%s" % (row))
        data = "%s" % (row['file'])
    return data

def get_urls():
    data = []
    records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(
        query_url,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER']
    )

    for result in records:
        data.append([result['url'], result['name']])

    return data

def install_config(config):
    for file in [
        '/app/cypher/file_types.cypher',
        '/app/cypher/modes.cypher',
        '/app/cypher/purges_upload_token_relations.cypher',
        '/app/cypher/purges_upload_token_nodes.cypher',
        '/app/cypher/purges_cookie_relations.cypher',
        '/app/cypher/purges_cookie_nodes.cypher',
        '/app/cypher/purges_ip_relations.cypher',
        '/app/cypher/purges_ip_nodes.cypher'
        ]:
        query = ""
        with open(file, 'rt') as f :
            query = f.read()

        if (len(query) == 0):
            return False

        results = app.config['NEO4J_DRIVER'].execute_query(
            query
        ).summary

        app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return True

def ssl_sni_check(ssl_socket, sni_name, ssl_ctx):
    if (sni_name != os.environ['INSTANCE_DNS']):
        app.logger.warning("... ssl_sni_check to %s from %s ..." % (sni_name, ssl_socket.getpeername() ))
        app.logger.info("    SSLContext compression : %s" % (ssl_socket.compression()))
        app.logger.info("    SSL Socket ALPN : %s" % ( ssl_socket.selected_alpn_protocol()))
        app.logger.info("    SSL Stats %s" % (context.session_stats()))

        if (app.config['NEO4J_DRIVER'] is None ):
            app.logger.warning(" !!! not logged in database !!! ")
            return ssl.ALERT_DESCRIPTION_HANDSHAKE_FAILURE

        if sni_name is None :
            sni_name = "NULL"

        results = app.config['NEO4J_DRIVER'].execute_query(
            query_banned_ip,
            dns= os.environ['INSTANCE_DNS'],
            instance_number= app.config['INSTANCE_NUMBER'],
            ip= ssl_socket.getpeername()[0],
            to_dns= sni_name
        )

        return ssl.ALERT_DESCRIPTION_UNRECOGNIZED_NAME
        #return ssl.ALERT_DESCRIPTION_HANDSHAKE_FAILURE
        #return ssl.ALERT_DESCRIPTION_INTERNAL_ERROR

    app.logger.info("... ssl_sni_check to %s from %s ..." % (sni_name, ssl_socket.getpeername() ))
    app.logger.info("    SSLContext compression : %s" % (ssl_socket.compression()))
    app.logger.info("    SSL Socket ALPN : %s" % ( ssl_socket.selected_alpn_protocol()))
    app.logger.info("    SSL Stats %s" % (context.session_stats()))
    return None

def session_check(request):
    instance_state = "not_defined"
    if is_ready(app.config['INSTANCE_CONFIG']):
        instance_state = "ready"
    elif is_wait_for_neo4j_credential(app.config['INSTANCE_CONFIG']):
        instance_state = "wait_for_neo4j_credential"
    elif is_wait_for_password(app.config['INSTANCE_CONFIG']):
        instance_state = "wait_for_password"
    else :
        instance_state = "booting"

    session_data = {}

    if (len(request.values) > 0) and ('token' in request.values) and (request.values['token']):
        session_data['upload_token'] = {'token': request.values['token']}
    else :
        session_data['upload_token'] = {'token': None}

    session_data['instance_config'] = {'state': instance_state}
    session_data['ip'] = {'name': request.remote_addr}
    session_data['session'] = {'name': request.cookies.get('session_name')}
    session_data['token'] = {}
    session_data['user'] = {}
    session_data['request'] = {
        'user_agent': {
            'string': request.user_agent.string,
            'platform': request.user_agent.platform,
            'browser': request.user_agent.browser,
            'version': request.user_agent.version,
            'language': request.user_agent.language
            },
        'url_root': request.url_root,
        'path': request.path
        }

    if session_data['session']['name'] is None :
        session_data['session']['name'] = gen_rand(64) #os.urandom(32).hex()

    if session_data['instance_config']['state'] != 'ready':
        session_data['ip']['status'] = "not_ready"
        session_data['session']['state'] = "not_ready"
        session_data['upload_token']['state'] = "not_ready"
        session_data['token']['state'] = "not_ready"
        return session_data

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_session_check,
        dns= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        ip= session_data['ip']['name'],
        session_name= session_data['session']['name'],
        upload_token= session_data['upload_token']['token']
    )

    for result in results.records:
        data = result.data()
        session_data['ip']['status'] = data['ip_status']
        session_data['ip']['nb_upload_token'] = data['nb_upload_token']
        session_data['session']['state'] = data['session_state']
        session_data['session']['challenge'] = data['session_challenge']
        session_data['session']['user_verification'] = data['session_user_verification']
        session_data['user']['id'] = bytes("%s" % (data['user_id']), 'utf8')
        session_data['user']['name'] = data['user_name']
        session_data['user']['display'] = data['user_display_name']
        session_data['token']['challenge'] = data['token_challenge']
        session_data['token']['state'] = data['token_state']
        session_data['token']['user_verification'] = data['token_user_verification']
        session_data['token']['authenticator_attachment'] = data['token_authenticator_attachment']
        session_data['token']['credential_data'] = data['token_credential_data']
        session_data['upload_token']['dest'] = data['dest_ut']
        session_data['upload_token']['source'] = data['source_ut']
        session_data['upload_token']['state'] = data['ut_state']
        session_data['upload_token']['token'] = data['upload_token']

    if ((session_data['upload_token']['state'] == 'ok')
        and (len(request.values) > 0) and ('token' in request.values) and (request.values['token'])
        and session_data['upload_token']['token'] == request.values['token']
        ):
        session_data['upload_token']['state'] = 'verified'

    return session_data

def logging_session_data(session_data):
    session_data = session_check(request)
    session_data['user']['id'] = '... removed ...'
    app.logger.info("url_root : %s", json.dumps(session_data['request']['url_root'], sort_keys=True, indent=4))
    app.logger.info("ip : %s", json.dumps(session_data['ip']['name'], sort_keys=True, indent=4))
    app.logger.debug("session_data : %s", json.dumps(session_data, sort_keys=True, indent=4))

def file_diff(uuid1, uuid2):
    read_block_size = 512
    data = {'uuid1': uuid1, 'uuid2': uuid2, 'identical' : False}
    with open(app.config["UPLOAD_FOLDER"] + '/' + str(uuid1), 'rb') as f1:
        with open(app.config["UPLOAD_FOLDER"] + '/' + str(uuid2), 'rb') as f2 :
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
            return data
    return data

def sha256_oldest_file(sha256):
    data = {'sha256': sha256}

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_sha256_oldest_file,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        sha256= sha256
    )

    for result in results.records:
        data_line = result.data()
        data['uuid'] = data_line['uuid']
        break

    return data

@app.route('/get_github_infos', methods = ['GET'])
def route_get_github_infos():
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    r = requests.get("https://api.github.com/meta")

    return jsonify(r.json())

@app.route('/<uuid:uuid1>/<uuid:uuid2>/diff', methods = ['GET'])
def route_file_diff(uuid1, uuid2):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = file_diff(uuid1, uuid2)
    return jsonify(data)

@app.route('/sha256_oldest_file/<string:sha256>', methods = ['GET', 'POST'])
def route_sha256_oldest_file(sha256):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = sha256_oldest_file(sha256)
    return jsonify(data)


@app.route('/<uuid:uuid>/sha256', methods = ['GET'])
def route_file_sha256(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {'uuid': uuid}
    data['sha256'] = digest(uuid, "sha256")
    return jsonify(data)

@app.route('/<uuid:uuid>/sha512', methods = ['GET'])
def route_file_sha512(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {'uuid': uuid}
    data['sha512'] = digest(uuid, "sha512")
    return jsonify(data)

@app.route('/<uuid:uuid>/type', methods = ['POST'])
def route_file_post_type(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {'uuid': uuid}

    if ((len(request.values) != 0) and ('file_type' in request.values) and (request.values['file_type'] != "")
        and ('token' in request.values) and (request.values['token'] == config['token'])):
        results = app.config['NEO4J_DRIVER'].execute_query(
            query_post_file_type,
            name= os.environ['INSTANCE_DNS'],
            instance_number= app.config['INSTANCE_NUMBER'],
            file_uuid= uuid,
            file_type= request.values['file_type']
        ).summary

        data['result_available_after'] = results.result_available_after
        app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    else :
        app.logger.info("No file_type")

    return jsonify(data)

@app.route('/<uuid:uuid>/type', methods = ['GET'])
def route_file_get_type(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {'uuid': uuid}
    results = app.config['NEO4J_DRIVER'].execute_query(
        query_get_file_type,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
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

@app.route('/<uuid:uuid>/location', methods = ['POST'])
def route_file_post_location(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {'uuid': uuid}

    if ((len(request.values) != 0) and ('location' in request.values) and (request.values['location'] != "")
        and ('token' in request.values) and (request.values['token'] == config['token'])):
        results = app.config['NEO4J_DRIVER'].execute_query(
            query_post_file_location,
            name= os.environ['INSTANCE_DNS'],
            instance_number= app.config['INSTANCE_NUMBER'],
            file_uuid= uuid,
            location= request.values['location']
        ).summary

        data['result_available_after'] = results.result_available_after
        app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    else :
        app.logger.info("No location")

    return jsonify(data)

@app.route('/full_backup_first_file', methods = ['POST'])
def route_file_get_full_backup_first_file():
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    if (session_data['upload_token']['state'] != "verified"):
        abort(401)

    data = {}
    results = app.config['NEO4J_DRIVER'].execute_query(
        query_full_backup_first_file,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER']
    )

    for result in results.records:
        data_line = result.data()
        data['uuid'] = data_line['uuid']
        #data['next'] = data_line['next']
        #data['actual'] = data_line['actual']
        break

    #app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    return jsonify(data)

@app.route('/<uuid:uuid>/next_backup', methods = ['POST'])
def route_file_get_next_backup(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {'uuid': uuid}
    if ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):

        results = app.config['NEO4J_DRIVER'].execute_query(
            query_next_backup,
            name= os.environ['INSTANCE_DNS'],
            instance_number= app.config['INSTANCE_NUMBER'],
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

@app.route('/<uuid:uuid>/infos', methods = ['POST'])
def route_file_post_infos(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {'uuid': uuid}

    if ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):
        if ((len(request.values) != 0) and ('location' in request.values) and (request.values['location'] != "")):
            results = app.config['NEO4J_DRIVER'].execute_query(
                query_post_file_infos,
                name= os.environ['INSTANCE_DNS'],
                instance_number= app.config['INSTANCE_NUMBER'],
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
            results = app.config['NEO4J_DRIVER'].execute_query(
                query_get_file_infos,
                name= os.environ['INSTANCE_DNS'],
                instance_number= app.config['INSTANCE_NUMBER'],
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

@app.route('/<uuid:uuid>/execute_query', methods = ['POST'])
def route_execute_query(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {}
    if ((len(request.values) != 0) and ('token' in request.values) and (request.values['token'] == config['token'])):
        file_name = neo4j_get_file(app.config['INSTANCE_CONFIG'], str(uuid))

        query = ""
        with open(app.config["UPLOAD_FOLDER"] + '/' + str(uuid), 'rt') as f :
            query = f.read()

        if (len(query) == 0):
            data['error'] == 'not found'
            return jsonify(data)

        data['records'], summary, data['keys'] = app.config['NEO4J_DRIVER'].execute_query(
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

@app.route('/filesystem/<path:location>', methods = ['GET'])
def route_download_location(location):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    data = {}

    records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(
        query_get_location,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        location= location
    )

    #app.logger.info("summary : %s - %s ms", results.counters.nodes_created, results.result_available_after)
    for result in records:
        app.logger.info("result : %s" % (result))
        row = result.data()
        app.logger.info("result.data() : %s" % (result.data()))

        if 'file_uuid' in row['content'] :
            url = "https://%s/%s" % (os.environ['INSTANCE_DNS'], row['content']['file_uuid'])
        else :
            url = "https://%s/filesystem/%s" % (os.environ['INSTANCE_DNS'], row['content']['name'])

        if row['content']['name'] not in data :
            data[ row['content']['name'] ] = {}
        data[ row['content']['name'] ][ row['content']['creation_date'].iso_format() ] = url

    return jsonify(data)

@app.route('/<uuid:uuid>', methods = ['GET'])
def route_download_file(uuid):
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    file_name = neo4j_get_file(app.config['INSTANCE_CONFIG'], str(uuid))
    app.logger.info("file_name : %s" % (file_name))
    return send_from_directory(app.config["UPLOAD_FOLDER"], str(uuid), as_attachment=True, download_name=file_name)

@app.route('/npm/<string:lib>/+esm', methods = ['GET'])
def route_download_npm_lib(lib):
    session_data = session_check(request)
    if (session_data['session']['state'] != 'valid'):
        abort(404)

    return send_from_directory(app.config["NPM_FOLDER"], str(lib), mimetype="text/javascript")

@app.route('/hooks/<string:hook_name>', methods=['GET', 'POST'])
def route_hooks(hook_name):
    session_data = session_check(request)
    if session_data['ip']['status'] == 'banned':
        abort(404)

    data = {'hook_name': hook_name}
    received_data = "not a json"
    if (request.is_json):
        received_data =  ", ".join(request.json)
    #data['len(request)'] = len(request.values)
    #for value in request.values:
    #    data[value] = request.values[value]
    app.logger.info("hook : %s - %s", hook_name, ", ".join(request.values))
    records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(
        query_hooks,
        name= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        hook_name= hook_name,
        ip= request.remote_addr,
        #data= ", ".join(request.values)
        data=received_data
    )

    app.logger.info("summary : %s ms", summary.result_available_after)

    log = "no"
    for record in records:
        log = record['logger']

    if log == 'ok' :
        app.logger.info("json data : %s" % ( json.dumps(request.json, sort_keys=True, indent=4) ))

    return jsonify(data)

@app.route("/api/session_data", methods=["GET", "POST"])
def route_session_data():
    session_data = session_check(request)
    if session_data['instance_config']['state'] != 'ready':
        abort(404)

    if session_data['ip']['status'] != 'ok':
        abort(404)

    logging_session_data(session_data)

    session_data['user']['id'] = '... removed ...'
    del session_data['token']
    return jsonify(session_data)

@app.route("/api/register/begin", methods=["POST"])
def route_register_begin():
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    options, state = app.config['FIDO2_SERVER'].register_begin(
        PublicKeyCredentialUserEntity(
            id= session_data['user']['id'],
            name= session_data['user']['name'],
            display_name= session_data['user']['display'],
        ),
        [], #credentials,
        user_verification= session_data['token']['user_verification'],
        authenticator_attachment= session_data['token']['authenticator_attachment'],
    )

    session_data['token']['challenge'] = state['challenge']
    session_data['token']['user_verification'] = state['user_verification']

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_set_cookie,
        dns= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        ip= session_data['ip']['name'],
        session_name= session_data['session']['name'],
        challenge= session_data['token']['challenge'],
        user_verification= session_data['token']['user_verification']
    )

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_token_register,
        dns= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        ip= session_data['ip']['name'],
        session_name= session_data['session']['name'],
        challenge= session_data['token']['challenge'],
        user_verification= session_data['token']['user_verification']
    )

    for result in results.records:
        data = result.data()
        pass

    resp = jsonify(dict(options))
    resp.set_cookie('session_name', session_data['session']['name'], secure=True, httponly=True, samesite='Strict')
    return resp

@app.route("/api/register/complete", methods=["POST"])
def route_register_complete():
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    response = request.json
    state = {
        'challenge': session_data['token']['challenge'],
        'user_verification': session_data['token']['user_verification']
    }

    auth_data = app.config['FIDO2_SERVER'].register_complete(state, response)

    b64_auth_data = base64.b64encode(auth_data.credential_data)

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_token_register_complete,
        dns= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        ip= session_data['ip']['name'],
        session_name= session_data['session']['name'],
        credential_data= b64_auth_data.decode('utf8')
    )

    for result in results.records:
        data = result.data()
        pass

    return jsonify({"status": "OK"})

@app.route("/api/authenticate/begin", methods=["POST"])
def route_authenticate_begin():
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    if session_data['token']['credential_data'] is None :
        abort(401)

    cred_bytes = base64.b64decode(session_data['token']['credential_data'].encode('utf8'))
    cred_data = AttestedCredentialData.unpack_from(cred_bytes)[0]

    options, state = app.config['FIDO2_SERVER'].authenticate_begin([cred_data])

    session_data['session']['challenge'] = state['challenge']
    session_data['session']['user_verification'] = state['user_verification']

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_set_cookie,
        dns= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        ip= session_data['ip']['name'],
        session_name= session_data['session']['name'],
        challenge= session_data['session']['challenge'],
        user_verification= session_data['session']['user_verification']
    )

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_token_auth,
        dns= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        ip= session_data['ip']['name'],
        session_name= session_data['session']['name'],
        challenge= session_data['session']['challenge'],
        user_verification= session_data['session']['user_verification']
    )

    for result in results.records:
        data = result.data()
        pass

    resp = jsonify(dict(options))
    resp.set_cookie('session_name', session_data['session']['name'], secure=True, httponly=True, samesite='Strict')
    return resp

@app.route("/api/authenticate/complete", methods=["POST"])
def route_authenticate_complete():
    session_data = session_check(request)
    if session_data['ip']['status'] != 'ok':
        abort(404)

    cred_bytes = base64.b64decode(session_data['token']['credential_data'].encode('utf8'))
    cred_data = AttestedCredentialData.unpack_from(cred_bytes)[0]

    response = request.json
    state = {
        'challenge': session_data['session']['challenge'],
        'user_verification': session_data['session']['user_verification']
    }

    app.config['FIDO2_SERVER'].authenticate_complete(
        state,
        [cred_data],
        response,
    )

    results = app.config['NEO4J_DRIVER'].execute_query(
        query_token_auth_complete,
        dns= os.environ['INSTANCE_DNS'],
        instance_number= app.config['INSTANCE_NUMBER'],
        ip= session_data['ip']['name'],
        session_name= session_data['session']['name'],
    )

    return jsonify({"status": "OK"})

@app.route("/api/upload_token", methods=["GET", "POST"])
def route_upload_token():
    session_data = session_check(request)
    if session_data['instance_config']['state'] != 'ready':
        abort(404)

    if session_data['ip']['status'] == 'banned':
        abort(404)

    if session_data['ip']['nb_upload_token'] > 5:
        abort(401)

    config_data = {
        'dns': os.environ['INSTANCE_DNS'],
        'instance_number': app.config['INSTANCE_NUMBER'],
        'ip': session_data['ip']['name'],
        'session_name': session_data['session']['name'],
        'upload_token': session_data['upload_token']['token']
    }

    if (session_data['upload_token']['state'] == "no_token"):
        config_data['upload_token'] = gen_rand(64)

        records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(query_upload_token, parameters_= config_data)
        app.logger.info("summary : %s ms", summary.result_available_after)

        for record in records:
            config_data['token'] = record['token']
            break

    return jsonify(config_data)

@app.route('/graph.css', methods=['GET', 'POST'])
def route_graph_css():
    session_data = session_check(request)
    if (session_data['session']['state'] != 'valid'):
        abort(404)

    return Response(render_template('graph.css'), mimetype='text/css')

@app.route('/graph.js', methods=['GET', 'POST'])
def route_graph_js():
    session_data = session_check(request)
    if (session_data['session']['state'] != 'valid'):
        abort(404)

    return Response(render_template('graph.js'), mimetype='text/javascript')

@app.route('/<string:node_id>/data.json', methods=['GET', 'POST'])
def route_data_json(node_id):
    session_data = session_check(request)
    if (session_data['session']['state'] != 'valid'):
        abort(404)

    nodes_presence = []
    nodes = []
    links = []
    #if ('node_id' not in request.values):
    #    return None

    records, summary, keys = app.config['NEO4J_DRIVER'].execute_query(query_data,
        parameters_= {'node_id': node_id
        })

    app.logger.info("summary : %s ms", summary.result_available_after)
    for data in records:
        if ( data['rel_type'] ) :
            links.append({'source': data['source'],
                'target': data['target'],
                'value': data['value'],
                'type': data['rel_type']
                })

        if data['source'] not in nodes_presence:
            nodes.append({'id': data['source'],
                'url': "/__my_login__?node_id=%s" % data['source'],
                'name': data['name_n1'],
                'labels': data['label_n1']})
            nodes_presence.append(data['source'])

        if data['target'] not in nodes_presence:
            nodes.append({'id': data['target'],
                'url': "/__my_login__?node_id=%s" % data['target'],
                'name': data['name_n2'],
                'labels': data['label_n2']})
            nodes_presence.append(data['target'])

    return jsonify({ 'nodes': nodes, 'links': links })

@app.route('/__my_login__', methods=['GET', 'POST'])
def route_login():
    session_data = session_check(request)
    if (session_data['ip']['status'] == 'banned'):
        abort(404)

    return render_template('index.html', title='login', status= 'ok',session_status=session_data['session']['state'])

@app.route('/', methods=['GET', 'POST'])
def route_upload_file_get():
    session_data = session_check(request)
    logging_session_data(session_data)
    if (session_data['ip']['status'] == 'banned'):
        app.logger.info("ip status : banned")
        abort(404)

    if is_ready(app.config['INSTANCE_CONFIG']) : #is_ready
        if ( (session_data['upload_token']['state'] == "verified")
            and (len(request.files) != 0) and ('file' in request.files) ):

            if session_data['ip']['status'] != 'ok':
                #abort(404)
                return render_template('simple_uploader.html', title='Upload file', status='ok', session_status=session_data['session']['state'])

            try :
                data = upload_file(request)
                return jsonify(data)

            except PermissionError:
                return render_template('simple_uploader.html', title='Upload file', status='permission error', session_status=session_data['session']['state'])

        elif (request.method == 'POST'):
            #if ('token' not in request.values):
            #    return render_template('simple_uploader.html', title='Upload file', status='missing token', session_status=session_data['session']['state'])

            #elif (('token' in request.values) and (request.values['token'] != app.config['INSTANCE_CONFIG']['token'])):
            #    return render_template('simple_uploader.html', title='Upload file', status='wrong token', session_status=session_data['session']['state'])

            if ('file' not in request.files):
                return render_template('simple_uploader.html', title='Upload file', status='missing file', session_status=session_data['session']['state'])

            else :
                return render_template('simple_uploader.html', title='Upload file', status='errors in information', session_status=session_data['session']['state'])

        else :
            return render_template('uploader.html', title='Home', status='ok', session_status=session_data['session']['state'], urls=get_urls())

    elif is_wait_for_neo4j_credential(app.config['INSTANCE_CONFIG']): #is_wait_for_neo4j_credential
        if verify_post_neo4j_credential(request): #verify_post_neo4j_credential
            app.config['INSTANCE_CONFIG']['neo4j']['instance'] = request.values['instance']
            app.config['INSTANCE_CONFIG']['neo4j']['login'] = request.values['login']
            app.config['INSTANCE_CONFIG']['neo4j']['password'] = request.values['password']
            save_config_file(app.config['INSTANCE_CONFIG'])

            if neo4j_connection(app.config['INSTANCE_CONFIG']):
                if install_config(app.config['INSTANCE_CONFIG']):
                    #return render_template('simple_uploader.html', title='Upload file', status='database connected', session_status=session_data['session']['state'])
                    return render_template('uploader.html', title='Home', status='database connected', session_status=session_data['session']['state'], urls=get_urls())
                else :
                    return render_template('simple_uploader.html', title='Upload file', status='database configuration failed', session_status=session_data['session']['state'])
            else :
                return render_template('simple_uploader.html', title='Upload file', status='connection failed', session_status=session_data['session']['state'])

        elif (request.method == 'POST'):
            return render_template('ask_neo4j_password.html', title='Ask Neo4J credential', status='errors in information', session_status=session_data['session']['state'])

        else :
            return render_template('ask_neo4j_password.html', title='Ask Neo4J credential', status='ok', session_status=session_data['session']['state'])

    elif is_wait_for_password(app.config['INSTANCE_CONFIG']): #is_wait_for_password
        if ( (len(request.values) != 0) and ('password' in request.values) and (request.values['password'] != "") ):
            app.config['INSTANCE_CONFIG']['key'] = derive(app.config['INSTANCE_CONFIG'], bytes(request.values['password'], 'utf-8'))

            if (app.config['INSTANCE_CONFIG']['neo4j']['instance'] != ''): #conf.json file already exists at boot
                tempo = open_config_file(app.config['INSTANCE_CONFIG']['key'])
                app.config['INSTANCE_CONFIG']['token'] = tempo['token']
                app.config['INSTANCE_CONFIG']['neo4j']['password'] = tempo['neo4j']['password']

                if neo4j_connection(app.config['INSTANCE_CONFIG']):
                    if install_config(app.config['INSTANCE_CONFIG']):
                        #return render_template('simple_uploader.html', title='Upload file', status='database connected', session_status=session_data['session']['state'])
                        return render_template('uploader.html', title='Home', status='database connected', session_status=session_data['session']['state'], urls=get_urls())
                    else :
                        return render_template('simple_uploader.html', title='Upload file', status='database configuration failed', session_status=session_data['session']['state'])

                else :
                    return render_template('simple_uploader.html', title='Upload file', status='connection failed', session_status=session_data['session']['state'])

            else :
                return render_template('ask_neo4j_password.html', title='Ask Neo4J credential', status='ok', session_status=session_data['session']['state'])

        elif (request.method == 'POST'):
            return render_template('ask_password.html', title='Ask password', status='empty password not allowed', session_status=session_data['session']['state'])

        else :
            return render_template('ask_password.html', title='Ask password', status='ok', session_status=session_data['session']['state'])

    else : #strange case
        return render_template('ask_password.html', title='Ask password', status='should not happen', session_status=session_data['session']['state'])

#this part is for flask server config not used used by gunicorn
if __name__ == "__main__":

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

    app.config['INSTANCE_CONFIG'] = open_config_file()

    try :
        dns_name = os.environ['INSTANCE_DNS']
        app.logger.info("dns_name : %s", dns_name)
        logs = os.system("/usr/bin/sudo /scripts/gen_certs.sh %s" % (dns_name))

        rp = PublicKeyCredentialRpEntity(name="Linked : %s" % (dns_name), id=dns_name)
        app.config['FIDO2_SERVER'] = Fido2Server(rp)

    finally:
        app.logger.info("logs : %s", logs)

    try:
        #context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain("/certs/fullchain.pem", "/certs/privkey.pem")
        app.logger.info("SSLContext get_ciphers : %s" % (context.get_ciphers()))
        app.logger.info("SSLContext tls_1.3 : %s" % (ssl.TLSVersion.TLSv1_3))
        app.logger.info("SSLContext tls_1.2 : %s" % (ssl.TLSVersion.TLSv1_2))
        app.logger.info("SSLContext maximum_version : %s" % (context.maximum_version))
        app.logger.info("SSLContext minimum_version : %s" % (context.minimum_version))
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        app.logger.info("    ... SSLContext minimum_version : %s" % (context.minimum_version))
        app.logger.info("    ... SSLContext get_ciphers : %s" % (context.get_ciphers()))
        context.sni_callback = ssl_sni_check

    except FileNotFoundError:
        app.run(host='::', port='443') #debug=True
        #app.run(host='0.0.0.0', port='443') #debug=True
        app.logger.info("!!! no certs found !!!", app.config['INSTANCE_NUMBER'])
    else:
        app.run(host='::', port='443', ssl_context=context) #debug=True
        #app.run(host='0.0.0.0', port='443', ssl_context=context) #debug=True
    finally :
        app.logger.info("instance name : %s", app.config['INSTANCE_NUMBER'])
