import json
import os
import glob

CURRENT_PROFILE = "default"
PORTFOLIOS_DIR = "portfolios"


def _ensure_dir():
    if not os.path.exists(PORTFOLIOS_DIR):
        os.makedirs(PORTFOLIOS_DIR, exist_ok=True)


def set_profile(name):
    global CURRENT_PROFILE
    CURRENT_PROFILE = name


def get_all_profiles():
    _ensure_dir()
    files = glob.glob(os.path.join(PORTFOLIOS_DIR, "*_butce.json")) + glob.glob("*_butce.json")
    profiles = set()
    for f in files:
        base = os.path.basename(f)
        profiles.add(base.replace("_butce.json", ""))
    return sorted(list(profiles))


def get_profile_summary(name):
    """Belirtilen profilin bütçe ve hisse sayısı özetini döndürür."""
    b_file = os.path.join(PORTFOLIOS_DIR, f"{name}_butce.json")
    if not os.path.exists(b_file):
        b_file = f"{name}_butce.json"
    if os.path.exists(b_file):
        try:
            with open(b_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                b = float(data.get("budget", 0.0))
                p = data.get("portfolio", {})
                return {"budget": b, "stock_count": len(p), "stocks": list(p.keys())}
        except Exception:
            pass
    return {"budget": 0.0, "stock_count": 0, "stocks": []}


def get_budget_file():
    _ensure_dir()
    old_file = f"{CURRENT_PROFILE}_butce.json"
    new_file = os.path.join(PORTFOLIOS_DIR, f"{CURRENT_PROFILE}_butce.json")
    if os.path.exists(old_file) and not os.path.exists(new_file):
        try:
            os.rename(old_file, new_file)
        except Exception:
            return old_file
    return new_file


def load_data():
    b_file = get_budget_file()
    if os.path.exists(b_file):
        try:
            with open(b_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass
    return {"budget": 0.0, "portfolio": {}}


def save_data(data):
    with open(get_budget_file(), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_budget():
    return load_data().get("budget", 0.0)


def save_budget(amount):
    data = load_data()
    data["budget"] = amount
    save_data(data)


def load_portfolio():
    return load_data().get("portfolio", {})


def save_portfolio(portfolio):
    data = load_data()
    data["portfolio"] = portfolio
    save_data(data)


def delete_profile(name):
    for d in [PORTFOLIOS_DIR, "."]:
        b_file = os.path.join(d, f"{name}_butce.json")
        l_file = os.path.join(d, f"{name}_islem_gecmisi.txt")
        if os.path.exists(b_file):
            try:
                os.remove(b_file)
            except Exception:
                pass
        if os.path.exists(l_file):
            try:
                os.remove(l_file)
            except Exception:
                pass


def reset_current_profile():
    save_data({"budget": 0.0, "portfolio": {}})
