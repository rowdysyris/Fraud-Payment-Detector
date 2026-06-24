import pandas as pd

from app.core.cleaning import clean_transactions_dataframe, parse_amount_value
from app.core.schema_mapping import map_transaction_schema


def _mapped_cleaned(dataframe: pd.DataFrame):
    mapped = map_transaction_schema(dataframe)
    return clean_transactions_dataframe(mapped.dataframe)


def test_parse_amount_handles_currency_symbols_and_text() -> None:
    assert parse_amount_value("₹1,200") == 1200.0
    assert parse_amount_value("Rs. 1,200.50") == 1200.50
    assert parse_amount_value("INR 2,500") == 2500.0
    assert parse_amount_value("$3,000") == 3000.0
    assert parse_amount_value("(Rs. 450)") == -450.0
    assert pd.isna(parse_amount_value("not an amount"))


def test_cleaning_preserves_row_count_and_standardizes_fields() -> None:
    dataframe = pd.DataFrame(
        {
            "customer": [" U1 ", "", "U3"],
            "payment_date": ["2026-01-01", "01/02/2026", "bad-date"],
            "txn_amt": ["₹1,000", "bad", "$2,500"],
            "shop": ["Store A", "", "😀 Mega Merchant"],
            "city": ["Bhopal", None, "Delhi"],
            "method": ["UPI", "Card", ""],
        }
    )

    result = _mapped_cleaned(dataframe)
    cleaned = result.dataframe

    assert len(cleaned) == 3
    assert cleaned["amount"].iloc[0] == 1000.0
    assert pd.isna(cleaned["amount"].iloc[1])
    assert cleaned["amount"].iloc[2] == 2500.0
    assert cleaned["transaction_time"].notna().sum() == 2
    assert pd.isna(cleaned["user_id"].iloc[1])
    assert cleaned["merchant"].iloc[2] == "😀 Mega Merchant"
    assert result.invalid_amount_count == 1
    assert result.invalid_transaction_time_count == 1


def test_cleaning_flags_duplicate_rows_and_duplicate_transaction_ids() -> None:
    dataframe = pd.DataFrame(
        {
            "transaction_id": ["DUP1", "DUP1", "DUP2"],
            "user_id": ["U1", "U1", "U2"],
            "transaction_time": ["2026-01-01 10:00:00", "2026-01-01 10:00:00", "2026-01-01 11:00:00"],
            "amount": [100, 100, 200],
            "merchant": ["Store A", "Store A", "Store B"],
        }
    )

    result = clean_transactions_dataframe(dataframe)
    cleaned = result.dataframe

    assert len(cleaned) == 3
    assert int(cleaned["duplicate_transaction_id_flag"].sum()) == 2
    assert int(cleaned["duplicate_row_flag"].sum()) >= 2
    assert result.duplicate_transaction_id_count == 2
    assert result.duplicate_row_count >= 1


def test_cleaning_generates_transaction_id_when_missing() -> None:
    dataframe = pd.DataFrame(
        {
            "user_id": ["U1", "U2"],
            "transaction_time": ["2026-01-01", "2026-01-02"],
            "amount": [100, 200],
        }
    )

    result = clean_transactions_dataframe(dataframe)

    assert result.dataframe["transaction_id"].tolist() == ["SP-ROW-000001", "SP-ROW-000002"]
