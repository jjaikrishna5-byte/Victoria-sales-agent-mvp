import re
from datetime import date
from database import get_connection


def month_bounds(month):
    if not re.fullmatch(r'20\d{2}-(0[1-9]|1[0-2])', month):
        raise ValueError('Use a valid month in YYYY-MM format.')
    first = date.fromisoformat(month + '-01')
    if first.month == 12:
        nxt = date(first.year+1,1,1)
    else:
        nxt = date(first.year,first.month+1,1)
    previous = date(first.year-1,12,1) if first.month == 1 else date(first.year,first.month-1,1)
    return first.isoformat(), nxt.isoformat(), previous.isoformat()


def get_sales_overview(month='2026-09'):
    start, end, previous = month_bounds(month)
    with get_connection() as c:
        current = c.execute('''SELECT COUNT(*) lines, COUNT(DISTINCT order_id) orders,
            COALESCE(SUM(quantity),0) units, COALESCE(SUM(quantity*unit_price_cents),0) cents
            FROM sales WHERE sale_date >= ? AND sale_date < ?''',(start,end)).fetchone()
        prior = c.execute('''SELECT COUNT(*) lines,COALESCE(SUM(quantity*unit_price_cents),0) cents
            FROM sales WHERE sale_date >= ? AND sale_date < ?''',(previous,start)).fetchone()
        markets = c.execute('''SELECT market, SUM(quantity) units, SUM(quantity*unit_price_cents) cents
            FROM sales WHERE sale_date >= ? AND sale_date < ? GROUP BY market ORDER BY cents DESC''',(start,end)).fetchall()
        products = c.execute('''SELECT product, category, SUM(quantity) units, SUM(quantity*unit_price_cents) cents
            FROM sales WHERE sale_date >= ? AND sale_date < ? GROUP BY product,category ORDER BY cents DESC''',(start,end)).fetchall()
    cents, orders, units = current['cents'], current['orders'], current['units']
    growth = round((cents / prior['cents'] - 1)*100, 2) if current['lines'] and prior['cents'] else None
    return {
      'mode': 'sample_database', 'month': month, 'currency':'USD', 'has_data': bool(current['lines']),
      'summary': {'revenue': round(cents/100,2), 'orders': orders, 'units_sold': units,
                  'average_order_value': round(cents / orders / 100,2) if orders else None,
                  'revenue_growth_percent':growth, 'previous_month_has_data':bool(prior['lines'])},
      'markets':[{'market':r['market'],'revenue':round(r['cents']/100,2),'units_sold':r['units'],
                  'revenue_share_percent':round(r['cents']/cents*100,2) if cents else None} for r in markets],
      'products':[{'product':r['product'],'category':r['category'],'revenue':round(r['cents']/100,2),
                   'units_sold':r['units'],'unit_share_percent':round(r['units']/units*100,2) if units else None} for r in products]
    }


def get_available_months():
    with get_connection() as c:
        rows=c.execute("SELECT DISTINCT substr(sale_date,1,7) AS month FROM sales ORDER BY month").fetchall()
    return [r['month'] for r in rows]


def get_trend(months=None):
    available=get_available_months()
    months=months or available
    return [{'month':m,'revenue':get_sales_overview(m)['summary']['revenue'],
             'orders':get_sales_overview(m)['summary']['orders']} for m in months]


def compare_months(first,second):
    a,b=get_sales_overview(first),get_sales_overview(second)
    if not a['has_data'] or not b['has_data']:
        return {'has_data':False,'months':[first,second], 'message':'One or both months have no sales records.'}
    x=a['summary']['revenue']; y=b['summary']['revenue']
    return {'has_data':True,'first':a,'second':b,'difference':round(y-x,2),
            'percent_change':round((y/x-1)*100,2) if x else None}
