#!/usr/bin/python3 -u

import os, sys, signal
import time, datetime, pytz, random
from collections import OrderedDict
import argparse

# We use robin_stocks for most REST operations
import robin_stocks.tda as tda
import tda_gobot_helper

# tda-api is used for streaming client
# https://tda-api.readthedocs.io/en/stable/streaming.html
import tda as tda_api
from tda.client import Client
from tda.streaming import StreamClient
import asyncio
import json


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='Stock ticker(s) to purchase (comma delimited)', required=True, type=str)
parser.add_argument("--stock_usd", help='Amount of money (USD) to invest per trade', default=1000, type=float)
parser.add_argument("--algo", help='Algorithm to use (rsi|stochrsi)', default='stochrsi', type=str)
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS', default='TX_LOGS', type=str)

parser.add_argument("--multiday", help='Watch stock until decr_threshold is reached. Do not sell and exit when market closes', action="store_true")

parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1.5, type=float)
parser.add_argument("--num_purchases", help='Number of purchases allowed per day', nargs='?', default=2, type=int)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("--max_failed_txs", help='Maximum number of failed transactions allowed for a given stock before stock is blacklisted', default=2, type=int)
parser.add_argument("--max_failed_usd", help='Maximum allowed USD for a failed transaction before the stock is blacklisted', default=100, type=int)
parser.add_argument("--scalp_mode", help='Enable scalp mode (fixes incr_threshold and decr_threshold', action="store_true")

parser.add_argument("--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
args = parser.parse_args()

## FOR TESTING
args.debug = True
## FOR TESTING

# Set timezone
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone

# Set incr_threshold and decr_threshold is scalp_mode==True
if ( args.scalp_mode == True ):
	args.incr_threshold = 0.1
	args.decr_threshold = 0.25

# Early exit criteria goes here
if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
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

				   # Candle data
				   'pricehistory':		{}
			}} )

	time.sleep(1)

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	sys.exit(1)

# TDA API is limited to 150 non-transactional calls per minute. It's best to sleep
#  a bit here to avoid spurious errors later.
time.sleep(60)

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

# Initialize signal handlers to dump stock history on exit
def graceful_exit(signum, frame):
	print("\nNOTICE: graceful_exit(): received signal: " + str(signum))
	sys.exit(0)

# Initialize SIGUSR1 signal handler to dump stocks on signal
# Calls sell_stocks() to immediately sell or buy_to_cover any open positions
def siguser1_handler(signum, frame):
	print("\nNOTICE: siguser1_handler(): received signal")
	print("NOTICE: Calling sell_stocks() to exit open positions...\n")

	tda_stochrsi_gobot_helper.sell_stocks()
	graceful_exit(None, None)
	sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGUSR1, siguser1_handler)


# MAIN: Log into tda-api and run the stream client
tda_api_key = os.environ['tda_consumer_key']
tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'

# Initializes and reads from TDA stream API
async def read_stream():
	await stream_client.login()
	await stream_client.quality_of_service(StreamClient.QOSLevel.EXPRESS)

	stream_client.add_chart_equity_handler(
		lambda msg: gap_monitor(msg, args.debug) )

	await stream_client.chart_equity_subs( stocks.keys() )

	while True:
		await stream_client.handle_message()


# Monitor stock for big jumps in price and volume
def gap_monitor(stream=None, debug=False):

	# Example stream:
	#
	# { 'service': 'CHART_EQUITY',
	#   'timestamp': 1619813320675,
	#   'command': 'SUBS',
	#   'content': [{
	#		'seq': 2712,
	#		'key': 'FB',
	#		'OPEN_PRICE': 325.05,
	#		'HIGH_PRICE': 325.05,
	#		'LOW_PRICE': 325.0,
	#		'CLOSE_PRICE': 325.02,
	#		'VOLUME': 898.0,
	#		'SEQUENCE': 547,
	#		'CHART_TIME': 1619813220000,
	#		'CHART_DAY': 18747 }]
	# }
	for idx in stream['content']:
		ticker = idx['key']

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		candle_data = { 'open':		idx['OPEN_PRICE'],
				'high':		idx['HIGH_PRICE'],
				'low':		idx['LOW_PRICE'],
				'close':	idx['CLOSE_PRICE'],
				'volume':	idx['VOLUME'],
				'datetime':	stream['timestamp'] }

		stocks[ticker]['pricehistory']['candles'].append(candle_data)


	if ( tda_gobot_helper.ismarketopen_US() == False ):
		return True

	# Iterate through the stock tickers
	# We are interested in significant increases or decreases in price, and significant increases in volume
	for ticker in stocks.keys():

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Wait for some data before making purchasing decisions
		if ( len(stocks[ticker]['pricehistory']['candles']) < 2 ):
			continue

		cur_price = float(stocks[ticker]['pricehistory']['candles'][-1]['close'])
		prev_price = float(stocks[ticker]['pricehistory']['candles'][-2]['close'])
		cur_vol = float(stocks[ticker]['pricehistory']['candles'][-1]['volume'])
		prev_vol = float(stocks[ticker]['pricehistory']['candles'][-2]['volume'])

		# Skip if price hasn't changed, or volume didn't increase
		if ( cur_price == prev_price or prev_vol >= cur_vol ):
			continue

		price_change = float(0)
		vol_change = float(0)
		if ( cur_price > prev_price ):
			# Bull
			direction = 'UP'
			price_change = ( (cur_price - prev_price) / cur_price ) * 100
		else:
			# Bear
			direction = 'DOWN'
			price_change = ( (prev_price - cur_price) / prev_price ) * 100

		vol_change = ( (cur_vol - prev_vol) / cur_vol ) * 100


		# FIXME
		# Call gap up/down if price and volume change significantly
		if ( price_change > 0.2 and vol_change > 0.25 ):
			print( '(' + str(ticker) + '): Gap ' + str(direction).upper() + ' detected' )

			print( 'Current Price: ' + str(round(cur_price, 2)) +
				', Previous Price: ' + str(round(prev_price, 2)) +
				' (' + str(round(price_change, 2)) + '%)' )

			print( 'Current Volume: ' + str(cur_vol) +
				', Previous Volume: ' + str(prev_vol) +
				' (' + str(round(vol_change, 2)) + '%)' )

	return True


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
