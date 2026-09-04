import os
import csv
import json
import shutil
import zipfile
import requests
import psycopg2
from src.config import settings


def format_sql_value(val):
    """SQL insert ifadeleri için veri tiplerine göre güvenli biçimlendirme yapar."""
    if val is None:
        return "NULL"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    else:
        escaped = str(val).replace("'", "''")
        return f"'{escaped}'"


def create_zip_archives(base_output_dir):
    """csv, json ve sql klasörlerini sırasıyla zip haline getirir."""
    folders = ["csv", "json", "sql"]
    zip_files = {}

    for folder in folders:
        folder_path = os.path.join(base_output_dir, folder)
        zip_path = os.path.join(base_output_dir, f"{folder}.zip")

        if os.path.exists(folder_path):
            shutil.make_archive(zip_path.replace(".zip", ""), 'zip', folder_path)
            zip_files[folder] = zip_path

    return zip_files


def upload_to_bunnycdn(zip_files):
    storage_zone = os.getenv("BUNNY_STORAGE_ZONE", "sabrigunes")
    access_key = os.getenv("BUNNY_ACCESS_KEY")

    if not access_key:
        print("BunnyCDN Access Key (.env) bulunamadı, yükleme atlandı.")
        return

    # Bölge öneki yerine doğrudan ana BunnyCDN storage adresini kullanıyoruz
    host = "storage.bunnycdn.com"

    for folder_type, local_path in zip_files.items():
        if not os.path.exists(local_path):
            continue

        remote_filename = f"{folder_type}.zip"
        url = f"https://{host}/{storage_zone}/datasets/2/{remote_filename}"

        headers = {
            "AccessKey": access_key,
            "Content-Type": "application/octet-stream"
        }

        try:
            with open(local_path, "rb") as f:
                response = requests.put(url, data=f, headers=headers)
                if response.status_code in [200, 201]:
                    print(f"Yüklendi (BunnyCDN): datasets/2/{remote_filename}")
                else:
                    print(f"Yükleme hatası ({remote_filename}): {response.status_code} - {response.text}")
        except Exception as e:
            print(f"BunnyCDN bağlantı hatası ({remote_filename}): {e}")


def export_all_tables():
    base_output_dir = "/opt/airflow/exports"
    os.makedirs(base_output_dir, exist_ok=True)

    # Eski dosya ve klasörleri temizle
    for filename in os.listdir(base_output_dir):
        file_path = os.path.join(base_output_dir, filename)
        try:
            if os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                os.remove(file_path)
        except Exception as e:
            print(f"Temizlenemedi {file_path}: {e}")

    # Formatlara özel alt klasörler
    csv_dir = os.path.join(base_output_dir, "csv")
    json_dir = os.path.join(base_output_dir, "json")
    sql_dir = os.path.join(base_output_dir, "sql")

    os.makedirs(csv_dir, exist_ok=True)
    os.makedirs(json_dir, exist_ok=True)
    os.makedirs(sql_dir, exist_ok=True)

    tables = [
        "cities", "districts", "neighborhoods",
        "ev_brands", "ev_connectors", "ev_electricity_companies",
        "ev_operators", "ev_sockets", "ev_stations"
    ]

    db_host = "postgres" if settings.DB_HOST in ["localhost", "127.0.0.1"] else settings.DB_HOST

    conn = psycopg2.connect(
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=db_host,
        port=settings.DB_PORT
    )
    cursor = conn.cursor()

    for table in tables:
        try:
            cursor.execute(f"SELECT * FROM public.{table}")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

            # 1. CSV Kaydı
            csv_path = os.path.join(csv_dir, f"{table}.csv")
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(rows)

            # 2. JSON Kaydı
            json_path = os.path.join(json_dir, f"{table}.json")
            data_list = [dict(zip(columns, row)) for row in rows]
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data_list, f, ensure_ascii=False, indent=4, default=str)

            # 3. SQL Kaydı
            sql_path = os.path.join(sql_dir, f"{table}.sql")
            with open(sql_path, "w", encoding="utf-8") as f:
                for row in rows:
                    values_str = ", ".join(format_sql_value(val) for val in row)
                    f.write(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({values_str});\n")

        except Exception as e:
            print(f"Hata oluştu ({table}): {e}")
            conn.rollback()

    cursor.close()
    conn.close()

    # Klasörleri zip arşivine dönüştür
    print("Dosyalar zip arşivine sıkıştırılıyor...")
    zip_files = create_zip_archives(base_output_dir)

    # BunnyCDN'e gönder
    print("Zip dosyaları BunnyCDN'e yükleniyor...")
    upload_to_bunnycdn(zip_files)