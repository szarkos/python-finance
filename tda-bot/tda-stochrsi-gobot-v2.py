#!/usr/bin/python3 -u

# Monitor a stock's Stochastic RSI values and make purchase decisions based off those values.
# Examples:
#  ./tda-rsi-gobot.py --algo=stochrsi --short --multiday --stoploss --decr_threshold=1.5 \
#			--num_purchases=20 --max_failed_txs=2 --max_failed_usd=300 \
#			--rsi_high_limit=80 --rsi_low_limit=20 --rsi_period=128 --rsi_k_period=128 --rsi_d_period=3 --rsi_slow=6 \
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
parser.add_argument("--algo", help='Algorithm to use (rsi|stochrsi)', default='stochrsi', type=str)
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")

parser.add_argument("--multiday", help='Watch stock until decr_threshold is reached. Do not sell and exit when market closes', action="store_true")
parser.add_argument("--notmarketclosed", help='Cancel order and exit if US stock market is closed', action="store_true")
parser.add_argument("--hold_overnight", help='Hold stocks overnight when --multiday is in use (default: False)', action="store_true")
parser.add_argument("--no_use_resistance", help='Do no use the high/low resistance to avoid possibly bad trades (default=False)', action="store_true")

parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1.5, type=float)
parser.add_argument("--num_purchases", help='Number of purchases allowed per day', nargs='?', default=4, type=int)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("--max_failed_txs", help='Maximum number of failed transactions allowed for a given stock before stock is blacklisted', default=2, type=int)
parser.add_argument("--max_failed_usd", help='Maximum allowed USD for a failed transaction before the stock is blacklisted', default=100, type=int)

parser.add_argument("--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_k_period", help='k period to use in StochRSI algorithm', default=14, type=int)
parser.add_argument("--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--stochrsi_period", help='RSI period to use for stochastic RSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='ohlc4', type=str)
parser.add_argument("--rsi_high_limit", help='RSI high limit', default=80, type=int)
parser.add_argument("--rsi_low_limit", help='RSI low limit', default=20, type=int)

parser.add_argument("--with_adx", help='Use the Average Directional Index (ADX) as a secondary indicator', action="store_true")
parser.add_argument("--with_dmi", help='Use the Directional Movement Index(DMI) as a secondary indicator', action="store_true")
parser.add_argument("--with_macd", help='Use the Moving Average Convergence Divergence (MACD) as a secondary indicator', action="store_true")
parser.add_argument("--with_aroonosc", help='Use the Aroon Oscillator as a secondary indicator', action="store_true")

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

# Early exit criteria goes here
if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
	print('Market is closed and --notmarketclosed was set, exiting')
	exit(1)

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        exit(1)

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
	exit(1)

# Initialize SIGUSR1 signal handler to dump stocks on signal
# Calls sell_stocks() to immediately sell or buy_to_cover any open positions
def siguser1_handler(signum, frame):
	print("\nNOTICE: siguser1_handler(): received signal")
	print("NOTICE: Calling sell_stocks() to exit open positions...\n")

	tda_stochrsi_gobot_helper.sell_stocks()
	sys.exit(0)

signal.signal(signal.SIGUSR1, siguser1_handler)


# Initialize stocks{}
print( 'Initializing stock tickers: ' + str(args.stocks.split(',')) )

stocks = OrderedDict()
for ticker in args.stocks.split(','):

	if ( ticker == '' ):
		continue

	# Fix up and sanity check the stock symbol before proceeding
	ticker = tda_gobot_helper.fix_stock_symbol(ticker)
	if ( tda_gobot_helper.check_stock_symbol(ticker) != True ):
		print('Error: check_stock_symbol(' + str(ticker) + ') returned False, removing from the list')
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
				   'final_sell_signal':		False,
				   'final_short_signal':	False,
				   'final_buy_to_cover_signal':	False,

				   'signal_mode':		'buy',

				   # Indicator variables
				    # StochRSI
				    'cur_rsi_k':		float(-1),
				    'prev_rsi_k':		float(-1),
				    'cur_rsi_d':		float(-1),
				    'prev_rsi_d':		float(-1),

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

				    # Support / Resistance
				    'three_week_high':		float(0),
				    'three_week_low':		float(0),
				    'three_week_avg':		float(0),
				    'twenty_week_high':		float(0),
				    'twenty_week_low':		float(0),
				    'twenty_week_avg':		float(0),

				   # Indicator Signals
				   'adx_signal':		False,
				   'dmi_signal':		False,
				   'aroonosc_signal':		False,
				   'macd_signal':		False,

				   'plus_di_crossover':		False,
				   'minus_di_crossover':	False,
				   'macd_crossover':		False,
				   'macd_avg_crossover':	False,

				   # Candle data
				   'pricehistory':		{}
			}} )

	# Start in 'buy' mode unless we're only shorting
	if ( args.shortonly == True ):
		stocks[ticker]['signal_mode'] = 'short'

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	exit(1)

