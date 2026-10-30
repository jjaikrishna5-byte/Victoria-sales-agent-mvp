"""
Victoria Sales Agent
Read-only, aggregated SQL Server reporting.

Supports:
- Local SQL Server using Windows Authentication
- SQL Server using SQL Authentication
- AWS-hosted SQL Server with secure configuration

Connection is configured using:
SQLSERVER_CONNECTION_STRING
"""

import os
from decimal import Decimal
from contextlib import contextmanager

import pyodbc


# ==========================================================
# 1. DATABASE CONNECTION
# ==========================================================

@contextmanager
def connection():
    """
    Connect to Victoria_AI_Dev using SQLSERVER_CONNECTION_STRING.

    Example for local Windows Authentication:

    DRIVER={ODBC Driver 18 for SQL Server};
    SERVER=localhost;
    DATABASE=Victoria_AI_Dev;
    Trusted_Connection=yes;
    Encrypt=yes;
    TrustServerCertificate=yes;

    Use a dedicated read-only database identity.
    """

    connection_string = os.environ.get(
        "SQLSERVER_CONNECTION_STRING"
    )

    if not connection_string:
        raise RuntimeError(
            "SQLSERVER_CONNECTION_STRING is not configured. "
            "Please configure it before starting Victoria."
        )

    conn = None

    try:
        conn = pyodbc.connect(
            connection_string,
            timeout=10,
            autocommit=False
        )

        # Require the database to accept only read operations
        # within this connection's transaction.
        conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")

        yield conn

    finally:
        if conn is not None:
            try:
                conn.rollback()
            finally:
                conn.close()


# ==========================================================
# 2. SQL QUERY EXECUTION
# ==========================================================

def fetch(sql, params=()):
    """
    Execute predefined reporting queries.

    User questions must never be executed directly as SQL.
    """

    with connection() as conn:

        cursor = conn.cursor()

        try:
            cursor.execute(sql, tuple(params))

            if cursor.description is None:
                raise RuntimeError(
                    "The reporting query did not return a result set."
                )

            columns = [
                column[0]
                for column in cursor.description
            ]

            result = []

            for values in cursor.fetchall():

                record = dict(zip(columns, values))

                for key, value in record.items():

                    if isinstance(value, Decimal):
                        record[key] = str(value)

                result.append(record)

            return result

        finally:
            cursor.close()


# ==========================================================
# 3. APPROVED REPORTING VIEWS
# ==========================================================

# Explicit allowlist.
# Never interpolate user-provided table or column names.

VIEWS = {

    "transactions": (
        "reporting.SalesMonthlySummary",
        "TransactionCount"
    ),

    "devices": (
        "reporting.DeviceMonthlySummary",
        "TotalQuantity"
    ),

    "products": (
        "reporting.ProductMonthlySummary",
        "TotalQuantity"
    ),

    "brands": (
        "reporting.BrandMonthlySummary",
        "TotalQuantity"
    ),

    "branches": (
        "reporting.BranchMonthlySummary",
        "TransactionCount"
    ),

    "regions": (
        "reporting.RegionMonthlySummary",
        "TransactionCount"
    ),
}


# ==========================================================
# 4. MONTHLY REPORTING DATA
# ==========================================================

def monthly_rows(kind, periods=None):
    """
    Retrieve monthly data from approved reporting views.

    Maximum comparison periods: 2
    """

    if kind not in VIEWS:
        raise ValueError(
            "Unsupported reporting view"
        )

    view, _ = VIEWS[kind]

    sql = f"SELECT * FROM {view}"

    parameters = []

    if periods:

        clauses = []

        for period in periods[:2]:

            try:
                year, month = [
                    int(value)
                    for value in period.split("-")
                ]

            except (ValueError, AttributeError):
                raise ValueError(
                    "Invalid period format. Use YYYY-MM."
                )

            if not (
                2020 <= year <= 2100
                and 1 <= month <= 12
            ):
                raise ValueError(
                    "Invalid reporting period"
                )

            clauses.append(
                "(SalesYear = ? AND SalesMonth = ?)"
            )

            parameters.extend(
                (year, month)
            )

        sql += " WHERE " + " OR ".join(clauses)

    return fetch(
        sql,
        parameters
    )


# ==========================================================
# 5. REAL SALES SUMMARY
# ==========================================================

def get_real_sales_summary():
    """
    Retrieve actual aggregated transaction data.

    These figures are preliminary transaction counts,
    not necessarily verified completed sales.
    """

    return {

        "mode": "real_database",

        "status": "preliminary",

        "source": "Victoria_AI_Dev",

        "data": monthly_rows(
            "transactions"
        )
    }


