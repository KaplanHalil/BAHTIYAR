import json
import os
import glob

CURRENT_PROFILE = "default"

def set_profile(name):
    global CURRENT_PROFILE
    CURRENT_PROFILE = name

def get_all_profiles():
    files = glob.glob("*_butce.json")
    return [f.replace("_butce.json", "") for f in files]

def get_budget_file():
    return f"{CURRENT_PROFILE}_butce.json"

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
        json.dump(data, f)

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
    b_file = f"{name}_butce.json"
    l_file = f"{name}_islem_gecmisi.txt"
    if os.path.exists(b_file):
        os.remove(b_file)
    if os.path.exists(l_file):
        os.remove(l_file)

def reset_current_profile():
    save_data({"budget": 0.0, "portfolio": {}})
