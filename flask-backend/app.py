from flask import Flask, jsonify, request
import os
import psycopg2

app = Flask(__name__)

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
    return "Hello from Flask API on Cloud Run!"

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
