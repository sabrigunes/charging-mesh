import sys
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.datasets import Dataset
from airflow.operators.python import PythonOperator

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
    extractor = EPDKEpisodExtractor()
    # Ham veriyi çekip MongoDB'ye kaydeden fonksiyonunuzu burada çağırabilirsiniz:
    # raw_data = extractor.fetch_raw_data()
    # mongo_client.save(raw_data)
    print("Ham veri başarıyla kaydedildi.")

with DAG(
    'epdk_extract_load_pipeline',
    default_args=default_args,
    description='EPDK Ham Veri Çekme ve Kaydetme (Her 2 saatte bir)',
    schedule_interval='0 */2 * * *',
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['epdk', 'extract', 'mongodb'],
) as dag:

    extract_load_task = PythonOperator(
        task_id='extract_and_load_raw_data',
        python_callable=run_extraction_to_raw,
        outlets=[epdk_raw_dataset]  # <--- Bu görev bittiğinde ikinci DAG otomatik tetiklenir!
    )