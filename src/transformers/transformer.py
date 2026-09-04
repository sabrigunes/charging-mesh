import json
import logging
import urllib.parse
import psycopg2
from pymongo import MongoClient
from thefuzz import process
from src.config import settings
from src.models.station import StationModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StationETLTransformer:
    def __init__(self):
        encoded_password = urllib.parse.quote_plus(settings.MONGO_PASSWORD)
        mongo_url = f"mongodb://{settings.MONGO_USER}:{encoded_password}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/"
        print(mongo_url)
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

        self.pg_conn_core = psycopg2.connect(
            host=settings.DB_HOST_CORE,
            database=settings.DB_NAME_CORE,
            user=settings.DB_USER_CORE,
            password=settings.DB_PASSWORD_CORE,
            port=settings.DB_PORT_CORE
        )

        self.pg_conn.autocommit = False

        # Coğrafi verileri hızlı eşleme için önbelleğe alıyoruz
        self.cache_geo_data()

    def tr_upper(self, text: str) -> str:
        """Türkçe karakter sorunsuz büyük harf dönüşümü."""
        if not text:
            return ""
        return (
            text.replace("i", "İ")
            .replace("ı", "I")
            .replace("ç", "Ç")
            .replace("ş", "Ş")
            .replace("ğ", "Ğ")
            .replace("ü", "Ü")
            .replace("ö", "Ö")
            .upper()
        )

    def cache_geo_data(self):
        """Veritabanındaki şehir, ilçe ve mahalleleri belleğe yükleyerek her satırda SQL sorgusu atılmasını önler."""
        cursor = self.pg_conn_core.cursor()
        try:
            cursor.execute("SELECT id, name FROM public.cities")
            self.cities_cache = {self.tr_upper(row[1]): row[0] for row in cursor.fetchall()}

            cursor.execute("SELECT id, city_id, name FROM public.districts")
            self.districts_cache = {}
            for row in cursor.fetchall():
                d_id, c_id, d_name = row[0], row[1], self.tr_upper(row[2])
                if c_id not in self.districts_cache:
                    self.districts_cache[c_id] = {}
                self.districts_cache[c_id][d_name] = d_id

            cursor.execute("SELECT id, district_id, name FROM public.neighborhoods")
            self.neighborhoods_cache = {}
            for row in cursor.fetchall():
                n_id, d_id, n_name = row[0], row[1], self.tr_upper(row[2])
                if d_id not in self.neighborhoods_cache:
                    self.neighborhoods_cache[d_id] = {}
                self.neighborhoods_cache[d_id][n_name] = n_id

            logger.info("Coğrafi referans verileri (Şehir, İlçe, Mahalle) başarıyla belleğe yüklendi.")
        except Exception as e:
            logger.warning(f"Coğrafi veriler önbelleğe alınırken hata oluştu (Tablolar henüz olmayabilir): {e}")
            self.cities_cache = {}
            self.districts_cache = {}
            self.neighborhoods_cache = {}
        finally:
            cursor.close()

    def parse_address_geography(self, address: str):
        """
        Hiyerarşik Adres Çözümleme Algoritması (Güncellenmiş):
        1. Adres metninin sonundaki şehir bilgisini (/ sonrasını) baz alarak şehri tespit et.
        2. Bulunan şehre ait ilçeleri tarayarak adreste geçen ilçeyi bul.
        3. Bulunan ilçeye ait mahalleleri tarayarak adreste geçen mahalleyi bul.
        """
        if not address:
            return None, None, None
 
        norm_address = self.tr_upper(address)
        city_id, district_id, neighborhood_id = None, None, None
        matched_city_name, matched_district_name, matched_neigh_name = None, None, None

        # 1. Adım: Şehri Tespit Et (Önce son "/" karakterinden sonrasına bak)
        if "/" in address:
            last_part = norm_address.split("/")[-1].strip()
            for c_name, c_id in self.cities_cache.items():
                if c_name in last_part or last_part in c_name:
                    city_id = c_id
                    matched_city_name = c_name 
                    break
 
        if not city_id:
            logger.info(f"[GEO] Şehir bulunamadı | Adres: {address}")
            return None, None, None

        # 2. Adım: Şehre ait ilçeleri al ve adreste geçen ilçeyi tespit et
        district_map = self.districts_cache.get(city_id, {})
        for d_name, d_id in district_map.items():
            if d_name in norm_address:
                district_id = d_id
                matched_district_name = d_name
                break

        if not district_id:
            logger.info(f"[GEO] İlçe bulunamadı | Şehir: {matched_city_name} | Adres: {address}")
            return city_id, None, None

        # 3. Adım: İlçeye ait mahalleleri al ve adreste geçen mahalleyi tespit et
        neighborhood_map = self.neighborhoods_cache.get(district_id, {})
        if neighborhood_map:
            for n_name, n_id in neighborhood_map.items():
                clean_n = n_name.replace(" MAHALLESİ", "").replace(" MAH.", "").strip()
                if clean_n and clean_n in norm_address:
                    neighborhood_id = n_id
                    matched_neigh_name = n_name
                    break

            if not neighborhood_id:
                choices = list(neighborhood_map.keys())
                match_result = process.extractOne(norm_address, choices)
                if match_result and match_result[1] >= 85:
                    matched_neigh_name = match_result[0]
                    neighborhood_id = neighborhood_map[matched_neigh_name]

        return city_id, district_id, neighborhood_id

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
        cursor = self.pg_conn.cursor()
        total_processed = 0

        try:
            logger.info("MongoDB'den ham belgeler taranıyor...")
            cursor_mongo = self.mongo_collection.find({})

            for doc in cursor_mongo:
                doc_id = doc["_id"]

                # Esnek veri yapısı kontrolü ("data", "stations" veya direkt liste/belge)
                stations_data = doc.get("data") or doc.get("stations") or (doc if isinstance(doc, list) else None)

                if not stations_data:
                    if isinstance(doc, dict) and len(doc) > 1:
                        stations_data = [doc]
                    else:
                        logger.warning(f"Belge formatı geçersiz (ID: {doc_id}), atlanıyor.")
                        continue

                if isinstance(stations_data, dict):
                    stations_data = [stations_data]


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

                        # Adres üzerinden Hiyerarşik Coğrafi ID'leri Çözümle (City, District, Neighborhood)
                        city_id, district_id, neighborhood_id = self.parse_address_geography(station_model.adres)

                        station_num_str = "".join(filter(str.isdigit, station_model.station_no))
                        station_number = int(station_num_str) if station_num_str else index

                        # 3. İstasyon Kaydı (ev_stations - Coğrafi ID'ler eklendi)
                        cursor.execute("""
                                       INSERT INTO public.ev_stations (number, name, address, latitude, longitude,
                                                                       is_public, is_green, operator_id, brand_id,
                                                                       electricity_company_id, dist_approval_no,
                                                                       city_id, district_id, neighborhood_id)
                                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                               %s) ON CONFLICT ("number") DO
                                       UPDATE SET
                                           name = EXCLUDED.name,
                                           address = EXCLUDED.address,
                                           latitude = EXCLUDED.latitude,
                                           longitude = EXCLUDED.longitude,
                                           brand_id = EXCLUDED.brand_id,
                                           electricity_company_id = EXCLUDED.electricity_company_id,
                                           city_id = EXCLUDED.city_id,
                                           district_id = EXCLUDED.district_id,
                                           neighborhood_id = EXCLUDED.neighborhood_id
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
                                           station_model.dagitim_sirketi_olumlu_gorus_belge_numarasi,
                                           city_id,
                                           district_id,
                                           neighborhood_id
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