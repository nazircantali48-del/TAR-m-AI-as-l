from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
import shutil
import os

from database import engine, get_db, Base
from models import Bahce, Analiz, Ilaclama
from gemini import analiz_et

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tarım AI")

os.makedirs("uploads", exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# --- SAYFALAR ---

@app.get("/")
def ana_sayfa():
    return FileResponse("frontend/index.html")

@app.get("/analiz")
def analiz_sayfasi():
    return FileResponse("frontend/analiz.html")

@app.get("/gecmis")
def gecmis_sayfasi():
    return FileResponse("frontend/gecmis.html")

@app.get("/bahceler")
def bahceler_sayfasi():
    return FileResponse("frontend/bahceler.html")

@app.get("/ilaclar")
def ilaclar_sayfasi():
    return FileResponse("frontend/ilaclar.html")


# --- BAHCE API ---

@app.get("/api/bahceler")
def bahceleri_getir(db: Session = Depends(get_db)):
    return db.query(Bahce).all()

@app.post("/api/bahceler")
def bahce_ekle(
    ad: str = Form(...),
    konum: str = Form(""),
    alan_m2: float = Form(0),
    notlar: str = Form(""),
    db: Session = Depends(get_db)
):
    bahce = Bahce(ad=ad, konum=konum, alan_m2=alan_m2, notlar=notlar)
    db.add(bahce)
    db.commit()
    db.refresh(bahce)
    return bahce

@app.delete("/api/bahceler/{bahce_id}")
def bahce_sil(bahce_id: int, db: Session = Depends(get_db)):
    bahce = db.query(Bahce).filter(Bahce.id == bahce_id).first()
    if not bahce:
        raise HTTPException(status_code=404, detail="Bahçe bulunamadı")
    db.delete(bahce)
    db.commit()
    return {"mesaj": "Silindi"}


# --- ANALİZ API ---

@app.get("/api/analizler")
def analizleri_getir(bahce_id: int = None, db: Session = Depends(get_db)):
    query = db.query(Analiz)
    if bahce_id:
        query = query.filter(Analiz.bahce_id == bahce_id)
    return query.order_by(Analiz.tarih.desc()).all()

@app.post("/api/analiz")
async def analiz_yap(
    fotograf: UploadFile = File(...),
    bahce_id: int = Form(...),
    db: Session = Depends(get_db)
):
    dosya_adi = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{fotograf.filename}"
    dosya_yolu = f"uploads/{dosya_adi}"

    with open(dosya_yolu, "wb") as buffer:
        shutil.copyfileobj(fotograf.file, buffer)

    sonuc = analiz_et(dosya_yolu)

    if not sonuc["basarili"]:
        raise HTTPException(status_code=500, detail=sonuc["hata"])

    analiz = Analiz(
        bahce_id=bahce_id,
        fotograf_yolu=dosya_yolu,
        hastalik_adi=sonuc["hastalik_adi"],
        ai_raporu=sonuc["rapor"]
    )
    db.add(analiz)
    db.commit()
    db.refresh(analiz)
    return {
        "analiz_id": analiz.id,
        "hastalik_adi": analiz.hastalik_adi,
        "rapor": analiz.ai_raporu,
        "onerilen_ilac": sonuc.get("onerilen_ilac", ""),
        "onerilen_doz": sonuc.get("onerilen_doz", ""),
        "uygulama_sikligi": sonuc.get("uygulama_sikligi", "")
    }


# --- İLAÇLAMA API ---

@app.get("/api/ilaclamalar")
def ilaçlamalari_getir(bahce_id: int = None, db: Session = Depends(get_db)):
    query = db.query(Ilaclama)
    if bahce_id:
        query = query.filter(Ilaclama.bahce_id == bahce_id)
    return query.order_by(Ilaclama.uygulama_tarihi.desc()).all()

@app.post("/api/ilaclamalar")
def ilaclama_ekle(
    bahce_id: int = Form(...),
    analiz_id: int = Form(None),
    ilac_adi: str = Form(...),
    doz: str = Form(""),
    uygulama_tarihi: str = Form(...),
    sonraki_tarih: str = Form(""),
    notlar: str = Form(""),
    db: Session = Depends(get_db)
):
    ilaclama = Ilaclama(
        bahce_id=bahce_id,
        analiz_id=analiz_id,
        ilac_adi=ilac_adi,
        doz=doz,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)