from hava import hava_durumu_al, hastalik_riski_hesapla
from email_bildirim import analiz_emaili_gonder
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import shutil
import os
import requests
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text

from database import engine, get_db, Base
from models import Bahce, Analiz, Ilaclama, Kullanici
from gemini import analiz_et
from ultralytics import YOLO

SECRET_KEY = "tarim-ai-gizli-anahtar-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

def sifre_hashle(sifre):
    return pwd_context.hash(sifre)

def sifre_dogrula(sifre, hash):
    return pwd_context.verify(sifre, hash)

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
        conn.execute(text("ALTER TABLE analizler ADD COLUMN IF NOT EXISTS risk_skoru INTEGER DEFAULT 0"))
        conn.execute(text("ALTER TABLE analizler ADD COLUMN IF NOT EXISTS tahmin TEXT"))
        conn.execute(text("ALTER TABLE analizler ADD COLUMN IF NOT EXISTS ai_raporu TEXT"))
        conn.commit()
    except Exception:
        conn.rollback()

app = FastAPI(title="Tarım AI")

SUPABASE_MODEL_URL = "https://your-project-id.supabase.co/storage/v1/object/public/models/best.pt"
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "best.pt")

def yolo_modeli_hazirla():
    os.makedirs(MODEL_DIR, exist_ok=True)
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 1000000:
        print("🚀 YOLOv8 Modeli yerel diskte bulundu.")
    else:
        print("📥 YOLOv8 Modeli Supabase'den kalıcı olarak indiriliyor...")
        try:
            with requests.get(SUPABASE_MODEL_URL, stream=True) as r:
                r.raise_for_status()
                with open(MODEL_PATH, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
            print("✅ Model kaydedildi!")
        except Exception as e:
            print(f"⚠️ Hata: {e}, varsayılan yolov8n.pt yükleniyor.")
            return YOLO("yolov8n.pt")
    return YOLO(MODEL_PATH)

yolo_model = yolo_modeli_hazirla()
os.makedirs("uploads", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# --- PAGES ---
@app.get("/")
def ana_sayfa(): return FileResponse("frontend/index.html")

@app.get("/analiz")
def analiz_sayfasi(): return FileResponse("frontend/analiz.html")

@app.get("/gecmis")
def gecmis_sayfasi(): return FileResponse("frontend/gecmis.html")

@app.get("/bahceler")
def bahceler_sayfasi(): return FileResponse("frontend/bahceler.html")

@app.get("/giris")
def giris_sayfasi(): return FileResponse("frontend/giris.html")

@app.get("/kayit")
def kayit_sayfasi(): return FileResponse("frontend/kayit.html")


# --- AUTH API ---
@app.post("/api/kayit")
def kayit_ol(ad: str = Form(...), email: str = Form(...), sifre: str = Form(...), db: Session = Depends(get_db)):
    mevcut = db.query(Kullanici).filter(Kullanici.email == email).first()
    if mevcut: raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı")
    kullanici = Kullanici(ad=ad, email=email, sifre_hash=sifre_hashle(sifre))
    db.add(kullanici)
    db.commit()
    db.refresh(kullanici)
    return {"token": token_olustur({"sub": kullanici.email}), "kullanici_ad": kullanici.ad}

@app.post("/api/giris")
def giris_yap(email: str = Form(...), sifre: str = Form(...), db: Session = Depends(get_db)):
    kullanici = db.query(Kullanici).filter(Kullanici.email == email).first()
    if not kullanici or not sifre_dogrula(sifre, kullanici.sifre_hash):
        raise HTTPException(status_code=401, detail="Email veya şifre hatalı")
    return {"token": token_olustur({"sub": kullanici.email}), "kullanici_ad": kullanici.ad}

@app.get("/api/ben")
def beni_getir(kullanici: Kullanici = Depends(aktif_kullanici)):
    if not kullanici: raise HTTPException(status_code=401, detail="Giriş yapılmadı")
    return {"id": kullanici.id, "ad": kullanici.ad, "email": kullanici.email}


# --- BAHCE API ---
@app.get("/api/bahceler")
def bahceleri_getir(kullanici: Kullanici = Depends(aktif_kullanici), db: Session = Depends(get_db)):
    if not kullanici: raise HTTPException(status_code=401, detail="Yetkisiz erişim")
    return db.query(Bahce).filter(Bahce.kullanici_id == kullanici.id).all()

@app.post("/api/bahceler")
def bahce_ekle(
    ad: str = Form(...), konum: str = Form(""), alan_m2: float = Form(0), notlar: str = Form(""),
    kullanici: Kullanici = Depends(aktif_kullanici), db: Session = Depends(get_db)
):
    if not kullanici: raise HTTPException(status_code=401, detail="Önce giriş yapmalısınız")
    # GELECEKTEKİ HATA ÖNLENDİ: Bahçe artık doğrudan giriş yapan kullanıcıya bağlanıyor
    bahce = Bahce(ad=ad, konum=konum, alan_m2=alan_m2, notlar=notlar, kullanici_id=kullanici.id)
    db.add(bahce)
    db.commit()
    db.refresh(bahce)
    return bahce

@app.delete("/api/bahceler/{bahce_id}")
def bahce_sil(bahce_id: int, kullanici: Kullanici = Depends(aktif_kullanici), db: Session = Depends(get_db)):
    if not kullanici: raise HTTPException(status_code=401)
    bahce = db.query(Bahce).filter(Bahce.id == bahce_id, Bahce.kullanici_id == kullanici.id).first()
    if not bahce: raise HTTPException(status_code=404, detail="Bahçe bulunamadı")
    db.delete(bahce)
    db.commit()
    return {"mesaj": "Silindi"}


# --- ANALİZ API ---
@app.post("/api/analiz")
async def analiz_yap(
    background_tasks: BackgroundTasks, # Arka plan iş yükü yöneticisi eklendi
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
        except ValueError: pass

    hava = hava_durumu_al(lat, lon)
    hava_ozeti = hava.get("ozet", "") if hava["basarili"] else ""

    yolo_sonuc = yolo_model(dosya_yolu, conf=0.25)[0]
    yolo_tahmini_sinif = "Bilinmeyen Durum"
    yolo_guven_skoru = 0.0
    
    if len(yolo_sonuc.boxes) > 0:
        best_box = yolo_sonuc.boxes[0]
        class_id = int(best_box.cls[0].item())
        yolo_guven_skoru = float(best_box.conf[0].item())
        yolo_tahmini_sinif = yolo_sonuc.names[class_id]

    onceki = db.query(Analiz).filter(Analiz.bahce_id == bahce_id).order_by(Analiz.tarih.desc()).first()
    onceki_fotograf = onceki.fotograf_yolu if onceki else None
    onceki_rapor = onceki.ai_raporu if onceki else None

    sonuc = analiz_et(dosya_yolu, onceki_fotograf, onceki_rapor, yolo_etiket=yolo_tahmini_sinif, hava_durumu=hava_ozeti)

    if not sonuc["basarili"]:
        raise HTTPException(status_code=500, detail=sonuc["hata"])

    analiz = Analiz(
        bahce_id=bahce_id,
        fotograf_yolu=dosya_yolu,
        hastalik_adi=sonuc["hastalik_adi"] if sonuc["hastalik_adi"] else yolo_tahmini_sinif,
        ai_raporu=sonuc["rapor"],
        risk_skoru=sonuc.get("risk_skoru", int(yolo_guven_skoru * 100)),
        tahmin=yolo_tahmini_sinif
    )
    db.add(analiz)
    db.commit()
    db.refresh(analiz)

    # İLERİ SEVİYE OPTİMİZASYON: E-posta gönderimi BackgroundTasks'e atandı (Kilitlenme Önleme)
    if bahce and bahce.kullanici_id:
        kullanici = db.query(Kullanici).filter(Kullanici.id == bahce.kullanici_id).first()
        if kullanici and kullanici.email:
            background_tasks.add_task(
                analiz_emaili_gonder,
                kullanici.email,
                kullanici.ad,
                analiz.hastalik_adi,
                analiz.risk_skoru,
                analiz.tahmin,
                bahce.ad
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
    if bahce_id: query = query.filter(Analiz.bahce_id == bahce_id)
    return query.order_by(Analiz.tarih.desc()).all()

@app.delete("/api/analizler/{analiz_id}")
def analiz_sil(analiz_id: int, db: Session = Depends(get_db)):
    analiz = db.query(Analiz).filter(Analiz.id == analiz_id).first()
    if not analiz: raise HTTPException(status_code=404)
    db.delete(analiz)
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