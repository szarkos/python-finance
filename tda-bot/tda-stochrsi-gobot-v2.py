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
parser.add_argument("--algos", help='Algorithms to use, comma delimited. Supported options: stochrsi, rsi, adx, dmi, macd, aroonosc, vwap, vpt, support_resistance (Example: --algos=stochrsi,adx --algos=stochrsi,macd)', required=True, nargs="*", action='append', type=str)
parser.add_argument("--algo_valid_tickers", help='Tickers to use with a particular algorithm (Example: --algo_valid_tickers=algo_id:MSFT,AAPL). If unset all tickers will be used for all algos. Also requires setting "algo_id:algo_name" with --algos=.', action='append', default=None, type=str)
parser.add_argument("--algo_exclude_tickers", help='Tickers to exclude with a particular algorithm (Example: --algo_exclude_tickers=algo_id:GME,AMC). If unset all tickers will be used for all algos. Also requires setting "algo_id:algo_name" with --algos=.', action='append', default=None, type=str)
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS', default='TX_LOGS', type=str)

parser.add_argument("--multiday", help='Run and monitor stock continuously across multiple days (but will not trade after hours) - see also --hold_overnight', action="store_true")
parser.add_argument("--singleday", help='Allows bot to start (but not trade) before market opens. Bot will revert to non-multiday behavior after the market opens.', action="store_true")
parser.add_argument("--unsafe", help='Allow trading between 9:30-10:15AM where volatility is high', action="store_true")
parser.add_argument("--hold_overnight", help='Hold stocks overnight when --multiday is in use (default: False) - Warning: implies --unsafe', action="store_true")

parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1, type=float)
parser.add_argument("--last_hour_threshold", help='Sell the stock if net gain is above this percentage during the final hour. Assumes --hold_overnight is False.', default=0.2, type=float)

