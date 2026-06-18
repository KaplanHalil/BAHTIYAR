import sys
import os
import yfinance as yf

from budget_manager import load_budget, save_budget, load_portfolio, save_portfolio, set_profile, get_all_profiles, delete_profile, reset_current_profile
from data_fetcher import fetch_data
from analyzer import analyze_stocks, evaluate_portfolio
from optimizer import allocate_budget
from logger import log_transaction, set_logger_profile
from shutil import get_terminal_size

try:
    from colorama import init as _colorama_init, Fore, Style
    _colorama_init()
    COLORAMA_AVAILABLE = True
except Exception:
    COLORAMA_AVAILABLE = False
    class Fore:  # fallback no-op
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = RESET = ''
    class Style:
        BRIGHT = NORMAL = RESET_ALL = ''


def print_separator():
    print("=" * 70)


def _colored(text: str, color: str = None, bright: bool = False) -> str:
    if not COLORAMA_AVAILABLE or not color:
        return text
    col = getattr(Fore, color.upper(), '')
    style = Style.BRIGHT if bright else ''
    return f"{style}{col}{text}{Style.RESET_ALL}"


def print_banner():
    term_width = get_terminal_size((80, 20)).columns
    w = min(66, max(40, term_width - 10))
    title = "BAHTİYAR PORTFÖY YÖNETİM SİSTEMİ"
    subtitle = "Gelişmiş Analiz ve Tavsiye Motoru ile Akıllı Yatırım Asistanınız"
    top = "╔" + "═" * w + "╗"
    bottom = "╚" + "═" * w + "╝"
    print(_colored(top, 'cyan', True))
    print(_colored("║" + title.center(w) + "║", 'green', True))
    print(_colored("║" + subtitle.center(w) + "║", 'yellow'))
    print(_colored(bottom, 'cyan', True))
    print()

def migrate_old_data():
    if os.path.exists("butce.json") and not os.path.exists("default_butce.json"):
        os.rename("butce.json", "default_butce.json")
    if os.path.exists("islem_gecmisi.md") and not os.path.exists("default_islem_gecmisi.md") and not os.path.exists("default_islem_gecmisi.txt"):
        os.rename("islem_gecmisi.md", "default_islem_gecmisi.md")
    if os.path.exists("islem_gecmisi.txt") and not os.path.exists("default_islem_gecmisi.txt"):
        os.rename("islem_gecmisi.txt", "default_islem_gecmisi.txt")

def init_profile():
    print_banner()
    print(_colored("Hoş geldiniz! Lütfen bir portföy seçin veya yenisini oluşturun.", 'magenta'))
    print()
    profiles = get_all_profiles()
    
    if profiles:
        print(_colored("Sistemde Kayıtlı Portföyler:", 'cyan', True))
        for i, p in enumerate(profiles):
            print(_colored(f" {i+1}. ", 'yellow', True) + _colored(f"{p}", 'green'))
        print("-" * 40)
        print(_colored("1. Var olan bir portföyü seç", 'blue'))
        print(_colored("2. Yeni bir portföy oluştur", 'blue'))

        choice = input(_colored("Seçiminiz (1/2): ", 'magenta')).strip()
        if choice == '1':
            try:
                p_idx = int(input(_colored("Girmek istediğiniz portföy numarası: ", 'magenta'))) - 1
                if 0 <= p_idx < len(profiles):
                    p_name = profiles[p_idx]
                else:
                    print(_colored("Geçersiz numara! Yeni portföy oluşturma ekranına yönlendiriliyorsunuz...", 'red'))
                    p_name = input(_colored("Yeni Portföy (Kullanıcı) Adı: ", 'magenta')).strip()
            except ValueError:
                print(_colored("Geçersiz giriş! Yeni portföy oluşturma ekranına yönlendiriliyorsunuz...", 'red'))
                p_name = input(_colored("Yeni Portföy (Kullanıcı) Adı: ", 'magenta')).strip()
        else:
            p_name = input(_colored("Yeni Portföy (Kullanıcı) Adı: ", 'magenta')).strip()
    else:
        print("Sistemde henüz kayıtlı bir portföy bulunmuyor.")
        p_name = input("Yeni Portföy (Kullanıcı) Adı: ").strip()
        
    if not p_name:
        p_name = "default"
        
    set_profile(p_name)
    set_logger_profile(p_name)
    print(f"\n--> [{p_name.upper()}] portföyü aktif edildi <--")
    return p_name

