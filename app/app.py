from flask import (
    Flask, jsonify, flash, request, redirect, url_for,
    render_template, send_file, send_from_directory, make_response,
    abort
    )
from werkzeug.utils import secure_filename
import os

UPLOAD_FOLDER = '/uploaded_files'
#ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'exe', 'ipynb', 'zip', 'tar', 'sh', ''}

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(32)  # Used for session.
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/', methods=['GET'])
def route_upload_file_get():
    html = '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
      <input type=text name=password>
    </form>
    '''
    resp = make_response(html)
#    resp.set_cookie('session_name', session_data['session_name'])
    return resp

@app.route('/<name>', methods = ['GET'])
def route_download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name, as_attachment=True, download_name=name)

@app.route('/', methods=['POST'])
def route_upload_file_post():
    if ( (len(request.values) != 0) and ('password' in request.values) and (request.values['password'] == 'test') ):
        file = request.files['file']
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    html = '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
      <input type=text name=password>
    </form>
    '''
    resp = make_response(html)
#    resp.set_cookie('session_name', session_data['session_name'])
    return resp

if __name__ == "__main__":
    app.run(host='0.0.0.0:443') #debug=True, ssl_context="adhoc", ... to_review !!!
