#!/usr/bin/python3 -u

# Monitor a stock's Stochastic RSI values and make purchase decisions based off those values.
# Examples:
#  ./tda-rsi-gobot.py --short --multiday --stoploss --num_purchases=20 \
#			MSFT  1000

import os, sys, signal
import time, datetime, pytz, random
from collections import OrderedDict
import argparse

# We use robin_stocks for most REST operations
import robin_stocks.tda as tda
import tda_gobot_helper
import tda_stochrsi_gobot_helper

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
parser.add_argument("--stocks", help='Stock ticker(s) to purchase (comma delimited)', required=True, type=str)
parser.add_argument("--stock_usd", help='Amount of money (USD) to invest per trade', default=1000, type=float)
parser.add_argument("--algos", help='Algorithms to use, comma delimited. Supported options: stochrsi, rsi, adx, dmi, macd, aroonosc, vwap, vpt, support_resistance (Example: --algos=stochrsi,adx --algos=stochrsi,macd)', required=True, nargs="*", action='append', type=str)
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS', default='TX_LOGS', type=str)

parser.add_argument("--multiday", help='Run and monitor stock continuously across multiple days (but will not trade after hours) - see also --hold_overnight', action="store_true")
parser.add_argument("--singleday", help='Allows bot to start (but not trade) before market opens. Bot will revert to non-multiday behavior after the market opens.', action="store_true")
parser.add_argument("--unsafe", help='Allow trading between 9:30-10:15AM where volatility is high', action="store_true")
parser.add_argument("--notmarketclosed", help='Cancel order and exit if US stock market is closed', action="store_true")
parser.add_argument("--hold_overnight", help='Hold stocks overnight when --multiday is in use (default: False) - Warning: implies --unsafe', action="store_true")
parser.add_argument("--no_use_resistance", help='Do no use the high/low resistance to avoid possibly bad trades (default=False)', action="store_true")

parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1.5, type=float)
parser.add_argument("--num_purchases", help='Number of purchases allowed per day', nargs='?', default=10, type=int)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("--max_failed_txs", help='Maximum number of failed transactions allowed for a given stock before stock is blacklisted', default=2, type=int)
parser.add_argument("--max_failed_usd", help='Maximum allowed USD for a failed transaction before the stock is blacklisted', default=100, type=int)
parser.add_argument("--scalp_mode", help='Enable scalp mode (fixes incr_threshold and decr_threshold)', action="store_true")
parser.add_argument("--exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)
parser.add_argument("--vwap_exit", help='Use vwap exit strategy - sell/close at half way between entry point and vwap', action="store_true")

parser.add_argument("--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_k_period", help='k period to use in StochRSI algorithm', default=128, type=int)
parser.add_argument("--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--stochrsi_period", help='RSI period to use for stochastic RSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='ohlc4', type=str)
parser.add_argument("--rsi_high_limit", help='RSI high limit', default=80, type=int)
parser.add_argument("--rsi_low_limit", help='RSI low limit', default=20, type=int)
parser.add_argument("--vpt_sma_period", help='SMA period for VPT signal line', default=72, type=int)
parser.add_argument("--adx_period", help='ADX period', default=48, type=int)
parser.add_argument("--period_multiplier", help='Period multiplier - set statically here, or otherwise gobot will determine based on the number of candles it receives per minute.', default=0, type=int)

# Deprecated - use --algos=... instead
#parser.add_argument("--with_rsi", help='Use standard RSI as a secondary indicator', action="store_true")
#parser.add_argument("--with_adx", help='Use the Average Directional Index (ADX) as a secondary indicator', action="store_true")
#parser.add_argument("--with_dmi", help='Use the Directional Movement Index(DMI) as a secondary indicator', action="store_true")
#parser.add_argument("--with_macd", help='Use the Moving Average Convergence Divergence (MACD) as a secondary indicator', action="store_true")
#parser.add_argument("--with_aroonosc", help='Use the Aroon Oscillator as a secondary indicator', action="store_true")
#parser.add_argument("--with_vwap", help='Use VWAP as a secondary indicator', action="store_true")

parser.add_argument("--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("--shortonly", help='Only short sell the stock', action="store_true")

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

# Set incr_threshold and decr_threshold is scalp_mode==True
if ( args.scalp_mode == True ):
	args.incr_threshold = 0.1
	args.decr_threshold = 0.25
	if ( args.exit_percent == None ):
		args.exit_percent = 0.2

# Early exit criteria goes here
if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False ):
	print('Market is closed and --notmarketclosed was set, exiting')
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
#	   'adx':			False,
#	   'dmi':			False,
#	   'macd':			False,
#	   'aroonosc':			False,
#	   'vwap':			False,
#	   'vpt':			False,
#	   'support_resistance':	False
#	}, {...} ]
print('Initializing algorithms... ', end = '')

algos = []
for algo in args.algos:
	print(algo, end = '')
	algo = ','.join(algo)

	stochrsi = rsi = adx = dmi = macd = aroonosc = vwap = vpt = support_resistance = False
	for a in algo.split(','):

		if ( a == 'stochrsi' ):		stochrsi	= True
		if ( a == 'rsi' ):		rsi		= True
		if ( a == 'adx' ):		adx		= True
		if ( a == 'dmi' ):		dmi		= True
		if ( a == 'macd' ):		macd		= True
		if ( a == 'aroonosc' ):		aroonosc	= True
		if ( a == 'vwap' ):		vwap		= True
		if ( a == 'vpt' ):		vpt		= True
		if ( a == 'support_resistance' ): support_resistance = True

	algo_list = {	'stochrsi':		True,  # For now this cannot be turned off
			'rsi':			rsi,
			'adx':			adx,
			'dmi':			dmi,
			'macd':			macd,
			'aroonosc':		aroonosc,
			'vwap':			vwap,
			'vpt':			vpt,
			'support_resistance':	support_resistance }

	algos.append(algo_list)

del(stochrsi,rsi,adx,dmi,macd,aroonosc,vwap,vpt,support_resistance)
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
				   'decr_threshold':		float(args.decr_threshold),

				   # Action signals
				   'buy_signal':		False,
				   'sell_signal':		False,
				   'short_signal':		False,
				   'buy_to_cover_signal':	False,

				   'final_buy_signal':		False,
				   'final_sell_signal':		False,		# Currently unused
				   'final_short_signal':	False,
				   'final_buy_to_cover_signal':	False,		# Currently unused

				   'exit_signal':		False,

				   'signal_mode':		'buy',

				   # Indicator variables
				    # StochRSI
				    'cur_rsi_k':		float(-1),
				    'prev_rsi_k':		float(-1),
				    'cur_rsi_d':		float(-1),
				    'prev_rsi_d':		float(-1),

				    # RSI
				    'cur_rsi':			float(-1),

				    # ADX
				    'cur_adx':			float(-1),

				    # DMI
				    'cur_plus_di':		float(-1),
				    'prev_plus_di':		float(-1),
				    'cur_minus_di':		float(-1),
				    'prev_minus_di':		float(-1),

				    # MACD
				    'cur_macd':			float(-1),
				    'prev_macd':		float(-1),
				    'cur_macd_avg':		float(-1),
				    'prev_macd_avg':		float(-1),

				    # Aroon Oscillator
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

				    # Support / Resistance
				    'three_week_high':		float(0),
				    'three_week_low':		float(0),
				    'three_week_avg':		float(0),
				    'twenty_week_high':		float(0),
				    'twenty_week_low':		float(0),
				    'twenty_week_avg':		float(0),

				    'previous_day_close':	None,

				   # Indicator Signals
				   'rsi_signal':		False,
				   'adx_signal':		False,
				   'dmi_signal':		False,
				   'macd_signal':		False,
				   'aroonosc_signal':		False,
				   'vwap_signal':		False,
				   'vpt_signal':		False,

				   'plus_di_crossover':		False,
				   'minus_di_crossover':	False,
				   'macd_crossover':		False,
				   'macd_avg_crossover':	False,

				   # Period log will log datetime to determine period_multiplier
				   'period_log':		[],
				   'period_multiplier':		args.period_multiplier,

				   # Candle data
				   'pricehistory':		{}
			}} )

	# Start in 'buy' mode unless we're only shorting
	if ( args.shortonly == True ):
		stocks[ticker]['signal_mode'] = 'short'

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	sys.exit(1)

