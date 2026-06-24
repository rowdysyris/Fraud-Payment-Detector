ALLOWED_UPLOAD_EXTENSIONS = {".csv", ".xlsx", ".xls"}
CSV_ENCODING_FALLBACKS = ("utf-8-sig", "utf-8", "latin1")

STANDARD_COLUMNS = [
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

REQUIRED_STANDARD_COLUMNS = ["amount", "user_id", "transaction_time"]
OPTIONAL_STANDARD_COLUMNS = [
    "transaction_id",
    "merchant",
    "location",
    "payment_method",
    "status",
    "currency",
]

OPTIONAL_COLUMN_DEFAULTS = {
    "merchant": "Unknown Merchant",
    "location": "Unknown Location",
    "payment_method": "Unknown Method",
    "status": "unknown",
    "currency": "Unknown Currency",
}

COLUMN_SYNONYMS = {
    "transaction_id": [
        "transaction_id",
        "txn_id",
        "transaction",
        "trans_id",
        "payment_id",
        "transactionid",
        "txn",
        "txnid",
        "paymentid",
        "order_id",
        "reference_id",
        "ref_id",
        "id",
    ],
    "user_id": [
        "user_id",
        "user",
        "customer",
        "customer_id",
        "cust_id",
        "account_id",
        "cardholder",
        "client_id",
        "member_id",
        "buyer_id",
        "userid",
        "customerid",
        "accountid",
    ],
    "transaction_time": [
        "transaction_time",
        "date",
        "time",
        "timestamp",
        "payment_date",
        "transaction_date",
        "created_at",
        "datetime",
        "txn_date",
        "txn_time",
        "trans_date",
        "paid_at",
        "purchase_date",
        "order_date",
    ],
    "amount": [
        "amount",
        "amt",
        "txn_amt",
        "transaction_amount",
        "value",
        "price",
        "total",
        "payment_amount",
        "paid_amount",
        "txn_amount",
        "transaction_value",
        "charge",
        "cost",
        "gross_amount",
        "net_amount",
    ],
    "merchant": [
        "merchant",
        "merchant_name",
        "shop",
        "shop_name",
        "vendor",
        "seller",
        "payee",
        "store",
        "store_name",
        "business",
        "merchant_id",
    ],
    "location": [
        "location",
        "city",
        "country",
        "geo",
        "address",
        "region",
        "state",
        "province",
        "pin_code",
        "postal_code",
        "zip",
        "ip_location",
    ],
    "payment_method": [
        "payment_method",
        "mode",
        "method",
        "payment_mode",
        "card_type",
        "channel",
        "payment_type",
        "instrument",
        "wallet",
        "card_network",
    ],
    "status": [
        "status",
        "txn_status",
        "payment_status",
        "result",
        "state",
        "outcome",
        "transaction_status",
    ],
    "currency": [
        "currency",
        "curr",
        "currency_code",
        "ccy",
        "money_type",
    ],
}

MISSING_MARKERS = {
    "",
    " ",
    "nan",
    "none",
    "null",
    "na",
    "n/a",
    "not available",
    "missing",
    "undefined",
    "nil",
    "-",
    "--",
}

FINAL_OUTPUT_COLUMNS = [
    "rule_fraud_score",
    "ml_fraud_probability",
    "fraud_score",
    "risk_level",
    "fraud_pattern",
    "fraud_reason",
    "triggered_agents",
    "confidence",
    "recommended_action",
    "review_status",
]

RISK_LEVELS = {
    "low": {"min": 0, "max": 30, "label": "Low Risk"},
    "medium": {"min": 31, "max": 60, "label": "Medium Risk"},
    "high": {"min": 61, "max": 80, "label": "High Risk"},
    "critical": {"min": 81, "max": 100, "label": "Critical Risk"},
}

AGENT_SPECS = {
    "amount_anomaly": {
        "display_name": "Amount Anomaly Agent",
        "score_column": "amount_anomaly_score",
        "reason_column": "amount_anomaly_reason",
        "triggered_column": "amount_anomaly_triggered",
        "pattern_column": "amount_anomaly_pattern",
        "max_score": 45,
    },
    "velocity_fraud": {
        "display_name": "Velocity Fraud Agent",
        "score_column": "velocity_fraud_score",
        "reason_column": "velocity_fraud_reason",
        "triggered_column": "velocity_fraud_triggered",
        "pattern_column": "velocity_fraud_pattern",
        "max_score": 45,
    },
    "user_behavior": {
        "display_name": "User Behavior Agent",
        "score_column": "user_behavior_score",
        "reason_column": "user_behavior_reason",
        "triggered_column": "user_behavior_triggered",
        "pattern_column": "user_behavior_pattern",
        "max_score": 20,
    },
    "merchant_risk": {
        "display_name": "Merchant Risk Agent",
        "score_column": "merchant_risk_score",
        "reason_column": "merchant_risk_reason",
        "triggered_column": "merchant_risk_triggered",
        "pattern_column": "merchant_risk_pattern",
        "max_score": 15,
    },
    "location_risk": {
        "display_name": "Location Risk Agent",
        "score_column": "location_risk_score",
        "reason_column": "location_risk_reason",
        "triggered_column": "location_risk_triggered",
        "pattern_column": "location_risk_pattern",
        "max_score": 15,
    },
    "duplicate_payment": {
        "display_name": "Duplicate Payment Agent",
        "score_column": "duplicate_payment_score",
        "reason_column": "duplicate_payment_reason",
        "triggered_column": "duplicate_payment_triggered",
        "pattern_column": "duplicate_payment_pattern",
        "max_score": 25,
    },
}

FRAUD_AGENT_SLUGS = [
    "amount_anomaly",
    "velocity_fraud",
    "user_behavior",
    "merchant_risk",
    "location_risk",
    "duplicate_payment",
]

FINAL_AGENT_SCORE_COLUMNS = [AGENT_SPECS[slug]["score_column"] for slug in FRAUD_AGENT_SLUGS]
FINAL_AGENT_REASON_COLUMNS = [AGENT_SPECS[slug]["reason_column"] for slug in FRAUD_AGENT_SLUGS]
FINAL_AGENT_TRIGGERED_COLUMNS = [AGENT_SPECS[slug]["triggered_column"] for slug in FRAUD_AGENT_SLUGS]
FINAL_AGENT_PATTERN_COLUMNS = [AGENT_SPECS[slug]["pattern_column"] for slug in FRAUD_AGENT_SLUGS]
