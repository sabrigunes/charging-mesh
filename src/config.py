import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_DIR = Path("/opt/projects/charging-mesh")
load_dotenv(PROJECT_DIR / ".env", override=True)

class Settings:
    # Ana Veritabanı (charging_db)
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "charging_db")
    DB_USER: str = os.getenv("DB_USER", "postgres_admin")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Coğrafi Verilerin Olduğu Core Veritabanı (Genellikle aynı veya ayrı olabilir)
    DB_HOST_CORE: str = os.getenv("DB_HOST_CORE", os.getenv("DB_HOST", "localhost"))
    DB_PORT_CORE: str = os.getenv("DB_PORT_CORE", os.getenv("DB_PORT", "5432"))
    DB_NAME_CORE: str = os.getenv("DB_NAME_CORE", os.getenv("DB_NAME", "charging_db"))
    DB_USER_CORE: str = os.getenv("DB_USER_CORE", os.getenv("DB_USER", "postgres_admin"))
    DB_PASSWORD_CORE: str = os.getenv("DB_PASSWORD_CORE", os.getenv("DB_PASSWORD", ""))

    @property
    def DATABASE_URL_CORE(self) -> str:
        return f"postgresql://{self.DB_USER_CORE}:{self.DB_PASSWORD_CORE}@{self.DB_HOST_CORE}:{self.DB_PORT_CORE}/{self.DB_NAME_CORE}"

    # MongoDB Yapılandırması
    MONGO_HOST: str = os.getenv("MONGO_HOST", "localhost")
    MONGO_PORT: str = os.getenv("MONGO_PORT", "27017")
    MONGO_USER: str = os.getenv("MONGO_USER", "")
    MONGO_PASSWORD: str = os.getenv("MONGO_PASSWORD", "")

    @property
    def MONGO_URL(self) -> str:
        if self.MONGO_USER and self.MONGO_PASSWORD:
            return f"mongodb://{self.MONGO_USER}:{self.MONGO_PASSWORD}@{self.MONGO_HOST}:{self.MONGO_PORT}/?authSource=admin"
        return f"mongodb://{self.MONGO_HOST}:{self.MONGO_PORT}"

settings = Settings()