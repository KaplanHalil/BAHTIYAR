"""
ui_menu.py — Terminal Kullanıcı Arayüzü (TUI) & Ok Tuşları ile Gezinme Motoru
===========================================================================
Terminal üzerinde ok tuşları (↑/↓) ile gezinilebilen, görsel olarak zenginleştirilmiş,
cross-platform (macOS, Linux, Windows) etkileşimli menü ve girdi yöneticisi.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any, Callable, List, Optional, Union

# Windows vs Unix klavye yakalama desteği
IS_WINDOWS = os.name == 'nt'

if IS_WINDOWS:
    import msvcrt
else:
    import termios
    import tty


# ═══════════════════════════════════════════════════════════════════ #
#  ANSI RENK VE BİÇİMLENDİRME
# ═══════════════════════════════════════════════════════════════════ #

COLORS = {
    'BLACK': '\033[30m',
    'RED': '\033[31m',
    'GREEN': '\033[32m',
    'YELLOW': '\033[33m',
    'BLUE': '\033[34m',
    'MAGENTA': '\033[35m',
    'CYAN': '\033[36m',
    'WHITE': '\033[37m',
    'RESET': '\033[0m',
    'BOLD': '\033[1m',
    'DIM': '\033[2m',
    'UNDERLINE': '\033[4m',
    'BG_CYAN': '\033[46m',
    'BG_BLUE': '\033[44m',
    'BG_BLACK': '\033[40m',
    'BG_GREEN': '\033[42m',
    'BG_YELLOW': '\033[43m',
}


def c(text: str, color: str = 'WHITE', bold: bool = False) -> str:
    """Metni ANSI renk kodlarıyla biçimlendirir."""
    color_code = COLORS.get(color.upper(), '')
    bold_code = COLORS['BOLD'] if bold else ''
    return f"{bold_code}{color_code}{text}{COLORS['RESET']}"


def clear_screen():
    """Terminal ekranını temizler (flicker-free ANSI sequence)."""
    if IS_WINDOWS:
        os.system('cls')
    else:
        sys.stdout.write('\033[H\033[2J')
        sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════ #
#  KLAVYE GİRDİ MOTORU
# ═══════════════════════════════════════════════════════════════════ #

KEY_UP = 'UP'
KEY_DOWN = 'DOWN'
KEY_LEFT = 'LEFT'
KEY_RIGHT = 'RIGHT'
KEY_ENTER = 'ENTER'
KEY_ESC = 'ESC'
KEY_BACKSPACE = 'BACKSPACE'


def get_key() -> str:
    """
    Klavyeden tek bir tuş vuruşunu anlık olarak (Enter beklemeden) okur.
    Özel tuşları (Ok yönleri, Enter, ESC vb.) standart anahtarlara dönüştürür.
    """
    if not sys.stdin.isatty():
        # Pipe/Non-interactive ortam
        line = sys.stdin.readline()
        if not line:
            return KEY_ESC
        return line.strip()

    if IS_WINDOWS:
        try:
            ch = msvcrt.getch()
            if ch in (b'\x00', b'\xe0'):
                ch2 = msvcrt.getch()
                if ch2 == b'H':
                    return KEY_UP
                elif ch2 == b'P':
                    return KEY_DOWN
                elif ch2 == b'K':
                    return KEY_LEFT
                elif ch2 == b'M':
                    return KEY_RIGHT
                return ''
            elif ch in (b'\r', b'\n'):
                return KEY_ENTER
            elif ch == b'\x1b':
                return KEY_ESC
            elif ch in (b'\x08', b'\x7f'):
                return KEY_BACKSPACE
            elif ch == b' ':
                return ' '
            else:
                return ch.decode('utf-8', errors='ignore')
        except Exception:
            return ''
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            # Python'un TextIOWrapper tamponlamasını önlemek için doğrudan os.read(fd) kullanıyoruz
            b = os.read(fd, 1)
            if not b:
                return ''
            if b == b'\x1b':
                import select
                # Escape dizisinin devamı var mı kontrol et (100ms)
                r, _, _ = select.select([fd], [], [], 0.1)
                if r:
                    seq = os.read(fd, 16)
                    # Standart ANSI, VT100/220, Application / SS3 modları
                    if seq in (b'[A', b'OA', b'[1;2A', b'[1;5A', b'[[A'):
                        return KEY_UP
                    elif seq in (b'[B', b'OB', b'[1;2B', b'[1;5B', b'[[B'):
                        return KEY_DOWN
                    elif seq in (b'[C', b'OC', b'[1;2C', b'[1;5C', b'[[C'):
                        return KEY_RIGHT
                    elif seq in (b'[D', b'OD', b'[1;2D', b'[1;5D', b'[[D'):
                        return KEY_LEFT
                    elif seq in (b'[H', b'OH', b'[1~'):
                        return 'HOME'
                    elif seq in (b'[F', b'OF', b'[4~'):
                        return 'END'
                    elif seq in (b'[5~',):
                        return 'PAGE_UP'
                    elif seq in (b'[6~',):
                        return 'PAGE_DOWN'
                    elif seq in (b'[3~',):
                        return 'DELETE'
                    # Tanınmayan diğer escape dizilerini yoksay (çıkış tetiklemesin)
                    return ''
                else:
                    return KEY_ESC
            elif b in (b'\r', b'\n'):
                return KEY_ENTER
            elif b in (b'\x7f', b'\x08'):
                return KEY_BACKSPACE
            elif b == b' ':
                return ' '
            else:
                return b.decode('utf-8', errors='ignore')
        except Exception:
            return ''
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ═══════════════════════════════════════════════════════════════════ #
#  ETKİLEŞİMLİ MENÜ BİLEŞENİ
# ═══════════════════════════════════════════════════════════════════ #

class MenuItem:
    def __init__(
        self,
        label: str,
        value: Any = None,
        shortcut: Optional[str] = None,
        badge: Optional[str] = None,
        desc: Optional[str] = None,
        is_separator: bool = False
    ):
        self.label = label
        self.value = value if value is not None else label
        self.shortcut = shortcut
        self.badge = badge
        self.desc = desc
        self.is_separator = is_separator


def interactive_menu(
    options: List[Union[MenuItem, dict, str]],
    title: str = "LÜTFEN SEÇİM YAPIN",
    subtitle: Optional[str] = None,
    header_text: Optional[str] = None,
    selected_index: int = 0,
    show_shortcuts: bool = True,
    clear_before_render: bool = True
) -> Any:
    """
    Ok tuşları (↑/↓) ile gezinilebilen etkileşimli bir TUI menüsü sunar.

    Args:
        options: Menü seçenekleri (MenuItem, dict veya str listesi)
        title: Menü çerçeve başlığı
        subtitle: Açıklama / bilgi metni
        header_text: Menünün üstünde gösterilecek özel banner/durum metni
        selected_index: Varsayılan seçili öğe indeksi
        show_shortcuts: Sayı kısayollarının gösterilip gösterilmeyeceği
        clear_before_render: Her karede ekranın temizlenmesi

    Returns:
        Seçilen öğenin `value` değeri veya ESC durumunda None
    """
    items: List[MenuItem] = []
    selectable_indices: List[int] = []

    for i, opt in enumerate(options):
        if isinstance(opt, MenuItem):
            item = opt
        elif isinstance(opt, dict):
            item = MenuItem(
                label=opt.get('label', ''),
                value=opt.get('value', opt.get('label', '')),
                shortcut=opt.get('shortcut'),
                badge=opt.get('badge'),
                desc=opt.get('desc'),
                is_separator=opt.get('is_separator', False)
            )
        elif isinstance(opt, str):
            if opt.startswith('---') or opt.startswith('═══'):
                item = MenuItem(label=opt, is_separator=True)
            else:
                item = MenuItem(label=opt, value=opt)
        else:
            item = MenuItem(label=str(opt), value=opt)

        items.append(item)
        if not item.is_separator:
            selectable_indices.append(len(items) - 1)

    if not selectable_indices:
        return None

    if selected_index not in selectable_indices:
        selected_index = selectable_indices[0]

    # Non-interactive / pipe modu için fallback
    if not sys.stdin.isatty():
        return _non_interactive_fallback(items, title, header_text)

    while True:
        if clear_before_render:
            clear_screen()

        # 1. Özel Header (Banner / Portföy Durumu)
        if header_text:
            print(header_text)

        # 2. Menü Çerçeve Başlığı
        box_width = 72
        title_str = f" {title} "
        left_pad = max(0, (box_width - 2 - len(title_str)) // 2)
        right_pad = max(0, box_width - 2 - len(title_str) - left_pad)

        print(c("┌" + "─" * (box_width - 2) + "┐", 'CYAN'))
        print(
            c("│", 'CYAN')
            + " " * left_pad
            + c(title_str, 'CYAN', bold=True)
            + " " * right_pad
            + c("│", 'CYAN')
        )
        print(c("├" + "─" * (box_width - 2) + "┤", 'CYAN'))

        if subtitle:
            sub_trimmed = subtitle[:box_width - 6]
            print(c("│", 'CYAN') + f"  {c(sub_trimmed, 'YELLOW')}" + " " * (box_width - 4 - len(sub_trimmed)) + c("│", 'CYAN'))
            print(c("├" + "─" * (box_width - 2) + "┤", 'CYAN'))

        # 3. Seçenekler
        shortcut_idx = 1
        for idx, item in enumerate(items):
            if item.is_separator:
                sep_line = "  " + "─" * (box_width - 6)
                print(c("│", 'CYAN') + c(sep_line, 'DIM') + "  " + c("│", 'CYAN'))
                continue

            is_selected = (idx == selected_index)
            pointer = "❯ " if is_selected else "  "
            badge_str = f" {item.badge}" if item.badge else ""
            base_label = f"{item.label}{badge_str}"

            if is_selected:
                line_content = f"{pointer}{c(base_label, 'CYAN', bold=True)}"
            else:
                line_content = f"{pointer}{c(base_label, 'WHITE')}"

            # Satır hizalaması
            raw_len = len(pointer) + len(base_label)
            spaces = max(1, box_width - 6 - raw_len)

            if is_selected:
                print(c("│", 'CYAN') + f" {c(' ' + pointer + base_label, 'CYAN', bold=True)}{' ' * spaces}" + c("│", 'CYAN'))
            else:
                print(c("│", 'CYAN') + f"   {line_content}{' ' * max(0, spaces - 1)}" + c("│", 'CYAN'))

            shortcut_idx += 1

        # 4. Menü Alt Bilgisi
        print(c("├" + "─" * (box_width - 2) + "┤", 'CYAN'))
        help_tip = "↑/↓: Gezin  |  ENTER: Seç  |  Sayı: Hızlı Seç  |  q: Çıkış"
        help_pad = max(0, box_width - 4 - len(help_tip))
        print(c("│", 'CYAN') + f"  {c(help_tip, 'DIM')}" + " " * help_pad + c("│", 'CYAN'))
        print(c("└" + "─" * (box_width - 2) + "┘", 'CYAN'))

        # 5. Tuş Okuma
        key = get_key()

        if key in (KEY_UP, 'k', 'K', 'w', 'W'):
            cur_pos = selectable_indices.index(selected_index)
            new_pos = (cur_pos - 1) % len(selectable_indices)
            selected_index = selectable_indices[new_pos]

        elif key in (KEY_DOWN, 'j', 'J', 's', 'S'):
            cur_pos = selectable_indices.index(selected_index)
            new_pos = (cur_pos + 1) % len(selectable_indices)
            selected_index = selectable_indices[new_pos]

        elif key in (KEY_ENTER, ' '):
            return items[selected_index].value

        elif key == 'HOME':
            selected_index = selectable_indices[0]

        elif key == 'END':
            selected_index = selectable_indices[-1]

        elif key in ('q', 'Q', KEY_ESC):
            for s_idx in selectable_indices:
                val = items[s_idx].value
                if val in (('action', 'exit'), 'exit', 'cikis', 'back', 'geri', 'quit', '0', '11') or str(val).lower() in ('exit', 'cikis', 'back', 'geri', 'quit', '0', '11'):
                    return val
            return None

        elif not key:
            continue

        else:
            # Sayı tuşları ile hızlı seçim
            num_idx = 1
            for s_idx in selectable_indices:
                sc = items[s_idx].shortcut or str(num_idx)
                if key == sc or (key.isdigit() and str(num_idx) == key):
                    return items[s_idx].value
                num_idx += 1


def _non_interactive_fallback(items: List[MenuItem], title: str, header_text: Optional[str]) -> Any:
    """Piped veya non-interactive terminaller için metin tabanlı seçim yedeği."""
    if header_text:
        print(header_text)
    print(f"\n=== {title} ===")
    valid_map = {}
    idx = 1
    for item in items:
        if item.is_separator:
            continue
        print(f" {idx}. {item.label} {item.badge or ''}")
        valid_map[str(idx)] = item.value
        idx += 1

    try:
        line = sys.stdin.readline()
        if not line:
            # EOF ulaşıldı, güvenli şekilde çık
            for item in items:
                if str(item.value).lower() in ('exit', '11', 'action_exit', str(('action', 'exit')), '6', 'back'):
                    return item.value
            sys.exit(0)
        choice = line.strip()
        if choice in valid_map:
            return valid_map[choice]
        for item in items:
            if str(item.value) == choice or item.shortcut == choice:
                return item.value
        return valid_map.get("1", items[0].value)
    except (EOFError, KeyboardInterrupt, Exception):
        for item in items:
            if str(item.value).lower() in ('exit', '11', 'action_exit', str(('action', 'exit')), '6', 'back'):
                return item.value
        sys.exit(0)


# ═══════════════════════════════════════════════════════════════════ #
#  GİRDİ VE ONAY FONKSİYONLARI
# ═══════════════════════════════════════════════════════════════════ #

def interactive_input(prompt: str, default: str = "") -> str:
    """Temiz ve renkli bir girdi istemcisi sunar."""
    default_hint = f" [{default}]" if default else ""
    prompt_str = c(f"{prompt}{default_hint}: ", 'MAGENTA', bold=True)
    try:
        val = input(prompt_str).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        return default


def interactive_confirm(prompt: str, default: bool = True) -> bool:
    """Etkileşimli Evet / Hayır onay sorusu."""
    hint = " [E/h]" if default else " [e/H]"
    prompt_str = c(f"{prompt}{hint}: ", 'YELLOW', bold=True)
    try:
        val = input(prompt_str).strip().lower()
        if not val:
            return default
        return val in ('e', 'evet', 'y', 'yes')
    except (EOFError, KeyboardInterrupt):
        return default
