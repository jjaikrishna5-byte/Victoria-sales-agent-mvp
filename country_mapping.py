"""
Victoria Sales Agent
Preliminary country mapping based on ERP subscription IDs.

IMPORTANT:
These mappings are inferred from geographic records.
They must be verified before calculating official
country-wise sales or revenue.
"""

COUNTRY_MAPPING = {
    1: "TANZANIA",
    1020: "TANZANIA",
    1022: "KENYA",
    1023: "KENYA",
    1032: "UGANDA",
    1034: "UGANDA",
    1102: "TANZANIA",
    1104: "UGANDA",
    1110: "KENYA",
    1116: "RWANDA",
}

COUNTRY_DIRECTORY = [
    "INDIA",
    "KENYA",
    "RWANDA",
    "TANZANIA",
    "UAE",
    "UGANDA",
]


def get_country(subsc_id):
    """Return the preliminary country for a subscription."""

    try:
        subscription = int(subsc_id)
    except (TypeError, ValueError):
        return "UNMAPPED"

    return COUNTRY_MAPPING.get(
        subscription,
        "UNMAPPED"
    )


def get_all_countries():
    """Return all countries registered in the ERP."""

    return COUNTRY_DIRECTORY.copy()