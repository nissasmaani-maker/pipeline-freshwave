
from flask import Flask, jsonify
import sqlite3
import pandas as pd

app = Flask(__name__)


# 1. Vérifier que l'API fonctionne
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "OK"})


# 2. Afficher les 100 premières ventes
@app.route("/sales", methods=["GET"])
def sales():
    conn = sqlite3.connect("business_data.db")

    df = pd.read_sql_query(
        "SELECT * FROM final_consolidated_data LIMIT 100", conn
    )

    conn.close()
    return jsonify(df.to_dict(orient="records"))


# 3. Afficher le CA total par ville
@app.route("/sales-by-city", methods=["GET"])
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

