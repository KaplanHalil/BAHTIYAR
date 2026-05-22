import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

# ============================================================================
#  GELİŞMİŞ TEKNİK ANALİZ MOTORU
#  Kullanılan Göstergeler:
#    1. RSI (14) - Momentum / Aşırı alım-satım
#    2. MACD (12,26,9) - Trend yönü ve ivme
#    3. SMA 50 & SMA 200 - Trend takibi, Golden/Death Cross
#    4. Bollinger Bantları (20,2) - Volatilite ve fiyat kanalı
#    5. Stochastic Oscillator (14,3) - Momentum doğrulama
#    6. Hacim Analizi - İşlem hacmi ile sinyal doğrulama
# ============================================================================

MAX_SKOR = 10  # Ağırlıklı puanlama sistemindeki maksimum puan

def analyze_stocks(data_dict):
    """
    BIST hisselerini gelişmiş teknik analiz ile değerlendirir.
    Ağırlıklı puanlama sistemi kullanır (Maks: 10 puan).
    """
    recommendations = []
    
    for ticker, df in data_dict.items():
        if len(df) < 50:
            continue
            
        try:
            close_prices = df['Close'].squeeze()
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]
            
            # Hacim verisini al
            volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
            if isinstance(volume, pd.DataFrame):
                volume = volume.iloc[:, 0]
                
            # ---- GÖSTERGE HESAPLAMALARI ----
            
            # 1. RSI (14 Günlük)
            rsi = RSIIndicator(close=close_prices, window=14).rsi()
            last_rsi = float(rsi.iloc[-1])
            
            # 2. MACD
            macd_indicator = MACD(close=close_prices)
            macd_diff = macd_indicator.macd_diff()
            last_macd_diff = float(macd_diff.iloc[-1])
            prev_macd_diff = float(macd_diff.iloc[-2]) if len(macd_diff) > 1 else 0
            
            # 3. SMA 50 & 200
            sma50 = SMAIndicator(close=close_prices, window=50).sma_indicator()
            last_sma50 = float(sma50.iloc[-1])
            
            has_sma200 = len(close_prices) >= 200
            last_sma200 = None
            if has_sma200:
                sma200 = SMAIndicator(close=close_prices, window=200).sma_indicator()
                last_sma200 = float(sma200.iloc[-1])
            
            # 4. Bollinger Bantları (20 günlük, 2 standart sapma)
            bb = BollingerBands(close=close_prices, window=20, window_dev=2)
            bb_lower = float(bb.bollinger_lband().iloc[-1])
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            bb_middle = float(bb.bollinger_mavg().iloc[-1])
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
            
            # 5. Stochastic Oscillator (14, 3)
            stoch = StochasticOscillator(
                high=df['High'].squeeze() if isinstance(df['High'].squeeze(), pd.Series) else df['High'].squeeze(),
                low=df['Low'].squeeze() if isinstance(df['Low'].squeeze(), pd.Series) else df['Low'].squeeze(),
                close=close_prices,
                window=14, smooth_window=3
            )
            last_stoch_k = float(stoch.stoch().iloc[-1])
            
            # 6. Hacim Analizi
            volume_confirmed = False
            if volume is not None and len(volume) >= 20:
                avg_volume = float(volume.iloc[-20:].mean())
                last_volume = float(volume.iloc[-1])
                volume_confirmed = last_volume > avg_volume * 1.2  # Son gün hacim ortalamanın %20 üstünde mi?
            
            last_price = float(close_prices.iloc[-1])
            
            # ---- AĞIRLIKLI PUANLAMA SİSTEMİ ----
            score = 0
            reasons = []
            
            # Kriter 1: RSI Analizi (Maks +2 puan)
            if last_rsi < 30:
                score += 2
                reasons.append(f"RSI Aşırı Satım ({last_rsi:.1f})")
            elif last_rsi < 40:
                score += 1
                reasons.append(f"RSI Düşük ({last_rsi:.1f})")
            elif last_rsi > 70:
                score -= 1  # Aşırı alım bölgesi, dikkat!
                
            # Kriter 2: MACD Analizi (Maks +2 puan)
            if last_macd_diff > 0 and prev_macd_diff <= 0:
                score += 2  # Taze pozitif kesişim (Crossover) - çok güçlü sinyal
                reasons.append("MACD Taze Kesişim ↑")
            elif last_macd_diff > 0:
                score += 1
                reasons.append("MACD Pozitif")
                
            # Kriter 3: Fiyat vs SMA50 (+1 puan)
            if last_price > last_sma50:
                score += 1
                reasons.append("Fiyat > SMA50")
                
            # Kriter 4: Golden Cross / Death Cross (Maks +2 puan)
            if has_sma200 and last_sma200 is not None:
                if last_sma50 > last_sma200:
                    score += 2
                    reasons.append("Golden Cross Aktif ★")
                else:
                    score -= 1  # Death Cross - olumsuz
                    
            # Kriter 5: Bollinger Bantları (+1 puan)
            if last_price <= bb_lower * 1.02:  # Alt banda çok yakın veya altında
                score += 1
                reasons.append("Bollinger Alt Bandı")
            if bb_width < 0.05:  # Bantlar çok dar = patlama (squeeze) bekleniyor
                score += 1
                reasons.append("Bollinger Sıkışma ⚡")
                
            # Kriter 6: Stochastic Oscillator (+1 puan)
            if last_stoch_k < 20:
                score += 1
                reasons.append(f"Stochastic Aşırı Satım ({last_stoch_k:.0f})")
            elif last_stoch_k > 80:
                score -= 1
                
            # Kriter 7: Hacim Doğrulaması (+1 puan bonus)
            if volume_confirmed and score >= 3:
                score += 1
                reasons.append("Hacim Doğrulaması ✓")
                
            # Skoru 0'ın altına düşürme
            score = max(score, 0)
            
            # Skor en az 4 ise tavsiye listesine ekle
            if score >= 4:
                sinyal_gucu = "Güçlü" if score >= 7 else ("Orta" if score >= 5 else "Zayıf")
                recommendations.append({
                    'Hisse': ticker.replace('.IS', ''),
                    'Fiyat': last_price,
                    'RSI': last_rsi,
                    'Skor': score,
                    'Sinyal': sinyal_gucu,
                    'Nedenler': ", ".join(reasons)
                })
                
        except Exception:
            continue
            
    # En yüksek skora, ardından en düşük RSI'a göre sırala
    recommendations.sort(key=lambda x: (-x['Skor'], x['RSI']))
    return recommendations


