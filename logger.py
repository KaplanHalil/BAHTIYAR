import os
import glob
from datetime import datetime

CURRENT_PROFILE = "default"
PORTFOLIOS_DIR = "portfolios"


def _ensure_dir():
    if not os.path.exists(PORTFOLIOS_DIR):
        os.makedirs(PORTFOLIOS_DIR, exist_ok=True)


def migrate_md_to_txt():
    _ensure_dir()
    md_files = glob.glob(os.path.join(PORTFOLIOS_DIR, "*_islem_gecmisi.md")) + glob.glob("*_islem_gecmisi.md")
    for file in md_files:
        txt_file = file.replace(".md", ".txt")
        
        try:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            continue
            
        parts = [p.strip() for p in content.split("|")]
        data_values = []
        for p in parts:
            if p and p not in ['---', 'Tarih', 'İşlem Tipi', 'Hisse', 'Lot', 'İşlem Fiyatı (TL)', 'Tutar (TL)', 'K/Z (TL)', 'K/Z (%)', 'Kalan Bütçe (TL)']:
                if not p.startswith("#"):
                    clean_p = p.replace('\n', '').strip()
                    if clean_p:
                        data_values.append(clean_p)
                        
        rows = [data_values[i:i+9] for i in range(0, len(data_values), 9) if len(data_values[i:i+9]) == 9]
        
        base = os.path.basename(file)
        profile_name = base.replace("_islem_gecmisi.md", "")
        
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
    _ensure_dir()
    old_file = f"{CURRENT_PROFILE}_islem_gecmisi.txt"
    new_file = os.path.join(PORTFOLIOS_DIR, f"{CURRENT_PROFILE}_islem_gecmisi.txt")
    if os.path.exists(old_file) and not os.path.exists(new_file):
        try:
            os.rename(old_file, new_file)
        except Exception:
            return old_file
    return new_file


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


def get_recently_sold_stocks(days: int = 1) -> dict:
    """
    Son `days` gün içinde satılmış hisseleri ve en son satıldığı zamanı döndürür.
    Örnek döndürülen sözlük: {'ALBRK': datetime_obj, 'BAHKM': datetime_obj}
    """
    log_file = get_log_file()
    if not os.path.exists(log_file):
        return {}

    recently_sold = {}
    now = datetime.now()

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line_lower = line.lower()
                if any(w in line_lower for w in ["satım", "satış", "satim", "satis"]):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 3:
                        tarih_str = parts[0].strip()
                        hisse = parts[2].strip().upper()
                        if hisse and hisse != "-":
                            try:
                                t_dt = datetime.strptime(tarih_str, "%Y-%m-%d %H:%M:%S")
                                delta_days = (now - t_dt).total_seconds() / 86400.0
                                if delta_days <= days:
                                    recently_sold[hisse] = t_dt
                            except Exception:
                                pass
    except Exception:
        pass

    return recently_sold
