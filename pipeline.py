
import pandas as pd
import sqlite3
import requests

# Dates du projet
START_DATE = "2024-05-01"
END_DATE = "2024-08-31"

# Coordonnées des villes
CITY_COORDS = {
    "Paris": (48.8566, 2.3522),
    "Lyon": (45.7640, 4.8357),
    "Marseille": (43.2965, 5.3698),
    "Bordeaux": (44.8378, -0.5792),
    "Lille": (50.6292, 3.0573),
    "Nantes": (47.2184, -1.5536),
    "Toulouse": (43.6047, 1.4442),
    "Nice": (43.7102, 7.2620)
}


# ÉTAPE 2 : INITIALISATION SQLITE
def init_database():
    conn = sqlite3.connect("business_data.db")

    for fichier in ["stores.sql", "products.sql"]:
        with open(fichier, "r", encoding="utf-8") as file:
            conn.executescript(file.read())

    conn.close()
    print("Base de données initialisée !")


# ÉTAPE 3 : RÉCUPÉRATION DE LA MÉTÉO
def fetch_weather_for_city(city, lat, lon):

    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "timezone": "Europe/Paris"
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    df = pd.DataFrame(response.json()["daily"])

    df = df.rename(columns={
        "time": "date",
        "temperature_2m_max": "temp_max",
        "temperature_2m_min": "temp_min",
        "precipitation_sum": "precipitation",
        "wind_speed_10m_max": "wind_speed"
    })

    df["city"] = city
    df["date"] = pd.to_datetime(df["date"])

    return df


# ÉTAPE 3 : EXTRACTION DES DONNÉES
def extract():

    # Charger les CSV
    sales = pd.read_csv("sales.csv")
    marketing = pd.read_csv("marketing_campaigns.csv")

    # Charger les tables SQLite
    conn = sqlite3.connect("business_data.db")
    stores = pd.read_sql_query("SELECT * FROM stores", conn)
    products = pd.read_sql_query("SELECT * FROM products", conn)
    conn.close()

    # Récupérer la météo des 8 villes
    weather_list = []

    for city, (lat, lon) in CITY_COORDS.items():
        weather = fetch_weather_for_city(city, lat, lon)
        weather_list.append(weather)

    # Regrouper les données météo
    weather = pd.concat(weather_list, ignore_index=True)

    print("Villes récupérées :", weather["city"].nunique())
    print("Données météo :", weather.shape)
    print("Date minimale :", weather["date"].min())
    print("Date maximale :", weather["date"].max())

    data = {
        "sales": sales,
        "marketing": marketing,
        "stores": stores,
        "products": products,
        "weather": weather
    }

    return data


