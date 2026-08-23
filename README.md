# ⚡ Charging Mesh: EPDK EV Charging Stations ETL & Pipeline

Bu proje, Enerji Piyasası Düzenleme Kurumu (EPDK) şarj istasyonu verilerini uçtan uca toplayan, doğrulayan, coğrafi verilerle (şehir, ilçe, mahalle vb.) zenginleştiren, MongoDB ham veri katmanında saklayan ve veritabanı bütünlüğü için **3NF (Third Normal Form)** prensibine uygun normalize edilmiş ilişkisel tablolarla PostgreSQL veritabanına aktaran, Apache Airflow ile otomatikleştirilmiş kurumsal bir **ETL (Extract, Transform, Load)** boru hattıdır.

---

## 🏗️ Mimari ve Kullanılan Teknolojiler

* **Python & Pydantic:** Veri çekme ve şema validasyon işlemleri.
* **Apache Airflow:** ETL süreçlerinin zamanlanması ve periyodik yönetimi (DAGs).
* **MongoDB:** Ham verilerin esnek şemayla saklandığı NoSQL katmanı.
* **PostgreSQL / PostGIS:** İlişkisel verilerin tutulduğu ana veri ambarı.
* **Docker & Docker Compose:** Tüm servislerin izole ve tutarlı bir şekilde ayakta tutulması için konteynerizasyon.

---

## 📂 Proje Dizin Yapısı

```text
charging-mesh/
│
├── dags/                     # Airflow DAG dosyaları
│   ├── epdk_extract_load_dag.py # 2 saatte bir ham veri çekme pipeline'ı
│   └── epdk_transform_dag.py    # Günlük transformasyon ve PostgreSQL yükleme pipeline'ı
│
├── src/                      # Çekirdek Python modülleri
│   ├── extractors/           # EPDK API entegrasyonu ve veri çekme yöneticileri
│   ├── models/               # Pydantic veri modelleri ve validasyon kuralları
│   └── transformers/         # Veriyi dönüştürme ve ilişkisel eşleme mantığı
│
├── init-scripts/             # Veritabanı başlangıç scriptleri
├── docker-compose.yml        # Altyapı servis yapılandırması
└── requirements.txt          # Python bağımlılıkları
```

---

## 🔄 ETL Akışı ve Süreçler

1. **Extract (Çekme):** EPDK'dan şarj istasyonu verileri periyodik olarak çekilir.
2. **Load (Ham Katman):** Gelen ham veriler hızlı erişim ve loglama için **MongoDB**'ye kaydedilir.
3. **Transform & Load (İlişkisel Katman):** Airflow üzerinden tetiklenen transformasyon adımıyla ham veriler işlenir, normalize edilir ve **PostgreSQL** veritabanına aktarılır.

---

## 🚀 Kurulum ve Çalıştırma

### 1. Projeyi Klonlayın
```bash
git clone <proje-repo-adresi>
cd charging-mesh
```

### 2. Docker ile Servisleri Ayağa Kaldırın
```bash
docker compose up -d
```

### 3. Airflow Kullanıcısı Oluşturma
Airflow arayüzüne giriş yapabilmek için admin kullanıcısını container içinde oluşturun:
```bash
docker exec -it central_airflow airflow users create \
    --username admin \
    --firstname Sabri \
    --lastname Gunes \
    --role Admin \
    --email admin@example.com \
    --password Str0ngPassw0rd
```

---

## 📊 Airflow DAG Yapısı

Projede iş yükünü optimize etmek amacıyla bağımsız iki DAG çalışmaktadır:
* **`epdk_extract_load_pipeline`** (`0 */2 * * *`): Her 2 saatte bir çalışarak ham veriyi çeker ve kaydeder.
* **`epdk_transform_pipeline`** (`@daily`): Günlük periyotta çalışarak verileri dönüştürür ve PostgreSQL'e yükler.