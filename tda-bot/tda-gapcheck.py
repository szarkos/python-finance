#!/usr/bin/python3 -u

import os, sys, signal
import time, datetime, pytz, random
from subprocess import Popen, STDOUT
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
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--autotrade", help='Make trades automatically with gap up/down alerts occur', action="store_true")
parser.add_argument("--fake", help='Paper trade only - runs tda-gobot with --fake option', action="store_true")
parser.add_argument("--monitor", help='Disables buy/sell functions', action="store_true")
parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=0.5, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1, type=float)
parser.add_argument("--scalp_mode", help='Enable scalp mode (fixes incr_threshold and decr_threshold to low values)', action="store_true")
parser.add_argument("--skip_avgvol", help='Skip calculating average volume - speeds startup avoiding get_pricehistory API', action="store_true")

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

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        sys.exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda = tda
tda_gobot_helper.tda_account_number = tda_account_number
tda_gobot_helper.passcode = passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure', file=sys.stderr)
	sys.exit(1)

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
				   'avg_volume':		1,
				   'process':			None,

				   # Candle data
				   'pricehistory':		{ 'candles': [] }
			}} )

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	sys.exit(1)

# Initialize additional stocks{} values
time_now = datetime.datetime.now( mytimezone )
time_prev = time_now - datetime.timedelta( days=9 )

# Make sure start and end dates don't land on a weekend or outside market hours
time_now = tda_gobot_helper.fix_timestamp(time_now)
time_prev = tda_gobot_helper.fix_timestamp(time_prev)

time_now_epoch = int( time_now.timestamp() * 1000 )
time_prev_epoch = int( time_prev.timestamp() * 1000 )

# tda.get_pricehistory() variables
p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

# Get stock_data info about the stock that we can use later (i.e. shortable)
try:
	stock_data = tda_gobot_helper.get_quotes(args.stocks)

except Exception as e:
	print('Caught exception: get_quote(): ' + str(e), file=sys.stderr)
	sys.exit(1)

if ( isinstance(stock_data, bool) and stock_data == False ):
	print('Error: tda_gobot_helper.get_quotes(): returned False')
	sys.exit(1)

# Populate ticker info in stocks[]
for ticker in list(stocks.keys()):
	if ( args.autotrade == True ):
		if ( tda_gobot_helper.check_blacklist(ticker) == True and args.force == False ):
			print('(' + str(ticker) + ') Error: stock ' + str(ticker) + ' found in blacklist file, removing from the list')
			stocks[ticker]['isvalid'] = False

			try:
				del stocks[ticker]
			except KeyError:
				print('Warning: failed to delete key "' + str(ticker) + '" from stocks{}')

			continue

	# Confirm that we can short this stock
	try:
		stock_data[ticker]['shortable']
		stock_data[ticker]['marginable']
	except:
		stock_data[ticker]['shortable'] = str(False)
		stock_data[ticker]['marginable'] = str(False)

	if ( stock_data[ticker]['shortable'] == str(False) or stock_data[ticker]['marginable'] == str(False) ):
		print('Warning: stock(' + str(ticker) + '): does not appear to be shortable, disabling --short')
		stocks[ticker]['shortable'] = False

	if ( args.skip_avgvol == False ):
		avg_vol = 0
		data = False
		while ( data == False ):
			data, epochs = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=False)
			if ( data == False ):
				time.sleep(5)
				if ( tda_gobot_helper.tdalogin(passcode) != True ):
					print('Error: (' + str(ticker) + '): Login failure')
				continue

		for key in data['candles']:
			avg_vol += float(key['volume'])
		stocks[ticker]['avg_volume'] = int( round(avg_vol / len(data['candles']), 0) )

		time.sleep(2)

# Initialize signal handlers to dump stock history on exit
def graceful_exit(signum, frame):
	print("\nNOTICE: graceful_exit(): received signal: " + str(signum))
	log_fh.close()
	sys.exit(0)

# Initialize SIGUSR1 signal handler to dump stocks on signal
# Calls sell_stocks() to immediately sell or buy_to_cover any open positions
def siguser1_handler(signum, frame):
	print("\nNOTICE: siguser1_handler(): received signal")
	print("NOTICE: Calling sell_stocks() to exit open positions...\n")

	if ( args.monitor == False ):
		sell_stocks()

	graceful_exit(None, None)
	sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGUSR1, siguser1_handler)


