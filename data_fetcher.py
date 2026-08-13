import yfinance as yf
import pandas as pd
import sys
import os
import logging
import json
import re

try:
    import requests
    from bs4 import BeautifulSoup
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False

# Genel piyasa rejimi için BIST 100 endeksi
MARKET_INDEX = 'XU100.IS'

# Yedek statik liste — helalfinans.net'e erişilemediğinde kullanılır
# Kaynak: helalfinans.net/hisseler?arindirmasiz=1 (27 hisse)
HELAL_STOCKS_FALLBACK = [
    "ALBRK.IS",  # Albaraka Türk Katılım Bankası A.Ş.
    "BAHKM.IS",  # Bahadır Kimya Sanayi ve Ticaret A.Ş.
    "BEGYO.IS",  # Batı Ege Gayrimenkul Yatırım Ortaklığı A.Ş.
    "BIMAS.IS",  # BİM Birleşik Mağazalar A.Ş.
    "BINBN.IS",  # Bin Ulaşım ve Akıllı Şehir Teknolojileri A.Ş.
    "BORSK.IS",  # Bor Şeker A.Ş.
    "BOSSA.IS",  # Bossa Ticaret ve Sanayi İşletmeleri A.Ş.
    "CELHA.IS",  # Çelik Halat ve Tel Sanayii A.Ş.
    "COSMO.IS",  # Cosmos Yatırım Holding A.Ş.
    "DARDL.IS",  # Dardanel Önentaş Gıda Sanayi A.Ş.
    "DOFRB.IS",  # Dof Robotik Sanayi A.Ş.
    "EBEBK.IS",  # Ebebek Mağazacılık A.Ş.
    "EKSUN.IS",  # Eksun Gıda Tarım Sanayi ve Ticaret A.Ş.
    "ESCOM.IS",  # Escort Teknoloji Yatırım A.Ş.
    "FZLGY.IS",  # Fuzul Gayrimenkul Yatırım Ortaklığı A.Ş.
    "GUNDG.IS",  # Gündoğdu Gıda Süt Ürünleri Sanayi A.Ş.
    "IZFAS.IS",  # İzmir Fırça Sanayi ve Ticaret A.Ş.
    "IZINV.IS",  # İz Yatırım Holding A.Ş.
    "KRGYO.IS",  # Körfez Gayrimenkul Yatırım Ortaklığı A.Ş.
    "KTLEV.IS",  # Katılımevim Tasarruf Finansman A.Ş.
    "KZBGY.IS",  # Kızılbük Gayrimenkul Yatırım Ortaklığı A.Ş.
    "LXGYO.IS",  # Luxera Gayrimenkul Yatırım Ortaklığı A.Ş.
    "MCARD.IS",  # Metropal Kurumsal Hizmetler A.Ş.
    "MPARK.IS",  # MLP Sağlık Hizmetleri A.Ş.
    "PENGD.IS",  # Penguen Gıda Sanayi A.Ş.
    "RODRG.IS",  # Rodrigo Tekstil Sanayi ve Ticaret A.Ş.
    "YUNSA.IS",  # Yünsa Yünlü Sanayi ve Ticaret A.Ş.
]

# Önbellek dosyası
_CACHE_FILE = "helal_stocks_cache.json"
_CACHE_TTL_HOURS = 24  # 24 saatte bir yenile

logging.disable(logging.CRITICAL)


def _load_cache():
    """Önbellekteki helal hisse listesini yükle. Geçerliyse döndür."""
    if not os.path.exists(_CACHE_FILE):
        return None
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        import time
        age_hours = (time.time() - data.get("timestamp", 0)) / 3600
        if age_hours < _CACHE_TTL_HOURS and data.get("stocks"):
            return data["stocks"]
    except Exception:
        pass
    return None


def _save_cache(stocks):
    """Helal hisse listesini önbelleğe yaz."""
    import time
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"timestamp": time.time(), "stocks": stocks}, f, ensure_ascii=False)
    except Exception:
        pass


def fetch_helal_stocks():
    """
    helalfinans.net/hisseler?arindirmasiz=1 adresinden arındırmasız hisseleri çeker.
    Başarısız olursa önbellek veya yedek statik liste döner.

    Returns:
        list: ['THYAO.IS', 'BIMAS.IS', ...] formatında hisse listesi
    """
    # Önce önbelleğe bak
    cached = _load_cache()
    if cached:
        return cached

    if not SCRAPER_AVAILABLE:
        print("  [UYARI] 'requests' veya 'beautifulsoup4' kurulu değil. Yedek liste kullanılıyor.")
        print("  Kurulum: pip install requests beautifulsoup4")
        return HELAL_STOCKS_FALLBACK

    url = "https://helalfinans.net/hisseler?arindirmasiz=1"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        stocks = []
        # Sayfadaki hisse kodlarını bul — genellikle tablo hücresi veya link içinde
        # Önce <a> etiketlerinde /hisse/ içerenleri dene
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            if "/hisse/" in href:
                code = href.rstrip("/").split("/")[-1].upper()
                if re.fullmatch(r"[A-Z]{3,5}", code):
                    ticker = f"{code}.IS"
                    if ticker not in stocks:
                        stocks.append(ticker)

        # Eğer link bazlı bulunamazsa metin bazlı tara
        if not stocks:
            for cell in soup.find_all(["td", "th", "span", "div"]):
                text = cell.get_text(strip=True).upper()
                if re.fullmatch(r"[A-Z]{3,5}", text):
                    ticker = f"{text}.IS"
                    if ticker not in stocks:
                        stocks.append(ticker)

        if stocks:
            print(f"  ✓ helalfinans.net'ten {len(stocks)} arındırmasız hisse çekildi.")
            _save_cache(stocks)
            return stocks
        else:
            print("  [UYARI] helalfinans.net sayfasında hisse kodu bulunamadı. Yedek liste kullanılıyor.")
            return HELAL_STOCKS_FALLBACK

    except Exception as e:
        print(f"  [UYARI] helalfinans.net'e erişilemedi ({e}). Yedek liste kullanılıyor.")
        return HELAL_STOCKS_FALLBACK


# Modül yüklendiğinde hisse listesini belirle (önbellek / canlı / yedek)
BIST_STOCKS = fetch_helal_stocks()


def fetch_data(stock_list=None, period="1y"):
    """
    Arındırmasız helal hisseleri ve BIST endeks verilerini çeker.

    Args:
        stock_list: Çekilecek hisse listesi (None ise BIST_STOCKS/helal listesi kullanılır)
        period: Veri dönemi (\"1y\", \"1mo\", etc)

    Returns:
        dict: {ticker: dataframe} formatında veri
    """
    if stock_list is None:
        stock_list = BIST_STOCKS

    result = {}

    # ========== HISSE VERİLERİ ==========
    if stock_list:
        try:
            data = yf.download(
                tickers=stock_list,
                period=period,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False
            )

            for ticker in stock_list:
                try:
                    if ticker in data.columns.levels[0]:
                        df = data[ticker].dropna(how="all")
                        if not df.empty:
                            result[ticker] = df
                except Exception:
                    pass

        except Exception as e:
            print(f"Hisse veri çekme hatası: {e}")

    # ========== BIST ENDEKS VERİSİ ==========
    try:
        index_data = yf.download(
            tickers=MARKET_INDEX,
            period=period,
            auto_adjust=False,
            progress=False
        )
        if not index_data.empty:
            result[MARKET_INDEX] = index_data.dropna(how="all")
    except Exception as e:
        print(f"BIST endeks veri çekme hatası: {e}")

    return result


