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

from src.transformers.transformer import StationETLTransformer

# Birinci DAG ile aynı Dataset tanımı
epdk_raw_dataset = Dataset("mongodb://raw_data/charging")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def run_transformation(**context):
    print("MongoDB'deki ham verileri işleme ve PostgreSQL'e aktarma (Transform & Load) süreci başlatılıyor...")
    transformer = StationETLTransformer()
    transformer.transform_and_load()
    print("Transform ve PostgreSQL aktarım süreci başarıyla tamamlandı.")

with DAG(
    'epdk_transform_pipeline',
    default_args=default_args,
    description='MongoDB Ham Verilerini PostgreSQL e Dönüştürme ve Yükleme',
    schedule=[epdk_raw_dataset],  # <--- Birinci DAG bittiğinde tetiklenir!
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['epdk', 'transform', 'postgres'],
) as dag:

    transform_task = PythonOperator(
        task_id='transform_and_load_postgres',
        python_callable=run_transformation,
    )