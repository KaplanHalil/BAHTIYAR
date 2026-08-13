"""
BACKTEST MOTORU - Tarihsel Veriler ile Sistem Performansı Testi
Son 2 yıl (veya özel dönem) için simülasyon çalıştırır.
Günlük alım/satım tavsiyelerine göre işlem yapar ve sonuçları raporlar.

DÜZELTILEN HATALAR:
  1. Satış değerlendirmesi: evaluate_portfolio(), ticker key formatı (suffix'siz)
     ile data_dict key formatı (.IS suffix'li) arasındaki uyumsuzluk giderildi.
  2. Portföy doluyken yeni alım yapılmaması sağlandı (max_stocks limiti).
  3. Tarihsel veri; get_data_for_date() içinde artık tam o günün kapanış fiyatını
     kullanıyor (önceki gün verisi sızmasına karşı strict filtreleme).
  4. Rapordaki aktif pozisyonlar bölümündeki yanlış key isimleri düzeltildi.
  5. analyze_stocks() çağrısındaki data_dict key formatı düzeltildi.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from analyzer import analyze_stocks
from optimizer import allocate_budget
import json
import os


class BacktestEngine:
    """Backtest simülasyonunu yönetir"""

    def __init__(self, initial_budget=10000, start_date=None, end_date=None, max_stocks=3):
        """
        Args:
            initial_budget: Başlangıç bütçesi (TL)
            start_date: Başlangıç tarihi (None ise 2 yıl öncesi)
            end_date: Bitiş tarihi (None ise bugün)
            max_stocks: Maksimum hisse sayısı (portföyde aynı anda tutulacak)
        """
        self.initial_budget = initial_budget
        self.current_budget = initial_budget
        # Portfolio yapısı: {ticker (suffix'SİZ): {'lot': X, 'maliyet': Y, 'type': 'H', 'buy_date': Z}}
        self.portfolio = {}
        self.transactions = []   # İşlem geçmişi
        self.daily_values = []   # Her gün portföy değeri
        self.max_stocks = max_stocks
        self.stop_loss_pct = -8.0
        self.trailing_stop_pct = -10.0
        self.take_profit_pct = 18.0
        self.cooldown_days = 30
        self.cooldown_until = {}

        # Tarihler
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=730)  # 2 yıl öncesi

        self.start_date = start_date
        self.end_date = end_date
        self.current_date = start_date

    # ------------------------------------------------------------------ #
    #  VERİ ÇEKME
    # ------------------------------------------------------------------ #

    def fetch_historical_data(self, stock_list=None):
        """
        Tüm test dönemine ait tarihsel veriyi tek seferde çek.
        SMA200 için +300 gün warm-up, ayrıca altın/gümüş ve USDTRY de çekilir.
        """
        from data_fetcher import BIST_STOCKS, MARKET_INDEX

        if stock_list is None:
            stock_list = BIST_STOCKS

        warmup_start = self.start_date - timedelta(days=300)
        print(f"Tarihsel veriler çekiliyor ({warmup_start.date()} - {self.end_date.date()})...")

        result = {}

        # ── Hisse verisi ──
        try:
            data = yf.download(
                tickers=stock_list,
                start=warmup_start,
                end=self.end_date + timedelta(days=1),
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False
            )
            downloaded = 0
            for ticker in stock_list:
                try:
                    if ticker in data.columns.get_level_values(0):
                        df = data[ticker].dropna(how="all")
                        if not df.empty and len(df) >= 50:
                            result[ticker] = df
                            downloaded += 1
                except Exception:
                    pass
            print(f"  ✓ {downloaded}/{len(stock_list)} hisse için veri indirildi.")
        except Exception as e:
            print(f"  Hisse verisi hatası: {e}")

        # ── BIST 100 endeksi: hisse alımlarını genel piyasa rejimine göre filtreler ──
        try:
            index_data = yf.download(
                tickers=MARKET_INDEX,
                start=warmup_start,
                end=self.end_date + timedelta(days=1),
                auto_adjust=False,
                progress=False
            )
            if not index_data.empty:
                result[MARKET_INDEX] = index_data.dropna(how="all")
                print(f"  ✓ {MARKET_INDEX} endeks verisi indirildi.")
        except Exception as e:
            print(f"  BIST endeks verisi hatası: {e}")

        print()
        return result

    def get_data_for_date(self, data_dict, target_date):
        """
        Belirli bir işlem günü için, o güne KADAR (dahil) olan veriyi döndür.
        Bu, geleceğe bakma (look-ahead bias) hatasını önler.
        data_dict key formatı: 'THYAO.IS' (suffix'li)
        """
        result = {}
        target = target_date.date()

        for ticker, df in data_dict.items():
            # Sadece target_date'e kadar olan satırları al
            mask = df.index.date <= target
            df_filtered = df[mask]

            # Minimum 50 satır şart (gösterge hesapları için)
            if len(df_filtered) >= 50:
                result[ticker] = df_filtered

        return result

    # ------------------------------------------------------------------ #
    #  ANA SİMÜLASYON DÖNGÜSÜ
    # ------------------------------------------------------------------ #

    def run_simulation(self):
        """Backtest simülasyonunu çalıştır"""
        print("\n" + "=" * 80)
        print("BACKTEST SİMÜLASYONU BAŞLANDIYOR")
        print("=" * 80)
        print(f"Başlangıç Bütçesi: {self.initial_budget:.2f} TL")
        print(f"Dönem: {self.start_date.date()} - {self.end_date.date()}")
        print(f"Maksimum Hisse: {self.max_stocks}")
        print("=" * 80 + "\n")

        # Tüm tarihi veriyi tek seferde çek
        all_data = self.fetch_historical_data()

        if not all_data:
            print("Veri çekme başarısız!")
            return False

        # Simülasyon tarihleri (haftalık analiz — performans dengesi)
        trading_dates = self._get_trading_dates(all_data)

        print(f"Simülasyon {len(trading_dates)} işlem günü için çalışacak...\n")

        for i, current_date in enumerate(trading_dates):
            # İlerleme raporu (her 20 günde bir)
            if i % 20 == 0:
                total_val = self._calculate_portfolio_value(current_date, self.get_data_for_date(all_data, current_date)) + self.current_budget
                print(
                    f"[{i:>4}/{len(trading_dates)}] {current_date.date()} | "
                    f"Bütçe: {self.current_budget:>10.2f} TL | "
                    f"Portföy: {len(self.portfolio):>2} hisse | "
                    f"Toplam: {total_val:>10.2f} TL"
                )

            # O güne kadar olan veri penceresi
            data_for_analysis = self.get_data_for_date(all_data, current_date)

            if not data_for_analysis:
                continue

            # ── 1. Mevcut portföyü değerlendir ve sat tavsiyelerini işle ──
            if self.portfolio:
                self._evaluate_and_sell(current_date, data_for_analysis)

            # ── 2. Yeni alım yap (portföy dolmamışsa ve bütçe varsa) ──
            available_slots = self.max_stocks - len(self.portfolio)
            if available_slots > 0 and self.current_budget > 100:
                self._get_recommendations_and_buy(
                    current_date, data_for_analysis, available_slots
                )

            # ── 3. Günlük portföy değerlemesi ──
            portfolio_val = self._calculate_portfolio_value(current_date, data_for_analysis)
            self.daily_values.append({
                'date': current_date,
                'portfolio_value': portfolio_val,
                'budget': self.current_budget,
                'total_value': portfolio_val + self.current_budget,
                'portfolio_count': len(self.portfolio)
            })

        print(f"\n✓ Simülasyon {len(trading_dates)} gün için tamamlandı.\n")
        return True

    # ------------------------------------------------------------------ #
    #  YARDIMCI METOTLAR
    # ------------------------------------------------------------------ #

    def _get_trading_dates(self, data_dict):
        """
        Veri setindeki tüm işlem tarihlerini belirle.
        Simülasyon start_date'den itibaren haftada bir analiz yapar.
        """
        # Tüm benzersiz tarihleri topla
        all_dates = set()
        for ticker, df in data_dict.items():
            all_dates.update(df.index.date)

        sorted_dates = sorted(list(all_dates))

        # Sadece start_date'den itibaren olan günleri al
        start = self.start_date.date()
        end = self.end_date.date()
        filtered = [d for d in sorted_dates if start <= d <= end]

        # Her işlem gününde analiz yap
        daily_dates = [pd.Timestamp(d) for d in filtered]

        return daily_dates

    def _get_recommendations_and_buy(self, current_date, data_for_analysis, available_slots):
        """
        Teknik analiz ile hisse tavsiyesi al, bütçeye göre al.
        - analyze_stocks() kullanılır
        - Portföyde olmayan hisseler filtrelenir
        """
        try:
            from analyzer import analyze_stocks

            # Hisse analizi
            recommendations = analyze_stocks(data_for_analysis)

            if not recommendations:
                return

            # Portföyde olmayan varlıkları filtrele
            new_recs = [
                r for r in recommendations
                if r['Hisse'] not in self.portfolio
                and self.cooldown_until.get(r['Hisse'], self.start_date) <= current_date
            ]

            if not new_recs:
                return

            new_recs = new_recs[:available_slots]

            allocations, _ = allocate_budget(
                self.current_budget, new_recs, len(new_recs)
            )

            if not allocations:
                return

            for item in allocations:
                ticker = item['Hisse']          # suffix'siz hisse
                fiyat  = item['Fiyat']
                lot    = item['Lot']
                maliyet = item['Toplam Maliyet']
                asset_type = item.get('AssetType', 'HISSE')

                if lot <= 0:
                    continue

                self.portfolio[ticker] = {
                    'lot': lot,
                    'maliyet': fiyat,
                    'type': asset_type,
                    'buy_date': current_date,
                    'peak_price': fiyat
                }
                self.current_budget -= maliyet

                self.transactions.append({
                    'date': current_date,
                    'type': 'BUY',
                    'ticker': ticker,
                    'lots': lot,
                    'price': fiyat,
                    'amount': maliyet,
                    'asset_type': asset_type,
                    'budget_remaining': self.current_budget
                })

        except Exception as e:
            import sys
            print(f"  [UYARI] Alım işlemi hatası ({current_date.date()}): {e}", file=sys.stderr)

    def _evaluate_and_sell(self, current_date, data_for_analysis):
        """
        Portföydeki hisseleri değerlendir; sat tavsiyesi gelenleri sat.
        """
        try:
            from analyzer import evaluate_portfolio

            # ── Hisse satış değerlendirmesi ──
            if self.portfolio:
                evaluations = evaluate_portfolio(self.portfolio, data_for_analysis)
                for ev in evaluations:
                    ticker = ev['Hisse']
                    fiyat  = ev['Fiyat']
                    durum  = ev['Durum']
                    lot    = ev['Lot']

                    if ticker not in self.portfolio:
                        continue

                    pos = self.portfolio[ticker]
                    maliyet_fiyati = pos['maliyet']
                    peak_price = max(pos.get('peak_price', maliyet_fiyati), fiyat)
                    pos['peak_price'] = peak_price

                    profit_pct = ((fiyat - maliyet_fiyati) / maliyet_fiyati) * 100 if maliyet_fiyati > 0 else 0
                    drawdown_from_peak = ((fiyat - peak_price) / peak_price) * 100 if peak_price > 0 else 0

                    should_sell = (durum == 'Sat')
                    should_sell = should_sell or profit_pct <= self.stop_loss_pct
                    should_sell = should_sell or drawdown_from_peak <= self.trailing_stop_pct
                    should_sell = should_sell or (profit_pct >= self.take_profit_pct and durum == 'Dikkatli Tut')

                    if should_sell:
                        satış_tutarı   = lot * fiyat
                        kar_zarar_tl   = (fiyat - maliyet_fiyati) * lot
                        self.current_budget += satış_tutarı
                        del self.portfolio[ticker]
                        self.cooldown_until[ticker] = current_date + timedelta(days=self.cooldown_days)
                        self.transactions.append({
                            'date': current_date, 'type': 'SELL',
                            'ticker': ticker, 'lots': lot,
                            'price': fiyat, 'amount': satış_tutarı,
                            'profit_loss': kar_zarar_tl,
                            'asset_type': 'HISSE',
                            'budget_remaining': self.current_budget
                        })

        except Exception as e:
            import sys
            print(f"  [UYARI] Satış değerlendirme hatası ({current_date.date()}): {e}", file=sys.stderr)

    def _calculate_portfolio_value(self, current_date, data_for_analysis):
        """
        Portföyün o günkü piyasa değerini hesapla.
        - Hisseler: .IS suffix ile data_dict'te aranır
        """
        total_value = 0.0

        for ticker, info in self.portfolio.items():
            try:
                ticker_key = f"{ticker}.IS" if not ticker.endswith('.IS') else ticker
                df = data_for_analysis.get(ticker_key) or data_for_analysis.get(ticker)
                if df is None or df.empty:
                    price = info['maliyet']
                else:
                    price = float(df['Close'].iloc[-1])

                total_value += price * info['lot']

            except Exception:
                total_value += info.get('maliyet', 0) * info.get('lot', 0)

        return total_value


    # ------------------------------------------------------------------ #
    #  RAPOR ÜRETME
    # ------------------------------------------------------------------ #

    def generate_report(self):
        """Backtest raporunu üret ve döndür"""
        if not self.daily_values:
            return None

        last_day = self.daily_values[-1]

        start_value = self.initial_budget
        end_value = last_day['total_value']
        profit_loss = end_value - start_value
        profit_loss_pct = (profit_loss / start_value) * 100 if start_value > 0 else 0

        buy_transactions = [t for t in self.transactions if t['type'] == 'BUY']
        sell_transactions = [t for t in self.transactions if t['type'] == 'SELL']

        total_buy = sum(t['amount'] for t in buy_transactions)
        total_sell = sum(t['amount'] for t in sell_transactions)
        realized_profit = sum(t.get('profit_loss', 0) for t in sell_transactions)

        report = {
            'summary': {
                'start_date': self.start_date,
                'end_date': self.end_date,
                'initial_budget': start_value,
                'final_value': end_value,
                'profit_loss_tl': profit_loss,
                'profit_loss_pct': profit_loss_pct,
                'max_portfolio_value': max(dv['total_value'] for dv in self.daily_values),
                'min_portfolio_value': min(dv['total_value'] for dv in self.daily_values),
            },
            'transactions': {
                'total_buy_count': len(buy_transactions),
                'total_sell_count': len(sell_transactions),
                'total_buy_amount': total_buy,
                'total_sell_amount': total_sell,
                'realized_profit': realized_profit,
            },
            'final_status': {
                'holdings_value': last_day['portfolio_value'],
                'cash_remaining': last_day['budget'],
                'active_positions': len(self.portfolio),
                'total_portfolio_value': last_day['portfolio_value'] + last_day['budget'],
            },
            'daily_values': self.daily_values,
            'all_transactions': self.transactions,
            'final_portfolio': self.portfolio,
        }

        return report

    def save_report(self, report, filename=None):
        """Raporu TXT dosyasına kaydet"""
        if filename is None:
            filename = f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("BAHTIYAR BACKTEST RAPORU - SİSTEM PERFORMANSI TESTI\n")
            f.write("=" * 100 + "\n\n")

            # ÖZET
            f.write("📊 TEST ÖZETİ\n")
            f.write("-" * 100 + "\n")
            s = report['summary']
            f.write(f"Test Dönemi:              {s['start_date'].date()} → {s['end_date'].date()}\n")
            f.write(f"Başlangıç Bütçesi:        {s['initial_budget']:>12.2f} TL\n")
            f.write(f"Son Portföy Değeri:       {s['final_value']:>12.2f} TL\n")
            f.write(f"Kar/Zarar:                {s['profit_loss_tl']:>12.2f} TL  ({s['profit_loss_pct']:+.2f}%)\n")
            f.write(f"Maksimum Portföy Değeri:  {s['max_portfolio_value']:>12.2f} TL\n")
            f.write(f"Minimum Portföy Değeri:   {s['min_portfolio_value']:>12.2f} TL\n\n")

            # İŞLEM İSTATİSTİKLERİ
            f.write("💼 İŞLEM İSTATİSTİKLERİ\n")
            f.write("-" * 100 + "\n")
            t = report['transactions']
            f.write(f"Toplam Alım Sayısı:       {t['total_buy_count']:>12}\n")
            f.write(f"Toplam Satış Sayısı:      {t['total_sell_count']:>12}\n")
            f.write(f"Toplam Alım Tutarı:       {t['total_buy_amount']:>12.2f} TL\n")
            f.write(f"Toplam Satış Tutarı:      {t['total_sell_amount']:>12.2f} TL\n")
            f.write(f"Gerçekleşen Kar/Zarar:    {t['realized_profit']:>12.2f} TL\n\n")

            # FINAL DURUM
            f.write("📈 FİNAL DURUM (Test Sonunda)\n")
            f.write("-" * 100 + "\n")
            fin = report['final_status']
            f.write(f"Aktif Yatırım Pozisyonları: {fin['active_positions']}\n")
            f.write(f"Hisse Portföyü Değeri:      {fin['holdings_value']:>12.2f} TL\n")
            f.write(f"Kalan Nakit:                {fin['cash_remaining']:>12.2f} TL\n")
            f.write(f"Toplam Portföy Değeri:      {fin['total_portfolio_value']:>12.2f} TL\n\n")

            # AKTİF POZİSYONLAR
            if fin['active_positions'] > 0:
                f.write("📊 AKTİF YATIRIM POZİSYONLARI\n")
                f.write("-" * 100 + "\n")
                f.write(f"{'Ticker':<10} | {'Lot':<6} | {'Alış Fiyatı':<12} | {'Alış Tarihi':<15}\n")
                f.write("-" * 100 + "\n")
                for ticker, pos in report['final_portfolio'].items():
                    # DÜZELTME: key'ler 'lot', 'maliyet', 'buy_date' (eski kodda yanlış key kullanılıyordu)
                    buy_date = pos.get('buy_date', '-')
                    if hasattr(buy_date, 'date'):
                        buy_date = buy_date.date()
                    f.write(
                        f"{ticker:<10} | {pos['lot']:<6} | {pos['maliyet']:<12.2f} | {buy_date}\n"
                    )
                f.write("\n")

            # İŞLEM GEÇMİŞİ (son 100 işlem)
            f.write("📋 İŞLEM GEÇMİŞİ (Son 100 İşlem)\n")
            f.write("-" * 100 + "\n")
            f.write(
                f"{'Tarih':<12} | {'Tip':<5} | {'Ticker':<8} | "
                f"{'Lot':<5} | {'Fiyat':<10} | {'Tutar':<12} | "
                f"{'K/Z':<12} | {'Kalan Bütçe':<12}\n"
            )
            f.write("-" * 100 + "\n")

            for tr in report['all_transactions'][-100:]:
                if tr['type'] == 'SELL' and 'profit_loss' in tr:
                    kz_str = f"{tr['profit_loss']:>11.2f}"
                else:
                    kz_str = "           -"

                date_str = str(tr['date'].date()) if hasattr(tr['date'], 'date') else str(tr['date'])
                f.write(
                    f"{date_str:<12} | {tr['type']:<5} | {tr['ticker']:<8} | "
                    f"{tr['lots']:<5} | {tr['price']:<10.2f} | {tr['amount']:<12.2f} | "
                    f"{kz_str} | {tr['budget_remaining']:<12.2f}\n"
                )

            f.write("\n" + "=" * 100 + "\n")
            f.write(
                "Test Tamamlandı - Raporun Üretilme Tarihi: "
                + datetime.now().strftime("%d.%m.%Y %H:%M:%S") + "\n"
            )
            f.write("=" * 100 + "\n")

        return filename


# ------------------------------------------------------------------ #
#  ETKİLEŞİMLİ GİRİŞ NOKTASI
# ------------------------------------------------------------------ #

def run_backtest_interactive():
    """Etkileşimli backtest çalıştır"""
    print("\n" + "=" * 80)
    print("BACKTEST MODU - SİSTEM PERFORMANSI TESTİ")
    print("=" * 80 + "\n")

    while True:
        try:
            initial_budget = float(input("Başlangıç Bütçesi (TL) [Default: 10000]: ").strip() or "10000")
            if initial_budget > 0:
                break
            print("Lütfen pozitif bir sayı girin.")
        except ValueError:
            print("Hatalı giriş.")

    while True:
        try:
            days = int(input("Test Dönemi (Gün) [Default: 730 (2 yıl)]: ").strip() or "730")
            if days > 0:
                break
            print("Lütfen pozitif bir sayı girin.")
        except ValueError:
            print("Hatalı giriş.")

    while True:
        try:
            max_stocks = int(input("Maksimum Hisse Sayısı [Default: 5]: ").strip() or "5")
            if 1 <= max_stocks <= 20:
                break
            print("Lütfen 1-20 arasında bir sayı girin.")
        except ValueError:
            print("Hatalı giriş.")

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    engine = BacktestEngine(
        initial_budget=initial_budget,
        start_date=start_date,
        end_date=end_date,
        max_stocks=max_stocks
    )

    if engine.run_simulation():
        report = engine.generate_report()

        if report:
            print("\n" + "=" * 80)
            print("SONUÇLAR")
            print("=" * 80)
            s = report['summary']
            t = report['transactions']
            print(f"Başlangıç Bütçesi:     {s['initial_budget']:>12.2f} TL")
            print(f"Son Portföy Değeri:    {s['final_value']:>12.2f} TL")
            print(f"Kar/Zarar:             {s['profit_loss_tl']:>12.2f} TL ({s['profit_loss_pct']:+.2f}%)")
            print(f"\nAlım Sayısı:           {t['total_buy_count']:>12}")
            print(f"Satış Sayısı:          {t['total_sell_count']:>12}")
            print(f"Gerçekleşen Kar/Zarar: {t['realized_profit']:>12.2f} TL")
            print("=" * 80 + "\n")

            filename = engine.save_report(report)
            print(f"✓ Rapor kaydedildi: {filename}")
            print("✓ Detaylı sonuçlar için dosyayı açınız.")
    else:
        print("Backtest çalıştırılamadı.")


if __name__ == "__main__":
    run_backtest_interactive()
