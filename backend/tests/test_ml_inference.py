from __future__ import annotations

import importlib
import json
import os
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.ml.feature_engineering import TARGET_LEAKAGE_COLUMNS, build_ml_features
from app.ml.inference import run_inference


def make_base_df(n=30, seed=42):
    rng = np.random.default_rng(seed)
    base = datetime(2024, 1, 15, 10, 0, 0)
    return pd.DataFrame({
        'transaction_id': [f'TXN{i:04d}' for i in range(n)],
        'user_id': [f'USER{i % 10 + 1:03d}' for i in range(n)],
        'amount': rng.uniform(200, 800, n).round(2).tolist(),
        'transaction_time': [
            (base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
            for i in range(n)
        ],
        'merchant': [f'Merchant{i % 6 + 1}' for i in range(n)],
        'location': [['Mumbai', 'Delhi', 'Bangalore'][i % 3] for i in range(n)],
        'payment_method': [['UPI', 'Card', 'Wallet'][i % 3] for i in range(n)],
    })


def make_velocity_df(normal_n=20):
    base = datetime(2024, 1, 15, 10, 0, 0)
    normal = [{
        'transaction_id': f'N{i}', 'user_id': f'USER{i+2:03d}',
        'amount': float(300 + i * 20),
        'transaction_time': (base + timedelta(hours=i * 3)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': f'Shop{i}', 'location': 'Mumbai', 'payment_method': 'UPI'
    } for i in range(normal_n)]
    velocity = [{
        'transaction_id': f'V{i}', 'user_id': 'USER001',
        'amount': float(100 + i * 5),
        'transaction_time': (base + timedelta(seconds=i * 8)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': f'VShop{i}', 'location': 'Delhi', 'payment_method': 'Card'
    } for i in range(12)]
    return pd.DataFrame(normal + velocity)


def make_anomaly_df(normal_amount_range=(200, 600), anomaly_amount=85000):
    rng = np.random.default_rng(123)
    base = datetime(2024, 1, 15, 10, 0, 0)
    rows = [{
        'transaction_id': f'N{i}', 'user_id': 'USER001',
        'amount': float(rng.uniform(*normal_amount_range)),
        'transaction_time': (base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': 'RegularShop', 'location': 'Mumbai', 'payment_method': 'UPI'
    } for i in range(25)]
    rows.append({
        'transaction_id': 'ANOMALY', 'user_id': 'USER001',
        'amount': float(anomaly_amount),
        'transaction_time': (base + timedelta(hours=26)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': 'LuxuryStore', 'location': 'Dubai', 'payment_method': 'Card'
    })
    return pd.DataFrame(rows)


def test_model_file_exists():
    path = os.path.join(os.path.dirname(__file__), '..', 'app', 'ml', 'model_store', 'fraud_model.joblib')
    assert os.path.exists(path), f'Model file not found at {path}'


def test_metadata_file_exists_and_valid():
    path = os.path.join(os.path.dirname(__file__), '..', 'app', 'ml', 'model_store', 'fraud_model_metadata.json')
    assert os.path.exists(path), 'Metadata file not found'
    with open(path, encoding='utf-8') as f:
        meta = json.load(f)
    assert isinstance(meta, dict), 'Metadata must be a dict'
    assert len(meta) > 0, 'Metadata is empty'
    for key in ['model_type', 'feature_columns', 'training_rows', 'positive_labels', 'negative_labels']:
        assert key in meta, f'Metadata missing key: {key}'


def test_inference_import():
    importlib.import_module('app.ml.inference')


def test_feature_engineering_import():
    importlib.import_module('app.ml.feature_engineering')


def test_inference_basic_output_columns():
    df = make_base_df(30)
    result = run_inference(df)
    assert result is not None
    assert len(result) == 30
    required = [
        'fraud_score', 'risk_level', 'fraud_reason',
        'fraud_pattern', 'triggered_agents', 'confidence',
        'recommended_action', 'review_status'
    ]
    for col in required:
        assert col in result.columns, f'Missing output column: {col}'


def test_inference_score_range():
    df = make_base_df(100)
    result = run_inference(df)
    assert result['fraud_score'].apply(lambda x: x == int(x)).all()
    assert result['fraud_score'].between(0, 100).all(), f"Scores out of range: {result['fraud_score'].describe()}"


def test_inference_confidence_range():
    df = make_base_df(100)
    result = run_inference(df)
    assert result['confidence'].between(0.0, 1.0).all(), f"Confidence out of range: {result['confidence'].describe()}"


def test_inference_risk_level_valid_values():
    df = make_base_df(80)
    result = run_inference(df)
    valid = {'Low Risk', 'Medium Risk', 'High Risk', 'Critical Risk'}
    invalid = set(result['risk_level'].unique()) - valid
    assert not invalid, f'Invalid risk_level values found: {invalid}'


def test_inference_risk_level_consistent_with_score():
    df = make_base_df(100)
    result = run_inference(df)
    for _, row in result.iterrows():
        score = int(row['fraud_score'])
        level = row['risk_level']
        if score <= 30:
            assert level == 'Low Risk', f'Score {score} should be Low Risk, got {level}'
        elif score <= 60:
            assert level == 'Medium Risk', f'Score {score} should be Medium Risk, got {level}'
        elif score <= 80:
            assert level == 'High Risk', f'Score {score} should be High Risk, got {level}'
        else:
            assert level == 'Critical Risk', f'Score {score} should be Critical Risk, got {level}'


def test_inference_confidence_equals_score_over_100():
    df = make_base_df(50)
    result = run_inference(df)
    for _, row in result.iterrows():
        expected = round(int(row['fraud_score']) / 100, 2)
        actual = round(float(row['confidence']), 2)
        assert abs(actual - expected) < 0.011, f'confidence {actual} != score/100 {expected}'


def test_velocity_fraud_gets_higher_score():
    df = make_velocity_df(normal_n=20)
    result = run_inference(df)
    velocity_ids = {f'V{i}' for i in range(12)}
    normal_ids = {f'N{i}' for i in range(20)}
    v_scores = result[result['transaction_id'].isin(velocity_ids)]['fraud_score']
    n_scores = result[result['transaction_id'].isin(normal_ids)]['fraud_score']
    assert len(v_scores) == 12, f'Expected 12 velocity txns, got {len(v_scores)}'
    assert len(n_scores) == 20, f'Expected 20 normal txns, got {len(n_scores)}'
    assert v_scores.mean() > n_scores.mean(), f'Velocity avg {v_scores.mean():.1f} should exceed normal avg {n_scores.mean():.1f}'


def test_large_amount_anomaly_gets_higher_score():
    df = make_anomaly_df(normal_amount_range=(200, 600), anomaly_amount=85000)
    result = run_inference(df)
    anomaly_score = result[result['transaction_id'] == 'ANOMALY']['fraud_score'].iloc[0]
    normal_avg = result[result['transaction_id'] != 'ANOMALY']['fraud_score'].mean()
    assert anomaly_score > normal_avg, f'Anomaly score {anomaly_score} should exceed normal avg {normal_avg:.1f}'


def test_single_row_no_crash():
    df = pd.DataFrame([{
        'transaction_id': 'TXN0001', 'user_id': 'USER001',
        'amount': 500.0,
        'transaction_time': '2024-01-15 10:00:00',
        'merchant': 'ShopA', 'location': 'Mumbai',
        'payment_method': 'UPI'
    }])
    result = run_inference(df)
    assert result is not None
    assert len(result) == 1
    assert 'fraud_score' in result.columns
    assert 0 <= int(result['fraud_score'].iloc[0]) <= 100


def test_two_rows_no_crash():
    df = pd.DataFrame([
        {'transaction_id': 'T1', 'user_id': 'USER001', 'amount': 300.0, 'transaction_time': '2024-01-15 10:00:00', 'merchant': 'ShopA', 'location': 'Mumbai', 'payment_method': 'UPI'},
        {'transaction_id': 'T2', 'user_id': 'USER002', 'amount': 500.0, 'transaction_time': '2024-01-15 11:00:00', 'merchant': 'ShopB', 'location': 'Delhi', 'payment_method': 'Card'},
    ])
    result = run_inference(df)
    assert len(result) == 2


def test_all_same_timestamp_no_crash():
    df = pd.DataFrame({
        'transaction_id': [f'T{i}' for i in range(100)],
        'user_id': [f'USER{i % 10 + 1:03d}' for i in range(100)],
        'amount': np.random.default_rng(15).uniform(100, 1000, 100).round(2),
        'transaction_time': ['2024-01-15 10:00:00'] * 100,
        'merchant': [f'Shop{i % 5}' for i in range(100)],
        'location': 'Mumbai',
        'payment_method': 'UPI'
    })
    result = run_inference(df)
    assert len(result) == 100
    assert result['fraud_score'].between(0, 100).all()


def test_all_same_user_no_crash():
    base = datetime(2024, 1, 15, 10, 0, 0)
    df = pd.DataFrame({
        'transaction_id': [f'T{i}' for i in range(200)],
        'user_id': ['USER001'] * 200,
        'amount': np.random.default_rng(16).uniform(100, 2000, 200).round(2),
        'transaction_time': [(base + timedelta(minutes=i * 3)).strftime('%Y-%m-%d %H:%M:%S') for i in range(200)],
        'merchant': [f'Shop{i % 10}' for i in range(200)],
        'location': 'Mumbai',
        'payment_method': 'UPI'
    })
    result = run_inference(df)
    assert len(result) == 200
    assert result['fraud_score'].between(0, 100).all()


def test_all_same_amount_no_crash():
    base = datetime(2024, 1, 15, 10, 0, 0)
    df = pd.DataFrame({
        'transaction_id': [f'T{i}' for i in range(50)],
        'user_id': [f'USER{i % 5 + 1:03d}' for i in range(50)],
        'amount': [1000.0] * 50,
        'transaction_time': [(base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S') for i in range(50)],
        'merchant': 'ShopA',
        'location': 'Mumbai',
        'payment_method': 'UPI'
    })
    result = run_inference(df)
    assert len(result) == 50
    assert result['fraud_score'].between(0, 100).all()


def test_zero_amounts_no_crash():
    base = datetime(2024, 1, 15, 10, 0, 0)
    df = pd.DataFrame({
        'transaction_id': [f'T{i}' for i in range(30)],
        'user_id': [f'USER{i % 5 + 1:03d}' for i in range(30)],
        'amount': [0.0] * 30,
        'transaction_time': [(base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S') for i in range(30)],
        'merchant': 'ShopA',
        'location': 'Mumbai',
        'payment_method': 'UPI'
    })
    result = run_inference(df)
    assert len(result) == 30
    assert result['fraud_score'].between(0, 100).all()


def test_negative_amounts_no_crash():
    base = datetime(2024, 1, 15, 10, 0, 0)
    df = pd.DataFrame({
        'transaction_id': [f'T{i}' for i in range(30)],
        'user_id': [f'USER{i % 5 + 1:03d}' for i in range(30)],
        'amount': [-500.0 if i % 3 == 0 else 300.0 for i in range(30)],
        'transaction_time': [(base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S') for i in range(30)],
        'merchant': 'ShopA',
        'location': 'Mumbai',
        'payment_method': 'UPI'
    })
    result = run_inference(df)
    assert len(result) == 30
    assert result['fraud_score'].between(0, 100).all()


def test_currency_symbol_amounts_no_crash():
    base = datetime(2024, 1, 15, 10, 0, 0)
    amounts = ['₹5,000', 'Rs. 2000', 'INR 7500', '$250', '12,000', ' 3000 ', 'Rs.500', '1500.50', 'N/A', 'null', '', None, '0', '-200']
    rows = [{
        'transaction_id': f'T{i}',
        'user_id': f'USER{i % 5 + 1:03d}',
        'amount': amounts[i % len(amounts)],
        'transaction_time': (base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': 'TestShop',
        'location': 'Mumbai',
        'payment_method': 'UPI'
    } for i in range(30)]
    result = run_inference(pd.DataFrame(rows))
    assert len(result) == 30
    assert result['fraud_score'].between(0, 100).all()


def test_invalid_dates_no_crash():
    bad_dates = ['not-a-date', '99/99/9999', '', 'abc', None, '2024-01-15', '15-01-2024', 'Jan 15 2024', '15 Jan 2024 3:30 PM']
    rows = [{
        'transaction_id': f'T{i}',
        'user_id': f'USER{i % 5 + 1:03d}',
        'amount': float(300 + i * 10),
        'transaction_time': bad_dates[i % len(bad_dates)],
        'merchant': 'ShopA',
        'location': 'Mumbai',
        'payment_method': 'UPI'
    } for i in range(30)]
    result = run_inference(pd.DataFrame(rows))
    assert result is not None
    assert len(result) == 30


def test_missing_optional_columns_no_crash():
    base = datetime(2024, 1, 15, 10, 0, 0)
    df = pd.DataFrame({
        'user_id': [f'USER{i % 5 + 1:03d}' for i in range(30)],
        'amount': [float(300 + i * 10) for i in range(30)],
        'transaction_time': [(base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S') for i in range(30)]
    })
    result = run_inference(df)
    assert result is not None
    assert len(result) == 30
    assert result['fraud_score'].between(0, 100).all()


def test_missing_user_id_column_no_crash():
    base = datetime(2024, 1, 15, 10, 0, 0)
    df = pd.DataFrame({
        'transaction_id': [f'T{i}' for i in range(20)],
        'amount': [float(300 + i * 10) for i in range(20)],
        'transaction_time': [(base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S') for i in range(20)]
    })
    result = run_inference(df)
    assert result is not None
    assert len(result) == 20


def test_extra_columns_ignored():
    df = make_base_df(30)
    for i in range(50):
        df[f'extra_col_{i}'] = f'value_{i}'
    result = run_inference(df)
    assert len(result) == 30
    assert result['fraud_score'].between(0, 100).all()


def test_fraud_reason_never_empty():
    df = make_base_df(50)
    result = run_inference(df)
    empty_reasons = result[result['fraud_reason'].isna() | (result['fraud_reason'].str.strip() == '')]
    assert len(empty_reasons) == 0, f'{len(empty_reasons)} transactions have empty fraud_reason'


def test_triggered_agents_never_empty():
    df = make_base_df(50)
    result = run_inference(df)
    empty_agents = result[result['triggered_agents'].isna() | (result['triggered_agents'].str.strip() == '')]
    assert len(empty_agents) == 0, f'{len(empty_agents)} transactions have empty triggered_agents'


def test_output_row_count_matches_input():
    for n in [1, 2, 10, 50, 200]:
        df = make_base_df(n, seed=n)
        result = run_inference(df)
        assert len(result) == n, f'Input {n} rows, got {len(result)} output rows'


def test_10000_rows_performance():
    base = datetime(2024, 1, 15, 10, 0, 0)
    rng = np.random.default_rng(99)
    n = 10000
    df = pd.DataFrame({
        'transaction_id': [f'T{i}' for i in range(n)],
        'user_id': [f'USER{i % 200 + 1:04d}' for i in range(n)],
        'amount': rng.uniform(100, 5000, n).round(2),
        'transaction_time': [(base + timedelta(minutes=i * 2)).strftime('%Y-%m-%d %H:%M:%S') for i in range(n)],
        'merchant': [f'Merchant{i % 50 + 1}' for i in range(n)],
        'location': [['Mumbai', 'Delhi', 'Bangalore', 'Chennai'][i % 4] for i in range(n)],
        'payment_method': [['UPI', 'Card', 'Net Banking', 'Wallet'][i % 4] for i in range(n)]
    })
    start = time.time()
    result = run_inference(df)
    elapsed = time.time() - start
    assert len(result) == n
    assert result['fraud_score'].between(0, 100).all()
    assert elapsed < 90, f'Took {elapsed:.1f}s, must be under 90s'
    print(f'10000 rows completed in {elapsed:.1f}s')


def test_extreme_amount_scores_higher():
    base = datetime(2024, 1, 15, 10, 0, 0)
    rng = np.random.default_rng(7)
    normal = [{
        'transaction_id': f'N{i}', 'user_id': f'USER{i % 10 + 2:03d}',
        'amount': float(rng.uniform(100, 800)),
        'transaction_time': (base + timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': f'Shop{i % 5}', 'location': 'Mumbai', 'payment_method': 'UPI'
    } for i in range(50)]
    extreme = {
        'transaction_id': 'EXTREME', 'user_id': 'USER001',
        'amount': 999999999.99,
        'transaction_time': (base + timedelta(hours=51)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': 'Unknown', 'location': 'Unknown', 'payment_method': 'Card'
    }
    result = run_inference(pd.DataFrame(normal + [extreme]))
    extreme_score = int(result[result['transaction_id'] == 'EXTREME']['fraud_score'].iloc[0])
    normal_avg = result[result['transaction_id'] != 'EXTREME']['fraud_score'].mean()
    assert extreme_score > normal_avg, f'Extreme score {extreme_score} should exceed normal avg {normal_avg:.1f}'


def test_duplicate_transactions_score_higher():
    base = datetime(2024, 1, 15, 10, 0, 0)
    unique = [{
        'transaction_id': f'U{i}', 'user_id': f'USER{i+10:03d}',
        'amount': float(400 + i * 50),
        'transaction_time': (base + timedelta(hours=i * 2)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': f'UniqueShop{i}', 'location': 'Mumbai', 'payment_method': 'UPI'
    } for i in range(20)]
    dups = [{
        'transaction_id': f'DUP{i}', 'user_id': 'USER001',
        'amount': 2500.0,
        'transaction_time': (base + timedelta(seconds=i * 20)).strftime('%Y-%m-%d %H:%M:%S'),
        'merchant': 'SameShop', 'location': 'Delhi', 'payment_method': 'Card'
    } for i in range(6)]
    result = run_inference(pd.DataFrame(unique + dups))
    dup_ids = {f'DUP{i}' for i in range(6)}
    dup_avg = result[result['transaction_id'].isin(dup_ids)]['fraud_score'].mean()
    unique_avg = result[result['transaction_id'].str.startswith('U')]['fraud_score'].mean()
    assert dup_avg > unique_avg, f'Duplicate avg {dup_avg:.1f} should exceed unique avg {unique_avg:.1f}'
