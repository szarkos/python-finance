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
from collections import OrderedDict
import argparse

# We use robin_stocks for most REST operations
import robin_stocks.tda as tda
import tda_gobot_helper
import tda_stochrsi_gobot_helper
import av_gobot_helper

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
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS', default='TX_LOGS', type=str)

parser.add_argument("--multiday", help='Run and monitor stock continuously across multiple days (but will not trade after hours) - see also --hold_overnight', action="store_true")
parser.add_argument("--singleday", help='Allows bot to start (but not trade) before market opens. Bot will revert to non-multiday behavior after the market opens.', action="store_true")
parser.add_argument("--unsafe", help='Allow trading between 9:30-10:15AM where volatility is high', action="store_true")
parser.add_argument("--hold_overnight", help='Hold stocks overnight when --multiday is in use (default: False) - Warning: implies --unsafe', action="store_true")
parser.add_argument("--no_use_resistance", help='Do no use the high/low resistance to avoid possibly bad trades (default=False)', action="store_true")
parser.add_argument("--lod_hod_check", help='Enable low of the day (LOD) / high of the day (HOD) resistance checks', action="store_true")

parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1, type=float)
parser.add_argument("--last_hour_threshold", help='Sell the stock if net gain is above this percentage during the final hour. Assumes --hold_overnight is False.', default=0.2, type=float)

