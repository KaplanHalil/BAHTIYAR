"""
news_analyzer.py — AI Destekli Haber Duygu Analizi Motoru
==========================================================
BIST hisselerine ait güncel haberleri Google News RSS'ten çeker ve
yapay zeka (Google Gemini veya OpenAI) ile Türkçe duygu analizi yapar.

API Anahtarı Yapılandırması (öncelik sırası):
  1. Çevre değişkeni : GEMINI_API_KEY  veya  OPENAI_API_KEY
  2. Yerel config    : ai_config.json  → {"gemini_api_key": "..."}

Önbellek: sentiment_cache.json (varsayılan TTL: 6 saat)
"""

import os
import json
import re
import sys
import warnings
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

# google-genai kütüphanesi Python 3.14'te DeprecationWarning fırlatır;
# bu bizim kodumuza ait olmayan, kütüphane içi bir uyarıdır — bastırıyoruz.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="google")
warnings.filterwarnings("ignore", message=".*_UnionGenericAlias.*")


# ── Sabitler ──────────────────────────────────────────────────────── #
CACHE_FILE      = "sentiment_cache.json"
CONFIG_FILE     = "ai_config.json"
CACHE_TTL_HOURS = 6
MAX_NEWS        = 5
NEWS_TIMEOUT    = 7   # saniye


# ═══════════════════════════════════════════════════════════════════ #
#  YAPILANDIRMA
# ═══════════════════════════════════════════════════════════════════ #

def load_ai_config() -> dict:
    """ai_config.json'dan API ayarlarını yükler."""
    if Path(CONFIG_FILE).exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_ai_config(config: dict):
    """API ayarlarını ai_config.json'a kaydeder."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [HATA] ai_config.json kaydedilemedi: {e}")


def get_api_key(provider: str = 'gemini') -> str:
    """
    API anahtarını önce ortam değişkeninden, sonra config dosyasından alır.
    provider: 'gemini' veya 'openai'
    """
    env_map = {'gemini': 'GEMINI_API_KEY', 'openai': 'OPENAI_API_KEY'}
    cfg_map = {'gemini': 'gemini_api_key', 'openai': 'openai_api_key'}

    key = os.environ.get(env_map.get(provider, ''), '').strip()
    if not key:
        cfg = load_ai_config()
        key = cfg.get(cfg_map.get(provider, ''), '').strip()
    return key


def is_ai_configured() -> bool:
    """Herhangi bir AI sağlayıcısının yapılandırılıp yapılandırılmadığını döndürür."""
    return bool(get_api_key('gemini') or get_api_key('openai'))


def get_active_provider() -> str:
    """Aktif AI sağlayıcısının adını döndürür ('gemini', 'openai' veya 'yok')."""
    if get_api_key('gemini'):
        return 'gemini'
    if get_api_key('openai'):
        return 'openai'
    return 'yok'


# ═══════════════════════════════════════════════════════════════════ #
#  ÖNBELLEK (CACHE) YÖNETİMİ
# ═══════════════════════════════════════════════════════════════════ #

def _load_cache() -> dict:
    if not Path(CACHE_FILE).exists():
        return {}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache: dict):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass


def _get_cached(ticker: str) -> dict | None:
    cache = _load_cache()
    entry = cache.get(ticker)
    if not entry:
        return None
    try:
        cached_time = datetime.fromisoformat(entry['timestamp'])
        if datetime.now() - cached_time > timedelta(hours=CACHE_TTL_HOURS):
            return None
    except Exception:
        return None
    return entry


def _set_cache(ticker: str, result: dict):
    cache = _load_cache()
    result['timestamp'] = datetime.now().isoformat()
    cache[ticker] = result
    _save_cache(cache)


def clear_sentiment_cache():
    """Tüm sentiment önbelleğini temizler."""
    try:
        if Path(CACHE_FILE).exists():
            Path(CACHE_FILE).unlink()
            return True
    except Exception:
        pass
    return False


# ═══════════════════════════════════════════════════════════════════ #
#  HABER ÇEKME (Google News RSS)
# ═══════════════════════════════════════════════════════════════════ #

def fetch_news_for_stock(ticker_code: str, company_name: str = None) -> list[str]:
    """
    Google News RSS'ten hisse için güncel haber başlıkları çeker.

    Args:
        ticker_code : 'THYAO' gibi suffix'siz hisse kodu
        company_name: Şirket adı (daha iyi sonuç verir)

    Returns:
        Haber başlıklarının listesi (max MAX_NEWS adet)
    """
    headlines = []
    queries = []

    # Önce şirket adıyla, sonra ticker koduyla ara
    if company_name and len(company_name) > 3:
        queries.append(f"{company_name} borsa hisse")
    queries.append(f"{ticker_code} BIST hisse")

    for query in queries:
        if len(headlines) >= MAX_NEWS:
            break
        try:
            encoded = urllib.parse.quote(query)
            url = (
                f"https://news.google.com/rss/search?q={encoded}"
                f"&hl=tr&gl=TR&ceid=TR:tr"
            )
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; BAHTIYAR-NewsBot/2.1)'}
            )
            with urllib.request.urlopen(req, timeout=NEWS_TIMEOUT) as resp:
                content = resp.read().decode('utf-8', errors='replace')

            # <title> etiketlerini basit regex ile çıkar
            raw_titles = re.findall(
                r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>',
                content, re.DOTALL
            )
            for title in raw_titles[1:]:   # ilk eleman feed başlığı, atla
                clean = re.sub(r'<[^>]+>', '', title).strip()
                clean = (clean.replace('&amp;', '&')
                              .replace('&lt;', '<')
                              .replace('&gt;', '>')
                              .replace('&quot;', '"')
                              .replace('&#39;', "'"))
                if clean and len(clean) > 15:
                    headlines.append(clean)
                if len(headlines) >= MAX_NEWS:
                    break

        except Exception:
            continue

    return headlines[:MAX_NEWS]


# ═══════════════════════════════════════════════════════════════════ #
#  YAPAY ZEKA DUYGU ANALİZİ
# ═══════════════════════════════════════════════════════════════════ #

def _build_prompt(ticker_code: str, headlines: list[str], company_name: str = None) -> str:
    """AI'ya gönderilecek prompt metnini oluşturur."""
    name_str = f" ({company_name})" if company_name else ""
    news_str = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(headlines))

    return f"""Sen deneyimli bir Türk borsası analistisisin.
Borsa İstanbul'da işlem gören {ticker_code}{name_str} hissesiyle ilgili güncel haber başlıkları:

{news_str}

GÖREV: Bu haberlerin {ticker_code} hissesinin kısa vadeli (1-5 işlem günü) fiyatı üzerindeki beklenen etkisini değerlendir.

YALNIZCA şu JSON formatında yanıt ver:
{{
  "skor": <-2 ile +2 arasında tam sayı>,
  "guven": <0.0 ile 1.0 arası ondalık>,
  "ozet": "<Türkçe, max 80 karakter>",
  "etiket": "<COK_OLUMLU | OLUMLU | NOTR | OLUMSUZ | COK_OLUMSUZ>"
}}

Skor kılavuzu:
+2 → Çok güçlü pozitif (büyük sözleşme, rekor kâr, analist yükseltmesi)
+1 → Hafif pozitif (olumlu gelişmeler)
 0 → Nötr veya karışık haberler
-1 → Hafif negatif (belirsizlik, riskler)
-2 → Çok güçlü negatif (büyük zarar, dava, ceza, iflas)"""


