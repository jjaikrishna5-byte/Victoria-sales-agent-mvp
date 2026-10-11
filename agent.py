
"""Victoria Sales Agent: deterministic answers from approved SQL aggregates."""

import re
from collections import defaultdict
from decimal import Decimal

from sql_reporting import monthly_rows, get_dashboard_data
from sales_service import get_sales_overview, get_available_months


MONTH_NAMES = {
    name: i
    for i, name in enumerate(
        (
            "january", "february", "march", "april",
            "may", "june", "july", "august",
            "september", "october", "november", "december"
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
    r"\b(" +
    "|".join(
        sorted(MONTH_ALIASES, key=len, reverse=True)
    ) +
    r")\b"
)


def detect_months(question):
    """Identify explicit YYYY-MM and named months with years."""
    found = []

    for match in re.finditer(
        r"\b(20\d{2})-(0[1-9]|1[0-2])\b",
        question,
    ):
        found.append((match.start(), match.group(0)))

    for match in re.finditer(
        MONTH_PATTERN + r"\s+(20\d{2})\b",
        question,
        re.I,
    ):
        month = MONTH_ALIASES[match.group(1).lower()]
        found.append(
            (match.start(), f"{match.group(2)}-{month:02d}")
        )

    for match in re.finditer(
        r"\b(20\d{2})\s+" + MONTH_PATTERN,
        question,
        re.I,
    ):
        month = MONTH_ALIASES[match.group(2).lower()]
        found.append(
            (match.start(), f"{match.group(1)}-{month:02d}")
        )

    # "March and April 2026"
    shared_year = re.search(
        MONTH_PATTERN +
        r"\s+(?:and|to|vs\.?|versus)\s+" +
        MONTH_PATTERN +
        r"\s+(20\d{2})\b",
        question,
        re.I,
    )

    if shared_year:
        year = shared_year.group(3)
        for index in (1, 2):
            month = MONTH_ALIASES[
                shared_year.group(index).lower()
            ]
            found.append(
                (
                    shared_year.start(),
                    f"{year}-{month:02d}"
                )
            )

    found.sort(key=lambda item: item[0])

    return list(dict.fromkeys(
        period for _, period in found
    ))


def available_periods():
    overview = get_dashboard_data()

    months = overview.get("months") or []

    if overview.get("period"):
        months = list(months) + [overview["period"]]

    valid = {
        value
        for value in months
        if isinstance(value, str)
        and re.fullmatch(
            r"20\d{2}-(0[1-9]|1[0-2])",
            value
        )
    }

    return sorted(valid)


def resolve_periods(question):
    """
    Returns (periods, error).

    Never silently replace a named month with
    the latest available reporting month.
    """
    explicit = detect_months(question)

    if explicit:
        return explicit, None

    available = available_periods()

    if not available:
        return [], "No reporting periods are available."

    names = list(re.finditer(
        MONTH_PATTERN,
        question,
        re.I,
    ))

    if names:
        resolved = []

        for match in names:
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
                    f"No records are available for "
                    f"{match.group(1).title()}."
                )

            if len(candidates) > 1:
                years = ", ".join(
                    period[:4]
                    for period in candidates
                )

                return [], (
                    f"Which {match.group(1).title()} "
                    f"do you mean: {years}? "
                    "Please include the year."
                )

            resolved.append(candidates[0])

        return list(dict.fromkeys(resolved)), None

    # A bare year is not enough to select a single month.
    year_only = re.findall(r"\b20\d{2}\b", question)

    if year_only:
        return [], (
            "Please include a month, such as "
            "March 2026, or ask for a supported "
            "monthly comparison."
        )

    # No date specified: make the chosen period explicit.
    return [available[-1]], None


def period_of(row):
    return (
        f"{int(row['SalesYear'])}-"
        f"{int(row['SalesMonth']):02d}"
    )


def category_of(row):
    return tuple(
        str(row.get(field) or "").strip().upper()
        for field in (
            "InvType",
            "DocStatus",
            "DeleteStatus",
        )
    )


def mdtable(headings, rows):
    output = [
        "| " + " | ".join(map(str, headings)) + " |",
        "|" + "|".join(
            ["---"] * len(headings)
        ) + "|",
    ]

    for row in rows:
        output.append(
            "| " + " | ".join(map(str, row)) + " |"
        )

    return "\n".join(output)


def num(value):
    return f"{int(value):,}"


def quantity(value):
    value = Decimal(str(value))

    if value == value.to_integral_value():
        return f"{value:,.0f}"

    return f"{value:,.2f}"


def unsupported(question):
    lower = question.lower()

    if re.search(
        r"\b(profit|forecast|predict|inventory|"
        r"customer|salesperson|employee|"
        r"phone number|stock level)\b",
        lower,
    ):
        return (
            "That information is not available in "
            "the approved aggregated reporting views."
        )

    if re.search(
        r"\b(revenue|turnover|gross margin)\b",
        lower,
    ):
        return (
            "Verified revenue is not available yet. "
            "Transaction amounts cannot be treated "
            "as confirmed sales revenue."
        )

    return None


def is_ranking_question(question):
    return bool(re.search(
        r"\b(top|highest|most|best|leading|"
        r"largest|maximum|number one|rank)\b",
        question,
        re.I,
    ))


def answer_device_question(question, periods):
    rows = monthly_rows("devices", periods)

    grouping = defaultdict(Decimal)

    for row in rows:
        brand = str(row.get("Brand") or "").strip()
        name = str(row.get("PartName") or "").strip()

        if (
            "samsung" in question.lower()
            and "SAMSUNG" not in brand.upper()
            and "SAMSUNG" not in name.upper()
        ):
            continue

        key = (period_of(row), brand, name)

        grouping[key] += Decimal(
            str(row.get("TotalQuantity") or 0)
        )

    if not grouping:
        return (
            "No device-candidate quantities were "
            f"found for {', '.join(periods)}."
        )

    ranking = sorted(
        grouping.items(),
        key=lambda item: (
            -item[1],
            item[0][0],
            item[0][2],
        ),
    )

    disclaimer = (
        "These are preliminary recorded detail "
        "quantities across transaction statuses, "
        "not verified completed sales."
    )

    # Answer the actual question first.
    if is_ranking_question(question) and len(periods) == 1:
        winner, winning_quantity = ranking[0]

        answer = (
            "## Highest recorded device\n\n"
            f"**Period:** {winner[0]}\n\n"
            f"**Device:** {winner[2]}\n\n"
            f"**Recorded quantity:** "
            f"{quantity(winning_quantity)}\n\n"
            f"{disclaimer}"
        )

        # Keep a short supporting comparison.
        top_rows = [
            (
                key[2],
                quantity(total),
            )
            for key, total in ranking[:5]
        ]

        answer += (
            "\n\n### Top device candidates\n\n"
            + mdtable(
                ["Device", "Recorded quantity"],
                top_rows,
            )
        )

        return answer

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


def answer_brand_question(periods):
    rows = monthly_rows("brands", periods)

    grouping = defaultdict(Decimal)

    for row in rows:
        key = (
            period_of(row),
            str(row.get("Brand") or "Unknown").strip(),
        )

        grouping[key] += Decimal(
            str(row.get("TotalQuantity") or 0)
        )

    values = sorted(
        grouping.items(),
        key=lambda item: (-item[1], item[0]),
    )[:15]

    return (
        "## Brand quantities (all product types)\n\n"
        + mdtable(
            [
                "Month",
                "Brand",
                "Recorded quantity",
            ],
            [
                (key[0], key[1], quantity(total))
                for key, total in values
            ],
        )
        + "\n\nIncludes license and fee products "
        "such as WATU. These are not confirmed "
        "physical-device sales."
    )


def answer_region_question(periods):
    rows = monthly_rows("regions", periods)

    grouping = defaultdict(int)

    for row in rows:
        region = (
            str(row.get("Region") or "").strip()
            or "Blank region"
        )

        grouping[
            (period_of(row), region)
        ] += int(row.get("TransactionCount") or 0)

    values = sorted(
        grouping.items(),
        key=lambda item: (-item[1], item[0]),
    )[:20]

    return (
        "## Transaction headers by region\n\n"
        + mdtable(
            ["Month", "Region", "Headers"],
            [
                (key[0], key[1], num(total))
                for key, total in values
            ],
        )
        + "\n\nUnmapped and blank regions remain "
        "visible. This is not a verified "
        "regional-sales ranking."
    )


def answer_branch_question(periods):
    rows = monthly_rows("branches", periods)

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
        key=lambda item: (-item[1], item[0]),
    )[:20]

    return (
        "## Transaction headers by branch\n\n"
        + mdtable(
            ["Month", "Code", "Branch", "Headers"],
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
        + "\n\nUnmapped branches remain visible."
    )


def answer_transaction_question(
    question,
    periods,
    compare,
):
    rows = monthly_rows("transactions", periods)

    if not rows:
        return (
            "No transaction records are available "
            f"for {', '.join(periods)}."
        )

    category_match = re.search(
        r"\b([A-Za-z]+)\s*/\s*"
        r"([A-Za-z]+)\s*/\s*"
        r"([A-Za-z]+)\b",
        question,
        re.I,
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
            row for row in rows
            if category_of(row) == category
        ]

    if not rows:
        return (
            "No records match the requested "
            "category and period."
        )

    is_value = bool(re.search(
        r"\b(value|amount|net value|total value)\b",
        question,
        re.I,
    ))

    if is_value:
        if not category or len(periods) != 1:
            return (
                "Specify one month and a transaction "
                "category such as R/A/N. Different "
                "currencies and statuses cannot be "
                "combined without validation."
            )

        currencies = {
            str(row.get("TxnCurrency") or "").strip()
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
                "The reported net values cannot be "
                "combined safely because currency "
                "or amount information is incomplete."
            )

        total = sum(
            (
                Decimal(str(row["TotalNetValue"]))
                for row in rows
            ),
            Decimal(0),
        )

        return (
            f"In {periods[0]}, category "
            f"{'/'.join(category)} has a preliminary "
            f"net transaction value of "
            f"**{total:,.2f} "
            f"{next(iter(currencies))}**.\n\n"
            "This is not verified revenue."
        )

    if compare:
        grouping = defaultdict(int)

        for row in rows:
            key = (
                period_of(row),
                str(
                    row.get("InvType")
                    or "Unknown"
                ).strip(),
            )

            grouping[key] += int(
                row["TransactionCount"]
            )

        types = sorted(
            {key[1] for key in grouping}
        )

        first, second = periods

        output = [
            (
                transaction_type,
                num(grouping[(first, transaction_type)]),
                num(grouping[(second, transaction_type)]),
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
                ["Type", first, second],
                output,
            )
            + "\n\nCounts include all statuses. "
            "Transaction codes are not verified "
            "business labels."
        )

    grouping = defaultdict(int)

    for row in rows:
        grouping[period_of(row)] += int(
            row["TransactionCount"]
        )

    if category and len(periods) == 1:
        return (
            f"In {periods[0]}, category "
            f"{'/'.join(category)} recorded "
            f"**{num(sum(grouping.values()))}** "
            "transaction headers.\n\n"
            "Not necessarily finalized sales."
        )

    return (
        "## Recorded transaction headers\n\n"
        + mdtable(
            ["Period", "Transaction headers"],
            [
                (period, num(total))
                for period, total in sorted(
                    grouping.items()
                )
            ],
        )
        + "\n\nCounts include all available "
        "transaction statuses, not only "
        "completed sales."
    )


def answer_real_sales_question(question):
    if not isinstance(question, str) or not question.strip():
        return "Please enter a question."

    question = question.strip()[:2000]
    lower = question.lower()

    blocked = unsupported(question)

    if blocked:
        return blocked

    periods, error = resolve_periods(question)

    if error:
        return error

    compare = bool(re.search(
        r"\b(compare|comparison|versus|difference)\b"
        r"|\bvs\.?\b",
        lower,
    )) or len(periods) == 2

    if compare and len(periods) != 2:
        return (
            "Please specify two reporting months, "
            "for example March 2026 and April 2026."
        )

    if not compare and len(periods) > 1:
        return (
            "Please ask about one period or request "
            "a comparison between two periods."
        )

    if any(
        word in lower
        for word in (
            "device",
            "model",
            "smartphone",
            "phone",
            "samsung",
            "product",
            "sold",
        )
    ):
        return answer_device_question(question, periods)

    if "brand" in lower:
        return answer_brand_question(periods)

    if any(
        word in lower
        for word in (
            "region",
            "district",
            "geograph",
            "location",
        )
    ):
        return answer_region_question(periods)

    if "branch" in lower:
        return answer_branch_question(periods)

    return answer_transaction_question(
        question,
        periods,
        compare,
    )


def answer_sales_question(question):
    """Legacy demo endpoint, retained for compatibility."""
    months = get_available_months()
    periods = detect_months(question)

    target = (
        periods[0]
        if periods
        else max(months) if months else "2026-09"
    )

    data = get_sales_overview(target)

    return (
        f"Sample dashboard data for {target}: "
        f"{data}. Use Ask Victoria for real reporting."
    )
