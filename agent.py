"""
VICTORIA SALES INTELLIGENCE AGENT
=================================

Real SQL Server reporting assistant.

Features:
- Country directory
- Country-wise transaction reporting
- Historical country comparisons
- Transaction reporting
- Monthly comparisons
- Device performance
- Samsung model rankings
- Brand reporting
- Branch reporting
- Regional reporting
- Preliminary transaction values
- Unsupported question detection

Security:
- Uses approved reporting functions
- Does not generate arbitrary SQL from user questions
- Does not execute user-provided SQL
- Does not claim preliminary figures are verified sales

Database:
Victoria_AI_Dev
"""

import re
from collections import defaultdict
from decimal import Decimal

from sql_reporting import monthly_rows, get_dashboard_data
from sales_service import get_sales_overview, get_available_months

from country_mapping import get_all_countries
from country_reporting import (
    answer_country_question as handle_country_question,
)


# ==========================================================
# 1. MONTH CONFIGURATION
# ==========================================================

MONTH_NAMES = {
    name: index
    for index, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        1,
    )
}

MONTH_ALIASES = {
    name[:3]: number
    for name, number in MONTH_NAMES.items()
}

MONTH_ALIASES.update(MONTH_NAMES)

MONTH_PATTERN = (
    r"\b("
    + "|".join(
        sorted(
            MONTH_ALIASES,
            key=len,
            reverse=True,
        )
    )
    + r")\b"
)

PERIOD_PATTERN = re.compile(
    r"20\d{2}-(?:0[1-9]|1[0-2])"
)


# ==========================================================
# 2. MONTH DETECTION
# ==========================================================

def detect_months(question):
    """
    Detect reporting periods.

    Supports:
    - September 2026
    - 2026-09
    - 2026 September
    - August and September 2026
    - March 2026 vs April 2026
    """

    found = []

    # YYYY-MM
    for match in re.finditer(
        r"\b(20\d{2}-(?:0[1-9]|1[0-2]))\b",
        question,
    ):
        found.append(
            (match.start(), match.group(1))
        )

    # September 2026
    for match in re.finditer(
        MONTH_PATTERN + r"\s+(20\d{2})\b",
        question,
        re.I,
    ):
        month = MONTH_ALIASES[
            match.group(1).lower()
        ]

        found.append(
            (
                match.start(),
                f"{match.group(2)}-{month:02d}",
            )
        )

    # 2026 September
    for match in re.finditer(
        r"\b(20\d{2})\s+" + MONTH_PATTERN,
        question,
        re.I,
    ):
        month = MONTH_ALIASES[
            match.group(2).lower()
        ]

        found.append(
            (
                match.start(),
                f"{match.group(1)}-{month:02d}",
            )
        )

    # August and September 2026
    shared = re.search(
        MONTH_PATTERN
        + r"\s+(?:and|to|vs\.?|versus)\s+"
        + MONTH_PATTERN
        + r"\s+(20\d{2})\b",
        question,
        re.I,
    )

    if shared:
        year = shared.group(3)

        for index in (1, 2):
            month = MONTH_ALIASES[
                shared.group(index).lower()
            ]

            found.append(
                (
                    shared.start(index),
                    f"{year}-{month:02d}",
                )
            )

    found.sort(
        key=lambda item: item[0]
    )

    return list(
        dict.fromkeys(
            period
            for _, period in found
        )
    )


# ==========================================================
# 3. REPORTING PERIOD RESOLUTION
# ==========================================================

def available_periods():
    """
    Get available reporting periods from SQL Server.
    """

    dashboard = get_dashboard_data()

    candidates = list(
        dashboard.get("months") or []
    )

    if dashboard.get("period"):
        candidates.append(
            dashboard["period"]
        )

    valid = {
        period
        for period in candidates
        if isinstance(period, str)
        and PERIOD_PATTERN.fullmatch(period)
    }

    return sorted(valid)


