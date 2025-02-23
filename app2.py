import os
from flask import Flask, request, render_template, jsonify, flash
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Flask app initialization
app = Flask(__name__)
app.secret_key = "supersecretkey"  # Change this for production

# Azure Storage Configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("CONTAINER_NAME")

blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/check_file', methods=['POST'])
def check_file():
    """Check if a file exists in Azure Storage"""
    filename = request.json.get('filename')
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=filename)
    
    if blob_client.exists():
        return jsonify({'exists': True})
    return jsonify({'exists': False})

@app.route('/upload', methods=['POST'])
def upload_files():
    """Upload files to Azure Storage"""
    files = request.files.getlist('files[]')
    overwrite = request.form.get('overwrite') == 'true'

    for file in files:
        if file.filename == '':
            continue
        
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=file.filename)

        try:
            blob_client.upload_blob(file, overwrite=overwrite)
            flash(f"Uploaded {file.filename} successfully!")
        except Exception as e:
            flash(f"Failed to upload {file.filename}: {str(e)}")

    return jsonify({'message': 'Upload completed'})

if __name__ == '__main__':
    app.run(debug=True)