# TDA API is limited to 150 non-transactional calls per minute. It's best to sleep
#  a bit here to avoid spurious errors later.
time.sleep(len(stocks) * 2)

# Initialize additional stocks{} values
for ticker in stocks.keys():
	if ( tda_gobot_helper.check_blacklist(ticker) == True and args.force == False ):
		print('(' + str(ticker) + ') Error: stock ' + str(ticker) + ' found in blacklist file, removing from the list')
		stocks[ticker]['isvalid'] = False
		continue

	# Confirm that we can short this stock
	if ( args.short == True or args.shortonly == True ):
		data,err = tda.stocks.get_quote(ticker, True)
		if ( err != None ):
			print('Error: get_quote(' + str(ticker) + '): ' + str(err), file=sys.stderr)

		if ( str(data[ticker]['shortable']) == str(False) or str(data[ticker]['marginable']) == str(False) ):
			if ( args.shortonly == True ):
				print('Error: stock(' + str(ticker) + '): does not appear to be shortable, removing from the list')
				stocks[ticker]['isvalid'] = False
				continue

			elif ( args.short == True ):
				print('Warning: stock(' + str(ticker) + '): does not appear to be shortable, disabling --short')
				stocks[ticker]['shortable'] = False

	time.sleep(1)


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
tda_stochrsi_gobot_helper.stocks = stocks
tda_stochrsi_gobot_helper.incr_threshold = args.incr_threshold
tda_stochrsi_gobot_helper.stock_usd = args.stock_usd
tda_stochrsi_gobot_helper.loopt = 10

# StochRSI
tda_stochrsi_gobot_helper.rsi_low_limit = args.rsi_low_limit
tda_stochrsi_gobot_helper.rsi_high_limit = args.rsi_high_limit
tda_stochrsi_gobot_helper.rsi_period = args.rsi_period
tda_stochrsi_gobot_helper.stochrsi_period = args.stochrsi_period
tda_stochrsi_gobot_helper.rsi_slow = args.rsi_slow
tda_stochrsi_gobot_helper.rsi_k_period = args.rsi_k_period
tda_stochrsi_gobot_helper.rsi_d_period = args.rsi_d_period
tda_stochrsi_gobot_helper.rsi_type = args.rsi_type

# ADX / DMI
tda_stochrsi_gobot_helper.adx_period = 64

# MACD
tda_stochrsi_gobot_helper.macd_short_period = 48
tda_stochrsi_gobot_helper.macd_long_period = 104
tda_stochrsi_gobot_helper.macd_signal_period = 36

# Aroonosc
tda_stochrsi_gobot_helper.aroonosc_period = 128


# Initialize pricehistory for each stock ticker
print( 'Populating pricehistory for stock tickers: ' + str(list(stocks.keys())) )

# TDA API is limited to 150 non-transactional calls per minute. It's best to sleep
#  a bit here to avoid spurious errors later.
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
time_prev = time_now - datetime.timedelta( days=4 )

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
		else:
			stocks[ticker]['pricehistory'] = data

	time.sleep(1)


# MAIN: Log into tda-api and run the stream client
tda_api_key = os.environ['tda_consumer_key']
tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'

# Initializes and reads from TDA stream API
async def read_stream():
	await stream_client.login()
	await stream_client.quality_of_service(StreamClient.QOSLevel.REAL_TIME)

	stream_client.add_chart_equity_handler(
		lambda msg: tda_stochrsi_gobot_helper.stochrsi_gobot(msg, args.debug) )

	await stream_client.chart_equity_subs( stocks.keys() )

	while True:
		await stream_client.handle_message()


# MAIN
while True:

	# Log in using the tda-api module to access the streams interface
	try:
		tda_client = tda_api.auth.client_from_token_file(tda_pickle, tda_api_key)

	except Exception as e:
		print('Exception caught: client_from_token_file(): unable to log in using tda-client: ' + str(e))
		time.sleep(30)
		continue

	# Initialize streams client
	print( 'Initializing streams client for stock tickers: ' + str(list(stocks.keys())) )
	try:
		stream_client = StreamClient(tda_client, account_id=tda_account_number)

	except Exception as e:
		print('Exception caught: StreamClient(): ' + str(e) + ': retrying...')
		time.sleep(30)
		continue

	# Call read_stream():stream_client.handle_message() to read from the stream continuously
	try:
		asyncio.run(read_stream())

	except KeyboardInterrupt:
		sys.exit(0)

	except Exception as e:
		print('Exception caught: read_stream(): ' + str(e) + ': retrying...')
		time.sleep(30)


sys.exit(0)