def resolve_periods(question):
    """
    Resolve reporting periods requested by the user.

    Never replace an explicitly requested period
    with another available month.
    """

    explicit = detect_months(question)

    if explicit:
        return explicit, None

    available = available_periods()

    if not available:
        return [], (
            "No reporting periods are available."
        )

    matches = list(
        re.finditer(
            MONTH_PATTERN,
            question,
            re.I,
        )
    )

    if matches:
        resolved = []

        for match in matches:
            month_number = MONTH_ALIASES[
                match.group(1).lower()
            ]

            candidates = [
                period
                for period in available
                if int(period[5:7]) == month_number
            ]

            if not candidates:
                return [], (
                    "No records are available for "
                    f"{match.group(1).title()}."
                )

            if len(candidates) > 1:
                years = ", ".join(
                    sorted(
                        period[:4]
                        for period in candidates
                    )
                )

                return [], (
                    f"Which {match.group(1).title()} "
                    f"do you mean: {years}? "
                    "Please include the year."
                )

            resolved.append(
                candidates[0]
            )

        return list(
            dict.fromkeys(resolved)
        ), None

    if re.search(
        r"\b20\d{2}\b",
        question,
    ):
        return [], (
            "Please specify a month and year, "
            "such as September 2026."
        )

    return [available[-1]], None


# ==========================================================
# 4. FORMATTING HELPERS
# ==========================================================

def period_of(row):
    return (
        f"{int(row['SalesYear'])}-"
        f"{int(row['SalesMonth']):02d}"
    )


def category_of(row):
    return tuple(
        str(row.get(field) or "")
        .strip()
        .upper()
        for field in (
            "InvType",
            "DocStatus",
            "DeleteStatus",
        )
    )


def mdtable(headings, rows):
    """
    Create a Markdown table.
    """

    def safe(value):
        return (
            str(value)
            .replace("|", "\\|")
            .replace("\n", " ")
        )

    lines = [
        "| "
        + " | ".join(map(safe, headings))
        + " |",

        "| "
        + " | ".join(
            "---"
            for _ in headings
        )
        + " |",
    ]

    lines.extend(
        "| "
        + " | ".join(map(safe, row))
        + " |"
        for row in rows
    )

    return "\n".join(lines)


def num(value):
    return f"{int(value):,}"


def quantity(value):
    value = Decimal(str(value))

    if value == value.to_integral_value():
        return f"{value:,.0f}"

    return f"{value:,.2f}"


# ==========================================================
# 5. QUESTION CLASSIFICATION
# ==========================================================

def classify_question(question):
    """
    Identify the type of business question.

    Supported intents:
    - country
    - device
    - brand
    - region
    - branch
    - transaction
    - revenue
    - unsupported
    - unknown

    Recognizes country names even when the user
    does not explicitly say "country".
    """

    lower = question.lower()

    # ------------------------------------------------------
    # UNSUPPORTED BUSINESS DATA
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"profit|forecast|predict|inventory|"
        r"customer|salesperson|employee|"
        r"phone number|stock level|"
        r"gross margin|margin"
        r")\b",
        lower,
    ):
        return "unsupported"

    # ------------------------------------------------------
    # UNVERIFIED REVENUE
    # ------------------------------------------------------

    if re.search(
        r"\b(revenue|turnover)\b",
        lower,
    ):
        return "revenue"

    # ------------------------------------------------------
    # COUNTRY QUESTIONS
    # ------------------------------------------------------

    country_names = get_all_countries()

    if re.search(
        r"\b("
        r"country|countries|nation|nations"
        r")\b",
        lower,
    ):
        return "country"

    for country in country_names:
        if re.search(
            r"\b" + re.escape(country) + r"\b",
            question,
            re.I,
        ):
            return "country"

    # ------------------------------------------------------
    # BRANCH QUESTIONS
    # ------------------------------------------------------

    if re.search(
        r"\b(branch|branches)\b",
        lower,
    ):
        return "branch"

    # ------------------------------------------------------
    # REGION QUESTIONS
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"region|regions|district|districts|"
        r"geography|geographic|location|locations"
        r")\b",
        lower,
    ):
        return "region"

    # ------------------------------------------------------
    # DEVICE QUESTIONS
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"device|devices|model|models|"
        r"smartphone|smartphones|phone|phones|"
        r"samsung|product|products"
        r")\b",
        lower,
    ):
        return "device"

    # ------------------------------------------------------
    # BRAND QUESTIONS
    # ------------------------------------------------------

    if re.search(
        r"\b(brand|brands)\b",
        lower,
    ):
        return "brand"

    # ------------------------------------------------------
    # TRANSACTION QUESTIONS
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"transaction|transactions|"
        r"sales|sale|sold|invoice|invoices|"
        r"orders|order|headers|"
        r"monthly comparison"
        r")\b",
        lower,
    ):
        return "transaction"

    return "unknown"


# ==========================================================
# 6. UNSUPPORTED QUESTION HANDLING
# ==========================================================

