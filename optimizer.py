def allocate_budget(budget, recommendations, max_stocks=3):
    # En yüksek skorlu olanlardan maksimum 'max_stocks' kadar hisse almayı dene
    top_picks = recommendations[:max_stocks]
    if not top_picks:
        return [], budget
        
    # Bütçeyi eşit böl
    budget_per_stock = budget / len(top_picks)
    portfolio = []
    remaining_budget = budget
    
    for pick in top_picks:
        price = pick['Fiyat']
        # Kesirli lot olmaz, tam sayı kısmını alıyoruz
        lots = int(budget_per_stock // price)
        
        if lots > 0:
            cost = lots * price
            remaining_budget -= cost
            portfolio.append({
                'Hisse': pick['Hisse'],
                'Fiyat': price,
                'Lot': lots,
                'Toplam Maliyet': cost,
                'Nedenler': pick['Nedenler']
            })
            
    return portfolio, remaining_budget
