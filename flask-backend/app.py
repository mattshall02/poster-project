from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import os
import psycopg2

app = Flask(__name__)

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key")
jwt = JWTManager(app)

# Configure the secret key for signing JWTs (in production, use a secure key and manage via environment variables)
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "your-secret-key")  # Change "your-secret-key" to a secure key
jwt = JWTManager(app)



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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