def unsupported_answer(intent):

    if intent == "revenue":
        return (
            "Verified revenue is not available yet. "
            "Transaction values cannot be treated "
            "as confirmed sales revenue."
        )

    return (
        "That information is not available in "
        "the approved aggregated reporting views. "
        "I cannot provide an accurate answer "
        "without a verified data source."
    )


def unknown_answer():

    return (
        "I couldn't identify a supported reporting "
        "metric for that question.\n\n"
        "I can currently help with:\n\n"
        "- Monthly transaction counts\n"
        "- Transaction comparisons\n"
        "- Recorded device quantities\n"
        "- Brand quantities\n"
        "- Branch transaction counts\n"
        "- Regional transaction counts\n"
        "- Country directory\n"
        "- Preliminary country-attributed transactions\n\n"
        "Verified revenue and completed sales figures "
        "require additional business-rule validation."
    )


# ==========================================================
# 7. COUNTRY REPORTING
# ==========================================================

def answer_country_question(question):
    """
    Delegate country questions to the dedicated
    historical country-reporting module.

    This module uses preliminary subscription
    mappings and clearly labels the results.
    """

    return handle_country_question(question)


# ==========================================================
# 8. DEVICE REPORTING
# ==========================================================

def is_ranking_question(question):

    return bool(
        re.search(
            r"\b("
            r"top|highest|most|best|leading|"
            r"largest|maximum|number one|rank"
            r")\b",
            question,
            re.I,
        )
    )


def answer_device_question(question, periods):
    """
    Retrieve recorded device quantities
    from approved reporting views.

    These are not verified completed sales.
    """

    rows = monthly_rows(
        "devices",
        periods,
    )

    grouping = defaultdict(Decimal)

    samsung_only = bool(
        re.search(
            r"\bsamsung\b",
            question,
            re.I,
        )
    )

    for row in rows:

        brand = str(
            row.get("Brand") or ""
        ).strip()

        name = str(
            row.get("PartName") or ""
        ).strip()

        if samsung_only:
            if not any(
                "SAMSUNG" in value.upper()
                for value in (brand, name)
            ):
                continue

        key = (
            period_of(row),
            brand,
            name,
        )

        grouping[key] += Decimal(
            str(
                row.get("TotalQuantity") or 0
            )
        )

    if not grouping:

        return (
            "No recorded device quantities "
            f"were found for {', '.join(periods)}."
        )

    ranking = sorted(
        grouping.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )

    disclaimer = (
        "These are preliminary recorded quantities "
        "across transaction statuses, not verified "
        "completed device sales."
    )

    if (
        is_ranking_question(question)
        and len(periods) == 1
    ):

        winner, total = ranking[0]

        top_rows = [
            (
                key[2],
                quantity(value),
            )
            for key, value in ranking[:5]
        ]

        return (
            "## Highest recorded device\n\n"
            f"**Period:** {winner[0]}\n\n"
            f"**Brand:** {winner[1]}\n\n"
            f"**Device:** {winner[2]}\n\n"
            f"**Recorded quantity:** "
            f"{quantity(total)}\n\n"
            "### Top device candidates\n\n"
            + mdtable(
                [
                    "Device",
                    "Recorded quantity",
                ],
                top_rows,
            )
            + "\n\n"
            + disclaimer
        )

    output = [
        (
            key[0],
            key[1],
            key[2],
            quantity(total),
        )
        for key, total in ranking[:15]
    ]

    return (
        "## Device quantities (preliminary)\n\n"
        + mdtable(
            [
                "Month",
                "Brand",
                "Device",
                "Recorded quantity",
            ],
            output,
        )
        + "\n\n"
        + disclaimer
    )


# ==========================================================
# 9. BRAND REPORTING
# ==========================================================

def answer_brand_question(periods):

    rows = monthly_rows(
        "brands",
        periods,
    )

    grouping = defaultdict(Decimal)

    for row in rows:

        key = (
            period_of(row),
            str(
                row.get("Brand") or "Unknown"
            ).strip(),
        )

        grouping[key] += Decimal(
            str(
                row.get("TotalQuantity") or 0
            )
        )

    values = sorted(
        grouping.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )[:15]

    if not values:

        return (
            "No brand quantities were found "
            "for the requested period."
        )

    return (
        "## Brand quantities (all product types)\n\n"
        + mdtable(
            [
                "Month",
                "Brand",
                "Recorded quantity",
            ],
            [
                (
                    key[0],
                    key[1],
                    quantity(total),
                )
                for key, total in values
            ],
        )
        + "\n\n"
        "Includes all product classifications "
        "represented in the view. These figures "
        "are not verified physical-device sales."
    )


