"""
Victoria AI - Historical Country Reporting

Data source:
    Victoria_AI_Dev

Transaction tables:
    dbo.STxnMst_01 through dbo.STxnMst_12

Country source:
    country_mapping.py

IMPORTANT:
Country assignments are preliminary.
Transaction counts are not verified sales.
"""

import re
from collections import defaultdict

from sql_reporting import fetch
from country_mapping import get_country, get_all_countries


# ==================================================
# 1. HISTORICAL TRANSACTION QUERY
# ==================================================

def get_historical_transactions():
    """
    Aggregate transaction headers by subscription,
    year, and month.

    Uses only the 12 known monthly transaction tables.
    Does not retrieve customer information.
    """

    monthly_queries = []

    for month in range(1, 13):

        table_name = f"dbo.STxnMst_{month:02d}"

        monthly_queries.append(
            f"""
            SELECT
                SubscID,
                DocDate,
                InvType,
                DocStatus,
                DeleteStatus
            FROM {table_name}
            WHERE DocDate IS NOT NULL
            """
        )

    combined_query = "\nUNION ALL\n".join(monthly_queries)

    sql = f"""
        WITH HistoricalTransactions AS (
            {combined_query}
        )

        SELECT
            SubscID,
            YEAR(DocDate) AS SalesYear,
            MONTH(DocDate) AS SalesMonth,

            COUNT_BIG(*) AS TransactionHeaders,

            SUM(
                CASE
                    WHEN InvType = 'R'
                     AND DocStatus = 'A'
                     AND DeleteStatus = 'N'
                    THEN CAST(1 AS BIGINT)
                    ELSE CAST(0 AS BIGINT)
                END
            ) AS CandidateApprovedHeaders

        FROM HistoricalTransactions

        GROUP BY
            SubscID,
            YEAR(DocDate),
            MONTH(DocDate)
    """

    return fetch(sql)


# ==================================================
# 2. COUNTRY REPORTING
# ==================================================

def get_country_sales_report(year=None, month=None, country=None):
    """
    Return preliminary country-attributed
    transaction counts.

    Supports:
        All available years
        One year
        One month in a year
        One country
        All mapped countries

    Does not claim transactions are verified sales.
    """

    if year is not None:
        year = int(year)

    if month is not None:
        month = int(month)

        if not 1 <= month <= 12:
            raise ValueError("Month must be between 1 and 12")

        if year is None:
            raise ValueError("Month filter requires a year")

    country_filter = (
        str(country).strip().upper()
        if country
        else None
    )

    grouped = defaultdict(
        lambda: {
            "transaction_headers": 0,
            "candidate_approved_headers": 0,
        }
    )

    rows = get_historical_transactions()

    available_years = set()

    for row in rows:

        sales_year = int(row["SalesYear"])
        sales_month = int(row["SalesMonth"])

        available_years.add(sales_year)

        if year is not None and sales_year != year:
            continue

        if month is not None and sales_month != month:
            continue

        mapped_country = get_country(
            row.get("SubscID")
        )

        if (
            country_filter is not None
            and mapped_country != country_filter
        ):
            continue

        key = (
            mapped_country,
            sales_year,
            sales_month,
        )

        grouped[key]["transaction_headers"] += int(
            row["TransactionHeaders"]
        )

        grouped[key]["candidate_approved_headers"] += int(
            row["CandidateApprovedHeaders"] or 0
        )

    result = []

    for key, values in sorted(grouped.items()):

        mapped_country, sales_year, sales_month = key

        result.append({
            "country": mapped_country,
            "year": sales_year,
            "month": sales_month,
            **values,
        })

    return {
        "mode": "real_database",
        "status": "preliminary",
        "country_mapping": "unverified",
        "available_years": sorted(available_years),
        "registered_countries": get_all_countries(),
        "data": result,
        "disclaimer": (
            "Country mappings are preliminary. "
            "Transaction headers include different document "
            "types and statuses. Candidate approved headers "
            "use R/A/N as a provisional classification. "
            "Neither metric represents verified completed sales."
        ),
    }


