from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Kullanici(Base):
    __tablename__ = "kullanicilar"

    id = Column(Integer, primary_key=True, index=True)
    ad = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    sifre_hash = Column(String, nullable=False)
    aktif = Column(Boolean, default=True)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

    bahceler = relationship("Bahce", back_populates="kullanici")

class Bahce(Base):
    __tablename__ = "bahceler"

    id = Column(Integer, primary_key=True, index=True)
    kullanici_id = Column(Integer, ForeignKey("kullanicilar.id"), nullable=True)
    ad = Column(String, nullable=False)
    konum = Column(String)
    alan_m2 = Column(Float)
    notlar = Column(Text)
    olusturma_tarihi = Column(DateTime, default=datetime.now)

    analizler = relationship("Analiz", back_populates="bahce")
    ilaclamalar = relationship("Ilaclama", back_populates="bahce")
    kullanici = relationship("Kullanici", back_populates="bahceler")

class Analiz(Base):
    __tablename__ = "analizler"

    id = Column(Integer, primary_key=True, index=True)
    bahce_id = Column(Integer, ForeignKey("bahceler.id"))
    fotograf_yolu = Column(String)
    hastalik_adi = Column(String)
    ai_raporu = Column(Text)
    risk_skoru = Column(Integer, default=0)
    tahmin = Column(Text)
    tarih = Column(DateTime, default=datetime.now)

    bahce = relationship("Bahce", back_populates="analizler")
    ilaclamalar = relationship("Ilaclama", back_populates="analiz")

class Ilaclama(Base):
    __tablename__ = "ilaclamalar"

    id = Column(Integer, primary_key=True, index=True)
    bahce_id = Column(Integer, ForeignKey("bahceler.id"))
    analiz_id = Column(Integer, ForeignKey("analizler.id"), nullable=True)
    ilac_adi = Column(String, nullable=False)
    doz = Column(String)
    uygulama_tarihi = Column(DateTime)
    sonraki_tarih = Column(DateTime, nullable=True)
    notlar = Column(Text)

    bahce = relationship("Bahce", back_populates="ilaclamalar")
    analiz = relationship("Analiz", back_populates="ilaclamalar")