parser.add_argument("--num_purchases", help='Number of purchases allowed per day', default=10, type=int)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("--max_failed_txs", help='Maximum number of failed transactions allowed for a given stock before stock is blacklisted', default=2, type=int)
parser.add_argument("--max_failed_usd", help='Maximum allowed USD for a failed transaction before the stock is blacklisted', default=99999, type=float)
parser.add_argument("--exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)
parser.add_argument("--variable_exit", help='Adjust incr_threshold, decr_threshold and exit_percent based on the price action of the stock over the previous hour',  action="store_true")

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

parser.add_argument("--stacked_ma_type", help='Moving average type to use (Default: sma)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods", help='List of MA periods to use, comma-delimited (Default: 8,13,21)', default='8,13,21', type=str)
parser.add_argument("--stacked_ma_type_primary", help='Moving average type to use when stacked_ma is used as primary indicator (Default: kama)', default='kama', type=str)
parser.add_argument("--stacked_ma_periods_primary", help='List of MA periods to use when stacked_ma is used as primary indicator, comma-delimited (Default: 8,13,21)', default='8,13,21', type=str)

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
parser.add_argument("--max_squeeze_natr", help='Maximum NATR allowed during consolidation (squeeze) phase (Default: None)', default=None, type=float)
parser.add_argument("--use_bbands_kchannel_5m", help='Use 5-minute candles to calculate the Bollinger bands and Keltner channel indicators (Default: False)', action="store_true")
parser.add_argument("--use_bbands_kchannel_xover_exit", help='Use price action after a Bollinger bands and Keltner channel crossover to assist with stock exit (Default: False)', action="store_true")
parser.add_argument("--bbands_kchannel_xover_exit_count", help='Number of periods to wait after a crossover to trigger --use_bbands_kchannel_xover_exit (Default: 10)', default=10, type=int)
parser.add_argument("--bbands_period", help='Period to use when calculating the Bollinger Bands (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_period", help='Period to use when calculating the Keltner channels (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_atr_period", help='Period to use when calculating the ATR for use with the Keltner channels (Default: 20)', default=20, type=int)

parser.add_argument("--check_etf_indicators", help='Tailor the stochastic indicator high/low levels based on the 5-minute SMA/EMA behavior of key ETFs (i.e. SPY, QQQ, DIA)', action="store_true")
parser.add_argument("--check_etf_indicators_strict", help='Do not allow trade unless the 5-minute SMA/EMA behavior of key ETFs (i.e. SPY, QQQ, DIA) agree with direction', action="store_true")
parser.add_argument("--etf_tickers", help='List of tickers to use with --check_etf_indicators (Default: SPY)', default='SPY', type=str)
parser.add_argument("--etf_roc_period", help='Rate of change lookback period (Default: 50)', default=50, type=int)
parser.add_argument("--etf_min_rs", help='Rate of change lookback period (Default: None)', default=None, type=float)

# Deprecated - use --algos=... instead
#parser.add_argument("--with_rsi", help='Use standard RSI as a secondary indicator', action="store_true")
#parser.add_argument("--with_adx", help='Use the Average Directional Index (ADX) as a secondary indicator', action="store_true")
#parser.add_argument("--with_dmi", help='Use the Directional Movement Index(DMI) as a secondary indicator', action="store_true")
#parser.add_argument("--with_macd", help='Use the Moving Average Convergence Divergence (MACD) as a secondary indicator', action="store_true")
#parser.add_argument("--with_aroonosc", help='Use the Aroon Oscillator as a secondary indicator', action="store_true")
#parser.add_argument("--with_vwap", help='Use VWAP as a secondary indicator', action="store_true")

parser.add_argument("--daily_ifile", help='Use pickle file for daily pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--weekly_ifile", help='Use pickle file for weekly pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--no_use_resistance", help='Do no use the high/low resistance to avoid possibly bad trades (default=False)', action="store_true")
parser.add_argument("--keylevel_strict", help='Use strict key level checks to enter trades (Default: False)', action="store_true")
parser.add_argument("--lod_hod_check", help='Enable low of the day (LOD) / high of the day (HOD) resistance checks', action="store_true")
parser.add_argument("--use_natr_resistance", help='Enable daily NATR level resistance checks', action="store_true")
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

# Safe open - ensure that we don't trade until after 10:15AM Eastern
safe_open = True
if ( args.unsafe == True ):
	safe_open = False
tda_stochrsi_gobot_helper.safe_open = safe_open

# Early exit criteria goes here
if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False and args.multiday == False and args.singleday == False ):
	print('Market is closed and --multiday or --singleday was not set, exiting')
	sys.exit(1)

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        sys.exit(1)

tda_account_number				= int( os.environ["tda_account_number"] )
passcode					= os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda				= tda
tda_stochrsi_gobot_helper.tda			= tda

tda_gobot_helper.tda_account_number		= tda_account_number
tda_stochrsi_gobot_helper.tda_account_number	= tda_account_number

tda_gobot_helper.passcode			= passcode
tda_stochrsi_gobot_helper.passcode		= passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
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
	primary_stochrsi = primary_stochmfi = primary_stacked_ma = stacked_ma = stochrsi_5m = stochmfi = stochmfi_5m = False
	rsi = mfi = adx = dmi = dmi_simple = macd = macd_simple = aroonosc = False
	chop_index = chop_simple = supertrend = bbands_kchannel = bbands_kchannel_simple = False
	vwap = vpt = support_resistance = False

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
	max_squeeze_natr		= args.max_squeeze_natr
	use_bbands_kchannel_5m		= args.use_bbands_kchannel_5m
	use_bbands_kchannel_xover_exit	= args.use_bbands_kchannel_xover_exit
	bbands_kchannel_xover_exit_count= args.bbands_kchannel_xover_exit_count
	bbands_period			= args.bbands_period
	kchannel_period			= args.kchannel_period
	kchannel_atr_period		= args.kchannel_atr_period

	check_etf_indicators		= args.check_etf_indicators
	check_etf_indicators_strict	= args.check_etf_indicators_strict
	etf_tickers			= args.etf_tickers
	etf_roc_period			= args.etf_roc_period
	etf_min_rs			= args.etf_min_rs

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

	use_natr_resistance		= args.use_natr_resistance
	min_intra_natr			= args.min_intra_natr
	max_intra_natr			= args.max_intra_natr
	min_daily_natr			= args.min_daily_natr
	max_daily_natr			= args.max_daily_natr

	for a in algo.split(','):
		a = re.sub( '[\s\t]*', '', a )

		# Algo_ID
		if ( re.match('algo_id:', a) != None ):	algo_id			= a.split(':')[1]

		# Algorithms
		if ( a == 'primary_stochrsi' ):		primary_stochrsi	= True
		if ( a == 'primary_stochmfi' ):		primary_stochmfi	= True
		if ( a == 'primary_stacked_ma' ):	primary_stacked_ma	= True
		if ( a == 'stacked_ma' ):		stacked_ma		= True
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
		if ( a == 'bbands_kchannel_simple' ):	bbands_kchannel_simple	= True
		if ( a == 'vwap' ):			vwap			= True
		if ( a == 'vpt' ):			vpt			= True
		if ( a == 'support_resistance' ):	support_resistance	= True

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
		if ( re.match('max_squeeze_natr:', a)			!= None ):	max_squeeze_natr		= float( a.split(':')[1] )
		if ( re.match('bbands_kchannel_xover_exit_count:', a)	!= None ):	bbands_kchannel_xover_exit_count= int( a.split(':')[1] )
		if ( re.match('bbands_period:', a)			!= None ):	bbands_period			= int( a.split(':')[1] )
		if ( re.match('kchannel_period:', a)			!= None ):	kchannel_period			= int( a.split(':')[1] )
		if ( re.match('kchannel_atr_period:', a)		!= None ):	kchannel_atr_period		= int( a.split(':')[1] )

		if ( re.match('check_etf_indicators', a)		!= None ):	check_etf_indicators		= True
		if ( re.match('check_etf_indicators_strict', a)		!= None ):	check_etf_indicators_strict	= True
		if ( re.match('etf_tickers:', a)			!= None ):	etf_tickers			= str( a.split(':')[1] )
		if ( re.match('etf_roc_period:', a)			!= None ):	etf_roc_period			= int( a.split(':')[1] )
		if ( re.match('etf_min_rs:', a)				!= None ):	etf_min_rs			= float( a.split(':')[1] )

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

		if ( re.match('use_natr_resistance:', a)		!= None ):	use_natr_resistance		= float( a.split(':')[1] )
		if ( re.match('min_intra_natr:', a)			!= None ):	min_intra_natr			= float( a.split(':')[1] )
		if ( re.match('max_intra_natr:', a)			!= None ):	max_intra_natr			= float( a.split(':')[1] )
		if ( re.match('min_daily_natr:', a)			!= None ):	min_daily_natr			= float( a.split(':')[1] )
		if ( re.match('max_daily_natr:', a)			!= None ):	max_daily_natr			= float( a.split(':')[1] )

	# Tweak or check the algo config
	if ( primary_stochrsi == True and primary_stochmfi == True ):
		print('Error: you can only use primary_stochrsi or primary_stochmfi, but not both. Exiting.')
		sys.exit(1)
	elif ( primary_stochrsi == False and primary_stochmfi == False and primary_stacked_ma == False ):
		print('Error: you must use one of primary_stochrsi, primary_stochmfi or primary_stacked_ma. Exiting.')
		sys.exit(1)

	if ( dmi == True and dmi_simple == True ):
		dmi_simple = False
	if ( macd == True and macd_simple == True ):
		macd_simple = False

	if ( str(use_natr_resistance).lower() == 'true' ):
		use_natr_resistance = True
	else:
		use_natr_resistance = False

	# Aroon Oscillator with MACD
	# aroonosc_with_macd_simple implies that if aroonosc is enabled, then macd_simple will be
	#   enabled or disabled based on the level of the aroon oscillator.
	if ( args.aroonosc_with_macd_simple == True and aroonosc == True ):
		if ( macd == True or macd_simple == True ):
			print('INFO: Aroonosc enabled with --aroonosc_with_macd_simple, disabling macd and macd_simple')
			macd = False
			macd_simple = False

	algo_list = {   'algo_id':				algo_id,

			'primary_stochrsi':			primary_stochrsi,
			'primary_stochmfi':			primary_stochmfi,
			'primary_stacked_ma':			primary_stacked_ma,
			'stacked_ma':				stacked_ma,
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
			'bbands_kchannel_simple':		bbands_kchannel_simple,
			'bbands_kchannel_offset':		bbands_kchannel_offset,
			'bbands_kchan_squeeze_count':		bbands_kchan_squeeze_count,
			'max_squeeze_natr':			max_squeeze_natr,
			'use_bbands_kchannel_5m':		use_bbands_kchannel_5m,
			'use_bbands_kchannel_xover_exit':	use_bbands_kchannel_xover_exit,
			'bbands_kchannel_xover_exit_count': 	bbands_kchannel_xover_exit_count,
			'bbands_period':			bbands_period,
			'kchannel_period':			kchannel_period,
			'kchannel_atr_period':			kchannel_atr_period,

			'check_etf_indicators':			check_etf_indicators,
			'check_etf_indicators_strict':		check_etf_indicators_strict,
			'etf_tickers':				etf_tickers,
			'etf_roc_period':			etf_roc_period,
			'etf_min_rs':				etf_min_rs,

			'stacked_ma_type_primary':		stacked_ma_type_primary,
			'stacked_ma_periods_primary':		stacked_ma_periods_primary,
			'stacked_ma_type':			stacked_ma_type,
			'stacked_ma_periods':			stacked_ma_periods,

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

			'use_natr_resistance':			use_natr_resistance,
			'min_intra_natr':			min_intra_natr,
			'max_intra_natr':			max_intra_natr,
			'min_daily_natr':			min_daily_natr,
			'max_daily_natr':			max_daily_natr,

			'valid_tickers':			[],
			'exclude_tickers':			[]  }

	algos.append(algo_list)

# Clean up this mess
# All the stuff above should be put into a function to avoid this cleanup stuff. I know it. It'll happen eventually.
del(primary_stochrsi,primary_stochmfi,primary_stacked_ma,stacked_ma,stochrsi_5m,stochmfi,stochmfi_5m)
del(rsi,mfi,adx,dmi,dmi_simple,macd,macd_simple,aroonosc,chop_index,chop_simple,supertrend,bbands_kchannel,bbands_kchannel_simple,vwap,vpt,support_resistance)
del(rsi_high_limit,rsi_low_limit,rsi_period,stochrsi_period,stochrsi_5m_period,rsi_k_period,rsi_k_5m_period,rsi_d_period,rsi_slow,stochrsi_offset,stochrsi_5m_offset)
del(mfi_high_limit,mfi_low_limit,mfi_period,stochmfi_period,stochmfi_5m_period,mfi_k_period,mfi_k_5m_period,mfi_d_period,mfi_slow,stochmfi_offset,stochmfi_5m_offset)
del(adx_threshold,adx_period,macd_long_period,macd_short_period,macd_signal_period,macd_offset,aroonosc_period,di_period,atr_period,vpt_sma_period)
del(chop_period,chop_low_limit,chop_high_limit,supertrend_atr_period,supertrend_min_natr,bbands_kchannel_offset,bbands_kchan_squeeze_count,bbands_period,kchannel_period,kchannel_atr_period,max_squeeze_natr)
del(stacked_ma_type_primary,stacked_ma_periods_primary,stacked_ma_type,stacked_ma_periods,use_natr_resistance,min_intra_natr,max_intra_natr,min_daily_natr,max_daily_natr)
del(use_bbands_kchannel_5m,use_bbands_kchannel_xover_exit,bbands_kchannel_xover_exit_count)
del(use_ha_exit,use_ha_candles,use_trend_exit,use_trend,trend_period,trend_type,use_combined_exit)
del(check_etf_indicators,check_etf_indicators_strict,etf_tickers,etf_roc_period,etf_min_rs)

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
			print('Caught exception: error setting algo_exclude_tickers (' + str(algo) + '), exiting.', file=sys.stderr)
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

# Initialize stocks{}
stock_list = args.stocks.split(',')
stock_list = list( dict.fromkeys(stock_list) )
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
				   'stock_qty':			int(0),
				   'num_purchases':		args.num_purchases,
				   'failed_txs':		args.max_failed_txs,
				   'failed_usd':		args.max_failed_usd,
				   'orig_base_price':		float(0),
				   'base_price':		float(0),
				   'primary_algo':		None,

				   'incr_threshold':		args.incr_threshold,
				   'orig_incr_threshold':	args.incr_threshold,
				   'decr_threshold':		args.decr_threshold,
				   'orig_decr_threshold':	args.decr_threshold,
				   'exit_percent':		args.exit_percent,

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

				   'cur_s_ma_ha_primary':	(0,0,0,0),
				   'prev_s_ma_ha_primary':	(0,0,0,0),
				   'cur_s_ma_ha':		(0,0,0,0),
				   'prev_s_ma_ha':		(0,0,0,0),

				   'cur_daily_ma':		(0,0,0,0),

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

				   'kl_long_support':		[],
				   'kl_long_resistance':	[],

				   # SMA200 and EMA50
				   'cur_sma':			None,
				   'cur_ema':			None,

				   # Rate of Change (ROC)
				   'cur_roc':			float(0),

				   # Per-algo indicator signals
				   'algo_signals':		{},

				   'prev_timestamp':		0,
				   'cur_seq':			0,
				   'prev_seq':			0,

				   # Candle data
				   'pricehistory':		{},
				   'pricehistory_5m':		{ 'candles': [], 'ticker': ticker },
				   'pricehistory_daily':	{},
				   'pricehistory_weekly':	{},
			}} )

	# Per algo signals
	for algo in algos:
		signals = { algo['algo_id']: {	'signal_mode':				'buy',

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
						'bbands_kchan_init_signal':		False,
						'bbands_kchan_crossover_signal':	False,
						'bbands_kchan_signal':			False,
						'bbands_kchan_signal_counter':		0,
						'bbands_kchan_xover_counter':		0,

						# Relative Strength
						'rs_signal':				False,

						'plus_di_crossover':			False,
						'minus_di_crossover':			False,
						'macd_crossover':			False,
						'macd_avg_crossover':			False }}

		stocks[ticker]['algo_signals'].update( signals )

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	sys.exit(1)


# If check_etf_indicators is enabled then make sure the ETF stocks are listed in the global stocks{} dict
#  and are configured as not tradeable.
if ( args.check_etf_indicators == True ):
	for ticker in args.etf_tickers.split(','):
		if ( ticker not in stocks ):
			print('Error: check_etf_indicators is enabled, however ticker "' + str(ticker) + '" does not appear to be configured in global stocks{} dictionary, exiting.')
			sys.exit(1)

		stocks[ticker]['tradeable'] = False


# Get stock_data info about the stock that we can use later (i.e. shortable)
try:
	stock_data = tda_gobot_helper.get_quotes(stock_list)

except Exception as e:
	print('Caught exception: tda_gobot_helper.get_quote(' + str(stock_list) + '): ' + str(e), file=sys.stderr)
	sys.exit(1)

# Initialize additional stocks{} values
# First purge the blacklist of stale entries
tda_gobot_helper.clean_blacklist(debug=False)
for ticker in list(stocks.keys()):
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

	# Get general information about the stock that we can use later
	# I.e. volatility, resistance, etc.
	# 3-week high / low / average
	high = low = avg = False
	while ( high == False ):
		try:
			high, low, avg = tda_gobot_helper.get_price_stats(ticker, days=15)

		except Exception as e:
			print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

		if ( isinstance(high, bool) and high == False ):
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
				print('Error: (' + str(ticker) + '): Login failure')
			time.sleep(5)

		else:
			stocks[ticker]['three_week_high'] = high
			stocks[ticker]['three_week_low'] = low
			stocks[ticker]['three_week_avg'] = avg
			break

	# 20-week high / low / average
	high = low = avg = False
	while ( high == False ):
		try:
			high, low, avg = tda_gobot_helper.get_price_stats(ticker, days=100)

		except Exception as e:
			print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

		if ( isinstance(high, bool) and high == False ):
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
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


# Initialize signal handlers to dump stock history on exit
def graceful_exit(signum=None, frame=None):
	print("\nNOTICE: graceful_exit(): received signal: " + str(signum))
	tda_stochrsi_gobot_helper.export_pricehistory()

	try:
		tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
		list(map(lambda task: task.cancel(), tasks))
		asyncio.get_running_loop().stop()

	except:
		pass

	sys.exit(0)

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
#   Start in the 'buy' mode where we are waiting for the right signal to purchase stock.
#   Then after purchasing stock we switch to the 'sell' mode where we begin searching
#   the signal to sell the stock.
#
# Ideal signal mode workflow looks like this:
#   buy -> sell -> short -> buy_to_cover -> buy -> ...
#
#  RSI passes from below rsi_low_limit to above = BUY
#  RSI passes from above rsi_high_limit to below = SELL and SHORT
#  RSI passes from below rsi_low_limit to above = BUY_TO_COVER and BUY

# Global variables
tda_stochrsi_gobot_helper.args					= args
tda_stochrsi_gobot_helper.algos					= algos
tda_stochrsi_gobot_helper.tx_log_dir				= args.tx_log_dir
tda_stochrsi_gobot_helper.stocks				= stocks
tda_stochrsi_gobot_helper.stock_usd				= args.stock_usd
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

# Support / Resistance
tda_stochrsi_gobot_helper.price_resistance_pct			= 1
tda_stochrsi_gobot_helper.price_support_pct			= 1

# Initialize pricehistory for each stock ticker
print( 'Populating pricehistory for stock tickers: ' + str(list(stocks.keys())) )

# TDA API is limited to 150 non-transactional calls per minute. It's best to sleep
#  a bit here to avoid spurious errors later.
if ( len(stocks) > 30 ):
	time.sleep(60)
else:
	time.sleep(len(stocks))

# Log in again - avoids failing later and we can call this as often as we want
if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: tdalogin(): Login failure', file=sys.stderr)

# tda.get_pricehistory() variables
p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

time_now = datetime.datetime.now( mytimezone )
time_prev = time_now - datetime.timedelta( days=8 )

# Make sure start and end dates don't land on a weekend or outside market hours
#time_now = tda_gobot_helper.fix_timestamp(time_now)
time_prev = tda_gobot_helper.fix_timestamp(time_prev)

time_now_epoch = int( time_now.timestamp() * 1000 )
time_prev_epoch = int( time_prev.timestamp() * 1000 )

for ticker in list(stocks.keys()):
	if ( stocks[ticker]['isvalid'] == False ):
		continue

	# Pull the stock history that we'll use to calculate the Stochastic RSI and other thingies
	data = False
	while ( isinstance(data, bool) and data == False ):
		data, epochs = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=True, debug=False)
		if ( isinstance(data, bool) and data == False ):
			time.sleep(5)
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
				print('Error: (' + str(ticker) + '): Login failure')
			continue

		else:
			stocks[ticker]['pricehistory'] = data

	if ( len(data['candles']) < int(args.stochrsi_period) * 2 ):
		print('Warning: stock(' + str(ticker) + '): len(pricehistory[candles]) is less than stochrsi_period*2 (new stock ticker?), removing from the list')
		stocks[ticker]['isvalid'] = False

		try:
			del stocks[ticker]
		except KeyError:
			print('Warning: failed to delete key "' + str(ticker) + '" from stocks{}')

		continue

	# 5-minute candles to calculate things like Average True Range
	for idx,key in enumerate( stocks[ticker]['pricehistory']['candles'] ):
		if ( idx == 0 ):
			continue

		cndl_num = idx + 1
		if ( cndl_num % 5 == 0 ):
			open_p	= float( stocks[ticker]['pricehistory']['candles'][idx - 4]['open'] )
			close	= float( stocks[ticker]['pricehistory']['candles'][idx]['close'] )
			high	= 0
			low	= 9999
			volume	= 0

			for i in range( 4, 0, -1):
				volume += stocks[ticker]['pricehistory']['candles'][idx-i]['volume']

				if ( high < stocks[ticker]['pricehistory']['candles'][idx-i]['high'] ):
					high = stocks[ticker]['pricehistory']['candles'][idx-i]['high']
				if ( low > stocks[ticker]['pricehistory']['candles'][idx-i]['low'] ):
					low = stocks[ticker]['pricehistory']['candles'][idx-i]['low']

			newcandle = {	'open':		open_p,
					'high':		high,
					'low':		low,
					'close':	close,
					'volume':	volume,
					'datetime':	stocks[ticker]['pricehistory']['candles'][idx]['datetime'] }

			stocks[ticker]['pricehistory_5m']['candles'].append(newcandle)

	del(open_p, high, low, close, volume, newcandle)

	# Translate and add Heiken Ashi candles to pricehistory (will add new array called stocks[ticker]['pricehistory']['hacandles'])
	stocks[ticker]['pricehistory'] = tda_gobot_helper.translate_heikin_ashi(stocks[ticker]['pricehistory'])

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

		while ( stocks[ticker]['pricehistory_weekly'] == {} ):
			stocks[ticker]['pricehistory_weekly'], ep = tda_gobot_helper.get_pricehistory(ticker, wkly_p_type, wkly_f_type, wkly_freq, wkly_period, needExtendedHoursData=False)

			if ( stocks[ticker]['pricehistory_weekly'] == {} or
					('empty' in stocks[ticker]['pricehistory_weekly'] and str(stocks[ticker]['pricehistory_weekly']['empty']).lower() == 'true') ):
				time.sleep(5)
				if ( tda_gobot_helper.tdalogin(passcode) != True ):
					print('Error: (' + str(ticker) + '): Login failure')

				continue

	if ( stocks[ticker]['pricehistory_weekly'] == {} ):
		print('(' + str(ticker) + '): Warning: unable to retrieve weekly data to calculate key levels, skipping.')
		continue

	# Calculate the keylevels
	try:
		stocks[ticker]['kl_long_support'], stocks[ticker]['kl_long_resistance'] = tda_algo_helper.get_keylevels(stocks[ticker]['pricehistory_weekly'], filter=False)

	except Exception as e:
		print('Exception caught: get_keylevels(' + str(ticker) + '): ' + str(e) + '. Keylevels will not be used.')

	if ( stocks[ticker]['kl_long_support'] == False ):
		stocks[ticker]['kl_long_support'] = []
		stocks[ticker]['kl_long_resistance'] = []

	time.sleep(1)
	# End Key Levels

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
				if ( tda_gobot_helper.tdalogin(passcode) != True ):
					print('Error: (' + str(ticker) + '): Login failure')
				continue

	if ( stocks[ticker]['pricehistory_daily'] == {} ):
		print('(' + str(ticker) + '): Warning: unable to retrieve daily data, skipping.')
		stocks[ticker]['pricehistory_daily'] = {}
		continue

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

	except Exception as e:
		print('(' + str(ticker) + '): Warning: unable to set previous day high/low/close: ' + str(e))
		stocks[ticker]['previous_day_high']	= 0
		stocks[ticker]['previous_day_low']	= 999999
		stocks[ticker]['previous_day_close']	= 0

	# Calculate the current daily ATR/NATR
	atr_d   = []
	natr_d  = []
	try:
		atr_d, natr_d = tda_algo_helper.get_atr( pricehistory=stocks[ticker]['pricehistory_daily'], period=args.daily_atr_period )

	except Exception as e:
		print('Exception caught: date_atr(' + str(ticker) + '): ' + str(e) + '. Daily NATR resistance will not be used.')

	stocks[ticker]['atr_daily']	= float( atr_d[-1] )
	stocks[ticker]['natr_daily']	= float( natr_d[-1] )

	# Ignore days where cur_daily_natr is below min_daily_natr or above max_daily_natr, if configured
	if ( args.min_daily_natr != None and stocks[ticker]['natr_daily'] < args.min_daily_natr ):
		print('(' + str(ticker) + ') Warning: daily NATR (' + str(round(stocks[ticker]['natr_daily'], 3)) + ') is below the min_daily_natr (' + str(args.min_daily_natr) + '), removing from the list')
		stocks[ticker]['isvalid'] = False

	if ( args.max_daily_natr != None and stocks[ticker]['natr_daily'] > args.max_daily_natr ):
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


# MAIN: Log into tda-api and run the stream client
tda_api_key	= os.environ['tda_consumer_key']
tda_pickle	= os.environ['HOME'] + '/.tokens/tda2.pickle'

# Initializes and reads from TDA stream API
async def read_stream():
	loop = asyncio.get_running_loop()
	loop.add_signal_handler( signal.SIGINT, graceful_exit )
	loop.add_signal_handler( signal.SIGTERM, graceful_exit )
	loop.add_signal_handler( signal.SIGUSR1, siguser1_handler )

	await asyncio.wait_for( stream_client.login(), 10 )
	await stream_client.quality_of_service(StreamClient.QOSLevel.REAL_TIME)

	stream_client.add_chart_equity_handler(
		lambda msg: tda_stochrsi_gobot_helper.stochrsi_gobot_run(msg, algos, args.debug) )

	# Max equity subs=300
	await asyncio.wait_for( stream_client.chart_equity_subs(stocks.keys()), 10 )

	while True:
		await asyncio.wait_for( stream_client.handle_message(), 120 )


# MAIN
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
