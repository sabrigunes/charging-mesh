import json
import logging
import requests
from typing import List, Dict, Any, Optional
from src.models.station import StationModel

# Basit bir loglama ayarı
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EPDKEpisodExtractor:
    def __init__(self, file_path: Optional[str] = None):
        self.url = "https://apigateway.epdk.gov.tr/sarjIstasyonlari"
        self.headers = {
            'Content-Type': 'application/json'
        }
        # Eğer test için dosya yolu verilirse oradan okunur, verilmezse doğrudan API'ye gidilir
        self.file_path = file_path

    def fetch_raw_response(self) -> Dict[Any, Any]:
        """
        Veriyi öncelikli olarak belirtilen yerel dosyadan (varsa), yoksa doğrudan EPDK API'sinden çeker.
        """
        try:
            if self.file_path:
                logger.info(f"Ham veri yerel dosyadan ({self.file_path}) okunuyor...")
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.info(f"Ham veri doğrudan EPDK API'sinden çekiliyor: {self.url}")
                response = requests.post(self.url, headers=self.headers, json={}, timeout=30)
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.error(f"Veri çekilirken/okunurken hata oluştu: {e}")
            raise

    def fetch_raw_data(self) -> List[Dict[Any, Any]]:
        """
        Yanıt objesini çözer ve 'data' içerisindeki şarj istasyonu listesini döner.
        """
        try:
            response_json = self.fetch_raw_response()
            stations_data = response_json.get("data", [])

            logger.info(f"Başarıyla {len(stations_data)} adet ham kayıt yüklendi.")
            return stations_data

        except Exception as e:
            logger.error(f"Ham veri işlenirken hata oluştu: {e}")
            raise

    def fetch_and_validate(self) -> List[StationModel]:
        """
        Ham veriyi çeker ve Pydantic modellerimizle valide ederek temiz bir liste döner.
        """
        raw_data = self.fetch_raw_data()
        validated_stations = []

        for index, item in enumerate(raw_data):
            try:
                station = StationModel(**item)
                validated_stations.append(station)
            except Exception as e:
                logger.warning(f"Kayıt doğrulanamadı (Index: {index}, Hata: {e})")

        logger.info(f"Toplam {len(validated_stations)} kayıt başarıyla valide edildi.")
        return validated_stations