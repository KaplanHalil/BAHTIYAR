import sys
import os
import yfinance as yf

from budget_manager import (
    load_budget, save_budget, load_portfolio, save_portfolio,
    set_profile, get_all_profiles, delete_profile, reset_current_profile,
    get_profile_summary
)
from data_fetcher import fetch_data
from analyzer import analyze_stocks, evaluate_portfolio, enrich_with_sentiment, calculate_market_health
from optimizer import allocate_budget
from logger import log_transaction, set_logger_profile
from stock_list_manager import (
    get_stock_list_with_names, add_stock, remove_stock,
    update_stock_name, stock_count
)
from news_analyzer import (
    is_ai_configured, get_active_provider, get_api_key,
    load_ai_config, save_ai_config, analyze_sentiment_batch,
    get_sentiment_score, format_sentiment, clear_sentiment_cache,
    ETIKET_SEMBOL
)
from signal_tracker import record_signals, print_performance_report, get_market_status
from ui_menu import interactive_menu, interactive_input, interactive_confirm, clear_screen, c
from shutil import get_terminal_size

try:
    from colorama import init as _colorama_init
    _colorama_init(strip=False, autoreset=True)
except Exception:
    pass

COLOR_CODES = {
    'BLACK': '\033[30m',
    'RED': '\033[31m',
    'GREEN': '\033[32m',
    'YELLOW': '\033[33m',
    'BLUE': '\033[34m',
    'MAGENTA': '\033[35m',
    'CYAN': '\033[36m',
    'WHITE': '\033[37m',
    'RESET': '\033[0m'
}


def print_separator():
    print("=" * 70)


def manage_ai_settings():
    """AI / Haber Analizi ve Uygulama Ayarları menüsü (TUI)."""
    while True:
        ai_ok      = is_ai_configured()
        provider   = get_active_provider()
        gemini_key = get_api_key('gemini')
        openai_key = get_api_key('openai')

        status_str = f"✅ Aktif ({provider.upper()})" if ai_ok else "❌ Devre Dışı"
        g_badge = f"****{gemini_key[-4:]}" if gemini_key else "Girilmemiş"
        o_badge = f"****{openai_key[-4:]}" if openai_key else "Girilmemiş"

        header = (
            "\n" + "=" * 70 + "\n"
            + _colored("     🤖 UYGULAMA & YAPAY ZEKA AYARLARI", 'cyan', True) + "\n"
            + "=" * 70 + "\n"
            + f"  AI Durumu      : {_colored(status_str, 'green' if ai_ok else 'red', True)}\n"
            + f"  Gemini API Key : {_colored(g_badge, 'cyan' if gemini_key else 'yellow')}\n"
            + f"  OpenAI API Key : {_colored(o_badge, 'cyan' if openai_key else 'yellow')}\n"
        )

        settings_options = [
            {
                'label': "🔑 Google Gemini API Anahtarı Gir / Güncelle",
                'value': '1',
                'badge': "[Önerilen — Ücretsiz]",
                'desc': "https://aistudio.google.com/ adresinden aldığınız anahtarı tanımlayın"
            },
            {
                'label': "🔑 OpenAI API Anahtarı Gir / Güncelle",
                'value': '2',
                'desc': "OpenAI GPT-4o-mini entegrasyonu için anahtar tanımlayın"
            },
            {
                'label': "🧹 Haber Önbelleğini Temizle (sentiment_cache.json)",
                'value': '4',
                'desc': "Eski analiz önbelleğini sıfırlayıp haberleri taze çekin"
            },
            {
                'label': "🧪 Tek Hisse İçin Test Haber Analizi Yap",
                'value': '5',
                'desc': "Seçeceğiniz bir hisse için haber duygu skorunu anlık test edin"
            },
            {
                'label': "🗑️  Kayıtlı API Anahtarlarını Sıfırla / Sil",
                'value': '3',
                'desc': "ai_config.json içindeki tüm anahtarları temizler"
            },
            {
                'label': "⬅️  Geri Dön",
                'value': '6',
                'desc': "Önceki ekrana geri dön"
            }
        ]

        sub = interactive_menu(
            options=settings_options,
            title="UYGULAMA & AI AYARLARI",
            subtitle="Ok tuşlarıyla gezinip ENTER ile seçin:",
            header_text=header
        )

        if not sub or sub == '6':
            break

        if sub == '1':
            key = interactive_input("Gemini API Anahtarı (https://aistudio.google.com/)").strip()
            if key:
                cfg = load_ai_config()
                cfg['gemini_api_key'] = key
                save_ai_config(cfg)
                print(_colored("\n  ✅ Gemini API anahtarı başarıyla kaydedildi.", 'green', True))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
        elif sub == '2':
            key = interactive_input("OpenAI API Anahtarı").strip()
            if key:
                cfg = load_ai_config()
                cfg['openai_api_key'] = key
                save_ai_config(cfg)
                print(_colored("\n  ✅ OpenAI API anahtarı başarıyla kaydedildi.", 'green', True))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
        elif sub == '3':
            if interactive_confirm("Kayıtlı API anahtarları silinsin mi?", default=False):
                save_ai_config({})
                print(_colored("\n  ✅ API anahtarları silindi.", 'green', True))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
        elif sub == '4':
            if clear_sentiment_cache():
                print(_colored("\n  ✅ Haber önbelleği temizlendi.", 'green', True))
            else:
                print(_colored("\n  Önbellekte silinecek veri yok.", 'yellow'))
            input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
        elif sub == '5':
            if not is_ai_configured():
                print(_colored("\n  ❌ Önce bir API anahtarı girin (Seçenek 1 veya 2).", 'red', True))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                continue
            kod = interactive_input("Test edilecek hisse kodu (Örn: BIMAS)").strip().upper()
            if not kod:
                continue
            stocks_map = {s['kod']: s.get('ad', '') for s in get_stock_list_with_names()}
            ad = stocks_map.get(kod, '')
            print(f"\n  '{kod}' için haberler çekiliyor ve AI analizi yapılıyor...")
            result = get_sentiment_score(kod, ad, use_cache=False)
            print("\n" + "-" * 70)
            print(_colored(f"  📰 {kod} — Haber Sentiment Sonucu", 'cyan', True))
            print("-" * 70)
            haberler = result.get('haberler', [])
            if haberler:
                for i, h in enumerate(haberler, 1):
                    print(f"  {i}. {h}")
            else:
                print(_colored("  Haber bulunamadı.", 'yellow'))
            print("-" * 70)
            print(f"  Sonuç : {format_sentiment(result)}")
            print(f"  Kaynak: {result.get('kaynak', 'yok').upper()}")
            print("-" * 70)
            input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))


