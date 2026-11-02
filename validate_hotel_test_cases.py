#!/usr/bin/env python3
"""
Hotel API test-case auditor — cross-file consistency checks for Tripjack v3 LIVE RUN folders.

Usage:
  python3 validate_hotel_test_cases.py
  python3 validate_hotel_test_cases.py --root "/path/to/HOTEL API TEST CASES - LIVE RUN"
  python3 validate_hotel_test_cases.py --case "Test Case 1"
  python3 validate_hotel_test_cases.py --json-report report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PRICE_TOLERANCE = 0.02

# Test Case specifications: (case_name_pattern, expected_domestic, room_counts, adult_counts, child_counts, requires_pan, requires_passport)
TEST_CASE_SPECS: dict[str, dict] = {
    "Test Case 1": {
        "desc": "Auto-cancellation of booking in ON HOLD status",
        "domestic": True,
        "rooms": 1,
        "adults": [1],
        "children": [0],
        "requires_pan": True,
    },
    "Test Case 2": {
        "desc": "Instant booking",
        "domestic": True,
        "rooms": 1,
        "adults": [4],
        "children": [2],
        "requires_pan": True,
    },
    "Test Case 3": {
        "desc": "Hold Booking then confirm Booking",
        "domestic": True,
        "rooms": 3,
        "adults": [2, 3, 2],
        "children": [2, 1, 1],
        "requires_pan": True,
    },
    "Test Case 4": {
        "desc": "Create a booking within cancellation deadline and cancel it",
        "domestic": True,
        "rooms": 5,
        "adults": [1, 2, 1, 1, 1],
        "children": [2, 1, 1, 0, 0],
        "requires_pan": True,
    },
    "Test Case 5": {
        "desc": "Create a booking outside cancellation deadline and cancel it",
        "domestic": False,
        "rooms": 1,
        "adults": [4],
        "children": [2],
        "requires_pan": True,
    },
    "Test Case 6": {
        "desc": "Cancel booking in On HOLD status",
        "domestic": False,
        "rooms": 3,
        "adults": [2, 3, 2],
        "children": [2, 1, 1],
        "children_alt": [2, 1, 2],  # room 3 accepts 1 or 2 children
        "requires_pan": True,
    },
    "Test Case 7": {
        "desc": "Instant Booking",
        "domestic": False,
        "rooms": 5,
        "adults": [1, 2, 1, 1, 1],
        "children": [2, 1, 1, 0, 0],
        "requires_pan": True,
    },
    "Test Case 8": {
        "desc": "Instant Booking",
        "domestic": False,
        "rooms": 2,
        "adults": [3, 3],
        "children": [0, 0],
        "requires_pan": True,
    },
    "Test Case 9": {
        "desc": "Verify that cancellation rules and policies are displayed on your application",
        "rooms": None,
        "requires_pan": None,
    },
    "Test Case 10": {
        "desc": "Same PAN for all rooms (Create a booking using the same PAN across all rooms)",
        "domestic": True,
        "rooms": 2,
        "adults": [2, 2],
        "children": [1, 0],
        "requires_pan": True,
        "same_pan_across_rooms": True,
    },
    "Test Case 11": {
        "desc": "Same PAN for all guests (Create a booking using the same PAN for all guests)",
        "domestic": True,
        "rooms": 1,
        "adults": [2],
        "children": [1],
        "requires_pan": True,
        "same_pan_for_all_guests": True,
    },
    "Test Case 12": {
        "desc": "Booking using PASSPORT (Create a booking by selecting a non-Indian nationality and using a valid Passport number)",
        "domestic": False,
        "rooms": 1,
        "adults": [2],
        "children": [1],
        "requires_passport": True,
        "no_pan": True,
    },
    "Test Case 14": {
        "desc": "Cancel all test bookings made during the certification process",
        "rooms": None,
        "cancel_all": True,
    },
    "Test Case 13": {
        "desc": "Booking with corporate PAN",
        "domestic": True,
        "rooms": 1,
        "adults": [2],
        "children": [1],
        "requires_pan": True,
        "corporate_pan": True,
    },
}

FILE_PATTERNS: dict[str, list[str]] = {
    "search_req": ["hotel search request", "search_request", "searchrequest",
                   "listing_request", "listingrequest", "listing.rq", "listing.req",
                   "listingrq", "listingreq"],
    "search_res": ["hotel search response", "search_response", "searchresponse",
                   "listing_response", "listingresponse", "listing.rs", "listing.res",
                   "listingrs", "listingres"],
    "detail_req": ["hoteldetail-search request", "hotel detail-search request", "hoteldetail search request",
                   "detail_request", "detailrequest",
                   "pricing_request", "pricingrequest", "pricing.rq", "pricing.req",
                   "pricingrq", "pricingreq"],
    "detail_res": ["hoteldetail-search response", "hotel detail-search response",
                   "detail_response", "detailresponse",
                   "pricing_response", "pricingresponse", "pricing.rs", "pricing.res",
                   "pricingrs", "pricingres"],
    "review_req": ["hotel review request", "review_request", "reviewrequest"],
    "review_res": ["hotel review response", "review_response", "reviewresponse"],
    "cancel_policy_req": ["cancellation policy request", "cancellationpolicy_request"],
    "cancel_policy_res": ["cancellation policy response", "cancellationpolicy_response"],
    "hold_req": ["hotel hold request", "hold_request", "holdrequest"],
    "hold_res": ["hotel hold response", "hold_response", "holdresponse"],
    "confirm_hold_req": ["confirm-hold request", "confirm hold request", "confirmhold_request"],
    "confirm_hold_res": ["confirm-hold response", "confirm hold response", "confirmhold_response"],
    "book_req": ["hotel book request", "book_request", "bookrequest"],
    "book_res": ["hotel book response", "book_response", "bookresponse"],
    "booking_detail_req": ["hotel booking detail request", "booking detail request",
                           "bookdetail_request", "bookingdetail_request", "bookdetailrequest"],
    "booking_detail_res": ["hotel booking detail response", "booking detail response",
                           "bookdetail_response", "bookingdetail_response", "bookdetailresponse"],
    "cancel_req": ["hotel cancel request", "cancel_request", "cancelrequest"],
    "cancel_res": ["hotel cancel response", "cancel_response", "cancelresponse"],
    "booking_detail_after_cancel_req": [
        # "booking detail after cancel" variants
        "booking detail after cancel request",
        "bookingdetailaftercancel request",
        "bookdetailaftercancel_request",
        "bookdetail_aftercancel_request",
        "aftercancel booking detail request",
        # "hotel detail after cancel" variants
        "hotel detail after cancel request",
        "hoteldetailaftercancel request",
        "hoteldetailaftercancel_request",
        "aftercancel hotel detail request",
    ],
    "booking_detail_after_cancel_res": [
        # "booking detail after cancel" variants
        "booking detail after cancel response",
        "bookingdetailaftercancel response",
        "bookdetailaftercancel_response",
        "bookdetail_aftercancel_response",
        "aftercancel booking detail response",
        # "hotel detail after cancel" variants
        "hotel detail after cancel response",
        "hoteldetailaftercancel response",
        "hoteldetailaftercancel_response",
        "aftercancel hotel detail response",
    ],
}


@dataclass
class Finding:
    severity: str  # ERROR | WARN | INFO
    rule: str
    message: str


@dataclass
class CaseResult:
    case_name: str
    files: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    booking_status: str | None = None
    booking_status_after_cancel: str | None = None
    hotel_name: str | None = None
    request_info: dict = field(default_factory=dict)        # what the partner actually searched (dates, rooms ...)
    booking_ids: set[str] = field(default_factory=set)      # bookings created in this case
    cancelled_ids: set[str] = field(default_factory=set)    # bookings proven CANCELLED by a booking-detail response

    def add(self, severity: str, rule: str, message: str) -> None:
        self.findings.append(Finding(severity, rule, message))


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


# ── cURL command parser ───────────────────────────────────────────────────────
def _extract_curl_body(text: str) -> "tuple[str, str] | None":
    """Extract (url, json_body_text) from a cURL command string.

    Handles multi-line bodies with line-continuation backslashes.
    Uses brace-counting so it works even when the JSON spans many lines.
    Returns None if the text is not a cURL command or no JSON body is found.
    """
    stripped = text.strip()
    if not re.match(r"^curl\b", stripped, re.IGNORECASE):
        return None

    # Extract URL — --location 'url' or curl 'url' / curl "url"
    url = ""
    m = re.search(r'--location\s+[\'"]([^\'">\s]+)[\'"]', stripped)
    if not m:
        m = re.search(r'^curl\s+[\'"]([^\'">\s]+)[\'"]', stripped, re.MULTILINE)
    if m:
        url = m.group(1)

    # Find the position of the JSON body (starts with '{' after --data-raw / --data / -d)
    data_m = re.search(r'(?:--data-raw|--data|-d)\s+[\'"]?(\{)', stripped, re.DOTALL)
    if not data_m:
        return None
    start = data_m.start(1)  # index of the opening '{'

    # Walk forward counting braces (respects JSON strings so inner braces are safe)
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(stripped[start:], start):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return (url, stripped[start : i + 1])
    return None


def _curl_url_to_slot(url: str) -> "str | None":
    """Map a Tripjack hotel API URL to a request slot name."""
    if not url:
        return None
    path = url.lower().split("?")[0].rstrip("/")
    # More specific patterns first
    if re.search(r"/confirm(?:hold|booking|hotel|b)|/hold/confirm", path):
        return "confirm_hold_req"
    if re.search(r"/bookingdetail|/booking[/-]detail|/getbooking|/booking-detail", path):
        return "booking_detail_req"
    if re.search(r"/cancel\b", path):
        return "cancel_req"
    if re.search(r"/hotel/book\b|/book\b", path):
        return "book_req"
    if re.search(r"/hotel/hold\b|/hold\b", path):
        return "hold_req"
    if re.search(r"/review\b", path):
        return "review_req"
    if re.search(r"/detail\b|/pricing\b", path):
        return "detail_req"
    if re.search(r"/search\b|/listing\b", path):
        return "search_req"
    return None


def _try_parse_curl(text: str) -> "Any | None":
    """Parse a cURL command and return the extracted JSON body.

    If the URL identifies a known API slot, wraps the result in
    {\"__headed__\": {slot: body}} so the caller routes it correctly.
    Returns None if text is not a cURL command or parsing fails.
    """
    result = _extract_curl_body(text)
    if result is None:
        return None
    url, body_text = result
    try:
        body = json.loads(body_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(body, dict):
        return None
    slot = _curl_url_to_slot(url)
    if slot:
        return {"__headed__": {slot: body}}
    return body


def _endpoint_key_to_slot(ek: str) -> "str | None":
    """Map an endpoint_key string like 'hotel_book' to a slot name."""
    k = ek.lower().replace("_", "").replace("-", "").replace(" ", "")
    if "confirmhold" in k or "confirmbook" in k:
        return "confirm_hold_req"
    if "bookingdetail" in k or "getbooking" in k or "bookinginfo" in k:
        return "booking_detail_req"
    if "bookingdetailcancel" in k or "postcanceldetail" in k:
        return "booking_detail_after_cancel_req"
    if "cancel" in k:
        return "cancel_req"
    if "book" in k:
        return "book_req"
    if "hold" in k:
        return "hold_req"
    if "review" in k:
        return "review_req"
    if "detail" in k or "pricing" in k:
        return "detail_req"
    if "search" in k or "listing" in k:
        return "search_req"
    return None


# Top-level keys that signal an HTTP-envelope wrapper object.
# These are never present in a real API request/response payload.
_HTTP_ENVELOPE_KEYS: frozenset[str] = frozenset({
    "method", "endpoint_key", "endpoint", "headers", "status_code",
    "statuscode", "status", "request_id", "requestid",
})


def _unwrap_http_envelope(obj: Any) -> "tuple[str, Any] | None":
    """Detect the HTTP-envelope format and return (slot_or_empty, body_dict).

    Recognises objects like::

        {
            "method": "POST",
            "url": "https://.../hotel/book",
            "endpoint_key": "hotel_book",
            "headers": {...},
            "body": { ...actual API payload... }
        }

    Returns (slot, body) when the body is a dict.
    Returns None if the object is not an HTTP envelope.
    """
    if not isinstance(obj, dict):
        return None

    # Must have a "body" or "request_body" / "response_body" key that is a dict
    body = obj.get("body") or obj.get("request_body") or obj.get("response_body")
    if not isinstance(body, dict):
        return None

    # Must have at least one envelope-specific key (not a normal API payload)
    obj_keys_lower = {k.lower().replace("_", "").replace("-", "") for k in obj}
    envelope_signals = {"method", "endpointkey", "endpoint", "headers",
                        "statuscode", "requestid", "capturedat", "provider"}
    if not (obj_keys_lower & envelope_signals):
        return None

    # Determine slot from URL → endpoint_key → content (priority order)
    url = str(obj.get("url") or obj.get("endpoint_url") or "")
    slot = _curl_url_to_slot(url)
    if not slot:
        ek = str(obj.get("endpoint_key") or obj.get("endpoint") or "")
        slot = _endpoint_key_to_slot(ek)
    if not slot:
        slot = _identify_by_content(body) or ""

    return (slot, body)


# Common envelope wrappers that Tripjack (and similar APIs) use to wrap the
# actual payload — checked after the top-level key lookup fails.
_WRAPPERS = ("data", "result", "response", "hotel", "body", "payload")


def _get_nested(obj: Any, key: str) -> Any:
    """Get `key` from obj, falling back through common envelope wrappers."""
    if not isinstance(obj, dict):
        return None
    val = obj.get(key)
    if val is not None:
        return val
    for wrapper in _WRAPPERS:
        wrapped = obj.get(wrapper)
        if isinstance(wrapped, dict):
            val = wrapped.get(key)
            if val is not None:
                return val
    return None


def _get_nested_list(obj: Any, key: str) -> list | None:
    """Same as _get_nested but only returns list values."""
    val = _get_nested(obj, key)
    return val if isinstance(val, list) else None


def _value_exists_anywhere(obj: Any, target: str) -> bool:
    """Return True if `target` appears as any string value anywhere in a nested JSON."""
    if isinstance(obj, str):
        return obj == target
    if isinstance(obj, dict):
        return any(_value_exists_anywhere(v, target) for v in obj.values())
    if isinstance(obj, list):
        return any(_value_exists_anywhere(item, target) for item in obj)
    return False


# ── Raw-text fallbacks ─────────────────────────────────────────────────────
# These work on the file bytes directly, so they succeed even when the file
# is not valid JSON, is a headed-text document, or has encoding issues.

def _raw_find_key(path: "Path | None", key: str) -> "str | None":
    """Extract the string value of `key` from a file's raw text via regex.

    Handles  "key": "value"  and  'key': 'value'  JSON styles, as well as
    key=value assignment forms.  Returns None if not found or file missing.
    """
    if not path or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(
            rf'["\']?{re.escape(key)}["\']?\s*[:=]\s*["\']([^"\'\r\n,}}\]]+)["\']',
            text,
        )
        if m:
            val = m.group(1).strip()
            return val if val else None
    except Exception:
        pass
    return None


def _raw_contains(path: "Path | None", value: str) -> bool:
    """Return True if `value` appears verbatim anywhere in the raw file text."""
    if not path or not path.is_file() or not value:
        return False
    try:
        return value in path.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        return False


# Regex that matches common booking / order ID key names followed by a string value.
_RAW_BID_RE = re.compile(
    r'["\']?(?:booking(?:Id|No|Number|Reference)|order(?:Id|Number|Reference)|'
    r'reservation(?:Id|No)|confirmation(?:Id|Number)|refNo|transactionId|'
    r'hold(?:Id|BookingId|ReferenceId|RefId|BookingNo|OrderId)|'
    r'preBookingId|tempBookingId|confirmHold(?:Id|BookingId))["\']?'
    r'\s*[:=]\s*["\']([A-Za-z0-9_\-]{3,80})["\']',
    re.IGNORECASE,
)


def _raw_booking_ids(path: "Path | None") -> "set[str]":
    """Extract booking / order ID values from raw file text using regex.

    Used as a fallback when the file cannot be parsed as JSON.
    """
    if not path or not path.is_file():
        return set()
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        return {m.group(1) for m in _RAW_BID_RE.finditer(text) if m.group(1)}
    except Exception:
        return set()


# Regex: find totalPrice / amount numeric values in raw text (price-like keys only)
_RAW_TOTAL_PRICE_RE = re.compile(
    r'["\']?(?:totalPrice|total_price|totalAmount|grossAmount|payableAmount|'
    r'finalPrice|netAmount|chargeAmount)["\']?\s*[:=]\s*["\']?(\d[\d,]*(?:\.\d+)?)["\']?',
    re.IGNORECASE,
)
_RAW_PAY_AMOUNT_RE = re.compile(
    r'["\']?(?:amount|paymentAmount|payableAmount|totalAmount|chargeAmount)["\']?'
    r'\s*[:=]\s*["\']?(\d[\d,]*(?:\.\d+)?)["\']?',
    re.IGNORECASE,
)


def _raw_find_total_price(path: "Path | None") -> "float | None":
    """Extract the first totalPrice-like value from raw file text.

    Tries common price key names (totalPrice, grossAmount, payableAmount …).
    Used when the review response did not parse as JSON.
    """
    if not path or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        m = _RAW_TOTAL_PRICE_RE.search(text)
        if m:
            return float(m.group(1).replace(",", ""))
    except Exception:
        pass
    return None


def _raw_find_amount(path: "Path | None") -> "float | None":
    """Extract the first payment amount value from raw file text.

    Tries common amount key names (amount, paymentAmount, payableAmount …).
    Used when the booking request did not parse as JSON.
    """
    if not path or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        m = _RAW_PAY_AMOUNT_RE.search(text)
        if m:
            return float(m.group(1).replace(",", ""))
    except Exception:
        pass
    return None


def _raw_price_in_file(path: "Path | None", target: float, tol: float = 0.02) -> bool:
    """Return True if `target` (±tol*target) appears as a numeric literal in the file."""
    if not path or not path.is_file() or target == 0:
        return False
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for m in re.finditer(r'\b(\d[\d,]*(?:\.\d+)?)\b', text):
            try:
                v = float(m.group(1).replace(",", ""))
                if abs(v - target) <= max(tol * target, 2.0):
                    return True
            except ValueError:
                pass
    except Exception:
        pass
    return False


def _get_review_option(review_res: Any) -> dict | None:
    """Extract the selected option dict from a review response."""
    if not isinstance(review_res, dict):
        return None
    # Try 'option' key (single object)
    opt = _get_nested(review_res, "option")
    if isinstance(opt, dict):
        return opt
    # Try 'options' array
    opts = _get_nested_list(review_res, "options")
    if opts:
        return opts[0] if isinstance(opts[0], dict) else None
    return None


# Known binary / media file extensions — everything NOT in this set is treated as
# potentially text-based and will be read by the validator.  This mirrors the
# denylist used by the upload filters so that .log, .response, .req, and any
# other text-based format the supplier might use are accepted automatically.
_BINARY_SUFFIXES: frozenset[str] = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff",
    ".mp3", ".mp4", ".mov", ".avi", ".mkv", ".wav", ".flac",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".db", ".sqlite", ".mdb",
    ".class", ".jar", ".pyc", ".o", ".a",
})


def _all_readable_files(case_dir: Path) -> list[Path]:
    """Return all non-hidden, non-binary files in case_dir.

    Accepts any extension not in _BINARY_SUFFIXES — including .json, .txt,
    .log, .response, .req, no-extension, etc.  Files are returned sorted
    alphabetically so processing order is deterministic.

    Files with "static" in their name (e.g. hotel-static-detail) are always
    excluded — they belong to a different API endpoint and must not affect
    any slot classification, hash extraction, or validation checks.
    """
    seen: set[Path] = set()
    result: list[Path] = []
    for p in sorted(case_dir.glob("*")):
        if not p.is_file() or p.name.startswith(".") or p.name.startswith("~"):
            continue
        if "static" in p.name.lower():
            continue
        if p.suffix.lower() not in _BINARY_SUFFIXES and p not in seen:
            seen.add(p)
            result.append(p)
    return result


def find_file(case_dir: Path, patterns: list[str], skip_if: list[str] | None = None) -> Path | None:
    candidates = _all_readable_files(case_dir)
    for path in candidates:
        norm = normalize_name(path.name)
        # Skip files whose names contain any exclusion keyword
        if skip_if and any(normalize_name(s) in norm for s in skip_if):
            continue
        for pattern in patterns:
            if normalize_name(pattern) in norm:
                return path
    return None


# Keys that must NOT match files containing these words.
# "bookdetail" covers snake_case files like bookDetail_request.txt /
# bookDetail_response.txt which sort before detail_request.txt alphabetically
# but belong to the booking_detail_req/res slot, not the hotel-detail slot.
_SKIP_IF: dict[str, list[str]] = {
    "detail_req": ["booking", "bookdetail", "static"],
    "detail_res": ["booking", "bookdetail", "static"],
}


def load_json(path: Path | None) -> Any | None:
    if path is None or not path.exists():
        return None
    # utf-8-sig strips BOM (common in Windows-created files)
    try:
        text = path.read_text(encoding="utf-8-sig").strip()
    except (UnicodeDecodeError, OSError):
        try:
            text = path.read_text(encoding="latin-1").strip()
        except Exception:
            return None
    if not text:
        return None
    # Try standard JSON first
    try:
        parsed = json.loads(text)
        # Detect HTTP-envelope format: {method, url, headers, body}
        # Unwrap to the real payload and route to the correct slot.
        if isinstance(parsed, dict):
            env = _unwrap_http_envelope(parsed)
            if env is not None:
                slot, body = env
                if slot:
                    return {"__headed__": {slot: body}}
                return body  # slot unknown — let content-based ID handle it
        return parsed
    except json.JSONDecodeError:
        pass
    # Try "URL:<url>\n\n{...body...}" format used in Tripjack RQ/RS text files
    _url_prefix_m = re.match(r'^URL\s*:\s*(\S+)\s*\n([\s\S]+)', text, re.IGNORECASE)
    if _url_prefix_m:
        _url_from_prefix = _url_prefix_m.group(1).strip()
        _body_text = _url_prefix_m.group(2).strip()
        if _body_text:
            try:
                _body_obj = json.loads(_body_text)
                if isinstance(_body_obj, (dict, list)):
                    _slot = _curl_url_to_slot(_url_from_prefix) if isinstance(_body_obj, dict) else None
                    if _slot:
                        return {"__headed__": {_slot: _body_obj}}
                    return _body_obj
            except json.JSONDecodeError:
                pass
        else:
            # URL-only file (e.g. cancel request with booking ID in path)
            _slot = _curl_url_to_slot(_url_from_prefix)
            if _slot:
                # Extract booking ID from URL path if present
                _bid_in_url = re.search(r'(?:TJ|OMS|B)[A-Za-z0-9]{6,}', _url_from_prefix)
                _stub: dict = {}
                if _bid_in_url:
                    _stub["bookingId"] = _bid_in_url.group(0)
                return {"__headed__": {_slot: _stub}}

    # Try cURL command format — extract JSON body from --data-raw / --data
    curl_parsed = _try_parse_curl(text)
    if curl_parsed is not None:
        return curl_parsed
    # Try NDJSON (newline-delimited JSON — multiple objects in one file)
    ndjson = _try_ndjson(text)
    if ndjson is not None:
        return ndjson  # returned as list; validate_case handles via extract_slots_from_combined

    # Try headed-text format  (section headings + JSON blocks)
    headed = parse_headed_text_file(text)
    if headed:
        return {"__headed__": headed}  # special sentinel handled in validate_case

    # Try supplier format  (API Method / Supplier Request / Supplier Response)
    supplier = parse_supplier_format_file(text)
    if supplier:
        return {"__headed__": supplier}

    return {"__parse_error__": f"not valid JSON (file: {path.name})"}


def normalize_rooms(rooms: Any) -> list[dict]:
    if not rooms:
        return []
    # Some APIs return a single room object instead of an array — wrap it
    if isinstance(rooms, dict):
        rooms = [rooms]
    if not isinstance(rooms, (list, tuple)):
        return []
    out = []
    for r in rooms:
        if not isinstance(r, dict):
            continue
        _raw_a = r.get("adults") or r.get("numberOfAdults") or r.get("adultCount") or 0
        _raw_c = r.get("children") or r.get("numberOfChild") or r.get("childCount") or 0
        try:
            _a = int(_raw_a)
        except (TypeError, ValueError):
            _a = 0
        try:
            _c = int(_raw_c)
        except (TypeError, ValueError):
            _c = 0
        entry = {"adults": _a, "children": _c}
        if "childAge" in r:
            _ca = r.get("childAge") or []
            if isinstance(_ca, (int, float)):
                _ca = [int(_ca)]
            entry["childAge"] = sorted(_ca)
        out.append(entry)
    return out


def rooms_signature(rooms: list[dict]) -> str:
    return json.dumps(normalize_rooms(rooms), sort_keys=True)


def hotel_id_from(obj: dict | None, *keys: str) -> str | None:
    if not obj:
        return None
    for key in keys:
        val = obj.get(key) if isinstance(obj, dict) else None
        if val is not None and str(val).strip():
            return str(val).strip()
    # Fallback: deep search for each key
    for key in keys:
        val = _deep_find(obj, key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def find_option(options: list | None, option_id: str | None) -> dict | None:
    if not options or not option_id:
        return None
    for opt in options:
        if isinstance(opt, dict) and opt.get("optionId") == option_id:
            return opt
    return None


def option_snapshot(opt: dict | None) -> dict | None:
    if not opt:
        return None
    rooms = opt.get("roomInfo") or []
    pricing = opt.get("pricing") or {}
    compliance = opt.get("compliance") or {}
    return {
        "optionId": opt.get("optionId"),
        "roomInfo": [
            {"id": r.get("id"), "name": r.get("name")}
            for r in rooms
            if isinstance(r, dict)
        ],
        "mealBasis": opt.get("mealBasis"),
        "pricing": {
            "totalPrice": pricing.get("totalPrice"),
            "basePrice": pricing.get("basePrice"),
            "currency": pricing.get("currency"),
        },
        "panRequired": compliance.get("panRequired"),
        "passportRequired": compliance.get("passportRequired"),
    }


def prices_close(a: Any, b: Any, tol: float = PRICE_TOLERANCE) -> bool:
    try:
        if a is None and b is None:
            return True
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def compare_option_snapshots(expected: dict | None, actual: dict | None, label: str) -> list[tuple[str, str]]:
    issues: list[tuple[str, str]] = []
    if not expected or not actual:
        issues.append(("ERROR", f"{label}: missing option payload"))
        return issues

    # optionId change at review step is expected Tripjack behaviour — not emitted
    # (room name, pricing, panRequired checks below still run regardless)

    exp_rooms = expected.get("roomInfo") or []
    act_rooms = actual.get("roomInfo") or []
    if len(exp_rooms) != len(act_rooms):
        issues.append(("ERROR", f"{label}: room count {len(exp_rooms)} vs {len(act_rooms)}"))
    else:
        for i, (er, ar) in enumerate(zip(exp_rooms, act_rooms)):
            if er.get("id") and ar.get("id") and er.get("id") != ar.get("id"):
                issues.append(("ERROR", f"{label}: room[{i}] id {er.get('id')!r} vs {ar.get('id')!r}"))
            if er.get("name") and ar.get("name") and er.get("name") != ar.get("name"):
                issues.append(("ERROR", f"{label}: room[{i}] name {er.get('name')!r} vs {ar.get('name')!r}"))

    exp_p = expected.get("pricing") or {}
    act_p = actual.get("pricing") or {}
    for field in ("totalPrice", "basePrice"):
        if not prices_close(exp_p.get(field), act_p.get(field)):
            issues.append(
                (
                    "ERROR",
                    f"{label}: pricing.{field} {exp_p.get(field)!r} vs {act_p.get(field)!r}",
                )
            )
    if exp_p.get("currency") and act_p.get("currency") and exp_p.get("currency") != act_p.get("currency"):
        issues.append(("ERROR", f"{label}: currency {exp_p.get('currency')!r} vs {act_p.get('currency')!r}"))

    if expected.get("panRequired") is not None and actual.get("panRequired") is not None:
        if expected.get("panRequired") != actual.get("panRequired"):
            issues.append(
                (
                    "ERROR",
                    f"{label}: panRequired {expected.get('panRequired')!r} vs {actual.get('panRequired')!r}",
                )
            )
    if expected.get("passportRequired") is not None and actual.get("passportRequired") is not None:
        if expected.get("passportRequired") != actual.get("passportRequired"):
            issues.append(
                (
                    "ERROR",
                    f"{label}: passportRequired {expected.get('passportRequired')!r} "
                    f"vs {actual.get('passportRequired')!r}",
                )
            )
    return issues


# Normalised key names that represent a booking / order ID.
# Add any additional key names your API uses here.
_BOOKING_ID_KEYS: frozenset[str] = frozenset({
    "bookingid", "bookingno", "bookingnumber", "bookingreference",
    "orderid", "ordernumber", "orderreference",
    "reservationid", "reservationno",
    "confirmationid", "confirmationnumber",
    "referenceid", "refno",
    "transactionid",
    # Hold / pre-booking specific IDs (TC3 hold+confirm flow)
    "holdid", "holdbookingid", "holdreferenceid", "holdrefid",
    "holdbookingno", "holdorderId", "holdorderid",
    "prebookingid", "prebookingreference", "tempbookingid",
    "confirmholdbookingid", "confirmholdid",
})

# Broader pattern: any normalized key that ENDS WITH a booking-ID suffix
_BOOKING_ID_KEY_SUFFIXES: tuple[str, ...] = (
    "bookingid", "bookingno", "bookingreference",
    "orderid", "reservationid", "confirmationid",
    "referenceid", "refno", "holdid", "holdref",
)


def collect_booking_ids(data: Any, found: set[str] | None = None) -> set[str]:
    """Recursively collect every booking/order ID value found anywhere in data.

    Searches ALL key names that could represent a booking ID (see
    _BOOKING_ID_KEYS) using case-insensitive matching that ignores
    underscores, hyphens, and spaces.  Fully recursive so it finds values
    inside nested envelopes, arrays, and wrapper dicts.
    """
    found = found or set()
    if isinstance(data, dict):
        for k, v in data.items():
            norm_key = k.lower().replace("_", "").replace("-", "").replace(" ", "")
            is_id_key = (
                norm_key in _BOOKING_ID_KEYS
                or any(norm_key.endswith(sfx) for sfx in _BOOKING_ID_KEY_SUFFIXES)
            )
            if is_id_key and v and isinstance(v, (str, int)):
                found.add(str(v))
            # always recurse — the ID might be nested
            if isinstance(v, (dict, list)):
                collect_booking_ids(v, found)
    elif isinstance(data, list):
        for item in data:
            collect_booking_ids(item, found)
    return found


def count_travellers_by_room(hold_or_book: dict | None) -> list[dict]:
    if not hold_or_book:
        return []
    rooms_out = []
    rti = (hold_or_book.get("roomTravellerInfo")
           or _deep_find(hold_or_book, "roomTravellerInfo") or [])
    if not isinstance(rti, (list, tuple)):
        rti = []
    for room in rti:
        adults = children = 0
        child_ages: list[int] = []
        has_pan = has_passport = False
        for t in room.get("travellerInfo") or []:
            pt = (t.get("pt") or "").upper()
            if pt == "ADULT":
                adults += 1
            elif pt == "CHILD":
                children += 1
                if t.get("age") is not None:
                    child_ages.append(int(t.get("age")))
            if t.get("pan"):
                has_pan = True
            if t.get("pNum") or t.get("passport"):
                has_passport = True
        rooms_out.append(
            {
                "adults": adults,
                "children": children,
                "childAge": sorted(child_ages),
                "hasPan": has_pan,
                "hasPassport": has_passport,
            }
        )
    return rooms_out


def _deep_find(obj: Any, key: str) -> Any:
    """Recursively find the first occurrence of `key` anywhere in JSON."""
    if isinstance(obj, dict):
        if key in obj and obj[key] is not None:
            return obj[key]
        for v in obj.values():
            found = _deep_find(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_find(item, key)
            if found is not None:
                return found
    return None


def _find_amount_anywhere(obj: Any, target: float, tol: float = PRICE_TOLERANCE) -> Any | None:
    """Find and return the first numeric value in `obj` that is within `tol` of `target`.

    Searches recursively through any JSON structure — works for any field name
    or nesting depth, so it handles both built-in and uploaded test case files.
    """
    if isinstance(obj, (int, float)):
        try:
            if abs(float(obj) - target) <= tol:
                return obj
        except (TypeError, ValueError):
            pass
        return None
    if isinstance(obj, str):
        try:
            val = float(obj)
            if abs(val - target) <= tol:
                return obj
        except (ValueError, TypeError):
            pass
        return None
    if isinstance(obj, dict):
        for v in obj.values():
            found = _find_amount_anywhere(v, target, tol)
            if found is not None:
                return found
        return None
    if isinstance(obj, list):
        for item in obj:
            found = _find_amount_anywhere(item, target, tol)
            if found is not None:
                return found
        return None
    return None


def _extract_review_total(review_res: Any) -> Any:
    """Extract totalPrice from review response using structured paths then deep key scan."""
    if not isinstance(review_res, dict):
        return None
    opt = _get_review_option(review_res)
    if isinstance(opt, dict):
        pricing = opt.get("pricing") or _get_nested(opt, "pricing") or {}
        if isinstance(pricing, dict) and pricing.get("totalPrice") is not None:
            return pricing["totalPrice"]
        for key in ("totalPrice", "total_price", "totalAmount"):
            if opt.get(key) is not None:
                return opt[key]
    # Deep key scan across the whole review response
    return _deep_find(review_res, "totalPrice")


def _extract_payment_infos_amount(req: dict | None, path: "Path | None") -> "float | None":
    """Extract paymentInfos[0].amount from a book / confirm-hold request.

    Looks only at the paymentInfos array — never at other numeric fields —
    so random price-like numbers elsewhere in the request cannot cause false matches.
    Falls back to raw-text regex on the file if the dict has no paymentInfos.
    """
    if isinstance(req, dict):
        pis = req.get("paymentInfos") or _deep_find(req, "paymentInfos")
        if isinstance(pis, list):
            for pi in pis:
                if isinstance(pi, dict) and pi.get("amount") is not None:
                    try:
                        return float(pi["amount"])
                    except (TypeError, ValueError):
                        pass
    # Raw-text fallback: find "amount": <number> inside paymentInfos block
    if path and path.is_file():
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            # Find the paymentInfos block first (case-insensitive key), then extract amount
            pi_m = re.search(r'"[Pp]ayment[Ii]nfos"\s*:\s*\[', text)
            if pi_m:
                sub = text[pi_m.end():]
                amt_m = re.search(r'"amount"\s*:\s*([0-9]+(?:\.[0-9]+)?)', sub)
                if amt_m:
                    return float(amt_m.group(1))
        except Exception:
            pass
    return None


def _extract_detail_total_price(detail_res: dict | None, opt_id: "str | None",
                                 path: "Path | None") -> "float | None":
    """Extract totalPrice from the selected option in a detail response.

    Tries the option matching opt_id first, then the first option, then a deep scan.
    Falls back to raw-text regex on the file.
    """
    if detail_res and isinstance(detail_res, dict):
        options = _get_nested_list(detail_res, "options")
        if not isinstance(options, list):
            options = _deep_find(detail_res, "options")
        if isinstance(options, list):
            # Prefer option matching the optionId from the review request
            candidates = [o for o in options
                          if isinstance(o, dict)
                          and (not opt_id or o.get("optionId") == opt_id)]
            if not candidates:
                candidates = [o for o in options if isinstance(o, dict)]
            for opt in candidates:
                pricing = opt.get("pricing") or {}
                if isinstance(pricing, dict) and pricing.get("totalPrice") is not None:
                    try:
                        return float(pricing["totalPrice"])
                    except (TypeError, ValueError):
                        pass
        # Deep-key fallback inside the detail response
        tp = _deep_find(detail_res, "totalPrice")
        if tp is not None:
            try:
                return float(tp)
            except (TypeError, ValueError):
                pass
    # Raw-text fallback
    if path and path.is_file():
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            m = re.search(r'"totalPrice"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text)
            if m:
                return float(m.group(1))
        except Exception:
            pass
    return None


# Maximum absolute difference (in currency units) allowed between two prices
# to be considered equal.  Covers floating-point rounding only — not a
# percentage tolerance.  1.0 = at most 1 unit (e.g. 1 INR) difference.
_PRICE_EXACT_TOL: float = 1.0


def validate_payment_amount(
    book_req: dict | None,
    review_res: dict | None,
    result: CaseResult,
    detail_res: dict | None = None,
    opt_id: str | None = None,
    review_res_path: "Path | None" = None,
    book_req_path: "Path | None" = None,
    detail_res_path: "Path | None" = None,
    all_case_files: "list | None" = None,
    payment_req_label: str = "Booking Request",
) -> None:
    """Validate that paymentInfos[0].amount in the booking request exactly equals
    option.pricing.totalPrice from the Review Response (within 1 currency unit).

    Also shows the Detail Response totalPrice for reference (informational only —
    price may legitimately change between detail and review steps).
    """

    # ── Step 1: totalPrice from Review Response ──────────────────────────────
    review_price: Any = _extract_review_total(review_res) if review_res else None
    if review_price is None:
        review_price = _raw_find_total_price(review_res_path)
    if review_price is None:
        return  # nothing to compare against

    try:
        review_float = float(review_price)
    except (TypeError, ValueError):
        return

    # ── Step 2: paymentInfos[0].amount from the payment request ─────────────
    # Only look at paymentInfos.amount — do NOT scan all numbers in the file.
    book_amount: float | None = _extract_payment_infos_amount(book_req, book_req_path)

    # ── Step 3: totalPrice from Detail Response (informational) ─────────────
    detail_price: float | None = _extract_detail_total_price(
        detail_res, opt_id, detail_res_path
    )

    # ── Build display values ─────────────────────────────────────────────────
    def _fmt(val: "float | None") -> str:
        if val is None:
            return "(not found)"
        # Show as integer when there is no fractional part
        return str(int(val)) if val == int(val) else str(val)

    has_pay_req = bool(book_req or book_req_path)
    has_detail  = bool(detail_res or detail_res_path)

    # Tags: compare each source against the review price
    def _price_tag(val: "float | None", has_source: bool) -> str:
        if val is None:
            return "  [NOT FOUND]" if has_source else ""
        return "  [MATCH]" if abs(val - review_float) <= _PRICE_EXACT_TOL else "  [MISMATCH]"

    book_tag   = _price_tag(book_amount, has_pay_req)
    detail_tag = _price_tag(detail_price, has_detail)

    _pay_label_padded = payment_req_label.ljust(len("Review Response"))
    msg = (
        f"Review Response  : {_fmt(review_float)}\n"
        f"{_pay_label_padded}  : {_fmt(book_amount)}{book_tag}\n"
        f"Detail Response  : {_fmt(detail_price)}{detail_tag}"
    )

    # ── Severity: only the booking-request amount is mandatory ───────────────
    if has_pay_req and book_amount is None:
        result.add("ERROR", "PAYMENT_INFO",
            f"paymentInfos[0].amount not found in {payment_req_label}\n{msg}")
    elif has_pay_req and book_amount is not None and abs(book_amount - review_float) > _PRICE_EXACT_TOL:
        result.add("ERROR", "PAYMENT_INFO",
            f"Amount MISMATCH: {payment_req_label} has {_fmt(book_amount)} "
            f"but Review Response totalPrice is {_fmt(review_float)}\n{msg}")
    elif has_detail and detail_price is not None and abs(detail_price - review_float) > _PRICE_EXACT_TOL:
        result.add("WARN", "PAYMENT_INFO",
            f"Price changed between Detail ({_fmt(detail_price)}) "
            f"and Review ({_fmt(review_float)}) — verify this is expected\n{msg}")
    else:
        result.add("INFO", "PAYMENT_INFO",
            f"Total price matches\n{msg}")


def _spec_for(case_name: str) -> dict:
    """Return the spec dict for a case folder, regardless of naming convention.

    Handles both canonical ('Test Case 2') and custom ('TJ test Hotel Case 2',
    'TC2', 'Case 2', ...) folder names by extracting the trailing number.
    """
    spec = TEST_CASE_SPECS.get(case_name)
    if spec is not None:
        return spec
    # Extract the first 1-2 digit number from the folder name
    m = re.search(r'\b(\d{1,2})\b', case_name)
    if m:
        canonical = f"Test Case {int(m.group(1))}"
        spec = TEST_CASE_SPECS.get(canonical)
        if spec is not None:
            return spec
    return {}


def validate_flow_sequence(result: CaseResult, paths: dict, case_name: str,
                           data: dict | None = None) -> None:
    """Validate the booking flow file sequence is complete."""
    spec = _spec_for(case_name)

    def _present(slot: str) -> bool:
        # A slot is present if it has a file path OR non-empty data
        # (supplier-format combined files populate data without a per-slot path)
        if paths.get(slot):
            return True
        if data and data.get(slot):
            return True
        return False

    is_hold    = _present("hold_req")    or _present("hold_res")
    has_confirm = _present("confirm_hold_req") or _present("confirm_hold_res")
    has_cancel  = _present("cancel_req") or _present("cancel_res")

    sequence: list[tuple[str, str]] = [
        ("search_req",  "Search Request"),
        ("search_res",  "Search Response"),
        ("detail_req",  "Detail Request"),
        ("detail_res",  "Detail Response"),
        ("review_req",  "Review Request"),
        ("review_res",  "Review Response"),
    ]
    if is_hold:
        sequence += [("hold_req", "Hold Request"), ("hold_res", "Hold Response")]
        if has_confirm:
            sequence += [("confirm_hold_req", "Confirm-Hold Request"), ("confirm_hold_res", "Confirm-Hold Response")]
    else:
        sequence += [("book_req", "Book Request"), ("book_res", "Book Response")]
    sequence += [("booking_detail_req", "Booking Detail Request"), ("booking_detail_res", "Booking Detail Response")]
    if has_cancel:
        sequence += [("cancel_req", "Cancel Request"), ("cancel_res", "Cancel Response")]

    present = [(k, lbl) for k, lbl in sequence if _present(k)]
    missing = [(k, lbl) for k, lbl in sequence if not _present(k)]

    if not missing:
        result.add("INFO", "FLOW_SEQUENCE",
            "Complete flow: " + " ->".join(lbl for _, lbl in sequence))
    else:
        if present:
            result.add("INFO", "FLOW_SEQUENCE",
                f"Flow files present ({len(present)}/{len(sequence)}): " + " ->".join(lbl for _, lbl in present))
        for _, lbl in missing:
            result.add("WARN", "FLOW_SEQUENCE", f"Missing flow file: {lbl}")


def _get_traveller_field(t: dict, *keys: str) -> str:
    """Extract a field from a traveller dict trying multiple key names (handles any naming convention)."""
    for k in keys:
        v = t.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def validate_traveller_identities(result: CaseResult, traveller_source: dict | None) -> None:
    """Extract PAN / Passport for every guest in the booking request and emit as INFO."""
    if not isinstance(traveller_source, dict):
        return

    # Handle both roomTravellerInfo (Tripjack) and common alternative key names
    rooms: list = (
        traveller_source.get("roomTravellerInfo")
        or _deep_find(traveller_source, "roomTravellerInfo")
        or traveller_source.get("rooms")
        or _deep_find(traveller_source, "rooms")
        or traveller_source.get("travellers")
        or []
    )
    if not rooms:
        return

    lines: list[str] = []
    total_guests = 0

    for r_idx, room in enumerate(rooms):
        if not isinstance(room, dict):
            continue
        travellers: list = (
            room.get("travellerInfo")
            or room.get("travellers")
            or room.get("guests")
            or room.get("passengers")
            or []
        )
        for g_idx, t in enumerate(travellers):
            if not isinstance(t, dict):
                continue
            total_guests += 1

            # Passenger type
            pt = _get_traveller_field(t, "pt", "pType", "passengerType", "type").upper() or "GUEST"

            # Name
            fn = _get_traveller_field(t, "fn", "fName", "firstName", "first_name", "givenName")
            ln = _get_traveller_field(t, "ln", "lName", "lastName", "last_name", "surname")
            name = (fn + " " + ln).strip() or ""

            # Identity documents
            pan = _get_traveller_field(t, "pan", "panNumber", "pan_number", "panNo")
            passport = _get_traveller_field(t, "pNum", "passportNumber", "passport_number",
                                            "passport", "passportNo")
            nationality = _get_traveller_field(t, "nationality", "nat", "nationalityCode")
            dob = _get_traveller_field(t, "dob", "dateOfBirth", "date_of_birth", "birthDate")
            passport_expiry = _get_traveller_field(t, "pDoE", "passportExpiry", "passport_expiry",
                                                   "expiryDate")

            # Build identity string
            parts: list[str] = []
            if name:
                parts.append(f"Name: {name}")
            if pan:
                parts.append(f"PAN: {pan}")
            if passport:
                parts.append(f"Passport: {passport}")
            if nationality and passport:
                parts.append(f"Nationality: {nationality}")
            if dob:
                parts.append(f"DOB: {dob}")
            if passport_expiry and passport:
                parts.append(f"Expiry: {passport_expiry}")

            identity_str = " | ".join(parts) if parts else "(no identity data)"
            label = f"Room {r_idx+1} Guest {g_idx+1} ({pt})"
            lines.append(f"{label} : {identity_str}")

    if lines:
        plural = "s" if total_guests != 1 else ""
        result.add("INFO", "TRAVELLER_IDENTITY",
            f"{total_guests} guest{plural} in {len(rooms)} room{'s' if len(rooms) != 1 else ''}\n"
            + "\n".join(lines))


def validate_test_case_spec(case_dir: Path, result: CaseResult, detail_req: dict | None, traveller_source: dict | None, search_req: dict | None = None) -> None:
    """Validate spec: rooms/guests in search_req, detail_req, and hold/book all match documented spec."""
    spec = _spec_for(case_dir.name)
    if not spec:
        return

    expected_rooms: int | None = spec.get("rooms")
    expected_adults: list[int] | None = spec.get("adults")
    expected_children: list[int] | None = spec.get("children")
    children_alt: list[int] | None = spec.get("children_alt")

    if expected_rooms is None or expected_adults is None or expected_children is None:
        return  # TC 9 — no traveller spec

    # ---- helpers ----

    def _fmt_room(a: int, c: int) -> str:
        ad = f"{a} Adult" + ("s" if a != 1 else "")
        ch = (f", {c} Child" + ("ren" if c > 1 else "")) if c > 0 else ", 0 Children"
        return ad + ch

    def _spec_summary() -> str:
        """One-line spec description e.g. '3 Rooms — Room 1: 2 Adults, 2 Children | Room 2: 3 Adults, 1 Child | Room 3: 2 Adults, 1 Child'"""
        rooms_str = " | ".join(
            f"Room {i+1}: {_fmt_room(a, c)}"
            for i, (a, c) in enumerate(zip(expected_adults, expected_children))
        )
        return f"{expected_rooms} Room{'s' if expected_rooms != 1 else ''} — {rooms_str}"

    def _rooms_desc(rooms_norm: list[dict]) -> str:
        """Human-readable description of actual rooms e.g. '2 Rooms (Room 1: 2 Adults, 1 Child | Room 2: 2 Adults, 1 Child)'."""
        n = len(rooms_norm)
        detail = " | ".join(
            f"Room {i+1}: {_fmt_room(r.get('adults', 0), r.get('children', 0))}"
            for i, r in enumerate(rooms_norm)
        )
        return f"{n} Room{'s' if n != 1 else ''} ({detail})"

    def _check_source(rooms_norm: list[dict]) -> list[str]:
        """Return list of human-readable mismatch descriptions (empty = all OK)."""
        errs: list[str] = []

        # Room count mismatch — show full expected vs actual breakdown
        if len(rooms_norm) != expected_rooms:
            expected_desc = _spec_summary()
            actual_desc   = _rooms_desc(rooms_norm)
            errs.append(
                f"Room combination mismatch\n"
                f"    Expected : {expected_desc}\n"
                f"    Got      : {actual_desc}"
            )
            return errs

        # Per-room adult / child count mismatch
        for i, (exp_a, exp_c) in enumerate(zip(expected_adults, expected_children)):
            try:
                act_a = int(rooms_norm[i].get("adults") or 0)
            except (TypeError, ValueError):
                act_a = 0
            try:
                act_c = int(rooms_norm[i].get("children") or 0)
            except (TypeError, ValueError):
                act_c = 0
            exp_a = int(exp_a)
            exp_c = int(exp_c)
            alt_c = children_alt[i] if children_alt and i < len(children_alt) else None
            if alt_c is not None:
                try:
                    alt_c = int(alt_c)
                except (TypeError, ValueError):
                    alt_c = None
            if act_a != exp_a:
                errs.append(
                    f"Room {i+1} adults — Expected: {exp_a}, Got: {act_a}"
                )
            c_ok = (act_c == exp_c) or (alt_c is not None and act_c == alt_c)
            if not c_ok:
                allowed = f"{exp_c}" if alt_c is None else f"{exp_c} or {alt_c}"
                errs.append(
                    f"Room {i+1} children — Expected: {allowed}, Got: {act_c}"
                )
        return errs

    # ---- gather sources ----
    sr = normalize_rooms(search_req.get("rooms") or _deep_find(search_req, "rooms")) if search_req else []
    dr = normalize_rooms(detail_req.get("rooms") or _deep_find(detail_req, "rooms")) if detail_req else []
    actual_trav = count_travellers_by_room(traveller_source)
    # convert traveller counts to same shape as rooms[]
    trav_rooms = [{"adults": t.get("adults", 0), "children": t.get("children", 0)} for t in actual_trav]

    sr_errs  = _check_source(sr)        if sr        else None
    dr_errs  = _check_source(dr)        if dr        else None
    bk_errs  = _check_source(trav_rooms) if trav_rooms else None

    # ---- emit errors (one per mismatch, pointing to which source) ----
    if sr_errs is not None:
        for e in sr_errs:
            result.add("ERROR", "TEST_CASE_SPEC", f"Search Request — {e}")
    if dr_errs is not None:
        for e in dr_errs:
            result.add("ERROR", "TEST_CASE_SPEC", f"Detail Request — {e}")
    if bk_errs is not None:
        for e in bk_errs:
            result.add("ERROR", "TEST_CASE_SPEC", f"Booking Request — {e}")

    # ---- single consolidated INFO line ----
    passed: list[str] = []
    if sr_errs  == []: passed.append("Search Request")
    if dr_errs  == []: passed.append("Detail Request")
    if bk_errs  == []: passed.append("Booking Request")

    spec_line = _spec_summary()
    if passed:
        result.add("INFO", "TEST_CASE_SPEC",
            f"{spec_line} — matched in: {', '.join(passed)}")
    elif sr_errs is None and dr_errs is None and bk_errs is None:
        result.add("WARN", "TEST_CASE_SPEC",
            f"Spec: {spec_line} — no request files available to verify")

    # ---- identity (PAN / Passport) — only when booking request is present ----
    if not actual_trav:
        return
    has_pan = any(r.get("hasPan") for r in actual_trav)
    has_passport = any(r.get("hasPassport") for r in actual_trav)
    requires_passport = spec.get("requires_passport")
    requires_pan = spec.get("requires_pan")
    no_pan = spec.get("no_pan")

    if requires_passport:
        if has_passport:
            result.add("INFO", "TEST_CASE_SPEC", "Passport (pNum) present — requirement met")
        else:
            result.add("ERROR", "TEST_CASE_SPEC", "Passport required (non-Indian nationality) but pNum missing in travellers")
    if requires_pan:
        if has_pan:
            result.add("INFO", "TEST_CASE_SPEC", "PAN present — requirement met")
        else:
            result.add("ERROR", "TEST_CASE_SPEC", "PAN required but missing in travellers")
    if no_pan:
        if not has_pan:
            result.add("INFO", "TEST_CASE_SPEC", "No PAN — correct for non-Indian nationality")
        else:
            result.add("WARN", "TEST_CASE_SPEC", "Non-Indian nationality booking should not include PAN, but PAN found")

    # TC 10: same PAN across all rooms
    if spec.get("same_pan_across_rooms"):
        rooms_with_pan = sum(1 for r in actual_trav if r.get("hasPan"))
        if rooms_with_pan == expected_rooms:
            result.add("INFO", "TEST_CASE_SPEC",
                f"Same PAN across all {expected_rooms} rooms — PAN present in every room")
        else:
            result.add("WARN", "TEST_CASE_SPEC",
                f"Same PAN across rooms required — PAN found in {rooms_with_pan} of {expected_rooms} rooms")

    # TC 11: same PAN for all guests
    if spec.get("same_pan_for_all_guests"):
        total_guests = sum(r.get("adults", 0) + r.get("children", 0) for r in actual_trav)
        if has_pan:
            result.add("INFO", "TEST_CASE_SPEC",
                f"Same PAN for all {total_guests} guests — PAN present in booking request")

    # TC 13: corporate PAN
    if spec.get("corporate_pan") and has_pan:
        result.add("INFO", "TEST_CASE_SPEC", "Corporate PAN present in booking request")


# Mapping: normalized key names found in combined files → slot names.
# Handles both camelCase and snake_case naming conventions.
_COMBINED_KEY_TO_SLOT: dict[str, str] = {}
for _patterns, _slot in [
    (["searchrequest","hotelsearchrequest","hotellistingrequest","searchreq"],                "search_req"),
    (["searchresponse","hotelsearchresponse","hotellistingresponse","searchres"],              "search_res"),
    (["detailrequest","hoteldetailrequest","hotelpricingrequest","pricerequest","detailreq"],  "detail_req"),
    (["detailresponse","hoteldetailresponse","hotelpricingresponse","priceresponse"],          "detail_res"),
    (["reviewrequest","hotelreviewrequest","reviewreq"],                                       "review_req"),
    (["reviewresponse","hotelreviewresponse","reviewres"],                                     "review_res"),
    (["holdrequest","hotelholdrequest","holdreq"],                                             "hold_req"),
    (["holdresponse","hotelholdresponse","holdres"],                                           "hold_res"),
    (["bookrequest","hotelbookrequest","bookingcreate","bookingrequest","bookingcreaterequest","bookreq"], "book_req"),
    (["bookresponse","hotelbookresponse","bookingcreateresponse","bookingresponse","bookres"],  "book_res"),
    (["confirmholdrequest","confirmholdbookrequest"],                                           "confirm_hold_req"),
    (["confirmholdresponse","confirmholdbookresponse"],                                        "confirm_hold_res"),
    (["bookingdetailrequest","bookdetailrequest","getbookingrequest","bookingdetailreq"],       "booking_detail_req"),
    (["bookingdetailresponse","bookdetailresponse","getbookingresponse","bookingdetailres"],    "booking_detail_res"),
    (["cancelrequest","hotelcancelrequest","cancelbookingrequest","cancelreq"],                 "cancel_req"),
    (["cancelresponse","hotelcancelresponse","cancelbookingresponse","cancelres"],              "cancel_res"),
    (["cancellationpolicyrequest","cancelpolicyrequest"],                                       "cancel_policy_req"),
    (["cancellationpolicyresponse","cancelpolicyresponse"],                                     "cancel_policy_res"),
]:
    for _k in _patterns:
        _COMBINED_KEY_TO_SLOT[_k] = _slot


def extract_slots_from_combined(obj: Any) -> dict[str, Any]:
    """If `obj` is a top-level dict whose keys map to slot names, return those mappings.

    This handles "combined" files where a single JSON file contains the whole
    booking flow under named keys, e.g.:
        { "searchRequest": {...}, "reviewRequest": {...}, "bookRequest": {...} }
    Also handles NDJSON (newline-delimited JSON) passed as a list.
    """
    if isinstance(obj, list):
        # Try to identify each element in the list by its content
        result: dict[str, Any] = {}
        for item in obj:
            slot = _identify_by_content(item)
            if slot and slot not in result:
                result[slot] = item
        return result

    if not isinstance(obj, dict):
        return {}

    # Check if top-level keys map to known slot names
    matched: dict[str, Any] = {}
    for k, v in obj.items():
        if not isinstance(v, dict):
            continue
        norm = normalize_name(k)
        slot = _COMBINED_KEY_TO_SLOT.get(norm)
        if slot:
            matched[slot] = v

    # Only treat as combined file if we matched 2+ slots
    # (avoids treating normal API responses as combined files)
    return matched if len(matched) >= 2 else {}


def _identify_by_content(obj: Any) -> str | None:
    """Guess the slot name for a JSON object based on its fields.

    Checks top-level keys PLUS keys one wrapper level deep (data/result/
    response/hotel/body/payload) so that wrapped responses like
    {"status":"SUCCESS","data":{"reviewHash":"...","options":[...]}} are
    recognised correctly.
    """
    if not isinstance(obj, dict):
        return None
    # Top-level normalised key set
    def _norm(k: str) -> str:
        return k.lower().replace("_", "").replace("-", "")

    keys = {_norm(k) for k in obj}
    # Expand with keys from common envelope wrappers (one level only)
    for wrapper in ("data", "result", "response", "hotel", "body", "payload"):
        inner = obj.get(wrapper)
        if isinstance(inner, dict):
            keys |= {_norm(k) for k in inner}

    # Search request: has hids[] and rooms[] and checkIn
    if "hids" in keys and "rooms" in keys and ("checkin" in keys or "checkindate" in keys):
        return "search_req"
    # Search response: has hotels[] and totalResults
    if "hotels" in keys and "totalresults" in keys:
        return "search_res"
    # Detail response: has reviewHash and options[]
    if "reviewhash" in keys and "options" in keys:
        return "detail_res"
    # Detail request: has hid and rooms[] and checkIn (but not reviewHash)
    if ("hid" in keys or "hotelid" in keys) and "rooms" in keys and "reviewhash" not in keys:
        return "detail_req"
    # Review response: has option (singular) and bookingId
    if "option" in keys and "bookingid" in keys:
        return "review_res"
    # Review request: has reviewHash and optionId but no options[]
    if "reviewhash" in keys and "optionid" in keys and "options" not in keys:
        return "review_req"
    # Book/Hold/Confirm-Hold request: has roomTravellerInfo
    if "roomtravellerinfo" in keys:
        has_payment = "paymentinfos" in keys
        # Confirm-Hold request: has paymentInfos AND a bookingId (the hold to confirm).
        # Regular book request: has paymentInfos but no pre-existing bookingId.
        has_booking_id = any(
            k in keys for k in ("bookingid", "holdbookingid", "holdid", "holdbookingno",
                                 "reservationid", "confirmationid", "referenceid")
        )
        if has_payment and has_booking_id:
            return "confirm_hold_req"
        return "book_req" if has_payment else "hold_req"
    # Booking detail response: has order and itemInfos
    if "order" in keys and "iteminfos" in keys:
        return "booking_detail_res"
    # Cancel response: has bookingId and cancellationPolicy
    if "bookingid" in keys and "cancellationpolicy" in keys:
        return "cancel_res"
    # Cancel request: has bookingId (or holdId) but no roomTravellerInfo/options/reviewHash
    # — small payload with just a booking reference to cancel
    _cancel_bid = any(k in keys for k in ("bookingid", "holdid", "holdbookingid", "reservationid"))
    _cancel_noise = any(k in keys for k in (
        "roomtravellerinfo", "options", "reviewhash", "hids", "hotels", "iteminfos",
    ))
    if _cancel_bid and not _cancel_noise:
        return "cancel_req"

    return None


# ── Headed-text slot mapping ──────────────────────────────────────────────────
# Maps normalised heading text → slot name.
# Normalisation strips arrows, numbers, "TJ", "Hotel", "Test", punctuation.
_HEADING_SLOT_MAP: dict[str, str] = {}
for _headings, _slot_name in [
    (["search request", "hotel search request", "listing request", "hotelsearch"],       "search_req"),
    (["search response", "hotel search response", "listing response"],                   "search_res"),
    (["detail request", "hotel detail request", "detail search request",
      "pricing request", "hotel pricing request",
      "hoteldetail search request", "hoteldetail-search request",
      "hotel detail-search request"],                                                    "detail_req"),
    (["detail response", "hotel detail response", "detail search response",
      "pricing response", "hotel pricing response",
      "hoteldetail search response", "hoteldetail-search response",
      "hotel detail-search response"],                                                   "detail_res"),
    (["review request", "hotel review request"],                                          "review_req"),
    (["review response", "hotel review response"],                                        "review_res"),
    (["hold request", "hotel hold request", "hold booking request"],                      "hold_req"),
    (["hold response", "hotel hold response", "hold booking response"],                   "hold_res"),
    (["confirm hold request", "confirm-hold request", "confirm booking request"],         "confirm_hold_req"),
    (["confirm hold response", "confirm-hold response", "confirm booking response"],      "confirm_hold_res"),
    (["book request", "hotel book request", "booking request", "instant book request"],   "book_req"),
    (["book response", "hotel book response", "booking response"],                        "book_res"),
    (["booking detail request", "hotel booking detail request",
      "get booking request", "booking info request"],                                     "booking_detail_req"),
    (["booking detail response", "hotel booking detail response",
      "get booking response", "booking info response"],                                   "booking_detail_res"),
    (["cancel request", "hotel cancel request", "cancel booking request"],                "cancel_req"),
    (["cancel response", "hotel cancel response", "cancel booking response"],             "cancel_res"),
    (["cancellation policy request", "cancel policy request"],                            "cancel_policy_req"),
    (["cancellation policy response", "cancel policy response"],                          "cancel_policy_res"),
    (["booking detail after cancel request", "hotel detail after cancel request",
      "post cancel booking detail request"],                                              "booking_detail_after_cancel_req"),
    (["booking detail after cancel response", "hotel detail after cancel response",
      "post cancel booking detail response"],                                             "booking_detail_after_cancel_res"),
]:
    for _h in _headings:
        _HEADING_SLOT_MAP[_h] = _slot_name


def _normalise_heading(raw: str) -> str:
    """Strip noise from a potential heading line so it matches _HEADING_SLOT_MAP."""
    s = raw.strip().lower()
    # Remove arrows and separators
    s = re.sub(r'\s*[-=:>|]+\s*$', '', s)      # trailing ->  :  =  |
    s = re.sub(r'^\s*[-=:>|]+\s*', '', s)      # leading  ->  :  =  |
    s = re.sub(r'\s*->\s*|\s*=>\s*|\s*→\s*', ' ', s)  # inline arrows
    # Normalize word-joining hyphens to spaces (hotelDetail-search → hoteldetail search)
    s = re.sub(r'(?<=[a-z0-9])-(?=[a-z0-9])', ' ', s)
    # Remove leading numbers / step labels  e.g. "1." "Step 2:"
    s = re.sub(r'^\d+[\s.\-:)]+', '', s)
    # Remove common noise words that prefix headings in Tripjack exports
    for noise in ("tj test ", "tj test hotel ", "test hotel ", "hotel api ",
                  "tripjack ", "tjtesthotel", "tjtest"):
        if s.startswith(noise):
            s = s[len(noise):]
    return re.sub(r'\s+', ' ', s).strip()


def parse_headed_text_file(text: str) -> dict[str, Any]:
    """Parse a text file where JSON sections are separated by heading labels.

    Supports formats like:
        Search Request
        { ... }

        Search Response
        { ... }

    or with arrows / step numbers:
        1. Search Request ->
        { ... }

        2. Search Response ->
        { ... }

    Returns {slot_name: parsed_json} for every recognised section.
    Only returns a non-empty dict when at least 2 labelled sections are found,
    so normal JSON files are not misidentified as headed-text files.
    """
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []   # [(slot, [json_lines]), ...]
    current_slot: str | None = None
    json_buf: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Is this line a heading?  Only consider lines that:
        #  - are not empty
        #  - do NOT start with JSON structural chars { [ " 0-9
        #  - normalise to a known slot name
        if stripped and stripped[0] not in ('{', '[', '"', '0', '1', '2', '3',
                                             '4', '5', '6', '7', '8', '9'):
            norm = _normalise_heading(stripped)
            slot = _HEADING_SLOT_MAP.get(norm)
            # Skip "static" detail headings — they belong to a different API endpoint
            if "static" in norm and slot in ("detail_req", "detail_res"):
                slot = None
            if slot:
                # Save the section we were collecting
                if current_slot is not None:
                    sections.append((current_slot, json_buf))
                current_slot = slot
                json_buf = []
                continue  # heading line — do not add to json_buf

        if current_slot is not None:
            json_buf.append(line)

    # Save the last section
    if current_slot is not None:
        sections.append((current_slot, json_buf))

    # Require at least 2 sections for ambiguous files, but allow a single section
    # when there is a recognised heading (e.g. a response-only file with a label).
    if len(sections) == 0:
        return {}
    if len(sections) == 1:
        # Only accept a single section if its body has real content.
        body_check = "\n".join(sections[0][1]).strip()
        if len(body_check) < 5:
            return {}

    result: dict[str, Any] = {}
    for slot, buf in sections:
        raw = '\n'.join(buf).strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                # Unwrap HTTP-envelope format inside a section
                env = _unwrap_http_envelope(obj)
                if env is not None:
                    _, obj = env  # use the body; heading already gives us the slot
            if isinstance(obj, (dict, list)):
                result[slot] = obj
        except json.JSONDecodeError:
            # Section body may be a cURL command — try to extract its JSON body
            curl_result = _extract_curl_body(raw)
            if curl_result:
                _, body_text = curl_result
                try:
                    obj = json.loads(body_text)
                    if isinstance(obj, (dict, list)):
                        result[slot] = obj
                except json.JSONDecodeError:
                    pass

    return result


# ── Supplier-format (API Method / Supplier Request / Supplier Response) ───────
# Maps normalised API method name → (req_slot, res_slot)
_SUPPLIER_METHOD_SLOTS: dict[str, tuple[str, str]] = {
    "search":                        ("search_req",                    "search_res"),
    "hotelsearch":                   ("search_req",                    "search_res"),
    "listing":                       ("search_req",                    "search_res"),
    "hotellisting":                  ("search_req",                    "search_res"),
    "detail":                        ("detail_req",                    "detail_res"),
    "hoteldetail":                   ("detail_req",                    "detail_res"),
    "pricing":                       ("detail_req",                    "detail_res"),
    "hotelpricing":                  ("detail_req",                    "detail_res"),
    "review":                        ("review_req",                    "review_res"),
    "hotelreview":                   ("review_req",                    "review_res"),
    "hold":                          ("hold_req",                      "hold_res"),
    "hotelhold":                     ("hold_req",                      "hold_res"),
    "confirmhold":                   ("confirm_hold_req",              "confirm_hold_res"),
    "confirmbooking":                ("confirm_hold_req",              "confirm_hold_res"),
    "book":                          ("book_req",                      "book_res"),
    "booking":                       ("book_req",                      "book_res"),
    "hotelbook":                     ("book_req",                      "book_res"),
    "hotelbooking":                  ("book_req",                      "book_res"),
    "instantbook":                   ("book_req",                      "book_res"),
    "bookingdetail":                 ("booking_detail_req",            "booking_detail_res"),
    "getbooking":                    ("booking_detail_req",            "booking_detail_res"),
    "hotelgetbooking":               ("booking_detail_req",            "booking_detail_res"),
    "bookinginfo":                   ("booking_detail_req",            "booking_detail_res"),
    "cancel":                        ("cancel_req",                    "cancel_res"),
    "hotelcancel":                   ("cancel_req",                    "cancel_res"),
    "cancelbooking":                 ("cancel_req",                    "cancel_res"),
    "cancellationpolicy":            ("cancel_policy_req",             "cancel_policy_res"),
    "cancelpolicy":                  ("cancel_policy_req",             "cancel_policy_res"),
    "bookingdetailaftercancel":      ("booking_detail_after_cancel_req", "booking_detail_after_cancel_res"),
    "postcancel":                    ("booking_detail_after_cancel_req", "booking_detail_after_cancel_res"),
    "hotelbookingdetailaftercancel": ("booking_detail_after_cancel_req", "booking_detail_after_cancel_res"),
    # Variations seen in real uploads
    "bookingdetails":                ("booking_detail_req",             "booking_detail_res"),
    "bookingcancellation":           ("cancel_req",                     "cancel_res"),
    "cancellation":                  ("cancel_req",                     "cancel_res"),
    "hotelbookingcancel":            ("cancel_req",                     "cancel_res"),
}


def _norm_api_method(raw: str) -> str:
    """Normalise API method name for _SUPPLIER_METHOD_SLOTS lookup."""
    s = raw.strip().lower()
    s = re.sub(r'\s+api\s*$', '', s)   # strip trailing " API"
    return re.sub(r'[^a-z0-9]', '', s)


def _extract_first_json(text: str) -> Any | None:
    """Find and parse the first complete JSON object or array in *text*."""
    start = -1
    for i, ch in enumerate(text):
        if ch in ('{', '['):
            start = i
            break
    if start < 0:
        return None
    candidate = text[start:]
    # Strip trailing separator lines (e.g. "----") and trailing whitespace
    candidate = re.sub(r'\n-{5,}[\s\S]*$', '', candidate).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Try up to the last closing bracket
    end = max(candidate.rfind('}'), candidate.rfind(']'))
    if end > 0:
        try:
            return json.loads(candidate[:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def parse_supplier_format_file(text: str) -> dict[str, Any]:
    """Parse the 'API Method / Supplier Request / Supplier Response' combined format.

    Each block in the file looks like::

        API Method :- Review API
        URL :- https://...

        Supplier Request:-

        { ... request JSON ... }

        ----

        Supplier Response:-

        { ... response JSON ... }

    Multiple blocks (one per API call) may appear in the same file.
    Returns {slot_name: parsed_json} merged across all recognised blocks.
    """
    # Normalise Windows (CRLF) and old Mac (CR) line endings so every regex
    # below can rely on plain \n boundaries.
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    text_lower = text.lower()
    if "api method" not in text_lower:
        return {}
    if "supplier request" not in text_lower and "supplier response" not in text_lower:
        # Accept bare "Request:-" / "Response:-" only when "API Method" is present
        if "request" not in text_lower and "response" not in text_lower:
            return {}

    # Split the file into per-API blocks at each "API Method" header line
    block_re = re.compile(r'(?im)^[ \t]*api\s+method\s*[:\-]+', re.MULTILINE)
    split_points = [m.start() for m in block_re.finditer(text)]
    if not split_points:
        return {}

    blocks: list[str] = []
    for i, sp in enumerate(split_points):
        end = split_points[i + 1] if i + 1 < len(split_points) else len(text)
        blocks.append(text[sp:end])

    # Markers that indicate request / response subsections.
    # Allow arbitrary prefix words (e.g. "Booking Supplier Response:-").
    req_re = re.compile(r'(?im)^[ \t]*(?:\w+[ \t]+)*request\s*:-[ \t]*$', re.MULTILINE)
    res_re = re.compile(r'(?im)^[ \t]*(?:\w+[ \t]+)*response\s*:-[ \t]*$', re.MULTILINE)

    result: dict[str, Any] = {}

    for block in blocks:
        # Extract the API method name from the first line
        first_line_m = re.match(r'(?i)[ \t]*api\s+method\s*[:\-]+[ \t]*(.*)', block)
        if not first_line_m:
            continue
        method_raw = first_line_m.group(1).strip().split('\n')[0].strip()
        method_key = _norm_api_method(method_raw)
        slots = _SUPPLIER_METHOD_SLOTS.get(method_key)
        if not slots:
            continue
        req_slot, res_slot = slots

        req_m = req_re.search(block)
        res_m = res_re.search(block)

        if req_m:
            req_end = res_m.start() if res_m else len(block)
            req_text = block[req_m.end():req_end]
            obj = _extract_first_json(req_text)
            if isinstance(obj, (dict, list)) and req_slot not in result:
                result[req_slot] = obj

        if res_m:
            res_text = block[res_m.end():]
            obj = _extract_first_json(res_text)
            if isinstance(obj, (dict, list)) and res_slot not in result:
                result[res_slot] = obj

    return result


def _try_ndjson(text: str) -> list[Any] | None:
    """Try to parse text as newline-delimited JSON (one JSON object per line)."""
    objects: list[Any] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError:
            return None  # Not clean NDJSON
    return objects if len(objects) >= 2 else None


def _extract_booking_status(obj: Any) -> str | None:
    """Find the first string-valued 'status' or 'bookingStatus' anywhere in obj.

    Strategy (priority order):
      1. obj.bookingStatus or obj.order.status / obj.order.bookingStatus
      2. obj.orders[0].status
      3. obj.data.* (recurse into common wrapper)
      4. obj.status if it is a plain string (skip HTTP envelope dicts)
      5. Deep recursive scan for any 'status' string value

    Works for any JSON structure including nested envelopes from uploaded files.
    """
    if not isinstance(obj, dict):
        return None

    # bookingStatus key (highest priority — most specific)
    val = obj.get("bookingStatus")
    if isinstance(val, str) and val.strip():
        return val.strip()

    # order.status / order.bookingStatus
    order = obj.get("order")
    if isinstance(order, dict):
        v = order.get("status") or order.get("bookingStatus")
        if isinstance(v, str) and v.strip():
            return v.strip()

    # orders[0].status
    orders = obj.get("orders")
    if isinstance(orders, list) and orders and isinstance(orders[0], dict):
        v = orders[0].get("status") or orders[0].get("bookingStatus")
        if isinstance(v, str) and v.strip():
            return v.strip()

    # data wrapper — recurse
    data_block = obj.get("data")
    if isinstance(data_block, dict):
        found = _extract_booking_status(data_block)
        if found:
            return found

    # Top-level status — only accept plain strings, not HTTP-envelope dicts
    val = obj.get("status")
    if isinstance(val, str) and val.strip():
        return val.strip()

    # Deep scan: find first string 'status' value anywhere in the response
    def _deep_status(o: Any) -> str | None:
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() in ("status", "bookingstatus") and isinstance(v, str) and v.strip():
                    return v.strip()
                found = _deep_status(v)
                if found:
                    return found
        elif isinstance(o, list):
            for item in o:
                found = _deep_status(item)
                if found:
                    return found
        return None

    return _deep_status(obj)


def _collect_key(obj: Any, key: str, found: "set[str] | None" = None) -> "set[str]":
    """Collect every string/int value stored under exactly `key` (case-insensitive) at any depth."""
    found = found if found is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == key and isinstance(v, (str, int)) and str(v).strip():
                found.add(str(v).strip())
            elif isinstance(v, (dict, list)):
                _collect_key(v, key, found)
    elif isinstance(obj, list):
        for item in obj:
            _collect_key(item, key, found)
    return found


def _is_cancelled(status: "str | None") -> bool:
    return (status or "").strip().upper() in ("CANCELLED", "CANCELED")


def _booking_detail_records(case_dir: Path) -> "list[tuple[str, str, str]]":
    """Return (bookingId, status, file name) for every booking-detail response in a case folder."""
    records: list[tuple[str, str, str]] = []
    for fp in _all_readable_files(case_dir):
        loaded = load_json(fp)
        if isinstance(loaded, dict) and "__headed__" in loaded:
            objs = list(loaded["__headed__"].values())
        elif isinstance(loaded, list):
            objs = loaded
        else:
            objs = [loaded]
        for obj in objs:
            if not isinstance(obj, dict) or "__parse_error__" in obj:
                continue
            order = _get_nested(obj, "order")
            if not isinstance(order, dict):
                continue  # not a booking-detail response (e.g. a cancel API reply)
            status = _extract_booking_status(obj)
            bid = order.get("bookingId") or _deep_find(obj, "bookingId")
            if bid and status:
                records.append((str(bid), status.upper(), fp.name))
    return records


def validate_cancel_all(case_dir: Path, result: CaseResult) -> None:
    """Test Case 14: every test booking must have a booking-detail response with status CANCELLED."""
    records = _booking_detail_records(case_dir)
    if not records:
        result.add(
            "ERROR", "CANCEL_ALL",
            "No Booking Detail response found. For every test booking, add the Booking Detail "
            "response that shows status CANCELLED to this folder.",
        )
        return

    # One verdict per booking: CANCELLED if any of its responses shows CANCELLED
    by_id: dict[str, tuple[str, str]] = {}
    for bid, status, fname in records:
        if bid not in by_id or (_is_cancelled(status) and not _is_cancelled(by_id[bid][0])):
            by_id[bid] = (status, fname)

    rows = []
    for bid, (status, fname) in sorted(by_id.items()):
        ok = _is_cancelled(status)
        if ok:
            result.cancelled_ids.add(bid)
        else:
            hint = (" - cancellation still pending, fetch Booking Detail again once it shows CANCELLED"
                    if "PENDING" in status else "")
            result.add("ERROR", "CANCEL_ALL",
                       f"Booking {bid} has status {status}, expected CANCELLED ({fname}){hint}")
        rows.append(f"{bid} : {status}  [{'matched' if ok else 'unmatched'}]")
    done = sum(1 for st, _ in by_id.values() if _is_cancelled(st))
    result.add("INFO", "CANCEL_ALL",
               f"{done} of {len(by_id)} booking(s) show CANCELLED\n" + "\n".join(rows))


def apply_cancel_coverage(results: "list[CaseResult]") -> None:
    """Test Case 14 must cover every booking created in the other cases.

    A booking counts as cancelled when ANY case holds a booking-detail response
    showing CANCELLED for it.  Runs after all cases are validated.
    """
    tc14 = [r for r in results if _spec_for(r.case_name).get("cancel_all")]
    if not tc14:
        return
    cancelled: set[str] = set().union(*(r.cancelled_ids for r in results))
    owners: dict[str, list[str]] = {}
    for r in results:
        if _spec_for(r.case_name).get("cancel_all"):
            continue
        for bid in r.booking_ids:
            owners.setdefault(bid, []).append(r.case_name)
    missing = {b: c for b, c in owners.items() if b not in cancelled}
    for r in tc14:
        if missing:
            lines = "\n".join(f"{b} : created in {', '.join(c)}  [unmatched]" for b, c in sorted(missing.items()))
            r.add("ERROR", "CANCEL_ALL",
                  f"{len(missing)} test booking(s) have no Booking Detail response with status CANCELLED\n{lines}")
        elif owners:
            r.add("INFO", "CANCEL_ALL", f"All {len(owners)} test booking(s) from the other cases are cancelled")


def json_error_details(raw: str) -> str:
    """Explain where a JSON text breaks: line, column, reason and the offending line."""
    if not raw.strip():
        return "Problem : the file is empty"
    try:
        json.loads(raw)
        return "Problem : the file is not in a supported request/response format"
    except json.JSONDecodeError as e:
        lines = raw.splitlines() or [raw]
        bad = lines[e.lineno - 1] if 0 < e.lineno <= len(lines) else ""
        start = max(0, e.colno - 60)
        snippet = (("…" if start else "") + bad[start:e.colno + 40].strip() + ("…" if len(bad) > e.colno + 40 else ""))
        return (f"Where : line {e.lineno}, column {e.colno}\n"
                f"Problem : {e.msg}\n"
                f"Text : {snippet or '(end of file)'}")


def validate_case(case_dir: Path, strict_option_id: bool = False) -> CaseResult:
    result = CaseResult(case_name=case_dir.name)
    paths: dict[str, Path | None] = {
        k: find_file(case_dir, v, skip_if=_SKIP_IF.get(k))
        for k, v in FILE_PATTERNS.items()
    }
    result.files = {k: str(p) if p else "" for k, p in paths.items()}

    data: dict[str, Any] = {}
    for key, path in paths.items():
        if path:
            loaded = load_json(path)
            if isinstance(loaded, dict) and "__headed__" in loaded:
                # Headed-text file: fill any empty slots from its sections
                for _slot, _obj in loaded["__headed__"].items():
                    if _slot not in data or not data[_slot]:
                        data[_slot] = _obj
                # If the file's own matched slot (key) was not filled by any section
                # (e.g. 2.pricing.RS.txt has URL:/pricing which maps to detail_req,
                # but the file belongs in detail_res), store the body under key too.
                if (key not in data or not data[key]) and loaded["__headed__"]:
                    data[key] = next(iter(loaded["__headed__"].values()))
                result.add("INFO", "FILES",
                    f"{path.name}: headed-text file — extracted "
                    f"{len(loaded['__headed__'])} section(s): "
                    + ", ".join(sorted(loaded["__headed__"].keys())))
            elif isinstance(loaded, dict) and "__parse_error__" in loaded:
                raw = path.read_text(encoding="utf-8-sig").strip()
                if raw.startswith("http"):
                    result.add("INFO", "FILES",
                        f"{path.name}: URL reference (not JSON)\nURL : {raw}")
                else:
                    result.add("ERROR", "JSON_PARSE", f"{path.name}: invalid JSON\n" + json_error_details(raw))
            else:
                data[key] = loaded

    # ── Combined-file extraction ──────────────────────────────────────────────
    # Pass 1: check already-loaded files for combined content
    for _loaded_val in list(data.values()):
        for _slot, _obj in extract_slots_from_combined(_loaded_val).items():
            if _slot not in data or not data[_slot]:
                data[_slot] = _obj

    # Pass 2: scan ALL readable files in the case directory.
    # Files not matched by find_file (e.g. combined files, no-extension files,
    # .text files) are tried here so nothing is missed.
    _matched_paths = set(filter(None, paths.values()))
    for _p in _all_readable_files(case_dir):
        if _p in _matched_paths:
            continue  # already processed via find_file
        _raw_obj = load_json(_p)
        if _raw_obj is None:
            continue
        # Headed-text file (highest priority for unmatched files)
        if isinstance(_raw_obj, dict) and "__headed__" in _raw_obj:
            for _slot, _obj in _raw_obj["__headed__"].items():
                if _slot not in data or not data[_slot]:
                    data[_slot] = _obj
            continue
        if isinstance(_raw_obj, dict) and ("__parse_error__" in _raw_obj):
            continue
        # Named combined JSON object
        for _slot, _obj in extract_slots_from_combined(_raw_obj).items():
            if _slot not in data or not data[_slot]:
                data[_slot] = _obj
        # Single-object content-based identification
        if isinstance(_raw_obj, dict) and not extract_slots_from_combined(_raw_obj):
            _slot = _identify_by_content(_raw_obj)
            if _slot and (_slot not in data or not data[_slot]):
                data[_slot] = _raw_obj

    search_req = data.get("search_req") or {}
    search_res = data.get("search_res") or {}
    detail_req = data.get("detail_req") or {}
    detail_res = data.get("detail_res") or {}
    review_req = data.get("review_req") or {}
    review_res = data.get("review_res") or {}
    hold_req = data.get("hold_req") or {}
    book_req = data.get("book_req") or {}
    confirm_req = data.get("confirm_hold_req") or {}

    # ── Smart slot reclassification ──────────────────────────────────────────
    # Name-based matching runs first and may put files in the wrong slot when
    # the file name doesn't reflect the actual API step.  These post-load
    # checks use content signals to move misidentified payloads to the right
    # slot — covering TC1/TC3/TC6 hold flows and all other cases.

    def _norm_keys(obj: dict) -> set[str]:
        return {k.lower().replace("_", "").replace("-", "") for k in obj} if obj else set()

    def _has_hold_status(obj: Any) -> bool:
        """True if obj contains any booking-status value that means HOLD."""
        if isinstance(obj, dict):
            for v in obj.values():
                if str(v).upper() in ("HOLD", "ON_HOLD", "ONHOLD",
                                      "PENDING_CONFIRM", "PRE_BOOK", "HOLD_CONFIRMED"):
                    return True
                if isinstance(v, (dict, list)) and _has_hold_status(v):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if _has_hold_status(item):
                    return True
        return False

    _HOLD_BID_KEYS = frozenset((
        "bookingid", "holdbookingid", "holdid", "holdbookingno",
        "reservationid", "confirmationid", "referenceid",
    ))

    # 1. book_req → hold_req  (TC1, TC6: hold request misnamed as "Book Request")
    #    Signal: has roomTravellerInfo but NO paymentInfos, and hold_req slot is empty.
    if book_req and not hold_req:
        _bk = _norm_keys(book_req)
        _bk_has_rti = "roomtravellerinfo" in _bk or bool(_deep_find(book_req, "roomTravellerInfo"))
        _bk_has_pay = "paymentinfos" in _bk or bool(_deep_find(book_req, "paymentInfos"))
        if _bk_has_rti and not _bk_has_pay:
            hold_req = book_req
            data["hold_req"] = book_req
            book_req = {}
            data["book_req"] = {}
            if paths.get("book_req"):
                paths["hold_req"] = paths["book_req"]
                paths["book_req"] = None

    # 2. book_req → confirm_hold_req  (TC3: confirm-hold misnamed as "Book Request")
    #    Signal: has paymentInfos AND an existing bookingId, AND hold_req is present.
    if book_req and not confirm_req and hold_req:
        _bk = _norm_keys(book_req)
        _bk_has_pay2 = "paymentinfos" in _bk or bool(_deep_find(book_req, "paymentInfos"))
        _bk_has_bid2 = bool(_bk & _HOLD_BID_KEYS) or any(
            bool(_deep_find(book_req, k)) for k in _HOLD_BID_KEYS
        )
        if _bk_has_pay2 and _bk_has_bid2:
            confirm_req = book_req
            data["confirm_hold_req"] = book_req
            book_req = {}
            data["book_req"] = {}
            if paths.get("book_req"):
                paths["confirm_hold_req"] = paths["book_req"]
                paths["book_req"] = None

    # 3. book_res → hold_res  (TC1, TC3, TC6: hold response misnamed as "Book Response")
    #    Signal: response contains a HOLD-status value and hold_res slot is empty.
    _book_res_raw = data.get("book_res") or {}
    if _book_res_raw and not data.get("hold_res") and (hold_req or data.get("hold_req")):
        if _has_hold_status(_book_res_raw):
            data["hold_res"] = _book_res_raw
            data["book_res"] = {}
            if paths.get("book_res"):
                paths["hold_res"] = paths["book_res"]
                paths["book_res"] = None

    # 4. book_res → confirm_hold_res  (TC3: confirm-hold response misnamed as "Book Response")
    #    Signal: confirm_hold_req is now populated but confirm_hold_res is empty,
    #    and book_res still has data (it was the confirm step's response).
    _book_res_raw = data.get("book_res") or {}
    if _book_res_raw and not data.get("confirm_hold_res") and (confirm_req or data.get("confirm_hold_req")):
        data["confirm_hold_res"] = _book_res_raw
        data["book_res"] = {}
        if paths.get("book_res"):
            paths["confirm_hold_res"] = paths["book_res"]
            paths["book_res"] = None

    # Refresh local variables after reclassification
    hold_req    = data.get("hold_req") or {}
    book_req    = data.get("book_req") or {}
    confirm_req = data.get("confirm_hold_req") or {}

    # --- correlationId ---
    corr_values: dict[str, str] = {}
    for label, obj in [
        ("search", search_req),
        ("detail", detail_req),
        ("review", review_req),
    ]:
        if isinstance(obj, dict) and obj.get("correlationId"):
            corr_values[label] = str(obj["correlationId"])
    if len(set(corr_values.values())) > 1:
        result.add("ERROR", "CORRELATION_ID", f"correlationId mismatch: {corr_values}")
    elif corr_values:
        result.add("INFO", "CORRELATION_ID", f"correlationId OK:{next(iter(corr_values.values()))}")

    # --- dates & room combo (search vs detail) ---
    if search_req and detail_req:
        for field in ("checkIn", "checkOut", "nationality", "currency"):
            sv = search_req.get(field) or _deep_find(search_req, field)
            dv = detail_req.get(field) or _deep_find(detail_req, field)
            if sv is not None and dv is not None and sv != dv:
                result.add("ERROR", "SEARCH_DETAIL_DATES", f"{field}: search {sv!r} vs detail {dv!r}")
        _sr_rooms = search_req.get("rooms") or _deep_find(search_req, "rooms")
        _dr_rooms = detail_req.get("rooms") or _deep_find(detail_req, "rooms")
        if rooms_signature(_sr_rooms) != rooms_signature(_dr_rooms):
            result.add(
                "ERROR",
                "ROOM_COMBO",
                f"rooms[] differ search vs detail: {_sr_rooms!r} vs {_dr_rooms!r}",
            )
    # --- nationality / timeoutMs / currency info ---
    _req_meta_fields = ("nationality", "timeoutMs", "currency")
    _req_meta_sources = [
        ("Search Request", search_req),
        ("Detail Request", detail_req),
    ]
    _meta_lines: list[str] = []
    for _field in _req_meta_fields:
        _row_parts: list[str] = []
        for _src_label, _src_obj in _req_meta_sources:
            _val = (_src_obj.get(_field) if isinstance(_src_obj, dict) else None) \
                   or _deep_find(_src_obj, _field)
            _row_parts.append(f"{_src_label}: {_val if _val is not None else '(not found)'}")
        _meta_lines.append(f"{_field:<14} — {' | '.join(_row_parts)}")
    if search_req or detail_req:
        result.add("INFO", "REQUEST_META",
                   "nationality / timeoutMs / currency\n" + "\n".join(_meta_lines))

    # ── Hotel ID full chain: Search Request → Search Response → Detail Request
    #                        → Detail Response → Review Request → Review Response ──

    # Extract hotel ID from each stage
    _hids_raw = search_req.get("hids") or _deep_find(search_req, "hids") or []
    hids_search_req: set[str] = {str(h) for h in _hids_raw if h}
    single_hid_search = hotel_id_from(search_req, "hid", "hotelId")
    if single_hid_search:
        hids_search_req.add(single_hid_search)

    # Hotel IDs that appear in the search response hotels list
    hids_search_res: set[str] = set()
    for hotel in (_get_nested_list(search_res, "hotels") or []):
        if isinstance(hotel, dict):
            h = hotel_id_from(hotel, "hid", "hotelId")
            if h:
                hids_search_res.add(h)

    hid_detail_req = hotel_id_from(detail_req, "hid", "hotelId")
    hid_detail_res = hotel_id_from(detail_res, "hotelId", "hid")
    hid_review_req = hotel_id_from(review_req, "hid", "hotelId")
    hid_review_res = hotel_id_from(review_res, "hotelId", "hid")

    # The hotel being tracked (use detail_req as the anchor)
    tracked = hid_detail_req or hid_review_req

    chain_errors: list[str] = []
    chain_steps: list[tuple[str, str]] = []   # (label, status)

    # Step 1 — Search Request: tracked hid must be in hids[]
    if tracked and hids_search_req:
        if tracked in hids_search_req:
            chain_steps.append(("Search Request", f"{tracked} (in hids[])"))
        else:
            chain_errors.append(
                f"Search Request: hid {tracked!r} not in hids[] {sorted(hids_search_req)}")
            chain_steps.append(("Search Request", f"MISMATCH — {tracked} not in hids[]"))
    elif tracked and search_req:
        chain_steps.append(("Search Request", "(hids[] not found — cannot verify)"))

    # Step 2 — Search Response: tracked hid must appear in hotels[]
    if tracked:
        if hids_search_res:
            if tracked in hids_search_res:
                chain_steps.append(("Search Response", f"{tracked} (in hotels[])"))
            else:
                chain_errors.append(
                    f"Search Response: hid {tracked!r} not found in hotels[] "
                    f"({len(hids_search_res)} hotels returned)")
                chain_steps.append(("Search Response", f"MISMATCH — not in hotels[]"))
        elif search_res and _value_exists_anywhere(search_res, tracked):
            chain_steps.append(("Search Response", f"{tracked} (found via deep scan)"))
        elif search_res:
            chain_steps.append(("Search Response", "(hotels[] absent — deep scan also negative)"))

    # Step 3 — Detail Request
    if hid_detail_req:
        chain_steps.append(("Detail Request", hid_detail_req))
    elif detail_req:
        chain_steps.append(("Detail Request", "(hid not found)"))

    # Step 4 — Detail Response
    if hid_detail_res:
        chain_steps.append(("Detail Response", hid_detail_res))
        if hid_detail_req and hid_detail_req != hid_detail_res:
            chain_errors.append(
                f"Detail Request -> Detail Response mismatch: "
                f"{hid_detail_req!r} vs {hid_detail_res!r}")
    elif detail_res:
        chain_steps.append(("Detail Response", "(hotelId not found)"))

    # Step 5 — Review Request
    if hid_review_req:
        chain_steps.append(("Review Request", hid_review_req))
        if hid_detail_res and hid_detail_res != hid_review_req:
            chain_errors.append(
                f"Detail Response -> Review Request mismatch: "
                f"{hid_detail_res!r} vs {hid_review_req!r}")
    elif review_req:
        chain_steps.append(("Review Request", "(hid not found)"))

    # Step 6 — Review Response
    if hid_review_res:
        chain_steps.append(("Review Response", hid_review_res))
        if hid_review_req and hid_review_req != hid_review_res:
            chain_errors.append(
                f"Review Request -> Review Response mismatch: "
                f"{hid_review_req!r} vs {hid_review_res!r}")
    elif review_res:
        chain_steps.append(("Review Response", "(hotelId not found)"))

    # Emit errors
    for err in chain_errors:
        result.add("ERROR", "HOTEL_ID", err)

    # Emit one consolidated INFO with the full chain
    if chain_steps:
        # Tag each step as [matched] / [unmatched] relative to `tracked`
        def _hotel_tag(val: str) -> str:
            if not val or not tracked:
                return ""
            skip = {"(hid not found)", "(hotelId not found)", "(hids[] not found — cannot verify)",
                    "(hotels[] absent — deep scan also negative)"}
            if val in skip or val.startswith("MISMATCH") or "not found" in val:
                return "  [unmatched]"
            # Extract just the ID (everything before the first space/paren)
            bare = val.split(" ")[0].split("(")[0].strip()
            return "  [matched]" if bare == tracked else "  [unmatched]"

        chain_str = "\n".join(
            f"{lbl:<18}: {val}{_hotel_tag(val)}" for lbl, val in chain_steps
        )
        # Consistency = no link errors AND every actual hotel ID value is the same
        raw_ids = {v for v in [hid_detail_req, hid_detail_res, hid_review_req, hid_review_res] if v}
        if not chain_errors and len(raw_ids) <= 1:
            result.add("INFO", "HOTEL_ID",
                f"hotel ID consistent across full chain\n{chain_str}")
        elif not chain_errors:
            result.add("INFO", "HOTEL_ID",
                f"hotel ID chain checked\n{chain_str}")
        else:
            result.add("INFO", "HOTEL_ID",
                f"hotel ID chain (see errors above)\n{chain_str}")

    # ── REVIEW_HASH ─────────────────────────────────────────────────────────
    # Rule: take reviewHash from Review Request → confirm the exact same value
    #       exists anywhere in the Detail Response.
    #
    # Extraction strategy (first hit wins):
    #   1. JSON _deep_find on parsed review_req dict
    #   2. Raw-text regex on every data file in the case dir (handles
    #      malformed JSON, text files, headed-text combined files)
    #
    # Search strategy (first hit wins):
    #   1. JSON _value_exists_anywhere on parsed detail_res dict
    #   2. Raw-text substring on the matched detail_res file
    #   3. Exhaustive raw-text search across ALL data files in case dir
    #      (fallback when file-slot mapping is imperfect — e.g. the detail
    #      response came from a headed-text file matched under a different slot)
    _rreq_path = paths.get("review_req")
    _dres_path = paths.get("detail_res")
    _all_case_files = list(_all_readable_files(case_dir))

    # ---- extract reviewHash from Review Request ----
    hash_review_req = _deep_find(review_req, "reviewHash") if review_req else None
    if not hash_review_req and _rreq_path:
        hash_review_req = _raw_find_key(_rreq_path, "reviewHash")
    if not hash_review_req:
        # raw-text scan of all files — find the first occurrence of "reviewHash"
        for _fp in _all_case_files:
            hash_review_req = _raw_find_key(_fp, "reviewHash")
            if hash_review_req:
                break

    # ---- extract reviewHash from Detail Response (for explicit side-by-side comparison) ----
    hash_detail_res = _deep_find(detail_res, "reviewHash") if detail_res else None
    if not hash_detail_res and _dres_path:
        hash_detail_res = _raw_find_key(_dres_path, "reviewHash")

    _has_rreq = bool(review_req) or bool(_rreq_path)
    _has_dres = bool(detail_res) or bool(_dres_path)

    if not _has_rreq:
        result.add("WARN", "REVIEW_HASH",
            "Review Request not found — cannot check reviewHash")
    elif not _has_dres:
        result.add("WARN", "REVIEW_HASH",
            "Detail Response not found — cannot check reviewHash")
    elif not hash_review_req:
        result.add("ERROR", "REVIEW_HASH",
            "reviewHash not found in Review Request "
            "(searched all files at all depths)")
    else:
        # 1. JSON value scan
        found_hash = _value_exists_anywhere(detail_res, hash_review_req) if detail_res else False
        # 2. Raw-text on matched detail_res file
        if not found_hash and _dres_path:
            found_hash = _raw_contains(_dres_path, hash_review_req)
        # 3. Exhaustive: all data files in the case dir
        #    (skip whichever file the hash was taken FROM to avoid self-match)
        if not found_hash:
            _skip = {_rreq_path} if _rreq_path else set()
            for _fp in _all_case_files:
                if _fp in _skip:
                    continue
                if _raw_contains(_fp, hash_review_req):
                    found_hash = True
                    break

        # Build side-by-side comparison with explicit [matched] / [unmatched] tags
        # Also accept partial match: review request sends hash prefix before "|"
        # e.g. detail_res has "ABC|correlationId" and review_req sends "ABC"
        _dres_hash_prefix = hash_detail_res.split("|")[0] if hash_detail_res else None
        exactly = (hash_detail_res and hash_review_req and (
            hash_detail_res == hash_review_req
            or _dres_hash_prefix == hash_review_req
        ))
        dr_tag  = "  [matched]"   if exactly else ("  [unmatched]" if hash_detail_res else "")
        rr_tag  = "  [matched]"   if exactly else ("  [unmatched]" if _has_dres else "")
        _rh_msg = (
            f"Detail Response : {hash_detail_res or '(not found)'}{dr_tag}\n"
            f"Review Request  : {hash_review_req}{rr_tag}"
        )

        if found_hash or exactly:
            result.add("INFO", "REVIEW_HASH", f"reviewHash matched\n{_rh_msg}")
        else:
            result.add("ERROR", "REVIEW_HASH", f"reviewHash MISMATCH\n{_rh_msg}")

    # ── OPTION_ID ────────────────────────────────────────────────────────────
    # Same multi-strategy approach as REVIEW_HASH.

    # ---- extract optionId ----
    opt_id_review_req = _deep_find(review_req, "optionId") if review_req else None
    if not opt_id_review_req and _rreq_path:
        opt_id_review_req = _raw_find_key(_rreq_path, "optionId")
    if not opt_id_review_req:
        for _fp in _all_case_files:
            opt_id_review_req = _raw_find_key(_fp, "optionId")
            if opt_id_review_req:
                break

    detail_options = _get_nested_list(detail_res, "options") if detail_res else None
    if not detail_options:
        _df_opts = _deep_find(detail_res, "options") if detail_res else None
        if isinstance(_df_opts, list):
            detail_options = _df_opts
    selected_detail_opt = find_option(detail_options, opt_id_review_req)

    if not _has_rreq:
        result.add("WARN", "OPTION_ID",
            "Review Request not found — cannot check optionId")
    elif not _has_dres:
        result.add("WARN", "OPTION_ID",
            "Detail Response not found — cannot check optionId")
    elif not opt_id_review_req:
        result.add("ERROR", "OPTION_ID",
            "optionId not found in Review Request "
            "(searched all files at all depths)")
    else:
        # 1. JSON value scan
        found_opt = _value_exists_anywhere(detail_res, opt_id_review_req) if detail_res else False
        # 2. Raw-text on matched detail_res file
        if not found_opt and _dres_path:
            found_opt = _raw_contains(_dres_path, opt_id_review_req)
        # 3. Exhaustive: all data files in the case dir
        if not found_opt:
            _skip = {_rreq_path} if _rreq_path else set()
            for _fp in _all_case_files:
                if _fp in _skip:
                    continue
                if _raw_contains(_fp, opt_id_review_req):
                    found_opt = True
                    break

        # Build side-by-side comparison with explicit [matched] / [unmatched] tags
        oi_tag  = "  [matched]" if found_opt else "  [unmatched]"
        dr_val  = opt_id_review_req if found_opt else "(not found in Detail Response options[])"
        _oi_msg = (
            f"Detail Response : {dr_val}{oi_tag}\n"
            f"Review Request  : {opt_id_review_req}{oi_tag}"
        )

        if found_opt:
            result.add("INFO", "OPTION_ID", f"optionId matched\n{_oi_msg}")
        else:
            result.add("ERROR", "OPTION_ID", f"optionId MISMATCH\n{_oi_msg}")

    # --- detail selected option vs review response ---
    review_option = _get_review_option(review_res) if review_res else None

    if selected_detail_opt and review_option:
        for sev, msg in compare_option_snapshots(
            option_snapshot(selected_detail_opt),
            option_snapshot(review_option),
            "detail(selected) vs review(response)",
        ):
            result.add(sev, "OPTION_CONSISTENCY", msg)
    # review_option not found — silently skip comparison (not required)

    # ── Booking ID: scan every file, display actual file names ───────────────
    # Pass 1 — collect all booking IDs across every file in the case directory
    #          using both JSON key-based scan and raw-text regex.
    _all_bid_ids: set[str] = set()
    # Build a reverse map: path → already-parsed dict (avoid re-reading)
    _path_to_parsed: dict[Path, Any] = {}
    for _slot, _spath in paths.items():
        if _spath and data.get(_slot):
            _path_to_parsed[_spath] = data[_slot]

    for _fp in _all_case_files:
        _parsed = _path_to_parsed.get(_fp) or load_json(_fp) or {}
        _all_bid_ids |= collect_booking_ids(_parsed)
        _all_bid_ids |= _raw_booking_ids(_fp)

    # Canonical booking ID = the one found in the most files
    _canonical_bid: str | None = None
    if _all_bid_ids:
        _canonical_bid = (
            next(iter(_all_bid_ids)) if len(_all_bid_ids) == 1
            else max(_all_bid_ids,
                     key=lambda x: sum(1 for _fp in _all_case_files
                                       if _raw_contains(_fp, x)))
        )

    # Pass 2 — for each file, record which booking IDs it contains.
    #           Only include files that actually contain a booking ID value.
    _bid_rows: list[tuple[str, list[str]]] = []
    for _fp in _all_case_files:
        _parsed = _path_to_parsed.get(_fp) or load_json(_fp) or {}
        _file_ids = collect_booking_ids(_parsed)
        _file_ids |= _raw_booking_ids(_fp)
        # Value-based fallback: does the canonical ID appear anywhere in this file?
        if not _file_ids and _canonical_bid:
            if _value_exists_anywhere(_parsed, _canonical_bid) or _raw_contains(_fp, _canonical_bid):
                _file_ids = {_canonical_bid}
        if _file_ids:
            _tag = "  [matched]" if _canonical_bid and all(i == _canonical_bid for i in _file_ids) \
                   else ("  [unmatched]" if _canonical_bid else "")
            _bid_rows.append((_fp.name, f"{' | '.join(sorted(_file_ids))}{_tag}"))

    # Display only — no pass/fail enforcement on booking ID consistency
    if _bid_rows:
        headline = (
            f"bookingId: {_canonical_bid}" if _canonical_bid
            else "bookingId: (not found in any file)"
        )
        _max_lbl = max((len(lbl) for lbl, _ in _bid_rows), default=20)
        _step_lines = "\n".join(
            f"{lbl:<{_max_lbl}} : {val}"
            for lbl, val in _bid_rows
        )
        result.add("INFO", "BOOKING_ID", f"{headline}\n{_step_lines}")

    # --- traveller / PAN vs room combo ---
    _dr_rooms_raw = (detail_req.get("rooms") or _deep_find(detail_req, "rooms")) if detail_req else None
    _sr_rooms_raw = (search_req.get("rooms") or _deep_find(search_req, "rooms")) if search_req else None
    expected_rooms = normalize_rooms(_dr_rooms_raw or _sr_rooms_raw)
    traveller_source = hold_req or book_req or confirm_req
    actual_trav = count_travellers_by_room(traveller_source)

    if expected_rooms and actual_trav:
        if len(expected_rooms) != len(actual_trav):
            result.add(
                "ERROR",
                "TRAVELLER_ROOMS",
                f"room count: search/detail {len(expected_rooms)} vs hold/book {len(actual_trav)}",
            )
        else:
            for i, (exp, act) in enumerate(zip(expected_rooms, actual_trav)):
                if exp.get("adults") != act.get("adults"):
                    result.add(
                        "ERROR",
                        "TRAVELLER_ROOMS",
                        f"room[{i}] adults: expected {exp.get('adults')} got {act.get('adults')}",
                    )
                exp_children = exp.get("children") or 0
                if exp_children != act.get("children"):
                    result.add(
                        "ERROR",
                        "TRAVELLER_ROOMS",
                        f"room[{i}] children: expected {exp_children} got {act.get('children')}",
                    )
                _exp_ca = exp.get("childAge") or []
                if isinstance(_exp_ca, (int, float)):
                    _exp_ca = [int(_exp_ca)]
                exp_ages = sorted(_exp_ca)
                if exp_ages and exp_ages != act.get("childAge"):
                    result.add(
                        "WARN",
                        "TRAVELLER_ROOMS",
                        f"room[{i}] child ages: expected {exp_ages} vs travellers {act.get('childAge')}",
                    )

        pan_required = None
        if review_option:
            pan_required = (review_option.get("compliance") or {}).get("panRequired")
        elif selected_detail_opt:
            pan_required = (selected_detail_opt.get("compliance") or {}).get("panRequired")

        if pan_required is True:
            for i, act in enumerate(actual_trav):
                if not act.get("hasPan") and not act.get("hasPassport"):
                    result.add("ERROR", "PAN", f"room[{i}]: panRequired but no pan/passport on travellers")
            # at least one pan on lead paths
            if actual_trav and not any(r.get("hasPan") for r in actual_trav):
                result.add("ERROR", "PAN", "panRequired=true but no PAN in hold/book payload")
        elif pan_required is False:
            if any(r.get("hasPan") for r in actual_trav):
                result.add("WARN", "PAN", "pan not required but PAN present (may be OK for corporate cases)")

    # --- missing expected files ---
    if not paths.get("search_req") and not data.get("search_req"):
        result.add("WARN", "FILES", "missing Hotel Search Request")
    if not paths.get("detail_res") and not data.get("detail_res"):
        result.add("WARN", "FILES", "missing hotelDetail-search Response")
    if not paths.get("review_res") and not data.get("review_res"):
        result.add("WARN", "FILES", "missing Hotel review Response")

    # --- Booking flow sequence ---
    validate_flow_sequence(result, paths, case_dir.name, data=data)

    # --- Payment amount (vs review response AND detail response) ---
    # Detect booking flow type to pick the right payment request source:
    #   - Hold + Confirm (TC3): paymentInfos are in confirm_hold_req only
    #   - Hold-only (TC1, TC6): booking was never confirmed, payment not applicable
    #   - Instant (TC2, TC4, TC5, TC7-13): paymentInfos in book_req
    _is_hold     = bool(data.get("hold_req") or data.get("hold_res") or
                        paths.get("hold_req") or paths.get("hold_res"))
    _has_confirm = bool(data.get("confirm_hold_req") or data.get("confirm_hold_res") or
                        paths.get("confirm_hold_req") or paths.get("confirm_hold_res"))

    if _is_hold and _has_confirm:
        # TC3: Hold → Confirm — validate against confirm_hold_req
        _pay_req   = data.get("confirm_hold_req") or {}
        _pay_path  = paths.get("confirm_hold_req")
        _pay_label = "Confirm-Hold Request"
        validate_payment_amount(
            _pay_req if _pay_req else None, review_res, result,
            detail_res=detail_res if detail_res else None,
            opt_id=opt_id_review_req,
            review_res_path=paths.get("review_res"),
            book_req_path=_pay_path,
            detail_res_path=paths.get("detail_res"),
            all_case_files=_all_case_files,
            payment_req_label=_pay_label,
        )
    elif _is_hold:
        # TC1, TC6: Hold-only — booking never confirmed, payment was not collected
        result.add("INFO", "PAYMENT_INFO",
            "Hold-only flow — booking was not confirmed, payment amount check not applicable")
    else:
        # Instant booking: paymentInfos in book_req
        validate_payment_amount(
            book_req, review_res, result,
            detail_res=detail_res if detail_res else None,
            opt_id=opt_id_review_req,
            review_res_path=paths.get("review_res"),
            book_req_path=paths.get("book_req"),
            detail_res_path=paths.get("detail_res"),
            all_case_files=_all_case_files,
            payment_req_label="Booking Request",
        )

    # --- Test case specification (search, detail, hold/book all vs spec) ---
    validate_test_case_spec(case_dir, result, detail_req, traveller_source,
                            search_req=search_req if search_req else None)

    # --- Guest PAN / Passport identities from booking request ---
    validate_traveller_identities(result, traveller_source)

    # --- Booking status from booking detail response ---
    bdr = data.get("booking_detail_res")
    if bdr and isinstance(bdr, dict):
        status_val = _extract_booking_status(bdr)
        if status_val:
            result.booking_status = status_val.upper()
            result.add("INFO", "BOOKING_STATUS",
                f"Booking detail status: {result.booking_status}")

    # --- Booking status from booking detail AFTER CANCEL response ---
    bdr_ac = data.get("booking_detail_after_cancel_res")
    if bdr_ac and isinstance(bdr_ac, dict):
        status_ac = _extract_booking_status(bdr_ac)
        if status_ac:
            result.booking_status_after_cancel = status_ac.upper()
            result.add("INFO", "BOOKING_STATUS",
                f"Booking status after cancellation: {result.booking_status_after_cancel}")

    # --- What was actually requested (from the search request, else the detail request) ---
    for _rq in (search_req, data.get("detail_req") or {}):
        if not isinstance(_rq, dict) or not _rq:
            continue
        _ci, _co = _deep_find(_rq, "checkIn"), _deep_find(_rq, "checkOut")
        _rooms = normalize_rooms(_rq.get("rooms") or _deep_find(_rq, "rooms"))
        if not (_ci or _co or _rooms):
            continue
        _nights = None
        try:
            from datetime import date as _d
            _nights = (_d.fromisoformat(str(_co)[:10]) - _d.fromisoformat(str(_ci)[:10])).days
        except Exception:
            pass
        result.request_info = {
            "check_in": _ci, "check_out": _co, "nights": _nights,
            "rooms": _rooms, "nationality": _deep_find(_rq, "nationality"),
            "currency": _deep_find(_rq, "currency"),
        }
        break

    # --- Hotel name from review response (deep search, any JSON structure) ---
    for _src in (review_res, detail_res, search_res):
        if not isinstance(_src, dict):
            continue
        # Try common key names in priority order, then deep scan
        _name = None
        for _key in ("hotelName", "hotel_name", "HotelName", "name"):
            _val = _get_nested(_src, _key)
            if isinstance(_val, str) and _val.strip() and len(_val.strip()) > 1:
                _name = _val.strip()
                break
        if _name is None:
            _raw = _deep_find(_src, "hotelName") or _deep_find(_src, "hotel_name")
            if isinstance(_raw, str) and _raw.strip():
                _name = _raw.strip()
        if _name:
            result.hotel_name = _name
            break  # stop at first source that has it

    # --- Bookings created / proven cancelled in this case (used by the Test Case 14 coverage check) ---
    for _slot in ("book_res", "hold_res", "confirm_hold_res"):
        result.booking_ids |= _collect_key(data.get(_slot) or {}, "bookingid")
    for _slot in ("booking_detail_res", "booking_detail_after_cancel_res"):
        _o = data.get(_slot)
        if isinstance(_o, dict) and _is_cancelled(_extract_booking_status(_o)):
            result.cancelled_ids |= _collect_key(_o, "bookingid")

    # --- Test Case 14: all test bookings must be shown as CANCELLED ---
    if _spec_for(case_dir.name).get("cancel_all"):
        validate_cancel_all(case_dir, result)

    return result


def _is_test_case_dir(name: str) -> bool:
    """Return True if a folder name looks like an individual test case.

    Deliberately narrow: "TJ TEST CASES", "HOTEL API TEST CASES - LIVE RUN",
    "Test Cases" etc. must NOT match so they are treated as containers and
    their children (the actual cases) are discovered by recursion.
    """
    n = name.lower()
    return (
        # "Test Case 1", "Test_Case_01", "TestCase2" — must have a digit after 'case'
        bool(re.match(r'^test[\s_-]*case[\s_-]*\d', n)) or
        bool(re.match(r'^\d{1,3}$', name)) or                      # pure number: 1, 2, 01
        bool(re.match(r'^(tc|case)[_\s-]?\d+', n)) or              # TC1, Case_01
        bool(re.match(r'^test[_\s-]\d+', n)) or                     # Test_01, Test 2
        bool(re.match(r'^(hotel|booking|scenario)[_\s-]\d+', n))    # Hotel_1, Scenario_01
    )


def _dir_has_data_files(d: Path) -> bool:
    """True if directory d directly contains at least one readable (non-binary) file."""
    try:
        for p in d.iterdir():
            if not p.is_file() or p.name.startswith('.') or p.name.startswith('~'):
                continue
            if p.suffix.lower() not in _BINARY_SUFFIXES:
                return True
    except PermissionError:
        pass
    return False


def _is_case_folder(path: Path) -> bool:
    """True if path is a directory that is a test case (by name OR by content)."""
    if not path.is_dir() or path.name.startswith('.'):
        return False
    return _is_test_case_dir(path.name) or _dir_has_data_files(path)


def discover_cases(root: Path, only_case: str | None) -> list[Path]:
    """Recursively collect all test-case folders under root.

    A folder is a test case if its name matches known patterns OR it directly
    contains data files (JSON/TXT).  Non-matching folders are descended into so
    that test cases nested at any depth are found.  We never recurse *inside* a
    recognised case folder (its contents are part of the case, not more cases).
    """
    cases: list[Path] = []

    def _collect(d: Path, depth: int = 0) -> None:
        if depth > 8:
            return
        try:
            children = sorted(d.iterdir())
        except PermissionError:
            return
        for path in children:
            if not path.is_dir() or path.name.startswith('.'):
                continue
            if _is_case_folder(path):
                if not only_case or path.name == only_case:
                    cases.append(path)
                # Do NOT recurse into case folders
            else:
                _collect(path, depth + 1)

    _collect(root)
    return cases


def print_report(results: list[CaseResult]) -> int:
    error_count = warn_count = 0
    print("\n" + "=" * 72)
    print("HOTEL API TEST CASE AUDIT")
    print("=" * 72)

    for cr in results:
        errors = [f for f in cr.findings if f.severity == "ERROR"]
        warns = [f for f in cr.findings if f.severity == "WARN"]
        infos = [f for f in cr.findings if f.severity == "INFO"]
        error_count += len(errors)
        warn_count += len(warns)

        status = "PASS" if not errors else "FAIL"
        print(f"\n{cr.case_name}  [{status}]  errors={len(errors)} warnings={len(warns)}")
        for f in errors + warns:
            print(f"  [{f.severity}] {f.rule}: {f.message}")
        if not errors and not warns and infos:
            for f in infos[:5]:
                print(f"  [INFO] {f.rule}: {f.message}")

    print("\n" + "-" * 72)
    print(f"SUMMARY: {len(results)} cases | {error_count} errors | {warn_count} warnings")
    print("=" * 72 + "\n")
    return 1 if error_count else 0


def to_json_report(results: list[CaseResult]) -> list[dict]:
    out = []
    for cr in results:
        out.append(
            {
                "case": cr.case_name,
                "files": cr.files,
                "status": "FAIL" if any(f.severity == "ERROR" for f in cr.findings) else "PASS",
                "booking_status": cr.booking_status,
                "booking_status_after_cancel": cr.booking_status_after_cancel,
                "hotel_name": cr.hotel_name,
                "request": cr.request_info,
                "findings": [
                    {"severity": f.severity, "rule": f.rule, "message": f.message} for f in cr.findings
                ],
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Hotel API LIVE RUN test case folders")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Root folder containing Test Case N directories",
    )
    parser.add_argument("--case", help="Validate only one folder, e.g. 'Test Case 1'")
    parser.add_argument("--json-report", type=Path, help="Write JSON findings to this path")
    parser.add_argument(
        "--strict-option-id",
        action="store_true",
        help="FAIL if review response optionId differs from detail/review request",
    )
    args = parser.parse_args()

    cases = discover_cases(args.root, args.case)
    if not cases:
        print(f"No test case folders under {args.root}", file=sys.stderr)
        return 2

    results = [validate_case(c, strict_option_id=args.strict_option_id) for c in cases]
    apply_cancel_coverage(results)
    if args.json_report:
        args.json_report.write_text(json.dumps(to_json_report(results), indent=2), encoding="utf-8")
        print(f"Wrote {args.json_report}")

    return print_report(results)


if __name__ == "__main__":
    sys.exit(main())
