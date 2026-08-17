"""
stock_list_manager.py
─────────────────────
Analiz ve tavsiye motorunun kullandığı hisse senedi listesini
yerel bir JSON dosyasında (hisse_listesi.json) saklar.

Liste tamamen kullanıcı tarafından yönetilir; internetten liste
çekilmez. Yalnızca fiyat verileri için yfinance kullanılmaya devam eder.
"""

import json
import os

_LIST_FILE = "hisse_listesi.json"

# Yedek başlangıç listesi — dosya hiç oluşturulmamışsa ilk kez kullanılır
_DEFAULT_STOCKS = [
    {"kod": "ALBRK", "ad": "Albaraka Türk Katılım Bankası A.Ş."},
    {"kod": "BAHKM", "ad": "Bahadır Kimya Sanayi ve Ticaret A.Ş."},
    {"kod": "BEGYO", "ad": "Batı Ege Gayrimenkul Yatırım Ortaklığı A.Ş."},
    {"kod": "BIMAS", "ad": "BİM Birleşik Mağazalar A.Ş."},
    {"kod": "BINBN", "ad": "Bin Ulaşım ve Akıllı Şehir Teknolojileri A.Ş."},
    {"kod": "BORSK", "ad": "Bor Şeker A.Ş."},
    {"kod": "BOSSA", "ad": "Bossa Ticaret ve Sanayi İşletmeleri A.Ş."},
    {"kod": "CELHA", "ad": "Çelik Halat ve Tel Sanayii A.Ş."},
    {"kod": "COSMO", "ad": "Cosmos Yatırım Holding A.Ş."},
    {"kod": "DARDL", "ad": "Dardanel Önentaş Gıda Sanayi A.Ş."},
    {"kod": "DOFRB", "ad": "Dof Robotik Sanayi A.Ş."},
    {"kod": "EBEBK", "ad": "Ebebek Mağazacılık A.Ş."},
    {"kod": "EKSUN", "ad": "Eksun Gıda Tarım Sanayi ve Ticaret A.Ş."},
    {"kod": "ESCOM", "ad": "Escort Teknoloji Yatırım A.Ş."},
    {"kod": "FZLGY", "ad": "Fuzul Gayrimenkul Yatırım Ortaklığı A.Ş."},
    {"kod": "GUNDG", "ad": "Gündoğdu Gıda Süt Ürünleri Sanayi A.Ş."},
    {"kod": "IZFAS", "ad": "İzmir Fırça Sanayi ve Ticaret A.Ş."},
    {"kod": "IZINV", "ad": "İz Yatırım Holding A.Ş."},
    {"kod": "KRGYO", "ad": "Körfez Gayrimenkul Yatırım Ortaklığı A.Ş."},
    {"kod": "KTLEV", "ad": "Katılımevim Tasarruf Finansman A.Ş."},
    {"kod": "KZBGY", "ad": "Kızılbük Gayrimenkul Yatırım Ortaklığı A.Ş."},
    {"kod": "LXGYO", "ad": "Luxera Gayrimenkul Yatırım Ortaklığı A.Ş."},
    {"kod": "MCARD", "ad": "Metropal Kurumsal Hizmetler A.Ş."},
    {"kod": "MPARK", "ad": "MLP Sağlık Hizmetleri A.Ş."},
    {"kod": "PENGD", "ad": "Penguen Gıda Sanayi A.Ş."},
    {"kod": "RODRG", "ad": "Rodrigo Tekstil Sanayi ve Ticaret A.Ş."},
    {"kod": "YUNSA", "ad": "Yünsa Yünlü Sanayi ve Ticaret A.Ş."},
]


# ─────────────────────────────────────────────
#  Yardımcı: dosya okuma / yazma
# ─────────────────────────────────────────────

def _load_raw() -> list[dict]:
    """JSON dosyasından ham listeyi yükler. Yoksa varsayılan listeyi kaydedip döner."""
    if not os.path.exists(_LIST_FILE):
        _save_raw(_DEFAULT_STOCKS)
        return list(_DEFAULT_STOCKS)
    try:
        with open(_LIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return list(_DEFAULT_STOCKS)


def _save_raw(stocks: list[dict]):
    """Ham listeyi JSON dosyasına yazar."""
    try:
        with open(_LIST_FILE, "w", encoding="utf-8") as f:
            json.dump(stocks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [HATA] hisse_listesi.json kaydedilemedi: {e}")


# ─────────────────────────────────────────────
#  Dışa açık API
# ─────────────────────────────────────────────

def get_stock_list() -> list[str]:
    """
    Analiz motorunun beklediği formatta ['THYAO.IS', ...] listesini döndürür.
    """
    raw = _load_raw()
    return [f"{s['kod'].upper()}.IS" for s in raw]


def get_stock_list_with_names() -> list[dict]:
    """
    Tam listeyi [{'kod': 'THYAO', 'ad': 'Türk Hava Yolları'}, ...] formatında döndürür.
    """
    return _load_raw()


def add_stock(kod: str, ad: str = "") -> str:
    """
    Listeye yeni hisse ekler.

    Returns:
        'added'   — eklendi
        'exists'  — zaten var
        'invalid' — geçersiz kod
    """
    kod = kod.strip().upper()
    if kod.endswith(".IS"):
        kod = kod[:-3]
    if not kod or not (2 <= len(kod) <= 6):
        return "invalid"

    stocks = _load_raw()
    for s in stocks:
        if s["kod"] == kod:
            return "exists"

    stocks.append({"kod": kod, "ad": ad.strip()})
    stocks.sort(key=lambda x: x["kod"])
    _save_raw(stocks)
    return "added"


def remove_stock(kod: str) -> str:
    """
    Listeden hisse çıkarır.

    Returns:
        'removed'   — silindi
        'not_found' — listede yok
    """
    kod = kod.strip().upper()
    stocks = _load_raw()
    new_stocks = [s for s in stocks if s["kod"] != kod]

    if len(new_stocks) == len(stocks):
        return "not_found"

    _save_raw(new_stocks)
    return "removed"


def update_stock_name(kod: str, yeni_ad: str) -> str:
    """
    Listedeki bir hissenin şirket adını günceller.

    Returns:
        'updated'   — güncellendi
        'not_found' — listede yok
    """
    kod = kod.strip().upper()
    stocks = _load_raw()
    for s in stocks:
        if s["kod"] == kod:
            s["ad"] = yeni_ad.strip()
            _save_raw(stocks)
            return "updated"
    return "not_found"


def stock_count() -> int:
    """Listedeki hisse sayısını döndürür."""
    return len(_load_raw())
