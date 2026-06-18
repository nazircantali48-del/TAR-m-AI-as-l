import urllib.request
import json

def hava_durumu_al(enlem: float = 37.0, boylam: float = 35.0) -> dict:
    """Open-Meteo API ile ücretsiz hava durumu çek"""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={enlem}&longitude={boylam}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_max"
            f"&forecast_days=7&timezone=auto"
        )
        with urllib.request.urlopen(url, timeout=5) as response:
            veri = json.loads(response.read())

        guncel = veri.get("current", {})
        gunluk = veri.get("daily", {})

        return {
            "basarili": True,
            "sicaklik": guncel.get("temperature_2m", 0),
            "nem": guncel.get("relative_humidity_2m", 0),
            "yagis": guncel.get("precipitation", 0),
            "ruzgar": guncel.get("wind_speed_10m", 0),
            "7gun_max_nem": max(gunluk.get("relative_humidity_2m_max", [0])),
            "7gun_toplam_yagis": sum(gunluk.get("precipitation_sum", [0])),
            "ozet": f"Sıcaklık: {guncel.get('temperature_2m')}°C, Nem: {guncel.get('relative_humidity_2m')}%, Yağış: {guncel.get('precipitation')}mm, Rüzgar: {guncel.get('wind_speed_10m')}km/h"
        }
    except Exception as e:
        return {
            "basarili": False,
            "ozet": "Hava durumu alınamadı",
            "hata": str(e)
        }

def hastalik_riski_hesapla(nem: float, sicaklik: float) -> str:
    """Hava koşullarına göre hastalık riski yorumu"""
    riskler = []

    if nem > 80:
        riskler.append("Yüksek nem (%{:.0f}) mantar hastalıkları için ideal ortam".format(nem))
    if 20 <= sicaklik <= 30 and nem > 70:
        riskler.append("Sıcaklık ve nem kombinasyonu külleme/mildiyö riski yaratıyor")
    if sicaklik > 35:
        riskler.append("Aşırı sıcaklık bitkiyi strese sokuyor, hastalığa karşı direnci düşürüyor")
    if sicaklik < 5:
        riskler.append("Düşük sıcaklık don riski ve bazı fungal hastalıklar için uygun")

    if not riskler:
        return "Hava koşulları hastalık gelişimi için düşük risk taşıyor"
    return " | ".join(riskler)