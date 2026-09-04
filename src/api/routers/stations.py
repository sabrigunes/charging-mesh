from fastapi import APIRouter, HTTPException
import psycopg2
from src.config import settings

router = APIRouter()


def get_db_connection():
    return psycopg2.connect(
        host=settings.DB_HOST,
        database=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        port=settings.DB_PORT
    )


@router.get("/charging")
def get_charging_stations(limit: int = 50, offset: int = 0):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT s.number,
                              s.name,
                              s.address,
                              s.latitude,
                              s.longitude,
                              s.is_public,
                              s.is_green,
                              c.name as city_name
                       FROM public.ev_stations s
                                LEFT JOIN public.cities c ON s.city_id = c.id
                           LIMIT %s
                       OFFSET %s
                       """, (limit, offset))

        rows = cursor.fetchall()
        stations = []
        for row in rows:
            stations.append({
                "number": row[0],
                "name": row[1],
                "address": row[2],
                "latitude": row[3],
                "longitude": row[4],
                "is_public": row[5],
                "is_green": row[6],
                "city": row[7]
            })

        cursor.close()
        conn.close()
        return {"total": len(stations), "data": stations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))