# ==========================================================
# 10. REGION REPORTING
# ==========================================================

def answer_region_question(periods):

    rows = monthly_rows(
        "regions",
        periods,
    )

    grouping = defaultdict(int)

    for row in rows:

        region = (
            str(
                row.get("Region") or ""
            ).strip()
            or "Blank region"
        )

        grouping[
            (period_of(row), region)
        ] += int(
            row.get("TransactionCount") or 0
        )

    values = sorted(
        grouping.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )[:20]

    if not values:

        return (
            "No regional transaction records "
            "were found."
        )

    return (
        "## Transaction headers by region\n\n"
        + mdtable(
            [
                "Month",
                "Region",
                "Headers",
            ],
            [
                (
                    key[0],
                    key[1],
                    num(total),
                )
                for key, total in values
            ],
        )
        + "\n\n"
        "Unmapped and blank regions remain visible. "
        "These are recorded transaction headers, "
        "not verified regional sales."
    )


# ==========================================================
# 11. BRANCH REPORTING
# ==========================================================

def answer_branch_question(periods):

    rows = monthly_rows(
        "branches",
        periods,
    )

    grouping = defaultdict(int)

    for row in rows:

        key = (
            period_of(row),

            str(
                row.get("TransactionBranchCode")
                or "Unspecified"
            ).strip(),

            str(
                row.get("BranchName")
                or "Unmapped branch"
            ).strip(),
        )

        grouping[key] += int(
            row.get("TransactionCount") or 0
        )

    values = sorted(
        grouping.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )[:20]

    if not values:

        return (
            "No branch transaction records "
            "were found."
        )

    return (
        "## Transaction headers by branch\n\n"
        + mdtable(
            [
                "Month",
                "Code",
                "Branch",
                "Headers",
            ],
            [
                (
                    key[0],
                    key[1],
                    key[2],
                    num(total),
                )
                for key, total in values
            ],
        )
        + "\n\n"
        "Unmapped branches remain visible."
    )


# ==========================================================
# 12. TRANSACTION REPORTING
# ==========================================================

def answer_transaction_question(
    question,
    periods,
    compare,
):
    """
    Answer transaction count and preliminary
    transaction-value questions.

    Uses reporting.SalesMonthlySummary.
    """

    rows = monthly_rows(
        "transactions",
        periods,
    )

    if not rows:

        return (
            "No transaction records are available "
            f"for {', '.join(periods)}."
        )

    # Optional transaction category
    category_match = re.search(
        r"\b([A-Za-z]+)\s*/\s*"
        r"([A-Za-z]+)\s*/\s*"
        r"([A-Za-z]+)\b",
        question,
    )

    category = (
        tuple(
            value.upper()
            for value in category_match.groups()
        )
        if category_match
        else None
    )

    if category:

        rows = [
            row
            for row in rows
            if category_of(row) == category
        ]

    if not rows:

        return (
            "No records match the requested "
            "category and period."
        )

    # ------------------------------------------------------
    # TRANSACTION VALUE
    # ------------------------------------------------------

    is_value_question = bool(
        re.search(
            r"\b("
            r"value|amount|net value|total value"
            r")\b",
            question,
            re.I,
        )
    )

    if is_value_question:

        if not category or len(periods) != 1:

            return (
                "Specify one month and a transaction "
                "category such as R/A/N. Different "
                "currencies and statuses cannot be "
                "combined without validation."
            )

        currencies = {
            str(
                row.get("TxnCurrency") or ""
            ).strip()
            for row in rows
        }

        if (
            len(currencies) != 1
            or next(iter(currencies)) in ("", "-")
            or any(
                row.get("TotalNetValue") is None
                for row in rows
            )
        ):

            return (
                "The reported net values cannot "
                "be combined safely because currency "
                "or amount information is incomplete."
            )

        total = sum(
            (
                Decimal(
                    str(row["TotalNetValue"])
                )
                for row in rows
            ),
            Decimal(0),
        )

        currency = next(iter(currencies))

        return (
            f"In {periods[0]}, category "
            f"{'/'.join(category)} has a preliminary "
            f"net transaction value of "
            f"**{total:,.2f} {currency}**.\n\n"
            "This is not verified revenue."
        )

    # ------------------------------------------------------
    # MONTHLY COMPARISON
    # ------------------------------------------------------

    if compare:

        grouping = defaultdict(int)

        for row in rows:

            key = (
                period_of(row),
                str(
                    row.get("InvType") or "Unknown"
                ).strip(),
            )

            grouping[key] += int(
                row.get("TransactionCount") or 0
            )

        types = sorted(
            {
                key[1]
                for key in grouping
            }
        )

        first, second = periods

        output = [
            (
                transaction_type,

                num(
                    grouping[
                        (first, transaction_type)
                    ]
                ),

                num(
                    grouping[
                        (second, transaction_type)
                    ]
                ),
            )
            for transaction_type in types
        ]

        first_total = sum(
            value
            for (period, _), value in grouping.items()
            if period == first
        )

        second_total = sum(
            value
            for (period, _), value in grouping.items()
            if period == second
        )

        output.append(
            (
                "**Total**",
                f"**{num(first_total)}**",
                f"**{num(second_total)}**",
            )
        )

        return (
            "## Transaction comparison\n\n"
            + mdtable(
                [
                    "Type",
                    first,
                    second,
                ],
                output,
            )
            + "\n\n"
            "Counts include all transaction statuses. "
            "Transaction type codes have not been "
            "validated as business labels."
        )

    # ------------------------------------------------------
    # TRANSACTION TOTALS
    # ------------------------------------------------------

    grouping = defaultdict(int)

    for row in rows:

        grouping[
            period_of(row)
        ] += int(
            row.get("TransactionCount") or 0
        )

    if category and len(periods) == 1:

        return (
            f"In {periods[0]}, category "
            f"{'/'.join(category)} recorded "
            f"**{num(sum(grouping.values()))}** "
            "transaction headers.\n\n"
            "These are not necessarily finalized sales."
        )

    return (
        "## Recorded transaction headers\n\n"
        + mdtable(
            [
                "Period",
                "Transaction headers",
            ],
            [
                (
                    period,
                    num(total),
                )
                for period, total in sorted(
                    grouping.items()
                )
            ],
        )
        + "\n\n"
        "Counts include all available transaction "
        "statuses, not only completed sales."
    )


