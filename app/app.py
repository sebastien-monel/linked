from flask import (
    Flask, jsonify, flash, request, redirect, url_for,
    render_template, send_file, send_from_directory, make_response,
    abort
    )

import os

UPLOAD_FOLDER = '/uploaded_files'
#ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'exe', 'ipynb', 'zip', 'tar', 'sh', ''}

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(32)  # Used for session.
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route("/", methods = ['GET', 'POST']) #page_accessible_hors_session
def route_index():
    html = ""
    html = "<html><head><title>Hey you</title></head><body>You here !!!</body></html>"

    resp = make_response(html)
#    resp.set_cookie('session_name', session_data['session_name'])
    return resp

if __name__ == "__main__":
    app.run(host='0.0.0.0') #debug=True, ssl_context="adhoc", ... to_review !!!
