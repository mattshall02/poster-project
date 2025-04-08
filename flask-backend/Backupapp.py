from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import os
import psycopg2

# Create the Flask app
app = Flask(__name__)

# Option 1: Allow CORS for all domains on all routes
CORS(app, resources={r"/*": {"origins": "*"}})

# Set configuration (JWT secret, etc.)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key")

# Now, create the JWTManager
jwt = JWTManager(app)

# Now create the serializer using the secret key from the app's config.
serializer = URLSafeTimedSerializer(app.config["JWT_SECRET_KEY"])

# Function to connect to the PostgreSQL database
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            database=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
        return conn
    except Exception as e:
        print("Database connection failed:", e)
        return None

# Health-check endpoint
@app.route("/")
def hello():
    return "Hello Crystal  from Flask API on Cloud Run!"

# Login Endpoint
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
        # Fetch the user's password hash from the database
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

    # Create a new token with the user identity
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200

#Profile Endpoint
@app.route("/profile", methods=["GET"])
@jwt_required()
def profile():
    current_user = get_jwt_identity()
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, email, created_at FROM users WHERE username = %s", (current_user,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        user = {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "created_at": row[3].isoformat() if row[3] else None
        }
    except Exception as e:
        print("Error fetching user profile:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify(user), 200


# Endpoint to fetch posters (assumes a 'posters' table exists)
@app.route("/posters")
def get_posters():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Failed to connect to database"}), 500

    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, description FROM posters;")
        rows = cur.fetchall()
        posters = [{"id": row[0], "title": row[1], "description": row[2]} for row in rows]
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify(posters)

# Poster Insert via POST
@app.route("/posters", methods=["POST"])
@jwt_required()
def create_poster():
    data = request.get_json()
    title = data.get("title")
    description = data.get("description")
    
    # Simple input validation
    if not title:
        return jsonify({"error": "Title is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO posters (title, description) VALUES (%s, %s) RETURNING id",
            (title, description)
        )
        new_id = cur.fetchone()[0]
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"id": new_id, "title": title, "description": description}), 201

