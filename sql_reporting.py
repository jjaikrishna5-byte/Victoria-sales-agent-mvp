"""Read-only, aggregated Victoria SQL Server reporting access."""
import os
from decimal import Decimal
from contextlib import contextmanager
import pyodbc

@contextmanager
def connection():
    password = os.environ.get('VICTORIA_SQL_PASSWORD')
    if not password:
        raise RuntimeError('VICTORIA_SQL_PASSWORD is not set in this terminal')
    settings = ('DRIVER={ODBC Driver 18 for SQL Server};'
                f'SERVER={os.getenv("VICTORIA_SQL_SERVER", "localhost")};'
                f'DATABASE={os.getenv("VICTORIA_SQL_DATABASE", "Victoria_AI_Dev")};'
                f'UID={os.getenv("VICTORIA_SQL_USER", "victoria_reporting_login")};'
                'Encrypt=yes;TrustServerCertificate=yes;')
    conn = pyodbc.connect(settings, pwd=password, timeout=10)
    try:
        yield conn
    finally:
        conn.close()

def fetch(sql, params=()):
    with connection() as conn:
        cursor = conn.cursor()
    
        cursor.execute(sql, tuple(params))
        columns = [c[0] for c in cursor.description]
        result = []
        for values in cursor.fetchall():
            record = dict(zip(columns, values))
            for key, value in record.items():
                if isinstance(value, Decimal):
                    record[key] = str(value)
            result.append(record)
        return result

# This is an explicit allowlist: never interpolate user-supplied table/column names.
VIEWS = {
    'transactions': ('reporting.SalesMonthlySummary', 'TransactionCount'),
    'devices': ('reporting.DeviceMonthlySummary', 'TotalQuantity'),
    'products': ('reporting.ProductMonthlySummary', 'TotalQuantity'),
    'brands': ('reporting.BrandMonthlySummary', 'TotalQuantity'),
    'branches': ('reporting.BranchMonthlySummary', 'TransactionCount'),
    'regions': ('reporting.RegionMonthlySummary', 'TransactionCount'),
}

def monthly_rows(kind, periods=None):
    if kind not in VIEWS:
        raise ValueError('Unsupported reporting view')
    view, _ = VIEWS[kind]
    sql = f'SELECT * FROM {view}'
    parameters = []
    if periods:
        clauses = []
        for period in periods[:2]:
            year, month = [int(v) for v in period.split('-')]
            if not (2020 <= year <= 2100 and 1 <= month <= 12):
                raise ValueError('Invalid period')
            clauses.append('(SalesYear = ? AND SalesMonth = ?)')
            parameters.extend((year, month))
        sql += ' WHERE ' + ' OR '.join(clauses)
    return fetch(sql, parameters)

def get_real_sales_summary():
    return {
        'mode': 'real_database', 'status': 'preliminary',
        'source': 'Victoria_AI_Dev',
        'data': monthly_rows('transactions'),
    }

def get_dashboard_data(period=None):
    # Only aggregates from preapproved views. No customer or sales-team identity records.
    months = fetch('''
        SELECT SalesYear, SalesMonth,
               SUM(TransactionCount) AS TransactionHeaders
        FROM reporting.SalesMonthlySummary
        GROUP BY SalesYear, SalesMonth
        ORDER BY SalesYear, SalesMonth
    ''')
    available = [f"{int(r['SalesYear'])}-{int(r['SalesMonth']):02d}" for r in months]
    if not available:
        return {'mode': 'real_database', 'months': [], 'has_data': False}
    period = period or available[-1]
    if period not in available:
        return {'mode': 'real_database', 'months': available, 'period': period, 'has_data': False}
    year, month = map(int, period.split('-'))
    counts = fetch('''
        SELECT InvType, DocStatus, DeleteStatus,
               SUM(TransactionCount) AS TransactionHeaders
        FROM reporting.SalesMonthlySummary
        WHERE SalesYear = ? AND SalesMonth = ?
        GROUP BY InvType, DocStatus, DeleteStatus
        ORDER BY TransactionHeaders DESC
    ''', (year, month))
    devices = fetch('''
        SELECT TOP (10) Brand, PartName,
               SUM(TotalQuantity) AS RecordedQuantity,
               SUM(DetailLineCount) AS DetailLines
        FROM reporting.DeviceMonthlySummary
        WHERE SalesYear = ? AND SalesMonth = ?
        GROUP BY Brand, PartName
        ORDER BY RecordedQuantity DESC
    ''', (year, month))
    regions = fetch('''
        SELECT TOP (12) Region, SUM(TransactionCount) AS TransactionHeaders
        FROM reporting.RegionMonthlySummary
        WHERE SalesYear = ? AND SalesMonth = ?
        GROUP BY Region
        ORDER BY TransactionHeaders DESC
    ''', (year, month))
    return {
        'mode': 'real_database', 'status': 'preliminary',
        'months': available, 'period': period, 'has_data': True,
        'transaction_headers': sum(int(r['TransactionHeaders']) for r in counts),
        'categories': counts, 'devices': devices, 'regions': regions,
        'trend': [{'period': f"{int(r['SalesYear'])}-{int(r['SalesMonth']):02d}",
                   'transaction_headers': int(r['TransactionHeaders'])} for r in months],
        'disclaimer': 'Transaction headers are not verified sales. Device quantities include all document statuses. Regions may be unmapped.'
    }