def main():
    migrate_old_data()
    
    active_profile = init_profile()
    
    while True:
        budget = load_budget()
        portfolio = load_portfolio()
        print("\n")
        print_banner()
        print(_colored(f"Aktif Portföy: ", 'yellow', True) + _colored(f"[{active_profile.upper()}]", 'green', True))
        print(_colored(f"Mevcut Bütçeniz: ", 'yellow') + _colored(f"{budget:.2f} TL", 'green'))
        print(_colored(f"Portföyünüzdeki Hisse Sayısı: ", 'yellow') + _colored(f"{len(portfolio)}", 'green'))
        print("\nMenü:")
        print("1. Bütçeyi Görüntüle / Güncelle")
        print("2. Piyasayı Analiz Et ve Alım Tavsiyesi Ver")
        print("3. Portföyümü Görüntüle ve Sat/Tut Tavsiyeleri Al")
        print("4. Portföye Manuel Hisse Ekle")
        print("5. Mevcut Portföyü Sıfırla veya Sil")
        print("6. Diğer Portföye Geç")
        print("7. Backtest Modu (Son 2 Yıl Test)")
        print("8. Çıkış")
        
        choice = input("\nSeçiminiz (1/2/3/4/5/6/7/8): ")
        
        if choice == '1':
            try:
                new_budget_str = input(f"Yeni bütçenizi girin (TL) [Mevcut: {budget:.2f}]: ")
                if not new_budget_str.strip():
                    continue
                new_budget = float(new_budget_str)
                if new_budget < 0:
                    print("Bütçe negatif olamaz!")
                else:
                    fark = new_budget - budget
                    save_budget(new_budget)
                    log_transaction("Bütçe Güncelleme", "-", "-", "-", fark, new_budget)
                    print("Bütçeniz başarıyla güncellendi.")
            except ValueError:
                print("Lütfen geçerli bir sayı girin.")
                
        elif choice == '2':
            if budget <= 0:
                print("Lütfen önce bütçenizi güncelleyin (Bütçeniz 0 TL).")
                continue
                
            print("\nPiyasa verileri çekiliyor (hisseler, altın, gümüş), lütfen bekleyin...")
            from data_fetcher import BIST_STOCKS, PRECIOUS_METALS, MARKET_INDEX
            data_dict = fetch_data(include_metals=True)
            
            stocks_count = len([t for t in data_dict.keys() if t.endswith('.IS') and t != MARKET_INDEX])
            metals_count = len([t for t in data_dict.keys() if t in ['GC=F', 'SI=F']])
            
            print(f"> {stocks_count}/{len(BIST_STOCKS)} hissenin, {metals_count}/{len(PRECIOUS_METALS)} değerli metalin verisi çekildi.")
            
            print("Veriler analiz ediliyor (hisseler + altın/gümüş)...")
            from analyzer import analyze_all_assets
            recommendations = analyze_all_assets(data_dict)
            
            if not recommendations:
                print("Şu anki piyasa koşullarında stratejiye uyan asset bulunamadı.")
                continue
                
            print("\n" + "="*70)
            print("*** OPSIYONEL HİSSELER VE DEĞERLI METALLER - TEKNİK ANALİZ SONUÇLARI ***")
            print("="*70)
            for r in recommendations[:10]:
                display = r.get('Display', r['Hisse'])
                asset_type = r.get('AssetType', 'HISSE')
                unit = r.get('Unit', 'adet')
                
                if asset_type == 'METAL':
                    print(f"- {display:<12} | Fiyat/Gram={r['Fiyat']:.2f} TL | Skor={r['Skor']}/{10} | Sinyal: {r['Sinyal']} | Vol:{r.get('Volatility',0):.1f}%")
                else:
                    print(f"- {display:<12} | Fiyat={r['Fiyat']:.2f} TL | Skor={r['Skor']}/{10} | Sinyal: {r['Sinyal']}")
                print(f"  └─ Nedenler: {r['Nedenler']}")
                
            print("\nBütçenize göre portföy oluşturuluyor...")
            allocations, remaining = allocate_budget(budget, recommendations)
            
            if not allocations:
                print("Bütçeniz önerilen asset'lerden almak için yetersiz.")
            else:
                print("\n" + "*" * 70)
                print("        TAVSİYE EDİLEN PORTFÖY DAĞILIMI (Hisseler + Altın/Gümüş)")
                print("*" * 70)
                total_spent = 0
                for item in allocations:
                    asset_type = item.get('AssetType', 'HISSE')
                    unit = item.get('Unit', 'adet')
                    display = item.get('Display', item['Hisse'])
                    
                    if asset_type == 'METAL':
                        print(f"{display:<12} | {item['Lot']:<4} gram | {item['Fiyat']:>7.2f} TL/gram | Toplam: {item['Toplam Maliyet']:>8.2f} TL")
                    else:
                        print(f"{display:<12} | {item['Lot']:<4} lot  | {item['Fiyat']:>7.2f} TL/lot  | Toplam: {item['Toplam Maliyet']:>8.2f} TL")
                    
                    total_spent += item['Toplam Maliyet']
                    
                print("-" * 70)
                print(f"Harcanan Toplam Bütçe: {total_spent:.2f} TL")
                print(f"Kalan Nakit:          {remaining:.2f} TL")
                
            al_cevap = input("\nBu tavsiyelerden veya kendi tercihinizle asset aldınız mı? (E/H): ").strip().upper()
            if al_cevap == 'E':
                while True:
                    asset_kodu = input("\nAldığınız Hisse/Metal Kodu (Örn: THYAO veya ALTIN): ").strip().upper()
                    asset_type = input("Asset Tipi (H=Hisse, M=Metal): ").strip().upper()
                    
                    if asset_type == 'M':
                        unit = "gram"
                    else:
                        unit = "lot"
                        asset_type = 'H'
                    
                    try:
                        miktar = int(input(f"[{asset_kodu}] Kaç {unit} Aldınız: ").strip())
                        alis_fiyati = float(input(f"[{asset_kodu}] Alış Fiyatınız (TL/{unit}): ").strip())
                        
                        toplam_tutar = miktar * alis_fiyati
                        if toplam_tutar > budget:
                            print(f"Hata: Alış tutarı ({toplam_tutar:.2f} TL) mevcut bütçenizden ({budget:.2f} TL) fazla olamaz!")
                        else:
                            if asset_kodu in portfolio:
                                mevcut_lot = portfolio[asset_kodu]['lot']
                                mevcut_maliyet = portfolio[asset_kodu]['maliyet']
                                yeni_lot = mevcut_lot + miktar
                                yeni_maliyet = ((mevcut_lot * mevcut_maliyet) + toplam_tutar) / yeni_lot
                                portfolio[asset_kodu] = {'lot': yeni_lot, 'maliyet': yeni_maliyet, 'type': asset_type}
                            else:
                                portfolio[asset_kodu] = {'lot': miktar, 'maliyet': alis_fiyati, 'type': asset_type}
                                
                            budget -= toplam_tutar
                            save_portfolio(portfolio)
                            save_budget(budget)
                            log_transaction(f"Asset Alım ({unit})", asset_kodu, miktar, alis_fiyati, -toplam_tutar, budget)
                            print(f"{asset_kodu} başarıyla portföye eklendi. Kalan Bütçeniz: {budget:.2f} TL")
                    except ValueError:
                        print("Hatalı giriş yaptınız. Lütfen miktar için tam sayı, fiyat için sayı girin.")
                        
                    baska = input("\nAldığınız başka asset var mı? (E/H): ").strip().upper()
                    if baska != 'E':
                        break
                    
        elif choice == '3':
            if not portfolio:
                print("\nPortföyünüzde henüz asset bulunmuyor.")
                continue
                
            print("\nPortföy verileriniz için güncel piyasa fiyatları çekiliyor...")
            from data_fetcher import BIST_STOCKS, PRECIOUS_METALS
            
            # Portföydeki hisseleri çekme listesine ekle
            portfolio_stocks = [t for t in portfolio.keys() if portfolio[t].get('type', 'H') == 'H']
            portfolio_metals = [t for t in portfolio.keys() if portfolio[t].get('type', 'H') == 'M']
            
            fetch_list = list(set(BIST_STOCKS + [f"{t}.IS" for t in portfolio_stocks]))
            
            # Metal fiyatları da ekle
            data_dict = fetch_data(fetch_list, include_metals=(len(portfolio_metals) > 0))
            
            stocks_count = len([t for t in data_dict.keys() if t.endswith('.IS')])
            metals_count = len([t for t in data_dict.keys() if t in ['GC=F', 'SI=F']])
            print(f"> {stocks_count}/{len(fetch_list)} hissenin, {metals_count}/{len(PRECIOUS_METALS)} metalin verisi çekildi.")
            
            print("Portföyünüz değerlendiriliyor...")
            evaluations = evaluate_portfolio(portfolio, data_dict)
            
            print("\n" + "=" * 80)
            print(f"                 [{active_profile.upper()}] PORTFÖY DURUMU VE TAVSİYELER")
            print("=" * 80)
            
            satilacaklar = []
            toplam_portfoy_degeri = 0
            toplam_maliyet = 0
            
            # Hisselerin değerlendirilmesi
            for ev in evaluations:
                hisse = ev['Hisse']
                lot = ev['Lot']
                fiyat = ev['Fiyat']
                maliyet = ev['Maliyet']
                k_z = ev['K/Z %']
                durum = ev['Durum']
                neden = ev['Nedenler']
                
                guncel_tutar = lot * fiyat
                hisse_maliyeti = lot * maliyet
                
                toplam_portfoy_degeri += guncel_tutar
                toplam_maliyet += hisse_maliyeti
                
                print(f"📊 Hisse: {hisse:<5} | Lot: {lot:<4} | Maliyet: {maliyet:>6.2f} | Güncel: {fiyat:>6.2f} | K/Z: %{k_z:>5.2f}")
                print(f"   -> TAVSİYE: {durum} (Neden: {neden})")
                print("-" * 80)
                
                if durum in ['Sat', 'Dikkatli Tut']:
                    satilacaklar.append(ev)
            
            # Portföydeki altın/gümüş'ü de göster
            print("\n" + "="*80)
            print("DEĞERLI METALLER")
            print("="*80)
            metals_in_portfolio = {k: v for k, v in portfolio.items() if v.get('type') == 'M'}
            
            if metals_in_portfolio:
                for metal_kodu, metal_info in metals_in_portfolio.items():
                    metal_lot = metal_info['lot']
                    metal_maliyet = metal_info['maliyet']
                    
                    # Metal gösterimi
                    if metal_kodu == 'ALTIN':
                        display = '🥇 Altın'
                        unit = 'gram'
                    elif metal_kodu == 'GUMUS':
                        display = '🥈 Gümüş'
                        unit = 'gram'
                    else:
                        display = metal_kodu
                        unit = 'birim'
                    
                    metal_guncel_tutar = metal_lot * metal_maliyet  # Canlı fiyat yoksa maliyet kullan
                    metal_k_z = 0  # Metal fiyatını almadığımız için K/Z hesaplayamıyoruz
                    
                    print(f"{display:<12} | {metal_lot:<4} {unit} | Maliyet: {metal_maliyet:>6.2f} | Toplam: {metal_guncel_tutar:>8.2f} TL")
                    toplam_portfoy_degeri += metal_guncel_tutar
                    toplam_maliyet += metal_guncel_tutar
            else:
                print("Portföyünüzde henüz metal bulunmuyor.")
            
            genel_kz_tl = toplam_portfoy_degeri - toplam_maliyet
            genel_kz_yuzde = (genel_kz_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
            
            print("\n" + "="*80)
            print(f"Portföyün Toplam Maliyeti: {toplam_maliyet:.2f} TL")
            print(f"Portföyün Güncel Toplam Değeri: {toplam_portfoy_degeri:.2f} TL")
            print(f"Genel Portföy K/Z Durumu: {genel_kz_tl:+.2f} TL (%{genel_kz_yuzde:+.2f})")
            print("=" * 80)
            
            log_transaction("Portföy Değerlemesi", "-", "-", "-", toplam_portfoy_degeri, budget, genel_kz_tl, genel_kz_yuzde)
            
            sat_cevap = input("\nPortföyünüzdeki herhangi bir asset'i satmak ister misiniz? (E/H): ").strip().upper()
            if sat_cevap == 'E':
                satis_yapildi = False
                while True:
                    satilan_asset = input("\nHangisini satmak istiyorsunuz? (Hisse/Metal kodunu yazın): ").strip().upper()
                    
                    if satilan_asset in portfolio:
                        try:
                            sat_miktar = int(input(f"Kaç {portfolio[satilan_asset].get('unit', 'lot')} satacaksınız? (Mevcut: {portfolio[satilan_asset]['lot']}): "))
                            if sat_miktar <= 0 or sat_miktar > portfolio[satilan_asset]['lot']:
                                print("Geçersiz miktar!")
                            else:
                                maliyet_fiyati = portfolio[satilan_asset]['maliyet']
                                asset_type = portfolio[satilan_asset].get('type', 'H')
                                
                                # Hisse için güncel fiyat evaluations'dan al, metal için maliyet fiyat kullan
                                if asset_type == 'H':
                                    guncel_fiyat = next((item['Fiyat'] for item in evaluations if item['Hisse'] == satilan_asset), maliyet_fiyati)
                                else:
                                    guncel_fiyat = maliyet_fiyati  # Metal fiyatları canlı olarak alınmıyor
                                
                                kar_zarar_tl = (guncel_fiyat - maliyet_fiyati) * sat_miktar
                                kar_zarar_yuzde = ((guncel_fiyat - maliyet_fiyati) / maliyet_fiyati) * 100 if maliyet_fiyati > 0 else 0
                                
                                satis_geliri = sat_miktar * guncel_fiyat
                                budget += satis_geliri
                                
                                portfolio[satilan_asset]['lot'] -= sat_miktar
                                if portfolio[satilan_asset]['lot'] == 0:
                                    del portfolio[satilan_asset]
                                    
                                save_portfolio(portfolio)
                                save_budget(budget)
                                
                                unit_name = 'gram' if asset_type == 'M' else 'lot'
                                log_transaction(f"Asset Satım ({unit_name})", satilan_asset, sat_miktar, guncel_fiyat, satis_geliri, budget, kar_zarar_tl, kar_zarar_yuzde)
                                print(f"\n{satilan_asset} satıldı. Satış Geliri: {satis_geliri:.2f} TL.")
                                print(f"İşlemden Elde Edilen K/Z: {kar_zarar_tl:+.2f} TL (%{kar_zarar_yuzde:+.2f})")
                                print(f"Yeni Bütçeniz: {budget:.2f} TL")
                                satis_yapildi = True
                                
                        except ValueError:
                            print("Lütfen geçerli bir sayı girin.")
                    else:
                        print("Bu asset portföyünüzde bulunmuyor.")
                        
                    if not portfolio:
                        print("\nPortföyünüzde satılacak asset kalmadı.")
                        break
                        
                    baska_sat = input("\nSatmak istediğiniz başka asset var mı? (E/H): ").strip().upper()
                    if baska_sat != 'E':
                        break
                        
                if satis_yapildi:
                    print("\nNakitiniz güncellendi. Yeni bütçenizle alınabilecek hisseler hesaplanıyor...")
                    recommendations = analyze_stocks(data_dict)
                    allocations, remaining = allocate_budget(budget, recommendations)
                    
                    if allocations:
                        print("\nİşte sattığınız hisselerin yerine alınabilecek öneriler:")
                        for item in allocations:
                            print(f"- {item['Hisse']:<6}: {item['Lot']} Lot alınabilir (Toplam: {item['Toplam Maliyet']:.2f} TL) | Neden: {item['Nedenler']}")
                    else:
                        print("Şu an yeni alım için uygun kriterde hisse bulunamadı.")

        elif choice == '4':
            while True:
                hisse_kodu = input("\nHisse Kodu (Örn: THYAO): ").strip().upper()
                try:
                    lot_miktari = int(input(f"[{hisse_kodu}] Kaç Lot: ").strip())
                    alis_fiyati = float(input(f"[{hisse_kodu}] Maliyetiniz (TL): ").strip())
                    
                    toplam_tutar = lot_miktari * alis_fiyati
                    budget -= toplam_tutar
                    
                    if hisse_kodu in portfolio:
                        mevcut_lot = portfolio[hisse_kodu]['lot']
                        mevcut_maliyet = portfolio[hisse_kodu]['maliyet']
                        yeni_lot = mevcut_lot + lot_miktari
                        yeni_maliyet = ((mevcut_lot * mevcut_maliyet) + toplam_tutar) / yeni_lot
                        portfolio[hisse_kodu] = {'lot': yeni_lot, 'maliyet': yeni_maliyet}
                    else:
                        portfolio[hisse_kodu] = {'lot': lot_miktari, 'maliyet': alis_fiyati}
                        
                    save_portfolio(portfolio)
                    save_budget(budget)
                    log_transaction("Manuel Hisse Ekleme", hisse_kodu, lot_miktari, alis_fiyati, -toplam_tutar, budget)
                    print(f"{hisse_kodu} portföye eklendi. İşlem tutarı bütçeden düşüldü. Yeni bütçeniz: {budget:.2f} TL")
                except ValueError:
                    print("Hatalı giriş!")
                    
                baska = input("\nEkleyeceğiniz başka hisse var mı? (E/H): ").strip().upper()
                if baska != 'E':
                    break
                
        elif choice == '5':
            print(f"\n--- [{active_profile.upper()}] Portföy Yönetimi ---")
            print("1. Portföyü Sıfırla (Bütçe ve hisseler temizlenir, log dosyası korunur)")
            print("2. Portföyü Tamamen Sil (Tüm kayıtlar ve log dosyası kalıcı olarak silinir)")
            print("3. İptal")
            
            sub_choice = input("Seçiminiz: ").strip()
            if sub_choice == '1':
                onay = input(f"[{active_profile}] portföyündeki bütçe ve hisseler SIFIRLANACAK. Emin misiniz? (E/H): ").strip().upper()
                if onay == 'E':
                    reset_current_profile()
                    log_transaction("Portföy Sıfırlama", "-", "-", "-", 0, 0)
                    print(f"\n[{active_profile}] portföyü başarıyla sıfırlandı.")
            elif sub_choice == '2':
                onay = input(f"[{active_profile}] portföyü ve işlem geçmişi TAMAMEN SİLİNECEK. Emin misiniz? (E/H): ").strip().upper()
                if onay == 'E':
                    delete_profile(active_profile)
                    print(f"\n[{active_profile}] portföyü kalıcı olarak silindi.")
                    print("Ana ekrana yönlendiriliyorsunuz...")
                    active_profile = init_profile()
            else:
                print("İşlem iptal edildi.")

        elif choice == '6':
            print(f"\n[{active_profile.upper()}] portföyünden çıkılıyor...")
            active_profile = init_profile()

        elif choice == '7':
            # BACKTEST MODU
            try:
                from backtest import run_backtest_interactive
                run_backtest_interactive()
            except Exception as e:
                print(f"Backtest modu çalıştırılamadı: {e}")

        elif choice == '8':
            print("Programdan çıkılıyor. Bol kazançlar!")
            sys.exit(0)
        else:
            print("Geçersiz seçim.")

if __name__ == "__main__":
    main()
