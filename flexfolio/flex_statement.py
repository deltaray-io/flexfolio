from typing import Tuple, Optional, List, Union, Dict
from typing import Any  # pylint: disable=unused-import
from collections import OrderedDict  # pylint: disable=unused-import
from datetime import datetime

import logging

import xmltodict
import pandas as pd
import numpy as np
from toolz import get_in

from .utils import get_equity_price

log = logging.getLogger(__name__)

ALL_MODELS = '__all_models'


def _typify(_: str, key: str, value: str
            ) -> Tuple[str, Union[str, float]]:
    if key.endswith(('time', 'date', 'Time', 'Date', 'conid')):
        # Skip converting @tradeDate, @date, @tradeTime and @toDate
        return key, value

    try:
        return key, float(value)
    except (ValueError, TypeError):
        return key, value


class FlexStatement:
    def __init__(self, flex_report_path: str) -> None:
        self.flex_report_path = flex_report_path
        with open(flex_report_path) as f:
            self.report = xmltodict.parse(
                f.read(),
                postprocessor=_typify)

        statements = self.report['FlexQueryResponse']['FlexStatements']
        # FlexStatements could be one or multiple in source,
        # consolidate it into a list
        if int(statements['@count']) == 1:
            self.stmts = [statements['FlexStatement'], ]
        else:
            self.stmts = statements['FlexStatement']

    @property
    def models(self) -> List[str]:
        # FIXME: Not all models are presented under ChangeInNav.
        return [e['ChangeInNAV']['@model'] for e in self.stmts]

    def stmts_for_model(self,
                        model: str = ALL_MODELS
                        ) -> Dict[str, 'OrderedDict[str, Any]']:
        return {e['ChangeInNAV']['@model']: e
                for e in self.stmts
                if model in (ALL_MODELS, e['ChangeInNAV']['@model'])}

    def nav(self, model: str) -> Tuple[float, float]:
        stmts = self.stmts_for_model(model)

        starting_nav = sum([model['ChangeInNAV']['@startingValue']
                            for model in stmts.values()])
        ending_nav = sum([model['ChangeInNAV']['@endingValue']
                          for model in stmts.values()])

        return starting_nav, ending_nav

    def cash_flow(self, model: str) -> pd.Series:
        # FIXME: Internal transfers and external withdrawals/deposits are not
        # differentiated by this function.
        # FIXME: This function sums transfers within the same day, hence
        # not showing those transactions where the incoming and outgoing's
        # sum is 0.
        # FIXME: Only the active models are represented here. The ones which
        # are were not active during the reporting period does not show in flex
        # report hence cannot be handled by this function.
        stmt_funds = self.stmt_funds(model)

        cash_flows = {}
        for model_name, funds in stmt_funds.items():
            cash_flow = funds[
                funds['@activityCode'].isin(('DEP', 'WITH')) &
                (funds['@levelOfDetail'] == 'BaseCurrency')]['@amount']
            cash_flows[model_name] = cash_flow.groupby(cash_flow.index).sum()

        cash_flows_df = pd.concat(cash_flows, axis=1)  # type: pd.DataFrame

        # Summarize the results so that the end result is a single series
        # with deduplicated index without any zero values
        cash_flows_series = cash_flows_df.sum(axis=1).sort_index()
        cash_flows_series = cash_flows_series[cash_flows_series != 0]
        cash_flows_series.name = 'cash_flow'

        return cash_flows_series

    def returns(self, model: str) -> pd.Series:
        # FIXME: this function has problems with reports where multiple
        # models are present.
        # Problem 1: the first two months are not showing up unless the
        # nav is calculated as:
        #             navs[model_name] = summary[
        #                 (summary['@total'] != 0.0) |
        #                 (summary['@totalLong'] != 0.0) |
        #                 (summary['@totalShort'] != 0.0)]['@total']
        # Problem with this nav calculation that it screws the return calc.
        # for multi-model periods
        # Problem 2: the end returns are not in sync with portfolio analyst
        # report.

        equity_summary = self.equity_summary(model)
        # Filter where cash is zero:
        # When the lookback period goes beyond account inception
        # or there was a paper trading acccount reset,
        # leading zeros are filling equity_summary, which disturbs
        # return calculation.
        # equity_summary = equity_summary[model]
        navs = {}
        for model_name, summary in equity_summary.items():
            navs[model_name] = summary[
                (summary['@cash'] != 0.0) |
                (summary['@cashLong'] != 0.0) |
                (summary['@cashShort'] != 0.0)]['@total']

        nav = \
            (pd.DataFrame(navs)
             .fillna(0)       # Fill NAs caused by joining multiple series
             .resample('1D').sum()  # Sum per day to avoid daily duplicates
             .dropna()        # Skip weekends
             .sum(axis=1))    # Reduce multiple series into one

        df = pd.DataFrame(data={'nav': nav})

        cash_flow = self.cash_flow(model)
        cash_flow = cash_flow.resample('1D').sum().dropna()
        df['cash_flow'] = cash_flow
        df['cash_flow'].fillna(0, inplace=True)

        df['initial_value'] = df['nav'].shift(1)
        df['end_value'] = df['nav'].shift(0)

        # Time Weighted Return
        df['returns'] = \
            (df['end_value'] - df['initial_value'] - df['cash_flow']) \
            / (df['initial_value'])

        # Replace initial NaN with 0.0
        df['returns'].iloc[0] = 0

        # TODO: Add credit interest, fees, dividends

        return df['returns']

    def flex_dict_to_df(self,
                        model: str,
                        keys: List[str],
                        date_field: Optional[Union[str, Tuple[str, str]]],
                        local_tz: str = 'US/Eastern'
                        ) -> Dict[str, pd.DataFrame]:
        """Returns a Multi-Index DataFrame with the parsed flex report.
        Top level keys are the models, second level keys are the fields from
        the flex statement. If model is not set all the models are returned.
        """
        # TODO: split date_field into date_field and time_field
        stmts = self.stmts_for_model(model)

        def to_df(stmt: 'OrderedDict[str, Any]') -> pd.DataFrame:
            df = pd.DataFrame(get_in(keys, stmt))

            if df.empty:
                return df

            if isinstance(date_field, tuple):
                df.index = \
                    pd.to_datetime(df[date_field[0]] + ' ' + df[date_field[1]])
                df.index = df.index.tz_localize(local_tz).tz_convert('UTC')
            elif date_field:
                df.index = pd.to_datetime(df[date_field])
                df.index = df.index.tz_localize(local_tz).tz_convert('UTC')
            else:
                pass
            df.sort_index(inplace=True)

            return df

        dict_of_dfs = {model_name: to_df(stmt)
                       for model_name, stmt in stmts.items()}

        return dict_of_dfs

    @staticmethod
    def dict_of_dfs_to_multiindex_df(dict_of_dfs: Dict[str, pd.DataFrame]
                                     ) -> pd.DataFrame:
        df = pd.concat(
            dict_of_dfs.values(), axis=1, keys=dict_of_dfs.keys()
            )  # type: pd.DataFrame
        return df

    def equity_summary(self, model: str) -> Dict[str, pd.DataFrame]:
        equity_summary = self.flex_dict_to_df(
                model,
                ['EquitySummaryInBase', 'EquitySummaryByReportDateInBase'],
                date_field='@reportDate', local_tz='UTC')

        return equity_summary

    def trades(self, model: str) -> Dict[str, pd.DataFrame]:
        trades = self.flex_dict_to_df(
            model,
            ['Trades', 'Trade'],
            date_field=('@tradeDate', '@tradeTime'), local_tz='US/Eastern')
        return trades

    def prior_period(self, model: str) -> Dict[str, pd.DataFrame]:
        return self.flex_dict_to_df(
                model,
                ['PriorPeriodPositions', 'PriorPeriodPosition'],
                date_field='@date', local_tz='UTC')

    def stmt_funds(self, model: str) -> Dict[str, pd.DataFrame]:
        return self.flex_dict_to_df(
            model,
            ['StmtFunds', 'StatementOfFundsLine'],
            date_field='@date', local_tz='UTC')

    def securities(self, model: str) -> Dict[str, pd.DataFrame]:
        return self.flex_dict_to_df(
            model,
            ['SecuritiesInfo', 'SecurityInfo'],
            date_field=None)

    def open_positions(self, model: str) -> Dict[str, pd.DataFrame]:
        return self.flex_dict_to_df(
            model,
            ['OpenPositions', 'OpenPosition'],
            date_field='@reportDate')

    @staticmethod
    def calc_daily_qty(final_qty: float,
                       trades: pd.Series,
                       start_date: datetime,
                       end_date: datetime) -> pd.Series:
        """Calculates the daily position quantities based on the final quantity
        and the trades occurred during the period."""
        df = pd.concat(
            [pd.DataFrame(
                data={'position': [np.nan, final_qty]},
                index=[start_date, end_date]),
             trades.to_frame('trade_qty')])  # type: pd.DataFrame
        df.sort_index(inplace=True)

        df = df.resample('1D').sum()

        df.index.name = 'dt'
        df.reset_index(inplace=True)

        # Global fillna won't work with pandas 0.18:
        # https://github.com/pandas-dev/pandas/issues/7630
        df['trade_qty'].fillna(0, inplace=True)
        df['position'].fillna(0, inplace=True)

        # FIXME: looping is not nice
        # https://stackoverflow.com/questions/34855859/
        #   is-there-a-way-in-pandas-to-use-previous-row-value-
        #   in-dataframe-apply-when-previ
        for i in reversed(range(len(df)-1)):
            df.loc[i, 'position'] = \
                df.loc[i + 1, 'position'] - df.loc[i + 1, 'trade_qty']

        df.index = df['dt']
        df.index.name = None

        return df['position']

    def positions(self, model: str) -> pd.DataFrame:
        # FIXME: IEX does not have coverage for non-US or de-listed stocks
        # FIXME: this function is pretty slow
        all_equity_summary = self.equity_summary(model)
        all_trades = self.trades(model)
        all_open_positions = self.open_positions(model)
        stmts = self.stmts_for_model(model)

        positions = {}
        for model_name in all_equity_summary.keys():
            start_date = \
                pd.to_datetime(stmts[model_name]['@fromDate'], utc=True)
            end_date = \
                pd.to_datetime(stmts[model_name]['@toDate'], utc=True)

            equity_summary = all_equity_summary[model_name]
            trades = all_trades[model_name]
            open_positions = all_open_positions[model_name]
            symbols = pd.concat(
                [get_in([model_name, '@symbol'], all_open_positions,
                        default=pd.DataFrame()),
                 get_in([model_name, '@symbol'], all_trades,
                        default=pd.DataFrame())])  # type: pd.DataFrame

            if trades.empty:
                continue

            positions[model_name] = equity_summary['@cash'].copy()
            positions[model_name].name = 'cash'

            for symbol in symbols.unique():
                final_position_state = \
                    open_positions[
                        open_positions['@symbol'] == symbol]

                daily_trades_df = \
                    trades[trades['@symbol'] == symbol].resample('1B').sum()
                daily_trades_series = pd.Series() if daily_trades_df.empty \
                    else daily_trades_df['@quantity']

                final_qty = 0 if final_position_state.empty \
                    else final_position_state.iloc[0]['@position']

                quantity = self.calc_daily_qty(
                    final_qty=final_qty,
                    trades=daily_trades_series,
                    start_date=start_date,
                    end_date=end_date)

                equity_price = get_equity_price(
                    symbol,
                    start_date=start_date,
                    end_date=end_date)

                equity_qty = pd.concat(
                    [equity_price, quantity.to_frame('position')],
                    axis=1)  # type: pd.DataFrame

                # Resampling needed as price is represented for UTC midnight,
                # whereas qty is stored as EST midnight.
                equity_qty = equity_qty.resample('1D').sum()

                equity_qty['position'] = \
                    equity_qty['position'].fillna(method='bfill')

                position = equity_qty['position'] * equity_qty['price']
                position.name = symbol

                if position.empty:
                    # If empty series is concat'd to a df the result will be
                    # an empty df. Avoid this by setting nan for the column
                    positions[model_name][position.name] = np.nan
                    log.warning('No position info for {symbol}.'.format(
                        symbol=symbol))
                else:
                    positions[model_name] = \
                        pd.concat([positions[model_name], position],
                                  axis=1)

            positions[model_name] = \
                positions[model_name].fillna(0).sort_index()

            # Drop the lines where there are no position held
            positions[model_name] = \
                positions[model_name].loc[
                    ~(positions[model_name].drop('cash', axis=1) == 0)
                    .all(axis=1)]

        summed_positions = None  # type: Optional[pd.DataFrame]
        for position in positions.values():
            if summed_positions is None:
                summed_positions = position
            else:
                summed_positions = summed_positions.add(position, fill_value=0)

        return summed_positions

    def transactions(self, model: str) -> pd.DataFrame:
        # FIXME: Remove forex transactions
        # TODO: commission comes as negative number, check if it is correct
        all_trades = self.trades(model)

        all_transactions = {}
        for model_name, trades in all_trades.items():
            if trades.empty:
                continue

            transactions = pd.DataFrame(
                data={
                    'amount': trades['@quantity'],
                    'commission': trades['@ibCommission'],
                    'order_id': trades['@ibExecID'],
                    'price': trades['@tradePrice'],
                    'symbol': trades['@symbol'],
                    'sid': trades['@symbol'],
                    'txn_dollars': trades['@netCash'],
                    'dt': trades.index
                },
                index=trades.index)

            all_transactions[model_name] = transactions

        merged_transactions = \
            pd.concat(all_transactions.values(), axis=0)  # type: pd.DataFrame

        return merged_transactions.sort_index()