def _parse_json_response(text: str) -> dict | None:
    """AI yanıt metninden JSON bloğunu çıkarır."""
    try:
        match = re.search(r'\{.*?\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return None


def _analyze_gemini(ticker_code: str, headlines: list[str], company_name: str = None) -> dict | None:
    """Google Gemini API (google-genai) ile duygu analizi yapar."""
    api_key = get_api_key('gemini')
    if not api_key:
        return None

    # Öncelik sırasıyla denenecek modeller
    MODELS = ['gemini-flash-latest', 'gemini-flash-lite-latest', 'gemini-pro-latest']

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = _build_prompt(ticker_code, headlines, company_name)

        last_err = None
        for model in MODELS:
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                result = _parse_json_response(response.text)
                if result is None:
                    import sys
                    print(f"  [UYARI] {ticker_code}: JSON parse edilemedi → {response.text[:120]}", file=sys.stderr)
                return result
            except Exception as e:
                last_err = e
                continue   # bir sonraki modeli dene

        import sys
        print(f"  [UYARI] Gemini API hatası ({ticker_code}): {last_err}", file=sys.stderr)
        return None

    except ImportError:
        print("  [UYARI] google-genai kurulu değil: pip install google-genai")
        return None
    except Exception as e:
        import sys
        print(f"  [UYARI] Gemini başlatma hatası ({ticker_code}): {e}", file=sys.stderr)
        return None


def _analyze_openai(ticker_code: str, headlines: list[str], company_name: str = None) -> dict | None:
    """OpenAI GPT API ile duygu analizi yapar."""
    api_key = get_api_key('openai')
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = _build_prompt(ticker_code, headlines, company_name)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )
        return _parse_json_response(resp.choices[0].message.content)
    except ImportError:
        print("  [UYARI] openai paketi kurulu değil: pip install openai")
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════ #
#  ANA FONKSİYON
# ═══════════════════════════════════════════════════════════════════ #