# Monitor stock for big jumps in price and volume
def gap_monitor(stream=None, debug=False):

	if ( stream == None ):
		return False

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
		if ( debug == True ):
			print('Market is closed.')

		return True

	if ( args.debug == True ):
		time_now = datetime.datetime.now(mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
		print(time_now)


	# Iterate through the stock tickers
	# We are interested in significant increases or decreases in price, and significant increases in volume
	for ticker in stocks.keys():

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Wait for some data before making decisions
		if ( len(stocks[ticker]['pricehistory']['candles']) < 10 ):
			continue

		# Command to run if we need to purchase/short this stock
		gobot_command = ['./tda-gobot.py', str(ticker), str(args.stock_usd), '--tx_log_dir=TX_LOGS-GAPCHECK',
				 '--decr_threshold='+str(args.decr_threshold), '--incr_threshold='+str(args.incr_threshold)]

		if ( args.fake == True ):
			gobot_command.append('--fake')

		# Get the latest candle open/close prices and volume
		cur_price = float(stocks[ticker]['pricehistory']['candles'][-1]['close'])
		prev_price = float(stocks[ticker]['pricehistory']['candles'][-4]['close'])

		cur_vol = float(stocks[ticker]['pricehistory']['candles'][-1]['volume']) + \
				float(stocks[ticker]['pricehistory']['candles'][-2]['volume']) + \
				float(stocks[ticker]['pricehistory']['candles'][-3]['volume']) + \
				float(stocks[ticker]['pricehistory']['candles'][-4]['volume'])

		# Skip if price hasn't changed
		if ( cur_price == prev_price ):
			continue

		price_change = float(0)
		vol_change = float(0)
		if ( cur_price > prev_price ):
			# Bull
			direction = 'UP'
			price_change = ( (cur_price - prev_price) / prev_price ) * 100
		else:
			# Bear
			direction = 'DOWN'
			price_change = ( (prev_price - cur_price) / prev_price ) * 100

		# Call gap up/down if price and volume change significantly (>1%)
		# Streams often gets two candles/minute, so combining volume from the last two
		#  candles makes sense to get a more accurate picture.
		if ( price_change > 1.2 and cur_vol > stocks[ticker]['avg_volume'] ):
			vol_change = ( (cur_vol - stocks[ticker]['avg_volume']) / stocks[ticker]['avg_volume'] ) * 100

			time_now = datetime.datetime.now(mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
			print( '(' + str(ticker) + '): Gap ' + str(direction).upper() + ' detected (' + str(time_now) + ')' )

			print( 'Current Price: ' + str(round(cur_price, 2)) + ', ' +
				'Previous Price: ' + str(round(prev_price, 2)) +
				' (' + str(round(price_change, 2)) + '%)' )

			print( 'Current Volume: ' + str(cur_vol) + ', ' +
				'Average Volume: ' + str(round(stocks[ticker]['avg_volume'], 2)) +
				'(+' + str(vol_change) + '%)' )

			print()

			# Short if stock price is going down
			if ( direction == 'DOWN' ):
				gobot_command.append('--short')

			# Make a trade on gapping stock if args.autotrade is set
			if ( args.autotrade == True ):

				# Check to see if we have a running process
				if ( isinstance(stocks[ticker]['process'], Popen) == True ):
					if ( stocks[ticker]['process'].poll() != None ):
						# process has exited
						stocks[ticker]['process'] = None
					else:
						# Another process is running for this ticker
						print('(' + str(ticker) + '): Another process (pid: ' + str(stocks[ticker]['process'].pid) + ') is already running')
						continue

				# If process==None then we should be safe to run a gobot instance for this stock
				if ( stocks[ticker]['process'] == None and args.monitor == False ):
					try:
						stocks[ticker]['process'] = Popen(gobot_command, stdin=None, stdout=log_fh, stderr=STDOUT, shell=False)

					except Exception as e:
						print('(' + str(ticker) + '): Exception caught: ' + str(e))

	return True


# Sell any open positions. This is usually called via a signal handler.
def sell_stocks():

	# Make sure we are logged into TDA
	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: sell_stocks(): tdalogin(): login failure')
		return False

	# Run through the stocks we are watching and sell/buy-to-cover any open positions
	data = tda.get_account(tda_account_number, options='positions', jsonify=True)
	for ticker in stocks.keys():

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Look up the stock in the account and sell
		for asset in data[0]['securitiesAccount']['positions']:
			if ( str(asset['instrument']['symbol']).upper() == str(ticker).upper() ):

				if ( float(asset['shortQuantity']) > 0 ):
					print('Covering ' + str(asset['shortQuantity']) + ' shares of ' + str(ticker))
					data = tda_gobot_helper.buytocover_stock_marketprice(ticker, asset['shortQuantity'], fillwait=False, debug=False)
				else:
					print('Selling ' + str(asset['longQuantity']) + ' shares of ' + str(ticker))
					data = tda_gobot_helper.sell_stock_marketprice(ticker, asset['longQuantity'], fillwait=False, debug=False)

				break

	return True


# MAIN: Log into tda-api and run the stream client
tda_api_key = os.environ['tda_consumer_key']
tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'

# Initializes and reads from TDA stream API
async def read_stream():
	await asyncio.wait_for( stream_client.login(), 10 )
	await asyncio.wait_for( stream_client.quality_of_service(StreamClient.QOSLevel.EXPRESS), 10 )

	stream_client.add_chart_equity_handler(
		lambda msg: gap_monitor(msg, args.debug) )

	await asyncio.wait_for( stream_client.chart_equity_subs(stocks.keys()), 10 )

	while True:
		await asyncio.wait_for( stream_client.handle_message(), 120 )


# MAIN
# Initialize log file handle
logfile = './logs/gapcheck.log'
try:
	log_fh = open(logfile, 'a')

except Exception as e:
	print('Unable to open log file ' + str(logfile) + ', exiting.')
	sys.exit(1)

# Main loop
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

