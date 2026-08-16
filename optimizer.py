def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _asset_unit(asset_type, fallback_unit=None):
    if fallback_unit:
        return fallback_unit
    return 'lot'


def _build_portfolio_item(pick, quantity, cost):
    asset_type = pick.get('AssetType', 'HISSE')
    item = {
        'Hisse': pick['Hisse'],
        'Fiyat': _safe_float(pick['Fiyat']),
        'Lot': quantity,
        'Toplam Maliyet': cost,
        'Nedenler': pick.get('Nedenler', ''),
        'AssetType': asset_type,
        'Unit': _asset_unit(asset_type, pick.get('Unit'))
    }

    if 'Display' in pick:
        item['Display'] = pick['Display']

    return item


def _rank_candidate(pick):
    score = _safe_float(pick.get('Skor'), 1.0)
    rsi = _safe_float(pick.get('RSI'), 50.0)
    price = _safe_float(pick.get('Fiyat'))
    return (-score, rsi, price, str(pick.get('Hisse', '')))


def allocate_budget(budget, recommendations, max_stocks=3, cash_reserve_pct=0.0):
    """
    Bütçeyi en iyi hisse tavsiyelerine ve piyasa nakit koruma (Cash Defense) oranına göre dağıtır.

    Args:
        budget: Kullanılabilir toplam nakit bütçe (TL)
        recommendations: Analiz sonuçları listesi
        max_stocks: Maksimum kaç hisseye yatırım yapılacak
        cash_reserve_pct: Savunma amacıyla nakitte korunacak oran (0.0 - 1.0)
                          Örn: 0.40 -> Bütçenin %40'ı nakitte korunur, %60'ı yatırıma gider.
                          1.00 -> %100 Nakitte kal.

    Returns:
        tuple: (portfolio, remaining_budget)
    """
    budget = _safe_float(budget)
    cash_reserve_pct = max(0.0, min(1.0, _safe_float(cash_reserve_pct, 0.0)))

    try:
        max_stocks = int(max_stocks)
    except (TypeError, ValueError):
        max_stocks = 0

    if budget <= 0 or max_stocks <= 0 or not recommendations or cash_reserve_pct >= 1.0:
        return [], max(budget, 0.0)

    # Yatırıma ayrılan efektif bütçe ve dokunulmaz nakit rezervi
    investable_budget = budget * (1.0 - cash_reserve_pct)
    reserved_cash = budget * cash_reserve_pct

    if investable_budget <= 0:
        return [], max(budget, 0.0)

    candidates = []
    for pick in recommendations:
        price = _safe_float(pick.get('Fiyat'))
        if price <= 0 or price > investable_budget:
            continue

        candidates.append({
            'pick': pick,
            'price': price,
            'score': max(_safe_float(pick.get('Skor'), 1.0), 1.0),
            'rsi': _safe_float(pick.get('RSI'), 50.0)
        })

    if not candidates:
        return [], budget

    candidates.sort(key=lambda item: _rank_candidate(item['pick']))
    selected = candidates[:max_stocks]

    total_score = sum(item['score'] for item in selected)
    remaining_investable = investable_budget
    quantities = {item['pick']['Hisse']: 0 for item in selected}

    # İlk geçiş: teknik skora göre hedef bütçe ayır.
    for item in selected:
        target_budget = investable_budget * (item['score'] / total_score)
        quantity = int(target_budget // item['price'])
        if quantity <= 0 and item['price'] <= remaining_investable:
            quantity = 1

        cost = quantity * item['price']
        if cost <= remaining_investable:
            quantities[item['pick']['Hisse']] += quantity
            remaining_investable -= cost

    # İkinci geçiş: yuvarlamadan kalan yatırılabilir nakdi en güçlü adaylarda değerlendir.
    while True:
        affordable = [
            item for item in selected
            if item['price'] <= remaining_investable
        ]
        if not affordable:
            break

        affordable.sort(key=lambda item: (-item['score'], item['rsi'], item['price']))
        best = affordable[0]
        quantities[best['pick']['Hisse']] += 1
        remaining_investable -= best['price']

    portfolio = []
    total_spent = 0.0
    for item in selected:
        pick = item['pick']
        quantity = quantities[pick['Hisse']]
        if quantity <= 0:
            continue

        cost = quantity * item['price']
        total_spent += cost
        portfolio.append(_build_portfolio_item(pick, quantity, cost))

    remaining_total_budget = budget - total_spent
    return portfolio, max(remaining_total_budget, 0.0)

