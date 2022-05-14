#!/usr/bin/python3 -u

# Monitor a stock's Stochastic RSI and other indicator values and make entry/exit decisions based off those values.
# Example:
#
# $ tickers='MSFT,AAPL' # put tickers here
#
# $ ./tda-stochrsi-gobot-v2.py --stoploss --stock_usd=5000 --stocks=${tickers} --short --singleday \
#	--decr_threshold=0.4 --incr_threshold=0.5 --max_failed_txs=2 --exit_percent=1 \
#	--algos=stochrsi,mfi,dmi_simple,aroonosc,adx,support_resistance,adx_threshold:6,rsi_low_limit:10 \
#	--algos=stochrsi,mfi,aroonosc,adx,support_resistance,mfi_high_limit:95,mfi_low_limit:5,adx_threshold:20,adx_period:48 \
#	--algos=stochrsi,rsi,mfi,adx,support_resistance,adx_threshold:20,mfi_high_limit:95,mfi_low_limit:5 \
#	--rsi_high_limit=95 --rsi_low_limit=15 \
#	--aroonosc_with_macd_simple --variable_exit --lod_hod_check \
#	--tx_log_dir=TX_LOGS_v2 --weekly_ifile=stock-analyze/weekly-csv/TICKER-weekly-2019-2021.pickle \
#	1> logs/gobot-v2.log 2>&1 &

import os, sys, signal, re, random
import time, datetime, pytz
import argparse
from collections import OrderedDict

import tda_gobot_helper
import tda_algo_helper
import tda_stochrsi_gobot_helper
import av_gobot_helper

# We use robin_stocks for most REST operations
import robin_stocks.tda as tda

# tda-api is used for streaming client
# https://tda-api.readthedocs.io/en/stable/streaming.html
import tda as tda_api
from tda.client import Client
from tda.streaming import StreamClient
import asyncio
import json

# Tulipy is used for producing indicators (i.e. macd and rsi)
import tulipy as ti


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='Stock ticker(s) to watch (comma delimited). Max supported tickers supported by TDA: 300', required=True, type=str)
parser.add_argument("--stock_usd", help='Amount of money (USD) to invest per trade', default=1000, type=float)

parser.add_argument("--account_number", help='Account number to use (default: use .env file)', default=None, type=int)
parser.add_argument("--passcode_prefix", help='Environment variable prefix that contains passcode for the account (default: None)', default=None, type=str)
parser.add_argument("--consumer_key_prefix", help='Environment variable prefix that contains consumer key for the account (default: None)', default=None, type=str)
parser.add_argument("--token_fname", help='Filename containing the account token for robin_stocks module (default: None)', default=None, type=str)
parser.add_argument("--tdaapi_token_fname", help='Filename containing the account token for tda-api module (default: None)', default=None, type=str)

parser.add_argument("--algos", help='Algorithms to use, comma delimited. Supported options: stochrsi, rsi, adx, dmi, macd, aroonosc, vwap, vpt, support_resistance (Example: --algos=stochrsi,adx --algos=stochrsi,macd)', required=True, nargs="*", action='append', type=str)
parser.add_argument("--algo_valid_tickers", help='Tickers to use with a particular algorithm (Example: --algo_valid_tickers=algo_id:MSFT,AAPL). If unset all tickers will be used for all algos. Also requires setting "algo_id:algo_name" with --algos=.', action='append', default=None, type=str)
parser.add_argument("--algo_exclude_tickers", help='Tickers to exclude with a particular algorithm (Example: --algo_exclude_tickers=algo_id:GME,AMC). If unset all tickers will be used for all algos. Also requires setting "algo_id:algo_name" with --algos=.', action='append', default=None, type=str)
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS', default='TX_LOGS', type=str)

parser.add_argument("--multiday", help='Run and monitor stock continuously across multiple days (but will not trade after hours) - see also --hold_overnight', action="store_true")
parser.add_argument("--singleday", help='Allows bot to start (but not trade) before market opens. Bot will revert to non-multiday behavior after the market opens.', action="store_true")
parser.add_argument("--unsafe", help='Allow trading between 9:30-10:15AM where volatility is high', action="store_true")
parser.add_argument("--ph_only", help='Allow trading only between 9:30-10:30AM and 3:00PM-4:00PM when volatility is high', action="store_true")
parser.add_argument("--hold_overnight", help='Hold stocks overnight when --multiday is in use (default: False) - Warning: implies --unsafe', action="store_true")

parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1, type=float)
parser.add_argument("--last_hour_threshold", help='Sell the stock if net gain is above this percentage during the final hour. Assumes --hold_overnight is False.', default=0.2, type=float)

