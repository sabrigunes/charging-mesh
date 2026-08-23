from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class CompanyModel(BaseModel):
    name: str = Field(..., alias="sarjAgiIsletmecisiUnvan")
    license_no: Optional[str] = Field(None, alias="sarjAgiIsletmecisiLisansNo")

    class Config:
        populate_by_name = True


class ElectricityCompanyModel(BaseModel):
    name: Optional[str] = Field(None, alias="olumluGorusVerenDagitimSirketiLisansUnvani")
    license_no: Optional[str] = Field(None, alias="olumluGorusVerenDagitimSirketiLisansNo")  # Lisans numarası eklendi
    document_no: Optional[str] = Field(None, alias="dagitimSirketiOlumluGorusBelgeNumarasi")

    class Config:
        populate_by_name = True


class SocketItemModel(BaseModel):
    socket_no: str = Field(..., alias="soketNo")
    socket_type: str = Field(..., alias="soketTipi")  # AC / DC
    socket_tur: str = Field(..., alias="soketTuru")  # DC_CCS, AC_TYPE2 vb.
    power_kw: float = Field(..., alias="soketGucu")  # Güç

    class Config:
        populate_by_name = True


class StationModel(BaseModel):
    station_no: str = Field(..., alias="sarjIstasyonuNo")
    station_adi: str = Field(..., alias="sarjIstasyonuAdi")
    operator: str = Field(..., alias="sarjIstasyonuIsletmecisi")
    sarj_istasyonu_isletmecisi: str = Field(..., alias="sarjIstasyonuIsletmecisi")
    adres: str = Field(..., alias="adres")
    hizmet_sekli: str = Field(..., alias="hizmetSekli")
    marka: Optional[str] = Field(None, alias="marka")
    enlem: float = Field(..., alias="enlem")
    boylam: float = Field(..., alias="boylam")
    yesil_sarj: str = Field(default="HAYIR", alias="yesilSarjIstasyonuMu")

    sarj_agi_isletmecisi_unvan: Optional[str] = Field(None, alias="sarjAgiIsletmecisiUnvan")
    sarj_agi_isletmecisi_lisans_no: Optional[str] = Field(None, alias="sarjAgiIsletmecisiLisansNo")
    olumlu_gorus_veren_dagitim_sirketi_lisans_unvani: Optional[str] = Field(None,
                                                                            alias="olumluGorusVerenDagitimSirketiLisansUnvani")
    olumlu_gorus_veren_dagitim_sirketi_lisans_no: Optional[str] = Field(None,
                                                                        alias="olumluGorusVerenDagitimSirketiLisansNo")
    dagitim_sirketi_olumlu_gorus_belge_numarasi: Optional[str] = Field(None,
                                                                       alias="dagitimSirketiOlumluGorusBelgeNumarasi")

    sockets: List[SocketItemModel] = Field(default=[], alias="soketler")

    @field_validator('enlem', mode='before')
    def validate_enlem(cls, v):
        if v is None or v == "":
            return 0.0
        return float(v)

    @field_validator('boylam', mode='before')
    def validate_boylam(cls, v):
        if v is None or v == "":
            return 0.0
        return float(v)

    class Config:
        populate_by_name = True