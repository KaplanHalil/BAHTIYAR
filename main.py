import sys
import os
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
        print("7. Çıkış")
        
        choice = input("\nSeçiminiz (1/2/3/4/5/6/7): ")
        
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
                
            print("\nPiyasa verileri çekiliyor, lütfen bekleyin...")
            from data_fetcher import BIST_STOCKS
            data_dict = fetch_data()
            print(f"> {len(data_dict)}/{len(BIST_STOCKS)} hissenin verisi başarıyla çekildi.")
            
            print("Veriler analiz ediliyor...")
            recommendations = analyze_stocks(data_dict)
            
            if not recommendations:
                print("Şu anki piyasa koşullarında stratejiye uyan hisse bulunamadı.")
                continue
                
            print("\n*** POTANSİYEL HİSSELERE AİT TEKNİK ANALİZ SONUÇLARI ***")
            for r in recommendations[:10]:
                print(f"- {r['Hisse']:<6}: Fiyat={r['Fiyat']:.2f} TL | Skor={r['Skor']}/{10} | Sinyal: {r['Sinyal']} | Neden: {r['Nedenler']}")
                
            print("\nBütçenize göre portföy oluşturuluyor...")
            allocations, remaining = allocate_budget(budget, recommendations)
            
            if not allocations:
                print("Bütçeniz önerilen hisselerden almak için (en az 1 lot) yetersiz.")
            else:
                print("\n" + "*" * 50)
                print("        TAVSİYE EDİLEN PORTFÖY DAĞILIMI")
                print("*" * 50)
                total_spent = 0
                for item in allocations:
                    print(f"Hisse: {item['Hisse']:<6} | Lot: {item['Lot']:<4} | Fiyat: {item['Fiyat']:>7.2f} TL | Toplam: {item['Toplam Maliyet']:>8.2f} TL")
                    total_spent += item['Toplam Maliyet']
                    
                print("-" * 50)
                print(f"Harcanan Toplam Bütçe: {total_spent:.2f} TL")
                print(f"Kalan Nakit:          {remaining:.2f} TL")
                
            al_cevap = input("\nBu tavsiyelerden veya kendi tercihinizle hisse aldınız mı? (E/H): ").strip().upper()
            if al_cevap == 'E':
                while True:
                    hisse_kodu = input("\nAldığınız Hisse Kodu (Örn: THYAO): ").strip().upper()
                    try:
                        lot_miktari = int(input(f"[{hisse_kodu}] Kaç Lot Aldınız: ").strip())
                        alis_fiyati = float(input(f"[{hisse_kodu}] Alış Fiyatınız (TL): ").strip())
                        
                        toplam_tutar = lot_miktari * alis_fiyati
                        if toplam_tutar > budget:
                            print(f"Hata: Alış tutarı ({toplam_tutar:.2f} TL) mevcut bütçenizden ({budget:.2f} TL) fazla olamaz!")
                        else:
                            if hisse_kodu in portfolio:
                                mevcut_lot = portfolio[hisse_kodu]['lot']
                                mevcut_maliyet = portfolio[hisse_kodu]['maliyet']
                                yeni_lot = mevcut_lot + lot_miktari
                                yeni_maliyet = ((mevcut_lot * mevcut_maliyet) + toplam_tutar) / yeni_lot
                                portfolio[hisse_kodu] = {'lot': yeni_lot, 'maliyet': yeni_maliyet}
                            else:
                                portfolio[hisse_kodu] = {'lot': lot_miktari, 'maliyet': alis_fiyati}
                                
                            budget -= toplam_tutar
                            save_portfolio(portfolio)
                            save_budget(budget)
                            log_transaction("Hisse Alım", hisse_kodu, lot_miktari, alis_fiyati, -toplam_tutar, budget)
                            print(f"{hisse_kodu} başarıyla portföye eklendi. Kalan Bütçeniz: {budget:.2f} TL")
                    except ValueError:
                        print("Hatalı giriş yaptınız. Lütfen lot için tam sayı, fiyat için sayı girin.")
                        
                    baska = input("\nAldığınız başka hisse var mı? (E/H): ").strip().upper()
                    if baska != 'E':
                        break
                    
        elif choice == '3':
            if not portfolio:
                print("\nPortföyünüzde henüz hisse bulunmuyor.")
                continue
                
            print("\nPortföy verileriniz için güncel piyasa fiyatları çekiliyor...")
            from data_fetcher import BIST_STOCKS
            fetch_list = list(set(BIST_STOCKS + [f"{t}.IS" for t in portfolio.keys()]))
            data_dict = fetch_data(fetch_list)
            print(f"> {len(data_dict)}/{len(fetch_list)} hissenin verisi başarıyla çekildi.")
            
            print("Portföyünüz değerlendiriliyor...")
            evaluations = evaluate_portfolio(portfolio, data_dict)
            
            print("\n" + "=" * 70)
            print(f"                 [{active_profile.upper()}] PORTFÖY DURUMU VE TAVSİYELER")
            print("=" * 70)
            
            satilacaklar = []
            toplam_portfoy_degeri = 0
            toplam_maliyet = 0
            
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
                
                print(f"Hisse: {hisse:<5} | Lot: {lot:<4} | Maliyet: {maliyet:>6.2f} | Güncel: {fiyat:>6.2f} | K/Z: %{k_z:>5.2f}")
                print(f"   -> TAVSİYE: {durum} (Neden: {neden})")
                print("-" * 70)
                
                if durum in ['Sat', 'Dikkatli Tut']:
                    satilacaklar.append(ev)
            
            genel_kz_tl = toplam_portfoy_degeri - toplam_maliyet
            genel_kz_yuzde = (genel_kz_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
            
            print(f"Portföydeki Hisselerin Toplam Maliyeti: {toplam_maliyet:.2f} TL")
            print(f"Portföydeki Hisselerin Güncel Toplam Değeri: {toplam_portfoy_degeri:.2f} TL")
            print(f"Genel Portföy K/Z Durumu: {genel_kz_tl:+.2f} TL (%{genel_kz_yuzde:+.2f})")
            print("=" * 70)
            
            log_transaction("Portföy Değerlemesi", "-", "-", "-", toplam_portfoy_degeri, budget, genel_kz_tl, genel_kz_yuzde)
            
            sat_cevap = input("\nPortföyünüzdeki herhangi bir hisseyi satmak ister misiniz? (E/H): ").strip().upper()
            if sat_cevap == 'E':
                satis_yapildi = False
                while True:
                    satilan_hisse = input("\nHangisini satmak istiyorsunuz? (Hisse kodunu yazın): ").strip().upper()
                    
                    if satilan_hisse in portfolio:
                        try:
                            sat_lot = int(input(f"Kaç lot satacaksınız? (Mevcut: {portfolio[satilan_hisse]['lot']}): "))
                            if sat_lot <= 0 or sat_lot > portfolio[satilan_hisse]['lot']:
                                print("Geçersiz lot miktarı!")
                            else:
                                guncel_fiyat = next((item['Fiyat'] for item in evaluations if item['Hisse'] == satilan_hisse), portfolio[satilan_hisse]['maliyet'])
                                maliyet_fiyati = portfolio[satilan_hisse]['maliyet']
                                
                                kar_zarar_tl = (guncel_fiyat - maliyet_fiyati) * sat_lot
                                kar_zarar_yuzde = ((guncel_fiyat - maliyet_fiyati) / maliyet_fiyati) * 100 if maliyet_fiyati > 0 else 0
                                
                                satis_geliri = sat_lot * guncel_fiyat
                                budget += satis_geliri
                                
                                portfolio[satilan_hisse]['lot'] -= sat_lot
                                if portfolio[satilan_hisse]['lot'] == 0:
                                    del portfolio[satilan_hisse]
                                    
                                save_portfolio(portfolio)
                                save_budget(budget)
                                log_transaction("Hisse Satım", satilan_hisse, sat_lot, guncel_fiyat, satis_geliri, budget, kar_zarar_tl, kar_zarar_yuzde)
                                print(f"\n{satilan_hisse} satıldı. Satış Geliri: {satis_geliri:.2f} TL.")
                                print(f"İşlemden Elde Edilen K/Z: {kar_zarar_tl:+.2f} TL (%{kar_zarar_yuzde:+.2f})")
                                print(f"Yeni Bütçeniz: {budget:.2f} TL")
                                satis_yapildi = True
                                
                        except ValueError:
                            print("Lütfen geçerli bir sayı girin.")
                    else:
                        print("Bu hisse portföyünüzde bulunmuyor.")
                        
                    if not portfolio:
                        print("\nPortföyünüzde satılacak hisse kalmadı.")
                        break
                        
                    baska_sat = input("\nSatmak istediğiniz başka hisse var mı? (E/H): ").strip().upper()
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
            print("Programdan çıkılıyor. Bol kazançlar!")
            sys.exit(0)
        else:
            print("Geçersiz seçim.")

if __name__ == "__main__":
    main()