def evaluate_portfolio(portfolio, data_dict):
    """
    Portföydeki hisseleri gelişmiş teknik analiz ile değerlendirir.
    Sat/Tut/Güçlü Tut kararı verir.
    """
    evaluations = []
    
    for ticker, info in portfolio.items():
        yf_ticker = f"{ticker}.IS"
        if yf_ticker not in data_dict:
            continue
            
        df = data_dict[yf_ticker]
        if len(df) < 50:
            continue
            
        try:
            close_prices = df['Close'].squeeze()
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]
                
            volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
            if isinstance(volume, pd.DataFrame):
                volume = volume.iloc[:, 0]
                
            # Gösterge hesaplamaları
            rsi = RSIIndicator(close=close_prices, window=14).rsi()
            macd_indicator = MACD(close=close_prices)
            macd_diff = macd_indicator.macd_diff()
            sma50 = SMAIndicator(close=close_prices, window=50).sma_indicator()
            
            bb = BollingerBands(close=close_prices, window=20, window_dev=2)
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            
            stoch = StochasticOscillator(
                high=df['High'].squeeze() if isinstance(df['High'].squeeze(), pd.Series) else df['High'].squeeze(),
                low=df['Low'].squeeze() if isinstance(df['Low'].squeeze(), pd.Series) else df['Low'].squeeze(),
                close=close_prices,
                window=14, smooth_window=3
            )
            last_stoch_k = float(stoch.stoch().iloc[-1])
            
            last_price = float(close_prices.iloc[-1])
            last_rsi = float(rsi.iloc[-1])
            last_macd_diff = float(macd_diff.iloc[-1])
            last_sma50 = float(sma50.iloc[-1])
            
            has_sma200 = len(close_prices) >= 200
            last_sma200 = None
            if has_sma200:
                sma200 = SMAIndicator(close=close_prices, window=200).sma_indicator()
                last_sma200 = float(sma200.iloc[-1])
            
            # Hacim analizi
            volume_spike_down = False
            if volume is not None and len(volume) >= 20:
                avg_volume = float(volume.iloc[-20:].mean())
                last_volume = float(volume.iloc[-1])
                # Hacim yüksek + fiyat düşüyorsa tehlike
                if last_volume > avg_volume * 1.5:
                    price_change = (last_price - float(close_prices.iloc[-2])) / float(close_prices.iloc[-2])
                    if price_change < -0.02:
                        volume_spike_down = True
            
            # ---- SATIŞ PUANLAMA SİSTEMİ ----
            sat_puani = 0
            action = "Tut"
            reasons = []
            
            # RSI Aşırı Alım
            if last_rsi > 80:
                sat_puani += 3
                reasons.append(f"RSI Aşırı Alım ({last_rsi:.1f}) ⚠")
            elif last_rsi > 70:
                sat_puani += 2
                reasons.append(f"RSI Yüksek ({last_rsi:.1f})")
                
            # MACD Negatif
            if last_macd_diff < 0:
                sat_puani += 1
                reasons.append("MACD Negatif")
                
            # Fiyat SMA50 altında
            if last_price < last_sma50:
                sat_puani += 1
                reasons.append("Fiyat < SMA50")
                
            # Death Cross
            if has_sma200 and last_sma200 is not None and last_sma50 < last_sma200:
                sat_puani += 2
                reasons.append("Death Cross Aktif ✗")
                
            # Fiyat SMA200 altında (güçlü düşüş trendi)
            if has_sma200 and last_sma200 is not None and last_price < last_sma200:
                sat_puani += 2
                reasons.append("Fiyat < SMA200")
                
            # Bollinger üst bandına temas
            if last_price >= bb_upper * 0.98:
                sat_puani += 1
                reasons.append("Bollinger Üst Bandı")
                
            # Stochastic aşırı alım
            if last_stoch_k > 80:
                sat_puani += 1
                reasons.append(f"Stochastic Yüksek ({last_stoch_k:.0f})")
                
            # Hacim patlamasıyla birlikte düşüş
            if volume_spike_down:
                sat_puani += 2
                reasons.append("Yüksek Hacimli Düşüş ↓")
            
            # ---- KARAR MATRİSİ ----
            if sat_puani >= 5:
                action = "Sat"
            elif sat_puani >= 3:
                action = "Dikkatli Tut"
            else:
                action = "Güçlü Tut"
                if not reasons:
                    reasons.append("Trend Olumlu ✓")
                    
            # Kar/Zarar hesaplaması
            maliyet = info.get('maliyet', last_price)
            k_z = 0
            if maliyet > 0:
                k_z = ((last_price - maliyet) / maliyet) * 100
                
            evaluations.append({
                'Hisse': ticker,
                'Durum': action,
                'Fiyat': last_price,
                'Maliyet': maliyet,
                'K/Z %': k_z,
                'Lot': info['lot'],
                'Sat Puanı': sat_puani,
                'Nedenler': ", ".join(reasons)
            })
            
        except Exception:
            continue
        
    return evaluations