_DEFAULT_RESULT = {
    'skor': 0, 'guven': 0.0,
    'ozet': 'Analiz yapılamadı.',
    'etiket': 'NOTR',
    'haberler': [],
    'kaynak': 'yok'
}


def get_sentiment_score(ticker_code: str, company_name: str = None,
                         use_cache: bool = True) -> dict:
    """
    Hisse için AI destekli haber duygu analizi yapar.

    Args:
        ticker_code : 'THYAO' gibi suffix'siz kod
        company_name: Şirket adı (opsiyonel, arama kalitesini artırır)
        use_cache   : Önbellek kullanılsın mı?

    Returns dict:
        skor    : int  → -2..+2  (teknik skora eklenir)
        guven   : float → 0..1
        ozet    : str  → Türkçe kısa açıklama
        etiket  : str  → COK_OLUMLU / OLUMLU / NOTR / OLUMSUZ / COK_OLUMSUZ
        haberler: list[str] → çekilen haber başlıkları
        kaynak  : str  → 'gemini' | 'openai' | 'cache' | 'yok'
    """
    # 1. Önbellek kontrolü
    if use_cache:
        cached = _get_cached(ticker_code)
        if cached:
            cached['kaynak'] = 'cache'
            return cached

    # 2. Haberleri çek
    headlines = fetch_news_for_stock(ticker_code, company_name)
    if not headlines:
        result = dict(_DEFAULT_RESULT)
        result['ozet'] = 'Haber bulunamadı.'
        return result

    # 3. AI analizi: önce Gemini, yoksa OpenAI
    ai_result = _analyze_gemini(ticker_code, headlines, company_name)
    source = 'gemini'

    if ai_result is None:
        ai_result = _analyze_openai(ticker_code, headlines, company_name)
        source = 'openai'

    # 4. AI yoksa skor 0, haberleri yine de döndür
    if ai_result is None:
        return {
            'skor': 0, 'guven': 0.5,
            'ozet': 'AI yapılandırılmamış; haberler listelendi.',
            'etiket': 'NOTR',
            'haberler': headlines,
            'kaynak': 'yok'
        }

    # 5. Skoru sınırla ve sonucu hazırla
    ai_result['skor'] = max(-2, min(2, int(ai_result.get('skor', 0))))
    ai_result['guven'] = max(0.0, min(1.0, float(ai_result.get('guven', 0.5))))
    ai_result['haberler'] = headlines
    ai_result['kaynak'] = source

    # 6. Önbelleğe kaydet
    _set_cache(ticker_code, ai_result)

    return ai_result


def analyze_sentiment_batch(tickers_info: list[dict],
                             verbose: bool = True) -> dict[str, dict]:
    """
    Birden fazla hisse için toplu sentiment analizi.

    Args:
        tickers_info: [{'kod': 'THYAO', 'ad': 'Türk Hava Yolları'}, ...]
        verbose     : İlerleme mesajlarını yazdır

    Returns:
        {'THYAO': {skor, guven, ozet, ...}, ...}
    """
    results = {}
    total = len(tickers_info)

    for i, item in enumerate(tickers_info):
        kod = item.get('kod', '')
        ad  = item.get('ad', '')
        if not kod:
            continue

        if verbose:
            print(f"  [{i+1}/{total}] {kod} analiz ediliyor...", end='\r', flush=True)

        results[kod] = get_sentiment_score(kod, ad)

    if verbose:
        print()  # satır sonu

    return results


# ═══════════════════════════════════════════════════════════════════ #
#  YARDIMCI: Etiket renk/sembol çıktısı
# ═══════════════════════════════════════════════════════════════════ #

ETIKET_SEMBOL = {
    'COK_OLUMLU': '🟢🟢',
    'OLUMLU':     '🟢',
    'NOTR':       '⚪',
    'OLUMSUZ':    '🔴',
    'COK_OLUMSUZ':'🔴🔴',
}

ETIKET_TR = {
    'COK_OLUMLU': 'Çok Olumlu',
    'OLUMLU':     'Olumlu',
    'NOTR':       'Nötr',
    'OLUMSUZ':    'Olumsuz',
    'COK_OLUMSUZ':'Çok Olumsuz',
}


def format_sentiment(result: dict) -> str:
    """Sentiment sonucunu tek satır metin olarak formatlar."""
    etiket = result.get('etiket', 'NOTR')
    sembol = ETIKET_SEMBOL.get(etiket, '⚪')
    etiket_tr = ETIKET_TR.get(etiket, 'Nötr')
    skor  = result.get('skor', 0)
    ozet  = result.get('ozet', '')
    guven = result.get('guven', 0)
    skor_str = f"+{skor}" if skor > 0 else str(skor)

    return f"{sembol} {etiket_tr} (Skor: {skor_str}, Güven: %{int(guven*100)}) — {ozet}"
