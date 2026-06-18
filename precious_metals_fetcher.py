"""
Kuveyt Türk - Altın ve Gümüş Fiyat Fetcher
TCMB API'sinden ve webscraping ile canlı fiyatlar alıyor
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import json
import os

# TCMB API'den altın ve gümüş verilerini al
def fetch_precious_metals_from_tcmb():
    """
    TCMB (Türkiye Cumhuriyet Merkez Bankası) API'sinden
    altın ve gümüş fiyatlarını çeker.
    """
    try:
        # Bugünün tarihini al
        today = datetime.now().strftime("%Y-%m-%d")
        
        # TCMB API endpoint
        url = f"https://www.tcmb.gov.tr/kurlar/{datetime.now().strftime('%d%m%Y')}.xml"
        
        response = requests.get(url, timeout=10)
        response.encoding = 'utf-8'
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            metals_data = {}
            
            # XML'den altın ve gümüş kodlarını ara
            # Altın: "XAU", Gümüş: "XAG"
            for currency in root.findall('Currency'):
                code = currency.get('Code')
                
                if code in ['XAU', 'XAG']:  # XAU=Altın, XAG=Gümüş
                    name_elem = currency.find('CurrencyName')
                    selling_elem = currency.find('Selling')
                    
                    if name_elem is not None and selling_elem is not None:
                        name = name_elem.text
                        price = float(selling_elem.text) if selling_elem.text else 0
                        
                        metals_data[code] = {
                            'name': name,
                            'price': price,
                            'date': today,
                            'source': 'TCMB'
                        }
            
            return metals_data if metals_data else None
            
    except Exception as e:
        print(f"TCMB'den veri çekme hatası: {e}")
        return None

# Alternatif: Kuveyt Türk'ün XML web servisi kullanarak
def fetch_precious_metals_from_kuveyt_turk():
    """
    Kuveyt Türk'ün finansal araçlarından altın ve gümüş fiyatlarını çeker.
    Web scraping ile canlı fiyatları alır.
    """
    try:
        # Kuveyt Türk kuyumcu/değerli metal hizmetleri sayfası
        url = "https://www.kuveytturk.com.tr/tr-tr/bireysel/yatirim-uygulamalari/kuyumculuk"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        
        # JSON formatında veriler varsa çıkar
        if 'prices' in response.text or 'altin' in response.text.lower():
            # HTML parsing ile fiyatları çıkart
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Bu kısım site yapısına göre custom yazılmalıdır
            # Genel taslak:
            metals_data = {}
            
            # Örnek: Belirlenen class/id'den verileri çıkart
            price_elements = soup.find_all('span', {'class': 'price'})  # Örnek
            
            return metals_data if metals_data else None
            
    except Exception as e:
        print(f"Kuveyt Türk'ten veri çekme hatası: {e}")
        return None

# Cache sistemli fetcher
def fetch_precious_metals(use_cache=True, cache_minutes=60):
    """
    Altın ve gümüş fiyatlarını çeker.
    Cache dosyası varsa ve yeterince yeni ise onu kullanır.
    """
    cache_file = "precious_metals_cache.json"
    
    # Cache dosyası varsa ve hala geçerliyse kullan
    if use_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                cache_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
                
                if datetime.now() - cache_time < timedelta(minutes=cache_minutes):
                    return cache_data.get('data', {})
        except:
            pass
    
    # Yeni veri çek
    metals_data = fetch_precious_metals_from_tcmb()
    
    if metals_data:
        # Cache'e kaydet
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': metals_data
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except:
            pass
        
        return metals_data
    
    # Eğer TCMB'den veri gelmezse, cache'den eski veri kullan
    if use_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                return cache_data.get('data', {})
        except:
            pass
    
    # Fallback: Dummy veri döndür
    return get_fallback_prices()

def get_fallback_prices():
    """
    Ağ bağlantısı olmadığında fallback fiyatları döndür.
    Güncel fiyatlar yerine önceki bilinen fiyatları kullan.
    """
    return {
        'XAU': {
            'name': 'Altın (Gram)',
            'price': 650.0,  # Örnek fiyat
            'date': datetime.now().strftime("%Y-%m-%d"),
            'source': 'FALLBACK'
        },
        'XAG': {
            'name': 'Gümüş (Gram)',
            'price': 28.0,  # Örnek fiyat
            'date': datetime.now().strftime("%Y-%m-%d"),
            'source': 'FALLBACK'
        }
    }

def get_metals_as_tickers():
    """
    Altın ve gümüşü hisse gibi ticker listesi olarak döndür.
    Analiz sistemine entegre etmek için.
    """
    return ['ALTIN', 'GUMUS']

def fetch_metals_history(periods=252):
    """
    Altın ve gümüş için tarihsel veri çeker.
    Teknik analiz için gerekli.
    
    Not: TCMB günlük veri sağlamadığından,
    alternative kaynaklardan (Yahoo Finance, etc) veri çekebiliriz.
    """
    try:
        # Alternatif: Yahoo Finance'ten çekmek
        import yfinance as yf
        
        # Altın ve Gümüş ticker'ları (USDTRY bazında)
        data_dict = {}
        
        # GC=F: Altın futures
        # SI=F: Gümüş futures
        # AUDUSD: Altın USD bazında
        
        for ticker in ['GC=F', 'SI=F']:
            try:
                df = yf.download(
                    ticker,
                    period='1y',
                    progress=False
                )
                
                if not df.empty:
                    # TL'ye çevirmek için USDTRY verisi gerek
                    # Şimdilik USD olarak tutabiliriz
                    data_dict[ticker] = df
                    
            except Exception as e:
                print(f"{ticker} için tarihsel veri çekme hatası: {e}")
        
        return data_dict
        
    except Exception as e:
        print(f"Altın/Gümüş tarihsel veri hatası: {e}")
        return {}

if __name__ == "__main__":
    # Test
    metals = fetch_precious_metals()
    print("Altın/Gümüş Fiyatları:")
    print(json.dumps(metals, ensure_ascii=False, indent=2))
