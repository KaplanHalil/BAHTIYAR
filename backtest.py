"""
BACKTEST MOTORU - Tarihsel Veriler ile Sistem Performansı Testi
Son 2 yıl (veya özel dönem) için simülasyon çalıştırır.
Günlük alım/satım tavsiyelerine göre işlem yapar ve sonuçları raporlar.
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
            max_stocks: Maksimum hisse sayısı
        """
        self.initial_budget = initial_budget
        self.current_budget = initial_budget
        # Portfolio yapısı: {ticker: {'lot': X, 'maliyet': Y, 'type': 'H', 'buy_date': Z}}
        # Bu evaluate_portfolio fonksiyonuyla uyumlu
        self.portfolio = {}  
        self.transactions = []  # İşlem geçmişi
        self.daily_values = []  # Her gün portföy değeri
        self.max_stocks = max_stocks
        
        # Tarihler
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=730)  # 2 yıl öncesi
            
        self.start_date = start_date
        self.end_date = end_date
        self.current_date = start_date
        
    def fetch_historical_data(self, stock_list=None, period_days=730):
        """
        Tarihsel veri çek
        """
        from data_fetcher import BIST_STOCKS
        
        if stock_list is None:
            stock_list = BIST_STOCKS
        
        print(f"Tarihsel veriler çekiliyor ({self.start_date.date()} - {self.end_date.date()})...")
        
        try:
            data = yf.download(
                tickers=stock_list,
                start=self.start_date,
                end=self.end_date,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False
            )
            
            result = {}
            for ticker in stock_list:
                try:
                    if ticker in data.columns.levels[0]:
                        df = data[ticker].dropna(how="all")
                        if not df.empty:
                            result[ticker] = df
                except Exception:
                    pass
            
            return result
            
        except Exception as e:
            print(f"Veri çekme hatası: {e}")
            return {}
    
    def get_data_for_date(self, data_dict, target_date, lookback_days=252):
        """
        Belirli bir tarih için geçmiş veriyi keser (lookback penceresi)
        """
        result = {}
        
        for ticker, df in data_dict.items():
            # Belirtilen tarihten önceki veriyi filtrele
            mask = df.index.date <= target_date.date()
            df_filtered = df[mask]
            
            # Yeterli veri var mı kontrol et
            if len(df_filtered) >= 50:
                result[ticker] = df_filtered
        
        return result
    
    def run_simulation(self):
        """
        Backtest simülasyonunu çalıştır
        """
        print("\n" + "="*80)
        print("BACKTEST SİMÜLASYONU BAŞLANDIYOR")
        print("="*80)
        print(f"Başlangıç Bütçesi: {self.initial_budget:.2f} TL")
        print(f"Dönem: {self.start_date.date()} - {self.end_date.date()}")
        print(f"Maksimum Hisse: {self.max_stocks}")
        print("="*80 + "\n")
        
        # Tüm tarihi veri çek
        all_data = self.fetch_historical_data()
        
        if not all_data:
            print("Veri çekme başarısız!")
            return False
        
        # Güncelleme aralığı: Her hafta (5 iş günü)
        trading_dates = self._get_trading_dates(all_data)
        
        print(f"Simülasyon {len(trading_dates)} gün için çalışacak...\n")
        
        day_count = 0
        
        for i, current_date in enumerate(trading_dates):
            day_count += 1
            
            # Her 50 günde bir ilerleme göster
            if i % 50 == 0:
                print(f"[{i}/{len(trading_dates)}] {current_date.date()} - Bütçe: {self.current_budget:.2f} TL - Portföy: {len(self.portfolio)} hisse")
            
            # Bu tarih için veriyi al (lookback)
            data_for_analysis = self.get_data_for_date(all_data, current_date, lookback_days=252)
            
            if not data_for_analysis:
                continue
            
            # ===== PORTFÖY DEĞERLEMESİ =====
            # Mevcut portföyde hisse var mı?
            if self.portfolio:
                self._evaluate_and_sell(current_date, data_for_analysis)
            
            # ===== TAVSİYE AL VE ALIM YAP =====
            if self.current_budget > 0:
                self._get_recommendations_and_buy(current_date, data_for_analysis)
            
            # ===== GÜNLÜK DEĞERLEME =====
            daily_value = self._calculate_portfolio_value(current_date, data_for_analysis)
            self.daily_values.append({
                'date': current_date,
                'portfolio_value': daily_value,
                'budget': self.current_budget,
                'total_value': daily_value + self.current_budget,
                'portfolio_count': len(self.portfolio)
            })
        
        print(f"\n✓ Simülasyon {day_count} gün için tamamlandı.\n")
        return True
    
    def _get_trading_dates(self, data_dict):
        """
        Tüm hisselerin ortak ticaret tarihlerini al
        """
        all_dates = set()
        
        for ticker, df in data_dict.items():
            all_dates.update(df.index.date)
        
        # Tarihleri sırala
        sorted_dates = sorted(list(all_dates))
        
        # Her hafta (5 iş günü) bir analiz yap - performans iyileştirmesi
        dates_weekly = [pd.Timestamp(d) for i, d in enumerate(sorted_dates) if i % 5 == 0]
        
        return dates_weekly
    
    def _get_recommendations_and_buy(self, current_date, data_for_analysis):
        """
        Tavsiye al ve tavsiyelere göre hisse al
        """
        try:
            # Analiz yapıp tavsiye al
            recommendations = analyze_stocks(data_for_analysis)
            
            if not recommendations:
                return
            
            # Bütçeyi optimize et
            allocations, remaining = allocate_budget(self.current_budget, recommendations, self.max_stocks)
            
            if not allocations:
                return
            
            # Tavsiyelere göre al
            for item in allocations:
                ticker = item['Hisse']
                fiyat = item['Fiyat']
                lot = item['Lot']
                maliyet = item['Toplam Maliyet']
                
                if lot > 0:
                    # Portföye ekle veya güncelle
                    if ticker in self.portfolio:
                        eski_lot = self.portfolio[ticker]['lot']
                        eski_maliyet = self.portfolio[ticker]['maliyet']
                        
                        yeni_lot = eski_lot + lot
                        yeni_ort_maliyet = ((eski_lot * eski_maliyet) + maliyet) / yeni_lot
                        
                        self.portfolio[ticker]['lot'] = yeni_lot
                        self.portfolio[ticker]['maliyet'] = yeni_ort_maliyet
                    else:
                        self.portfolio[ticker] = {
                            'lot': lot,
                            'maliyet': fiyat,
                            'type': 'H',
                            'buy_date': current_date
                        }
                    
                    self.current_budget -= maliyet
                    
                    self.transactions.append({
                        'date': current_date,
                        'type': 'BUY',
                        'ticker': ticker,
                        'lots': lot,
                        'price': fiyat,
                        'amount': maliyet,
                        'budget_remaining': self.current_budget
                    })
        
        except Exception as e:
            pass
    
    def _evaluate_and_sell(self, current_date, data_for_analysis):
        """
        Portföydeki hisseleri değerlendir ve sat tavsiyesine göre satış yap
        """
        try:
            from analyzer import evaluate_portfolio
            
            # Portfolio'yu evaluate_portfolio uyumlu formata çevir
            # evaluate_portfolio {ticker: {'lot': X, 'maliyet': Y}} formatında bekliyor
            evaluations = evaluate_portfolio(self.portfolio, data_for_analysis)
            
            for ev in evaluations:
                ticker = ev['Hisse']
                fiyat = ev['Fiyat']
                durum = ev['Durum']
                lot = ev['Lot']
                
                # SAT tavsiyesi geldi mi?
                if durum == 'Sat' and ticker in self.portfolio:
                    maliyet_fiyati = self.portfolio[ticker]['maliyet']
                    satış_tutarı = lot * fiyat
                    kar_zarar_tl = (fiyat - maliyet_fiyati) * lot
                    
                    self.current_budget += satış_tutarı
                    del self.portfolio[ticker]
                    
                    self.transactions.append({
                        'date': current_date,
                        'type': 'SELL',
                        'ticker': ticker,
                        'lots': lot,
                        'price': fiyat,
                        'amount': satış_tutarı,
                        'profit_loss': kar_zarar_tl,
                        'budget_remaining': self.current_budget
                    })
        
        except Exception as e:
            pass
    
    def _calculate_portfolio_value(self, current_date, data_for_analysis):
        """
        Portföyün güncel değerini hesapla
        """
        total_value = 0
        
        for ticker, info in self.portfolio.items():
            try:
                # Ticker formatını kontrol et
                ticker_key = f"{ticker}.IS" if not ticker.endswith('.IS') else ticker
                
                if ticker_key in data_for_analysis:
                    df = data_for_analysis[ticker_key]
                    
                    # En son fiyatı al
                    last_price = float(df['Close'].iloc[-1])
                    lot = info['lot']
                    
                    total_value += last_price * lot
            
            except Exception:
                pass
        
        return total_value
    
    def generate_report(self):
        """
        Backtest raporunu üret ve döndür
        """
        if not self.daily_values:
            return None
        
        # Başlangıç ve son değerler
        first_day = self.daily_values[0]
        last_day = self.daily_values[-1]
        
        start_value = self.initial_budget
        end_value = last_day['total_value']
        profit_loss = end_value - start_value
        profit_loss_pct = (profit_loss / start_value) * 100 if start_value > 0 else 0
        
        # İşlem istatistikleri
        buy_transactions = [t for t in self.transactions if t['type'] == 'BUY']
        sell_transactions = [t for t in self.transactions if t['type'] == 'SELL']
        
        total_buy = sum([t['amount'] for t in buy_transactions])
        total_sell = sum([t['amount'] for t in sell_transactions])
        realized_profit = sum([t.get('profit_loss', 0) for t in sell_transactions])
        
        # Final portföy
        final_holdings_value = last_day['portfolio_value']
        final_budget = last_day['budget']
        
        report = {
            'summary': {
                'start_date': self.start_date,
                'end_date': self.end_date,
                'initial_budget': start_value,
                'final_value': end_value,
                'profit_loss_tl': profit_loss,
                'profit_loss_pct': profit_loss_pct,
                'max_portfolio_value': max([dv['total_value'] for dv in self.daily_values]),
                'min_portfolio_value': min([dv['total_value'] for dv in self.daily_values])
            },
            'transactions': {
                'total_buy_count': len(buy_transactions),
                'total_sell_count': len(sell_transactions),
                'total_buy_amount': total_buy,
                'total_sell_amount': total_sell,
                'realized_profit': realized_profit
            },
            'final_status': {
                'holdings_value': final_holdings_value,
                'cash_remaining': final_budget,
                'active_positions': len(self.portfolio),
                'total_portfolio_value': final_holdings_value + final_budget
            },
            'daily_values': self.daily_values,
            'all_transactions': self.transactions,
            'final_portfolio': self.portfolio
        }
        
        return report
    
    def save_report(self, report, filename=None):
        """
        Raporu TXT dosyasına kaydet
        """
        if filename is None:
            filename = f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*100 + "\n")
            f.write("BAHTIYAR BACKTEST RAPORU - SİSTEM PERFORMANSI TESTI\n")
            f.write("="*100 + "\n\n")
            
            # ÖZET
            f.write("📊 TEST ÖZETİ\n")
            f.write("-"*100 + "\n")
            summary = report['summary']
            f.write(f"Test Dönemi:              {summary['start_date'].date()} → {summary['end_date'].date()}\n")
            f.write(f"Başlangıç Bütçesi:        {summary['initial_budget']:>12.2f} TL\n")
            f.write(f"Son Portföy Değeri:       {summary['final_value']:>12.2f} TL\n")
            f.write(f"Kar/Zarar:                {summary['profit_loss_tl']:>12.2f} TL  ({summary['profit_loss_pct']:+.2f}%)\n")
            f.write(f"Maksimum Portföy Değeri:  {summary['max_portfolio_value']:>12.2f} TL\n")
            f.write(f"Minimum Portföy Değeri:   {summary['min_portfolio_value']:>12.2f} TL\n")
            f.write("\n")
            
            # İŞLEM İSTATİSTİKLERİ
            f.write("💼 İŞLEM İSTATİSTİKLERİ\n")
            f.write("-"*100 + "\n")
            trans = report['transactions']
            f.write(f"Toplam Alım Sayısı:       {trans['total_buy_count']:>12}\n")
            f.write(f"Toplam Satış Sayısı:      {trans['total_sell_count']:>12}\n")
            f.write(f"Toplam Alım Tutarı:       {trans['total_buy_amount']:>12.2f} TL\n")
            f.write(f"Toplam Satış Tutarı:      {trans['total_sell_amount']:>12.2f} TL\n")
            f.write(f"Gerçekleşen Kar/Zarar:    {trans['realized_profit']:>12.2f} TL\n")
            f.write("\n")
            
            # FINAL DURUM
            f.write("📈 FİNAL DURUM (Test Sonunda)\n")
            f.write("-"*100 + "\n")
            final = report['final_status']
            f.write(f"Aktif Yatırım Pozisyonları: {final['active_positions']}\n")
            f.write(f"Hisse Portföyü Değeri:      {final['holdings_value']:>12.2f} TL\n")
            f.write(f"Kalan Nakit:                {final['cash_remaining']:>12.2f} TL\n")
            f.write(f"Toplam Portföy Değeri:      {final['total_portfolio_value']:>12.2f} TL\n")
            f.write("\n")
            
            # AKTIF POZİSYONLAR
            if final['active_positions'] > 0:
                f.write("📊 AKTIF YATIRIMI POZİSYONLARI\n")
                f.write("-"*100 + "\n")
                f.write(f"{'Ticker':<10} | {'Lot':<6} | {'Alış Fiyatı':<12} | {'Alış Tarihi':<15}\n")
                f.write("-"*100 + "\n")
                
                for ticker, pos in report['final_portfolio'].items():
                    ticker_name = ticker.replace('.IS', '')
                    f.write(f"{ticker_name:<10} | {pos['lots']:<6} | {pos['buy_price']:<12.2f} | {pos['buy_date'].date()}\n")
                f.write("\n")
            
            # İŞLEM DETAYLARI (Son 50 işlem göster)
            f.write("📋 İŞLEM GEÇMİŞİ (Son 50 İşlem)\n")
            f.write("-"*100 + "\n")
            f.write(f"{'Tarih':<12} | {'Tip':<5} | {'Ticker':<8} | {'Lot':<5} | {'Fiyat':<10} | {'Tutar':<12} | {'K/Z':<12} | {'Kalan Bütçe':<12}\n")
            f.write("-"*100 + "\n")
            
            transactions = report['all_transactions'][-50:]  # Son 50 işlem
            
            for trans in transactions:
                profit_loss_str = ""
                if trans['type'] == 'SELL' and 'profit_loss' in trans:
                    pf = trans['profit_loss']
                    profit_loss_str = f"{pf:>11.2f}"
                else:
                    profit_loss_str = "         - "
                
                f.write(f"{str(trans['date'].date()):<12} | {trans['type']:<5} | {trans['ticker']:<8} | {trans['lots']:<5} | {trans['price']:<10.2f} | {trans['amount']:<12.2f} | {profit_loss_str} | {trans['budget_remaining']:<12.2f}\n")
            
            f.write("\n")
            f.write("="*100 + "\n")
            f.write("Test Tamamlandı - Raporun Üretilme Tarihi: " + datetime.now().strftime("%d.%m.%Y %H:%M:%S") + "\n")
            f.write("="*100 + "\n")
        
        return filename