def manage_stock_list():
    """Hisse Senedi Listesini Yönet — listeleme, ekleme, çıkarma, ad güncelleme."""
    while True:
        stocks = get_stock_list_with_names()
        header = (
            "\n" + "=" * 70 + "\n"
            + _colored("       📋 HİSSE SENEDİ LİSTESİ YÖNETİMİ", 'cyan', True) + "\n"
            + "=" * 70 + "\n"
            + _colored(f"  Toplam {len(stocks)} hisse takip havuzunda yer almaktadır.\n", 'yellow')
        )
        if stocks:
            header += f"  {'No':<4} {'Kod':<8} {'Şirket Adı'}\n"
            header += "  " + "-" * 65 + "\n"
            for i, s in enumerate(stocks[:15], 1):
                kod_str = _colored(f"{s['kod']:<8}", 'green', True)
                ad_str  = s['ad'] if s['ad'] else _colored("(Ad girilmemiş)", 'yellow')
                header += f"  {i:<4} {kod_str} {ad_str}\n"
            if len(stocks) > 15:
                header += f"  ... ve {len(stocks) - 15} hisse daha\n"

        stock_menu_opts = [
            {'label': "➕ Listeye Yeni Hisse Ekle", 'value': '1', 'desc': "Analiz havuzuna yeni hisse kodu tanımlayın"},
            {'label': "➖ Listeden Hisse Çıkar", 'value': '2', 'desc': "Takip listesinden hisse silin"},
            {'label': "✏️  Hisse Adını Güncelle", 'value': '3', 'desc': "Hisseye ait şirket adını düzenleyin"},
            {'label': "⬅️  Geri Dön", 'value': '4', 'desc': "Önceki ekrana geri dön"}
        ]

        sub = interactive_menu(
            options=stock_menu_opts,
            title="HİSSE LİSTESİ İŞLEMLERİ",
            subtitle="Ok tuşlarıyla seçip ENTER'a basın:",
            header_text=header
        )

        if not sub or sub == '4':
            break

        if sub == '1':
            while True:
                kod = interactive_input("Eklenecek Hisse Kodu (Örn: THYAO)").strip().upper()
                if not kod:
                    break
                ad = interactive_input(f"[{kod}] Şirket Adı (boş bırakılabilir)").strip()
                sonuc = add_stock(kod, ad)
                if sonuc == "added":
                    print(_colored(f"\n  ✓ [{kod}] listeye eklendi.", 'green', True))
                elif sonuc == "exists":
                    print(_colored(f"\n  [UYARI] [{kod}] zaten listede mevcut.", 'yellow', True))
                elif sonuc == "invalid":
                    print(_colored(f"\n  [HATA] Geçersiz hisse kodu. 2-6 karakter arası büyük harf olmalı.", 'red', True))

                if not interactive_confirm("Başka hisse eklenecek mi?", default=False):
                    break
            import data_fetcher as _df
            from stock_list_manager import get_stock_list as _gsl
            _df.BIST_STOCKS = _gsl()

        elif sub == '2':
            if not stocks:
                print(_colored("\n  Listede silinecek hisse yok.", 'red', True))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                continue
            while True:
                kod = interactive_input("Çıkarılacak Hisse Kodu").strip().upper()
                if not kod:
                    break
                sonuc = remove_stock(kod)
                if sonuc == "removed":
                    print(_colored(f"\n  ✓ [{kod}] listeden çıkarıldı.", 'green', True))
                elif sonuc == "not_found":
                    print(_colored(f"\n  [UYARI] [{kod}] listede bulunamadı.", 'yellow', True))

                if not interactive_confirm("Başka hisse çıkarılacak mı?", default=False):
                    break
            import data_fetcher as _df
            from stock_list_manager import get_stock_list as _gsl
            _df.BIST_STOCKS = _gsl()

        elif sub == '3':
            if not stocks:
                print(_colored("\n  Listede güncellenecek hisse yok.", 'red', True))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                continue
            kod = interactive_input("Adı güncellenecek Hisse Kodu").strip().upper()
            if kod:
                yeni_ad = interactive_input(f"[{kod}] Yeni Şirket Adı").strip()
                sonuc = update_stock_name(kod, yeni_ad)
                if sonuc == "updated":
                    print(_colored(f"\n  ✓ [{kod}] adı güncellendi.", 'green', True))
                elif sonuc == "not_found":
                    print(_colored(f"\n  [UYARI] [{kod}] listede bulunamadı.", 'yellow', True))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))


def _colored(text: str, color: str = None, bright: bool = False) -> str:
    if not color:
        return text
    col_code = COLOR_CODES.get(color.upper(), '')
    style_code = '\033[1m' if bright else ''
    if not col_code and not style_code:
        return text
    return f"{style_code}{col_code}{text}\033[0m"


def get_app_banner() -> str:
    term_width = get_terminal_size((80, 20)).columns
    w = min(66, max(40, term_width - 10))
    title = "BAHTİYAR PORTFÖY YÖNETİM SİSTEMİ"
    subtitle = "Gelişmiş Analiz ve Tavsiye Motoru ile Akıllı Yatırım Asistanınız"
    top = "╔" + "═" * w + "╗"
    bottom = "╚" + "═" * w + "╝"
    return (
        f"{_colored(top, 'cyan', True)}\n"
        f"{_colored('║' + title.center(w) + '║', 'green', True)}\n"
        f"{_colored('║' + subtitle.center(w) + '║', 'yellow')}\n"
        f"{_colored(bottom, 'cyan', True)}"
    )


def print_banner():
    print(get_app_banner())
    print()


