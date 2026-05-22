import os
import glob
from datetime import datetime

CURRENT_PROFILE = "default"

def migrate_md_to_txt():
    md_files = glob.glob("*_islem_gecmisi.md")
    for file in md_files:
        txt_file = file.replace(".md", ".txt")
        
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()
            
        parts = [p.strip() for p in content.split("|")]
        data_values = []
        for p in parts:
            if p and p not in ['---', 'Tarih', 'İşlem Tipi', 'Hisse', 'Lot', 'İşlem Fiyatı (TL)', 'Tutar (TL)', 'K/Z (TL)', 'K/Z (%)', 'Kalan Bütçe (TL)']:
                if not p.startswith("#"):
                    clean_p = p.replace('\n', '').strip()
                    if clean_p:
                        data_values.append(clean_p)
                        
        rows = [data_values[i:i+9] for i in range(0, len(data_values), 9) if len(data_values[i:i+9]) == 9]
        
        profile_name = file.replace("_islem_gecmisi.md", "")
        
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write("=" * 128 + "\n")
            f.write(f"{profile_name.upper()} PORTFÖYÜ - İŞLEM GEÇMİŞİ".center(128) + "\n")
            f.write("=" * 128 + "\n")
            f.write(f"{'Tarih':<20} | {'İşlem Tipi':<20} | {'Hisse':<6} | {'Lot':<6} | {'Fiyat (TL)':<10} | {'Tutar (TL)':<12} | {'K/Z (TL)':<10} | {'K/Z (%)':<8} | {'Bütçe (TL)':<12}\n")
            f.write("-" * 128 + "\n")
            for r in rows:
                f.write(f"{r[0]:<20} | {r[1]:<20} | {r[2]:<6} | {r[3]:<6} | {r[4]:<10} | {r[5]:<12} | {r[6]:<10} | {r[7]:<8} | {r[8]:<12}\n")
                
        try:
            os.remove(file)
        except Exception:
            pass

def set_logger_profile(name):
    global CURRENT_PROFILE
    CURRENT_PROFILE = name
    migrate_md_to_txt()

def get_log_file():
    return f"{CURRENT_PROFILE}_islem_gecmisi.txt"

def log_transaction(islem_tipi, hisse_kodu="-", lot="-", fiyat="-", islem_tutari="-", kalan_butce="-", kar_zarar_tl="-", kar_zarar_yuzde="-"):
    log_file = get_log_file()
    file_exists = os.path.exists(log_file)
    
    with open(log_file, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("=" * 128 + "\n")
            f.write(f"{CURRENT_PROFILE.upper()} PORTFÖYÜ - İŞLEM GEÇMİŞİ".center(128) + "\n")
            f.write("=" * 128 + "\n")
            f.write(f"{'Tarih':<20} | {'İşlem Tipi':<20} | {'Hisse':<6} | {'Lot':<6} | {'Fiyat (TL)':<10} | {'Tutar (TL)':<12} | {'K/Z (TL)':<10} | {'K/Z (%)':<8} | {'Bütçe (TL)':<12}\n")
            f.write("-" * 128 + "\n")
            
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        fiyat_str = f"{fiyat:.2f}" if isinstance(fiyat, (int, float)) else str(fiyat)
        tutar_str = f"{islem_tutari:.2f}" if isinstance(islem_tutari, (int, float)) else str(islem_tutari)
        butce_str = f"{kalan_butce:.2f}" if isinstance(kalan_butce, (int, float)) else str(kalan_butce)
        
        kz_tl_str = f"{kar_zarar_tl:+.2f}" if isinstance(kar_zarar_tl, (int, float)) else str(kar_zarar_tl)
        kz_yuzde_str = f"%{kar_zarar_yuzde:+.2f}" if isinstance(kar_zarar_yuzde, (int, float)) else str(kar_zarar_yuzde)
        
        f.write(f"{tarih:<20} | {islem_tipi:<20} | {hisse_kodu:<6} | {lot:<6} | {fiyat_str:<10} | {tutar_str:<12} | {kz_tl_str:<10} | {kz_yuzde_str:<8} | {butce_str:<12}\n")
