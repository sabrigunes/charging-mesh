import logging
import urllib.parse
from pymongo import MongoClient
from src.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MongoRawLoader:
    def __init__(self):
        # Şifredeki özel karakterleri RFC 3986 standardına göre encode ediyoruz
        encoded_password = urllib.parse.quote_plus(settings.MONGO_PASSWORD)

        # Bağlantı adresini güvenli bir şekilde oluşturuyoruz
        mongo_url = f"mongodb://{settings.MONGO_USER}:{encoded_password}@{settings.MONGO_HOST}:{settings.MONGO_PORT}/"

        self.client = MongoClient(mongo_url)

        # Doğrudan .env'den gelen isimleri veya varsayılan değerleri kullanıyoruz
        # (Settings sınıfında bu alanlar tanımlı olmadığı için hata alıyorduk)
        self.db = self.client["raw_data"]
        self.collection = self.db["charging"]

    def save_raw_data(self, response_json: dict):
        try:
            logger.info("Ham veri MongoDB'ye kaydediliyor...")
            result = self.collection.insert_one(response_json)
            logger.info(f"Ham veri başarıyla MongoDB'ye yazıldı. Document ID: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"MongoDB'ye yazılırken hata oluştu: {e}")
            raise