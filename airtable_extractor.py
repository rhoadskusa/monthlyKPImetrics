"""
AirTable "Properties" table extractor.

Used only for portfolio scoping: which Yardi property codes count as
"active" for this month's report. Mirrors the field names and PropStatus
filter documented for the user's existing extractors/airtable_extractor.py.

*** OPEN ITEM ***
`config.AIRTABLE_TABLE_PROPERTIES` and the field names below (`PropStatus`,
`Yardi Code`) should be confirmed against the live base before relying on
this in production -- the reference doc this was built from described a
different script's usage of the same base.
"""

from __future__ import annotations

import logging

import requests

import config

log = logging.getLogger(__name__)

AIRTABLE_API_URL = "https://api.airtable.com/v0"
PROPSTATUS_FIELD = "PropStatus"
YARDI_CODE_FIELD = "Yardi Code"


def get_active_property_codes() -> set[str]:
    """Return the set of (trimmed) Yardi property codes for active properties.

    A property counts as active if PropStatus is one of
    config.ACTIVE_PROPSTATUS_VALUES.
    """
    headers = {"Authorization": f"Bearer {config.AIRTABLE_API_KEY}"}
    url = f"{AIRTABLE_API_URL}/{config.AIRTABLE_BASE_ID}/{config.AIRTABLE_TABLE_PROPERTIES}"

    active_codes: set[str] = set()
    offset = None
    pages = 0

    while True:
        params = {"offset": offset} if offset else {}
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        pages += 1

        for record in payload.get("records", []):
            fields = record.get("fields", {})
            prop_status = fields.get(PROPSTATUS_FIELD)
            yardi_code = fields.get(YARDI_CODE_FIELD)
            if prop_status in config.ACTIVE_PROPSTATUS_VALUES and yardi_code:
                active_codes.add(str(yardi_code).strip())

        offset = payload.get("offset")
        if not offset:
            break

    log.info(
        "AirTable: %d active properties found across %d page(s)",
        len(active_codes),
        pages,
    )
    return active_codes