def get_profile_dashboard_bar(profile_name, budget, stock_count, m_status, ai_badge) -> str:
    if m_status['is_open']:
        m_badge = _colored("🟢 Açık (Canlı Seans)", 'green', True)
    elif m_status['is_weekend']:
        m_badge = _colored(f"🔴 Kapalı (Hafta Sonu — Açılış: {m_status['next_session_desc']})", 'yellow', True)
    else:
        m_badge = _colored(f"🟡 {m_status['desc']} (Açılış: {m_status['next_session_desc']})", 'yellow', True)

    lines = [
        _colored("Aktif Portföy            : ", 'yellow', True) + _colored(f"[{profile_name.upper()}]", 'green', True) + f"  {ai_badge}",
        _colored("BIST Piyasa Durumu       : ", 'yellow', True) + m_badge,
        _colored("Mevcut Nakit Bütçeniz    : ", 'yellow', True) + _colored(f"{budget:,.2f} TL", 'green', True),
        _colored("Portföydeki Hisse Sayısı : ", 'yellow', True) + _colored(f"{stock_count}", 'cyan', True),
    ]
    return "\n".join(lines)


def migrate_old_data():
    if os.path.exists("butce.json") and not os.path.exists("default_butce.json"):
        os.rename("butce.json", "default_butce.json")
    if os.path.exists("islem_gecmisi.md") and not os.path.exists("default_islem_gecmisi.md") and not os.path.exists("default_islem_gecmisi.txt"):
        os.rename("islem_gecmisi.md", "default_islem_gecmisi.md")
    if os.path.exists("islem_gecmisi.txt") and not os.path.exists("default_islem_gecmisi.txt"):
        os.rename("islem_gecmisi.txt", "default_islem_gecmisi.txt")


def init_profile() -> str:
    """
    Başlangıç ekranı (TUI):
    - Mevcut kayıtlı portföyler (hisse adedi ve bütçe önizlemesiyle)
    - ➕ Yeni Portföy Oluştur
    - ⚙️  Uygulama & AI Ayarları (API Key, Önbellek, vb.)
    - 🚪 Çıkış
    """
    while True:
        profiles = get_all_profiles()
        options = []

        if profiles:
            for p in profiles:
                summ = get_profile_summary(p)
                badge_text = f"({summ['stock_count']} hisse | {summ['budget']:,.2f} TL)"
                options.append({
                    'label': f"💼 {p.upper()}",
                    'value': ('profile', p),
                    'badge': badge_text,
                    'desc': f"'{p}' portföyüne giriş yap"
                })
            options.append({'label': "────────────────────────────────────────", 'is_separator': True})

        options.append({
            'label': "➕ Yeni Portföy Oluştur",
            'value': ('action', 'new_profile'),
            'desc': "Yeni bir portföy hesabı açın"
        })
        options.append({
            'label': "⚙️  Uygulama & AI Ayarları",
            'value': ('action', 'settings'),
            'desc': "Gemini/OpenAI API anahtarı ve sistem ayarları"
        })
        options.append({
            'label': "🚪 Çıkış",
            'value': ('action', 'exit'),
            'desc': "Programdan çıkış yap"
        })

        m_status = get_market_status()
        if m_status['is_open']:
            m_badge = _colored("🟢 Açık (Canlı Seans)", 'green', True)
        elif m_status['is_weekend']:
            m_badge = _colored(f"🔴 Kapalı (Hafta Sonu — Açılış: {m_status['next_session_desc']})", 'yellow', True)
        else:
            m_badge = _colored(f"🟡 {m_status['desc']} (Açılış: {m_status['next_session_desc']})", 'yellow', True)

        header = (
            get_app_banner() + "\n\n"
            + _colored("BIST Piyasa Durumu       : ", 'yellow', True) + m_badge + "\n"
        )

        selected = interactive_menu(
            options=options,
            title="BAŞLANGIÇ EKRANI — PORTFÖY SEÇİMİ",
            subtitle="Giriş yapmak istediğiniz portföyü seçin veya yeni oluşturun:",
            header_text=header
        )

        if not selected or selected in (('action', 'exit'), 'exit', 'action_exit', 'q', '11'):
            print(_colored("\nProgramdan çıkılıyor. Bol kazançlar! 👋", 'green', True))
            sys.exit(0)

        kind, val = selected if isinstance(selected, tuple) else ('profile', selected)

        if kind == 'profile':
            set_profile(val)
            set_logger_profile(val)
            print(_colored(f"\n--> [{val.upper()}] portföyü aktif edildi <--", 'green', True))
            return val

        elif kind == 'action':
            if val == 'new_profile':
                while True:
                    p_name = interactive_input("Yeni Portföy (Kullanıcı) Adı").strip()
                    if not p_name:
                        print(_colored("❌ Portföy adı boş bırakılamaz!", 'red', True))
                    else:
                        set_profile(p_name)
                        set_logger_profile(p_name)
                        print(_colored(f"\n--> [{p_name.upper()}] portföyü oluşturuldu ve aktif edildi <--", 'green', True))
                        return p_name
            elif val == 'settings':
                manage_ai_settings()


