import os
import uuid
import re
import traceback
import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, 
    create_access_token, 
    jwt_required, 
    get_jwt_identity,
    verify_jwt_in_request,
    decode_token # <-- Added this import
)
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from google.cloud import storage

# Initialize Flask app and enable CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure JWT settings; ensure token lookup is only from headers
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key")
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
jwt = JWTManager(app)

# Initialize itsdangerous serializer
serializer = URLSafeTimedSerializer(app.config["JWT_SECRET_KEY"])

# Cloud Storage bucket name (default to your bucket)
BUCKET_NAME = os.environ.get("POSTER_BUCKET_NAME", "poster-app-photos-137340833578")

def get_db_connection():
    dbname = os.environ["DB_NAME"]
    user = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    socket_path = os.environ["DB_HOST"]
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=socket_path
        )
        return conn
    except Exception as e:
        print("‼️ Database connection failed:", e)
        return None

def upload_file_to_bucket(file_obj, bucket_name, destination_blob_name):
    """
    Uploads a file to Google Cloud Storage and returns its public URL.
    """
    safe_blob_name = re.sub(r'[^a-z0-9\-_.]', '', destination_blob_name.lower())
    try:
        print(f"upload_file_to_bucket: Uploading file with blob name: {safe_blob_name}")
        print("File content type:", file_obj.content_type)
        file_obj.seek(0)  # Ensure file pointer is reset
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(safe_blob_name)
        blob.upload_from_file(file_obj, content_type=file_obj.content_type)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print("Error in upload_file_to_bucket:", e)
        print(traceback.format_exc())
        raise

# ---------------- User Endpoints -----------------

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    email = data.get("email", None)
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    password_hash = generate_password_hash(password)
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return jsonify({"error": "Username already exists"}), 409
        cur.execute(
            "INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING id",
            (username, password_hash, email)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        print("Error during registration:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"id": user_id, "username": username, "email": email}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"msg": "Username and password required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"msg": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if not row:
            return jsonify({"msg": "Bad username or password"}), 401
        user_id, password_hash = row
        if not check_password_hash(password_hash, password):
            return jsonify({"msg": "Bad username or password"}), 401
    except Exception as e:
        print("Error during login:", e)
        return jsonify({"msg": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200

@app.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    current_user = get_jwt_identity()
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, email, is_verified, created_at FROM users WHERE username = %s", (current_user,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        user = {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "is_verified": row[3],
            "created_at": row[4].isoformat() if row[4] else None
        }
    except Exception as e:
        print("Error fetching profile:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify(user), 200

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Username is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

    token = serializer.dumps(username, salt="password-reset-salt")
    return jsonify({"reset_token": token, "message": "Use this token with /reset-password within 15 minutes"}), 200

@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get("token")
    new_password = data.get("new_password")
    if not token or not new_password:
        return jsonify({"error": "Token and new password are required"}), 400
    try:
        username = serializer.loads(token, salt="password-reset-salt", max_age=900)
    except SignatureExpired:
        return jsonify({"error": "The reset token has expired"}), 400
    except BadSignature:
        return jsonify({"error": "Invalid reset token"}), 400

    new_password_hash = generate_password_hash(new_password)
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET password_hash = %s WHERE username = %s RETURNING id, username, email", 
                    (new_password_hash, username))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        conn.commit()
    except Exception as e:
        print("Error resetting password:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"message": f"Password updated for user '{username}'"}), 200

@app.route("/request-verification", methods=["POST"])
@jwt_required()
def request_verification():
    username = get_jwt_identity()
    token = serializer.dumps(username, salt="email-verification-salt")
    return jsonify({"verification_token": token, "message": "Use this token with /verify-email within one hour"}), 200

@app.route("/verify-email", methods=["POST"])
def verify_email():
    data = request.get_json()
    token = data.get("token")
    if not token:
        return jsonify({"error": "Token is required"}), 400
    try:
        username = serializer.loads(token, salt="email-verification-salt", max_age=3600)
    except SignatureExpired:
        return jsonify({"error": "The verification token has expired"}), 400
    except BadSignature:
        return jsonify({"error": "Invalid verification token"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET is_verified = TRUE WHERE username = %s RETURNING id, username, email, is_verified", (username,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        conn.commit()
    except Exception as e:
        print("Error during email verification:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"message": f"Email verified for user '{username}'", "user": {"id": row[0], "username": row[1], "email": row[2], "is_verified": row[3]}}), 200

# ---------------- Poster Endpoints -----------------

@app.route("/posters/upload", methods=["POST"])
def create_poster_with_photo():
    try:
        # Manually extract and decode the JWT token from the Authorization header
        auth_header = request.headers.get("Authorization", None)
        if not auth_header:
            return jsonify({"msg": "Missing Authorization header"}), 401
        try:
            token = auth_header.split()[1]
        except IndexError:
            return jsonify({"msg": "Invalid Authorization header format"}), 401
        
        try:
            decoded = decode_token(token)
            current_user = decoded.get("sub")
        except Exception as e:
            return jsonify({"msg": "Token decoding failed", "error": str(e)}), 401

        # Log the received form keys for debugging
        print("Request form keys:", list(request.form.keys()))
        title = request.form.get("title")
        description = request.form.get("description")
        print("Extracted title:", title)
        print("Extracted description:", description)

        if not title:
            print("Title is missing!")
            return jsonify({"error": "Title is required"}), 400

        file_obj = request.files.get("photo")
        photo_url = None
        if file_obj:
            raw_filename = file_obj.filename or "upload"
            safe_filename = re.sub(r'[^a-z0-9\-_.]', '', raw_filename.lower())
            filename = f"{uuid.uuid4()}_{safe_filename}"
            print(f"Uploading file with filename: {filename}")
            try:
                photo_url = upload_file_to_bucket(file_obj, BUCKET_NAME, filename)
                print("File successfully uploaded. Public URL:", photo_url)
            except Exception as upload_e:
                print("Error during file upload:", upload_e)
                return jsonify({"error": "Failed to upload image", "details": str(upload_e)}), 500

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO posters (title, description, photo_url) VALUES (%s, %s, %s) RETURNING id",
                (title, description, photo_url)
            )
            poster_id = cur.fetchone()[0]
            conn.commit()
            print(f"Created poster with id: {poster_id}")
        except Exception as db_e:
            print("Error creating poster:", db_e)
            return jsonify({"error": "Error creating poster", "details": str(db_e)}), 500
        finally:
            cur.close()
            conn.close()

        return jsonify({
            "id": poster_id,
            "title": title,
            "description": description,
            "photo_url": photo_url
        }), 201

    except Exception as e:
        print("Unhandled exception in /posters/upload:", e)
        print(traceback.format_exc())
        return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

@app.route("/posters", methods=["GET"])
def list_posters():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, description, photo_url FROM posters ORDER BY id DESC LIMIT 10")
        rows = cur.fetchall()
        posters = [{
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "photo_url": row[3]
        } for row in rows]
        return jsonify(posters), 200
    except Exception as e:
        print("Error fetching posters:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    
@app.route("/debug-multipart", methods=["POST"])
def debug_multipart():
    print("Request form keys:", list(request.form.keys()))
    form_data = {k: request.form.get(k) for k in request.form.keys()}
    return jsonify(form_data), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