# ==========================================================
# 6. DASHBOARD DATA
# ==========================================================

def get_dashboard_data(period=None):
    """
    Retrieve dashboard metrics from approved SQL views.

    Includes:
    - Available months
    - Transaction headers
    - Document categories
    - Top devices
    - Regional transaction counts
    - Monthly transaction trends
    """

    # ------------------------------------------------------
    # AVAILABLE MONTHS
    # ------------------------------------------------------

    months = fetch(
        """
        SELECT
            SalesYear,
            SalesMonth,
            SUM(TransactionCount) AS TransactionHeaders

        FROM reporting.SalesMonthlySummary

        GROUP BY
            SalesYear,
            SalesMonth

        ORDER BY
            SalesYear,
            SalesMonth
        """
    )

    available = [

        f"{int(row['SalesYear'])}-{int(row['SalesMonth']):02d}"

        for row in months
    ]

    if not available:

        return {

            "mode": "real_database",

            "months": [],

            "has_data": False
        }

    # ------------------------------------------------------
    # SELECT REPORTING PERIOD
    # ------------------------------------------------------

    period = period or available[-1]

    if period not in available:

        return {

            "mode": "real_database",

            "months": available,

            "period": period,

            "has_data": False
        }

    year, month = map(
        int,
        period.split("-")
    )

    # ------------------------------------------------------
    # TRANSACTION COUNTS
    # ------------------------------------------------------

    counts = fetch(
        """
        SELECT
            InvType,
            DocStatus,
            DeleteStatus,

            SUM(TransactionCount)
                AS TransactionHeaders

        FROM reporting.SalesMonthlySummary

        WHERE
            SalesYear = ?
            AND SalesMonth = ?

        GROUP BY
            InvType,
            DocStatus,
            DeleteStatus

        ORDER BY
            TransactionHeaders DESC
        """,
        (year, month)
    )

    # ------------------------------------------------------
    # TOP DEVICES
    # ------------------------------------------------------

    devices = fetch(
        """
        SELECT TOP (10)

            Brand,
            PartName,

            SUM(TotalQuantity)
                AS RecordedQuantity,

            SUM(DetailLineCount)
                AS DetailLines

        FROM reporting.DeviceMonthlySummary

        WHERE
            SalesYear = ?
            AND SalesMonth = ?

        GROUP BY
            Brand,
            PartName

        ORDER BY
            RecordedQuantity DESC
        """,
        (year, month)
    )

    # ------------------------------------------------------
    # REGIONAL REPORTING
    # ------------------------------------------------------

    regions = fetch(
        """
        SELECT TOP (12)

            Region,

            SUM(TransactionCount)
                AS TransactionHeaders

        FROM reporting.RegionMonthlySummary

        WHERE
            SalesYear = ?
            AND SalesMonth = ?

        GROUP BY
            Region

        ORDER BY
            TransactionHeaders DESC
        """,
        (year, month)
    )

    # ------------------------------------------------------
    # TOTAL TRANSACTION HEADERS
    # ------------------------------------------------------

    transaction_headers = sum(

        int(row["TransactionHeaders"])

        for row in counts

    )

    # ------------------------------------------------------
    # MONTHLY TREND
    # ------------------------------------------------------

    trend = [

        {

            "period": (
                f"{int(row['SalesYear'])}-"
                f"{int(row['SalesMonth']):02d}"
            ),

            "transaction_headers": int(
                row["TransactionHeaders"]
            )
        }

        for row in months
    ]

    # ------------------------------------------------------
    # FINAL DASHBOARD RESPONSE
    # ------------------------------------------------------

    return {

        "mode": "real_database",

        "status": "preliminary",

        "source": "Victoria_AI_Dev",

        "months": available,

        "period": period,

        "has_data": True,

        "transaction_headers": transaction_headers,

        "categories": counts,

        "devices": devices,

        "regions": regions,

        "trend": trend,

        "disclaimer": (
            "Transaction headers are not verified sales. "
            "Device quantities include all document statuses. "
            "Regions may be unmapped."
        )
    }


# ==========================================================
# 7. DATABASE CONNECTION HEALTH CHECK
# ==========================================================

def check_database_connection():
    """
    Verify that SQL Server connectivity is working.

    This function does not modify database records.
    """

    try:

        with connection() as conn:

            cursor = conn.cursor()

            cursor.execute(
                "SELECT DB_NAME()"
            )

            database_name = cursor.fetchone()[0]

            cursor.close()

            return {

                "status": "connected",

                "database": database_name,

                "reporting": "available"
            }

    except pyodbc.Error:

        return {

            "status": "disconnected",

            "database": None,

            "reporting": "unavailable"
        }