# ÉTAPE 4 : TRANSFORMATION DES DONNÉES
def transform(data):

    # 1. Convertir les dates
    data["sales"]["date"] = pd.to_datetime(data["sales"]["date"])
    data["marketing"]["date"] = pd.to_datetime(data["marketing"]["date"])
    data["weather"]["date"] = pd.to_datetime(data["weather"]["date"])

    # 2. Filtrer les données
    data["sales"] = data["sales"][
        data["sales"]["date"].between(START_DATE, END_DATE)
    ]

    data["marketing"] = data["marketing"][
        data["marketing"]["date"].between(START_DATE, END_DATE)
    ]

    # 3. Fusionner ventes, magasins et produits
    sales = pd.merge(data["sales"], data["stores"], on="store_id")
    sales = pd.merge(sales, data["products"], on="product_id")

    # 4. Ajouter la météo
    sales = pd.merge(
        sales, data["weather"],
        on=["date", "city"], how="left"
    )

    # 5. Identifier les week-ends
    sales["is_weekend"] = sales["date"].dt.day_of_week >= 5

    # 6. Catégories de température
    sales["temp_bucket"] = pd.cut(
        sales["temp_max"],
        [-100, 20, 25, 30, 100],
        labels=["<=20°C", "20-25°C", "25-30°C", ">30°C"]
    )

    # 7. Catégories de précipitations
    sales["rain_bucket"] = pd.cut(
        sales["precipitation"],
        [-0.1, 0, 5, 20, float("inf")],
        labels=["0 mm", "0-5 mm", "5-20 mm", ">20 mm"]
    )

    # 8. Agréger les ventes
    sales_agg = sales.groupby(
        ["date", "store_id", "city", "product_id"],
        observed=True
    ).agg(
        total_revenue=("revenue", "sum"),
        total_quantity=("quantity_sold", "sum"),
        nb_transactions=("sale_id", "count")
    ).reset_index()


    # ÉTAPE 5 : ANALYSE DES DONNÉES

    # 1. CA moyen par température
    temp_analysis = sales.groupby(
        ["temp_bucket", "category"], observed=True
    ).agg(
        avg_revenue=("revenue", "mean")
    ).reset_index()

    # 2. CA moyen par précipitations
    rain_analysis = sales.groupby(
        ["rain_bucket", "category"], observed=True
    ).agg(
        avg_revenue=("revenue", "mean")
    ).reset_index()

    # 3. Analyse des campagnes marketing
    marketing_agg = data["marketing"].groupby(
        ["date", "city"]
    ).agg(
        marketing_spend=("marketing_spend", "sum"),
        nb_campaigns=("campaign_id", "count")
    ).reset_index()

    daily_sales = sales.groupby(["date", "city"]).agg(
        total_revenue=("revenue", "sum")
    ).reset_index()

    marketing_analysis = pd.merge(
        daily_sales, marketing_agg,
        on=["date", "city"], how="left"
    )

    marketing_analysis[["marketing_spend", "nb_campaigns"]] = (
        marketing_analysis[["marketing_spend", "nb_campaigns"]].fillna(0)
    )

    marketing_analysis["has_campaign"] = (
        marketing_analysis["nb_campaigns"] > 0
    )

    marketing_comparison = marketing_analysis.groupby(
        "has_campaign"
    ).agg(
        avg_revenue=("total_revenue", "mean"),
        avg_spend=("marketing_spend", "mean"),
        avg_campaigns=("nb_campaigns", "mean")
    ).reset_index()

    # 4. CA total par ville
    city_analysis = sales.groupby("city").agg(
        total_revenue=("revenue", "sum")
    ).reset_index()

    city_analysis = city_analysis.sort_values(
        "total_revenue", ascending=False
    )

    # 5. Comparaison week-end / semaine
    weekend_daily = sales.groupby(
        ["date", "store_id", "is_weekend"]
    ).agg(
        total_revenue=("revenue", "sum")
    ).reset_index()

    weekend_analysis = weekend_daily.groupby(
        "is_weekend"
    ).agg(
        avg_revenue=("total_revenue", "mean")
    ).reset_index()


    # ÉTAPE 6 : CRÉATION DU DATASET FINAL

    # Partir des ventes agrégées
    final = pd.merge(
        sales_agg,
        data["stores"][["store_id", "store_name"]],
        on="store_id",
        how="left"
    )

    # Ajouter les informations produits
    final = pd.merge(
        final,
        data["products"][["product_id", "product_name", "category"]],
        on="product_id",
        how="left"
    )

    # Ajouter les données météo
    final = pd.merge(
        final,
        data["weather"][["date", "city", "temp_max", "temp_min",
                         "precipitation", "wind_speed"]],
        on=["date", "city"],
        how="left"
    )

    # Ajouter les données marketing
    final = pd.merge(
        final,
        marketing_agg,
        on=["date", "city"],
        how="left"
    )

    # Remplacer les valeurs marketing manquantes
    final[["marketing_spend", "nb_campaigns"]] = (
        final[["marketing_spend", "nb_campaigns"]].fillna(0)
    )

    # Renommer les colonnes météo
    final = final.rename(columns={
        "temp_max": "temperature_max",
        "temp_min": "temperature_min",
        "precipitation": "precipitation_sum",
        "wind_speed": "wind_speed_max"
    })

    # Ajouter les catégories météo et le week-end
    final["is_weekend"] = final["date"].dt.day_of_week >= 5

    final["temp_bucket"] = pd.cut(
        final["temperature_max"],
        [-100, 20, 25, 30, 100],
        labels=["<=20°C", "20-25°C", "25-30°C", ">30°C"]
    )

    final["rain_bucket"] = pd.cut(
        final["precipitation_sum"],
        [-0.1, 0, 5, 20, float("inf")],
        labels=["0 mm", "0-5 mm", "5-20 mm", ">20 mm"]
    )

    # Stocker les résultats
    data["sales"] = sales
    data["sales_agg"] = sales_agg
    data["temp_analysis"] = temp_analysis
    data["rain_analysis"] = rain_analysis
    data["marketing_analysis"] = marketing_analysis
    data["marketing_comparison"] = marketing_comparison
    data["city_analysis"] = city_analysis
    data["weekend_analysis"] = weekend_analysis
    data["final"] = final

    # Afficher les analyses
    print("\nAnalyse température :")
    print(temp_analysis)

    print("\nAnalyse pluie :")
    print(rain_analysis)

    print("\nAnalyse marketing :")
    print(marketing_comparison)

    print("\nAnalyse par ville :")
    print(city_analysis)

    print("\nAnalyse week-end :")
    print(weekend_analysis)

    return data


# ÉTAPE 6 : SAUVEGARDE DANS SQLITE
def load(data):

    conn = sqlite3.connect("business_data.db")

    data["final"].to_sql(
        "final_consolidated_data",
        conn,
        if_exists="replace",
        index=False
    )

    conn.close()

    print("\nDonnées sauvegardées avec succès !")


# FONCTION PRINCIPALE
def main():

    init_database()
    data = extract()
    data = transform(data)
    load(data)


if __name__ == "__main__":
    main()