parser.add_argument("--num_purchases", help='Number of purchases allowed per day', default=10, type=int)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("--max_failed_txs", help='Maximum number of failed transactions allowed for a given stock before stock is blacklisted', default=2, type=int)
parser.add_argument("--max_failed_usd", help='Maximum allowed USD for a failed transaction before the stock is blacklisted', default=100, type=int)
parser.add_argument("--exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)
parser.add_argument("--vwap_exit", help='Use vwap exit strategy - sell/close at half way between entry point and vwap', action="store_true")
parser.add_argument("--variable_exit", help='Adjust incr_threshold, decr_threshold and exit_percent based on the price action of the stock over the previous hour',  action="store_true")

parser.add_argument("--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_k_period", help='k period to use in StochRSI algorithm', default=128, type=int)
parser.add_argument("--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--stochrsi_period", help='RSI period to use for stochastic RSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='hlc3', type=str)
parser.add_argument("--rsi_high_limit", help='RSI high limit', default=80, type=int)
parser.add_argument("--rsi_low_limit", help='RSI low limit', default=20, type=int)
parser.add_argument("--vpt_sma_period", help='SMA period for VPT signal line', default=72, type=int)
parser.add_argument("--adx_period", help='ADX period', default=92, type=int)
parser.add_argument("--di_period", help='Plus/Minus DI period', default=48, type=int)
parser.add_argument("--aroonosc_period", help='Aroon Oscillator period', default=24, type=int)
parser.add_argument("--atr_period", help='Average True Range period', default=14, type=int)
parser.add_argument("--mfi_period", help='Money Flow Index (MFI) period', default=14, type=int)
parser.add_argument("--mfi_high_limit", help='MFI high limit', default=80, type=int)
parser.add_argument("--mfi_low_limit", help='MFI low limit', default=20, type=int)
parser.add_argument("--period_multiplier", help='Period multiplier - set statically here, or otherwise gobot will determine based on the number of candles it receives per minute.', default=0, type=int)

parser.add_argument("--aroonosc_with_macd_simple", help='When using Aroon Oscillator, use macd_simple as tertiary indicator if AroonOsc is less than +/- 72 (Default: False)', action="store_true")
parser.add_argument("--aroonosc_secondary_threshold", help='AroonOsc threshold for when to enable macd_simple when --aroonosc_with_macd_simple is enabled (Default: 72)', default=72, type=float)
parser.add_argument("--adx_threshold", help='ADX threshold for when to trigger the ADX signal (Default: 25)', default=25, type=float)

# Deprecated - use --algos=... instead
#parser.add_argument("--with_rsi", help='Use standard RSI as a secondary indicator', action="store_true")
#parser.add_argument("--with_adx", help='Use the Average Directional Index (ADX) as a secondary indicator', action="store_true")
#parser.add_argument("--with_dmi", help='Use the Directional Movement Index(DMI) as a secondary indicator', action="store_true")
#parser.add_argument("--with_macd", help='Use the Moving Average Convergence Divergence (MACD) as a secondary indicator', action="store_true")
#parser.add_argument("--with_aroonosc", help='Use the Aroon Oscillator as a secondary indicator', action="store_true")
#parser.add_argument("--with_vwap", help='Use VWAP as a secondary indicator', action="store_true")

parser.add_argument("--weekly_ifile", help='Use pickle file for weekly pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--keylevel_strict", help='Use strict key level checks to enter trades (Default: False)', action="store_true")

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

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda = tda
tda_stochrsi_gobot_helper.tda = tda

tda_gobot_helper.tda_account_number = tda_account_number
tda_stochrsi_gobot_helper.tda_account_number = tda_account_number

tda_gobot_helper.passcode = passcode
tda_stochrsi_gobot_helper.passcode = passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure', file=sys.stderr)
	sys.exit(1)

# Initialize algos[]
#
# args.algos = [[algo1,algo2], [...]]
#
# algos = [ {'stochrsi':		True,  # For now this cannot be turned off
#	   'rsi':			False,
#	   'mfi':			False,
#	   'adx':			False,
#	   'dmi':			False,
#	   'dmi_simple':		False,
#	   'macd':			False,
#	   'macd_simple':		False,
#	   'aroonosc':			False,
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

	# Generate a random unique algo_id
	while True:
		algo_id = random.randint(1000, 9999)
		if 'algo_'+str(algo_id) in algo_ids:
			continue
		else:
			algo_ids.append('algo_' + str(algo_id))
			break

	# Indicators
	stochrsi = rsi = mfi = adx = dmi = dmi_simple = macd = macd_simple = aroonosc = vwap = vpt = support_resistance = False

	# Indicator modifiers
	rsi_high_limit	= args.rsi_high_limit
	rsi_low_limit	= args.rsi_low_limit
	rsi_k_period	= args.rsi_k_period
	rsi_d_period	= args.rsi_d_period
	rsi_slow	= args.rsi_slow
	rsi_period	= args.rsi_period

	mfi_high_limit	= args.mfi_high_limit
	mfi_low_limit	= args.mfi_low_limit
	mfi_period	= args.mfi_period

	adx_threshold	= args.adx_threshold
	adx_period	= args.adx_period

	aroonosc_period	= args.aroonosc_period
	di_period	= args.di_period

	atr_period	= args.atr_period
	vpt_sma_period	= args.vpt_sma_period

	for a in algo.split(','):

		if ( a == 'stochrsi' ):		stochrsi	= True
		if ( a == 'rsi' ):		rsi		= True
		if ( a == 'mfi' ):		mfi		= True
		if ( a == 'adx' ):		adx		= True
		if ( a == 'dmi' ):		dmi		= True
		if ( a == 'dmi_simple' ):	dmi_simple	= True
		if ( a == 'macd' ):		macd		= True
		if ( a == 'macd_simple' ):	macd_simple	= True
		if ( a == 'aroonosc' ):		aroonosc	= True
		if ( a == 'vwap' ):		vwap		= True
		if ( a == 'vpt' ):		vpt		= True
		if ( a == 'support_resistance' ): support_resistance = True

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

		# Modifiers
		if ( re.match('rsi_high_limit:', a)	!= None ):	rsi_high_limit	= int( a.split(':')[1] )

		if ( re.match('rsi_low_limit:', a)	!= None ):	rsi_low_limit	= int( a.split(':')[1] )
		if ( re.match('rsi_k_period:', a)	!= None ):	rsi_k_period	= int( a.split(':')[1] )
		if ( re.match('rsi_d_period:', a)	!= None ):	rsi_d_period	= int( a.split(':')[1] )
		if ( re.match('rsi_slow:', a)		!= None ):	rsi_slow	= int( a.split(':')[1] )
		if ( re.match('rsi_period:', a)		!= None ):	rsi_period	= int( a.split(':')[1] )

		if ( re.match('mfi_high_limit:', a)	!= None ):	mfi_high_limit	= int( a.split(':')[1] )
		if ( re.match('mfi_low_limit:', a)	!= None ):	mfi_low_limit	= int( a.split(':')[1] )
		if ( re.match('mfi_period:', a)		!= None ):	mfi_period	= int( a.split(':')[1] )

		if ( re.match('adx_threshold:', a)	!= None ):	adx_threshold	= int( a.split(':')[1] )
		if ( re.match('adx_period:', a)		!= None ):	adx_period	= int( a.split(':')[1] )
		if ( re.match('aroonosc_period:', a)	!= None ):	aroonosc_period	= int( a.split(':')[1] )
		if ( re.match('di_period:', a)		!= None ):	di_period	= int( a.split(':')[1] )
		if ( re.match('atr_period:', a)		!= None ):	atr_period	= int( a.split(':')[1] )
		if ( re.match('vpt_sma_period:', a)	!= None ):	vpt_sma_period	= int( a.split(':')[1] )

	algo_list = {   'algo_id':		algo_id,

			'stochrsi':		True,  # For now this cannot be turned off
			'rsi':			rsi,
			'mfi':			mfi,
			'adx':			adx,
			'dmi':			dmi,
			'dmi_simple':		dmi_simple,
			'macd':			macd,
			'macd_simple':		macd_simple,
			'aroonosc':		aroonosc,
			'vwap':			vwap,
			'vpt':			vpt,
			'support_resistance':	support_resistance,

			# Algo modifiers
			'rsi_high_limit':	rsi_high_limit,
			'rsi_low_limit':	rsi_low_limit,
			'rsi_k_period':		rsi_k_period,
			'rsi_d_period':		rsi_d_period,
			'rsi_slow':		rsi_slow,
			'rsi_period':		rsi_period,
			'mfi_high_limit':	mfi_high_limit,
			'mfi_low_limit':	mfi_low_limit,
			'mfi_period':		mfi_period,
			'adx_threshold':	adx_threshold,
			'adx_period':		adx_period,
			'aroonosc_period':	aroonosc_period,
			'di_period':		di_period,
			'atr_period':		atr_period,
			'vpt_sma_period':	vpt_sma_period }

	algos.append(algo_list)

del(stochrsi,rsi,adx,dmi,macd,aroonosc,vwap,vpt,support_resistance)
del(rsi_high_limit,rsi_low_limit,rsi_k_period,rsi_d_period,rsi_slow,rsi_period,mfi_high_limit,mfi_low_limit,mfi_period,adx_threshold,adx_period,aroonosc_period,di_period,atr_period,vpt_sma_period)
print()


# Initialize stocks{}
print( 'Initializing stock tickers: ' + str(args.stocks.split(',')) )

# Fix up and sanity check the stock symbol before proceeding
args.stocks = tda_gobot_helper.fix_stock_symbol(args.stocks)
args.stocks = tda_gobot_helper.check_stock_symbol(args.stocks)
if ( isinstance(args.stocks, bool) and args.stocks == False ):
	print('Error: check_stock_symbol(' + str(args.stocks) + ') returned False, exiting.')
	exit(1)

time.sleep(2)

stocks = OrderedDict()
for ticker in args.stocks.split(','):

	if ( ticker == '' ):
		continue

	stocks.update( { ticker: { 'shortable':			True,
				   'isvalid':			True,
				   'tx_id':			random.randint(1000, 9999),
				   'stock_qty':			int(0),
				   'num_purchases':		int(args.num_purchases),
				   'failed_txs':		int(args.max_failed_txs),
				   'orig_base_price':		float(0),
				   'base_price':		float(0),

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

				   'signal_mode':		'buy',

				   # Indicator variables
				   # StochRSI
				   'cur_rsi_k':			float(-1),
				   'prev_rsi_k':		float(-1),
				   'cur_rsi_d':			float(-1),
				   'prev_rsi_d':		float(-1),

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

				   # VWAP
				   'cur_vwap':			float(-1),
				   'cur_vwap_up':		float(-1),
				   'cur_vwap_down':		float(-1),

				   # VPT
				   'cur_vpt':			float(-1),
				   'prev_vpt':			float(-1),
				   'cur_vpt_sma':		float(-1),
				   'prev_vpt_sma':		float(-1),

				   # ATR
				   'cur_atr':			float(-1),
				   'cur_natr':			float(-1),

				   # Support / Resistance
				   'three_week_high':		float(0),
				   'three_week_low':		float(0),
				   'three_week_avg':		float(0),
				   'twenty_week_high':		float(0),
				   'twenty_week_low':		float(0),
				   'twenty_week_avg':		float(0),

				   'previous_day_close':	None,

				   'kl_long_support':		[],
				   'kl_long_resistance':	[],

				   # SMA200 and EMA50
				   'cur_sma':			None,
				   'cur_ema':			None,

				   # Per-algo indicator signals
				   'algo_signals':		{},

				   # Period log will log datetime to determine period_multiplier
				   'period_log':		[],
				   'period_multiplier':		args.period_multiplier,
				   'prev_timestamp':		0,
				   'prev_seq':			0,

				   # Candle data
				   'pricehistory':		{},
				   'pricehistory_5m':		{ 'candles': [], 'ticker': ticker }
			}} )

	# Start in 'buy' mode unless we're only shorting
	if ( args.shortonly == True ):
		stocks[ticker]['signal_mode'] = 'short'

	# Per algo signals
	for algo in algos:
		signals = { algo['algo_id']: {	'buy_signal':			False,
						'sell_signal':			False,
						'short_signal':			False,
						'buy_to_cover_signal':		False,

						# Indicator signals
						'rsi_signal':			False,
						'mfi_signal':			False,
						'adx_signal':			False,
						'dmi_signal':			False,
						'macd_signal':			False,
						'aroonosc_signal':		False,
						'vwap_signal':			False,
						'vpt_signal':			False,
						'resistance_signal':		False,

						'plus_di_crossover':		False,
						'minus_di_crossover':		False,
						'macd_crossover':		False,
						'macd_avg_crossover':		False }}

		stocks[ticker]['algo_signals'].update( signals )

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	sys.exit(1)

# Get stock_data info about the stock that we can use later (i.e. shortable)
try:
	stock_data = tda_gobot_helper.get_quotes(args.stocks)

except Exception as e:
	print('Caught exception: tda_gobot_helper.get_quote(' + str(args.stocks) + '): ' + str(e), file=sys.stderr)
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
	sys.exit(0)

# Initialize SIGUSR1 signal handler to dump stocks on signal
# Calls sell_stocks() to immediately sell or buy_to_cover any open positions
def siguser1_handler(signum=None, frame=None):
	print("\nNOTICE: siguser1_handler(): received signal")
	print("NOTICE: Calling sell_stocks() to exit open positions...\n")

	tda_stochrsi_gobot_helper.sell_stocks()
	graceful_exit(None, None)
	sys.exit(0)

#signal.signal(signal.SIGINT, graceful_exit)
#signal.signal(signal.SIGTERM, graceful_exit)
#signal.signal(signal.SIGUSR1, siguser1_handler)


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
tda_stochrsi_gobot_helper.args = args
tda_stochrsi_gobot_helper.algos = algos
tda_stochrsi_gobot_helper.tx_log_dir = args.tx_log_dir
tda_stochrsi_gobot_helper.stocks = stocks
tda_stochrsi_gobot_helper.stock_usd = args.stock_usd
tda_stochrsi_gobot_helper.prev_timestamp = 0

# StochRSI / RSI
tda_stochrsi_gobot_helper.stochrsi_signal_cancel_low_limit = 20
tda_stochrsi_gobot_helper.stochrsi_signal_cancel_high_limit = 80
tda_stochrsi_gobot_helper.rsi_signal_cancel_low_limit = 30
tda_stochrsi_gobot_helper.rsi_signal_cancel_high_limit = 70
tda_stochrsi_gobot_helper.rsi_type = args.rsi_type

# MFI
tda_stochrsi_gobot_helper.mfi_signal_cancel_low_limit = 30
tda_stochrsi_gobot_helper.mfi_signal_cancel_high_limit = 70

# MACD
tda_stochrsi_gobot_helper.macd_short_period = 48
tda_stochrsi_gobot_helper.macd_long_period = 104
tda_stochrsi_gobot_helper.macd_signal_period = 36
tda_stochrsi_gobot_helper.macd_offset = 0.006

# Aroonosc
tda_stochrsi_gobot_helper.aroonosc_threshold = 60
tda_stochrsi_gobot_helper.aroonosc_secondary_threshold = args.aroonosc_secondary_threshold

# Support / Resistance
tda_stochrsi_gobot_helper.price_resistance_pct = 1
tda_stochrsi_gobot_helper.price_support_pct = 1

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
time_now = tda_gobot_helper.fix_timestamp(time_now)
time_prev = tda_gobot_helper.fix_timestamp(time_prev)

time_now_epoch = int( time_now.timestamp() * 1000 )
time_prev_epoch = int( time_prev.timestamp() * 1000 )

for ticker in list(stocks.keys()):
	if ( stocks[ticker]['isvalid'] == False ):
		continue

	# Pull the stock history that we'll use to calculate the Stochastic RSI
	data = False
	while ( data == False ):
		data, epochs = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=True, debug=False)
		if ( data == False ):
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

	# Populate the period_log with history data
	#  and find PDC
	yesterday = time_now - datetime.timedelta(days=1)
	yesterday = tda_gobot_helper.fix_timestamp(yesterday)
	yesterday = yesterday.strftime('%Y-%m-%d')
	for key in data['candles']:

		stocks[ticker]['period_log'].append( key['datetime'] )

		# PDC
		day = datetime.datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone)
		if ( day.strftime('%Y-%m-%d') == yesterday ):

			# Sometimes low/zero EOD volume misses a candle, try a couple EOD candles to be safe
			hm = day.strftime('%H:%M')
			if ( hm == '15:59' or hm == '16:00' ):
				stocks[ticker]['previous_day_close'] = float( key['close'] )

	if ( stocks[ticker]['previous_day_close'] == None ):
		print('Warning: (' + str(ticker) + '): failed to find PDC from pricehistory, falling back to get_pdc()')

		tries = 0
		while ( tries < 3 ):
			stocks[ticker]['previous_day_close'] = tda_gobot_helper.get_pdc(data)
			if ( stocks[ticker]['previous_day_close'] == None ):
				print('Error: (' + str(ticker) + '): get_pdc() returned None, retrying...')
				stocks[ticker]['previous_day_close'] = 0
				tries += 1

				time.sleep(5)
				continue
			break

	# Key Levels
	# Use weekly_ifile or download weekly candle data
	weekly_ph = False
	if ( args.weekly_ifile != None ):
		import pickle

		parent_path = os.path.dirname( os.path.realpath(__file__) )
		weekly_ifile = str(parent_path) + '/' + re.sub('TICKER', ticker, args.weekly_ifile)
		print('Using ' + str(weekly_ifile))

		try:
			with open(weekly_ifile, 'rb') as handle:
				weekly_ph = handle.read()
				weekly_ph = pickle.loads(weekly_ph)

		except Exception as e:
			print('Exception caught, error opening file ' + str(weekly_ifile) + ': ' + str(e) + '. Falling back to get_pricehistory().')

	if ( weekly_ph == False):

		# Use get_pricehistory() to download weekly data
		wkly_p_type = 'year'
		wkly_period = '2'
		wkly_f_type = 'weekly'
		wkly_freq = '1'

		while ( weekly_ph == False ):
			weekly_ph, ep = tda_gobot_helper.get_pricehistory(ticker, wkly_p_type, wkly_f_type, wkly_freq, wkly_period, needExtendedHoursData=False)

			if ( weekly_ph == False ):
				time.sleep(5)
				if ( tda_gobot_helper.tdalogin(passcode) != True ):
					print('Error: (' + str(ticker) + '): Login failure')

				continue

	if ( weekly_ph == False ):
		print('(' + str(ticker) + '): Warning: unable to retrieve weekly data to calculate key levels, skipping.')
		continue

	# Calculate the keylevels
	try:
		stocks[ticker]['kl_long_support'], stocks[ticker]['kl_long_resistance'] = tda_gobot_helper.get_keylevels(weekly_ph, filter=False)

	except Exception as e:
		print('Exception caught: get_keylevels(' + str(ticker) + '): ' + str(e) + '. Keylevels will not be used.')

	if ( stocks[ticker]['kl_long_support'] == False ):
		stocks[ticker]['kl_long_support'] = []
		stocks[ticker]['kl_long_resistance'] = []

	# End Key Levels

	time.sleep(1)


# MAIN: Log into tda-api and run the stream client
tda_api_key = os.environ['tda_consumer_key']
tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'

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
	print( 'Initializing streams client for stock tickers: ' + str(list(stocks.keys())) )
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
		graceful_exit(None, None)
		sys.exit(0)

	except Exception as e:
		print('Exception caught: read_stream(): ' + str(e) + ': retrying...')


sys.exit(0)