def run_backtest_interactive():
    """
    Etkileşimli backtest çalıştır
    """
    print("\n" + "="*80)
    print("BACKTEST MODU - SİSTEM PERFORMANSI TESTİ")
    print("="*80 + "\n")
    
    # Parametreleri al
    while True:
        try:
            initial_budget = float(input("Başlangıç Bütçesi (TL) [Default: 10000]: ").strip() or "10000")
            if initial_budget > 0:
                break
            print("Lütfen pozitif bir sayı girin.")
        except ValueError:
            print("Hatalı giriş. Lütfen geçerli bir sayı girin.")
    
    while True:
        try:
            days = int(input("Test Dönemi (Gün) [Default: 730 (2 yıl)]: ").strip() or "730")
            if days > 0:
                break
            print("Lütfen pozitif bir sayı girin.")
        except ValueError:
            print("Hatalı giriş. Lütfen geçerli bir sayı girin.")
    
    while True:
        try:
            max_stocks = int(input("Maksimum Hisse Sayısı [Default: 3]: ").strip() or "3")
            if 1 <= max_stocks <= 10:
                break
            print("Lütfen 1-10 arasında bir sayı girin.")
        except ValueError:
            print("Hatalı giriş. Lütfen geçerli bir sayı girin.")
    
    # Backtest oluştur
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    engine = BacktestEngine(
        initial_budget=initial_budget,
        start_date=start_date,
        end_date=end_date,
        max_stocks=max_stocks
    )
    
    # Çalıştır
    if engine.run_simulation():
        # Rapor oluştur
        report = engine.generate_report()
        
        if report:
            # Ekrana özet yazdır
            print("\n" + "="*80)
            print("SONUÇLAR")
            print("="*80)
            print(f"Başlangıç Bütçesi:    {report['summary']['initial_budget']:>12.2f} TL")
            print(f"Son Portföy Değeri:   {report['summary']['final_value']:>12.2f} TL")
            print(f"Kar/Zarar:            {report['summary']['profit_loss_tl']:>12.2f} TL ({report['summary']['profit_loss_pct']:+.2f}%)")
            print(f"\nAlım Sayısı:          {report['transactions']['total_buy_count']:>12}")
            print(f"Satış Sayısı:         {report['transactions']['total_sell_count']:>12}")
            print(f"Gerçekleşen Kar/Zarar:{report['transactions']['realized_profit']:>12.2f} TL")
            print("="*80 + "\n")
            
            # Raporu dosyaya kaydet
            filename = engine.save_report(report)
            print(f"✓ Rapor kaydedildi: {filename}")
            print(f"✓ Detaylı sonuçlar için dosyayı açınız.")
    else:
        print("Backtest çalıştırılamadı.")


if __name__ == "__main__":
    run_backtest_interactive()
