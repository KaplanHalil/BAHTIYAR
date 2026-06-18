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
    top_picks = recommendations[:max_stocks]
    if not top_picks:
        return [], budget
        
    # Bütçeyi eşit böl
    budget_per_asset = budget / len(top_picks)
    portfolio = []
    remaining_budget = budget
    
    for pick in top_picks:
        price = pick['Fiyat']
        asset_type = pick.get('AssetType', 'HISSE')
        
        # Hisse: adet cinsinden lot hesapla
        if asset_type == 'HISSE':
            lots = int(budget_per_asset // price)
            
            if lots > 0:
                cost = lots * price
                remaining_budget -= cost
                portfolio.append({
                    'Hisse': pick['Hisse'],
                    'Fiyat': price,
                    'Lot': lots,
                    'Toplam Maliyet': cost,
                    'Nedenler': pick['Nedenler'],
                    'AssetType': 'HISSE',
                    'Unit': 'adet'
                })
        
        # Değerli Metal (Altın/Gümüş): gram cinsinden hesapla
        elif asset_type == 'METAL':
            grams = int(budget_per_asset // price)
            
            if grams > 0:
                cost = grams * price
                remaining_budget -= cost
                portfolio.append({
                    'Hisse': pick['Hisse'],
                    'Fiyat': price,
                    'Lot': grams,  # Gram miktarı
                    'Toplam Maliyet': cost,
                    'Nedenler': pick['Nedenler'],
                    'AssetType': 'METAL',
                    'Unit': 'gram',
                    'Display': pick.get('Display', pick['Hisse'])
                })
            
    return portfolio, remaining_budget
