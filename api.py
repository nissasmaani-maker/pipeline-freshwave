from flask import Flask, jsonify, request
import sqlite3
import pandas as pd
from functools import wraps
import os

####
from dotenv import load_dotenv
load_dotenv()
VALID_KEYS = {k.strip() for k in os.environ['API_KEYS'].split(',') if k.strip()}
#####

app = Flask(__name__)

#####
def require_api_key(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if not key or not any(secrets.compare_digest(key, k) for k in VALID_KEYS):
            return jsonify(error="Clé API invalide ou absente"), 401
        return f(*args, **kwargs)
    return wrapper
#####

# 1. Vérifier que l'API fonctionne
@app.route("/health", methods=["GET"]) 
@require_api_key
def health():
    return jsonify({"status": "OK"})


# 2. Afficher les 100 premières ventes
@app.route("/sales", methods=["GET"])
#####
@require_api_key
#####
def sales():
    conn = sqlite3.connect("business_data.db")

    df = pd.read_sql_query(
        "SELECT * FROM final_consolidated_data LIMIT 100", conn
    )

    conn.close()
    return jsonify(df.to_dict(orient="records"))


# 3. Afficher le CA total par ville
@app.route("/sales-by-city", methods=["GET"])
#####
@require_api_key
#####
def sales_by_city():
    conn = sqlite3.connect("business_data.db")

    df = pd.read_sql_query("""
        SELECT city, SUM(total_revenue) AS total_revenue
        FROM final_consolidated_data
        GROUP BY city
        ORDER BY total_revenue DESC
    """, conn)

    conn.close()
    return jsonify(df.to_dict(orient="records"))


if __name__ == "__main__":
    app.run(debug=True)