# ==================================================
# 3. COUNTRY SUMMARY
# ==================================================

def get_country_summary(year=None):
    """
    Summarize transaction headers by country.

    UNMAPPED is preserved as a separate category.
    """

    report = get_country_sales_report(year=year)

    totals = defaultdict(
        lambda: {
            "transaction_headers": 0,
            "candidate_approved_headers": 0,
        }
    )

    for row in report["data"]:

        country = row["country"]

        totals[country]["transaction_headers"] += (
            row["transaction_headers"]
        )

        totals[country]["candidate_approved_headers"] += (
            row["candidate_approved_headers"]
        )

    return {
        "year": year,
        "status": "preliminary",
        "data": [
            {
                "country": country,
                **values,
            }
            for country, values in sorted(totals.items())
        ],
        "disclaimer": report["disclaimer"],
    }


# ==================================================
# 4. COUNTRY QUESTION HANDLER
# ==================================================

def answer_country_question(question):
    """
    Handle country-related questions.

    Examples:
        What are all the countries?
        Show country transactions in 2025
        Kenya transactions in September 2026
        Compare country transactions in 2025 and 2026
    """

    question_lower = question.lower()

    countries = get_all_countries()

    country_mentions = [
        country
        for country in countries
        if re.search(
            r"\b" + re.escape(country) + r"\b",
            question,
            re.I,
        )
    ]

    # Country directory questions
    if (
        re.search(
            r"\b(list|which|what|name|all)\b",
            question_lower,
        )
        and re.search(
            r"\b(countries|country)\b",
            question_lower,
        )
        and not re.search(
            r"\b(sales|transactions|revenue|sold)\b",
            question_lower,
        )
    ):

        return (
            "## Countries registered in Victoria ERP\n\n"
            + "\n".join(
                f"- {country.title()}"
                for country in countries
            )
            + "\n\n"
            "These are registered countries, "
            "not necessarily countries with recorded sales."
        )

    years = sorted({
        int(y)
        for y in re.findall(r"\b20\d{2}\b", question)
    })

    # Explicitly reject revenue questions until
    # financial definitions are verified.
    if re.search(
        r"\b(revenue|turnover|profit|sales value)\b",
        question_lower,
    ):
        return (
            "Verified country revenue is not available yet. "
            "We can currently report preliminary "
            "country-attributed transaction counts."
        )

    from agent import detect_months

    periods = detect_months(question)

    # Specific country + specific month
    if len(country_mentions) == 1 and len(periods) == 1:

        year, month = map(int, periods[0].split("-"))

        report = get_country_sales_report(
            year=year,
            month=month,
            country=country_mentions[0],
        )

        total = sum(
            row["transaction_headers"]
            for row in report["data"]
        )

        return (
            f"## {country_mentions[0].title()} "
            f"transactions in {periods[0]}\n\n"
            f"**Recorded transaction headers:** {total:,}\n\n"
            "Country attribution is preliminary. "
            "These are not verified completed sales."
        )

    if periods:
        return (
            "For month-specific country reporting, "
            "please specify one month and one country."
        )

    if len(years) > 2:
        return (
            "Please specify up to two years for "
            "a country transaction comparison."
        )

    # Country summary for each requested year,
    # or all years when none is specified.
    report_years = years if years else [None]

    output = ["## Country Transaction Report\n"]

    for selected_year in report_years:

        summary = get_country_summary(
            year=selected_year
        )

        title = (
            str(selected_year)
            if selected_year
            else "All available years"
        )

        output.append(f"### {title}\n")

        output.append(
            "| Country | Transaction headers |"
        )
        output.append(
            "|---|---:|"
        )

        for row in summary["data"]:

            output.append(
                f"| {row['country']} | "
                f"{row['transaction_headers']:,} |"
            )

        output.append("")

    output.append(
        "**Note:** Country attribution is preliminary. "
        "UNMAPPED transactions remain visible. "
        "These figures are not verified completed sales."
    )

    return "\n".join(output)