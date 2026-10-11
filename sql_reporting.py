
import os
from decimal import Decimal

import pyodbc


def get_real_sales_summary():
    password = os.getenv("VICTORIA_SQL_PASSWORD")

    if not password:
        raise RuntimeError("SQL reporting password is not configured")

    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=Victoria_AI_Dev;"
        "UID=victoria_reporting_login;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )

    connection = pyodbc.connect(
        connection_string,
        pwd=password,
        timeout=10,
    )

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                SalesYear,
                SalesMonth,
                InvType,
                DocStatus,
                DeleteStatus,
                TxnCurrency,
                TransactionCount,
                TotalNetValue
            FROM reporting.SalesMonthlySummary
            ORDER BY
                SalesYear DESC,
                SalesMonth DESC,
                TransactionCount DESC
        """)

        columns = [column[0] for column in cursor.description]

        results = []

        for row in cursor.fetchall():
            record = dict(zip(columns, row))

            for key, value in record.items():
                if isinstance(value, Decimal):
                    record[key] = str(value)

            results.append(record)

        return {
            "mode": "real_database",
            "status": "preliminary",
            "source": "Victoria_AI_Dev",
            "data": results,
        }

    finally:
        connection.close()