def main():
    migrate_old_data()

    while True:
        active_profile = init_profile()
        if not active_profile:
            break

        while True:
            budget = load_budget()
            portfolio = load_portfolio()
            m_status = get_market_status()
            ai_ok = is_ai_configured()
            provider_str = get_active_provider().upper()
            ai_badge = _colored(f" [AI:{provider_str}]", 'cyan', True) if ai_ok else _colored(" [AI:Kapalı]", 'yellow')

            header = (
                get_app_banner() + "\n\n"
                + get_profile_dashboard_bar(active_profile, budget, len(portfolio), m_status, ai_badge) + "\n"
            )

            main_options = [
                {
                    'label': "📈 Piyasayı Analiz Et ve Alım Tavsiyesi Ver",
                    'value': '2',
                    'badge': ai_badge,
                    'desc': "BIST teknik analiz motoru ve AI haber duygu analizi"
                },
                {
                    'label': "💼 Portföyümü Görüntüle ve Sat/Tut Tavsiyeleri Al",
                    'value': '3',
                    'desc': "Mevcut hisseler, kâr/zarar durumu ve iz süren stop analizi"
                },
                {
                    'label': "💰 Bütçeyi Görüntüle / Güncelle",
                    'value': '1',
                    'badge': f"({budget:,.2f} TL)",
                    'desc': "Nakit alım gücünüzü görüntüleyin veya güncelleyin"
                },
                {
                    'label': "➕ Portföye Manuel Hisse Ekle",
                    'value': '4',
                    'desc': "Borsa dışından veya geçmişten hisse/maliyet girişi"
                },
                {
                    'label': "📊 AI Performans Raporu (Sinyal Takibi)",
                    'value': '10',
                    'desc': "Geçmiş AL sinyallerinin 5g/10g/20g getiri başarım ölçümü"
                },
                {
                    'label': "🧪 Backtest Modu (Son 2 Yıl Strateji Testi)",
                    'value': '9',
                    'desc': "Geçmiş borsa verileriyle algoritmanın kârlılığını test edin"
                },
                {
                    'label': "📋 Hisse Senedi Listesini Yönet",
                    'value': '7',
                    'desc': "Analiz havuzuna yeni hisse ekleme / çıkarma"
                },
                {
                    'label': "🔄 Portföy Değiştir (Başlangıç Ekranına Dön)",
                    'value': '6',
                    'desc': "Farklı bir portföye geçiş yapın"
                },
                {
                    'label': "⚙️  Uygulama & AI Ayarları",
                    'value': '8',
                    'desc': "Gemini / OpenAI API anahtarları ve önbellek yönetimi"
                },
                {
                    'label': "🗑️  Mevcut Portföyü Sıfırla veya Sil",
                    'value': '5',
                    'desc': "Aktif portföy veritabanını temizle veya hesabı tamamen sil"
                },
                {
                    'label': "🚪 Çıkış",
                    'value': '11',
                    'desc': "Programdan çıkış yap"
                }
            ]

            choice = interactive_menu(
                options=main_options,
                title=f"ANA MENÜ — [{active_profile.upper()}]",
                subtitle="Ok tuşları (↑/↓) ile seçip ENTER'a basın:",
                header_text=header
            )

            if choice == '1':
                try:
                    new_budget_str = input(_colored(f"Yeni bütçenizi girin (TL) [Mevcut: {budget:.2f}]: ", 'magenta')).strip()
                    if not new_budget_str:
                        continue
                    new_budget = float(new_budget_str)
                    if new_budget < 0:
                        print(_colored("❌ Bütçe negatif olamaz!", 'red', True))
                    else:
                        fark = new_budget - budget
                        save_budget(new_budget)
                        log_transaction("Bütçe Güncelleme", "-", "-", "-", fark, new_budget)
                        print(_colored("✅ Bütçeniz başarıyla güncellendi.", 'green', True))
                except ValueError:
                    print(_colored("❌ Lütfen geçerli bir sayı girin.", 'red'))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                    
            elif choice == '2':
                if budget <= 0:
                    print(_colored("⚠️  Lütfen önce bütçenizi güncelleyin (Bütçeniz 0 TL).", 'yellow', True))
                    continue
                    
                if m_status['is_weekend']:
                    print("\n" + _colored("┌─────────────────────────────────────────────────────────────┐", 'yellow'))
                    print(_colored("│  ℹ️  HAFTA SONU PİYASA BİLGİLENDİRMESİ                      │", 'yellow', True))
                    print(_colored("├─────────────────────────────────────────────────────────────┤", 'yellow'))
                    print(_colored("│  • Borsa İstanbul hafta sonu kapalıdır.                     │", 'white'))
                    print(_colored("│  • Analizler Cuma günkü resmi kapanış verileriyle yapılır.  │", 'white'))
                    print(_colored(f"│  • Sinyaller ilk işlem günü ({m_status['effective_date']}) için planlanır. │", 'cyan'))
                    print(_colored("└─────────────────────────────────────────────────────────────┘", 'yellow'))
                elif not m_status['is_open']:
                    print(_colored(f"\nℹ️  Piyasa şu anda kapalı ({m_status['desc']}). Analizler son kapanış verileriyle yapılmaktadır.", 'yellow'))

                print(_colored("\n🔎 Piyasa verileri çekiliyor (hisseler ve BIST100 endeksi)...", 'cyan'))
                from data_fetcher import BIST_STOCKS, MARKET_INDEX
                data_dict = fetch_data()
                
                stocks_count = len([t for t in data_dict.keys() if t.endswith('.IS') and t != MARKET_INDEX])
                print(_colored(f"> {stocks_count}/{len(BIST_STOCKS)} hissenin verisi çekildi.", 'green'))
                
                # ── Piyasa Sağlık Endeksi & Rejim Analizi ──────────────── #
                print(_colored("⚡ BIST Piyasa Sağlık Endeksi ve Risk Rejimi hesaplanıyor...", 'yellow'))
                market_health = calculate_market_health(data_dict)

                # Piyasa Sağlık Paneli
                reg_color = 'green' if market_health['regime'] == 'BULL' else ('yellow' if market_health['regime'] == 'NEUTRAL' else 'red')
                cash_pct_display = int(market_health['cash_target_pct'] * 100)
                invest_pct_display = 100 - cash_pct_display

                print("\n" + _colored("┌─────────────────────────────────────────────────────────────┐", reg_color))
                print(_colored(f"│  {market_health['regime_emoji']} BIST PİYASA SAĞLIK ENDEKSİ: {market_health['health_score']}/100 — [{market_health['regime_title']}]", reg_color, True))
                print(_colored("├─────────────────────────────────────────────────────────────┤", reg_color))
                print(_colored(f"│  • Strateji          : {market_health['summary_msg']}", 'white'))
                print(_colored(f"│  • Hedef Dağılım     : %{cash_pct_display} NAKİT SAVUNMASI  |  %{invest_pct_display} HİSSE YATIRIMI", 'cyan', True))
                print(_colored(f"│  • BIST100 Trend/Mom : {market_health['trend_score']}/40 Trend  |  {market_health['momentum_score']}/30 Momentum", 'white'))
                print(_colored(f"│  • Piyasa Genişliği  : Hisselerin %{market_health['pct_above_sma20']:.0f}'si SMA20 üzerinde ({market_health['breadth_score']}/30 Puan)", 'white'))
                print(_colored("└─────────────────────────────────────────────────────────────┘", reg_color))

                # Ayı / Düşüş Piyasasında %100 Nakitte Bekle
                if not market_health['allow_new_buys']:
                    print("\n" + _colored("🛑 PİYASA KORUMA MODU AKTİF:", 'red', True))
                    print(_colored("   Piyasa genel düşüş trendinde olduğu için sermayeniz %100 NAKİTTE korunmaktadır.", 'yellow'))
                    print(_colored("   Sahte alım sinyallerinden kaçınmak amacıyla yeni hisse alımı yapılmamaktadır.", 'yellow'))
                    input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                    continue

                recommendations = analyze_stocks(data_dict, market_health=market_health)

                if not recommendations:
                    print(_colored("⚠️  Şu anki piyasa koşullarında seçici stratejiye uyan hisse bulunamadı.", 'yellow', True))
                    input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                    continue

                # ── AI Haber Sentiment Analizi (opsiyonel) ──────────────── #
                top_recs = recommendations[:10]
                if is_ai_configured():
                    print(_colored(f"\n🤖 AI ({get_active_provider().upper()}) ile haber duygu analizi yapılıyor...", 'cyan', True))
                    stocks_map = {s['kod']: s.get('ad', '') for s in get_stock_list_with_names()}
                    tickers_info = [
                        {'kod': r['Hisse'], 'ad': stocks_map.get(r['Hisse'], '')}
                        for r in top_recs
                    ]
                    sentiment_results = analyze_sentiment_batch(tickers_info, verbose=True)
                    top_recs = enrich_with_sentiment(top_recs, sentiment_results)
                    print(_colored("✓ Haber analizi tamamlandı.", 'green', True))

                    # ── Sinyalleri kaydet ── #
                    kaydedilen = record_signals(top_recs, sentiment_results)
                    if kaydedilen > 0:
                        if m_status['is_weekend']:
                            print(_colored(f"  📝 {kaydedilen} yeni sinyal Pazartesi ({m_status['effective_date']}) işlem günü için kaydedildi.", 'cyan'))
                        else:
                            print(_colored(f"  📝 {kaydedilen} yeni sinyal kaydedildi (Menü 10'dan takip edebilirsiniz).", 'cyan'))
                else:
                    sentiment_results = {}

                print("\n" + _colored("="*75, 'cyan'))
                print(_colored("          *** 📈 BIST HİSSE TAVSİYELERİ VE TEKNİK DETAYLAR ***", 'cyan', True))
                print(_colored("="*75, 'cyan'))
                for r in top_recs:
                    display    = r.get('Display', r['Hisse'])
                    efektif    = r.get('EfektiveSkor', r['Skor'])
                    skor_str   = _colored(f"{r['Skor']}/15", 'yellow', True)
                    sinyal_col = {'Güçlü': 'green', 'Orta': 'yellow', 'Zayıf': 'red'}.get(r['Sinyal'], 'white')
                    sinyal_str = _colored(r['Sinyal'], sinyal_col, True)

                    if efektif != r['Skor']:
                        delta = efektif - r['Skor']
                        delta_str = _colored(f" (AI{'+' if delta>0 else ''}{delta}→{efektif})", 'cyan', True)
                    else:
                        delta_str = ''

                    disp_str = _colored(f"{display:<12}", 'green', True)
                    fiyat_str = _colored(f"{r['Fiyat']:.2f} TL", 'white', True)
                    print(f"- {disp_str} | Fiyat={fiyat_str} | Skor={skor_str}{delta_str} | Sinyal: {sinyal_str}")
                    if 'HedefFiyat' in r and 'StopLoss' in r:
                        hedef = r['HedefFiyat']
                        stop = r['StopLoss']
                        rr = r.get('RiskOdul', 1.5)
                        print(f"  ├─ 🎯 Hedef: {_colored(f'{hedef:.2f} TL', 'green', True)} | 🛑 Stop-Loss: {_colored(f'{stop:.2f} TL', 'red', True)} | R/R: 1:{rr:.1f}")
                    print(f"  └─ {_colored(r['Nedenler'], 'white')}")
                    
                print(_colored("\n💡 Piyasa rejimine göre optimize edilmiş sepet dağılımı hesaplanıyor...", 'yellow'))
                max_stk = market_health.get('max_recommended_stocks', 3)
                cash_res = market_health.get('cash_target_pct', 0.0)
                allocations, remaining = allocate_budget(budget, recommendations, max_stocks=max_stk, cash_reserve_pct=cash_res)
                
                if not allocations:
                    print(_colored("⚠️  Bütçeniz önerilen hisselerden almak için yetersiz veya nakit kalkanı ayrıldı.", 'red'))
                else:
                    print("\n" + _colored("*" * 75, 'yellow'))
                    print(_colored("                 💰 TAVSİYE EDİLEN SEPET DAĞILIMI", 'yellow', True))
                    print(_colored("*" * 75, 'yellow'))
                    total_spent = 0
                    for item in allocations:
                        display = item.get('Display', item['Hisse'])
                        disp_col = _colored(f"{display:<12}", 'cyan', True)
                        lot_col  = _colored(f"{item['Lot']:<4} lot", 'yellow', True)
                        fiyat_col = _colored(f"{item['Fiyat']:>7.2f} TL/lot", 'white')
                        toplam_col = _colored(f"{item['Toplam Maliyet']:>8.2f} TL", 'green', True)
                        print(f"  {disp_col} | {lot_col} | {fiyat_col} | Toplam: {toplam_col}")
                        total_spent += item['Toplam Maliyet']
                        
                    print(_colored("-" * 75, 'yellow'))
                    print(f"Yatırıma Harcanan Tutar   : {_colored(f'{total_spent:.2f} TL', 'green', True)}")
                    if cash_res > 0:
                        res_val = budget * cash_res
                        print(f"🛡️ Güvenlik Nakit Kalkanı : {_colored(f'{res_val:.2f} TL (%{cash_res*100:.0f})', 'yellow', True)}")
                    print(f"Kalan Toplam Nakit Bütçe  : {_colored(f'{remaining:.2f} TL', 'cyan', True)}")
                    
                al_cevap = input(_colored("\nBu tavsiyelerden veya kendi tercihinizle hisse aldınız mı? (E/H): ", 'magenta', True)).strip().upper()
                if al_cevap == 'E':
                    while True:
                        asset_kodu = input(_colored("\nAldığınız Hisse Kodu (Örn: THYAO): ", 'magenta')).strip().upper()
                        
                        try:
                            miktar = int(input(_colored(f"[{asset_kodu}] Kaç lot aldınız: ", 'magenta')).strip())
                            alis_fiyati = float(input(_colored(f"[{asset_kodu}] Alış Fiyatınız (TL/lot): ", 'magenta')).strip())
                            
                            toplam_tutar = miktar * alis_fiyati
                            if toplam_tutar > budget:
                                print(_colored(f"❌ Hata: Alış tutarı ({toplam_tutar:.2f} TL) mevcut bütçenizden ({budget:.2f} TL) fazla olamaz!", 'red', True))
                            else:
                                if asset_kodu in portfolio:
                                    mevcut_lot = portfolio[asset_kodu]['lot']
                                    mevcut_maliyet = portfolio[asset_kodu]['maliyet']
                                    yeni_lot = mevcut_lot + miktar
                                    yeni_maliyet = ((mevcut_lot * mevcut_maliyet) + toplam_tutar) / yeni_lot
                                    portfolio[asset_kodu] = {'lot': yeni_lot, 'maliyet': yeni_maliyet}
                                else:
                                    portfolio[asset_kodu] = {'lot': miktar, 'maliyet': alis_fiyati}
                                    
                                budget -= toplam_tutar
                                save_portfolio(portfolio)
                                save_budget(budget)
                                log_transaction("Hisse Alım (lot)", asset_kodu, miktar, alis_fiyati, -toplam_tutar, budget)
                                print(_colored(f"✅ {asset_kodu} başarıyla portföye eklendi. Kalan Bütçeniz: {budget:.2f} TL", 'green', True))
                        except ValueError:
                            print(_colored("❌ Hatalı giriş yaptınız. Lütfen miktar için tam sayı, fiyat için sayı girin.", 'red'))
                            
                        baska = input(_colored("\nAldığınız başka hisse var mı? (E/H): ", 'magenta')).strip().upper()
                        if baska != 'E':
                            break
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))

            elif choice == '3':
                if not portfolio:
                    print(_colored("\n⚠️  Portföyünüzde henüz hisse bulunmuyor.", 'yellow'))
                    input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                    continue

                if m_status['is_weekend']:
                    print(_colored("\nℹ️  Hafta sonu: Portföy değerlemesi Cuma kapanış fiyatlarıyla hesaplanmaktadır.", 'yellow'))

                print(_colored("\n🔎 Portföy verileriniz için güncel piyasa fiyatları çekiliyor...", 'cyan'))
                from data_fetcher import BIST_STOCKS, MARKET_INDEX

                fetch_list = list(set(BIST_STOCKS + [f"{t}.IS" for t in portfolio.keys()] + [MARKET_INDEX]))
                data_dict = fetch_data(fetch_list)

                stocks_count = len([t for t in data_dict.keys() if t.endswith('.IS') and t != MARKET_INDEX])
                print(_colored(f"> {stocks_count}/{len(fetch_list)-1} hissenin verisi çekildi.", 'green'))

                market_health = calculate_market_health(data_dict)
                print(_colored("⚡ Portföyünüz teknik analiz, piyasa rejimi ve iz süren stop motoru ile değerlendiriliyor...", 'yellow'))
                evaluations = evaluate_portfolio(portfolio, data_dict, market_health=market_health)

                # ── AI Haber Sentiment (portföy hisseleri için) ────────────── #
                portfolio_sentiment = {}
                if is_ai_configured():
                    print(_colored(f"\n🤖 AI ({get_active_provider().upper()}) ile portföy haber analizi yapılıyor...", 'cyan', True))
                    stocks_map = {s['kod']: s.get('ad', '') for s in get_stock_list_with_names()}
                    port_tickers = [{'kod': h, 'ad': stocks_map.get(h, '')} for h in portfolio.keys()]
                    portfolio_sentiment = analyze_sentiment_batch(port_tickers, verbose=True)
                    print(_colored("✓ Haber analizi tamamlandı.", 'green', True))

                print("\n" + _colored("=" * 80, 'cyan'))
                print(_colored(f"          [{active_profile.upper()}] PORTFÖY DURUMU — TEKNİK + HABER ANALİZİ", 'cyan', True))
                if market_health['regime'] != 'BULL':
                    reg_col = 'yellow' if market_health['regime'] == 'NEUTRAL' else 'red'
                    print(_colored(f"  Piyasa Rejimi: {market_health['regime_emoji']} {market_health['regime_title']} ({market_health['health_score']}/100) — {market_health['summary_msg']}", reg_col, True))
                print(_colored("=" * 80, 'cyan'))

                satilacaklar = []
                toplam_portfoy_degeri = 0
                toplam_maliyet = 0

                for ev in evaluations:
                    hisse   = ev['Hisse']
                    lot     = ev['Lot']
                    fiyat   = ev['Fiyat']
                    maliyet = ev['Maliyet']
                    k_z     = ev['K/Z %']
                    durum   = ev['Durum']
                    neden   = ev['Nedenler']

                    guncel_tutar  = lot * fiyat
                    hisse_maliyeti = lot * maliyet
                    toplam_portfoy_degeri += guncel_tutar
                    toplam_maliyet        += hisse_maliyeti

                    # K/Z rengi
                    kz_color = 'green' if k_z >= 0 else 'red'
                    kz_str   = _colored(f"%{k_z:>+6.2f}", kz_color, True)

                    print(f"📊 {_colored(hisse, 'yellow', True):<5} | "
                          f"Lot: {_colored(str(lot), 'cyan'):<4} | "
                          f"Maliyet: {maliyet:>7.2f} TL | "
                          f"Güncel: {fiyat:>7.2f} TL | "
                          f"K/Z: {kz_str}")

                    # Teknik tavsiye satırı
                    durum_color = {'Sat': 'red', 'Dikkatli Tut': 'yellow', 'Güçlü Tut': 'green'}.get(durum, 'white')
                    t_stop = ev.get('TrailingStop', 0.0)
                    t_stop_str = f" | 🛡️ İz Süren Stop: {_colored(f'{t_stop:.2f} TL', 'cyan', True)}" if t_stop > 0 else ""
                    print(f"   📈 Teknik : {_colored(durum, durum_color, True)}{t_stop_str} — {neden}")

                    # AI Sentiment satırı (varsa)
                    sent = portfolio_sentiment.get(hisse)
                    nihai_durum = durum

                    if sent and sent.get('kaynak') != 'yok':
                        sent_line = format_sentiment(sent)
                        print(f"   {sent_line}")

                        if sent.get('etiket') == 'COK_OLUMSUZ' and durum == 'Güçlü Tut':
                            print(_colored("   ⚠️  AI SAT UYARISI: Çok olumsuz haber akışı teknik sinyale rağmen risk oluşturuyor!", 'red', True))
                            nihai_durum = 'Dikkatli Tut'
                        elif sent.get('etiket') == 'OLUMSUZ' and durum == 'Güçlü Tut':
                            print(_colored("   ⚡ AI DİKKAT: Olumsuz haberler mevcut, takipte kalın.", 'yellow', True))
                            nihai_durum = 'Dikkatli Tut'
                        elif sent.get('etiket') in ('COK_OLUMLU', 'OLUMLU') and durum == 'Sat':
                            print(_colored("   💡 AI NOT: Olumlu haber akışı var; satış kararını gözden geçirin.", 'cyan', True))

                    print(_colored("-" * 80, 'cyan'))

                    if nihai_durum in ['Sat', 'Dikkatli Tut']:
                        satilacaklar.append(ev)

                genel_kz_tl    = toplam_portfoy_degeri - toplam_maliyet
                genel_kz_yuzde = (genel_kz_tl / toplam_maliyet) * 100 if toplam_maliyet > 0 else 0
                kz_renk        = 'green' if genel_kz_tl >= 0 else 'red'

                print("\n" + _colored("=" * 80, 'cyan'))
                print(f"Portföyün Toplam Maliyeti    : {_colored(f'{toplam_maliyet:>12.2f} TL', 'white', True)}")
                print(f"Portföyün Güncel Toplam Değeri: {_colored(f'{toplam_portfoy_degeri:>12.2f} TL', 'cyan', True)}")
                print(_colored(
                    f"Genel Portföy K/Z Durumu     : {genel_kz_tl:>+12.2f} TL ({genel_kz_yuzde:>+.2f}%)",
                    kz_renk, True
                ))
                print(_colored("=" * 80, 'cyan'))

                log_transaction("Portföy Değerlemesi", "-", "-", "-", toplam_portfoy_degeri, budget, genel_kz_tl, genel_kz_yuzde)
                
                sat_cevap = input(_colored("\nPortföyünüzdeki herhangi bir hisseyi satmak ister misiniz? (E/H): ", 'magenta', True)).strip().upper()
                if sat_cevap == 'E':
                    satis_yapildi = False
                    while True:
                        satilan_asset = input(_colored("\nHangi hisseyi satmak istiyorsunuz? (Hisse kodu): ", 'magenta', True)).strip().upper()
                        
                        if satilan_asset in portfolio:
                            try:
                                sat_miktar = int(input(_colored(f"Kaç lot satacaksınız? (Mevcut: {portfolio[satilan_asset]['lot']}): ", 'magenta')).strip())
                                if sat_miktar <= 0 or sat_miktar > portfolio[satilan_asset]['lot']:
                                    print(_colored("❌ Geçersiz miktar!", 'red'))
                                else:
                                    maliyet_fiyati = portfolio[satilan_asset]['maliyet']
                                    guncel_fiyat = next((item['Fiyat'] for item in evaluations if item['Hisse'] == satilan_asset), maliyet_fiyati)
                                    
                                    satis_input = input(_colored(f"[{satilan_asset}] Satış Fiyatınız (TL/lot) [Boş = Güncel Fiyat {guncel_fiyat:.2f} TL]: ", 'magenta')).strip()
                                    if satis_input:
                                        satis_fiyati = float(satis_input)
                                        if satis_fiyati <= 0:
                                            print(_colored("❌ Satış fiyatı 0'dan büyük olmalıdır!", 'red'))
                                            continue
                                    else:
                                        satis_fiyati = guncel_fiyat

                                    kar_zarar_tl = (satis_fiyati - maliyet_fiyati) * sat_miktar
                                    kar_zarar_yuzde = ((satis_fiyati - maliyet_fiyati) / maliyet_fiyati) * 100 if maliyet_fiyati > 0 else 0
                                    
                                    satis_geliri = sat_miktar * satis_fiyati
                                    budget += satis_geliri
                                    
                                    portfolio[satilan_asset]['lot'] -= sat_miktar
                                    if portfolio[satilan_asset]['lot'] == 0:
                                        del portfolio[satilan_asset]
                                        
                                    save_portfolio(portfolio)
                                    save_budget(budget)
                                    
                                    log_transaction("Hisse Satım (lot)", satilan_asset, sat_miktar, satis_fiyati, satis_geliri, budget, kar_zarar_tl, kar_zarar_yuzde)
                                    print(_colored(f"\n✅ {satilan_asset} satıldı ({sat_miktar} lot @ {satis_fiyati:.2f} TL). Satış Geliri: {satis_geliri:.2f} TL.", 'green', True))
                                    kz_col = 'green' if kar_zarar_tl >= 0 else 'red'
                                    print(_colored(f"İşlemden Elde Edilen K/Z: {kar_zarar_tl:+.2f} TL (%{kar_zarar_yuzde:+.2f})", kz_col, True))
                                    print(_colored(f"Yeni Bütçeniz: {budget:.2f} TL", 'cyan', True))
                                    satis_yapildi = True
                                    
                            except ValueError:
                                print(_colored("❌ Lütfen geçerli bir sayı girin.", 'red'))
                        else:
                            print(_colored("❌ Bu hisse portföyünüzde bulunmuyor.", 'red'))
                            
                        if not portfolio:
                            print(_colored("\nPortföyünüzde satılacak hisse kalmadı.", 'yellow'))
                            break
                            
                        baska_sat = input(_colored("\nSatmak istediğiniz başka hisse var mı? (E/H): ", 'magenta')).strip().upper()
                        if baska_sat != 'E':
                            break
                            
                    if satis_yapildi:
                        print(_colored("\n🔄 Nakitiniz güncellendi. Yeni bütçenizle alınabilecek hisseler hesaplanıyor...", 'cyan'))
                        recommendations = analyze_stocks(data_dict)
                        allocations, remaining = allocate_budget(budget, recommendations)
                        
                        if allocations:
                            print(_colored("\nİşte sattığınız hisselerin yerine alınabilecek öneriler:", 'yellow', True))
                            for item in allocations:
                                disp = _colored(item['Hisse'], 'cyan', True)
                                lot_str = _colored(f"{item['Lot']} Lot", 'yellow', True)
                                top_str = _colored(f"{item['Toplam Maliyet']:.2f} TL", 'green', True)
                                print(f"- {disp:<6}: {lot_str} alınabilir (Toplam: {top_str}) | Neden: {item['Nedenler']}")
                        else:
                            print(_colored("Şu an yeni alım için uygun kriterde hisse bulunamadı.", 'yellow'))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))

            elif choice == '4':
                while True:
                    hisse_kodu = input(_colored("\nHisse Kodu (Örn: THYAO): ", 'magenta', True)).strip().upper()
                    try:
                        lot_miktari = int(input(_colored(f"[{hisse_kodu}] Kaç Lot: ", 'magenta')).strip())
                        alis_fiyati = float(input(_colored(f"[{hisse_kodu}] Maliyetiniz (TL): ", 'magenta')).strip())
                        
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
                        print(_colored(f"✅ {hisse_kodu} portföye eklendi. İşlem tutarı bütçeden düşüldü. Yeni bütçeniz: {budget:.2f} TL", 'green', True))
                    except ValueError:
                        print(_colored("❌ Hatalı giriş yaptınız!", 'red'))
                        
                    baska = input(_colored("\nEkleyeceğiniz başka hisse var mı? (E/H): ", 'magenta')).strip().upper()
                    if baska != 'E':
                        break
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))

            elif choice == '5':
                sub_opts = [
                    {
                        'label': "🗑️  Portföyü Sıfırla (Bütçe ve hisseleri sıfırlar, log kalır)",
                        'value': '1',
                        'desc': "Hesap kalır ancak nakit bütçe ve hisseler sıfırlanır"
                    },
                    {
                        'label': "❌ Portföyü Tamamen Sil (Tüm dosyaları kalıcı olarak siler)",
                        'value': '2',
                        'desc': "Hesap, bütçe dosyası ve tüm işlem geçmişi tamamen yok edilir"
                    },
                    {
                        'label': "⬅️  İptal (Geri Dön)",
                        'value': '3',
                        'desc': "Herhangi bir değişiklik yapmadan ana menüye dön"
                    }
                ]

                sub_choice = interactive_menu(
                    options=sub_opts,
                    title=f"[{active_profile.upper()}] PORTFÖY YÖNETİMİ",
                    subtitle="Lütfen yapmak istediğiniz işlemi seçin:"
                )

                if sub_choice == '1':
                    if interactive_confirm(f"[{active_profile.upper()}] portföyündeki bütçe ve hisseler SIFIRLANACAK. Emin misiniz?", default=False):
                        reset_current_profile()
                        log_transaction("Portföy Sıfırlama", "-", "-", "-", 0, 0)
                        print(_colored(f"\n✅ [{active_profile.upper()}] portföyü başarıyla sıfırlandı.", 'green', True))
                        input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                elif sub_choice == '2':
                    if interactive_confirm(f"⚠️  DİKKAT: [{active_profile.upper()}] portföyü ve tüm işlem geçmişi TAMAMEN SİLİNECEK! Emin misiniz?", default=False):
                        delete_profile(active_profile)
                        print(_colored(f"\n🗑️  [{active_profile.upper()}] portföyü kalıcı olarak silindi.", 'red', True))
                        input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))
                        break  # Başlangıç ekranına dön
                else:
                    print(_colored("\nİşlem iptal edildi.", 'yellow'))
                    input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))

            elif choice == '6':
                print(_colored(f"\n[{active_profile.upper()}] portföyünden çıkılıyor...", 'cyan'))
                break  # Başlangıç ekranına dön

            elif choice == '7':
                manage_stock_list()

            elif choice == '8':
                manage_ai_settings()

            elif choice == '9':
                # BACKTEST MODU
                try:
                    from backtest import run_backtest_interactive
                    run_backtest_interactive()
                except Exception as e:
                    print(_colored(f"❌ Backtest modu çalıştırılamadı: {e}", 'red'))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))

            elif choice == '10':
                # AI PERFORMANS RAPORU
                print("\n" + _colored("=" * 80, 'cyan'))
                print(_colored("  📊 AI PERFORMANS RAPORU — Sinyal Takip ve Karşılaştırma", 'cyan', True))
                print(_colored("=" * 80, 'cyan'))
                if not is_ai_configured():
                    print(_colored("  ⚠️  AI yapılandırılmamış. Önce Menü 8'den API anahtarı girin.", 'yellow', True))
                else:
                    try:
                        print_performance_report()
                    except Exception as e:
                        print(_colored(f"  ❌ Rapor oluşturulamadı: {e}", 'red'))
                input(_colored("\nDevam etmek için ENTER'a basın...", 'cyan'))

            elif choice in ('11', 'exit', None):
                print(_colored("\nProgramdan çıkılıyor. Bol kazançlar! 👋", 'green', True))
                sys.exit(0)


if __name__ == "__main__":
    main()
