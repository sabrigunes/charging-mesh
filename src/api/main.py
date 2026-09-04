from fastapi import FastAPI
from src.config import settings
from src.api.routers import stations

app = FastAPI(
    title="Charging Mesh API",
    version="1.0.0",
    description="EPDK şarj istasyonu veri servis katmanı"
)

app.include_router(stations.router, prefix="/api/v1", tags=["Stations"])

@app.get("/")
def root():
    return {"status": "online", "service": "Charging Mesh API"}