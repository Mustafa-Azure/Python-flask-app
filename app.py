from flask import Flask, render_template
from flask import request, redirect, url_for, flash,Response
from azure.storage.blob import BlobServiceClient
import os

app = Flask(__name__)

app.config['SECRET_KEY'] = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'

# Replace with your Azure Storage account connection string
AZURE_STORAGE_CONNECTION_STRING = ""

@app.route('/')
def list_containers():
    try:
        user_role = "Reader"
        # Create a BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

        # List containers
        containers = blob_service_client.list_containers()
        container_names = [container['name'] for container in containers]

        #return render_template('containers.html', containers=container_names,user_role=user_role)
        return render_template('g - Copy.html', containers=container_names,user_role=user_role)
    except Exception as e:
        return str(e)

@app.route('/blobs/<container_name>/<path:folder_path>', methods=['GET'])
@app.route('/blobs/<container_name>/', methods=['GET'])
def list_blobs(container_name, folder_path=''):
    try:
        # Create a BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

        # Get the container client
        container_client = blob_service_client.get_container_client(container_name)

        # List blobs in the container or folder
        blobs = container_client.list_blobs(name_starts_with=folder_path)
        
        # Initialize lists for files and folders
        files = []
        folders = set()  
        

        for blob in blobs:
            # Split the blob name to find folders
            parts = blob.name.split('/')
            if len(parts) > 1:
                # If there are parts, treat the first part as a folder
                folder_name = parts[0]
                if folder_name != folder_path:  # Avoid adding the current folder
                    folders.add(folder_name)
            else:
                # Otherwise, it's a file
                files.append(blob.name)

        return render_template('blobs.html', container_name=container_name, files=files, folders=list(folders), current_folder=folder_path)
    except Exception as e:
        return str(e)

@app.route('/upload/<container_name>/<path:folder_path>', methods=['POST'])
def upload_blob(container_name, folder_path):
    try:
        # Create a BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

        # Get the container client
        container_client = blob_service_client.get_container_client(container_name)

        # Get the uploaded file
        file = request.files['file']
        if file:
            # Create a blob name with the folder path
            blob_name = folder_path + file.filename
            # Upload the file
            container_client.upload_blob(name=blob_name, data=file, overwrite=True)
            flash('File uploaded successfully!', 'success')
        else:
            flash('No file selected for upload.', 'error')

        return redirect(url_for('list_blobs', container_name=container_name, folder_path=folder_path))
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')
        return redirect(url_for('list_blobs', container_name=container_name, folder_path=folder_path))

### Step 4: Add Download Functionality

@app.route('/download/<container_name>/<path:blob_name>', methods=['GET'])
def download_blob(container_name, blob_name):
    try:
        # Create a BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

        # Get the container client
        container_client = blob_service_client.get_container_client(container_name)

        # Get the blob client
        blob_client = container_client.get_blob_client(blob_name)

        # Download the blob
        blob_data = blob_client.download_blob()
        return Response(blob_data.readall(), mimetype='application/octet-stream', headers={
            'Content-Disposition': f'attachment; filename={blob_name.split("/")[-1]}'
        })
    except Exception as e:
        return str(e)


@app.route('/delete_blobs/<container_name>', methods=['POST'])
def delete_blobs(container_name):
    try:
        # Create a BlobServiceClient
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

        # Get the container client
        container_client = blob_service_client.get_container_client(container_name)

        # Get the list of blob names from the form
        blob_names = request.form.getlist('blob_names')

        # Delete each selected blob
        for blob_name in blob_names:
            container_client.delete_blob(blob_name)

        flash('Selected files and folders deleted successfully!', 'success')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'error')

    return redirect(url_for('list_blobs', container_name=container_name))

if __name__ == '__main__':
    app.run(debug=True)