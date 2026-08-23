import logging
import urllib.parse
import json
import psycopg2
from src.config import settings
from src.models.station import StationModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StationETLTransformer:
    def __init__(self):
        encoded_password = urllib.parse.quote_plus(settings.MONGO_PASSWORD)
        mongo_url = f"mongodb://{settings.MONGO_USER}:{encoded_password}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/"

        self.mongo_client = MongoClient(mongo_url)
        self.mongo_db = self.mongo_client["raw_data"]
        self.mongo_collection = self.mongo_db["charging"]

        self.pg_conn = psycopg2.connect(
            host=settings.DB_HOST,
            database=settings.DB_NAME,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            port=settings.DB_PORT
        )
        self.pg_conn.autocommit = False

    def get_or_create_lookup(self, cursor, table_name, column_name, value):
        if not value:
            return None

        cursor.execute(f"SELECT id FROM public.{table_name} WHERE {column_name} = %s", (value,))
        result = cursor.fetchone()

        if result:
            return result[0]

        cursor.execute(
            f"INSERT INTO public.{table_name} ({column_name}) VALUES (%s) RETURNING id",
            (value,)
        )
        return cursor.fetchone()[0]

    def get_or_create_electricity_company(self, cursor, name, license_no):
        if not name:
            return None

        cursor.execute(
            "SELECT id FROM public.ev_electricity_companies WHERE name = %s AND (license_number = %s OR (%s IS NULL AND license_number IS NULL))",
            (name, license_no, license_no)
        )
        result = cursor.fetchone()

        if result:
            return result[0]

        cursor.execute(
            "INSERT INTO public.ev_electricity_companies (name, license_number) VALUES (%s, %s) RETURNING id",
            (name, license_no)
        )
        return cursor.fetchone()[0]

    def transform_and_load(self):
        from pymongo import MongoClient  
        cursor = self.pg_conn.cursor()
        total_processed = 0

        try:
            logger.info("MongoDB'den ham belgeler taranıyor...")
            cursor_mongo = self.mongo_collection.find({})

            for doc in cursor_mongo:
                doc_id = doc["_id"]
                if "data" not in doc:
                    logger.warning(f"Belge formatı geçersiz (ID: {doc_id}), atlanıyor.")
                    continue

                stations_data = doc["data"]
                logger.info(
                    f"MongoDB belgesi işleniyor (ID: {doc_id}), içerisindeki kayıt sayısı: {len(stations_data)}")

                success_count = 0

                for index, item in enumerate(stations_data):
                    try:
                        # 1. Pydantic ile Validasyon
                        station_model = StationModel(**item)

                        # 2. Lookup Tabloları (Dimension) Yönetimi
                        operator_id = self.get_or_create_lookup(
                            cursor, "ev_operators", "name", station_model.sarj_istasyonu_isletmecisi
                        )

                        company_id = self.get_or_create_lookup(
                            cursor, "ev_companies", "name", station_model.sarj_agi_isletmecisi_unvan
                        )

                        elec_company_id = self.get_or_create_electricity_company(
                            cursor,
                            station_model.olumlu_gorus_veren_dagitim_sirketi_lisans_unvani,
                            station_model.olumlu_gorus_veren_dagitim_sirketi_lisans_no
                        )

                        brand_id = self.get_or_create_lookup(
                            cursor, "ev_brands", "name", station_model.marka
                        )

                        station_num_str = "".join(filter(str.isdigit, station_model.station_no))
                        station_number = int(station_num_str) if station_num_str else index

                        # 3. İstasyon Kaydı (ev_stations)
                        cursor.execute("""
                                       INSERT INTO public.ev_stations (number, name, address, latitude, longitude,
                                                                       is_public, is_green, operator_id, brand_id,
                                                                       electricity_company_id, dist_approval_no)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT ("number") DO
                                       UPDATE SET
                                           name = EXCLUDED.name,
                                           address = EXCLUDED.address,
                                           latitude = EXCLUDED.latitude,
                                           longitude = EXCLUDED.longitude,
                                           brand_id = EXCLUDED.brand_id,
                                           electricity_company_id = EXCLUDED.electricity_company_id
                                           RETURNING id;
                                       """, (
                                           station_number,
                                           station_model.station_adi,
                                           station_model.adres,
                                           station_model.enlem,
                                           station_model.boylam,
                                           True if station_model.hizmet_sekli == "HALKA_ACIK" else False,
                                           True if station_model.yesil_sarj == "EVET" else False,
                                           operator_id,
                                           brand_id,
                                           elec_company_id,
                                           station_model.dagitim_sirketi_olumlu_gorus_belge_numarasi
                                       ))

                        station_db_id = cursor.fetchone()[0]

                        # 4. Soket Kayıtları (ev_sockets)
                        for socket_idx, socket in enumerate(station_model.sockets):
                            power_type = socket.socket_type  # AC veya DC
                            connector_name = socket.socket_tur  # DC_CCS, AC_TYPE2 vb.

                            cursor.execute(
                                "SELECT id FROM public.ev_connectors WHERE name = %s AND power_type = %s",
                                (connector_name, power_type)
                            )
                            conn_res = cursor.fetchone()

                            if conn_res:
                                connector_type_id = conn_res[0]
                            else:
                                cursor.execute(
                                    "INSERT INTO public.ev_connectors (power_type, name) VALUES (%s, %s) RETURNING id",
                                    (power_type, connector_name)
                                )
                                connector_type_id = cursor.fetchone()[0]

                            power_kw_val = float(socket.power_kw) if socket.power_kw else 0.0

                            cursor.execute("""
                                           INSERT INTO public.ev_sockets (station_id, number, connector_type_id,
                                                                          power_kw)
                                           VALUES (%s, %s, %s, %s)
                                           """, (
                                               station_db_id,
                                               socket_idx + 1,
                                               connector_type_id,
                                               power_kw_val
                                           ))

                        self.pg_conn.commit()
                        success_count += 1

                    except Exception as row_err:
                        self.pg_conn.rollback()
                        logger.warning(f"Kayıt aktarılamadı (Index: {index}), Hata: {row_err}")
                        print(f"\n--- HATALI / YAZILAMAYAN KAYIT (Index: {index}) ---")
                        print(json.dumps(item, ensure_ascii=False, indent=2))
                        print("-" * 50)

                if success_count > 0:
                    self.mongo_collection.delete_one({"_id": doc_id})
                    logger.info(
                        f"[BAŞARILI] Belge PostgreSQL'e aktarıldı ve MongoDB'den silindi. Document ID: {doc_id}")
                    total_processed += success_count

            logger.info(f"ETL Süreci Tamamlandı. Toplam aktarılan istasyon sayısı: {total_processed}")

        except Exception as e:
            self.pg_conn.rollback()
            logger.error(f"ETL Transform sırasında kritik hata: {e}")
            raise
        finally:
            cursor.close()
            self.pg_conn.close()
            self.mongo_client.close()


if __name__ == "__main__":
    transformer = StationETLTransformer()
    transformer.transform_and_load()