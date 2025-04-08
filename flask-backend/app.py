import os
import uuid
import re
import traceback
import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from google.cloud import storage

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes (for development use; restrict in production)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configure JWT
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key")
jwt = JWTManager(app)

# Initialize itsdangerous serializer (used for password reset and email verification)
serializer = URLSafeTimedSerializer(app.config["JWT_SECRET_KEY"])

# Set Cloud SQL and Cloud Storage configuration from environment variables
BUCKET_NAME = os.environ.get("POSTER_BUCKET_NAME", "poster-app-photos-137340833578")

def get_db_connection():
    host = os.environ.get("DB_HOST")
    dbname = os.environ.get("DB_NAME")
    user = os.environ.get("DB_USER")
    password = os.environ.get("DB_PASSWORD")
    try:
        conn = psycopg2.connect(host=host, database=dbname, user=user, password=password)
        return conn
    except Exception as e:
        print("Database connection failed:", e)
        return None

def upload_file_to_bucket(file_obj, bucket_name, destination_blob_name):
    """
    Uploads a file to a Google Cloud Storage bucket and returns its public URL.
    The destination blob name is sanitized to allow only certain characters.
    """
    safe_blob_name = re.sub(r'[^a-z0-9\-_.]', '', destination_blob_name.lower())
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(safe_blob_name)
        # Reset the file pointer in case it has been read already.
        file_obj.seek(0)
        blob.upload_from_file(file_obj, content_type=file_obj.content_type)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print("Error uploading file:", e)
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

@app.route("/posters", methods=["GET"])
def get_posters():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, description, photo_url FROM posters")
        rows = cur.fetchall()
        posters = []
        for row in rows:
            posters.append({
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "photo_url": row[3]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify(posters), 200

@app.route("/posters", methods=["POST"])
@jwt_required()
def create_poster():
    data = request.get_json()
    title = data.get("title")
    description = data.get("description")
    if not title:
        return jsonify({"error": "Title is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO posters (title, description) VALUES (%s, %s) RETURNING id",
                    (title, description))
        poster_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        print("Error creating poster:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"id": poster_id, "title": title, "description": description}), 201

@app.route("/posters/upload", methods=["POST"])
@jwt_required()
def create_poster_with_photo():
    title = request.form.get("title")
    description = request.form.get("description")
    if not title:
        return jsonify({"error": "Title is required"}), 400

    file_obj = request.files.get("photo")
    photo_url = None
    if file_obj:
        raw_filename = file_obj.filename or "upload"
        safe_filename = re.sub(r'[^a-z0-9\-_.]', '', raw_filename.lower())
        filename = f"{uuid.uuid4()}_{safe_filename}"
        try:
            photo_url = upload_file_to_bucket(file_obj, BUCKET_NAME, filename)
        except Exception as e:
            print("Error in /posters/upload:", e)
            return jsonify({"error": "Failed to upload image"}), 500

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
    except Exception as e:
        print("Error creating poster:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({
        "id": poster_id,
        "title": title,
        "description": description,
        "photo_url": photo_url
    }), 201

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