parser.add_argument("--options", help='Purchase CALL/PUT options instead of equities', action="store_true")
parser.add_argument("--options_usd", help='Amount of money (USD) to invest per options trade', default=1000, type=float)
parser.add_argument("--near_expiration", help='Choose an option contract with the earliest expiration date', action="store_true")
parser.add_argument("--otm_level", help='Out-of-the-money strike price to choose (Default: 1)', default=1, type=int)
parser.add_argument("--start_day_offset", help='Use start_day_offset to push start day of option search +N days out (Default: 0)', default=0, type=int)
parser.add_argument("--options_incr_threshold", help='Reset base_price if stock increases by this percent', default=2, type=float)
parser.add_argument("--options_decr_threshold", help='Max allowed drop percentage of the stock price', default=5, type=float)
parser.add_argument("--options_exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)

parser.add_argument("--num_purchases", help='Number of purchases allowed per day', default=10, type=int)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("--max_failed_txs", help='Maximum number of failed transactions allowed for a given stock before stock is blacklisted', default=2, type=int)
parser.add_argument("--max_failed_usd", help='Maximum allowed USD for a failed transaction before the stock is blacklisted', default=99999, type=float)
parser.add_argument("--exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)
parser.add_argument("--variable_exit", help='Adjust incr_threshold, decr_threshold and exit_percent based on the price action of the stock over the previous hour',  action="store_true")

parser.add_argument("--quick_exit", help='Exit immediately if an exit_percent strategy was set, do not wait for the next candle', action="store_true")
parser.add_argument("--quick_exit_percent", help='Exit immediately if --quick_exit and this profit target is achieved', default=None, type=float)
parser.add_argument("--trend_quick_exit", help='Enable quick exit when entering counter-trend moves', action="store_true")
parser.add_argument("--qe_stacked_ma_periods", help='Moving average periods to use with --trend_quick_exit (Default: )', default='34,55,89', type=str)
parser.add_argument("--qe_stacked_ma_type", help='Moving average type to use when calculating trend_quick_exit stacked_ma (Default: vidya)', default='vidya', type=str)
parser.add_argument("--scalp_mode", help='Enable scalp mode', action="store_true")
parser.add_argument("--scalp_mode_pct", help='Required percent increase in value before exiting trade', default=2, type=float)

parser.add_argument("--use_ha_exit", help='Use Heikin Ashi candles with exit_percent-based exit strategy', action="store_true")
parser.add_argument("--use_ha_candles", help='Use Heikin Ashi candles with stacked MA indicators', action="store_true")
parser.add_argument("--use_trend_exit", help='Use ttm_trend algorithm with exit_percent-based exit strategy', action="store_true")
parser.add_argument("--use_trend", help='Use ttm_trend algorithm with stacked MA indicators', action="store_true")
parser.add_argument("--trend_type", help='Candle type to use with ttm_trend algorithm (Default: hl2)', default='hl2', type=str)
parser.add_argument("--trend_period", help='Period to use with ttm_trend algorithm (Default: 5)', default=5, type=int)
parser.add_argument("--use_combined_exit", help='Use both the ttm_trend algorithm and Heikin Ashi candles with exit_percent-based exit strategy', action="store_true")

parser.add_argument("--rsi_high_limit", help='RSI high limit', default=80, type=int)
parser.add_argument("--rsi_low_limit", help='RSI low limit', default=20, type=int)
parser.add_argument("--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("--rsi_period_5m", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("--stochrsi_period", help='RSI period to use for stochastic RSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("--stochrsi_5m_period", help='RSI period to use for stochastic RSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("--rsi_k_period", help='k period to use in StochRSI algorithm', default=128, type=int)
parser.add_argument("--rsi_k_5m_period", help='k period to use in StochRSI algorithm', default=128, type=int)
parser.add_argument("--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='hlc3', type=str)
parser.add_argument("--stochrsi_offset", help='Offset between K and D to determine strength of trend', default=8, type=int)

parser.add_argument("--stacked_ma_type", help='Moving average type to use (Default: kama)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods", help='List of MA periods to use, comma-delimited (Default: 8,13,21)', default='8,13,21', type=str)
parser.add_argument("--stacked_ma_type_primary", help='Moving average type to use when stacked_ma is used as primary indicator (Default: kama)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods_primary", help='List of MA periods to use when stacked_ma is used as primary indicator, comma-delimited (Default: 8,13,21)', default='8,13,21', type=str)
parser.add_argument("--stacked_ma_secondary", help='Use stacked MA as a secondary indicator for trade entries (Default: False)', action="store_true")
parser.add_argument("--stacked_ma_type_secondary", help='Moving average type to use (Default: kama)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods_secondary", help='List of MA periods to use, comma-delimited (Default: 8,13,21)', default='8,13,21', type=str)

parser.add_argument("--mesa_sine_strict", help='Use strict version of the MESA Sine Wave indicator (Default: False)', action="store_true")
parser.add_argument("--mesa_sine_period", help='Lookback period to use with MESA Sine Wave (Default: 25)', default=25, type=int)
parser.add_argument("--mesa_sine_type", help='Input type to use with MESA Sine Wave (Default: hl2)', default='hl2', type=str)

parser.add_argument("--mfi_high_limit", help='MFI high limit', default=80, type=int)
parser.add_argument("--mfi_low_limit", help='MFI low limit', default=20, type=int)
parser.add_argument("--mfi_period", help='Money Flow Index (MFI) period', default=14, type=int)
parser.add_argument("--mfi_5m_period", help='Money Flow Index (MFI) period', default=14, type=int)
parser.add_argument("--stochmfi_period", help='Money Flow Index (MFI) period for stochastic MFI calculation', default=14, type=int)
parser.add_argument("--stochmfi_5m_period", help='Money Flow Index (MFI) period for stochastic MFI calculation', default=14, type=int)
parser.add_argument("--mfi_k_period", help='k period to use in StochMFI algorithm', default=128, type=int)
parser.add_argument("--mfi_k_5m_period", help='k period to use in StochMFI algorithm', default=128, type=int)
parser.add_argument("--mfi_d_period", help='D period to use in StochMFI algorithm', default=3, type=int)
parser.add_argument("--mfi_slow", help='Slowing period to use in StochMFI algorithm', default=3, type=int)
parser.add_argument("--stochmfi_offset", help='Offset between K and D to determine strength of trend', default=3, type=int)

parser.add_argument("--vpt_sma_period", help='SMA period for VPT signal line', default=72, type=int)
parser.add_argument("--adx_period", help='ADX period', default=92, type=int)
parser.add_argument("--di_period", help='Plus/Minus DI period', default=48, type=int)
parser.add_argument("--aroonosc_period", help='Aroon Oscillator period', default=24, type=int)
parser.add_argument("--aroonosc_alt_period", help='Alternate Aroon Oscillator period for higher volatility stocks', default=60, type=int)
parser.add_argument("--aroonosc_alt_threshold", help='Threshold for enabling the alternate Aroon Oscillator period for higher volatility stocks', default=0.24, type=float)
parser.add_argument("--atr_period", help='Average True Range period', default=14, type=int)
parser.add_argument("--daily_atr_period", help='Daily (Normalized) Average True Range period', default=3, type=int)
parser.add_argument("--aroonosc_with_macd_simple", help='When using Aroon Oscillator, use macd_simple as tertiary indicator if AroonOsc is less than +/- 72 (Default: False)', action="store_true")
parser.add_argument("--aroonosc_secondary_threshold", help='AroonOsc threshold for when to enable macd_simple when --aroonosc_with_macd_simple is enabled (Default: 72)', default=72, type=float)
parser.add_argument("--adx_threshold", help='ADX threshold for when to trigger the ADX signal (Default: 25)', default=25, type=float)
parser.add_argument("--chop_period", help='Choppiness Index period', default=14, type=int)
parser.add_argument("--chop_low_limit", help='Choppiness Index low limit', default=38.2, type=float)
parser.add_argument("--chop_high_limit", help='Choppiness Index high limit', default=61.8, type=float)
parser.add_argument("--macd_short_period", help='MACD short (fast) period', default=48, type=int)
parser.add_argument("--macd_long_period", help='MACD long (slow) period', default=104, type=int)
parser.add_argument("--macd_signal_period", help='MACD signal (length) period', default=36, type=int)
parser.add_argument("--macd_offset", help='MACD offset for signal lines', default=0.006, type=float)
parser.add_argument("--supertrend_atr_period", help='ATR period to use for the supertrend indicator (Default: 70)', default=70, type=int)
parser.add_argument("--supertrend_min_natr", help='Minimum daily NATR a stock must have to enable supertrend indicator (Default: 2)', default=2, type=float)

parser.add_argument("--bbands_kchannel_offset", help='Percentage offset between the Bollinger bands and Keltner channel indicators to trigger an initial trade entry (Default: 0.15)', default=0.15, type=float)
parser.add_argument("--bbands_kchan_squeeze_count", help='Number of squeeze periods needed before triggering bbands_kchannel signal (Default: 4)', default=4, type=int)
parser.add_argument("--bbands_kchan_ma_check", help='Check price action in relation to a moving average during a squeeze to ensure price stays above or below a moving average (Default: False)', action="store_true")
parser.add_argument("--bbands_kchan_ma_type", help='Moving average type to use with bbands_kchan_ma_check (Default: ema)', default='ema', type=str)
parser.add_argument("--bbands_kchan_ma_ptype", help='Candle type to use when calculating moving average for use with bbands_kchan_ma_check (Default: close)', default='close', type=str)
parser.add_argument("--bbands_kchan_ma_period", help='Period to use when calculating moving average for use with bbands_kchan_ma_check (Default: 21)', default=21, type=int)
parser.add_argument("--max_squeeze_natr", help='Maximum NATR allowed during consolidation (squeeze) phase (Default: None)', default=None, type=float)
parser.add_argument("--bbands_roc_threshold", help='BBands rate of change threshold to trigger bbands signal (Default: 90)', default=90, type=float)
parser.add_argument("--bbands_roc_count", help='Number of times the BBands rate of change threshold must be met to trigger bbands signal (Default: 2)', default=2, type=int)
parser.add_argument("--bbands_roc_strict", help='Require a change in Bollinger Bands rate-of-change equivalent to --bbands_roc_count (Default: False) to signal',  action="store_true")
parser.add_argument("--use_bbands_kchannel_5m", help='Use 5-minute candles to calculate the Bollinger bands and Keltner channel indicators (Default: False)', action="store_true")
parser.add_argument("--use_bbands_kchannel_xover_exit", help='Use price action after a Bollinger bands and Keltner channel crossover to assist with stock exit (Default: False)', action="store_true")
parser.add_argument("--bbands_kchannel_xover_exit_count", help='Number of periods to wait after a crossover to trigger --use_bbands_kchannel_xover_exit (Default: 10)', default=10, type=int)
parser.add_argument("--bbands_period", help='Period to use when calculating the Bollinger Bands (Default: 20)', default=20, type=int)
parser.add_argument("--bbands_matype", help='Moving average type to use with Bollinger Bands calculation (Default: 0)', default=0, type=int)
parser.add_argument("--kchannel_period", help='Period to use when calculating the Keltner channels (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_atr_period", help='Period to use when calculating the ATR for use with the Keltner channels (Default: 20)', default=20, type=int)
parser.add_argument("--kchan_matype", help='MA type to use when calculating the Keltner Channel (Default: ema)', default='ema', type=str)

parser.add_argument("--check_etf_indicators", help='Tailor the stochastic indicator high/low levels based on the 5-minute SMA/EMA behavior of key ETFs (i.e. SPY, QQQ, DIA)', action="store_true")
parser.add_argument("--check_etf_indicators_strict", help='Do not allow trade unless the 5-minute SMA/EMA behavior of key ETFs (i.e. SPY, QQQ, DIA) agree with direction', action="store_true")
parser.add_argument("--etf_tickers", help='List of tickers to use with --check_etf_indicators (Default: SPY)', default='SPY', type=str)
parser.add_argument("--etf_tickers_allowtrade", help='Normally ETF tickers are not tradeable. List any ETF tickers that you want to allow the gobot to trade (comma-delimited)', default=None, type=str)
parser.add_argument("--etf_roc_period", help='Rate of change lookback period (Default: 50)', default=50, type=int)
parser.add_argument("--etf_min_rs", help='Minimum relative strength between equity and ETF to allow trade (Default: None)', default=None, type=float)
parser.add_argument("--etf_min_natr", help='Minimum intraday NATR of ETF to allow trade (Default: None)', default=None, type=float)

parser.add_argument("--trin_roc_type", help='Rate of change candles type to use with $TRIN algorithm (Default: hlc3)', default='hlc3', type=str)
parser.add_argument("--trin_roc_period", help='Period to use with ROC algorithm (Default: 1)', default=1, type=int)
parser.add_argument("--trin_ma_type", help='MA type to use with $TRIN algorithm (Default: ema)', default='ema', type=str)
parser.add_argument("--trin_ma_period", help='Period to use with ROC algorithm (Default: 5)', default=5, type=int)
parser.add_argument("--trin_oversold", help='Oversold threshold for $TRIN algorithm (Default: 3)', default=3, type=float)
parser.add_argument("--trin_overbought", help='Overbought threshold for $TRIN algorithm (Default: -1)', default=-1, type=float)

parser.add_argument("--tick_threshold", help='+/- threshold level before triggering a signal (Default: 50)', default=50, type=int)
parser.add_argument("--tick_ma_type", help='MA type to use with $TICK algorithm (Default: ema)', default='ema', type=str)
parser.add_argument("--tick_ma_period", help='Period to use with ROC algorithm (Default: 5)', default=5, type=int)

parser.add_argument("--roc_type", help='Rate of change candles type to use (Default: hlc3)', default='hlc3', type=str)
parser.add_argument("--roc_exit", help='Use Rate-of-Change (ROC) indicator to signal an exit', action="store_true")
parser.add_argument("--roc_period", help='Period to use with ROC algorithm (Default: 14)', default=14, type=int)
parser.add_argument("--roc_ma_type", help='MA period to use with ROC algorithm (Default: wma)', default='wma', type=str)
parser.add_argument("--roc_ma_period", help='MA period to use with ROC algorithm (Default: 5)', default=5, type=int)
parser.add_argument("--roc_threshold", help='Threshold to cancel the ROC algorithm (Default: 0.15)', default=0.15, type=float)

parser.add_argument("--sp_monitor_tickers", help='List of tickers and their weighting (in %) to use with --with_sp_monitor, comma-delimited (Example: MSFT:1.2,AAPL:1.0,...', default=None, type=str)
parser.add_argument("--sp_monitor_threshold", help='+/- threshold before triggering final signal (Default: 2)', default=2, type=float)
parser.add_argument("--sp_roc_type", help='Rate of change candles type to use with sp_monitor (Default: hlc3)', default='hlc3', type=str)
parser.add_argument("--sp_roc_period", help='Period to use with ROC algorithm for sp_monitor (Default: 1)', default=1, type=int)
parser.add_argument("--sp_ma_period", help='Moving average period to use with the RoC values for sp_monitor (Default: 5)', default=5, type=int)
parser.add_argument("--sp_monitor_stacked_ma_type", help='Moving average type to use with sp_monitor stacked_ma (Default: vidya)', default='vidya', type=str)
parser.add_argument("--sp_monitor_stacked_ma_periods", help='Moving average periods to use with sp_monitor stacked_ma (Default: 8,13,21)', default='8,13,21', type=str)
parser.add_argument("--sp_monitor_use_trix", help='Use TRIX algorithm instead of stacked_ma to help gauge strength/direction of sp_monitor', action="store_true")
parser.add_argument("--sp_monitor_trix_ma_type", help='Moving average type to use with sp_monitor TRIX (Default: ema)', default='ema', type=str)
parser.add_argument("--sp_monitor_trix_ma_period", help='Moving average period to use with sp_monitor TRIX (Default: 8)', default=8, type=int)
parser.add_argument("--sp_monitor_strict", help='Enable some stricter checks when entering trades', action="store_true")

parser.add_argument("--time_sales_algo", help='Enable monitors for time and sales algo behavior', action="store_true")
parser.add_argument("--time_sales_use_keylevel", help='Add key levels at major absorption areas when using --time_sales_algo', action="store_true")
parser.add_argument("--time_sales_size_threshold", help='Trade size threshold for use with time and sales monitor', default=3000, type=int)
parser.add_argument("--time_sales_kl_size_threshold", help='Trade size threshold for use with time and sales monitor', default=6000, type=int)

parser.add_argument("--daily_ifile", help='Use pickle file for daily pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--weekly_ifile", help='Use pickle file for weekly pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--no_use_resistance", help='Do no use the high/low resistance to avoid possibly bad trades (default=False)', action="store_true")
parser.add_argument("--use_vwap", help='Use vwap resistance checks to enter trades (Default: True if --no_use_resistance=False)', action="store_true")
parser.add_argument("--use_pdc", help='Use previous day close resistance level checks to enter trades (Default: True if --no_use_resistance=False)', action="store_true")
parser.add_argument("--use_keylevel", help='Use keylevel resistance to avoid possibly bad trades (default=False, True if --no_use_resistance is False)', action="store_true")
parser.add_argument("--keylevel_use_daily", help='Use daily candles as well as weeklies to determine key levels (Default: False)', action="store_true")
parser.add_argument("--keylevel_strict", help='Use strict key level checks to enter trades (Default: False)', action="store_true")
parser.add_argument("--va_check", help='Use the previous day Value Area High (VAH) Value Area Low (VAL) as resistance', action="store_true")
parser.add_argument("--lod_hod_check", help='Enable low of the day (LOD) / high of the day (HOD) resistance checks', action="store_true")
parser.add_argument("--use_natr_resistance", help='Enable daily NATR level resistance checks', action="store_true")
parser.add_argument("--price_resistance_pct", help='Percentage threshold from resistance or keylevel to trigger signal (Default: 1)', default=1, type=float)
parser.add_argument("--price_support_pct", help='Percentage threshold from resistance or keylevel to trigger signal (Default: 1)', default=1, type=float)
parser.add_argument("--resist_pct_dynamic", help='Calculate price_resistance_pct/price_support_pct dynamically', action="store_true")

parser.add_argument("--min_intra_natr", help='Minimum intraday NATR value to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--max_intra_natr", help='Maximum intraday NATR value to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--min_daily_natr", help='Do not process tickers with less than this daily NATR value (Default: None)', default=None, type=float)
parser.add_argument("--max_daily_natr", help='Do not process tickers with more than this daily NATR value (Default: None)', default=None, type=float)

parser.add_argument("--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("--shortonly", help='Only short sell the stock', action="store_true")
parser.add_argument("--short_check_ma", help='Allow short selling of the stock when it is bearish (SMA200 < SMA50)', action="store_true")

parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
args = parser.parse_args()

## FOR TESTING
args.debug = True
## FOR TESTING

# Set timezone
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone
tda_stochrsi_gobot_helper.mytimezone = mytimezone

# --hold_overnight implies --multiday
# --hold_overnight implies --unsafe (safe_open=False)
if ( args.hold_overnight == True ):
	args.multiday = True
	args.unsafe = True

# Early exit criteria goes here
# Safe open - ensure that we don't trade until after 10:15AM Eastern
safe_open = not args.unsafe
if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False and args.multiday == False and args.singleday == False ):
	print('Market is closed and --multiday or --singleday was not set, exiting.')
	sys.exit(0)
if ( args.singleday == True and tda_gobot_helper.ismarketopen_US(check_day_only=True) == False ):
	print('Market is closed today (' + str(datetime.datetime.now(mytimezone).strftime('%Y-%m-%d')) + '), exiting.')
	sys.exit(0)

# Initialize and log into TD Ameritrade
#  - Account number is presumed kept in local .env file unless specified
#     on the command-line.
#  - Consumer key and passcode are presumed kept in a local .env file
#  - Cert and refresh certficate are kept in ~/.tokens/
#
# For historic reasons we use both robin_stocks and tda-api modules. Robin_stocks
#  is used for the HTTP endpoint APIs, and tda-api module for the websocket
#  streaming API. Both require the certs in .tokens/*.pickle, but the formatting is
#  different (robin_stocks uses basic var=value whereas tda-api uses a dict). Use
#  --token_fname for robin_stocks token filename, and --tdaapi_token_fname for
#  the tda-api token file.
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file', file=sys.stderr)
	sys.exit(1)

try:
	# Account Number
	if ( args.account_number != None ):
		tda_account_number = args.account_number
	else:
		tda_account_number = int( os.environ["tda_account_number"] )

	# Passcode
	passcode_prefix = 'tda_encryption_passcode'
	if ( args.passcode_prefix != None ):
		passcode_prefix = str(args.passcode_prefix) + '_tda_encryption_passcode'

	passcode = os.environ[passcode_prefix]

	# Token filename
	token_fname = args.token_fname

	# Consumer key
	consumer_key_prefix = 'tda_consumer_key'
	if ( args.consumer_key_prefix != None ):
		consumer_key_prefix = str(args.consumer_key_prefix) + '_tda_consumer_key'
	tda_api_key = os.environ[consumer_key_prefix]

	# TDA token (.pickle) file
	tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'
	if ( args.tdaapi_token_fname != None ):
		tda_pickle = os.environ['HOME'] + '/.tokens/' + str(args.tdaapi_token_fname)

except Exception as e:
	print('Error parsing account credentials: ' + str(e) + ', exiting')
	sys.exit(1)

tda_gobot_helper.tda				= tda
tda_stochrsi_gobot_helper.tda			= tda

tda_gobot_helper.tda_account_number		= tda_account_number
tda_stochrsi_gobot_helper.tda_account_number	= tda_account_number

tda_gobot_helper.passcode			= passcode
tda_stochrsi_gobot_helper.passcode		= passcode

tda_gobot_helper.token_fname			= token_fname
tda_stochrsi_gobot_helper.token_fname		= token_fname

if ( tda_gobot_helper.tdalogin(passcode, token_fname) != True ):
	print('Error: Login failure', file=sys.stderr)
	sys.exit(1)

# Initialize algos[]
#
# args.algos = [[indicator1,indicator2,...], [...]]
#
# algos = [ {'stochrsi':		False,
#	   'rsi':			False,
#	   'mfi':			False,
#	   'adx':			False,
#	   'dmi':			False,
#	   'dmi_simple':		False,
#	   'macd':			False,
#	   'macd_simple':		False,
#	   'aroonosc':			False,
#	   'chop_index':		False,
#	   'chop_simple':		False,
#	   'supertrend':		False,
#	   'vwap':			False,
#	   'vpt':			False,
#	   'support_resistance':	False
#	}, {...} ]
print('Initializing algorithms... ')
algos = []
algo_ids = []
for algo in args.algos:
	print(algo)
	algo = ','.join(algo)

	algo_id = None
	if ( re.match('algo_id:', algo) == None ):
		# Generate a random unique algo_id if needed
		while True:
			algo_id = random.randint(1000, 9999)
			if 'algo_'+str(algo_id) in algo_ids:
				continue
			else:
				algo_ids.append('algo_' + str(algo_id))
				break

	# Indicators
	primary_stochrsi = primary_stochmfi = primary_stacked_ma = primary_mama_fama = primary_mesa_sine = primary_trin = primary_sp_monitor = False
	stacked_ma = stacked_ma_secondary = mama_fama = stochrsi_5m = stochmfi = stochmfi_5m = False
	rsi = mfi = adx = dmi = dmi_simple = macd = macd_simple = aroonosc = False
	chop_index = chop_simple = supertrend = bbands_kchannel = False
	vwap = vpt = support_resistance = False
	trin = tick = roc = sp_monitor = False

	# Per-algo entry limit
	stock_usd			= args.stock_usd
	options				= args.options
	options_usd			= args.options_usd
	near_expiration			= args.near_expiration
	otm_level			= args.otm_level
	start_day_offset		= args.start_day_offset
	ph_only				= args.ph_only
	safe_open			= not args.unsafe

	quick_exit			= args.quick_exit
	quick_exit_percent		= args.quick_exit_percent
	trend_quick_exit		= args.trend_quick_exit
	qe_stacked_ma_periods		= args.qe_stacked_ma_periods
	qe_stacked_ma_type		= args.qe_stacked_ma_type
	scalp_mode			= args.scalp_mode
	scalp_mode_pct			= args.scalp_mode_pct

	# Indicator modifiers
	rsi_high_limit			= args.rsi_high_limit
	rsi_low_limit			= args.rsi_low_limit

	rsi_period			= args.rsi_period
	stochrsi_period			= args.stochrsi_period
	stochrsi_5m_period		= args.stochrsi_5m_period
	rsi_k_period			= args.rsi_k_period
	rsi_k_5m_period			= args.rsi_k_5m_period
	rsi_d_period			= args.rsi_d_period
	rsi_slow			= args.rsi_slow
	stochrsi_offset			= args.stochrsi_offset
	stochrsi_5m_offset		= stochrsi_offset

	# Stacked MA
	stacked_ma_type_primary		= args.stacked_ma_type_primary
	stacked_ma_periods_primary	= args.stacked_ma_periods_primary
	stacked_ma_type			= args.stacked_ma_type
	stacked_ma_periods		= args.stacked_ma_periods
	stacked_ma_type_secondary	= args.stacked_ma_type_secondary
	stacked_ma_periods_secondary	= args.stacked_ma_periods_secondary

	mesa_sine_strict		= args.mesa_sine_strict
	mesa_sine_period		= args.mesa_sine_period
	mesa_sine_type			= args.mesa_sine_type

	# Heikin Ashi and TTM_Trend
	use_ha_exit			= args.use_ha_exit
	use_ha_candles			= args.use_ha_candles
	use_trend_exit			= args.use_trend_exit
	use_trend			= args.use_trend
	trend_period			= args.trend_period
	trend_type			= args.trend_type
	use_combined_exit		= args.use_combined_exit

	# Bollinger Bands and Keltner Channel
	bbands_kchannel_offset		= args.bbands_kchannel_offset
	bbands_kchan_squeeze_count	= args.bbands_kchan_squeeze_count
	bbands_kchan_ma_check		= args.bbands_kchan_ma_check
	bbands_kchan_ma_type		= args.bbands_kchan_ma_type
	bbands_kchan_ma_ptype		= args.bbands_kchan_ma_ptype
	bbands_kchan_ma_period		= args.bbands_kchan_ma_period
	max_squeeze_natr		= args.max_squeeze_natr
	bbands_roc_threshold		= args.bbands_roc_threshold
	bbands_roc_count		= args.bbands_roc_count
	bbands_roc_strict		= args.bbands_roc_strict
	use_bbands_kchannel_5m		= args.use_bbands_kchannel_5m
	use_bbands_kchannel_xover_exit	= args.use_bbands_kchannel_xover_exit
	bbands_kchannel_xover_exit_count= args.bbands_kchannel_xover_exit_count
	bbands_period			= args.bbands_period
	bbands_matype			= args.bbands_matype
	kchannel_period			= args.kchannel_period
	kchannel_atr_period		= args.kchannel_atr_period
	kchan_matype			= args.kchan_matype

	check_etf_indicators		= args.check_etf_indicators
	check_etf_indicators_strict	= args.check_etf_indicators_strict
	etf_tickers			= args.etf_tickers
	etf_roc_period			= args.etf_roc_period
	etf_min_rs			= args.etf_min_rs
	etf_min_natr			= args.etf_min_natr

	trin_roc_type			= args.trin_roc_type
	trin_roc_period			= args.trin_roc_period
	trin_ma_type			= args.trin_ma_type
	trin_ma_period			= args.trin_ma_period
	trin_oversold			= args.trin_oversold
	trin_overbought			= args.trin_overbought

	tick_threshold			= args.tick_threshold
	tick_ma_type			= args.tick_ma_type
	tick_ma_period			= args.tick_ma_period

	roc_type			= args.roc_type
	roc_exit			= args.roc_exit
	roc_period			= args.roc_period
	roc_ma_type			= args.roc_ma_type
	roc_ma_period			= args.roc_ma_period
	roc_threshold			= args.roc_threshold

	sp_monitor_tickers		= args.sp_monitor_tickers
	sp_monitor_threshold		= args.sp_monitor_threshold
	sp_roc_type			= args.sp_roc_type
	sp_roc_period			= args.sp_roc_period
	sp_ma_period			= args.sp_ma_period
	sp_monitor_stacked_ma_type	= args.sp_monitor_stacked_ma_type
	sp_monitor_stacked_ma_periods	= args.sp_monitor_stacked_ma_periods
	sp_monitor_use_trix		= args.sp_monitor_use_trix
	sp_monitor_trix_ma_type		= args.sp_monitor_trix_ma_type
	sp_monitor_trix_ma_period	= args.sp_monitor_trix_ma_period
	sp_monitor_strict		= args.sp_monitor_strict

	time_sales_algo			= args.time_sales_algo
	time_sales_use_keylevel		= args.time_sales_use_keylevel
	time_sales_size_threshold	= args.time_sales_size_threshold
	time_sales_kl_size_threshold	= args.time_sales_kl_size_threshold

	# MFI
	mfi_high_limit			= args.mfi_high_limit
	mfi_low_limit			= args.mfi_low_limit

	mfi_period			= args.mfi_period
	stochmfi_period			= args.stochmfi_period
	stochmfi_5m_period		= args.stochmfi_5m_period
	mfi_k_period			= args.mfi_k_period
	mfi_k_5m_period			= args.mfi_k_5m_period
	mfi_d_period			= args.mfi_d_period
	mfi_slow			= args.mfi_slow
	stochmfi_offset			= args.stochmfi_offset
	stochmfi_5m_offset		= stochmfi_offset

	# Additional Indicators
	adx_threshold			= args.adx_threshold
	adx_period			= args.adx_period

	macd_long_period		= args.macd_long_period
	macd_short_period		= args.macd_short_period
	macd_signal_period		= args.macd_signal_period
	macd_offset			= args.macd_offset

	aroonosc_period			= args.aroonosc_period
	di_period			= args.di_period

	atr_period			= args.atr_period
	vpt_sma_period			= args.vpt_sma_period

	chop_period			= args.chop_period
	chop_low_limit			= args.chop_low_limit
	chop_high_limit			= args.chop_high_limit

	supertrend_atr_period		= args.supertrend_atr_period
	supertrend_min_natr		= args.supertrend_min_natr

	use_keylevel			= args.use_keylevel
	use_vwap			= args.use_vwap
	use_pdc				= args.use_pdc
	lod_hod_check			= args.lod_hod_check
	use_natr_resistance		= args.use_natr_resistance
	va_check			= args.va_check
	keylevel_use_daily		= args.keylevel_use_daily
	keylevel_strict			= args.keylevel_strict
	price_resistance_pct		= args.price_resistance_pct
	price_support_pct		= args.price_support_pct
	resist_pct_dynamic		= args.resist_pct_dynamic

	min_intra_natr			= args.min_intra_natr
	max_intra_natr			= args.max_intra_natr
	min_daily_natr			= args.min_daily_natr
	max_daily_natr			= args.max_daily_natr

	for a in algo.split(','):
		a = re.sub( '[\s\t]*', '', a )

		# Algo_ID
		if ( re.match('algo_id:', a) != None ): algo_id = a.split(':')[1]

		# Algorithms
		if ( a == 'primary_stochrsi' ):		primary_stochrsi	= True
		if ( a == 'primary_stochmfi' ):		primary_stochmfi	= True
		if ( a == 'primary_stacked_ma' ):	primary_stacked_ma	= True
		if ( a == 'primary_mama_fama' ):	primary_mama_fama	= True
		if ( a == 'primary_mesa_sine' ):	primary_mesa_sine	= True
		if ( a == 'primary_trin' ):		primary_trin		= True
		if ( a == 'primary_sp_monitor' ):	primary_sp_monitor	= True
		if ( a == 'trin'):			trin			= True
		if ( a == 'tick'):			tick			= True
		if ( a == 'roc'):			roc			= True
		if ( a == 'sp_monitor'):		sp_monitor		= True
		if ( a == 'stacked_ma' ):		stacked_ma		= True
		if ( a == 'stacked_ma_secondary' ):	stacked_ma_secondary	= True
		if ( a == 'mama_fama' ):		mama_fama		= True
		if ( a == 'stochrsi_5m' ):		stochrsi_5m		= True
		if ( a == 'stochmfi' ):			stochmfi		= True
		if ( a == 'stochmfi_5m' ):		stochmfi_5m		= True
		if ( a == 'rsi' ):			rsi			= True
		if ( a == 'mfi' ):			mfi			= True
		if ( a == 'adx' ):			adx			= True
		if ( a == 'dmi' ):			dmi			= True
		if ( a == 'dmi_simple' ):		dmi_simple		= True
		if ( a == 'macd' ):			macd			= True
		if ( a == 'macd_simple' ):		macd_simple		= True
		if ( a == 'aroonosc' ):			aroonosc		= True
		if ( a == 'chop_index' ):		chop_index		= True
		if ( a == 'chop_simple' ):		chop_simple		= True
		if ( a == 'supertrend' ):		supertrend		= True
		if ( a == 'bbands_kchannel' ):		bbands_kchannel		= True
		if ( a == 'vwap' ):			vwap			= True
		if ( a == 'vpt' ):			vpt			= True

		# Support / Resistance
		if ( a == 'support_resistance' ):	support_resistance	= True
		if ( a == 'use_keylevel' ):		use_keylevel		= True
		if ( a == 'use_vwap' ):			use_vwap		= True
		if ( a == 'use_pdc' ):			use_pdc			= True
		if ( a == 'use_natr_resistance' ):	use_natr_resistance	= True
		if ( a == 'va_check' ):			va_check		= True
		if ( a == 'lod_hod_check' ):		lod_hod_check		= True

		# Entry limit
		if ( re.match('stock_usd:', a)				!= None ):	stock_usd			= float( a.split(':')[1] )
		if ( re.match('ph_only', a)				!= None ):	ph_only				= True
		if ( re.match('safe_open', a)				!= None ):	safe_open			= True
		if ( re.match('unsafe', a)				!= None ):	safe_open			= False

		if ( re.match('quick_exit', a)				!= None ):	quick_exit			= True
		if ( re.match('quick_exit_percent:', a)			!= None ):	quick_exit_percent		= float( a.split(':')[1] )
		if ( re.match('trend_quick_exit', a)			!= None ):	trend_quick_exit		= True
		if ( re.match('qe_stacked_ma_periods:', a)		!= None ):	qe_stacked_ma_periods		= str( a.split(':')[1] )
		if ( re.match('qe_stacked_ma_type:', a)			!= None ):	qe_stacked_ma_type		= str( a.split(':')[1] )
		if ( re.match('scalp_mode', a)				!= None ):	scalp_mode			= True
		if ( re.match('scalp_mode_pct:', a)			!= None ):	scalp_mode_pct			= float( a.split(':')[1] )

		# Options
		if ( re.match('options', a)				!= None ):	options				= True
		if ( re.match('options_usd:', a)			!= None ):	options_usd			= float( a.split(':')[1] )
		if ( re.match('near_expiration', a)			!= None ):	near_expiration			= True
		if ( re.match('otm_level:', a)				!= None ):	otm_level			= int( a.split(':')[1] )
		if ( re.match('start_day_offset:', a)			!= None ):	start_day_offset		= int( a.split(':')[1] )

		# Modifiers
		if ( re.match('rsi_high_limit:', a)			!= None ):	rsi_high_limit			= float( a.split(':')[1] )
		if ( re.match('rsi_low_limit:', a)			!= None ):	rsi_low_limit			= float( a.split(':')[1] )

		if ( re.match('rsi_period:', a)				!= None ):	rsi_period			= int( a.split(':')[1] )
		if ( re.match('stochrsi_period:', a)			!= None ):	stochrsi_period			= int( a.split(':')[1] )
		if ( re.match('stochrsi_period_5m:', a)			!= None ):	stochrsi_period_5m		= int( a.split(':')[1] )
		if ( re.match('rsi_k_period:', a)			!= None ):	rsi_k_period			= int( a.split(':')[1] )
		if ( re.match('rsi_k_5m_period:', a)			!= None ):	rsi_k_5m_period			= int( a.split(':')[1] )
		if ( re.match('rsi_d_period:', a)			!= None ):	rsi_d_period			= int( a.split(':')[1] )
		if ( re.match('rsi_slow:', a)				!= None ):	rsi_slow			= int( a.split(':')[1] )
		if ( re.match('stochrsi_offset:', a)			!= None ):	stochrsi_offset			= float( a.split(':')[1] )
		if ( re.match('stochrsi_5m_offset:', a)			!= None ):	stochrsi_5m_offset		= float( a.split(':')[1] )

		if ( re.match('stacked_ma_type_primary:', a)		!= None ):	stacked_ma_type_primary		= str( a.split(':')[1] )
		if ( re.match('stacked_ma_periods_primary:', a)		!= None ):	stacked_ma_periods_primary	= str( a.split(':')[1] )
		if ( re.match('stacked_ma_type:', a)			!= None ):	stacked_ma_type			= str( a.split(':')[1] )
		if ( re.match('stacked_ma_periods:', a)			!= None ):	stacked_ma_periods		= str( a.split(':')[1] )
		if ( re.match('stacked_ma_type_secondary:', a)		!= None ):	stacked_ma_type_secondary	= str( a.split(':')[1] )
		if ( re.match('stacked_ma_periods_secondary:', a)	!= None ):	stacked_ma_periods_secondary	= str( a.split(':')[1] )

		if ( re.match('mesa_sine_strict', a)			!= None ):	mesa_sine_strict		= True
		if ( re.match('mesa_sine_period:', a)			!= None ):	mesa_sine_period		= int( a.split(':')[1] )
		if ( re.match('mesa_sine_type:', a)			!= None ):	mesa_sine_type			= str( a.split(':')[1] )

		if ( re.match('use_ha_exit', a)				!= None ):	use_ha_exit			= True
		if ( re.match('use_ha_candles', a)			!= None ):	use_ha_candles			= True
		if ( re.match('use_trend_exit', a)			!= None ):	use_trend_exit			= True
		if ( re.match('use_trend', a)				!= None ):	use_trend			= True
		if ( re.match('trend_period:', a)			!= None ):	trend_period			= str( a.split(':')[1] )
		if ( re.match('trend_type:', a)				!= None ):	trend_type			= str( a.split(':')[1] )
		if ( re.match('use_combined_exit', a)			!= None ):	use_combined_exit		= True

		if ( re.match('use_bbands_kchannel_5m', a)		!= None ):	use_bbands_kchannel_5m		= True
		if ( re.match('use_bbands_kchannel_xover_exit', a)	!= None ):	use_bbands_kchannel_xover_exit	= True
		if ( re.match('bbands_kchannel_offset:', a)		!= None ):	bbands_kchannel_offset		= float( a.split(':')[1] )
		if ( re.match('bbands_kchan_squeeze_count:', a)		!= None ):	bbands_kchan_squeeze_count	= int( a.split(':')[1] )

		if ( re.match('bbands_kchan_ma_check', a)		!= None ):	bbands_kchan_ma_check		= True
		if ( re.match('bbands_kchan_ma_type:', a)		!= None ):	bbands_kchan_ma_type		= str( a.split(':')[1] )
		if ( re.match('bbands_kchan_ma_ptype:', a)		!= None ):	bbands_kchan_ma_ptype		= str( a.split(':')[1] )
		if ( re.match('bbands_kchan_ma_period:', a)		!= None ):	bbands_kchan_ma_period		= int( a.split(':')[1] )
		if ( re.match('max_squeeze_natr:', a)			!= None ):	max_squeeze_natr		= float( a.split(':')[1] )
		if ( re.match('bbands_roc_threshold:', a)		!= None ):	bbands_roc_threshold		= float( a.split(':')[1] )
		if ( re.match('bbands_roc_count:', a)			!= None ):	bbands_roc_count		= int( a.split(':')[1] )
		if ( re.match('bbands_roc_strict', a)			!= None ):	bbands_roc_strict		= True
		if ( re.match('bbands_kchannel_xover_exit_count:', a)	!= None ):	bbands_kchannel_xover_exit_count= int( a.split(':')[1] )
		if ( re.match('bbands_period:', a)			!= None ):	bbands_period			= int( a.split(':')[1] )
		if ( re.match('bbands_matype:', a)			!= None ):	bbands_matype			= int( a.split(':')[1] )
		if ( re.match('kchannel_period:', a)			!= None ):	kchannel_period			= int( a.split(':')[1] )
		if ( re.match('kchannel_atr_period:', a)		!= None ):	kchannel_atr_period		= int( a.split(':')[1] )
		if ( re.match('kchan_matype:', a)			!= None ):	kchan_matype			= str( a.split(':')[1] )

		if ( re.match('check_etf_indicators', a)		!= None ):	check_etf_indicators		= True
		if ( re.match('check_etf_indicators_strict', a)		!= None ):	check_etf_indicators_strict	= True
		if ( re.match('etf_tickers:', a)			!= None ):	etf_tickers			= str( a.split(':')[1] )
		if ( re.match('etf_roc_period:', a)			!= None ):	etf_roc_period			= int( a.split(':')[1] )
		if ( re.match('etf_min_rs:', a)				!= None ):	etf_min_rs			= float( a.split(':')[1] )
		if ( re.match('etf_min_natr:', a)			!= None ):	etf_min_natr			= float( a.split(':')[1] )

		if ( re.match('mfi_high_limit:', a)			!= None ):	mfi_high_limit			= float( a.split(':')[1] )
		if ( re.match('mfi_low_limit:', a)			!= None ):	mfi_low_limit			= float( a.split(':')[1] )
		if ( re.match('mfi_period:', a)				!= None ):	mfi_period			= int( a.split(':')[1] )
		if ( re.match('stochmfi_period:', a)			!= None ):	stoch_mfi_period		= int( a.split(':')[1] )
		if ( re.match('stochmfi_5m_period:', a)			!= None ):	stoch_mfi_5m_period		= int( a.split(':')[1] )
		if ( re.match('mfi_k_period:', a)			!= None ):	mfi_k_period			= int( a.split(':')[1] )
		if ( re.match('mfi_k_5m_period:', a)			!= None ):	mfi_k_5m_period			= int( a.split(':')[1] )
		if ( re.match('mfi_d_period:', a)			!= None ):	mfi_d_period			= int( a.split(':')[1] )
		if ( re.match('mfi_slow:', a)				!= None ):	mfi_slow			= int( a.split(':')[1] )
		if ( re.match('stochmfi_offset:', a)			!= None ):	stochmfi_offset			= float( a.split(':')[1] )
		if ( re.match('stochmfi_5m_offset:', a)			!= None ):	stochmfi_5m_offset		= float( a.split(':')[1] )

		if ( re.match('adx_threshold:', a)			!= None ):	adx_threshold			= float( a.split(':')[1] )
		if ( re.match('adx_period:', a)				!= None ):	adx_period			= int( a.split(':')[1] )
		if ( re.match('macd_long_period:', a)			!= None ):	macd_long_period		= int( a.split(':')[1] )
		if ( re.match('macd_short_period:', a)			!= None ):	macd_short_period		= int( a.split(':')[1] )
		if ( re.match('macd_signal_period:', a)			!= None ):	macd_signal_period		= int( a.split(':')[1] )
		if ( re.match('macd_offset:', a)			!= None ):	macd_offset			= float( a.split(':')[1] )

		if ( re.match('aroonosc_period:', a)			!= None ):	aroonosc_period			= int( a.split(':')[1] )
		if ( re.match('di_period:', a)				!= None ):	di_period			= int( a.split(':')[1] )
		if ( re.match('atr_period:', a)				!= None ):	atr_period			= int( a.split(':')[1] )
		if ( re.match('vpt_sma_period:', a)			!= None ):	vpt_sma_period			= int( a.split(':')[1] )

		if ( re.match('chop_period:', a)			!= None ):	chop_period			= int( a.split(':')[1] )
		if ( re.match('chop_low_limit:', a)			!= None ):	chop_low_limit			= float( a.split(':')[1] )
		if ( re.match('chop_high_limit:', a)			!= None ):	chop_high_limit			= float( a.split(':')[1] )

		if ( re.match('supertrend_atr_period:', a)		!= None ):	supertrend_atr_period		= int( a.split(':')[1] )
		if ( re.match('supertrend_min_natr:', a)		!= None ):	supertrend_min_natr		= float( a.split(':')[1] )

		if ( re.match('trin_roc_type:', a)			!= None ):	trin_roc_type			= str( a.split(':')[1] )
		if ( re.match('trin_roc_period:', a)			!= None ):	trin_roc_period			= int( a.split(':')[1] )
		if ( re.match('trin_ma_type:', a)			!= None ):	trin_ma_type			= str( a.split(':')[1] )
		if ( re.match('trin_ma_period:', a)			!= None ):	trin_ma_period			= int( a.split(':')[1] )
		if ( re.match('trin_oversold:', a)			!= None ):	trin_oversold			= float( a.split(':')[1] )
		if ( re.match('trin_overbought:', a)			!= None ):	trin_overbought			= float( a.split(':')[1] )

		if ( re.match('tick_threshold:', a)			!= None ):	tick_threshold			= float( a.split(':')[1] )
		if ( re.match('tick_ma_type:', a)			!= None ):	tick_ma_type			= str( a.split(':')[1] )
		if ( re.match('tick_ma_period:', a)			!= None ):	tick_ma_period			= int( a.split(':')[1] )

		if ( re.match('roc_type:', a)				!= None ):	roc_type			= str( a.split(':')[1] )
		if ( re.match('roc_exit', a)				!= None ):	roc_exit			= True
		if ( re.match('roc_period:', a)				!= None ):	roc_period			= int( a.split(':')[1] )
		if ( re.match('roc_ma_type:', a)			!= None ):	roc_ma_type			= str( a.split(':')[1] )
		if ( re.match('roc_ma_period:', a)			!= None ):	roc_ma_period			= int( a.split(':')[1] )
		if ( re.match('roc_threshold:', a)			!= None ):	roc_threshold			= float( a.split(':')[1] )

		if ( re.match('sp_monitor_tickers:', a)			!= None ):	sp_monitor_tickers		= str( a.split(':', 1)[1] )
		if ( re.match('sp_monitor_threshold:', a)		!= None ):	sp_monitor_threshold		= float( a.split(':')[1] )
		if ( re.match('sp_roc_type:', a)			!= None ):	sp_roc_type			= str( a.split(':')[1] )
		if ( re.match('sp_roc_period:', a)			!= None ):	sp_roc_period			= int( a.split(':')[1] )
		if ( re.match('sp_ma_period:', a)			!= None ):	sp_ma_period			= int( a.split(':')[1] )
		if ( re.match('sp_monitor_stacked_ma_type:', a)		!= None ):	sp_monitor_stacked_ma_type	= str( a.split(':')[1] )
		if ( re.match('sp_monitor_stacked_ma_periods:', a)	!= None ):	sp_monitor_stacked_ma_periods	= str( a.split(':')[1] )
		if ( re.match('sp_monitor_use_trix', a)			!= None ):	sp_monitor_use_trix		= True
		if ( re.match('sp_monitor_trix_ma_type:', a)		!= None ):	sp_monitor_trix_ma_type		= str( a.split(':')[1] )
		if ( re.match('sp_monitor_trix_ma_period:', a)		!= None ):	sp_monitor_trix_ma_period	= int( a.split(':')[1] )
		if ( re.match('sp_monitor_strict', a)			!= None ):	sp_monitor_strict		= True

		if ( re.match('time_sales_algo', a)			!= None ):	time_sales_algo			= True
		if ( re.match('time_sales_use_keylevel', a)		!= None ):	time_sales_use_keylevel		= True
		if ( re.match('time_sales_size_threshold:', a)		!= None ):	time_sales_size_threshold	= int( a.split(':')[1] )
		if ( re.match('time_sales_kl_size_threshold:', a)	!= None ):	time_sales_kl_size_threshold	= int( a.split(':')[1] )

		if ( re.match('keylevel_use_daily', a)			!= None ):	keylevel_use_daily		= True
		if ( re.match('keylevel_strict', a)			!= None ):	keylevel_strict			= True
		if ( re.match('price_support_pct', a)			!= None ):	price_support_pct		= float( a.split(':')[1] )
		if ( re.match('price_resistance_pct', a)		!= None ):	price_resistance_pct		= float( a.split(':')[1] )
		if ( re.match('resist_pct_dynamic', a)			!= None ):	resist_pct_dynamic		= True

		if ( re.match('min_intra_natr:', a)			!= None ):	min_intra_natr			= float( a.split(':')[1] )
		if ( re.match('max_intra_natr:', a)			!= None ):	max_intra_natr			= float( a.split(':')[1] )
		if ( re.match('min_daily_natr:', a)			!= None ):	min_daily_natr			= float( a.split(':')[1] )
		if ( re.match('max_daily_natr:', a)			!= None ):	max_daily_natr			= float( a.split(':')[1] )

	# Tweak or check the algo config
	if ( primary_stochrsi == True and primary_stochmfi == True ):
		print('Error: you can only use primary_stochrsi or primary_stochmfi, but not both. Exiting.')
		sys.exit(1)
	elif ( primary_stochrsi == False and primary_stochmfi == False and primary_stacked_ma == False and
			primary_mama_fama == False and primary_mesa_sine == False and primary_trin == False and primary_sp_monitor == False ):
		print('Error: you must use one of primary_stochrsi, primary_stochmfi, primary_stacked_ma, primary_mama_fama, primary_mesa_sine, primary_trin or primary_sp_monitor. Exiting.')
		sys.exit(1)

	# Stacked MA periods expect to be comma-delimited, but the --algos line is already comma-delimited. So MA
	#  periods may be specified on the algos line using a period delimiter, which we convert back to comma here.
	if ( stacked_ma_periods_primary != args.stacked_ma_periods_primary ):		stacked_ma_periods_primary	= re.sub( '\.', ',', stacked_ma_periods_primary )
	if ( stacked_ma_periods !=  args.stacked_ma_periods ):				stacked_ma_periods		= re.sub( '\.', ',', stacked_ma_periods )
	if ( stacked_ma_periods_secondary != args.stacked_ma_periods_secondary ):	stacked_ma_periods_secondary	= re.sub( '\.', ',', stacked_ma_periods_secondary )

	if ( qe_stacked_ma_periods != args.qe_stacked_ma_periods ):			qe_stacked_ma_periods		= re.sub( '\.', ',', qe_stacked_ma_periods )
	if ( sp_monitor_stacked_ma_periods != args.sp_monitor_stacked_ma_periods ):	sp_monitor_stacked_ma_periods	= re.sub( '\.', ',', sp_monitor_stacked_ma_periods )

	# Similar to above, convert the etf_tickers using a period delimiter to comma-delimited
	if ( etf_tickers != args.etf_tickers ):						etf_tickers			= re.sub( '\.', ',', etf_tickers )
	args.etf_tickers = str(args.etf_tickers) + ',' + str(etf_tickers)

	# sp_monitor_tickers are '+' delimited
	if ( sp_monitor_tickers != args.sp_monitor_tickers ):				sp_monitor_tickers		= re.sub( '\+', ',', sp_monitor_tickers )

	# support_resistance==True implies that use_keylevel==True
	if ( support_resistance == True):
		#use_natr_resistance	= True # Optional
		#lod_hod_check		= True # Optional
		use_keylevel		= True
		use_vwap		= True
		use_pdc			= True

	# DMI/MACD overrides the simple variant of the algorithm
	if ( dmi == True and dmi_simple == True ):
		dmi_simple = False
	if ( macd == True and macd_simple == True ):
		macd_simple = False

	# Aroon Oscillator with MACD
	# aroonosc_with_macd_simple implies that if aroonosc is enabled, then macd_simple will be
	#   enabled or disabled based on the level of the aroon oscillator.
	if ( args.aroonosc_with_macd_simple == True and aroonosc == True ):
		if ( macd == True or macd_simple == True ):
			print('INFO: Aroonosc enabled with --aroonosc_with_macd_simple, disabling macd and macd_simple')
			macd = False
			macd_simple = False

	# Default quick_exit_percent to exit_percent if it is unset
	if ( options == False and (quick_exit_percent == None and args.exit_percent != None) ):
		quick_exit_percent = args.exit_percent
	elif ( options == True and (quick_exit_percent == None and args.options_exit_percent != None) ):
		quick_exit_percent = args.options_exit_percent

	# If using scalpe_mode, enable quick_exit and set quick_exit_percent to scalp_mode_pct
	if ( scalp_mode == True ):
		quick_exit		= True
		quick_exit_percent	= scalp_mode_pct

	if ( ph_only == True ):
		safe_open = False

	# Populate the algo{} dict with all the options parsed above
	algo_list = {   'algo_id':				algo_id,

			'stock_usd':				stock_usd,
			'safe_open':				safe_open,
			'ph_only':				ph_only,

			'quick_exit':				quick_exit,
			'quick_exit_percent':			quick_exit_percent,
			'trend_quick_exit':			trend_quick_exit,
			'qe_stacked_ma_periods':		qe_stacked_ma_periods,
			'qe_stacked_ma_type':			qe_stacked_ma_type,
			'scalp_mode':				scalp_mode,
			'scalp_mode_pct':			scalp_mode_pct,

			'options':				options,
			'options_usd':				options_usd,
			'near_expiration':			near_expiration,
			'otm_level':				otm_level,
			'start_day_offset':			start_day_offset,

			'primary_stochrsi':			primary_stochrsi,
			'primary_stochmfi':			primary_stochmfi,
			'primary_stacked_ma':			primary_stacked_ma,
			'primary_mama_fama':			primary_mama_fama,
			'primary_mesa_sine':			primary_mesa_sine,
			'primary_trin':				primary_trin,
			'primary_sp_monitor':			primary_sp_monitor,

			'trin':					trin,
			'tick':					tick,
			'roc':					roc,
			'sp_monitor':				sp_monitor,

			'stacked_ma':				stacked_ma,
			'stacked_ma_secondary':			stacked_ma_secondary,
			'mama_fama':				mama_fama,
			'stochrsi_5m':				stochrsi_5m,
			'stochmfi':				stochmfi,
			'stochmfi_5m':				stochmfi_5m,
			'rsi':					rsi,
			'mfi':					mfi,
			'adx':					adx,
			'dmi':					dmi,
			'dmi_simple':				dmi_simple,
			'macd':					macd,
			'macd_simple':				macd_simple,
			'aroonosc':				aroonosc,
			'chop_index':				chop_index,
			'chop_simple':				chop_simple,
			'supertrend':				supertrend,
			'vwap':					vwap,
			'vpt':					vpt,

			'support_resistance':			support_resistance,
			'use_keylevel':				use_keylevel,
			'use_vwap':				use_vwap,
			'use_pdc':				use_pdc,
			'lod_hod_check':			lod_hod_check,
			'use_natr_resistance':			use_natr_resistance,
			'va_check':				va_check,

			# Algo modifiers
			'rsi_high_limit':			rsi_high_limit,
			'rsi_low_limit':			rsi_low_limit,

			'rsi_period':				rsi_period,
			'stochrsi_period':			stochrsi_period,
			'stochrsi_5m_period':			stochrsi_5m_period,
			'rsi_k_period':				rsi_k_period,
			'rsi_k_5m_period':			rsi_k_5m_period,
			'rsi_d_period':				rsi_d_period,
			'rsi_slow':				rsi_slow,
			'stochrsi_offset':			stochrsi_offset,
			'stochrsi_5m_offset':			stochrsi_5m_offset,

			'bbands_kchannel':			bbands_kchannel,
			'bbands_kchannel_offset':		bbands_kchannel_offset,
			'bbands_kchan_squeeze_count':		bbands_kchan_squeeze_count,
			'bbands_kchan_ma_check':		bbands_kchan_ma_check,
			'bbands_kchan_ma_type':			bbands_kchan_ma_type,
			'bbands_kchan_ma_ptype':		bbands_kchan_ma_ptype,
			'bbands_kchan_ma_period':		bbands_kchan_ma_period,
			'max_squeeze_natr':			max_squeeze_natr,
			'bbands_roc_threshold':			bbands_roc_threshold,
			'bbands_roc_count':			bbands_roc_count,
			'bbands_roc_strict':			bbands_roc_strict,
			'use_bbands_kchannel_5m':		use_bbands_kchannel_5m,
			'use_bbands_kchannel_xover_exit':	use_bbands_kchannel_xover_exit,
			'bbands_kchannel_xover_exit_count': 	bbands_kchannel_xover_exit_count,
			'bbands_period':			bbands_period,
			'bbands_matype':			bbands_matype,
			'kchannel_period':			kchannel_period,
			'kchannel_atr_period':			kchannel_atr_period,
			'kchan_matype':				kchan_matype,

			'check_etf_indicators':			check_etf_indicators,
			'check_etf_indicators_strict':		check_etf_indicators_strict,
			'etf_tickers':				etf_tickers,
			'etf_roc_period':			etf_roc_period,
			'etf_min_rs':				etf_min_rs,
			'etf_min_natr':				etf_min_natr,

			'stacked_ma_type_primary':		stacked_ma_type_primary,
			'stacked_ma_periods_primary':		stacked_ma_periods_primary,
			'stacked_ma_type':			stacked_ma_type,
			'stacked_ma_periods':			stacked_ma_periods,
			'stacked_ma_type_secondary':		stacked_ma_type_secondary,
			'stacked_ma_periods_secondary':		stacked_ma_periods_secondary,

			'mesa_sine_strict':			mesa_sine_strict,
			'mesa_sine_period':			mesa_sine_period,
			'mesa_sine_type':			mesa_sine_type,

			'use_ha_exit':				use_ha_exit,
			'use_ha_candles':			use_ha_candles,
			'use_trend_exit':			use_trend_exit,
			'use_trend':				use_trend,
			'trend_period':				trend_period,
			'trend_type':				trend_type,
			'use_combined_exit':			use_combined_exit,

			'mfi_high_limit':			mfi_high_limit,
			'mfi_low_limit':			mfi_low_limit,

			'mfi_period':				mfi_period,
			'stochmfi_period':			stochmfi_period,
			'stochmfi_5m_period':			stochmfi_5m_period,
			'mfi_k_period':				mfi_k_period,
			'mfi_k_5m_period':			mfi_k_5m_period,
			'mfi_d_period':				mfi_d_period,
			'mfi_slow':				mfi_slow,
			'stochmfi_offset':			stochmfi_offset,
			'stochmfi_5m_offset':			stochmfi_5m_offset,

			'adx_threshold':			adx_threshold,
			'adx_period':				adx_period,

			'macd_long_period':			macd_long_period,
			'macd_short_period':			macd_short_period,
			'macd_signal_period':			macd_signal_period,
			'macd_offset':				macd_offset,

			'aroonosc_period':			aroonosc_period,
			'di_period':				di_period,
			'atr_period':				atr_period,
			'vpt_sma_period':			vpt_sma_period,
			'chop_period':				chop_period,
			'chop_low_limit':			chop_low_limit,
			'chop_high_limit':			chop_high_limit,

			'supertrend_atr_period':		supertrend_atr_period,
			'supertrend_min_natr':			supertrend_min_natr,

			'trin_roc_type':			trin_roc_type,
			'trin_roc_period':			trin_roc_period,
			'trin_ma_type':				trin_ma_type,
			'trin_ma_period':			trin_ma_period,
			'trin_oversold':			trin_oversold,
			'trin_overbought':			trin_overbought,

			'tick_threshold':			tick_threshold,
			'tick_ma_type':				tick_ma_type,
			'tick_ma_period':			tick_ma_period,

			'roc_type':				roc_type,
			'roc_exit':				roc_exit,
			'roc_period':				roc_period,
			'roc_ma_type':				roc_ma_type,
			'roc_ma_period':			roc_ma_period,
			'roc_threshold':			roc_threshold,

			'sp_monitor_tickers':			sp_monitor_tickers,
			'sp_monitor_threshold':			sp_monitor_threshold,
			'sp_roc_type':				sp_roc_type,
			'sp_roc_period':			sp_roc_period,
			'sp_ma_period':				sp_ma_period,
			'sp_monitor_stacked_ma_type':		sp_monitor_stacked_ma_type,
			'sp_monitor_stacked_ma_periods':	sp_monitor_stacked_ma_periods,
			'sp_monitor_use_trix':			sp_monitor_use_trix,
			'sp_monitor_trix_ma_type':		sp_monitor_trix_ma_type,
			'sp_monitor_trix_ma_period':		sp_monitor_trix_ma_period,
			'sp_monitor_strict':			sp_monitor_strict,

			'time_sales_algo':			time_sales_algo,
			'time_sales_use_keylevel':		time_sales_use_keylevel,
			'time_sales_size_threshold':		time_sales_size_threshold,
			'time_sales_kl_size_threshold':		time_sales_kl_size_threshold,

			'keylevel_use_daily':			keylevel_use_daily,
			'keylevel_strict':			keylevel_strict,
			'price_resistance_pct':			price_resistance_pct,
			'price_support_pct':			price_support_pct,
			'resist_pct_dynamic':			resist_pct_dynamic,

			'min_intra_natr':			min_intra_natr,
			'max_intra_natr':			max_intra_natr,
			'min_daily_natr':			min_daily_natr,
			'max_daily_natr':			max_daily_natr,

			'valid_tickers':			[],
			'exclude_tickers':			[]  }

	algos.append(algo_list)

# Clean up this mess
# All the stuff above should be put into a function to avoid this cleanup stuff. I know it. It'll happen eventually.
del(stock_usd,quick_exit,quick_exit_percent,trend_quick_exit,qe_stacked_ma_periods,qe_stacked_ma_type,scalp_mode,scalp_mode_pct,ph_only)
del(primary_stochrsi,primary_stochmfi,primary_stacked_ma,primary_mama_fama,primary_mesa_sine,primary_trin,primary_sp_monitor)
del(stacked_ma,stacked_ma_secondary,mama_fama,stochrsi_5m,stochmfi,stochmfi_5m)
del(rsi,mfi,adx,dmi,dmi_simple,macd,macd_simple,aroonosc,chop_index,chop_simple,supertrend,bbands_kchannel,vwap,vpt)
del(support_resistance,use_keylevel,lod_hod_check,use_natr_resistance,use_vwap,use_pdc)
del(rsi_high_limit,rsi_low_limit,rsi_period,stochrsi_period,stochrsi_5m_period,rsi_k_period,rsi_k_5m_period,rsi_d_period,rsi_slow,stochrsi_offset,stochrsi_5m_offset)
del(mfi_high_limit,mfi_low_limit,mfi_period,stochmfi_period,stochmfi_5m_period,mfi_k_period,mfi_k_5m_period,mfi_d_period,mfi_slow,stochmfi_offset,stochmfi_5m_offset)
del(adx_threshold,adx_period,macd_long_period,macd_short_period,macd_signal_period,macd_offset,aroonosc_period,di_period,atr_period,vpt_sma_period)
del(chop_period,chop_low_limit,chop_high_limit,supertrend_atr_period,supertrend_min_natr)
del(bbands_kchannel_offset,bbands_kchan_squeeze_count,bbands_period,kchannel_period,kchannel_atr_period,max_squeeze_natr,bbands_roc_threshold,bbands_roc_count,bbands_roc_strict)
del(bbands_kchan_ma_check,bbands_kchan_ma_type,bbands_kchan_ma_ptype,bbands_kchan_ma_period)
del(stacked_ma_type_primary,stacked_ma_periods_primary,stacked_ma_type,stacked_ma_periods,stacked_ma_type_secondary,stacked_ma_periods_secondary,mesa_sine_period,mesa_sine_type,mesa_sine_strict)
del(keylevel_use_daily,keylevel_strict,va_check,min_intra_natr,max_intra_natr,min_daily_natr,max_daily_natr,price_resistance_pct,price_support_pct,resist_pct_dynamic)
del(use_bbands_kchannel_5m,use_bbands_kchannel_xover_exit,bbands_kchannel_xover_exit_count,bbands_matype,kchan_matype)
del(use_ha_exit,use_ha_candles,use_trend_exit,use_trend,trend_period,trend_type,use_combined_exit)
del(check_etf_indicators,check_etf_indicators_strict,etf_tickers,etf_roc_period,etf_min_rs,etf_min_natr)
del(trin,tick,roc,sp_monitor,trin_roc_type,trin_roc_period,trin_ma_type,trin_ma_period,trin_oversold,trin_overbought,tick_threshold,tick_ma_type,tick_ma_period)
del(roc_type,roc_period,roc_ma_type,roc_ma_period,roc_threshold,roc_exit)
del(sp_monitor_tickers,sp_monitor_threshold,sp_roc_type,sp_roc_period,sp_ma_period,sp_monitor_stacked_ma_type,sp_monitor_stacked_ma_periods,sp_monitor_use_trix,sp_monitor_trix_ma_type,sp_monitor_trix_ma_period,sp_monitor_strict)
del(time_sales_algo,time_sales_use_keylevel,time_sales_size_threshold,time_sales_kl_size_threshold)
del(options,options_usd,near_expiration,otm_level,start_day_offset)

# Set valid tickers for each algo, if configured
if ( args.algo_valid_tickers != None ):
	for algo in args.algo_valid_tickers:
		try:
			algo_id, tickers = algo.split(':')

		except Exception as e:
			print('Caught exception: error setting algo_valid_tickers (' + str(algo) + '), exiting.', file=sys.stderr)
			sys.exit(1)

		valid_ids = [ a['algo_id'] for a in algos ]
		if ( algo_id in valid_ids ):
			for a in algos:
				if ( a['algo_id'] == algo_id ):
					a['valid_tickers'] = a['valid_tickers'] + tickers.split(',')

			# Append this list to the global stock list (duplicates will be filtered later)
			args.stocks = str(args.stocks) + ',' + str(tickers)

		else:
			print('Error: algo_id not found in algos{}. Valid algos: (' + str(valid_ids) + '), exiting.', file=sys.stderr)
			sys.exit(1)

# Set tickers to exclude for each algo
if ( args.algo_exclude_tickers != None ):
	for algo in args.algo_exclude_tickers:
		try:
			algo_id, tickers = algo.split(':')

		except Exception as e:
			print('Caught exception: error setting algo_exclude_tickers (' + str(algo) + '), ' + str(e), file=sys.stderr)
			sys.exit(1)

		exclude_ids = [ a['algo_id'] for a in algos ]
		if ( algo_id in exclude_ids ):
			for a in algos:
				if ( a['algo_id'] == algo_id ):
					a['exclude_tickers'] = a['exclude_tickers'] + tickers.split(',')

		else:
			print('Error: algo_id not found in algos{}. Valid algos: (' + str(valid_ids) + '), exiting.', file=sys.stderr)
			sys.exit(1)


# Add etf_tickers if check_etf_indicators is True
# etf_tickers should go in the front of args.stocks to ensure these stocks are not truncated
if ( args.check_etf_indicators == True ):
	args.stocks = str(args.etf_tickers) + ',' + str(args.stocks)

# Process sp_monitor, trin and tick indicators to add the appropriate ticker name to stocks[ticker] array.
sp_tickers = []
for algo in range( len(algos) ):

	# SP_Monitor
	# Format is "ticker1:pct1,ticker2:pct2,..."
	# Populate sp_tickers[] to use later, and turn algos[algo]['sp_monitor_tickers'] into an array containing a dict with
	#  the tickername and percent weighting of each ticker:
	#
	#	algos[algo]['sp_monitor_tickers'] = [ { 'sp_t': tickername, 'sp_pct': percent_weight }, ... ]
	#
	if ( algos[algo]['sp_monitor_tickers'] != None ):
		sp_monitor_tickers = algos[algo]['sp_monitor_tickers'].split(',')
		if ( len(sp_monitor_tickers) != 0 ):
			algos[algo]['sp_monitor_tickers'] = []
			for sp_ticker in sp_monitor_tickers:
				try:
					sp_t	= sp_ticker.split(':')[0]
					sp_pct	= float( sp_ticker.split(':')[1] ) / 100

				except Exception as e:
					print('Caught exception: error parsing sp_ticker (' + str(sp_ticker) + '), ' + str(e), file=sys.stderr)
					sys.exit(1)

				sp_tickers.append( sp_t )
				algos[algo]['sp_monitor_tickers'].append( { 'sp_t': sp_t, 'sp_pct': sp_pct } )

	# TRIN
	if ( algos[algo]['primary_trin'] == True or algos[algo]['trin'] == True ):
		args.stocks = '$TRIN,$TRINA,$TRINQ,' + str(args.stocks)

	# TICK
	if ( algos[algo]['tick'] == True ):
		args.stocks = '$TICK,' + str(args.stocks)

if ( len(sp_tickers) > 0 ):
	args.stocks = ','.join(sp_tickers) + ',' + str(args.stocks)


# Initialize stocks{}
stock_list = args.stocks.split(',')
stock_list = list( dict.fromkeys(stock_list) ) # remove any duplicate tickers
stock_list = ','.join(stock_list)

print()
print( 'Initializing stock tickers: ' + str(stock_list) )

# Fix up and sanity check the stock symbol before proceeding
stock_list = tda_gobot_helper.fix_stock_symbol(stock_list)
stock_list = tda_gobot_helper.check_stock_symbol(stock_list)
if ( isinstance(stock_list, bool) and stock_list == False ):
	print('Error: check_stock_symbol(' + str(stock_list) + ') returned False, exiting.')
	exit(1)

stocks = OrderedDict()
for ticker in stock_list.split(','):

	if ( ticker == '' ):
		continue

	stocks.update( { ticker: { 'shortable':			True,
				   'isvalid':			True,
				   'tradeable':			True,
				   'tx_id':			random.randint(1000, 9999),

				   'num_purchases':		args.num_purchases,
				   'failed_txs':		args.max_failed_txs,
				   'failed_usd':		args.max_failed_usd,

				   'stock_usd':			args.stock_usd,
				   'stock_qty':			0,
				   'order_id':			None,
				   'orig_base_price':		float(0),
				   'base_price':		float(0),

				   'options_ticker':		None,
				   'options_usd':		args.options_usd,
				   'options_qty':		0,
				   'options_orig_base_price':	float(0),
				   'options_base_price':	float(0),

				   'incr_threshold':		args.incr_threshold,
				   'orig_incr_threshold':	args.incr_threshold,
				   'decr_threshold':		args.decr_threshold,
				   'orig_decr_threshold':	args.decr_threshold,
				   'exit_percent':		args.exit_percent,

				   'quick_exit':		args.quick_exit,
				   'roc_exit':			args.roc_exit,

				   'options_incr_threshold':	args.options_incr_threshold,
				   'options_decr_threshold':	args.options_decr_threshold,
				   'options_exit_percent':	args.options_exit_percent,

				   'primary_algo':		None,

				   # Action signals
				   'final_buy_signal':		False,
				   'final_sell_signal':		False,	# Currently unused
				   'final_short_signal':	False,
				   'final_buy_to_cover_signal':	False,	# Currently unused

				   'exit_percent_signal':	False,

				   # Indicator variables
				   # StochRSI
				   'cur_rsi_k':			float(-1),
				   'prev_rsi_k':		float(-1),
				   'cur_rsi_d':			float(-1),
				   'prev_rsi_d':		float(-1),

				   'cur_rsi_k_5m':		float(-1),
				   'prev_rsi_k_5m':		float(-1),
				   'cur_rsi_d_5m':		float(-1),
				   'prev_rsi_d_5m':		float(-1),

				   # StochMFI
				   'cur_mfi_k':			float(-1),
				   'prev_mfi_k':		float(-1),
				   'cur_mfi_d':			float(-1),
				   'prev_mfi_d':		float(-1),

				   'cur_mfi_k_5m':		float(-1),
				   'prev_mfi_k_5m':		float(-1),
				   'cur_mfi_d_5m':		float(-1),
				   'prev_mfi_d_5m':		float(-1),

				   # Stacked MA
				   'cur_s_ma_primary':		(0,0,0,0),
				   'prev_s_ma_primary':		(0,0,0,0),
				   'cur_s_ma':			(0,0,0,0),
				   'prev_s_ma':			(0,0,0,0),
				   'cur_s_ma_secondary':	(0,0,0,0),
				   'prev_s_ma_secondary':	(0,0,0,0),

				   'cur_s_ma_ha_primary':	(0,0,0,0),
				   'prev_s_ma_ha_primary':	(0,0,0,0),
				   'cur_s_ma_ha':		(0,0,0,0),
				   'prev_s_ma_ha':		(0,0,0,0),
				   'cur_s_ma_ha_secondary':	(0,0,0,0),
				   'prev_s_ma_ha_secondary':	(0,0,0,0),

				   'cur_daily_ma':		(0,0,0,0),

				   # MAMA/FAMA
				   'cur_mama':			float(-1),
				   'prev_mama':			float(-1),
				   'cur_fama':			float(-1),
				   'prev_fama':			float(-1),

				   # MESA Sine Wave
				   'cur_sine':			float(-1),
				   'prev_sine':			float(-1),
				   'cur_lead':			float(-1),
				   'prev_lead':			float(-1),

				   # RSI
				   'cur_rsi':			float(-1),
				   'prev_rsi':			float(-1),

				   # MFI
				   'cur_mfi':			float(-1),
				   'prev_mfi':			float(-1),

				   # ADX
				   'cur_adx':			float(-1),

				   # DMI
				   'cur_plus_di':		float(-1),
				   'prev_plus_di':		float(-1),
				   'cur_minus_di':		float(-1),
				   'prev_minus_di':		float(-1),

				   # MACD
				   'cur_macd':			float(-1),
				   'prev_macd':			float(-1),
				   'cur_macd_avg':		float(-1),
				   'prev_macd_avg':		float(-1),

				   # Aroon Oscillator
				   'aroonosc_period':		args.aroonosc_period,
				   'cur_aroonosc':		float(-1),

				   # Chop Index
				   'cur_chop':			float(-1),
				   'prev_chop':			float(-1),

				   # Supertrend
				   'cur_supertrend':		float(-1),
				   'prev_supertrend':		float(-1),

				   # Bollinger Bands and Keltner Channel
				   'cur_bbands':		float(-1),
				   'prev_bbands':		float(-1),
				   'cur_kchannel':		float(-1),
				   'prev_kchannel':		float(-1),

				   # $TRIN, $TICK and ROC
				   'cur_trin':			0,
				   'prev_trin':			0,

				   'cur_tick':			0,
				   'prev_tick':			0,

				   'cur_roc_ma':		0,
				   'prev_roc_ma':		0,

				   # SP Monitor
				   'cur_sp_monitor':		0,
				   'prev_sp_monitor':		0,

				   # VWAP
				   'cur_vwap':			float(-1),
				   'cur_vwap_up':		float(-1),
				   'cur_vwap_down':		float(-1),

				   # VPT
				   'cur_vpt':			float(-1),
				   'prev_vpt':			float(-1),
				   'cur_vpt_sma':		float(-1),
				   'prev_vpt_sma':		float(-1),

				   # ATR / NATR
				   'cur_atr':			float(-1),
				   'cur_natr':			float(-1),
				   'atr_daily':			float(-1),
				   'natr_daily':		float(-1),

				   # Support / Resistance
				   'three_week_high':		float(0),
				   'three_week_low':		float(0),
				   'three_week_avg':		float(0),
				   'twenty_week_high':		float(0),
				   'twenty_week_low':		float(0),
				   'twenty_week_avg':		float(0),

				   'today_open':		float(0),
				   'previous_day_close':	float(0),
				   'previous_day_high':		float(0),
				   'previous_day_low':		float(0),
				   'previous_twoday_close':	float(0),
				   'previous_twoday_high':	float(0),
				   'previous_twoday_low':	float(0),

				   # Key levels
				   'kl_long_support':		[],
				   'kl_long_resistance':	[],
				   'kl_long_support_daily':	[],
				   'kl_long_resistance_daily':	[],

				   # Volume Area High (VAH) and Volume Area Low (VAL)
				   'vah':			0,
				   'val':			0,
				   'vah_1':			0,
				   'val_1':			0,
				   'vah_2':			0,
				   'val_2':			0,

				   # SMA200 and EMA50
				   'cur_sma':			None,
				   'cur_ema':			None,

				   # Rate of Change (ROC)
				   'cur_roc':			float(0),

				   # Trend Quick Exit
				   'cur_qe_s_ma':		(0,0,0,0),
				   'prev_qe_s_ma':		(0,0,0,0),

				   # Per-algo indicator signals
				   'algo_signals':		{},

				   'prev_timestamp':		0,
				   'cur_seq':			0,
				   'prev_seq':			0,

				   # Candle data
				   'pricehistory':		{ 'candles': [], 'symbol': ticker },
				   'pricehistory_5m':		{ 'candles': [], 'symbol': ticker },
				   'pricehistory_daily':	{},
				   'pricehistory_weekly':	{},

				   'exchange':			None,
				   'ask_price':			float(1),
				   'ask_size':			int(0),
				   'bid_price':			float(0),
				   'bid_size':			int(0),
				   'bid_ask_pct':		float(0),
				   'last_price':		float(0),
				   'last_size':			int(0),
				   'security_status':		'Normal',
				   'total_volume':		int(0),

				   # Level 1 data
				   'level1':			{},

				   # Level 2 order book data
				   'level2':			{ 'cur_ask': {	'ask_price':	float(0),
										'num_asks':	int(0),
										'total_volume':	int(0) },

								  'cur_bid': {	'bid_price':	float(0),
										'num_bids':	int(0),
										'total_volume':	int(0) },

								  'asks':	{},
								  'bids':	{},

								  'history':	{} }, # end level2{}

				   # Equity time and sale data
				   'ets':			{ 'cumulative_vol':	0,
								  'downtick_vol':	0,
								  'uptick_vol':		0,

								  'cumulative_delta':	{},
								  'keylevels':		{},
								  'tx_data':		{},

								  'history':		[] }, # end ets (time/sales)
			}} )

	# Per algo signals
	for algo in algos:
		signals = { algo['algo_id']: {	'signal_mode':				'long',

						'buy_signal':				False,
						'sell_signal':				False,
						'short_signal':				False,
						'buy_to_cover_signal':			False,

						# Indicator signals
						'stochrsi_signal':			False,
						'stochrsi_crossover_signal':		False,
						'stochrsi_threshold_signal':		False,

						'stochrsi_5m_signal':			False,
						'stochrsi_5m_crossover_signal':		False,
						'stochrsi_5m_threshold_signal':		False,
						'stochrsi_5m_final_signal':		False,

						'stochmfi_signal':			False,
						'stochmfi_crossover_signal':		False,
						'stochmfi_threshold_signal':		False,
						'stochmfi_final_signal':		False,

						'stochmfi_5m_signal':			False,
						'stochmfi_5m_crossover_signal':		False,
						'stochmfi_5m_threshold_signal':		False,
						'stochmfi_5m_final_signal':		False,

						'rsi_signal':				False,
						'mfi_signal':				False,
						'adx_signal':				False,
						'dmi_signal':				False,
						'macd_signal':				False,
						'aroonosc_signal':			False,
						'chop_init_signal':			False,
						'chop_signal':				False,
						'supertrend_signal':			False,
						'vwap_signal':				False,
						'vpt_signal':				False,
						'resistance_signal':			False,

						'stacked_ma_signal':			False,
						'mama_fama_signal':			False,
						'mesa_sine_signal':			False,
						'bbands_kchan_init_signal':		False,
						'bbands_roc_threshold_signal':		False,
						'bbands_kchan_crossover_signal':	False,
						'bbands_kchan_signal':			False,
						'bbands_kchan_signal_counter':		0,
						'bbands_kchan_xover_counter':		0,
						'bbands_roc_counter':			0,

						'trin_init_signal':			False,
						'trin_signal':				False,
						'trin_counter':				0,
						'tick_signal':				False,
						'roc_signal':				False,

						'sp_monitor_init_signal':		False,
						'sp_monitor_signal':			False,

						# Time and Sales monitor
						'ts_monitor_signal':			False,

						# Relative Strength
						'rs_signal':				False,

						'plus_di_crossover':			False,
						'minus_di_crossover':			False,
						'macd_crossover':			False,
						'macd_avg_crossover':			False }}

		stocks[ticker]['algo_signals'].update( signals )

		# Support time_sales_algo
		stocks[ticker]['ets']['cumulative_delta'][algo['algo_id']]	= 0
		stocks[ticker]['ets']['keylevels'][algo['algo_id']]		= []
		stocks[ticker]['ets']['tx_data'][algo['algo_id']]		= {}

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	sys.exit(1)


# If check_etf_indicators is enabled then make sure the ETF stocks are listed in the global stocks{} dict
#  and are configured as not tradeable.
if ( args.check_etf_indicators == True ):
	args.etf_tickers_allowtrade = args.etf_tickers_allowtrade.split(',')

	for ticker in args.etf_tickers.split(','):
		if ( ticker not in stocks ):
			print('Error: check_etf_indicators is enabled, however ticker "' + str(ticker) + '" does not appear to be configured in global stocks{} dictionary, exiting.')
			sys.exit(1)

		stocks[ticker]['tradeable'] = False
		if ( args.etf_tickers_allowtrade != None and ticker in args.etf_tickers_allowtrade ):
			stocks[ticker]['tradeable'] = True

# Ensure sp_monitor tickers are not tradeable
if ( len(sp_tickers) != 0 ):
	for ticker in sp_tickers:
		if ( ticker not in stocks ):
			print('Error: sp_tickers is not empty, however ticker "' + str(ticker) + '" does not appear to be configured in global stocks{} dictionary, exiting.')
			sys.exit(1)

		stocks[ticker]['tradeable'] = False

# $TRIN and $TICK are not tradeable
try:
	stocks['$TRIN']['isvalid']	= True
	stocks['$TRIN']['tradeable']	= False

	stocks['$TRINQ']['isvalid']	= True
	stocks['$TRINQ']['tradeable']	= False

	stocks['$TRINA']['isvalid']	= True
	stocks['$TRINA']['tradeable']	= False
except:
	pass

try:
	stocks['$TICK']['isvalid']	= True
	stocks['$TICK']['tradeable']	= False

except:
	pass


# Get stock_data info about the stock that we can use later (i.e. shortable)
try:
	stock_data = tda_gobot_helper.get_quotes(stock_list)

except Exception as e:
	print('Caught exception: tda_gobot_helper.get_quote(' + str(stock_list) + '): ' + str(e), file=sys.stderr)
	sys.exit(1)

# Initialize additional stocks{} values
# First purge the blacklist of stale entries
tda_gobot_helper.clean_blacklist(debug=False)
nasdaq_tickers	= []
nyse_tickers	= []
for ticker in list(stocks.keys()):

	# Skip ths section if the ticker is an indicator or otherwise not marked as tradeable
#	if ( stocks[ticker]['tradeable'] == False ):
	if ( re.search('^\$', ticker) != None ):
		continue

	# Invalidate ticker if it is noted in the blacklist file
	if ( tda_gobot_helper.check_blacklist(ticker) == True and args.force == False ):
		print('(' + str(ticker) + ') Warning: stock ' + str(ticker) + ' found in blacklist file, removing from the list')
		stocks[ticker]['isvalid'] = False

		try:
			del stocks[ticker]
		except KeyError:
			print('Warning: failed to delete key "' + str(ticker) + '" from stocks{}')

		continue

	# Confirm that we can short this stock
	# Sometimes this parameter is not set in the TDA get_quote response?
	try:
		stock_data[ticker]['shortable']
		stock_data[ticker]['marginable']
	except:
		stock_data[ticker]['shortable'] = str(False)
		stock_data[ticker]['marginable'] = str(False)

	if ( args.short == True or args.shortonly == True ):
		if ( stock_data[ticker]['shortable'] == str(False) or stock_data[ticker]['marginable'] == str(False) ):
			if ( args.shortonly == True ):
				print('Error: stock(' + str(ticker) + '): does not appear to be shortable, removing from the list')
				stocks[ticker]['isvalid'] = False

				try:
					del stocks[ticker]
				except KeyError:
					print('Warning: failed to delete key "' + str(ticker) + '" from stocks{}')

				continue

			elif ( args.short == True ):
				print('Warning: stock(' + str(ticker) + '): does not appear to be shortable, disabling --short')
				stocks[ticker]['shortable'] = False

	# Find out on which exchange the ticker is listed
	# This is needed later if we want to subscribe to the level2 stream, which support NYSE and NASDAQ tickers
	# Pacific Exchange (PCX) operates through NYSEArca, so these should work as well
	#
	# Exchange codes:
	#    NYSE	 = n
	#    AMEX	 = a
	#    NASDAQ	 = q
	#    OTCBB	 = u
	#    PACIFIC	 = p
	#    INDICES	 = x
	#    AMEX_INDE	 = g
	#    MUTUAL_FUND = m
	#    PINK_SHEET	 = 9
	#    INDICATOR   = i
	try:
		stocks[ticker]['exchange'] = stock_data[ticker]['exchange']
		if ( stock_data[ticker]['exchange'] == 'q' ):
			nasdaq_tickers.append( str(ticker) )

		elif ( stock_data[ticker]['exchange'] == 'n' or stock_data[ticker]['exchange'] == 'p' ):
			nyse_tickers.append( str(ticker) )

		else:
			print('Warning: ticker ' + str(ticker) + ' not found or not listed on NYSE or NASDAQ (Exchange ID: ' + str(stock_data[ticker]['exchange']) + '), level2 data will not be available')

	except:
		print('Warning: exchange info not returned for ticker ' + str(ticker) + ', level2 data will not be available')
		pass

	# Get general information about the stock that we can use later
	# I.e. volatility, resistance, etc.
	# 3-week high / low / average
	high = low = avg = False
	count = 0
	while ( count <= 3 ):
		count += 1
		try:
			high, low, avg = tda_gobot_helper.get_price_stats(ticker, days=15)

		except Exception as e:
			print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

		if ( isinstance(high, bool) and high == False ):
			if ( count >= 3 ):
				print('Error: get_price_stats(' + str(ticker) + '): invalidating ticker')
				stocks[ticker]['isvalid'] = False
				continue

			if ( tda_gobot_helper.tdalogin(passcode, token_fname) != True ):
				print('Error: (' + str(ticker) + '): Login failure')
			time.sleep(5)

		else:
			stocks[ticker]['three_week_high'] = high
			stocks[ticker]['three_week_low'] = low
			stocks[ticker]['three_week_avg'] = avg
			break

	# 20-week high / low / average
	high = low = avg = False
	count = 0
	while ( count <= 3 ):
		count += 1
		try:
			high, low, avg = tda_gobot_helper.get_price_stats(ticker, days=100)

		except Exception as e:
			print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

		if ( isinstance(high, bool) and high == False ):
			if ( count >= 3 ):
				print('Error: get_price_stats(' + str(ticker) + '): invalidating ticker')
				stocks[ticker]['isvalid'] = False
				continue

			if ( tda_gobot_helper.tdalogin(passcode, token_fname) != True ):
				print('Error: (' + str(ticker) + '): Login failure')
			time.sleep(5)

		else:
			stocks[ticker]['twenty_week_high'] = high
			stocks[ticker]['twenty_week_low'] = low
			stocks[ticker]['twenty_week_avg'] = avg
			break

	# SMA200 and EMA50
	if ( args.short_check_ma == True ):
		try:
			sma_t = av_gobot_helper.av_get_ma(ticker, ma_type='sma', time_period=200)
			ema_t = av_gobot_helper.av_get_ma(ticker, ma_type='ema', time_period=50)

		except Exception as e:
			print('Warning: av_get_ma(' + str(ticker) + '): ' + str(e) + ', skipping sma/ema check')

		else:
			# Check SMA/EMA to see if stock is bullish or bearish
			day_t = next(reversed( sma_t['moving_avg'] )) # This returns only the key to the latest value
			stocks[ticker]['cur_sma'] = float( sma_t['moving_avg'][day_t] )

			day_t = next(reversed( ema_t['moving_avg'] ))
			stocks[ticker]['cur_ema'] = float( ema_t['moving_avg'][day_t] )

			if ( stocks[ticker]['cur_ema'] > stocks[ticker]['cur_sma'] ):
				# Stock is bullish, disable shorting
				stocks[ticker]['shortable'] = False

	time.sleep(1)

# SAZ - 2022-03-14 - Max number of tickers for listed_book_subs() and nasdaq_book_subs() is 100.
#  This is in contrast to equity OHLCV data which is 300 tickers. Unfortunately, I don't have a
#  solution for this yet and so we just need to truncate each list if either is >100.
if ( len(nyse_tickers) > 100 ):
	nyse_tickers = nyse_tickers[0:100]
if ( len(nasdaq_tickers) > 100 ):
	nasdaq_tickers = nasdaq_tickers[0:100]

# Initialize signal handlers to dump stock history on exit
def graceful_exit(signum=None, frame=None):
	print("\nNOTICE: graceful_exit(): received signal: " + str(signum))
	tda_stochrsi_gobot_helper.export_pricehistory()

	# FIXME: I don't think this actually works
	try:
		tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
		list(map(lambda task: task.cancel(), tasks))
		asyncio.get_running_loop().stop()

	except:
		pass

	os._exit(0)

# Initialize SIGUSR1 signal handler to dump stocks on signal
# Calls sell_stocks() to immediately sell or buy_to_cover any open positions
def siguser1_handler(signum=None, frame=None):
	print("\nNOTICE: siguser1_handler(): received signal")
	print("NOTICE: Calling sell_stocks() to exit open positions...\n")

	tda_stochrsi_gobot_helper.sell_stocks()
	graceful_exit(None, None)
	sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGUSR1, siguser1_handler)


# Main Loop
#
# This bot has four modes of operation -
#   Start in the 'long' mode where we are waiting for the right signal to purchase stock.
#   Then after purchasing stock we switch to the 'sell' mode where we begin searching
#   the signal to sell the stock.
#
# Ideal signal mode workflow looks like this:
#   long -> sell -> short -> buy_to_cover -> long -> ...
#
#  RSI passes from below rsi_low_limit to above = LONG
#  RSI passes from above rsi_high_limit to below = SELL and SHORT
#  RSI passes from below rsi_low_limit to above = BUY_TO_COVER and LONG

# Global variables
tda_stochrsi_gobot_helper.args					= args
tda_stochrsi_gobot_helper.algos					= algos
tda_stochrsi_gobot_helper.tx_log_dir				= args.tx_log_dir
tda_stochrsi_gobot_helper.stocks				= stocks
tda_stochrsi_gobot_helper.prev_timestamp			= 0

# StochRSI / RSI
tda_stochrsi_gobot_helper.stoch_default_low_limit		= 20
tda_stochrsi_gobot_helper.stoch_default_high_limit		= 80

tda_stochrsi_gobot_helper.stoch_signal_cancel_low_limit		= 60	# Cancel stochrsi short signal at this level
tda_stochrsi_gobot_helper.stoch_signal_cancel_high_limit	= 40	# Cancel stochrsi buy signal at this level

tda_stochrsi_gobot_helper.rsi_signal_cancel_low_limit		= 30
tda_stochrsi_gobot_helper.rsi_signal_cancel_high_limit		= 70
tda_stochrsi_gobot_helper.rsi_type				= args.rsi_type

# MFI
tda_stochrsi_gobot_helper.mfi_signal_cancel_low_limit		= 30
tda_stochrsi_gobot_helper.mfi_signal_cancel_high_limit		= 70

# Aroonosc
tda_stochrsi_gobot_helper.aroonosc_threshold			= 60
tda_stochrsi_gobot_helper.aroonosc_secondary_threshold		= args.aroonosc_secondary_threshold

# Chop Index
tda_stochrsi_gobot_helper.default_chop_low_limit		= 38.2
tda_stochrsi_gobot_helper.default_chop_high_limit		= 61.8

# Initialize pricehistory for each stock ticker
print( 'Populating pricehistory for stock tickers: ' + str(list(stocks.keys())) )

# TDA API is limited to 150 non-transactional calls per minute. It's best to sleep
#  a bit here to avoid spurious errors later.
if ( len(stocks) > 30 ):
	time.sleep(60)
else:
	time.sleep(len(stocks))

# Log in again - avoids failing later and we can call this as often as we want
if ( tda_gobot_helper.tdalogin(passcode, token_fname) != True ):
	print('Error: tdalogin(): Login failure', file=sys.stderr)

# tda.get_pricehistory() variables
p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

time_now = datetime.datetime.now( mytimezone )
time_prev = time_now - datetime.timedelta( days=8 )

# Make sure start and end dates don't land on a weekend or outside market hours
#time_now = tda_gobot_helper.fix_timestamp(time_now)	# SAZ - This needs to be commented for regular hours, uncomment when testing during the weekend
time_prev = tda_gobot_helper.fix_timestamp(time_prev)

time_now_epoch = int( time_now.timestamp() * 1000 )
time_prev_epoch = int( time_prev.timestamp() * 1000 )

for ticker in list(stocks.keys()):
	if ( stocks[ticker]['isvalid'] == False ):
		continue

	# Pull the stock history that we'll use to calculate various indicators
	extended_hours = True
	if ( re.search('^\$', ticker) != None ):
		# Disable extended hours for indicator tickers
		extended_hours = False

	data = False
	while ( isinstance(data, bool) and data == False ):
		data, epochs = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=extended_hours, debug=False)
		if ( isinstance(data, bool) and data == False ):
			time.sleep(5)
			if ( tda_gobot_helper.tdalogin(passcode, token_fname) != True ):
				print('Error: (' + str(ticker) + '): Login failure')
			continue

		else:
			stocks[ticker]['pricehistory'] = data

	if ( len(data['candles']) < int(args.stochrsi_period) * 2 ):

		# BUG: TDA's pricehistory is particularly buggy with $TRINQ for some reason.
		#  As a workaround, we'll set $TRINQ history to $TRIN, and the equity stream will
		#  eventually fill in the real-time $TRINQ data.
		if ( ticker == '$TRINQ' ):
			stocks['$TRINQ']['isvalid']		= True
			stocks['$TRINQ']['pricehistory']	= stocks['$TRIN']['pricehistory']

		else:
			print('Warning: stock(' + str(ticker) + '): len(pricehistory[candles]) is less than stochrsi_period*2 (new stock ticker?), removing from the list')
			stocks[ticker]['isvalid'] = False
			try:
				del stocks[ticker]
			except KeyError:
				print('Warning: failed to delete key "' + str(ticker) + '" from stocks{}')

			continue

	# 5-minute candles to calculate things like Average True Range
	stocks[ticker]['pricehistory_5m'] = tda_gobot_helper.translate_1m( pricehistory=stocks[ticker]['pricehistory'], candle_type=5 )

	# Translate and add Heiken Ashi candles to pricehistory (will add new array called stocks[ticker]['pricehistory']['hacandles'])
	stocks[ticker]['pricehistory'] = tda_gobot_helper.translate_heikin_ashi(stocks[ticker]['pricehistory'])

	# Skip the rest of the setup procedure for indicator tickers
	if ( re.search('^\$', ticker) != None ):
		continue

	# Key Levels
	# Use weekly_ifile or download weekly candle data
	if ( args.weekly_ifile != None ):
		import pickle

		parent_path = os.path.dirname( os.path.realpath(__file__) )
		weekly_ifile = str(parent_path) + '/' + re.sub('TICKER', ticker, args.weekly_ifile)
		print('Using ' + str(weekly_ifile))

		try:
			with open(weekly_ifile, 'rb') as handle:
				stocks[ticker]['pricehistory_weekly'] = handle.read()
				stocks[ticker]['pricehistory_weekly'] = pickle.loads(stocks[ticker]['pricehistory_weekly'])

		except Exception as e:
			print(str(e) + ', falling back to get_pricehistory().')
			stocks[ticker]['pricehistory_weekly'] = {}

	if ( stocks[ticker]['pricehistory_weekly'] == {} ):

		# Use get_pricehistory() to download weekly data
		wkly_p_type = 'year'
		wkly_period = '2'
		wkly_f_type = 'weekly'
		wkly_freq = '1'

		print('(' + str(ticker) + '): Using TDA API for weekly pricehistory...')
		while ( stocks[ticker]['pricehistory_weekly'] == {} ):
			stocks[ticker]['pricehistory_weekly'], ep = tda_gobot_helper.get_pricehistory(ticker, wkly_p_type, wkly_f_type, wkly_freq, wkly_period, needExtendedHoursData=False)

			if ( (isinstance(stocks[ticker]['pricehistory_weekly'], bool) and stocks[ticker]['pricehistory_weekly'] == False) or
					stocks[ticker]['pricehistory_weekly'] == {} or
					('empty' in stocks[ticker]['pricehistory_weekly'] and str(stocks[ticker]['pricehistory_weekly']['empty']).lower() == 'true') ):
				time.sleep(5)
				if ( tda_gobot_helper.tdalogin(passcode, token_fname) != True ):
					print('Error: (' + str(ticker) + '): Login failure')

				continue

	if ( stocks[ticker]['pricehistory_weekly'] == {} ):
		print('(' + str(ticker) + '): Warning: unable to retrieve weekly data to calculate key levels, skipping.')
		continue

	# Use daily_ifile or download daily candle data
	if ( args.daily_ifile != None ):
		import pickle

		parent_path = os.path.dirname( os.path.realpath(__file__) )
		daily_ifile = str(parent_path) + '/' + re.sub('TICKER', ticker, args.daily_ifile)
		print('Using ' + str(daily_ifile))

		try:
			with open(daily_ifile, 'rb') as handle:
				stocks[ticker]['pricehistory_daily'] = handle.read()
				stocks[ticker]['pricehistory_daily'] = pickle.loads(stocks[ticker]['pricehistory_daily'])

		except Exception as e:
			print(str(e) + ', falling back to get_pricehistory().')
			stocks[ticker]['pricehistory_daily'] = {}

	if ( stocks[ticker]['pricehistory_daily'] == {} ):

		# Use get_pricehistory() to download daily data
		daily_p_type = 'year'
		daily_period = '2'
		daily_f_type = 'daily'
		daily_freq = '1'

		print('(' + str(ticker) + '): Using TDA API for daily pricehistory...')
		while ( stocks[ticker]['pricehistory_daily'] == {} ):
			stocks[ticker]['pricehistory_daily'], ep = tda_gobot_helper.get_pricehistory(ticker, daily_p_type, daily_f_type, daily_freq, daily_period, needExtendedHoursData=False)

			if ( (isinstance(stocks[ticker]['pricehistory_daily'], bool) and stocks[ticker]['pricehistory_daily'] == False) or
					stocks[ticker]['pricehistory_daily'] == {} or
					('empty' in stocks[ticker]['pricehistory_daily'] and str(stocks[ticker]['pricehistory_daily']['empty']).lower() == 'true') ):

				time.sleep(5)
				stocks[ticker]['pricehistory_daily'] = {}
				if ( tda_gobot_helper.tdalogin(passcode, token_fname) != True ):
					print('Error: (' + str(ticker) + '): Login failure')
				continue

	if ( stocks[ticker]['pricehistory_daily'] == {} ):
		print('(' + str(ticker) + '): Warning: unable to retrieve daily data, skipping.')
		stocks[ticker]['pricehistory_daily'] = {}
		continue

	# Calculate the keylevels
	kl_long_support_full	= []
	kl_long_resistance_full	= []
	try:
		# Pull the main keylevels, filtered to reduce redundant keylevels
		stocks[ticker]['kl_long_support'], stocks[ticker]['kl_long_resistance'] = tda_algo_helper.get_keylevels(stocks[ticker]['pricehistory_weekly'], filter=True)

		# Also pull the full keylevels, and include those that have been hit more than once
		kl_long_support_full, kl_long_resistance_full = tda_algo_helper.get_keylevels(stocks[ticker]['pricehistory_weekly'], filter=False)

		kl = dt = count = 0
		for kl,dt,count in kl_long_support_full:
			if ( count > 1 and (kl, dt, count) not in stocks[ticker]['kl_long_support'] ):
				stocks[ticker]['kl_long_support'].append( (kl, dt, count) )

		for kl,dt,count in kl_long_resistance_full:
			if ( count > 1 and (kl, dt, count) not in stocks[ticker]['kl_long_resistance'] ):
				stocks[ticker]['kl_long_resistance'].append( (kl, dt, count) )

		# Populate the keylevels using daily values in case cur_algo['keylevel_use_daily'] is configured
		kl_long_support_full, kl_long_resistance_full = tda_algo_helper.get_keylevels( stocks[ticker]['pricehistory_daily'], filter=False )

		kl = dt = count = 0
		for kl,dt,count in kl_long_support_full:
			if ( count > 1 and (kl, dt, count) not in stocks[ticker]['kl_long_support'] ):
				stocks[ticker]['kl_long_support_daily'].append( (kl, dt, count) )

		for kl,dt,count in kl_long_resistance_full:
			if ( count > 1 and (kl, dt, count) not in stocks[ticker]['kl_long_resistance'] ):
				stocks[ticker]['kl_long_resistance_daily'].append( (kl, dt, count) )

	except Exception as e:
		print('Exception caught: get_keylevels(' + str(ticker) + '): ' + str(e) + '. Keylevels will not be used.')

	if ( stocks[ticker]['kl_long_support'] == False ):
		stocks[ticker]['kl_long_support']		= []
		stocks[ticker]['kl_long_resistance']		= []
		stocks[ticker]['kl_long_support_daily']		= []
		stocks[ticker]['kl_long_resistance_daily']	= []

	# End Key Levels

	# Volume Profile
	# Don't bother processing tickers like $TRIN and $TICK since they have no volume data
	if ( ticker not in nasdaq_tickers and ticker not in nyse_tickers ):
		print('INFO: get_market_profile(' + str(ticker) + '): skipping since ticker is not listed in nasdaq_tickers or nyse_tickers')

	else:
		mprofile = {}
		try:
			mprofile = tda_algo_helper.get_market_profile(pricehistory=stocks[ticker]['pricehistory'], close_type='hl2', mp_mode='vol', tick_size=0.01)

		except Exception as e:
			print('Exception caught: get_market_profile(' + str(ticker) + '): ' + str(e) + '. VAH/VAL will not be used.')

		# Get the previous day's and 2-day VAH/VAL
		prev_day_1 = list(mprofile.keys())[-2]
		prev_day_2 = list(mprofile.keys())[-3]

		if ( prev_day_1 in mprofile ):
			stocks[ticker]['vah_1']	= round( mprofile[prev_day_1]['vah'], 2 )
			stocks[ticker]['val_1']	= round( mprofile[prev_day_1]['val'], 2 )
		else:
			print('Warning: get_market_profile(' + str(ticker) + '): previous day (' + str(prev_day_1) + ') not returned in mprofile{}. VAH/VAL will not be used.')

		if ( prev_day_2 in mprofile ):
			stocks[ticker]['vah_2']	= round( mprofile[prev_day_2]['vah'], 2 )
			stocks[ticker]['val_2']	= round( mprofile[prev_day_2]['val'], 2 )
		else:
			print('Warning: get_market_profile(' + str(ticker) + '): previous 2-day (' + str(prev_day_2) + ') not returned in mprofile{}. VAH/VAL will not be used.')

	# End Volume Profile

	# Today's open + previous day high/low/close (PDH/PDL/PDC)
	cur_day_start = time_now.strftime('%Y-%m-%d')
	for key in stocks[ticker]['pricehistory']['candles']:
		tmp_t = datetime.datetime.fromtimestamp(int(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M')
		if ( tmp_t == str(cur_day_start) + ' 09:30' ):
			stocks[ticker]['today_open'] = key['open']
			break

	try:
		stocks[ticker]['previous_day_high']	= stocks[ticker]['pricehistory_daily']['candles'][-1]['high']
		stocks[ticker]['previous_day_low']	= stocks[ticker]['pricehistory_daily']['candles'][-1]['low']
		stocks[ticker]['previous_day_close']	= stocks[ticker]['pricehistory_daily']['candles'][-1]['close']

		stocks[ticker]['previous_twoday_high']	= stocks[ticker]['pricehistory_daily']['candles'][-2]['high']
		stocks[ticker]['previous_twoday_low']	= stocks[ticker]['pricehistory_daily']['candles'][-2]['low']
		stocks[ticker]['previous_twoday_close']	= stocks[ticker]['pricehistory_daily']['candles'][-2]['close']

	except Exception as e:
		print('(' + str(ticker) + '): Warning: unable to set previous day high/low/close: ' + str(e))
		stocks[ticker]['previous_day_high']	= 0
		stocks[ticker]['previous_day_low']	= 999999
		stocks[ticker]['previous_day_close']	= 0

		stocks[ticker]['previous_twoday_high']	= 0
		stocks[ticker]['previous_twoday_low']	= 999999
		stocks[ticker]['previous_twoday_close']	= 0

	# Calculate the current daily ATR/NATR
	atr_d   = []
	natr_d  = []
	try:
		atr_d, natr_d = tda_algo_helper.get_atr( pricehistory=stocks[ticker]['pricehistory_daily'], period=args.daily_atr_period )

	except Exception as e:
		print('Exception caught: date_atr(' + str(ticker) + '): ' + str(e) + '. Daily NATR resistance will not be used.')

	stocks[ticker]['atr_daily']	= float( atr_d[-1] )
	stocks[ticker]['natr_daily']	= float( natr_d[-1] )

	# Ignore days where cur_daily_natr is below min_daily_natr or above max_daily_natr, if configured.
	# However, ignore stocks that are not listed as 'tradeable' (i.e. ETF indicators).
	if ( args.min_daily_natr != None and stocks[ticker]['natr_daily'] < args.min_daily_natr ):
		if ( stocks[ticker]['tradeable'] == True ):
			print('(' + str(ticker) + ') Warning: daily NATR (' + str(round(stocks[ticker]['natr_daily'], 3)) + ') is below the min_daily_natr (' + str(args.min_daily_natr) + '), removing from the list')
			stocks[ticker]['isvalid'] = False

	if ( args.max_daily_natr != None and stocks[ticker]['natr_daily'] > args.max_daily_natr ):
		if ( stocks[ticker]['tradeable'] == True ):
			print('(' + str(ticker) + ') Warning: daily NATR (' + str(round(stocks[ticker]['natr_daily'], 3)) + ') is above the max_daily_natr (' + str(args.max_daily_natr) + '), removing from the list')
			stocks[ticker]['isvalid'] = False

	# End daily ATR/NATR

	# Daily stacked MA
	daily_ma_type	= 'wma'
	ma3		= []
	ma5		= []
	ma8		= []
	try:
		ma3 = tda_algo_helper.get_alt_ma(pricehistory=stocks[ticker]['pricehistory_daily'], ma_type=daily_ma_type, period=3 )
		ma5 = tda_algo_helper.get_alt_ma(pricehistory=stocks[ticker]['pricehistory_daily'], ma_type=daily_ma_type, period=5 )
		ma8 = tda_algo_helper.get_alt_ma(pricehistory=stocks[ticker]['pricehistory_daily'], ma_type=daily_ma_type, period=8 )

		assert not isinstance(ma3, bool)
		assert not isinstance(ma5, bool)
		assert not isinstance(ma8, bool)

	except AssertionError:
		print('Exception caught: get_alt_ma(' + str(ticker) + '): returned False, possibly a new ticker?')
	except Exception as e:
		print('Exception caught: get_alt_ma(' + str(ticker) + '): ' + str(e) + '. Daily stacked MA will not be available.')
	else:
		stocks[ticker]['cur_daily_ma'] = ( ma3[-1], ma5[-1], ma8[-1] )


# Initializes and reads from TDA stream API
async def read_stream():
	loop = asyncio.get_running_loop()
	loop.add_signal_handler( signal.SIGINT, graceful_exit )
	loop.add_signal_handler( signal.SIGTERM, graceful_exit )
	loop.add_signal_handler( signal.SIGUSR1, siguser1_handler )

	await asyncio.wait_for( stream_client.login(), 10 )

	# QOS level options:
	# EXPRESS:	500ms between updates (fastest available)
	# REAL_TIME:	750ms between updates
	# FAST:		1000ms between updates (TDA default)
	# MODERATE:	1500ms between updates
	# SLOW:		3000ms between updates
	# DELAYED:	5000ms between updates
	await stream_client.quality_of_service(stream_client.QOSLevel.MODERATE)

	# Subscribe to equity 1-minute candle data
	# Note: Max tickers=300, list will be truncated if >300
	stream_client.add_chart_equity_handler(
		lambda msg: tda_stochrsi_gobot_helper.gobot_run(msg, algos, args.debug) )
	await asyncio.wait_for( stream_client.chart_equity_subs(stocks.keys()), 10 )

	# Subscribe to equity level1 data
	# 2022-02-10 - Not needed for now since we are also grabbing L2 order book data
	l1_fields = [	stream_client.LevelOneEquityFields.SYMBOL,
			stream_client.LevelOneEquityFields.BID_PRICE,
			stream_client.LevelOneEquityFields.ASK_PRICE,
			stream_client.LevelOneEquityFields.LAST_PRICE,
			stream_client.LevelOneEquityFields.BID_SIZE,
			stream_client.LevelOneEquityFields.ASK_SIZE,
			stream_client.LevelOneEquityFields.TOTAL_VOLUME,
			stream_client.LevelOneEquityFields.LAST_SIZE,
			stream_client.LevelOneEquityFields.BID_TICK,
			stream_client.LevelOneEquityFields.SECURITY_STATUS ]
	stream_client.add_level_one_equity_handler(
		lambda msg: tda_stochrsi_gobot_helper.gobot_level1(msg, algos, args.debug) )
	await asyncio.wait_for( stream_client.level_one_equity_subs(nyse_tickers+nasdaq_tickers, fields=l1_fields), 10 )

	# Subscribe to equity level2 order books
	# NYSE ("listed")
	stream_client.add_listed_book_handler(
		lambda msg: tda_stochrsi_gobot_helper.gobot_level2(msg, args.debug) )
	await asyncio.wait_for( stream_client.listed_book_subs(nyse_tickers), 10 )

	# NASDAQ
	stream_client.add_nasdaq_book_handler(
		lambda msg: tda_stochrsi_gobot_helper.gobot_level2(msg, args.debug) )
	await asyncio.wait_for( stream_client.nasdaq_book_subs(nasdaq_tickers), 10 )

	# T&S Data
	# Note: we subscribe to nyse_tickers+nasdaq_tickers here to be sure we have valid equity tickers.
	#  Some tickers in stocks.keys(), i.e. indicators like $TICK or $TRIN, will not have time/sale data.
	stream_client.add_timesale_equity_handler(
		lambda msg: tda_stochrsi_gobot_helper.gobot_ets(msg, algos, False) )
	await asyncio.wait_for( stream_client.timesale_equity_subs(nyse_tickers+nasdaq_tickers), 10 )


	# Wait for and process messages
	while True:
		await asyncio.wait_for( stream_client.handle_message(), 120 )


# MAIN: Log into tda-api and run the stream client
# Most time is spent in read_stream() looping and processing messages from TDA. However, the
# websocket connection can be reset for a variety of reasons. So we loop here to handle any
#  exceptions in the streaming client, login again and restart the client when an error occurs.
while True:

	# Log in using the tda-api module to access the streams interface
	try:
		tda_client = tda_api.auth.client_from_token_file(tda_pickle, tda_api_key)

	except Exception as e:
		print('Exception caught: client_from_token_file(): unable to log in using tda-client: ' + str(e))
		time.sleep(2)
		continue

	# Initialize streams client
	print( 'Initializing streams client for stock tickers: ' + str(list(stocks.keys())) + "\n" )
	try:
		stream_client = StreamClient(tda_client, account_id=tda_account_number)

	except Exception as e:
		print('Exception caught: StreamClient(): ' + str(e) + ': retrying...')
		time.sleep(2)
		continue

	# Call read_stream():stream_client.handle_message() to read from the stream continuously
	try:
		asyncio.run(read_stream())

	except KeyboardInterrupt:
		sys.exit(0)

	except Exception as e:
		print('Exception caught: read_stream(): ' + str(e) + ': retrying...')


sys.exit(0)