# Get stock_data info about the stock that we can use later (i.e. shortable)
try:
	stock_data,err = tda.stocks.get_quotes(args.stocks, True)

except Exception as e:
	print('Caught exception: get_quote(' + str(ticker) + '): ' + str(e), file=sys.stderr)
	sys.exit(1)

# Initialize additional stocks{} values
for ticker in stocks.keys():
	if ( tda_gobot_helper.check_blacklist(ticker) == True and args.force == False ):
		print('(' + str(ticker) + ') Error: stock ' + str(ticker) + ' found in blacklist file, removing from the list')
		stocks[ticker]['isvalid'] = False
		continue

	# Confirm that we can short this stock
	if ( args.short == True or args.shortonly == True ):
		if ( stock_data[ticker]['shortable'] == str(False) or stock_data[ticker]['marginable'] == str(False) ):
			if ( args.shortonly == True ):
				print('Error: stock(' + str(ticker) + '): does not appear to be shortable, removing from the list')
				stocks[ticker]['isvalid'] = False
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
tda_stochrsi_gobot_helper.args = args
tda_stochrsi_gobot_helper.tx_log_dir = args.tx_log_dir
tda_stochrsi_gobot_helper.stocks = stocks
tda_stochrsi_gobot_helper.incr_threshold = args.incr_threshold
tda_stochrsi_gobot_helper.stock_usd = args.stock_usd
tda_stochrsi_gobot_helper.loopt = 0.1

# StochRSI
tda_stochrsi_gobot_helper.rsi_low_limit = args.rsi_low_limit
tda_stochrsi_gobot_helper.rsi_high_limit = args.rsi_high_limit

tda_stochrsi_gobot_helper.rsi_signal_cancel_low_limit = 20
tda_stochrsi_gobot_helper.rsi_signal_cancel_high_limit = 80

tda_stochrsi_gobot_helper.rsi_period = args.rsi_period
tda_stochrsi_gobot_helper.stochrsi_period = args.stochrsi_period
tda_stochrsi_gobot_helper.rsi_slow = args.rsi_slow
tda_stochrsi_gobot_helper.rsi_k_period = args.rsi_k_period
tda_stochrsi_gobot_helper.rsi_d_period = args.rsi_d_period
tda_stochrsi_gobot_helper.rsi_type = args.rsi_type

# ADX / DMI
tda_stochrsi_gobot_helper.adx_period = args.adx_period # Usually 48-62

# MACD
tda_stochrsi_gobot_helper.macd_short_period = 48
tda_stochrsi_gobot_helper.macd_long_period = 104
tda_stochrsi_gobot_helper.macd_signal_period = 36

# Aroonosc
tda_stochrsi_gobot_helper.aroonosc_period = 128

# VPT
tda_stochrsi_gobot_helper.vpt_sma_period = args.vpt_sma_period # Typically 72

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
	print('Error: Login failure')

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

for ticker in stocks.keys():
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
		continue

	# Populate the period_log with history data
	for key in data['candles']:
		stocks[ticker]['period_log'].append( key['datetime'] )

#	stocks[ticker]['previous_day_close'] = tda_gobot_helper.get_pdc(data)

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

	if ( args.scalp_mode == True ):
		await stream_client.quality_of_service(StreamClient.QOSLevel.EXPRESS)
	else:
		await stream_client.quality_of_service(StreamClient.QOSLevel.REAL_TIME)

	stream_client.add_chart_equity_handler(
		lambda msg: tda_stochrsi_gobot_helper.stochrsi_gobot_run(msg, algos, args.debug) )

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
		time.sleep(2)


sys.exit(0)
