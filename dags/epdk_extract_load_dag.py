import os
import sys
import urllib.parse
from datetime import datetime, timedelta
from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator
from pymongo import MongoClient

# Projenin ana dizinini Python path'ine ekliyoruz
PROJECT_DIR = '/opt/projects/charging-mesh'
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from src.extractors.api_extractor import EPDKEpisodExtractor

# Ortak Dataset tanımı (İki DAG arasında köprü kurar)
epdk_raw_dataset = Dataset("mongodb://raw_data/charging")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def run_extraction_to_raw(**context):
    print("EPDK API'den ham veri çekme ve ham katmana (MongoDB) kaydetme süreci başlatılıyor...")

    # 1. Extractor'ı başlat ve veriyi çek
    extractor = EPDKEpisodExtractor()
    raw_data = extractor.fetch_raw_data()

    if not raw_data:
        print("Uyarı: API'den hiç veri dönmedi!")
        return

    # 2. MongoDB'ye bağlan ve kaydet
    mongo_host = "mongodb"
    mongo_port = "27017"
    mongo_user = "mongo_admin"
    mongo_password = "yYiBT+Q9zCGGz]@x"
    db_name = "raw_data"
    collection_name = "charging"

    encoded_password = urllib.parse.quote_plus(mongo_password)
    mongo_uri = f"mongodb://{mongo_user}:{encoded_password}@{mongo_host}:{mongo_port}/?authSource=admin"

    client = MongoClient(mongo_uri)

    db = client[db_name]
    collection = db[collection_name]

    # Kayıt işlemi
    if isinstance(raw_data, list) and len(raw_data) > 0:
        collection.insert_many(raw_data)
        print(f"Toplam {len(raw_data)} adet kayıt MongoDB ({db_name}.{collection_name}) veritabanına başarıyla kaydedildi.")
    else:
        print("Kaydedilecek uygun formatta veri bulunamadı.")

    client.close()


with DAG(
        '01_charging_mesh_extractor',
        default_args=default_args,
        description='EPDK Ham Veri Çekme ve Kaydetme (Her 2 saatte bir)',
        schedule_interval='0 */2 * * *',
        start_date=datetime(2026, 1, 1),
        catchup=False,
        tags=['charging_mesh','epdk', 'extract', 'load'],
) as dag:
    extract_load_task = PythonOperator(
        task_id='extract_and_load_raw_data',
        python_callable=run_extraction_to_raw,
        outlets=[epdk_raw_dataset]  # Bu görev bittiğinde ikinci DAG otomatik tetiklenir
    )