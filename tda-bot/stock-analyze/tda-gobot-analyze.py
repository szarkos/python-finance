#!/usr/bin/python3 -u

# Backtest a variety of algorithms and print a report

import os, sys
import time, datetime, pytz
import random
import re
import argparse
import pickle
from collections import OrderedDict

import robin_stocks.tda as tda
import tulipy as ti

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper
import tda_gobot_analyze_helper


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("--stock_usd", help='Amount of money (USD) to invest', default=1000, type=float)
parser.add_argument("--algo", help='Analyze the most recent 5-day and 10-day history for a stock ticker using this bot\'s algorithim(s) - (Default: stochrsi)', default='stochrsi-new', type=str)
parser.add_argument("--ofile", help='Dump the pricehistory data to pickle file', default=None, type=str)
parser.add_argument("--ifile", help='Use pickle file for pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--augment_ifile", help='Pull additional history data and append it to candles imported from ifile', action="store_true")
parser.add_argument("--weekly_ifile", help='Use pickle file for weekly pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--daily_ifile", help='Use pickle file for daily pricehistory data rather than accessing the API', default=None, type=str)

parser.add_argument("--start_date", help='The day to start trading (i.e. 2021-05-12). Typically useful for verifying history logs', default=None, type=str)
parser.add_argument("--stop_date", help='The day to stop trading (i.e. 2021-05-12)', default=None, type=str)
parser.add_argument("--skip_blacklist", help='Do not process blacklisted tickers', action="store_true")
parser.add_argument("--skip_perma_blacklist", help='Do not process permanently blacklisted tickers, but allow others that are less than 30-days old', action="store_true")
parser.add_argument("--skip_check", help="Skip fixup and check of stock ticker", action="store_true")
parser.add_argument("--unsafe", help='Allow trading between 9:30-10:15AM where volatility is high', action="store_true")
parser.add_argument("--hold_overnight", help='Allow algorithm to hold stocks across multiple days', action="store_true")

parser.add_argument("--no_use_resistance", help='Do no use the high/low resistance to avoid possibly bad trades (Default: False)', action="store_true")
parser.add_argument("--use_vwap", help='Use vwap resistance checks to enter trades (Default: True if --no_use_resistance=False)', action="store_true")
parser.add_argument("--use_pdc", help='Use previous day close resistance level checks to enter trades (Default: True if --no_use_resistance=False)', action="store_true")
parser.add_argument("--use_keylevel", help='Use key level checks to enter trades (Default: True if --no_use_resistance=False)', action="store_true")
parser.add_argument("--keylevel_strict", help='Use strict key level checks to enter trades (Default: False)', action="store_true")
parser.add_argument("--keylevel_use_daily", help='Use daily candles as well as weeklies to determine key levels (Default: False)', action="store_true")
parser.add_argument("--price_resistance_pct", help='Resistance indicators will come into effect if price is within this percentage of a known support/resistance line', default=1, type=float)
parser.add_argument("--price_support_pct", help='Support indicators will come into effect if price is within this percentage of a known support/resistance line', default=1, type=float)
parser.add_argument("--resist_pct_dynamic", help='Calculate price_resistance_pct/price_support_pct dynamically', action="store_true")
parser.add_argument("--use_natr_resistance", help='Enable the daily NATR resistance check', action="store_true")
parser.add_argument("--use_pivot_resistance", help='Enable the use of pivot points and PDH/PDL resistance check', action="store_true")
parser.add_argument("--lod_hod_check", help='Enable low of the day (LOD) / high of the day (HOD) resistance checks', action="store_true")
parser.add_argument("--va_check", help='Use the previous day Value Area High (VAH) Value Area Low (VAL) as resistance', action="store_true")

parser.add_argument("--check_etf_indicators", help='Use the relative strength against one or more ETF indicators to assist with trade entry', action="store_true")
parser.add_argument("--check_etf_indicators_strict", help='Do not allow trade unless check_etf_indicators agrees with direction', action="store_true")
parser.add_argument("--etf_tickers", help='List of tickers to use with --check_etf_indicators (Default: SPY)', default='SPY', type=str)
parser.add_argument("--etf_roc_period", help='Rate of change lookback period (Default: 50)', default=50, type=int)
parser.add_argument("--etf_roc_type", help='Rate of change candles type to use with algorithm (Default: hlc3)', default='hlc3', type=str)
parser.add_argument("--etf_min_rs", help='ETF minimum relative strength (Default: None)', default=None, type=float)
parser.add_argument("--etf_min_roc", help='ETF minimum rate-of-change (Default: None)', default=None, type=float)
parser.add_argument("--etf_min_natr", help='ETF minimum NATR (Default: None)', default=None, type=float)

parser.add_argument("--etf_use_emd", help='Use MESA EMD to check cycle vs. trend mode of the ETF', action="store_true")
parser.add_argument("--etf_emd_fraction", help='MESA EMD fraction to use with ETF', default=0.1, type=float)
parser.add_argument("--etf_emd_period", help='MESA EMD period to use with ETF', default=20, type=int)
parser.add_argument("--etf_emd_type", help='MESA EMD type to use with ETF', default='hl2', type=str)

parser.add_argument("--with_trin", help='Use $TRIN indicator', action="store_true")
parser.add_argument("--trin_roc_type", help='Rate of change candles type to use with $TRIN algorithm (Default: hlc3)', default='hlc3', type=str)
parser.add_argument("--trin_roc_period", help='Rate of change period to use with $TRIN algorithm (Default: 1)', default=1, type=int)
parser.add_argument("--trin_ma_type", help='MA type to use with $TRIN algorithm (Default: ema)', default='ema', type=str)
parser.add_argument("--trin_ma_period", help='Period to use with $TRIN moving average (Default: 5)', default=5, type=int)
parser.add_argument("--trin_oversold", help='Oversold threshold for $TRIN algorithm (Default: 3)', default=3, type=float)
parser.add_argument("--trin_overbought", help='Overbought threshold for $TRIN algorithm (Default: -1)', default=-1, type=float)

parser.add_argument("--with_tick", help='Use $TICK indicator', action="store_true")
parser.add_argument("--tick_threshold", help='+/- threshold level before triggering a signal (Default: 50)', default=50, type=int)
parser.add_argument("--tick_ma_type", help='MA type to use with $TICK algorithm (Default: ema)', default='ema', type=str)
parser.add_argument("--tick_ma_period", help='Period to use with ROC algorithm (Default: 5)', default=5, type=int)

parser.add_argument("--with_roc", help='Use Rate-of-Change (ROC) indicator', action="store_true")
parser.add_argument("--roc_exit", help='Use Rate-of-Change (ROC) indicator to signal an exit', action="store_true")
parser.add_argument("--roc_type", help='Rate of change candles type to use (Default: hlc3)', default='hlc3', type=str)
parser.add_argument("--roc_period", help='Period to use with ROC algorithm (Default: 14)', default=14, type=int)
parser.add_argument("--roc_ma_type", help='MA period to use with ROC algorithm (Default: wma)', default='wma', type=str)
parser.add_argument("--roc_ma_period", help='MA period to use with ROC algorithm (Default: 4)', default=4, type=int)
parser.add_argument("--roc_threshold", help='Threshold to cancel the ROC algorithm (Default: 0.15)', default=0.15, type=float)

parser.add_argument("--with_sp_monitor", help='When trading an ETF like SPY, monitor a set of stocks with weighting to help determine how the ETF will move', action="store_true")
parser.add_argument("--sp_monitor_threshold", help='+/- threshold before triggering final signal (Default: 2)', default=2, type=float)
parser.add_argument("--sp_monitor_tickers", help='List of tickers and their weighting (in %) to use with --with_sp_monitor, comma-delimited (Example: MSFT:1.2,AAPL:1.0,...', default='', type=str)
parser.add_argument("--sp_roc_type", help='Rate of change candles type to use with sp_monitor (Default: hlc3)', default='hlc3', type=str)
parser.add_argument("--sp_roc_period", help='Period to use with ROC algorithm for sp_monitor (Default: 1)', default=1, type=int)
parser.add_argument("--sp_ma_period", help='Moving average period to use with the RoC values for sp_monitor (Default: 5)', default=5, type=int)
parser.add_argument("--sp_monitor_stacked_ma_type", help='Moving average type to use with sp_monitor stacked_ma (Default: vidya)', default='vidya', type=str)
parser.add_argument("--sp_monitor_stacked_ma_periods", help='Moving average periods to use with sp_monitor stacked_ma (Default: 8,13,21)', default='8,13,21', type=str)
parser.add_argument("--sp_monitor_use_trix", help='Use TRIX algorithm instead of stacked_ma to help gauge strength/direction of sp_monitor', action="store_true")
parser.add_argument("--sp_monitor_trix_ma_type", help='Moving average type to use with sp_monitor TRIX (Default: ema)', default='ema', type=str)
parser.add_argument("--sp_monitor_trix_ma_period", help='Moving average period to use with sp_monitor TRIX (Default: 8)', default=8, type=int)
parser.add_argument("--sp_monitor_strict", help='Enable some stricter checks when entering trades', action="store_true")

parser.add_argument("--with_vix", help='Use the VIX volatility index ticker as an indicator', action="store_true")
parser.add_argument("--vix_stacked_ma_periods", help='Moving average periods to use when calculating VIX stacked MA (Default: 5,8,13)', default='5,8,13', type=str)
parser.add_argument("--vix_stacked_ma_type", help='Moving average type to use when calculating VIX stacked MA (Default: ema)', default='ema', type=str)
parser.add_argument("--vix_use_ha_candles", help='Use Heikin Ashi candles when calculating the stacked MA', action="store_true")

parser.add_argument("--emd_affinity_long", help='Require EMD affinity to allow long trade (Default: None)', default=None, type=int)
parser.add_argument("--emd_affinity_short", help='Require EMD affinity to allow short trade (Default: None)', default=None, type=int)
parser.add_argument("--mesa_emd_fraction", help='MESA EMD fraction to use with --emd_affinity_long or --emd_affinity_short', default=0.1, type=float)
parser.add_argument("--mesa_emd_period", help='MESA EMD period to use with --emd_affinity_long or --emd_affinity_short', default=20, type=int)
parser.add_argument("--mesa_emd_type", help='MESA EMD type to use with --emd_affinity_long or --emd_affinity_short', default='hl2', type=str)

# Experimental
parser.add_argument("--experimental", help='Enable experimental features (Default: False)', action="store_true")
# Experimental

parser.add_argument("--primary_stoch_indicator", help='Use this indicator as the primary stochastic indicator (Default: stochrsi)', default='stochrsi', type=str)
parser.add_argument("--with_stoch_5m", help='Use 5-minute candles with the --primary_stoch_indicator', action="store_true")
parser.add_argument("--with_stochrsi_5m", help='Use StochRSI with 5-min candles as an additional stochastic indicator (Default: False)', action="store_true")
parser.add_argument("--with_stochmfi", help='Use StochMFI as an additional stochastic indicator (Default: False)', action="store_true")
parser.add_argument("--with_stochmfi_5m", help='Use StochMFI with 5-min candles as an additional stochastic indicator (Default: False)', action="store_true")

parser.add_argument("--with_stacked_ma", help='Use stacked MA as a secondary indicator for trade entries (Default: False)', action="store_true")
parser.add_argument("--stacked_ma_type", help='Moving average type to use (Default: kama)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods", help='List of MA periods to use, comma-delimited (Default: 5,8,13)', default='5,8,13', type=str)
parser.add_argument("--with_stacked_ma_secondary", help='Use stacked MA as a secondary indicator for trade entries (Default: False)', action="store_true")
parser.add_argument("--stacked_ma_type_secondary", help='Moving average type to use (Default: kama)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods_secondary", help='List of MA periods to use, comma-delimited (Default: 5,8,13)', default='5,8,13', type=str)
parser.add_argument("--stacked_ma_type_primary", help='Moving average type to use when stacked_ma is used as primary indicator (Default: kama)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods_primary", help='List of MA periods to use when stacked_ma is used as primary indicator, comma-delimited (Default: 5,8,13)', default='5,8,13', type=str)

parser.add_argument("--with_momentum", help='Use Momentum indicator as a secondary indicator for trade entries (Default: False)', action="store_true")
parser.add_argument("--momentum_type", help='OHLC type to use with Momentum indicator (Default: hl2)', default='hl2', type=str)
parser.add_argument("--momentum_period", help='Period to use with Momentum indicator (Default: 12)', default=12, type=int)
parser.add_argument("--momentum_use_trix", help='Use TRIX as Momentum indicator (Default: False)', action="store_true")

parser.add_argument("--daily_ma_type", help='Moving average type to use (Default: wma)', default='wma', type=str)
parser.add_argument("--confirm_daily_ma", help='Confirm that the daily moving average agrees with the direction stock entry', action="store_true")

parser.add_argument("--with_mama_fama", help='Use MESA Adaptive Moving Average as a secondary indicator for trade entries (Default: False)', action="store_true")
parser.add_argument("--mama_require_xover", help='When using MESA Adaptive Moving Average, require crossover of MAMA and FAMA to initiate signal (Default: False)', action="store_true")
parser.add_argument("--with_mesa_sine", help='Use MESA Sine Wave as a secondary indicator for trade entries (Default: False)', action="store_true")
parser.add_argument("--mesa_sine_strict", help='Use strict version of the MESA Sine Wave indicator (Default: False)', action="store_true")
parser.add_argument("--mesa_sine_period", help='Lookback period to use with MESA Sine Wave (Default: 25)', default=25, type=int)
parser.add_argument("--mesa_sine_type", help='Input type to use with MESA Sine Wave (Default: hl2)', default='hl2', type=str)

parser.add_argument("--with_rsi", help='Use standard RSI as a secondary indicator', action="store_true")
parser.add_argument("--with_rsi_simple", help='Use just the current RSI value as a secondary indicator', action="store_true")
parser.add_argument("--with_mfi", help='Use MFI (Money Flow Index) as a secondary indicator', action="store_true")
parser.add_argument("--with_mfi_simple", help='Use simple version of MFI (Money Flow Index) as a secondary indicator', action="store_true")
parser.add_argument("--with_adx", help='Use ADX as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_dmi", help='Use DMI as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_dmi_simple", help='Use DMI as secondary indicator to advise trade entries/exits, but do not wait for crossover (Default: False)', action="store_true")
parser.add_argument("--with_aroonosc", help='Use Aroon Oscillator as secondary indicator to advise trade entries (Default: False)', action="store_true")
parser.add_argument("--with_aroonosc_simple", help='Use Aroon Oscillator as secondary indicator to advise trade entries, but only evaluate AroonOsc value, not zero-line crossover (Default: False)', action="store_true")
parser.add_argument("--with_macd", help='Use MACD as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_macd_simple", help='Use MACD as secondary indicator to advise trade entries/exits, but do not wait for crossover (default=False)', action="store_true")
parser.add_argument("--with_vwap", help='Use VWAP as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_vpt", help='Use VPT as secondary indicator to advise trade entries (Default: False)', action="store_true")
parser.add_argument("--with_chop_index", help='Use the Choppiness Index as secondary indicator to advise trade entries (Default: False)', action="store_true")
parser.add_argument("--with_chop_simple", help='Use a simple version Choppiness Index as secondary indicator to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--with_supertrend", help='Use the Supertrend indicator as secondary indicator to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--supertrend_atr_period", help='ATR period to use for the supertrend indicator (Default: 128)', default=128, type=int)
parser.add_argument("--supertrend_min_natr", help='Minimum daily NATR a stock must have to enable supertrend indicator (Default: 5)', default=5, type=float)

parser.add_argument("--with_bbands_kchannel", help='Use the Bollinger bands and Keltner channel indicators as secondary to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--with_bbands_kchannel_simple", help='Use a simple version of the Bollinger bands and Keltner channel indicators as secondary to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--bbands_matype", help='Moving average type to use with Bollinger Bands calculation (Default: 0)', default=0, type=int)
parser.add_argument("--use_bbands_kchannel_5m", help='Use 5-minute candles to calculate the Bollinger bands and Keltner channel indicators (Default: False)', action="store_true")
parser.add_argument("--bbands_kchan_crossover_only", help='Only signal on Bollinger bands and Keltner channel crossover (Default: False)', action="store_true")
parser.add_argument("--use_bbands_kchannel_xover_exit", help='Use price action after a Bollinger bands and Keltner channel crossover to assist with stock exit (Default: False)', action="store_true")
parser.add_argument("--bbands_kchannel_straddle", help='Attempt straddle trade if primary trade is not working (Default: False)', action="store_true")
parser.add_argument("--bbands_kchannel_xover_exit_count", help='Number of periods to wait after a crossover to trigger --use_bbands_kchannel_xover_exit (Default: 10)', default=10, type=int)
parser.add_argument("--bbands_kchannel_offset", help='Percentage offset between the Bollinger bands and Keltner channel indicators to trigger an initial trade entry (Default: 0.15)', default=0.15, type=float)
parser.add_argument("--bbands_kchan_x1_xover", help='Require that the Bollinger bands cross between the Keltner channel with ATR multiplier == 1 (Default: False)', action="store_true")
parser.add_argument("--bbands_kchan_squeeze_count", help='Number of squeeze periods needed before triggering bbands_kchannel signal (Default: 8)', default=8, type=int)
parser.add_argument("--bbands_kchan_ma_check", help='Check price action in relation to a moving average during a squeeze to ensure price stays above or below a moving average (Default: False)', action="store_true")
parser.add_argument("--bbands_kchan_ma_type", help='Moving average type to use with bbands_kchan_ma_check (Default: ema)', default='ema', type=str)
parser.add_argument("--bbands_kchan_ma_ptype", help='Candle type to use when calculating moving average for use with bbands_kchan_ma_check (Default: close)', default='close', type=str)
parser.add_argument("--bbands_kchan_ma_period", help='Period to use when calculating moving average for use with bbands_kchan_ma_check (Default: 21)', default=21, type=int)
parser.add_argument("--max_squeeze_natr", help='Maximum NATR allowed during consolidation (squeeze) phase (Default: None)', default=None, type=float)
parser.add_argument("--max_bbands_natr", help='Maximum NATR between upper and lower Bolinger Bands allowed during consolidation (squeeze) phase (Default: None)', default=None, type=float)
parser.add_argument("--min_bbands_natr", help='Minimum NATR between upper and lower Bolinger Bands allowed during consolidation (squeeze) phase (Default: None)', default=None, type=float)
parser.add_argument("--bbands_roc_threshold", help='BBands rate of change threshold to trigger bbands signal (Default: 90)', default=90, type=float)
parser.add_argument("--bbands_roc_count", help='Number of times the BBands rate of change threshold must be met to trigger bbands signal (Default: 2)', default=2, type=int)
parser.add_argument("--bbands_roc_strict", help='Require a change in Bollinger Bands rate-of-change equivalent to --bbands_roc_threshold (Default: False) to signal', action="store_true")
parser.add_argument("--bbands_period", help='Period to use when calculating the Bollinger Bands (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_period", help='Period to use when calculating the Keltner channels (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_atr_period", help='Period to use when calculating the ATR for use with the Keltner channels (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_multiplier", help='Multiple to use when calculating upper and lower Keltner channels (Default: 1.5)', default=1.5, type=float)
parser.add_argument("--kchan_matype", help='MA type to use when calculating the Keltner Channel (Default: ema)', default='ema', type=str)

parser.add_argument("--aroonosc_with_macd_simple", help='When using Aroon Oscillator, use macd_simple as tertiary indicator if AroonOsc is less than +/- 70 (Default: False)', action="store_true")
parser.add_argument("--aroonosc_with_vpt", help='When using Aroon Oscillator, use vpt as tertiary indicator if AroonOsc is less than +/- 70 (Default: False)', action="store_true")
parser.add_argument("--aroonosc_secondary_threshold", help='AroonOsc threshold for when to enable macd_simple when --aroonosc_with_macd_simple is enabled (Default: 70)', default=72, type=float)
parser.add_argument("--adx_threshold", help='ADX threshold for when to trigger the ADX signal (Default: 25)', default=25, type=float)
parser.add_argument("--dmi_with_adx", help='Use ADX when confirming DI signal (Default: False)', action="store_true")

parser.add_argument("--days", help='Number of days to test. Separate with a comma to test multiple days.', default='10', type=str)
parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1.5, type=float)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (Default: False)', action="store_true")
parser.add_argument("--exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)
parser.add_argument("--strict_exit_percent", help='Only exit when exit_percent signals an exit, ignore stochrsi', action="store_true")
parser.add_argument("--variable_exit", help='Adjust incr_threshold, decr_threshold and exit_percent based on the price action of the stock over the previous hour', action="store_true")
parser.add_argument("--cost_basis_exit", help='Set stoploss to cost-basis if price improves by this percentile', default=None, type=float)

parser.add_argument("--use_ha_exit", help='Use Heikin Ashi candles with exit_percent-based exit strategy', action="store_true")
parser.add_argument("--use_ha_candles", help='Use Heikin Ashi candles with entry strategy', action="store_true")
parser.add_argument("--use_trend_exit", help='Use ttm_trend algorithm with exit_percent-based exit strategy', action="store_true")
parser.add_argument("--use_rsi_exit", help='Use stochastic RSI indicator as exit signal', action="store_true")
parser.add_argument("--use_mesa_sine_exit", help='Use MESA Sine wave indicator as exit signal', action="store_true")
parser.add_argument("--use_trend", help='Use ttm_trend algorithm with entry strategy', action="store_true")
parser.add_argument("--trend_type", help='Type to use with ttm_trend algorithm (Default: hl2)', default='hl2', type=str)
parser.add_argument("--trend_period", help='Period to use with ttm_trend algorithm (Default: 5)', default=5, type=int)
parser.add_argument("--use_combined_exit", help='Use both the ttm_trend algorithm and Heikin Ashi candles with exit_percent-based exit strategy', action="store_true")

parser.add_argument("--quick_exit", help='Exit immediately if an exit_percent strategy was set, do not wait for the next candle', action="store_true")
parser.add_argument("--quick_exit_percent", help='Exit immediately if --quick_exit and this profit target is achieved', default=None, type=float)
parser.add_argument("--trend_quick_exit", help='Enable quick exit when entering counter-trend moves', action="store_true")
parser.add_argument("--qe_stacked_ma_periods", help='Moving average periods to use with --trend_quick_exit (Default: )', default='34,55,89', type=str)
parser.add_argument("--qe_stacked_ma_type", help='Moving average type to use when calculating trend_quick_exit stacked_ma (Default: vidya)', default='vidya', type=str)

parser.add_argument("--blacklist_earnings", help='Blacklist trading one week before and after quarterly earnings dates (Default: False)', action="store_true")
parser.add_argument("--check_volume", help='Check the last several days (up to 6-days, depending on how much history is available) to ensure stock is not trading at a low volume threshold (Default: False)', action="store_true")
parser.add_argument("--avg_volume", help='Skip trading for the day unless the average volume over the last few days equals this value', default=1000000, type=int)
parser.add_argument("--min_volume", help='Skip trading for the day unless the daily volume over the last few days equals at least this value', default=1000000, type=int)
parser.add_argument("--min_ticker_age", help='Do not process tickers younger than this number of days (Default: None)', default=None, type=int)
parser.add_argument("--min_daily_natr", help='Do not process tickers with less than this daily NATR value (Default: None)', default=None, type=float)
parser.add_argument("--max_daily_natr", help='Do not process tickers with more than this daily NATR value (Default: None)', default=None, type=float)
parser.add_argument("--min_intra_natr", help='Minimum intraday NATR value to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--max_intra_natr", help='Maximum intraday NATR value to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--min_price", help='Minimum stock price to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--max_price", help='Maximum stock price to allow trade entry (Default: None)', default=None, type=float)

parser.add_argument("--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("--stochrsi_period", help='RSI period to use for StochRSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("--stochrsi_5m_period", help='RSI period to use for StochRSI calculation (Default: 28)', default=28, type=int)
parser.add_argument("--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_k_period", help='k period to use in StochRSI algorithm', default=128, type=int)
parser.add_argument("--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='hlc3', type=str)
parser.add_argument("--rsi_high_limit", help='RSI high limit', default=80, type=int)
parser.add_argument("--rsi_low_limit", help='RSI low limit', default=20, type=int)
parser.add_argument("--stochrsi_offset", help='Offset between K and D to determine strength of trend', default=8, type=float)
parser.add_argument("--nocrossover", help='Modifies the algorithm so that k and d crossovers will not generate a signal (Default: False)', action="store_true")
parser.add_argument("--crossover_only", help='Modifies the algorithm so that only k and d crossovers will generate a signal (Default: False)', action="store_true")

parser.add_argument("--stochmfi_period", help='Money Flow Index (MFI) period to use for StochMFI calculation (Default: 14)', default=14, type=int)
parser.add_argument("--stochmfi_5m_period", help='Money Flow Index (MFI) period to use for StochMFI calculation using 5-minute candles (Default: 14)', default=14, type=int)
parser.add_argument("--mfi_period", help='Money Flow Index (MFI) period', default=14, type=int)
parser.add_argument("--mfi_high_limit", help='MFI high limit', default=80, type=int)
parser.add_argument("--mfi_low_limit", help='MFI low limit', default=20, type=int)

parser.add_argument("--atr_period", help='Average True Range period for intraday calculations', default=14, type=int)
parser.add_argument("--daily_atr_period", help='Average True Range period for daily calculations', default=3, type=int)
parser.add_argument("--vpt_sma_period", help='SMA period for VPT signal line', default=72, type=int)
parser.add_argument("--adx_period", help='ADX period', default=92, type=int)
parser.add_argument("--di_period", help='Plus/Minus DI period', default=48, type=int)
parser.add_argument("--aroonosc_period", help='Aroon Oscillator period', default=24, type=int)
parser.add_argument("--aroonosc_alt_period", help='Alternate Aroon Oscillator period for higher volatility stocks', default=48, type=int)
parser.add_argument("--aroonosc_alt_threshold", help='Threshold for enabling the alternate Aroon Oscillator period for higher volatility stocks', default=0.24, type=float)

parser.add_argument("--chop_period", help='Choppiness Index period', default=14, type=int)
parser.add_argument("--chop_low_limit", help='Choppiness Index low limit', default=38.2, type=float)
parser.add_argument("--chop_high_limit", help='Choppiness Index high limit', default=61.8, type=float)

parser.add_argument("--macd_short_period", help='MACD short (fast) period', default=48, type=int)
parser.add_argument("--macd_long_period", help='MACD long (slow) period', default=104, type=int)
parser.add_argument("--macd_signal_period", help='MACD signal (length) period', default=36, type=int)
parser.add_argument("--macd_offset", help='MACD offset for signal lines', default=0.006, type=float)

parser.add_argument("--stochrsi_signal_cancel_low_limit", help='Limit used to cancel StochRSI short signals', default=60, type=int)
parser.add_argument("--stochrsi_signal_cancel_high_limit", help='Limit used to cancel StochRSI long signals', default=40, type=int)
parser.add_argument("--rsi_signal_cancel_low_limit", help='Limit used to cancel RSI short signals', default=60, type=int)
parser.add_argument("--rsi_signal_cancel_high_limit", help='Limit used to cancel RSI long signals', default=40, type=int)
parser.add_argument("--mfi_signal_cancel_low_limit", help='Limit used to cancel MFI short signals', default=60, type=int)
parser.add_argument("--mfi_signal_cancel_high_limit", help='Limit used to cancel MFI long signals', default=40, type=int)

parser.add_argument("--noshort", help='Disable short selling of stock', action="store_true")
parser.add_argument("--shortonly", help='Only short sell the stock', action="store_true")

parser.add_argument("--verbose", help='Print additional information about each transaction (Default: False)', action="store_true")
parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
parser.add_argument("--debug_all", help='Enable extra debugging output', action="store_true")

# Obsolete, but it would have been cool if it worked...
#parser.add_argument("--use_candle_monitor", help='Enable the trivial candle monitor (Default: False)', action="store_true")

args		= parser.parse_args()
args.debug	= True	# Should default to False eventually, testing for now

decr_threshold	= args.decr_threshold
incr_threshold	= args.incr_threshold

stock		= args.stock
stock_usd	= args.stock_usd

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv(dotenv_path=parent_path+'/../.env') != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        exit(1)

tda_account_number			= int( os.environ["tda_account_number"] )
passcode				= os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda			= tda
tda_gobot_analyze_helper.tda		= tda
tda_gobot_helper.passcode		= passcode
tda_gobot_analyze_helper.passcode	= passcode
tda_gobot_helper.tda_account_number	= tda_account_number

if ( args.skip_check == False ):
	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure', file=sys.stderr)
		sys.exit(1)

# Fix up and sanity check the stock symbol before proceeding
if ( args.skip_check == False ):
	stock = tda_gobot_helper.fix_stock_symbol(stock)
	ret = tda_gobot_helper.check_stock_symbol(stock)
	if ( isinstance(ret, bool) and ret == False ):
		print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
		sys.exit(1)

# Check if stock is in the blacklist
if ( tda_gobot_helper.check_blacklist(stock) == True ):
	if ( args.skip_blacklist == True ):
		print('(' + str(stock) + ') WARNING: skipping ' + str(stock) + ' because it is currently blacklisted and --skip_blacklist is set.', file=sys.stderr)
		sys.exit(1)
	else:
		print('(' + str(stock) + ') WARNING: stock ' + str(stock) + ' is currently blacklisted')

if ( args.skip_perma_blacklist == True ):
	if ( tda_gobot_helper.check_blacklist(ticker=stock, permaban_only=True) == True ):
		print('(' + str(stock) + ') WARNING: skipping ' + str(stock) + ' because it is permanently blacklisted and --skip_perma_blacklist is set.', file=sys.stderr)
		sys.exit(1)


# Confirm that we can short this stock
if ( args.ifile == None ):
	if ( args.noshort == False or args.shortonly == True ):
		data,err = tda.stocks.get_quote(stock, True)
		if ( err != None ):
			print('Error: get_quote(' + str(stock) + '): ' + str(err), file=sys.stderr)

		if ( str(data[stock]['shortable']) == str(False) or str(data[stock]['marginable']) == str(False) ):
			if ( args.shortonly == True ):
				print('Error: stock(' + str(stock) + '): does not appear to be shortable, exiting.')
				exit(1)

			if ( args.noshort == False ):
				print('Warning: stock(' + str(stock) + '): does not appear to be shortable, disabling sell-short')
				args.noshort = True


# tda.get_price_history() variables
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone
tda_gobot_analyze_helper.mytimezone = mytimezone

safe_open = True
if ( args.unsafe == True ):
	safe_open = False

p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

# RSI variables
rsi_type = args.rsi_type
rsi_period = args.rsi_period
rsi_slow = args.rsi_slow
cur_rsi = 0
prev_rsi = 0
rsi_low_limit = args.rsi_low_limit
rsi_high_limit = args.rsi_high_limit

# Report colors
red = '\033[0;31m'
green = '\033[0;32m'
reset_color = '\033[0m'
text_color = ''

# Get general info about the stock
marginable = None
shortable = None
delayed = True
volatility = 0
lastprice = 0
high = low = 0

if ( args.ifile == None ):

	try:
		data,err = tda.stocks.get_quote(stock, True)
		if ( err == None and data != {} ):
			if ( str(data[stock]['marginable']) == 'True' ):
				marginable = True
			if ( str(data[stock]['shortable']) == 'True' ):
				shortable = True
			if ( str(data[stock]['delayed']) == 'False' ):
				delayed = False

			volatility = data[stock]['volatility'] # FIXME: I don't know what this means yet
			lastprice = data[stock]['lastPrice']
			high = data[stock]['52WkHigh']
			low = data[stock]['52WkLow']

	except Exception as e:
		print('Caught exception in tda.stocks.get_quote(' + str(stock) + '): ' + str(e))
		pass

print()
print( 'Stock summary for "' + str(stock) + "\"\n" )
print( 'Last Price: $' + str(lastprice) )
print( 'Amount Per Trade: $' + str(stock_usd) )
print( '52WkHigh: $' + str(high) )
print( '52WkLow: $' + str(low) )

text_color = green
if ( shortable == False ):
	text_color = red
print( 'Shortable: ' + text_color + str(shortable) + reset_color )

text_color = green
if ( marginable == False ):
	text_color = red
print( 'Marginable: ' + text_color + str(marginable) + reset_color )

text_color = green
if ( delayed == True ):
	text_color = red
print( 'Delayed: ' + text_color + str(delayed) + reset_color )
print( 'Volatility: ' + str(volatility) )
print()


# --algo=rsi, --algo=stochrsi
for algo in args.algo.split(','):

	algo = algo.lower()
	if ( algo != 'rsi' and algo != 'stochrsi' and algo != 'stochrsi-new'):
		print('Unsupported algorithm "' + str(algo) + '"')
		continue

	if ( args.ifile != None ):
		try:
			with open(args.ifile, 'rb') as handle:
				data = handle.read()
				data = pickle.loads(data)

		except Exception as e:
			print('Error opening file ' + str(args.ifile) + ': ' + str(e))
			exit(1)

		args.days = -1

		# Add data to ifile to ensure we have enough history to perform calculations
		if ( args.augment_ifile == True ):

			days = 3
			time_now = datetime.datetime.now( mytimezone )
			time_prev = time_now - datetime.timedelta( days=days )

			# Make sure start and end dates don't land on a weekend
			#  or outside market hours
			time_now = tda_gobot_helper.fix_timestamp(time_now)
			time_prev = tda_gobot_helper.fix_timestamp(time_prev)

			time_now_epoch = int( time_now.timestamp() * 1000 )
			time_prev_epoch = int( time_prev.timestamp() * 1000 )

			try:
				ph_data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(ticker) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
				continue

			if ( ph_data == False ):
				continue

			# Populate new_data up until the last date
			new_data = { 'candles': [],
				     'symbol': ph_data['symbol'] }

			last_date = float( data['candles'][0]['datetime'] )
			for idx,key in enumerate(ph_data['candles']):
				if ( float(key['datetime']) < last_date ):
					new_data['candles'].append( ph_data['candles'][idx] )
				else:
					break

			for idx,key in enumerate(data['candles']):
				new_data['candles'].append( data['candles'][idx] )

			data = new_data
			del(new_data, ph_data)

	# Weekly Candles
	data_weekly = None
	if ( args.weekly_ifile != None ):
		try:
			with open(args.weekly_ifile, 'rb') as handle:
				data_weekly = handle.read()
				data_weekly = pickle.loads(data_weekly)

		except Exception as e:
			print('Error opening file ' + str(args.weekly_ifile) + ': ' + str(e))
			exit(1)

	# Daily Candles
	data_daily = None
	if ( args.daily_ifile != None ):
		try:
			with open(args.daily_ifile, 'rb') as handle:
				data_daily = handle.read()
				data_daily = pickle.loads(data_daily)

		except Exception as e:
			print('Error opening file ' + str(args.daily_ifile) + ': ' + str(e))
			exit(1)

	# ETF Indicators
	etf_tickers = args.etf_tickers.split(',')
	etf_indicators = {}
	for t in etf_tickers:
		etf_indicators[t] = {	'pricehistory':		{},
					'pricehistory_5m':	{},
					'roc':			{},
					'roc_close':		{},
					'stacked_ma':		{},
					'roc_stacked_ma':	{},
					'mama_fama':		{},
					'mesa_emd':		{},
					'natr':			{},
					'last_dt':		0
		}

	if ( args.check_etf_indicators == True ):
		if ( args.ifile != None ):
			for t in etf_tickers:
				etf_data	= None
				stock_path	= re.sub('\/[a-zA-Z0-9\.\-_]*$', '', args.ifile)
				etf_ifile	= re.sub('^.*\/' + str(stock), '', args.ifile)
				etf_ifile	= stock_path + '/' + str(t) + etf_ifile
				try:
					with open(etf_ifile, 'rb') as handle:
						etf_data = handle.read()
						etf_data = pickle.loads(etf_data)

				except Exception as e:
					print('Error opening file ' + str(etf_ifile) + ': ' + str(e))
					sys.exit(1)

				etf_indicators[t]['pricehistory']	= etf_data
				etf_indicators[t]['pricehistory_5m']	= tda_gobot_helper.translate_1m( pricehistory=etf_indicators[t]['pricehistory'], candle_type=5 )
				etf_indicators[t]['pricehistory']	= tda_gobot_helper.translate_heikin_ashi( pricehistory=etf_indicators[t]['pricehistory'] )

		else:
			days = 9
			time_now = datetime.datetime.now( mytimezone )
			time_prev = time_now - datetime.timedelta( days=days )

			# Make sure start and end dates don't land on a weekend
			#  or outside market hours
			time_prev = tda_gobot_helper.fix_timestamp(time_prev)
			if ( int(time_now.strftime('%w')) == 0 or int(time_now.strftime('%w')) == 6 ): # 0=Sunday, 6=Saturday
				time_now = tda_gobot_helper.fix_timestamp(time_now)

			time_now_epoch = int( time_now.timestamp() * 1000 )
			time_prev_epoch = int( time_prev.timestamp() * 1000 )

			for t in etf_tickers:

				etf_data = []
				try:
					etf_data, epochs = tda_gobot_helper.get_pricehistory(t, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

				except Exception as e:
					print('Caught Exception: get_pricehistory(' + str(t) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
					continue

				etf_indicators[t]['pricehistory']	= etf_data
				etf_indicators[t]['pricehistory_5m']	= tda_gobot_helper.translate_1m(pricehistory=etf_indicators[t]['pricehistory'], candle_type=5)


	# $TRIN and $TICK Indicators
	trin_tick = {	'trin': {	'pricehistory':		{},
					'pricehistory_5m':	{},
					'roc':			OrderedDict(),
					'roc_ma':		{}
				},
			'trinq': {	'pricehistory':		{},
					'pricehistory_5m':	{},
					'roc':			OrderedDict(),
				},
			'trina': {	'pricehistory':		{},
					'pricehistory_5m':	{},
					'roc':			OrderedDict(),
				},

			'tick': {	'pricehistory':		{},
					'pricehistory_5m':	{},
					'roc':			OrderedDict(),
					'roc_ma':		{}
				},
			'ticka': {	'pricehistory':		{},
					'pricehistory_5m':	{},
					'roc':			OrderedDict(),
					'roc_ma':		{}
				},
	}

	if ( args.with_trin == True or args.primary_stoch_indicator == 'trin' or args.with_tick == True ):
		if ( args.ifile != None ):
			trin_data	= None
			trinq_data	= None
			tick_data	= None

			stock_path	= re.sub('\/[a-zA-Z0-9\.\-_]*$', '', args.ifile)
			ifile		= re.sub('^.*\/' + str(stock), '', args.ifile)
			trin_ifile	= stock_path + '/TRIN' + ifile
			trinq_ifile	= stock_path + '/TRINQ' + ifile
			trina_ifile	= stock_path + '/TRINA' + ifile
			tick_ifile	= stock_path + '/TICK' + ifile

			try:
				with open(trin_ifile, 'rb') as handle:
					trin_data = handle.read()
					trin_data = pickle.loads(trin_data)

			#	with open(trinq_ifile, 'rb') as handle:
			#		trinq_data = handle.read()
			#		trinq_data = pickle.loads(trinq_data)

				with open(trina_ifile, 'rb') as handle:
					trina_data = handle.read()
					trina_data = pickle.loads(trina_data)

				with open(tick_ifile, 'rb') as handle:
					tick_data = handle.read()
					tick_data = pickle.loads(tick_data)

			except Exception as e:
				print('Error opening file: ' + str(e))
				sys.exit(1)

			trin_tick['trin']['pricehistory']	= trin_data
			trin_tick['trin']['pricehistory_5m']	= tda_gobot_helper.translate_1m( pricehistory=trin_tick['trin']['pricehistory'], candle_type=5 )

			#trin_tick['trinq']['pricehistory']	= trinq_data
			#trin_tick['trinq']['pricehistory_5m']	= tda_gobot_helper.translate_1m( pricehistory=trin_tick['trinq']['pricehistory'], candle_type=5 )

			trin_tick['trina']['pricehistory']	= trina_data
			trin_tick['trina']['pricehistory_5m']	= tda_gobot_helper.translate_1m( pricehistory=trin_tick['trina']['pricehistory'], candle_type=5 )

			trin_tick['tick']['pricehistory']	= tick_data
			trin_tick['tick']['pricehistory_5m']	= tda_gobot_helper.translate_1m( pricehistory=trin_tick['tick']['pricehistory'], candle_type=5 )

			# FIXME: disabling ticka for now
			trin_tick['ticka']['pricehistory']	= tick_data

		else:
			days = 10
			time_now	= datetime.datetime.now( mytimezone )
			time_prev	= time_now - datetime.timedelta( days=days )

			# Make sure start and end dates don't land on a weekend
			#  or outside market hours
			#if ( int(time_now.strftime('%w')) == 0 or int(time_now.strftime('%w')) == 6 ): # 0=Sunday, 6=Saturday
			time_now = tda_gobot_helper.fix_timestamp(time_now)
			time_prev = tda_gobot_helper.fix_timestamp(time_prev)

			time_now_epoch	= int( time_now.timestamp() * 1000 )
			time_prev_epoch	= int( time_prev.timestamp() * 1000 )

			trin_data	= []
			trinq_data	= []
			trina_data	= []

			tick_data	= []
			ticka_data	= []
			try:
				trin_data, epochs	= tda_gobot_helper.get_pricehistory('$TRIN', p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=False, debug=False)
			#	trinq_data, epochs	= tda_gobot_helper.get_pricehistory('$TRINQ', p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=False, debug=False)
				trina_data, epochs	= tda_gobot_helper.get_pricehistory('$TRINA', p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=False, debug=False)

				tick_data, epochs	= tda_gobot_helper.get_pricehistory('$TICK', p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=False, debug=False)
				ticka_data, epochs	= tda_gobot_helper.get_pricehistory('$TICKA', p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=False, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
				continue

			if ( len(trin_data['candles']) == 0 ):
				print('Warning: trin_data[] is empty!', file=sys.stderr)
			#if ( len(trinq_data['candles']) == 0 ):
			#	print('Warning: trinq_data[] is empty!', file=sys.stderr)
			if ( len(trina_data['candles']) == 0 ):
				print('Warning: trina_data[] is empty!', file=sys.stderr)

			trin_tick['trin']['pricehistory']	= trin_data
			trin_tick['trin']['pricehistory_5m']	= tda_gobot_helper.translate_1m(pricehistory=trin_tick['trin']['pricehistory'], candle_type=5)

			#trin_tick['trinq']['pricehistory']	= trinq_data
			#trin_tick['trinq']['pricehistory_5m']	= tda_gobot_helper.translate_1m(pricehistory=trin_tick['trinq']['pricehistory'], candle_type=5)

			trin_tick['trina']['pricehistory']	= trina_data
			trin_tick['trina']['pricehistory_5m']	= tda_gobot_helper.translate_1m(pricehistory=trin_tick['trina']['pricehistory'], candle_type=5)

			if ( len(tick_data['candles']) == 0 ):
				print('Warning: tick_data[] is empty!')

			trin_tick['tick']['pricehistory']	= tick_data
			trin_tick['tick']['pricehistory_5m']	= tda_gobot_helper.translate_1m(pricehistory=trin_tick['tick']['pricehistory'], candle_type=5)

			trin_tick['ticka']['pricehistory']	= tick_data
#			trin_tick['ticka']['pricehistory']	= ticka_data
#			trin_tick['ticka']['pricehistory_5m']	= tda_gobot_helper.translate_1m(pricehistory=trin_tick['tick']['pricehistory'], candle_type=5)

	# ETF SP monitor
	sp_monitor_tickers	= args.sp_monitor_tickers.split(',')
	sp_monitor		= {	'roc_ma':	OrderedDict(),
					'stacked_ma':	OrderedDict(),
					'trix':		OrderedDict(),
					'trix_signal':	OrderedDict() }
	for t in sp_monitor_tickers:
		try:
			sp_t = str(t.split(':')[0])
		except:
			print('Warning, invalid sp_monitor ticker format, skipping(' + str(t) + '): ' + str(e))
			continue

		sp_monitor[sp_t]	= {	'pricehistory':		{},
						'pricehistory_5m':	{}
		}

	if ( args.with_sp_monitor == True or args.primary_stoch_indicator == 'sp_monitor' ):
		for t in sp_monitor_tickers:
			try:
				sp_t = str(t.split(':')[0])
			except:
				print('Warning, invalid sp_monitor ticker format, skipping(' + str(t) + '): ' + str(e))
				continue

			if ( args.ifile != None ):
				sp_data		= None
				stock_path	= re.sub('\/[a-zA-Z0-9\.\-_]*$', '', args.ifile)
				sp_ifile	= re.sub('^.*\/' + str(stock), '', args.ifile)
				sp_ifile	= stock_path + '/' + str(sp_t) + sp_ifile
				try:
					with open(sp_ifile, 'rb') as handle:
						sp_data = handle.read()
						sp_data = pickle.loads(sp_data)

				except Exception as e:
					print('Error opening file ' + str(sp_ifile) + ': ' + str(e))
					sys.exit(1)

				sp_monitor[sp_t]['pricehistory']	= sp_data
				sp_monitor[sp_t]['pricehistory_5m']	= tda_gobot_helper.translate_1m( pricehistory=sp_monitor[sp_t]['pricehistory'], candle_type=5 )

			else:
				days = 9
				time_now = datetime.datetime.now( mytimezone )
				time_prev = time_now - datetime.timedelta( days=days )

				# Make sure start and end dates don't land on a weekend
				#  or outside market hours
				time_prev = tda_gobot_helper.fix_timestamp(time_prev)
				if ( int(time_now.strftime('%w')) == 0 or int(time_now.strftime('%w')) == 6 ): # 0=Sunday, 6=Saturday
					time_now = tda_gobot_helper.fix_timestamp(time_now)

				time_now_epoch = int( time_now.timestamp() * 1000 )
				time_prev_epoch = int( time_prev.timestamp() * 1000 )

				sp_data = []
				try:
					sp_data, epochs = tda_gobot_helper.get_pricehistory(sp_t, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

				except Exception as e:
					print('Caught Exception: get_pricehistory(' + str(sp_t) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
					sys.exit(1)

				if ( isinstance(sp_data, bool) and sp_data == False ):
					print('Error: get_pricehistory(' + str(sp_t) + ') returned False, exiting')
					sys.exit(1)

				sp_monitor[sp_t]['pricehistory']	= sp_data
				sp_monitor[sp_t]['pricehistory_5m']	= tda_gobot_helper.translate_1m(pricehistory=sp_monitor[sp_t]['pricehistory'], candle_type=5)

	# VIX - volatility index
	vix = {	'pricehistory':	{},
		'ma':		OrderedDict(),
	}
	if ( args.with_vix == True ):
		if ( args.ifile != None ):
			vix_data	= None

			stock_path	= re.sub('\/[a-zA-Z0-9\.\-_]*$', '', args.ifile)
			ifile		= re.sub('^.*\/' + str(stock), '', args.ifile)
			vix_ifile	= stock_path + '/VXX' + ifile

			try:
				with open(vix_ifile, 'rb') as handle:
					vix_data = handle.read()
					vix_data = pickle.loads(vix_data)

			except Exception as e:
				print('Error opening file: ' + str(e))
				sys.exit(1)

			vix['pricehistory'] = vix_data
			vix['pricehistory'] = tda_gobot_helper.translate_heikin_ashi(pricehistory=vix['pricehistory'])

		else:
			days = 9
			time_now = datetime.datetime.now( mytimezone )
			time_prev = time_now - datetime.timedelta( days=days )

			# Make sure start and end dates don't land on a weekend
			#  or outside market hours
			time_prev = tda_gobot_helper.fix_timestamp(time_prev)
			if ( int(time_now.strftime('%w')) == 0 or int(time_now.strftime('%w')) == 6 ): # 0=Sunday, 6=Saturday
				time_now = tda_gobot_helper.fix_timestamp(time_now)

			time_now_epoch = int( time_now.timestamp() * 1000 )
			time_prev_epoch = int( time_prev.timestamp() * 1000 )

			vix_data = []
			try:
#				vix_data, epochs = tda_gobot_helper.get_pricehistory('$VIX.X', p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)
				vix_data, epochs = tda_gobot_helper.get_pricehistory('VXX', p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
				continue

			if ( isinstance(vix_data, bool) and vix_data == False ):
				print('Error: get_pricehistory($VIX.X) returned False, exiting')
				sys.exit(1)

			vix['pricehistory'] = vix_data
			vix['pricehistory'] = tda_gobot_helper.translate_heikin_ashi(pricehistory=vix['pricehistory'])

	# Print results for the most recent 10 and 5 days of data
	for days in str(args.days).split(','):

		# Pull the 1-minute stock history
		# Note: Not asking for extended hours for now since our bot doesn't even trade after hours
		if ( args.ifile != None ):
			# Use ifile for data
			start_day = data['candles'][0]['datetime']
			end_day = data['candles'][-1]['datetime']

			start_day = datetime.datetime.fromtimestamp(float(start_day)/1000, tz=mytimezone)
			end_day = datetime.datetime.fromtimestamp(float(end_day)/1000, tz=mytimezone)

			delta = start_day - end_day
			days = str(abs(int(delta.days)))

		elif ( days != '-1' ):
			try:
				days = int(days)
			except:
				print('Error, days (' + str(days) + ') is not an integer - exiting.')
				exit(1)

			if ( days > 10 ):
				days = 10 # TDA API only allows 10-days of 1-minute daily data
			elif ( days < 3 ):
				days += 2

			try:
				data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, days, needExtendedHoursData=True, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(ticker) + '): ' + str(e))
				continue

		# Specifying days=-1 will get you the most recent info we can from the API
		# But we still need to ask for a few days in order to force it to give us at least two days of data
		else:
			days = 9
			time_now = datetime.datetime.now( mytimezone )
			time_prev = time_now - datetime.timedelta( days=days )

			# Make sure start and end dates don't land on a weekend
			#  or outside market hours
			time_prev = tda_gobot_helper.fix_timestamp(time_prev)
			if ( int(time_now.strftime('%w')) == 0 or int(time_now.strftime('%w')) == 6 ): # 0=Sunday, 6=Saturday
				time_now = tda_gobot_helper.fix_timestamp(time_now)

			time_now_epoch = int( time_now.timestamp() * 1000 )
			time_prev_epoch = int( time_prev.timestamp() * 1000 )

			try:
				data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(ticker) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
				continue

		if ( data == False ):
			continue

		if ( int(len(data['candles'])) <= rsi_period ):
			print('Not enough data - returned candles=' + str(len(data['candles'])) + ', rsi_period=' + str(rsi_period))
			continue

		# Translate and add Heiken Ashi candles to pricehistory (will add new array called data['hacandles'])
		data = tda_gobot_helper.translate_heikin_ashi(pricehistory=data)

		# Dump pickle data if requested
		if ( args.ofile != None ):
			try:
				file = open(args.ofile, "wb")
				pickle.dump(data, file)
				file.close()
			except Exception as e:
				print('Unable to write to file ' + str(args.ofile) + ': ' + str(e))

		# Subtract 1 because stochrsi_analyze_new() skips the first day of data
		days = int(days) - 1

		# Run the analyze function
		print('Analyzing ' + str(days) + '-day history for stock ' + str(stock) + ' using the ' + str(algo) + " algorithm:")
		print()
		print('### Debug Logs ###')

		if ( algo == 'rsi' ):
			print('Deprecated: see branch 1.0 for this algorithm')
			sys.exit(1)

		elif ( algo == 'stochrsi' or algo == 'stochrsi-new' ):

			test_params = {
					# Test range and input options
					'stock_usd':				args.stock_usd,

					'start_date':				args.start_date,
					'stop_date':				args.stop_date,
					'safe_open':				safe_open,
					'weekly_ph':				data_weekly,
					'daily_ph':				data_daily,

					'debug':				args.debug,
					'debug_all':				args.debug_all,

					# Trade exit parameters
					'incr_threshold':			args.incr_threshold,
					'decr_threshold':			args.decr_threshold,
					'stoploss':				args.stoploss,
					'exit_percent':				args.exit_percent,
					'strict_exit_percent':			args.strict_exit_percent,
					'variable_exit':			args.variable_exit,
					'cost_basis_exit':			args.cost_basis_exit,

					'use_ha_exit':				args.use_ha_exit,
					'use_ha_candles':			args.use_ha_candles,
					'use_trend_exit':			args.use_trend_exit,
					'use_rsi_exit':				args.use_rsi_exit,
					'use_mesa_sine_exit':			args.use_mesa_sine_exit,
					'use_trend':				args.use_trend,
					'trend_type':				args.trend_type,
					'trend_period':				args.trend_period,
					'use_combined_exit':			args.use_combined_exit,
					'hold_overnight':			args.hold_overnight,

					'quick_exit':				args.quick_exit,
					'quick_exit_percent':			args.quick_exit_percent,
					'trend_quick_exit':			args.trend_quick_exit,
					'qe_stacked_ma_periods':		args.qe_stacked_ma_periods,
					'qe_stacked_ma_type':			args.qe_stacked_ma_type,

					# Stock shorting options
					'noshort':				args.noshort,
					'shortonly':				args.shortonly,

					# Other stock behavior options
					'blacklist_earnings':			args.blacklist_earnings,
					'check_volume':				args.check_volume,
					'avg_volume':				args.avg_volume,
					'min_volume':				args.min_volume,
					'min_ticker_age':			args.min_ticker_age,
					'min_daily_natr':			args.min_daily_natr,
					'max_daily_natr':			args.max_daily_natr,
					'min_intra_natr':			args.min_intra_natr,
					'max_intra_natr':			args.max_intra_natr,
					'min_price':				args.min_price,
					'max_price':				args.max_price,

					# Indicators
					'primary_stoch_indicator':		args.primary_stoch_indicator,
					'with_stoch_5m':			args.with_stoch_5m,
					'with_stochrsi_5m':			args.with_stochrsi_5m,
					'with_stochmfi':			args.with_stochmfi,
					'with_stochmfi_5m':			args.with_stochmfi_5m,

					'with_stacked_ma':			args.with_stacked_ma,
					'stacked_ma_type':			args.stacked_ma_type,
					'stacked_ma_periods':			args.stacked_ma_periods,
					'with_stacked_ma_secondary':		args.with_stacked_ma_secondary,
					'stacked_ma_type_secondary':		args.stacked_ma_type_secondary,
					'stacked_ma_periods_secondary':		args.stacked_ma_periods_secondary,
					'stacked_ma_type_primary':		args.stacked_ma_type_primary,
					'stacked_ma_periods_primary':		args.stacked_ma_periods_primary,

					'with_momentum':			args.with_momentum,
					'momentum_period':			args.momentum_period,
					'momentum_type':			args.momentum_type,
					'momentum_use_trix':			args.momentum_use_trix,

					'daily_ma_type':			args.daily_ma_type,
					'confirm_daily_ma':			args.confirm_daily_ma,

					'with_mama_fama':			args.with_mama_fama,
					'mama_require_xover':			args.mama_require_xover,
					'with_mesa_sine':			args.with_mesa_sine,
					'mesa_sine_strict':			args.mesa_sine_strict,
					'mesa_sine_period':			args.mesa_sine_period,
					'mesa_sine_type':			args.mesa_sine_type,

					'with_rsi':				args.with_rsi,
					'with_rsi_simple':			args.with_rsi_simple,

					'with_dmi':				args.with_dmi,
					'with_dmi_simple':			args.with_dmi_simple,
					'with_adx':				args.with_adx,

					'with_macd':				args.with_macd,
					'with_macd_simple':			args.with_macd_simple,

					'with_aroonosc':			args.with_aroonosc,
					'with_aroonosc_simple':			args.with_aroonosc_simple,

					'with_mfi':				args.with_mfi,
					'with_mfi_simple':			args.with_mfi_simple,

					'with_vpt':				args.with_vpt,
					'with_vwap':				args.with_vwap,
					'with_chop_index':			args.with_chop_index,
					'with_chop_simple':			args.with_chop_simple,

					'with_supertrend':			args.with_supertrend,
					'supertrend_atr_period':		args.supertrend_atr_period,
					'supertrend_min_natr':			args.supertrend_min_natr,

					'with_bbands_kchannel':			args.with_bbands_kchannel,
					'with_bbands_kchannel_simple':		args.with_bbands_kchannel_simple,
					'bbands_matype':			args.bbands_matype,
					'use_bbands_kchannel_5m':		args.use_bbands_kchannel_5m,
					'bbands_kchan_crossover_only':		args.bbands_kchan_crossover_only,
					'use_bbands_kchannel_xover_exit':	args.use_bbands_kchannel_xover_exit,
					'bbands_kchannel_straddle':		args.bbands_kchannel_straddle,
					'bbands_kchannel_xover_exit_count':	args.bbands_kchannel_xover_exit_count,
					'bbands_kchannel_offset':		args.bbands_kchannel_offset,
					'bbands_kchan_x1_xover':		args.bbands_kchan_x1_xover,
					'bbands_kchan_squeeze_count':		args.bbands_kchan_squeeze_count,
					'bbands_kchan_ma_check':		args.bbands_kchan_ma_check,
					'bbands_kchan_ma_type':			args.bbands_kchan_ma_type,
					'bbands_kchan_ma_ptype':		args.bbands_kchan_ma_ptype,
					'bbands_kchan_ma_period':		args.bbands_kchan_ma_period,
					'max_squeeze_natr':			args.max_squeeze_natr,
					'max_bbands_natr':			args.max_bbands_natr,
					'bbands_roc_threshold':			args.bbands_roc_threshold,
					'bbands_roc_count':			args.bbands_roc_count,
					'bbands_roc_strict':			args.bbands_roc_strict,
					'bbands_period':			args.bbands_period,
					'kchannel_period':			args.kchannel_period,
					'kchannel_atr_period':			args.kchannel_atr_period,
					'kchannel_multiplier':			args.kchannel_multiplier,
					'kchan_matype':				args.kchan_matype,

 					# Indicator parameters and modifiers
					'stochrsi_period':			args.stochrsi_period,
					'stochrsi_5m_period':			args.stochrsi_5m_period,
					'rsi_period':				args.rsi_period,
					'rsi_type':				args.rsi_type,
					'rsi_slow':				args.rsi_slow,
					'rsi_k_period':				args.rsi_k_period,
					'rsi_d_period':				args.rsi_d_period,
					'rsi_low_limit':			args.rsi_low_limit,
					'rsi_high_limit':			args.rsi_high_limit,
					'stochrsi_offset':			args.stochrsi_offset,
					'nocrossover':				args.nocrossover,
					'crossover_only':			args.crossover_only,

					'di_period':				args.di_period,
					'adx_period':				args.adx_period,
					'adx_threshold':			args.adx_threshold,
					'dmi_with_adx':				args.dmi_with_adx,

					'macd_short_period':			args.macd_short_period,
					'macd_long_period':			args.macd_long_period,
					'macd_signal_period':			args.macd_signal_period,
					'macd_offset':				args.macd_offset,

					'aroonosc_period':			args.aroonosc_period,
					'aroonosc_alt_period':			args.aroonosc_alt_period,
					'aroonosc_alt_threshold':		args.aroonosc_alt_threshold,
					'aroonosc_secondary_threshold':		args.aroonosc_secondary_threshold,
					'aroonosc_with_macd_simple':		args.aroonosc_with_macd_simple,
					'aroonosc_with_vpt':			args.aroonosc_with_vpt,

					'stochmfi_period':			args.stochmfi_period,
					'stochmfi_5m_period':			args.stochmfi_5m_period,
					'mfi_period':				args.mfi_period,
					'mfi_high_limit':			args.mfi_high_limit,
					'mfi_low_limit':			args.mfi_low_limit,

					'atr_period':				args.atr_period,
					'daily_atr_period':			args.daily_atr_period,
					'vpt_sma_period':			args.vpt_sma_period,

					'chop_period':				args.chop_period,
					'chop_low_limit':			args.chop_low_limit,
					'chop_high_limit':			args.chop_high_limit,

					'stochrsi_signal_cancel_low_limit':	args.stochrsi_signal_cancel_low_limit,
					'stochrsi_signal_cancel_high_limit':	args.stochrsi_signal_cancel_high_limit,
					'rsi_signal_cancel_low_limit':		args.rsi_signal_cancel_low_limit,
					'rsi_signal_cancel_high_limit':		args.rsi_signal_cancel_high_limit,
					'mfi_signal_cancel_low_limit':		args.mfi_signal_cancel_low_limit,
					'mfi_signal_cancel_high_limit':		args.mfi_signal_cancel_high_limit,

					# Resistance indicators
					'no_use_resistance':			args.no_use_resistance,
					'price_resistance_pct':			args.price_resistance_pct,
					'price_support_pct':			args.price_support_pct,
					'resist_pct_dynamic':			args.resist_pct_dynamic,
					'use_pdc':				args.use_pdc,
					'use_vwap':				args.use_vwap,
					'lod_hod_check':			args.lod_hod_check,
					'use_keylevel':				args.use_keylevel,
					'keylevel_strict':			args.keylevel_strict,
					'keylevel_use_daily':			args.keylevel_use_daily,
					'use_natr_resistance':			args.use_natr_resistance,
					'use_pivot_resistance':			args.use_pivot_resistance,
					'va_check':				args.va_check,

					'experimental':				args.experimental,
					'check_etf_indicators':			args.check_etf_indicators,
					'check_etf_indicators_strict':		args.check_etf_indicators_strict,
					'etf_tickers':				etf_tickers,
					'etf_indicators':			etf_indicators,
					'etf_roc_period':			args.etf_roc_period,
					'etf_roc_type':				args.etf_roc_type,
					'etf_min_rs':				args.etf_min_rs,
					'etf_min_roc':				args.etf_min_roc,
					'etf_min_natr':				args.etf_min_natr,

					'etf_use_emd':				args.etf_use_emd,
					'etf_emd_fraction':			args.etf_emd_fraction,
					'etf_emd_period':			args.etf_emd_period,
					'etf_emd_type':				args.etf_emd_type,

					'with_trin':				args.with_trin,
					'trin_roc_type':			args.trin_roc_type,
					'trin_roc_period':			args.trin_roc_period,
					'trin_ma_type':				args.trin_ma_type,
					'trin_ma_period':			args.trin_ma_period,
					'trin_oversold':			args.trin_oversold,
					'trin_overbought':			args.trin_overbought,

					'with_tick':				args.with_tick,
					'tick_threshold':			args.tick_threshold,
					'tick_ma_type':				args.tick_ma_type,
					'tick_ma_period':			args.tick_ma_period,
					'trin_tick':				trin_tick,

					'with_roc':				args.with_roc,
					'roc_exit':				args.roc_exit,
					'roc_type':				args.roc_type,
					'roc_period':				args.roc_period,
					'roc_ma_type':				args.roc_ma_type,
					'roc_ma_period':			args.roc_ma_period,
					'roc_threshold':			args.roc_threshold,

					'with_sp_monitor':			args.with_sp_monitor,
					'sp_monitor_threshold':			args.sp_monitor_threshold,
					'sp_roc_type':				args.sp_roc_type,
					'sp_roc_period':			args.sp_roc_period,
					'sp_ma_period':				args.sp_ma_period,
					'sp_monitor_stacked_ma_type':		args.sp_monitor_stacked_ma_type,
					'sp_monitor_stacked_ma_periods':	args.sp_monitor_stacked_ma_periods,
					'sp_monitor_use_trix':			args.sp_monitor_use_trix,
					'sp_monitor_trix_ma_type':		args.sp_monitor_trix_ma_type,
					'sp_monitor_trix_ma_period':		args.sp_monitor_trix_ma_period,
					'sp_monitor_strict':			args.sp_monitor_strict,
					'sp_monitor_tickers':			sp_monitor_tickers,
					'sp_monitor':				sp_monitor,

					'with_vix':				args.with_vix,
					'vix_stacked_ma_periods':		args.vix_stacked_ma_periods,
					'vix_stacked_ma_type':			args.vix_stacked_ma_type,
					'vix_use_ha_candles':			args.vix_use_ha_candles,
					'vix':					vix,

					'emd_affinity_long':			args.emd_affinity_long,
					'emd_affinity_short':			args.emd_affinity_short,
					'mesa_emd_fraction':			args.mesa_emd_fraction,
					'mesa_emd_period':			args.mesa_emd_period,
					'mesa_emd_type':			args.mesa_emd_type,
			}

			# Call stochrsi_analyze_new() with test_params{} to run the backtest
			results = tda_gobot_analyze_helper.stochrsi_analyze_new( pricehistory=data, ticker=stock, params=test_params )

		# Check and print the results from stochrsi_analyze_new()
		if ( isinstance(results, bool) and results == False ):
			print('Error: rsi_analyze(' + str(stock) + ') returned false', file=sys.stderr)
			continue
		if ( int(len(results)) == 0 ):
			print('There were no possible trades for requested time period, exiting.')
			continue

		# Print the returned results
		elif ( (algo == 'stochrsi' or algo == 'stochrsi-new') and args.verbose ):
			print()
			print('### Trade Ledger ###')
			print('{0:18} {1:12} {2:12} {3:12} {4:15} {5:12} {6:12} {7:15} {8:20} {9:20} {10:10} {11:10} {12:10}'.format('Buy/Sell Price', 'Num Shares', 'Net Change', 'RSI_K/RSI_D', 'MFI_K/MFI_D', 'NATR', 'Daily_NATR', 'BBands_NATR', 'BBands_Squeeze_NATR', 'RoC', 'RS', 'ADX', 'Time'))

		rating = 0
		success = fail = 0
		net_gain = float(0)
		net_loss = float(0)
		total_return = float(0)
		counter = 0
		while ( counter < len(results) - 1 ):

			price_tx, num_shares, short, rsi_tx, mfi_tx, natr_tx, dnatr_tx, bbands_natr, bbands_squeeze_natr, roc, rs, adx_tx, time_tx = results[counter].split( ',', 13 )
			price_rx, short, rsi_rx, mfi_rx, natr_rx, dnatr_rx, adx_rx, time_rx = results[counter+1].split( ',', 8 )

			vwap_tx = vwap_rx = 0
			stochrsi_tx = stochrsi_rx = 0

			# Returned RSI/MFI format is "prev_rsi/cur_rsi"
			rsi_k_tx,rsi_d_tx = rsi_tx.split( '/', 2 )
			rsi_k_rx,rsi_d_rx = rsi_rx.split( '/', 2 )

			mfi_k_tx,mfi_d_tx = mfi_tx.split( '/', 2 )
			mfi_k_rx,mfi_d_rx = mfi_rx.split( '/', 2 )

			net_change = float(price_rx) - float(price_tx)
			if ( short == str(False) ):
				if ( float(net_change) <= 0 ):
					fail += 1
					net_loss += float(net_change)
				else:
					success += 1
					net_gain += float(net_change)
			else:
				if ( float(net_change) < 0 ):
					success += 1
					net_gain += abs(float(net_change))
				else:
					fail += 1
					net_loss -= float(net_change)

			price_tx = round( float(price_tx), 2 )
			price_rx = round( float(price_rx), 2 )

			net_change = round(net_change, 2)

			#num_shares = int(stock_usd / price_tx)
			num_shares = int(num_shares)

			if ( short == str(False) ):
				total_return += num_shares * net_change

			else:
				if ( net_change <= 0 ):
					total_return += abs(num_shares * net_change)
				else:
					total_return += num_shares * -net_change

			vwap_tx = round( float(vwap_tx), 2 )
			vwap_rx = round( float(vwap_rx), 2 )

			rsi_k_tx = round( float(rsi_k_tx), 1 )
			rsi_d_tx = round( float(rsi_d_tx), 1 )
			rsi_k_rx = round( float(rsi_k_rx), 1 )
			rsi_d_rx = round( float(rsi_d_rx), 1 )

			mfi_k_tx = round( float(mfi_k_tx), 1 )
			mfi_d_tx = round( float(mfi_d_tx), 1 )
			mfi_k_rx = round( float(mfi_k_rx), 1 )
			mfi_d_rx = round( float(mfi_d_rx), 1 )

			stochrsi_tx = round( float(stochrsi_tx), 4 )
			stochrsi_rx = round( float(stochrsi_rx), 4 )

			is_success = False
			if ( short == 'True' ):
				if ( net_change < 0 ):
					is_success = True

				price_tx = str(price_tx) + '*'
				price_rx = str(price_rx) + '*'

			else:
				if ( net_change > 0 ):
					is_success = True

			if ( args.verbose == True ):
				text_color = red
				if ( is_success == True ):
					text_color = green

				rsi_tx = str(rsi_k_tx) + '/' + str(rsi_d_tx)
				rsi_rx = str(rsi_k_rx) + '/' + str(rsi_d_rx)

				mfi_tx = str(mfi_k_tx) + '/' + str(mfi_d_tx)
				mfi_rx = str(mfi_k_rx) + '/' + str(mfi_d_rx)

				print(text_color, end='')
				print('{0:18} {1:12} {2:12} {3:12} {4:15} {5:12} {6:12} {7:15} {8:20} {9:20} {10:10} {11:10} {12:10}'.format(str(price_tx), str(num_shares), '-', str(rsi_tx), str(mfi_tx), str(natr_tx), str(dnatr_tx), str(bbands_natr), str(bbands_squeeze_natr), str(roc), str(rs), str(adx_tx), time_tx), end='')
				print(reset_color, end='')

				print()

				print(text_color, end='')
				print('{0:18} {1:12} {2:12} {3:12} {4:15} {5:12} {6:12} {7:15} {8:20} {9:20} {10:10} {11:10} {12:10}'.format(str(price_rx), '-', str(net_change), str(rsi_rx), str(mfi_rx), '-', '-', '-', '-', '-', '-', str(adx_tx), time_rx), end='')
				print(reset_color, end='')

				print()

			counter += 2


		# Rate the stock
		#   txs/day < 1				 = -1 point	# SAZ - temporarily suspended this one 2021-04-26
		#   avg_gain_per_share < 1		 = -1 points
		#   success_pct < 10% higher than fail % = -2 points
		#   success_pct <= fail_pct		 = -4 points
		#   average_gain <= average_loss	 = -8 points
		#   shortable == False			 = -4 points
		#   marginable == False			 = -2 points
		#   delayed == True			 = -2 points
		#
		# Rating:
		#   0 			 = Very Good
		#   -1			 = Good
		#   <-2 & >-4		 = Poor
		#   <-3			 = Bad
		#   Success % <= Fail %  = FAIL
		#   Avg Gain <= Avg Loss = FAIL
		print()
		print('### Statistics ###')

		txs = int(len(results) / 2) / int(days)					# Average buy or sell triggers per day
		if ( success == 0 ):
			success_pct = 0
		else:
			success_pct = (int(success) / int(len(results) / 2) ) * 100	# % Successful trades using algorithm

		if ( fail == 0 ):
			fail_pct = 0
		else:
			fail_pct = ( int(fail) / int(len(results) / 2) ) * 100		# % Failed trades using algorithm

		average_gain = 0
		average_loss = 0
		if ( success != 0 ):
			average_gain = net_gain / success				# Average improvement in price using algorithm
		if ( fail != 0 ):
			average_loss = net_loss / fail					# Average regression in price using algorithm

		print()

		# Check number of transactions/day
		text_color = green
#		if ( txs < 1 ):
#			rating -= 1
#			text_color = red

		print( 'Average txs/day: ' + text_color + str(round(txs,2)) + reset_color )

		# Compare success/fail percentage
		if ( success_pct <= fail_pct ):
			rating -= 4
			text_color = red
		elif ( success_pct - fail_pct < 10 ):
			rating -= 2
			text_color = red
		else:
			text_color = green

		print( 'Success rate: ' + text_color + str(round(success_pct, 2)) + reset_color )
		print( 'Fail rate: ' + text_color + str(round(fail_pct, 2)) + reset_color )

		# Compare average gain vs average loss
		if ( average_gain <= abs(average_loss) ):
			rating -= 8
			text_color = red
		else:
			text_color = green

		print( 'Average gain: ' + text_color + str(round(average_gain, 2)) + ' / share' + reset_color )
		print( 'Average loss: ' + text_color + str(round(average_loss, 2)) + ' / share' + reset_color )

		# Compare net gain vs net loss
		if ( net_gain <= abs(net_loss) ):
			rating -= 8
			text_color = red
		else:
			text_color = green

		print( 'Net gain: ' + text_color + str(round(net_gain, 2)) + ' / share' + reset_color )
		print( 'Net loss: ' + text_color + str(round(net_loss, 2)) + ' / share' + reset_color )

		# Calculate the average gain per share price
		if ( args.ifile != None ):
			last_price = data['candles'][-1]['close']
		else:
			last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)

		if ( last_price != False ):
			avg_gain_per_share = float(average_gain) / float(last_price) * 100
			if ( avg_gain_per_share < 1 ):
				rating -= 1
				text_color = red
			else:
				text_color = green

			print( 'Average gain per share: ' + text_color + str(round(avg_gain_per_share, 3)) + '%' + reset_color )

		# Total return
		text_color = green
		if ( total_return < 0 ):
			text_color = red

		print( 'Total return: ' + text_color + str(round(total_return, 2)) + reset_color )

		# Shortable / marginable / delayed / etc.
		if ( shortable == False ):
			rating -= 4
		if ( marginable == False ):
			rating -= 2
		if ( delayed == True ):
			rating -= 2

		# Print stock rating (see comments above)
		if ( success_pct <= fail_pct or average_gain <= average_loss ):
			rating = red + 'FAIL' + reset_color
		elif ( rating == 0 ):
			rating = green + 'Very Good' + reset_color
		elif ( rating == -1 ):
			rating = green + 'Good' + reset_color
		elif ( rating <= -4 ):
			rating = red + 'Bad' + reset_color
		elif ( rating <= -2 ):
			rating = red + 'Poor' + reset_color

		print( 'Stock rating: ' + str(rating) )
		print()

exit(0)
