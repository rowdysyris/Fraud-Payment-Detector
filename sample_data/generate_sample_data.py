from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

OUTPUT_DIR = Path(__file__).resolve().parent
SEED = 20260624
BASE_TIME = datetime(2026, 1, 15, 9, 0, 0)

USERS = [f"USER-{idx:04d}" for idx in range(1, 81)]
MERCHANTS = [
    "Metro Grocers",
    "UrbanFuel Station",
    "CloudKart",
    "City Pharmacy",
    "QuickBite Cafe",
    "BookNest",
    "RideSwift",
    "HomeNeeds",
    "StyleHub",
    "TechSquare",
    "MovieMax",
    "GreenBasket",
]
SUSPICIOUS_MERCHANTS = [
    "FlashCryptoX",
    "NightOwl Electronics",
    "GiftCard Vault",
    "Shell Merchant 991",
    "HighRiskPayee",
]
LOCATIONS = [
    "Bengaluru",
    "Mumbai",
    "Hyderabad",
    "Delhi",
    "Chennai",
    "Pune",
    "Bhopal",
    "Kolkata",
    "Jaipur",
    "Ahmedabad",
]
PAYMENT_METHODS = ["UPI", "Debit Card", "Credit Card", "Net Banking", "Wallet"]
CURRENCIES = ["INR", "USD"]


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def iso_time(minutes: int) -> str:
    return (BASE_TIME + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def standard_row(
    transaction_id: str,
    user_id: str,
    minutes: int,
    amount: object,
    merchant: str,
    location: str,
    payment_method: str,
    status: str = "success",
    currency: str = "INR",
) -> dict[str, object]:
    return {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "transaction_time": iso_time(minutes),
        "amount": amount,
        "merchant": merchant,
        "location": location,
        "payment_method": payment_method,
        "status": status,
        "currency": currency,
    }


def make_standard_transactions() -> list[dict[str, object]]:
    rng = random.Random(SEED + 1)
    rows: list[dict[str, object]] = []

    for idx in range(1, 151):
        amount = round(rng.uniform(120, 6500), 2)
        rows.append(
            standard_row(
                f"STD-{idx:06d}",
                rng.choice(USERS),
                idx * 18,
                amount,
                rng.choice(MERCHANTS),
                rng.choice(LOCATIONS),
                rng.choice(PAYMENT_METHODS),
                "success",
                "INR",
            )
        )

    for offset in range(151, 171):
        rows.append(
            standard_row(
                f"STD-MED-{offset:06d}",
                rng.choice(USERS[:30]),
                offset * 11,
                rng.choice([5000, 10000, 15000]),
                rng.choice(MERCHANTS),
                rng.choice(LOCATIONS),
                rng.choice(PAYMENT_METHODS),
                "success",
            )
        )

    for burst_idx in range(12):
        rows.append(
            standard_row(
                f"STD-VEL-{burst_idx:06d}",
                "USER-VELOCITY-CRITICAL",
                3200 + burst_idx,
                900 + burst_idx * 75,
                SUSPICIOUS_MERCHANTS[burst_idx % len(SUSPICIOUS_MERCHANTS)],
                LOCATIONS[burst_idx % len(LOCATIONS)],
                "Credit Card",
                "success",
            )
        )
    rows.append(
        standard_row(
            "STD-VEL-LARGE-000001",
            "USER-VELOCITY-CRITICAL",
            3213,
            250000,
            "FlashCryptoX",
            "Dubai-IP",
            "Credit Card",
            "success",
        )
    )

    duplicate_time = 3600
    for dup_idx in range(6):
        rows.append(
            standard_row(
                "STD-DUPLICATE-ID-0001" if dup_idx < 3 else f"STD-DUP-{dup_idx:06d}",
                "USER-DUPLICATE-777",
                duplicate_time,
                24999,
                "GiftCard Vault",
                "Bengaluru",
                "UPI",
                "success",
            )
        )

    for idx in range(36):
        rows.append(
            standard_row(
                f"STD-MERCHANT-RISK-{idx:06d}",
                f"USER-MERCHANT-{idx:03d}",
                3900 + idx * 2,
                18000 + (idx % 6) * 4000,
                "FlashCryptoX",
                rng.choice(LOCATIONS),
                rng.choice(PAYMENT_METHODS),
                "success",
            )
        )

    rows.extend(
        [
            standard_row("STD-ZERO-000001", "USER-ZERO-001", 4300, 0, "Metro Grocers", "Pune", "UPI", "success"),
            standard_row("STD-NEG-000001", "USER-REFUND-001", 4302, -3499, "CloudKart", "Mumbai", "Wallet", "refund"),
            standard_row("STD-EXTREME-000001", "USER-EXTREME-001", 4305, 9999999, "NightOwl Electronics", "Delhi", "Credit Card", "success"),
        ]
    )

    while len(rows) < 220:
        idx = len(rows) + 1
        rows.append(
            standard_row(
                f"STD-FILL-{idx:06d}",
                rng.choice(USERS),
                5000 + idx * 13,
                round(rng.uniform(250, 9000), 2),
                rng.choice(MERCHANTS),
                rng.choice(LOCATIONS),
                rng.choice(PAYMENT_METHODS),
                "success",
            )
        )
    return rows


def format_messy_amount(amount: float, idx: int) -> str:
    patterns = [
        f"₹{amount:,.2f}",
        f"Rs. {amount:,.0f}",
        f"INR {amount:,.2f}",
        f"${amount / 83.0:,.2f}",
        f" {amount:,.2f} ",
    ]
    return patterns[idx % len(patterns)]


def mixed_date(minutes: int, idx: int) -> str:
    dt = BASE_TIME + timedelta(minutes=minutes)
    patterns = [
        dt.strftime("%Y-%m-%d %H:%M:%S"),
        dt.strftime("%d/%m/%Y %H:%M"),
        dt.strftime("%m/%d/%Y %I:%M %p"),
        dt.strftime("%d-%b-%Y %H:%M"),
        dt.isoformat(),
    ]
    return patterns[idx % len(patterns)]


def make_messy_transactions() -> tuple[list[str], list[dict[str, object]]]:
    rng = random.Random(SEED + 2)
    headers = [
        " Txn ID ",
        "CUSTOMER!!!",
        " Payment Date/Time ",
        "Txn Amt ₹",
        "Shop Name!!!",
        "City/Region",
        "Mode of Payment",
        "txn_status",
        "curr",
        "raw_notes_ignored",
    ]
    rows: list[dict[str, object]] = []

    weird_merchants = [
        "Mega Store 🔥",
        "Vendor#42@@@",
        "Payee_With_Spaces      ",
        "नमस्ते किराना",
        "Ultra Long Merchant Name " + "X" * 180,
        "GiftCard Vault!!!",
    ]
    weird_locations = ["Bengaluru 😊", "Mumbai-West", "Unknown??", "Delhi/NCR", "東京-IP", "São Paulo"]

    for idx in range(1, 161):
        amount = rng.choice([rng.uniform(100, 6000), 5000, 10000, 24999])
        rows.append(
            {
                " Txn ID ": f"MSY-{idx:06d}",
                "CUSTOMER!!!": rng.choice(USERS),
                " Payment Date/Time ": mixed_date(idx * 17, idx),
                "Txn Amt ₹": format_messy_amount(float(amount), idx),
                "Shop Name!!!": rng.choice(weird_merchants + MERCHANTS),
                "City/Region": rng.choice(weird_locations + LOCATIONS),
                "Mode of Payment": rng.choice(PAYMENT_METHODS),
                "txn_status": rng.choice(["success", "paid", "settled"]),
                "curr": rng.choice(["INR", "INR", "USD"]),
                "raw_notes_ignored": rng.choice(["normal", "manual import", "legacy row", "contains emoji 🚩"]),
            }
        )

    duplicate_source = {
        " Txn ID ": "MSY-DUP-ID-0001",
        "CUSTOMER!!!": "USER-MESSY-DUP",
        " Payment Date/Time ": mixed_date(3000, 1),
        "Txn Amt ₹": "₹24,999.00",
        "Shop Name!!!": "GiftCard Vault!!!",
        "City/Region": "Bengaluru 😊",
        "Mode of Payment": "UPI",
        "txn_status": "success",
        "curr": "INR",
        "raw_notes_ignored": "intentional duplicate row",
    }
    for _ in range(5):
        rows.append(dict(duplicate_source))

    for burst_idx in range(24):
        rows.append(
            {
                " Txn ID ": f"MSY-RAPID-{burst_idx:06d}" if burst_idx != 12 else "MSY-DUP-ID-0001",
                "CUSTOMER!!!": "USER-MESSY-RAPID",
                " Payment Date/Time ": mixed_date(3600 + burst_idx, burst_idx),
                "Txn Amt ₹": format_messy_amount(800 + burst_idx * 110, burst_idx),
                "Shop Name!!!": weird_merchants[burst_idx % len(weird_merchants)],
                "City/Region": weird_locations[burst_idx % len(weird_locations)],
                "Mode of Payment": "Credit Card",
                "txn_status": "success",
                "curr": "INR" if burst_idx % 4 else "USD",
                "raw_notes_ignored": "rapid sequence",
            }
        )

    for idx in range(40):
        rows.append(
            {
                " Txn ID ": f"MSY-HIGH-{idx:06d}",
                "CUSTOMER!!!": f"USER-MSY-HIGH-{idx:03d}",
                " Payment Date/Time ": mixed_date(4100 + idx * 3, idx),
                "Txn Amt ₹": format_messy_amount(50000 + idx * 2500, idx),
                "Shop Name!!!": "FlashCryptoX 🚩",
                "City/Region": rng.choice(weird_locations + LOCATIONS),
                "Mode of Payment": rng.choice(PAYMENT_METHODS),
                "txn_status": rng.choice(["success", "manual_review", "settled"]),
                "curr": rng.choice(["INR", "USD"]),
                "raw_notes_ignored": "merchant concentration",
            }
        )

    return headers, rows[:230]


def make_edge_case_transactions() -> list[dict[str, object]]:
    rng = random.Random(SEED + 3)
    rows: list[dict[str, object]] = []

    edge_amounts: list[object] = [
        "not_a_number",
        "N/A",
        "ten thousand",
        "₹0",
        0,
        -1,
        -2500,
        "Rs. -4,500",
        "INR 999999999",
        "$12,000.50",
        "1,25,000",
        "₹ 2,50,000.75",
        "",
        None,
        "null",
        "--",
    ]

    for idx in range(1, 121):
        amount = edge_amounts[idx % len(edge_amounts)] if idx <= 60 else round(rng.uniform(100, 12000), 2)
        rows.append(
            standard_row(
                f"EDGE-{idx:06d}",
                rng.choice(USERS),
                idx * 9,
                amount,
                rng.choice(MERCHANTS + SUSPICIOUS_MERCHANTS),
                rng.choice(LOCATIONS + ["", "Unknown", "N/A"]),
                rng.choice(PAYMENT_METHODS + ["", "Unknown"]),
                rng.choice(["success", "refund", "chargeback", "failed", "reversal"]),
                rng.choice(["INR", "USD", "EUR", "", "JPY"]),
            )
        )

    for rapid_idx in range(45):
        rows.append(
            standard_row(
                f"EDGE-RAPID-{rapid_idx:06d}",
                "USER-EDGE-RAPID",
                2000 + rapid_idx,
                300 + rapid_idx * 50 if rapid_idx < 38 else 300000,
                SUSPICIOUS_MERCHANTS[rapid_idx % len(SUSPICIOUS_MERCHANTS)],
                LOCATIONS[rapid_idx % len(LOCATIONS)],
                PAYMENT_METHODS[rapid_idx % len(PAYMENT_METHODS)],
                "success",
                "INR",
            )
        )

    for location_idx in range(35):
        rows.append(
            standard_row(
                f"EDGE-LOC-{location_idx:06d}",
                "USER-EDGE-TRAVEL",
                2600 + location_idx * 2,
                rng.choice([999, 1499, 1999, 50000]),
                rng.choice(MERCHANTS),
                f"Location-{location_idx:02d}",
                "UPI",
                "success",
                "INR",
            )
        )

    for idx in range(35):
        rows.append(
            standard_row(
                "EDGE-DUP-ID-001" if idx < 4 else f"EDGE-DUP-{idx:06d}",
                "USER-EDGE-DUP",
                3300,
                7777,
                "Repeat Merchant",
                "Bhopal",
                "Wallet",
                "success",
                "INR",
            )
        )

    while len(rows) < 230:
        idx = len(rows) + 1
        rows.append(
            standard_row(
                f"EDGE-FILL-{idx:06d}",
                rng.choice(USERS),
                4200 + idx * 5,
                round(rng.uniform(200, 10000), 2),
                rng.choice(MERCHANTS),
                rng.choice(LOCATIONS),
                rng.choice(PAYMENT_METHODS),
                "success",
                rng.choice(["INR", "USD"]),
            )
        )

    return rows



def generate_all() -> None:
    standard_headers = [
        "transaction_id",
        "user_id",
        "transaction_time",
        "amount",
        "merchant",
        "location",
        "payment_method",
        "status",
        "currency",
    ]

    standard_rows = make_standard_transactions()
    write_csv(OUTPUT_DIR / "standard_transactions.csv", standard_headers, standard_rows)

    messy_headers, messy_rows = make_messy_transactions()
    write_csv(OUTPUT_DIR / "messy_transactions.csv", messy_headers, messy_rows)

    edge_rows = make_edge_case_transactions()
    write_csv(OUTPUT_DIR / "edge_case_transactions.csv", standard_headers, edge_rows)

    print("Generated deterministic SentinelPay AI sample datasets:")
    for file_name in [
        "standard_transactions.csv",
        "messy_transactions.csv",
        "edge_case_transactions.csv",
    ]:
        path = OUTPUT_DIR / file_name
        print(f"- {file_name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    generate_all()
