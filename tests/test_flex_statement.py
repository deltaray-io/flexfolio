import pytest
import pandas as pd
from pandas.util.testing import assert_frame_equal, assert_series_equal

from flexfolio.flex_statement import FlexStatement, ALL_MODELS

from .reports import flex_statements, ALL_FLEX_REPORTS, \
    load_expected_results, store_expected_results

STORE_RESULTS = False


@pytest.mark.parametrize("flex_stmt_path", ALL_FLEX_REPORTS)  # type: ignore
def test_models(flex_stmt_path: str) -> None:
    # Given a flex report
    flex_stmt = FlexStatement(flex_stmt_path)

    # When we request the models
    actual_models = pd.DataFrame(flex_stmt.models)

    if STORE_RESULTS:
        store_expected_results(flex_stmt_path, 'models', actual_models)

    # Then the returned models should match with the expected
    expected_models = load_expected_results(flex_stmt_path, 'models')

    assert_frame_equal(left=expected_models, right=actual_models)


@pytest.mark.parametrize("flex_stmt_path", ALL_FLEX_REPORTS)  # type: ignore
def test_starting_and_ending_nav(flex_stmt_path: str) -> None:
    # Given a flex report
    flex_stmt = FlexStatement(flex_stmt_path)

    # When we get the nav
    nav_dict = {}
    for model in flex_stmt.models + [ALL_MODELS, ]:
        nav_dict[model] = flex_stmt.nav(model)
    actual_navs = pd.DataFrame(nav_dict,
                               index=['starting_nav', 'ending_nav']).T

    if STORE_RESULTS:
        store_expected_results(flex_stmt_path, 'navs', actual_navs)

    # Then the expected should match the actual
    expected_navs = load_expected_results(flex_stmt_path, 'navs')
    assert_frame_equal(expected_navs, actual_navs)


@pytest.mark.parametrize("flex_stmt_path", ALL_FLEX_REPORTS)  # type: ignore
def test_cash_flows(flex_stmt_path: str) -> None:
    # Given a flex report
    flex_stmt = FlexStatement(flex_stmt_path)

    # When we get the cash flows
    cash_flows = {}
    for model in flex_stmt.models + [ALL_MODELS, ]:
        cash_flows[model] = flex_stmt.cash_flow(model)
    actual_cash_flows = pd.concat(
        cash_flows.values(), axis=1, keys=cash_flows.keys()
        )  # type: pd.DataFrame

    if STORE_RESULTS:
        store_expected_results(flex_stmt_path, 'cash-flows', actual_cash_flows)

    # Then the expected should match the actual
    expected_cash_flows = load_expected_results(flex_stmt_path, 'cash-flows')

    assert_frame_equal(
        expected_cash_flows.sort_index(axis=1),
        actual_cash_flows.sort_index(axis=1))


@pytest.mark.parametrize("flex_stmt_path", ALL_FLEX_REPORTS)  # type: ignore
def test_returns(flex_stmt_path: str) -> None:
    # Given a flex report
    flex_stmt = FlexStatement(flex_stmt_path)

    # When we parse it
    returns = {}
    for model in flex_stmt.models + [ALL_MODELS, ]:
        returns[model] = flex_stmt.returns(model)
    actual_returns = pd.concat(
        returns.values(), axis=1, keys=returns.keys()
        )  # type: pd.DataFrame

    if STORE_RESULTS:
        store_expected_results(flex_stmt_path, 'returns', actual_returns)

    # Then the returns should match the expected output
    expected_returns = load_expected_results(flex_stmt_path, 'returns')

    assert_frame_equal(
        expected_returns.sort_index(axis=1),
        actual_returns.sort_index(axis=1))


def test_calc_daily_qty_with_nonzero_final_and_no_trades() -> None:
    # Given a zero final qty and two trades
    final_qty = 40
    trades = pd.Series()

    # When we calculate the daily qty
    actual_daily_qty = FlexStatement.calc_daily_qty(
        final_qty=final_qty,
        trades=trades,
        start_date=pd.to_datetime('2018-02-05', utc=True),
        end_date=pd.to_datetime('2018-02-09', utc=True))

    # Then the daily quantities should be all zero
    expected_daily_qty = pd.Series(
        name='position',
        data=[40.0, 40.0, 40.0, 40.0, 40.0],
        index=[
            pd.to_datetime('2018-02-05', utc=True),
            pd.to_datetime('2018-02-06', utc=True),
            pd.to_datetime('2018-02-07', utc=True),
            pd.to_datetime('2018-02-08', utc=True),
            pd.to_datetime('2018-02-09', utc=True),
        ]
    )
    assert_series_equal(actual_daily_qty, expected_daily_qty)


