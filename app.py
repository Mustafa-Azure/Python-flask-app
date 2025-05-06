from flask import Flask, render_template, request, redirect, url_for, flash
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash messages

# Azure Storage configuration - Replace with your actual connection string and container name
AZURE_CONNECTION_STRING = ""
AZURE_CONTAINER_NAME = "product-images"
AZURE_TABLE_NAME = "ProductMetadata"

# Allowed extensions for upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Initialize BlobServiceClient
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

# Initialize TableServiceClient
table_service_client = TableServiceClient.from_connection_string(AZURE_CONNECTION_STRING)

# Ensure blob container exists
try:
    container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)
    container_client.get_container_properties()
except Exception:
    container_client = blob_service_client.create_container(AZURE_CONTAINER_NAME)

# Ensure table exists
try:
    table_client = table_service_client.get_table_client(table_name=AZURE_TABLE_NAME)
    table_client.get_table_access_policy()
except Exception:
    table_client = table_service_client.create_table(table_name=AZURE_TABLE_NAME)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')

@app.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload():
    # Validate file
    if 'image' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('index'))
    file = request.files['image']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('index'))
    if not allowed_file(file.filename):
        flash('Invalid file type. Allowed types: png, jpg, jpeg, gif', 'error')
        return redirect(url_for('index'))

    # Validate metadata fields
    name = request.form.get('name', '').strip()
    category = request.form.get('category', '').strip()
    ptype = request.form.get('type', '').strip()
    price = request.form.get('price', '').strip()

    if not name or not category or not ptype or not price:
        flash("All metadata fields are required: Name, Category, Type, Price.", 'error')
        return redirect(url_for('index'))
    # Validate price is a number (float)
    try:
        price_val = float(price)
    except ValueError:
        flash("Price must be a valid number.", 'error')
        return redirect(url_for('index'))

    filename = secure_filename(file.filename)
    row_key = str(uuid.uuid4())
    # Store category in lowercase as PartitionKey for consistency
    partition_key = category.lower()

    try:
        # Upload image to Azure Blob Storage
        blob_client = container_client.get_blob_client(filename)
        blob_client.upload_blob(file.stream, overwrite=True)
    except Exception as e:
        flash(f"Error uploading image to Blob Storage: {str(e)}", 'error')
        return redirect(url_for('index'))

    try:
        # Store metadata to Azure Table Storage
        entity = {
            'PartitionKey': partition_key,
            'RowKey': row_key,
            'FileName': filename,
            'Name': name,
            'Category': category,
            'Type': ptype,
            'Price': price_val
        }
        table_client.upsert_entity(entity=entity)
    except Exception as e:
        flash(f"Error saving metadata to Table Storage: {str(e)}", 'error')
        return redirect(url_for('index'))

    flash(f'File "{filename}" uploaded successfully with metadata.', 'success')
    return redirect(url_for('index'))


@app.route('/products', methods=['GET'])
def products():
    # Get filter query parameters
    filter_name = request.args.get('name', '').strip()
    filter_category = request.args.get('category', '').strip().lower()  # convert to lowercase
    filter_type = request.args.get('type', '').strip()
    price_min = request.args.get('price_min', '').strip()
    price_max = request.args.get('price_max', '').strip()

    # Convert price filters to float or None
    try:
        price_min_val = float(price_min) if price_min else None
    except ValueError:
        price_min_val = None
    try:
        price_max_val = float(price_max) if price_max else None
    except ValueError:
        price_max_val = None

    products_list = []
    error = None
    try:
        # Build OData filter string for Azure Table Storage
        filters = []

        if filter_category:
            cat_escaped = filter_category.replace("'", "''")
            filters.append(f"PartitionKey eq '{cat_escaped}'")

        if price_min_val is not None:
            filters.append(f"Price ge {price_min_val}")
        if price_max_val is not None:
            filters.append(f"Price le {price_max_val}")

        filter_query = ' and '.join(filters) if filters else None

        entities = table_client.list_entities(filter=filter_query)

        for entity in entities:
            name_entity = entity.get('Name', '')
            type_entity = entity.get('Type', '')
            category_entity = entity.get('Category', '').lower()

            if filter_name and filter_name.lower() not in name_entity.lower():
                continue
            if filter_type and filter_type.lower() not in type_entity.lower():
                continue
            # Additional client-side filter for category in case PartitionKey differs
            if filter_category and filter_category != category_entity:
                continue

            products_list.append({
                'name': entity.get('Name'),
                'category': entity.get('Category'),
                'type': entity.get('Type'),
                'price': entity.get('Price'),
                'partitionKey': entity.get('PartitionKey'),
                'rowKey': entity.get('RowKey'),
                'fileName': entity.get('FileName')
            })

    except Exception as e:
        error = f"Error loading products: {str(e)}"

    if error:
        flash(error, 'error')
        return redirect(url_for('home'))

    return render_template('products.html', products=products_list,
                           filter_name=filter_name,
                           filter_category=filter_category,
                           filter_type=filter_type,
                           filter_price_min=price_min,
                           filter_price_max=price_max)


@app.route('/products/delete', methods=['POST'])
def delete_products():
    selected = request.form.getlist('selected_products')
    if not selected:
        flash("No products selected for deletion.", 'error')
        return redirect(url_for('products'))

    errors = []
    success_count = 0

    for item in selected:
        try:
            partitionKey, rowKey = item.split('|', 1)
            # Get entity to find filename
            entity = table_client.get_entity(partitionKey=partitionKey, row_key=rowKey)
            filename = entity.get('FileName')

            # Delete from Table Storage
            table_client.delete_entity(partitionKey=partitionKey, row_key=rowKey)

            # Delete from Blob Storage
            blob_client = container_client.get_blob_client(filename)
            blob_client.delete_blob()

            success_count += 1
        except Exception as e:
            errors.append(f"Error deleting product with ID {rowKey}: {str(e)}")

    if success_count:
        flash(f"{success_count} product(s) deleted successfully.", 'success')
    if errors:
        flash(" ".join(errors), 'error')

    return redirect(url_for('products'))


if __name__ == '__main__':
    app.run(debug=True)
