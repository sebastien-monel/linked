from flask import (
    Flask, jsonify, flash, request, redirect, url_for,
    render_template, send_file, send_from_directory, make_response,
    abort
    )
from werkzeug.utils import secure_filename
import os
import json

UPLOAD_FOLDER = '/uploaded_files'
#ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'py', 'exe', 'ipynb', 'zip', 'tar', 'sh', ''}

app = Flask(__name__, static_url_path="")
app.secret_key = os.urandom(32)  # Used for session.
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

config = {}
config['password'] = ""

index_html = '''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=password name=password>
      <input type=submit value=Upload>
    </form>
'''

wrong_password_html = '''
    <!doctype html>
    <title>Password error</title>
    <h1>Password error</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=password name=password>
      <input type=submit value=Upload>
    </form>
'''

password_html = '''
    <!doctype html>
    <title>Set password</title>
    <h1>Set password</h1>
    <form method=post enctype=multipart/form-data>
      <input type=password name=password>
      <input type=submit value="Set password">
    </form>
'''


@app.route('/', methods=['GET'])
def route_upload_file_get():
    if (config['password'] != "") :
        html = index_html
    else :
        html = password_html

    resp = make_response(html)
#    resp.set_cookie('session_name', session_data['session_name'])
    return resp

@app.route('/<name>', methods = ['GET'])
def route_download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name, as_attachment=True, download_name=name)

@app.route('/', methods=['POST'])
def route_upload_file_post():
    if (config['password'] != "") :
        if ( (len(request.values) != 0) and ('password' in request.values) ):
            if (request.values['password'] != config['password']) :
                html = wrong_password_html

            else :
                if ('file' in request.files) :
                    file = request.files['file']
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    html = index_html
                else :
                    html = index_html
                    #flash('No file part')
                    #return redirect(request.url)

        else :
            html = index_html
            #flash('No password')
            #return redirect(request.url)

    else :
        if ( (len(request.values) != 0) and ('password' in request.values) and (request.values['password'] != "") ):
            config['password'] = request.values['password']
            html = index_html
        else:
            html = password_html

    resp = make_response(html)
#    resp.set_cookie('session_name', session_data['session_name'])
    return resp

if __name__ == "__main__":
    app.run(host='0.0.0.0:443') #debug=True, ssl_context="adhoc", ... to_review !!!