# Poster Update via PUT
@app.route("/posters/<int:poster_id>", methods=["PUT"])
@jwt_required()
def update_poster(poster_id):
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
        cur.execute(
            "UPDATE posters SET title=%s, description=%s WHERE id=%s RETURNING id",
            (title, description, poster_id)
        )
        updated = cur.fetchone()
        if not updated:
            return jsonify({"error": "Poster not found"}), 404
        conn.commit()
    except Exception as e:
        print("Error updating poster:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"id": poster_id, "title": title, "description": description})

# Delete Poster via DELETE
@app.route("/posters/<int:poster_id>", methods=["DELETE"])
@jwt_required()
def delete_poster(poster_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM posters WHERE id = %s RETURNING id", (poster_id,))
        deleted = cur.fetchone()
        if not deleted:
            return jsonify({"error": "Poster not found"}), 404
        conn.commit()
    except Exception as e:
        print("Error deleting poster:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({"message": f"Poster {poster_id} deleted"})

# User Registration Endpoint
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    email = data.get("email", None)

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    # Hash the password for secure storage
    password_hash = generate_password_hash(password)

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        # Check if the username already exists
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            return jsonify({"error": "Username already exists"}), 409

        # Insert the new user
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

#Update Profile
@app.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    current_user = get_jwt_identity()  # Get the username from the JWT token
    data = request.get_json()

    # Get new values from the request; these are optional.
    new_email = data.get("email")
    new_password = data.get("password")

    # If neither field is provided, there's nothing to update.
    if new_email is None and new_password is None:
        return jsonify({"error": "No updates provided"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()

    try:
        if new_email is not None and new_password is not None:
            # Both email and password provided; hash the new password.
            password_hash = generate_password_hash(new_password)
            cur.execute(
                "UPDATE users SET email = %s, password_hash = %s WHERE username = %s RETURNING id, username, email",
                (new_email, password_hash, current_user)
            )
        elif new_email is not None:
            # Only updating the email.
            cur.execute(
                "UPDATE users SET email = %s WHERE username = %s RETURNING id, username, email",
                (new_email, current_user)
            )
        elif new_password is not None:
            # Only updating the password; hash the new password.
            password_hash = generate_password_hash(new_password)
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE username = %s RETURNING id, username, email",
                (password_hash, current_user)
            )
        
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        
        conn.commit()
        updated_user = {
            "id": row[0],
            "username": row[1],
            "email": row[2]
        }
    except Exception as e:
        print("Error updating profile:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    
    return jsonify(updated_user), 200

#Delete User Profile
@app.route("/profile", methods=["DELETE"])
@jwt_required()
def delete_profile():
    current_user = get_jwt_identity()
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE username = %s RETURNING id, username, email", (current_user,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        conn.commit()
    except Exception as e:
        print("Error deleting user:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({
        "message": f"User '{current_user}' deleted",
        "user": {
            "id": row[0],
            "username": row[1],
            "email": row[2]
        }
    }), 200

#Forgot PAssword Endpoint
@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    username = data.get("username")
    
    if not username:
        return jsonify({"error": "Username is required"}), 400

    # Look up the user in the database
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

    # Generate a reset token valid for 15 minutes (900 seconds)
    token = serializer.dumps(username, salt="password-reset-salt")
    # For testing, we'll just return the token.
    # In production, you'd send this in an email.
    return jsonify({"reset_token": token, "message": "Use this token with /reset-password within 15 minutes"}), 200

#Password Reset Endpoint
@app.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    token = data.get("token")
    new_password = data.get("new_password")
    
    if not token or not new_password:
        return jsonify({"error": "Token and new password are required"}), 400

    try:
        # Try to load the username from the token (expires in 15 minutes)
        username = serializer.loads(token, salt="password-reset-salt", max_age=900)
    except SignatureExpired:
        return jsonify({"error": "The reset token has expired"}), 400
    except BadSignature:
        return jsonify({"error": "Invalid reset token"}), 400

    # Hash the new password
    new_password_hash = generate_password_hash(new_password)

    # Update the user's password in the database
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

#Request Verification Endpoint
@app.route("/request-verification", methods=["POST"])
@jwt_required()
def request_verification():
    # Get the current username from the JWT token
    username = get_jwt_identity()
    
    # Generate a verification token that is valid for one hour (3600 seconds)
    token = serializer.dumps(username, salt="email-verification-salt")
    
    # In production, you’d send this token via email. For now, return it in the response.
    return jsonify({"verification_token": token, "message": "Use this token with /verify-email within one hour"}), 200

#Verify Email Endpoint
@app.route("/verify-email", methods=["POST"])
def verify_email():
    data = request.get_json()
    token = data.get("token")
    
    if not token:
        return jsonify({"error": "Token is required"}), 400
    
    try:
        # Attempt to retrieve the username from the token; token expires in 1 hour.
        username = serializer.loads(token, salt="email-verification-salt", max_age=3600)
    except SignatureExpired:
        return jsonify({"error": "The verification token has expired"}), 400
    except BadSignature:
        return jsonify({"error": "Invalid verification token"}), 400

    # Update the user's email verification status in the database
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

#User Admin Endpoints
@app.route("/admin/users", methods=["GET"])
@jwt_required()
def admin_list_users():
    current_user = get_jwt_identity()
    if current_user != "admin":
        return jsonify({"error": "Admin privileges required"}), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cur = conn.cursor()
    try:
        cur.execute("SELECT id, username, email, is_verified, created_at FROM users")
        rows = cur.fetchall()
        users_list = []
        for row in rows:
            users_list.append({
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "is_verified": row[3],
                "created_at": row[4].isoformat() if row[4] else None
            })
    except Exception as e:
        print("Error listing users:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify(users_list), 200

@app.route("/admin/users/<string:username>", methods=["DELETE"])
@jwt_required()
def admin_delete_user(username):
    current_user = get_jwt_identity()
    if current_user != "admin":
        return jsonify({"error": "Admin privileges required"}), 403
    if username == "admin":
        return jsonify({"error": "Cannot delete admin user"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE username = %s RETURNING id, username, email", (username,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "User not found"}), 404
        conn.commit()
    except Exception as e:
        print("Error deleting user:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()
    return jsonify({
        "message": f"User '{username}' deleted",
        "user": {"id": row[0], "username": row[1], "email": row[2]}
    }), 200




@app.route("/posters/upload", methods=["POST"])
@jwt_required()
def create_poster_with_photo():
    # Get text fields from form data
    title = request.form.get("title")
    description = request.form.get("description")

    if not title:
        return jsonify({"error": "Title is required"}), 400

    # Get the file from the request (if provided)
    file_obj = request.files.get("photo")

    photo_url = None
    if file_obj:
        # Generate a unique filename using uuid
               try:
            # Upload the file to the bucket and return its public URL
            photo_url = upload_file_to_bucket(file_obj, BUCKET_NAME, filename)
        except Exception as e:
            print("Error uploading file:", e)
            return jsonify({"error": "Failed to upload image"}), 500

    # Insert the poster details into the database
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

def upload_file_to_bucket(file_obj, bucket_name, destination_blob_name):
    """Uploads a file to a Google Cloud Storage bucket and returns its public URL."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    
    # Upload file contents; stream it from the uploaded file object
    blob.upload_from_file(file_obj, content_type=file_obj.content_type)
    
    # Make the file publicly accessible
    blob.make_public()
    
    return blob.public_url

if __name__ == "__main__":
    # Read the port from the environment, default to 8080 if not set
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
