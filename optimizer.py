def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _asset_unit(asset_type, fallback_unit=None):
    if fallback_unit:
        return fallback_unit
    return 'gram' if asset_type == 'METAL' else 'adet'


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


def allocate_budget(budget, recommendations, max_stocks=3):
    """
    Bütçeyi en iyi tavsiyelere göre dağıtır.
    Hem hisseleri hem de değerli metalleri (altın/gümüş) destekler.

    Args:
        budget: Kullanılabilir bütçe (TL)
        recommendations: Analiz sonuçları listesi
        max_stocks: Maksimum kaç asset'e yatırım yapılacak

    Returns:
        tuple: (portfolio, remaining_budget)
    """
    budget = _safe_float(budget)

    try:
        max_stocks = int(max_stocks)
    except (TypeError, ValueError):
        max_stocks = 0

    if budget <= 0 or max_stocks <= 0 or not recommendations:
        return [], max(budget, 0)

    candidates = []
    for pick in recommendations:
        price = _safe_float(pick.get('Fiyat'))
        if price <= 0 or price > budget:
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
    remaining_budget = budget
    quantities = {item['pick']['Hisse']: 0 for item in selected}

    # İlk geçiş: eşit dağıtım yerine teknik skora göre hedef bütçe ayır.
    for item in selected:
        target_budget = budget * (item['score'] / total_score)
        quantity = int(target_budget // item['price'])
        if quantity <= 0 and item['price'] <= remaining_budget:
            quantity = 1

        cost = quantity * item['price']
        if cost <= remaining_budget:
            quantities[item['pick']['Hisse']] += quantity
            remaining_budget -= cost

    # İkinci geçiş: yuvarlamadan kalan nakdi en güçlü/ucuz adaylarda değerlendir.
    while True:
        affordable = [
            item for item in selected
            if item['price'] <= remaining_budget
        ]
        if not affordable:
            break

        affordable.sort(key=lambda item: (-item['score'], item['rsi'], item['price']))
        best = affordable[0]
        quantities[best['pick']['Hisse']] += 1
        remaining_budget -= best['price']

    portfolio = []
    for item in selected:
        pick = item['pick']
        quantity = quantities[pick['Hisse']]
        if quantity <= 0:
            continue

        cost = quantity * item['price']
        portfolio.append(_build_portfolio_item(pick, quantity, cost))

    return portfolio, max(remaining_budget, 0)