# ==========================================================
# 13. MAIN REAL SQL QUESTION HANDLER
# ==========================================================

def answer_real_sales_question(question):
    """
    Main entry point for Victoria's real
    SQL Server reporting.

    Routes supported questions to approved
    reporting functions.
    """

    if (
        not isinstance(question, str)
        or not question.strip()
    ):
        return "Please enter a question."

    question = question.strip()[:2000]

    lower = question.lower()

    # ------------------------------------------------------
    # STEP 1: CLASSIFY QUESTION
    # ------------------------------------------------------

    intent = classify_question(question)

    # Unsupported questions
    if intent in ("unsupported", "revenue"):
        return unsupported_answer(intent)

    # Country questions
    if intent == "country":
        return answer_country_question(question)

    # Unknown questions
    if intent == "unknown":
        return unknown_answer()

    # ------------------------------------------------------
    # STEP 2: RESOLVE PERIOD
    # ------------------------------------------------------

    periods, error = resolve_periods(question)

    if error:
        return error

    if len(periods) > 2:
        return (
            "Please ask about one reporting month "
            "or compare exactly two months."
        )

    # ------------------------------------------------------
    # STEP 3: DETECT COMPARISON
    # ------------------------------------------------------

    compare = bool(
        re.search(
            r"\b("
            r"compare|comparison|versus|"
            r"vs\.?|difference"
            r")\b",
            lower,
        )
    ) or len(periods) == 2

    if compare and len(periods) != 2:

        return (
            "Please specify two reporting months, "
            "for example August 2026 and September 2026."
        )

    # ------------------------------------------------------
    # STEP 4: ROUTE QUESTION
    # ------------------------------------------------------

    if intent == "device":

        return answer_device_question(
            question,
            periods,
        )

    if intent == "brand":

        return answer_brand_question(periods)

    if intent == "region":

        return answer_region_question(periods)

    if intent == "branch":

        return answer_branch_question(periods)

    if intent == "transaction":

        return answer_transaction_question(
            question,
            periods,
            compare,
        )

    return unknown_answer()


# ==========================================================
# 14. LEGACY DEMO COMPATIBILITY
# ==========================================================

def answer_sales_question(question):
    """
    Legacy demonstration endpoint.

    Demo figures are synthetic and must never
    be represented as actual sales.
    """

    months = get_available_months()

    periods = detect_months(question)

    target = (
        periods[0]
        if periods
        else (
            max(months)
            if months
            else "2026-09"
        )
    )

    data = get_sales_overview(target)

    return (
        f"Sample dashboard data for {target}: "
        f"{data}. "
        "Use Ask Victoria for real reporting."
    )