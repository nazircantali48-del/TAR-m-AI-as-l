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
    olusturma_tarihi = Column(DateTime, default=datetime.utcnow)  # Güvenli zaman damgası

    bahceler = relationship("Bahce", back_populates="kullanici", cascade="all, delete-orphan")


class Bahce(Base):
    __tablename__ = "bahceler"

    id = Column(Integer, primary_key=True, index=True)
    kullanici_id = Column(Integer, ForeignKey("kullanicilar.id"), nullable=True)
    ad = Column(String, nullable=False)
    konum = Column(String)  # "37.0, 35.0" formatında dinamik hava durumu koordinatı taşır
    alan_m2 = Column(Float)
    notlar = Column(Text)
    olusturma_tarihi = Column(DateTime, default=datetime.utcnow)

    analizler = relationship("Analiz", back_populates="bahce", cascade="all, delete-orphan")
    ilaclamalar = relationship("Ilaclama", back_populates="bahce", cascade="all, delete-orphan")
    kullanici = relationship("Kullanici", back_populates="bahceler")


class Analiz(Base):
    __tablename__ = "analizler"

    id = Column(Integer, primary_key=True, index=True)
    bahce_id = Column(Integer, ForeignKey("bahceler.id"))
    fotograf_yolu = Column(String)
    hastalik_adi = Column(String)  # Gemini'dan dönen ziraat teşhis ismi (Örn: Demir Eksikliği)
    ai_raporu = Column(Text)       # Detaylı reçete, çevre analizi ve aksiyon planı
    risk_skoru = Column(Integer, default=0) # 1-10 arası tehlike derecesi
    tahmin = Column(Text)          # YOLOv8 modelinin bastığı ham etiket (Örn: magnezyum_eksikligi)
    tarih = Column(DateTime, default=datetime.utcnow)

    bahce = relationship("Bahce", back_populates="analizler")
    ilaclamalar = relationship("Ilaclama", back_populates="analiz", cascade="all, delete-orphan")


class Ilaclama(Base):
    __tablename__ = "ilaclamalar"

    id = Column(Integer, primary_key=True, index=True)
    bahce_id = Column(Integer, ForeignKey("bahceler.id"))
    analiz_id = Column(Integer, ForeignKey("analizler.id"), nullable=True)
    ilac_adi = Column(String, nullable=False)  # Önerilen ilaç ya da gübrenin adı
    doz = Column(String)                       # Örn: "200g / 100L su"
    uygulama_tarihi = Column(DateTime, nullable=False)
    sonraki_tarih = Column(DateTime, nullable=True) # Periyodik kontrol için sistemin ürettiği tarih
    notlar = Column(Text)

    bahce = relationship("Bahce", back_populates="ilaclamalar")
    analiz = relationship("Analiz", back_populates="ilaclamalar")