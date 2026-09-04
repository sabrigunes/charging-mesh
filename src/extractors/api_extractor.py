import json
import logging
import requests
from typing import List, Dict, Any, Optional
from src.models.station import StationModel

# Loglama ayarını daha detaylı hale getiriyoruz (zaman, seviye ve mesaj)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)


class EPDKEpisodExtractor:
    def __init__(self, file_path: Optional[str] = None):
        self.url = "https://apigateway.epdk.gov.tr/sarjIstasyonlari"
        self.headers = {
            'Content-Type': 'application/json'
        }
        self.file_path = file_path
        print("-> [INFO] EPDKEpisodExtractor başarıyla başlatıldı.")

    def fetch_raw_response(self) -> Dict[Any, Any]:
        """
        Veriyi öncelikli olarak belirtilen yerel dosyadan (varsa), yoksa doğrudan EPDK API'sinden çeker.
        """
        try:
            if self.file_path:
                print(f"-> [INFO] Ham veri yerel dosyadan okunmaya çalışılıyor: {self.file_path}")
                logger.info(f"Ham veri yerel dosyadan ({self.file_path}) okunuyor...")
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    print(f"-> [SUCCESS] Yerel dosyadan veri başarıyla okundu.")
                    return data
            else:
                print(f"-> [INFO] EPDK API'sine GET isteği gönderiliyor: {self.url}")
                logger.info(f"Ham veri doğrudan EPDK API'sinden çekiliyor: {self.url}")

                headers = {
                    'Content-Type': 'application/json'
                }

                # POST yerine Postman'in belirttiği gibi GET kullanıyoruz
                response = requests.request("GET", self.url, headers=headers, data=json.dumps({}))

                print(f"-> [INFO] API HTTP Status Code: {response.status_code}")
                response.raise_for_status()

                response_json = response.json()
                print(f"-> [SUCCESS] API'den yanıt başarıyla alındı ve JSON'a çevrildi.")
                return response_json

        except requests.exceptions.RequestException as req_err:
            print(f"-> [ERROR] API isteği sırasında hata oluştu: {req_err}")
            logger.error(f"API isteği sırasında hata oluştu: {req_err}")
            raise
        except Exception as e:
            print(f"-> [ERROR] Veri çekilirken beklenmeyen bir hata oluştu: {e}")
            logger.error(f"Veri çekilirken/okunurken hata oluştu: {e}")
            raise

    def fetch_raw_data(self) -> List[Dict[Any, Any]]:
        """
        Yanıt objesini çözer ve 'data' içerisindeki şarj istasyonu listesini döner.
        """
        try:
            print("-> [INFO] fetch_raw_data çalıştırılıyor...")
            response_json = self.fetch_raw_response()

            # Yanıtın yapısını kontrol etmek için anahtarları basalım
            print(
                f"-> [INFO] API yanıt anahtarları (keys): {list(response_json.keys()) if isinstance(response_json, dict) else 'Yanıt dict değil'}")

            stations_data = response_json.get("data", [])
            print(f"-> [SUCCESS] 'data' alanı içerisinden toplam {len(stations_data)} adet ham kayıt çekildi.")
            logger.info(f"Başarıyla {len(stations_data)} adet ham kayıt yüklendi.")
            return stations_data

        except Exception as e:
            print(f"-> [ERROR] Ham veri işlenirken hata oluştu: {e}")
            logger.error(f"Ham veri işlenirken hata oluştu: {e}")
            raise

    def fetch_and_validate(self) -> List[StationModel]:
        """
        Ham veriyi çeker ve Pydantic modellerimizle valide ederek temiz bir liste döner.
        """
        print("-> [INFO] Veri validasyon süreci (Pydantic) başlatılıyor...")
        raw_data = self.fetch_raw_data()
        validated_stations = [] 

        failed_count = 0
        for index, item in enumerate(raw_data):
            try:
                station = StationModel(**item)
                validated_stations.append(station)
            except Exception as e:
                failed_count += 1
                # Her hatayı boğmamak için ilk 5 hatayı detaylı basalım
                if failed_count <= 5:
                    print(f"-> [WARNING] Kayıt doğrulanamadı (Index: {index}, Hata: {e})")
                logger.warning(f"Kayıt doğrulanamadı (Index: {index}, Hata: {e})")

        print(
            f"-> [SUMMARY] Toplam {len(raw_data)} kayıttan {len(validated_stations)} tanesi başarılı, {failed_count} tanesi hatalı/doğrulanamadı.")
        logger.info(f"Toplam {len(validated_stations)} kayıt başarıyla valide edildi.")
        return validated_stations