from flask import Flask, render_template, request, jsonify, url_for
from azure.storage.blob import BlobServiceClient
import os
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()
# Azure Storage configuration
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)


def list_containers():
    """Retrieve a list of containers from Azure Storage."""
    try:
        containers = blob_service_client.list_containers()
        return [container["name"] for container in containers]
    except Exception as e:
        return [f"Error: {str(e)}"]


def list_blobs(container_name, prefix=""):
    """Retrieve blobs and directories from the selected container and subfolders."""
    try:
        container_client = blob_service_client.get_container_client(container_name)
        blob_list = container_client.list_blobs(name_starts_with=prefix)

        files = []
        directories = set()

        for blob in blob_list:
            blob_name = blob.name[len(prefix):]  # Remove prefix to get relative path
            parts = blob_name.split("/", 1)

            if len(parts) > 1:  # Directory detected
                directories.add(parts[0] + "/")
            else:  # File detected
                files.append(blob.name)

        return sorted(directories), sorted(files)

    except Exception as e:
        return [f"Error: {str(e)}"], []


def search_blobs(container_name, query):
    """Search blobs (files & folders) within a container including subfolders."""
    try:
        container_client = blob_service_client.get_container_client(container_name)
        blob_list = container_client.list_blobs()

        results = []
        for blob in blob_list:
            if query.lower() in blob.name.lower():
                # Determine if it's a file or directory
                is_folder = "/" in blob.name.strip("/")
                item_type = "folder" if is_folder else "file"

                results.append({"name": blob.name, "type": item_type})

        return sorted(results, key=lambda x: x["name"])
    except Exception as e:
        return [{"name": f"Error: {str(e)}", "type": "error"}]


@app.route("/")
def home():
    """Render home page with a list of containers."""
    containers = list_containers()
    return render_template("index.html", containers=containers)


@app.route("/container/<container_name>/", defaults={"prefix": ""})
@app.route("/container/<container_name>/<path:prefix>/")
def view_container(container_name, prefix):
    """List blobs (files & directories) inside a container or subdirectory."""
    directories, files = list_blobs(container_name, prefix)
    return render_template(
        "container.html",
        container_name=container_name,
        directories=directories,
        files=files,
        prefix=prefix,
    )


@app.route("/search/<container_name>/")
def search(container_name):
    """Search API for real-time blob search."""
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify([])

    results = search_blobs(container_name, query)
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)
