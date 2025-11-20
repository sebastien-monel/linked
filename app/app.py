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

@app.route('/', methods=['GET'])
def route_upload_file_get():
    if (config['password'] != "") :
        return render_template('simple_uploader.html', title='Upload file')
    else :
        return render_template('ask_password.html', title='Ask password')

@app.route('/<name>', methods = ['GET'])
def route_download_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name, as_attachment=True, download_name=name)

@app.route('/', methods=['POST'])
def route_upload_file_post():
    if (config['password'] != "") :
        if ( (len(request.values) != 0) and ('password' in request.values) ):
            if (request.values['password'] != config['password']) :
                return render_template('simple_uploader.html', title='Upload file - wrong password')

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
        if ( (len(request.values) != 0) and ('password' in request.values) and (request.values['password'] != "") ):
            config['password'] = request.values['password']
            return render_template('simple_uploader.html', title='Upload file')

        else:
            return render_template('ask_password.html', title='Ask password')

if __name__ == "__main__":
    app.run(host='0.0.0.0:443') #debug=True, ssl_context="adhoc", ... to_review !!!
