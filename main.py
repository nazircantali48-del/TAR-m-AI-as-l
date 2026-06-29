from hava import hava_durumu_al, hastalik_riski_hesapla
from email_bildirim import analiz_emaili_gonder
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import shutil
import os
import bcrypt
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text

from database import engine, get_db, Base
from models import Bahce, Analiz, Ilaclama, Kullanici, MusteriIliskisi
from gemini import analiz_et

SECRET_KEY = "tarim-ai-gizli-anahtar-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def sifre_hashle(sifre):
    return bcrypt.hashpw(sifre.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def sifre_dogrula(sifre, hash):
    return bcrypt.checkpw(sifre.encode("utf-8"), hash.encode("utf-8"))

def token_olustur(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def aktif_kullanici(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
        kullanici = db.query(Kullanici).filter(Kullanici.email == email).first()
        return kullanici
    except JWTError:
        return None

Base.metadata.create_all(bind=engine)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE bahceler ADD COLUMN IF NOT EXISTS kullanici_id INTEGER"))
        conn.execute(text("ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS aktif BOOLEAN DEFAULT TRUE"))
        conn.execute(text("ALTER TABLE kullanicilar ADD COLUMN IF NOT EXISTS rol VARCHAR DEFAULT 'ciftci'"))
        conn.execute(text("ALTER TABLE analizler ADD COLUMN IF NOT EXISTS risk_skoru INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE analizler ADD COLUMN IF NOT EXISTS tahmin TEXT"))
        conn.execute(text("ALTER TABLE analizler ADD COLUMN IF NOT EXISTS ai_raporu TEXT"))
        conn.commit()
    except Exception:
        conn.rollback()

app = FastAPI(title="Tarım AI")

os.makedirs("uploads", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# --- SAYFALAR ---
@app.get("/")
def ana_sayfa(): return FileResponse("frontend/index.html")

@app.get("/analiz")
def analiz_sayfasi(): return FileResponse("frontend/analiz.html")

@app.get("/gecmis")
def gecmis_sayfasi(): return FileResponse("frontend/gecmis.html")

@app.get("/bahceler")
def bahceler_sayfasi(): return FileResponse("frontend/bahceler.html")

@app.get("/ilaclar")
def ilaclar_sayfasi(): return FileResponse("frontend/ilaclar.html")

@app.get("/giris")
def giris_sayfasi(): return FileResponse("frontend/giris.html")

@app.get("/kayit")
def kayit_sayfasi(): return FileResponse("frontend/kayit.html")

@app.get("/musteriler")
def musteriler_sayfasi(): return FileResponse("frontend/musteriler.html")


# --- AUTH API ---
@app.post("/api/kayit")
def kayit_ol(
    ad: str = Form(...),
    email: str = Form(...),
    sifre: str = Form(...),
    rol: str = Form("ciftci"),
    db: Session = Depends(get_db)
):
    mevcut = db.query(Kullanici).filter(Kullanici.email == email).first()
    if mevcut:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")
    if rol not in ["ciftci", "ziraat_muhendisi"]:
        rol = "ciftci"
    kullanici = Kullanici(ad=ad, email=email, sifre_hash=sifre_hashle(sifre), rol=rol)
    db.add(kullanici)
    db.commit()
    db.refresh(kullanici)
    return {
        "token": token_olustur({"sub": kullanici.email}),
        "kullanici_ad": kullanici.ad,
        "rol": kullanici.rol
    }

@app.post("/api/giris")
def giris_yap(email: str = Form(...), sifre: str = Form(...), db: Session = Depends(get_db)):
    kullanici = db.query(Kullanici).filter(Kullanici.email == email).first()
    if not kullanici or not sifre_dogrula(sifre, kullanici.sifre_hash):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")
    return {
        "token": token_olustur({"sub": kullanici.email}),
        "kullanici_ad": kullanici.ad,
        "rol": kullanici.rol
    }

@app.get("/api/ben")
def beni_getir(kullanici: Kullanici = Depends(aktif_kullanici)):
    if not kullanici:
        raise HTTPException(status_code=401, detail="Giriş yapılmadı")
    return {"id": kullanici.id, "ad": kullanici.ad, "email": kullanici.email, "rol": kullanici.rol}


# --- BAHCE API ---
@app.get("/api/bahceler")
def bahceleri_getir(kullanici: Kullanici = Depends(aktif_kullanici), db: Session = Depends(get_db)):
    if not kullanici:
        raise HTTPException(status_code=401)
    return db.query(Bahce).filter(Bahce.kullanici_id == kullanici.id).all()

@app.post("/api/bahceler")
def bahce_ekle(
    ad: str = Form(...), konum: str = Form(""), alan_m2: float = Form(0), notlar: str = Form(""),
    kullanici: Kullanici = Depends(aktif_kullanici), db: Session = Depends(get_db)
):
    if not kullanici:
        raise HTTPException(status_code=401)
    bahce = Bahce(ad=ad, konum=konum, alan_m2=alan_m2, notlar=notlar, kullanici_id=kullanici.id)
    db.add(bahce)
    db.commit()
    db.refresh(bahce)
    return bahce

@app.delete("/api/bahceler/{bahce_id}")
def bahce_sil(bahce_id: int, kullanici: Kullanici = Depends(aktif_kullanici), db: Session = Depends(get_db)):
    if not kullanici:
        raise HTTPException(status_code=401)
    bahce = db.query(Bahce).filter(Bahce.id == bahce_id, Bahce.kullanici_id == kullanici.id).first()
    if not bahce:
        raise HTTPException(status_code=404, detail="Bahçe bulunamadı")
    db.delete(bahce)
    db.commit()
    return {"mesaj": "Silindi"}


# --- MÜŞTERİ API (Ziraat Mühendisi) ---
@app.get("/api/musteriler")
def musterileri_getir(kullanici: Kullanici = Depends(aktif_kullanici), db: Session = Depends(get_db)):
    if not kullanici or kullanici.rol != "ziraat_muhendisi":
        raise HTTPException(status_code=403, detail="Sadece ziraat mühendisleri erişebilir")
    iliskiler = db.query(MusteriIliskisi).filter(MusteriIliskisi.muhendis_id == kullanici.id).all()
    sonuc = []
    for iliski in iliskiler:
        ciftci = db.query(Kullanici).filter(Kullanici.id == iliski.ciftci_id).first()
        if not ciftci:
            continue
        bahceler = db.query(Bahce).filter(Bahce.kullanici_id == ciftci.id).all()
        bahce_durumlari = []
        for b in bahceler:
            son_analiz = db.query(Analiz).filter(
                Analiz.bahce_id == b.id
            ).order_by(Analiz.tarih.desc()).first()
            bahce_durumlari.append({
                "id": b.id,
                "ad": b.ad,
                "konum": b.konum,
                "son_analiz_tarihi": son_analiz.tarih.isoformat() if son_analiz else None,
                "son_risk_skoru": son_analiz.risk_skoru if son_analiz else None,
                "son_hastalik": son_analiz.hastalik_adi if son_analiz else None,
            })
        sonuc.append({
            "iliski_id": iliski.id,
            "ciftci_id": ciftci.id,
            "ciftci_ad": ciftci.ad,
            "ciftci_email": ciftci.email,
            "notlar": iliski.notlar,
            "bahceler": bahce_durumlari
        })
    return sonuc

@app.post("/api/musteri-ekle")
def musteri_ekle(
    ciftci_email: str = Form(...),
    notlar: str = Form(""),
    kullanici: Kullanici = Depends(aktif_kullanici),
    db: Session = Depends(get_db)
):
    if not kullanici or kullanici.rol != "ziraat_muhendisi":
        raise HTTPException(status_code=403)
    ciftci = db.query(Kullanici).filter(Kullanici.email == ciftci_email).first()
    if not ciftci:
        raise HTTPException(status_code=404, detail="Bu emailde kayıtlı çiftçi bulunamadı")
    if ciftci.rol != "ciftci":
        raise HTTPException(status_code=400, detail="Bu kullanıcı çiftçi değil")
    mevcut = db.query(MusteriIliskisi).filter(
        MusteriIliskisi.muhendis_id == kullanici.id,
        MusteriIliskisi.ciftci_id == ciftci.id
    ).first()
    if mevcut:
        raise HTTPException(status_code=400, detail="Bu çiftçi zaten müşteriniz")
    iliski = MusteriIliskisi(muhendis_id=kullanici.id, ciftci_id=ciftci.id, notlar=notlar)
    db.add(iliski)
    db.commit()
    return {"mesaj": f"{ciftci.ad} müşteri olarak eklendi", "ciftci_ad": ciftci.ad}

@app.delete("/api/musteri-sil/{iliski_id}")
def musteri_sil(
    iliski_id: int,
    kullanici: Kullanici = Depends(aktif_kullanici),
    db: Session = Depends(get_db)
):
    if not kullanici or kullanici.rol != "ziraat_muhendisi":
        raise HTTPException(status_code=403)
    iliski = db.query(MusteriIliskisi).filter(
        MusteriIliskisi.id == iliski_id,
        MusteriIliskisi.muhendis_id == kullanici.id
    ).first()
    if not iliski:
        raise HTTPException(status_code=404)
    db.delete(iliski)
    db.commit()
    return {"mesaj": "Müşteri silindi"}

@app.get("/api/musteri-analizler/{ciftci_id}")
def musteri_analizleri_getir(
    ciftci_id: int,
    kullanici: Kullanici = Depends(aktif_kullanici),
    db: Session = Depends(get_db)
):
    if not kullanici or kullanici.rol != "ziraat_muhendisi":
        raise HTTPException(status_code=403)
    iliski = db.query(MusteriIliskisi).filter(
        MusteriIliskisi.muhendis_id == kullanici.id,
        MusteriIliskisi.ciftci_id == ciftci_id
    ).first()
    if not iliski:
        raise HTTPException(status_code=403, detail="Bu çiftçi müşteriniz değil")
    bahceler = db.query(Bahce).filter(Bahce.kullanici_id == ciftci_id).all()
    bahce_idleri = [b.id for b in bahceler]
    analizler = db.query(Analiz).filter(
        Analiz.bahce_id.in_(bahce_idleri)
    ).order_by(Analiz.tarih.desc()).all()
    return analizler


# --- ANALİZ API ---
@app.post("/api/analiz")
async def analiz_yap(
    background_tasks: BackgroundTasks,
    fotograf: UploadFile = File(...),
    bahce_id: int = Form(...),
    db: Session = Depends(get_db)
):
    dosya_adi = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{fotograf.filename}"
    dosya_yolu = f"uploads/{dosya_adi}"

    with open(dosya_yolu, "wb") as buffer:
        shutil.copyfileobj(fotograf.file, buffer)

    bahce = db.query(Bahce).filter(Bahce.id == bahce_id).first()
    lat, lon = 37.0, 35.0
    if bahce and bahce.konum and "," in bahce.konum:
        try:
            lat_str, lon_str = bahce.konum.split(",")
            lat, lon = float(lat_str.strip()), float(lon_str.strip())
        except ValueError:
            pass

    hava = hava_durumu_al(lat, lon)
    hava_ozeti = hava.get("ozet", "") if hava["basarili"] else ""

    onceki = db.query(Analiz).filter(
        Analiz.bahce_id == bahce_id
    ).order_by(Analiz.tarih.desc()).first()
    onceki_fotograf = onceki.fotograf_yolu if onceki else None
    onceki_rapor = onceki.ai_raporu if onceki else None

    sonuc = analiz_et(dosya_yolu, onceki_fotograf, onceki_rapor, hava_durumu=hava_ozeti)

    if not sonuc["basarili"]:
        raise HTTPException(status_code=500, detail=sonuc["hata"])

    analiz = Analiz(
        bahce_id=bahce_id,
        fotograf_yolu=dosya_yolu,
        hastalik_adi=sonuc["hastalik_adi"],
        ai_raporu=sonuc["rapor"],
        risk_skoru=sonuc.get("risk_skoru", 0),
        tahmin=sonuc.get("tahmin", "")
    )
    db.add(analiz)
    db.commit()
    db.refresh(analiz)

    if bahce and bahce.kullanici_id:
        kullanici = db.query(Kullanici).filter(Kullanici.id == bahce.kullanici_id).first()
        if kullanici and kullanici.email:
            background_tasks.add_task(
                analiz_emaili_gonder,
                kullanici.email, kullanici.ad,
                analiz.hastalik_adi, analiz.risk_skoru,
                analiz.tahmin, bahce.ad
            )

    return {
        "analiz_id": analiz.id,
        "hastalik_adi": analiz.hastalik_adi,
        "rapor": analiz.ai_raporu,
        "risk_skoru": analiz.risk_skoru,
        "tahmin": analiz.tahmin,
        "degisim": sonuc.get("degisim", ""),
        "onerilen_ilac": sonuc.get("onerilen_ilac", ""),
        "onerilen_doz": sonuc.get("onerilen_doz", ""),
        "uygulama_sikligi": sonuc.get("uygulama_sikligi", "")
    }

@app.get("/api/analizler")
def analizleri_getir(bahce_id: int = None, db: Session = Depends(get_db)):
    query = db.query(Analiz)
    if bahce_id:
        query = query.filter(Analiz.bahce_id == bahce_id)
    return query.order_by(Analiz.tarih.desc()).all()

@app.delete("/api/analizler/{analiz_id}")
def analiz_sil(analiz_id: int, db: Session = Depends(get_db)):
    analiz = db.query(Analiz).filter(Analiz.id == analiz_id).first()
    if not analiz:
        raise HTTPException(status_code=404, detail="Bulunamadı")
    db.delete(analiz)
    db.commit()
    return {"mesaj": "Silindi"}


# --- İLAÇLAMA API ---
@app.get("/api/ilaclamalar")
def ilaclamalari_getir(bahce_id: int = None, db: Session = Depends(get_db)):
    query = db.query(Ilaclama)
    if bahce_id:
        query = query.filter(Ilaclama.bahce_id == bahce_id)
    return query.order_by(Ilaclama.uygulama_tarihi.desc()).all()

@app.post("/api/ilaclamalar")
def ilaclama_ekle(
    bahce_id: int = Form(...), analiz_id: int = Form(None), ilac_adi: str = Form(...),
    doz: str = Form(""), uygulama_tarihi: str = Form(...), sonraki_tarih: str = Form(""),
    notlar: str = Form(""), db: Session = Depends(get_db)
):
    ilaclama = Ilaclama(
        bahce_id=bahce_id, analiz_id=analiz_id, ilac_adi=ilac_adi, doz=doz,
        uygulama_tarihi=datetime.fromisoformat(uygulama_tarihi),
        sonraki_tarih=datetime.fromisoformat(sonraki_tarih) if sonraki_tarih else None,
        notlar=notlar
    )
    db.add(ilaclama)
    db.commit()
    db.refresh(ilaclama)
    return ilaclama

@app.delete("/api/ilaclamalar/{ilaclama_id}")
def ilaclama_sil(ilaclama_id: int, db: Session = Depends(get_db)):
    ilaclama = db.query(Ilaclama).filter(Ilaclama.id == ilaclama_id).first()
    if not ilaclama:
        raise HTTPException(status_code=404, detail="Bulunamadı")
    db.delete(ilaclama)
    db.commit()
    return {"mesaj": "Silindi"}

@app.get("/api/proaktif-kontrol")
def proaktif_kontrol():
    from proaktif import yuksek_riskli_kontrol
    yuksek_riskli_kontrol()
    return {"mesaj": "Kontrol tamamlandı"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)