def test_calc_daily_qty_with_nonzero_final_and_trades() -> None:
    # Given a zero final qty and two trades
    final_qty = 40
    trades = pd.Series(
        name='@quantity',
        data=[-5.0, -10.0, 20.0],
        index=[
            pd.to_datetime('2018-02-05', utc=True),
            pd.to_datetime('2018-02-07', utc=True),
            pd.to_datetime('2018-02-09', utc=True)])

    # When we calculate the daily qty
    actual_daily_qty = FlexStatement.calc_daily_qty(
        final_qty=final_qty,
        trades=trades,
        start_date=pd.to_datetime('2018-02-05', utc=True),
        end_date=pd.to_datetime('2018-02-09', utc=True))

    # Then the daily quantities should be all zero
    expected_daily_qty = pd.Series(
        name='position',
        data=[30.0, 30.0, 20.0, 20.0, 40.0],
        index=[
            pd.to_datetime('2018-02-05', utc=True),
            pd.to_datetime('2018-02-06', utc=True),
            pd.to_datetime('2018-02-07', utc=True),
            pd.to_datetime('2018-02-08', utc=True),
            pd.to_datetime('2018-02-09', utc=True),
        ]
    )
    assert_series_equal(actual_daily_qty, expected_daily_qty)


def test_calc_daily_qty_with_zero_final_and_trades() -> None:
    # Given a zero final qty and two trades
    final_qty = 0
    trades = pd.Series(
        name='@quantity',
        data=[5.0, -10.0, 20.0],
        index=[
            pd.to_datetime('2018-02-06', utc=True),
            pd.to_datetime('2018-02-07', utc=True),
            pd.to_datetime('2018-02-09', utc=True)])

    # When we calculate the daily qty
    actual_daily_qty = FlexStatement.calc_daily_qty(
        final_qty=final_qty,
        trades=trades,
        start_date=pd.to_datetime('2018-02-05', utc=True),
        end_date=pd.to_datetime('2018-02-09', utc=True))

    # Then the daily quantities should be all zero
    expected_daily_qty = pd.Series(
        name='position',
        data=[-15.0, -10.0, -20.0, -20.0, 0.0],
        index=[
            pd.to_datetime('2018-02-05', utc=True),
            pd.to_datetime('2018-02-06', utc=True),
            pd.to_datetime('2018-02-07', utc=True),
            pd.to_datetime('2018-02-08', utc=True),
            pd.to_datetime('2018-02-09', utc=True),
        ]
    )
    assert_series_equal(actual_daily_qty, expected_daily_qty)


def test_calc_daily_qty_with_zero_final_and_no_trades() -> None:
    # Given a zero final qty and no trades
    final_qty = 0
    trades = pd.Series()

    # When we calculate the daily qty
    actual_daily_qty = FlexStatement.calc_daily_qty(
        final_qty=final_qty,
        trades=trades,
        start_date=pd.to_datetime('2018-02-05', utc=True),
        end_date=pd.to_datetime('2018-02-09', utc=True))

    # Then the daily quantities should be all zero
    expected_daily_qty = pd.Series(
        name='position',
        data=[0.0, 0.0, 0.0, 0.0, 0.0],
        index=[
            pd.to_datetime('2018-02-05', utc=True),
            pd.to_datetime('2018-02-06', utc=True),
            pd.to_datetime('2018-02-07', utc=True),
            pd.to_datetime('2018-02-08', utc=True),
            pd.to_datetime('2018-02-09', utc=True),
        ]
    )
    assert_series_equal(actual_daily_qty, expected_daily_qty)


@pytest.mark.parametrize("flex_stmt_path", ALL_FLEX_REPORTS)  # type: ignore
def test_positions(flex_stmt_path: str) -> None:
    # Given a flex report
    flex_stmt = FlexStatement(flex_stmt_path)

    # When we parse it
    positions = {}
    for model in flex_stmt.models + [ALL_MODELS, ]:
        positions[model] = flex_stmt.positions(model)
    actual_positions = pd.concat(
        positions.values(), axis=1, keys=positions.keys()
        )  # type: pd.DataFrame

    if STORE_RESULTS:
        store_expected_results(flex_stmt_path, 'positions', actual_positions)

    # Then the positions should match the expected output
    expected_positions = load_expected_results(flex_stmt_path, 'positions')

    assert_frame_equal(
        expected_positions.sort_index(axis=1),
        actual_positions.sort_index(axis=1))


@pytest.mark.parametrize(  # type: ignore
    "flex_stmt_path",
    flex_statements(x_fail_patterns=[
        'buyandhold-20181123-ytd-all-models'  # Remove Forex transactions
    ]))
def test_transactions(flex_stmt_path: str) -> None:
    # Given a flex report which includes deposit
    flex_stmt = FlexStatement(flex_stmt_path)

    # When we parse it
    transactions = {}
    for model in flex_stmt.models + [ALL_MODELS, ]:
        # XXX: reset_index() is required as transactions has duplicate
        # values in indices which makes concat-ing impossible
        transactions[model] = flex_stmt.transactions(model).reset_index()
    actual_transactions = pd.concat(
        transactions.values(), axis=1, keys=transactions.keys()
        )  # type: pd.DataFrame

    if STORE_RESULTS:
        store_expected_results(flex_stmt_path, 'transactions',
                               actual_transactions)

    # Then the positions should match the expected output
    expected_transactions = load_expected_results(
        flex_stmt_path, 'transactions')

    assert_frame_equal(
        expected_transactions.sort_index(axis=1, level=[0, 1]),
        actual_transactions.sort_index(axis=1, level=[0, 1]))
