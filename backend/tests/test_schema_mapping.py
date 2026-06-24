import pandas as pd

from app.core.schema_mapping import map_transaction_schema, normalize_column_name


def test_schema_mapping_maps_messy_columns() -> None:
    dataframe = pd.DataFrame(
        {
            " txn_id ": ["T1"],
            "CUSTOMER": ["U1"],
            "Payment Date": ["2026-01-01"],
            "Rs. Transaction Amount": ["Rs. 1,200"],
            "Shop Name": ["Store A"],
            "City": ["Bhopal"],
            "Payment Mode": ["UPI"],
            "Payment Status": ["success"],
            "Currency Code": ["INR"],
        }
    )

    result = map_transaction_schema(dataframe)

    assert result.missing_required_columns == []
    assert "transaction_id" in result.dataframe.columns
    assert "user_id" in result.dataframe.columns
    assert "transaction_time" in result.dataframe.columns
    assert "amount" in result.dataframe.columns
    assert "merchant" in result.dataframe.columns
    assert "location" in result.dataframe.columns
    assert "payment_method" in result.dataframe.columns
    assert result.mapped_columns["user_id"] == "CUSTOMER"
    assert result.mapped_columns["amount"] == "Rs. Transaction Amount"


def test_schema_mapping_creates_optional_defaults_and_transaction_id() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_id": ["U1", "U2"],
            "created_at": ["2026-01-01", "2026-01-02"],
            "value": [100, 200],
        }
    )

    result = map_transaction_schema(dataframe)

    assert result.missing_required_columns == []
    for column in ["merchant", "location", "payment_method", "status", "currency"]:
        assert column in result.dataframe.columns
    assert result.dataframe["transaction_id"].tolist() == ["SP-ROW-000001", "SP-ROW-000002"]
    assert result.warnings


def test_schema_mapping_reports_missing_required_columns() -> None:
    dataframe = pd.DataFrame(
        {
            "customer_id": ["U1"],
            "created_at": ["2026-01-01"],
            "merchant": ["Store A"],
        }
    )

    result = map_transaction_schema(dataframe)

    assert "amount" in result.missing_required_columns


def test_schema_mapping_handles_uppercase_whitespace_and_special_characters() -> None:
    dataframe = pd.DataFrame(
        {
            " USER#ID ": ["U1"],
            " TRANSACTION!!!TIME ": ["2026-01-01 10:00:00"],
            " $$$ AMOUNT ": ["$1,250"],
            " VENDOR@@NAME ": ["Merchant"],
        }
    )

    result = map_transaction_schema(dataframe)

    assert result.missing_required_columns == []
    assert result.mapped_columns["user_id"] == " USER#ID "
    assert result.mapped_columns["transaction_time"] == " TRANSACTION!!!TIME "
    assert result.mapped_columns["amount"] == " $$$ AMOUNT "
    assert result.mapped_columns["merchant"] == " VENDOR@@NAME "


def test_normalize_column_name_is_stable() -> None:
    assert normalize_column_name("  Rs. Transaction Amount ₹ ") == "rs_transaction_amount_rupee"
    assert normalize_column_name("!!!") == "unnamed_column"
