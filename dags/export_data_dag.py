from datetime import datetime, timedelta
import sys
from airflow import DAG
from airflow.operators.python import PythonOperator

# Proje ana dizinini Python path'ine ekle (src klasörünün bir üstü)
sys.path.append("/opt/projects/charging-mesh")

from src.exporters.exporter import export_all_tables

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
        "03_charging_mesh_data_exporter",
        default_args=default_args,
        description="Her tabloyu kendi adıyla CSV, JSON ve SQL olarak ayrı ayrı dışarı aktarır",
        schedule_interval="@daily",
        tags=['charging_mesh', 'epdk', 'export'],
        start_date=datetime(2026, 1, 1),
        catchup=False,
) as dag:
    run_export = PythonOperator(
        task_id="export_all_tables",
        python_callable=export_all_tables,
    )