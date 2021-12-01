#!/usr/bin/python3 -u

# Uses TDA's streams API to monitor stocks for -
#  - Gaps up
#  - Gaps down
#  - Approaching VWAP support

import os, sys, signal
import time, datetime, pytz, random
import re
from subprocess import Popen, PIPE, STDOUT
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

import tda_api_helper
import tda_algo_helper


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='Stock ticker(s) to purchase (comma delimited)', required=True, type=str)
parser.add_argument("--stock_usd", help='Amount of money (USD) to invest per trade', default=1000, type=float)
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--skip_history", help='Skip retrieving price history. Speeds startup but disables calculating average volume and VWAP', action="store_true")

parser.add_argument("--autotrade", help='Make trades automatically with gap up/down alerts occur', action="store_true")
parser.add_argument("--fake", help='Paper trade only - runs tda-gobot with --fake option', action="store_true")
parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=0.5, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1, type=float)
parser.add_argument("--scalp_mode", help='Enable scalp mode (fixes incr_threshold and decr_threshold to low values)', action="store_true")
parser.add_argument("--after_hours", help='Enable running after hours (pre/post market)', action="store_true")

parser.add_argument("--gap_threshold", help='Percent threshold for price gap up/down detection (Default: 1 percent)', default=1, type=float)
parser.add_argument("--vol_threshold", help='Percent threshold for volume gap up detection (Default: 300 percent)', default=300, type=float)
parser.add_argument("--vwap_threshold", help='Threshold for VWAP proximity detection (percentage)', default=1, type=float)
parser.add_argument("--max_tickers", help='Max tickers to print out per category (Default: 20)', default=20, type=int)
parser.add_argument("--gap_candles", help='Number of candles to count when determining price gap up/down (Default: 4 candles)', default=4, type=int)

parser.add_argument("--ib_short", help='Enable Interactive Brokers short watch', action="store_true")
parser.add_argument("--ib_short_pct", help='Percentage decrease to alert on for shorts available when querying Interactive Brokers (Default:90)', default=90, type=int)
parser.add_argument("--ib_short_cmd", help='Location of the ibrokers-short.py command (Default: "../interactivebrokers/ibrokers-short.py")', default='../interactivebrokers/ibrokers-short.py', type=str)

parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
args = parser.parse_args()

## FOR TESTING
args.debug = True

# Set timezone
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        sys.exit(1)

tda_account_number			= int( os.environ["tda_account_number"] )
passcode				= os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda			= tda
tda_gobot_helper.tda_account_number	= tda_account_number
tda_gobot_helper.passcode		= passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure', file=sys.stderr)
	sys.exit(1)

# Global params
watchlists = [ 'STOCK-MONITOR-GAPUP', 'STOCK-MONITOR-GAPDOWN', 'STOCK-MONITOR-VOLUME', 'STOCK-MONITOR-VWAP' ]
watchlist_template = {  "name": "",
			"watchlistItems": [
				{ "instrument": { "symbol": "GME", "assetType": "EQUITY" } }
			] }

prev_timestamp = 0
gap_up_list = []
gap_down_list = []
vol_gap_up_list = []
vwap_list = []
ib_out = ib_err = None

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
				   'process':			None,

				   'avg_volume':		1,

				   'previous_day_close':	None,

				   # Candle data
				   'pricehistory':		{ 'candles': [] }
			}} )

if ( len(stocks) == 0 ):
	print('Error: no valid stock tickers provided, exiting.')
	sys.exit(1)

# Initialize additional stocks{} values
time_now = datetime.datetime.now( mytimezone )
time_prev = time_now - datetime.timedelta( days=10 )

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

	# Populate pricehistory
	# Calculate average volume
	# Find PDC
	if ( args.skip_history == False ):
		avg_vol = 0
		data = False
		while ( data == False ):
			data, epochs = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=False)
			if ( data == False ):
				time.sleep(5)
				if ( tda_gobot_helper.tdalogin(passcode) != True ):
					print('Error: (' + str(ticker) + '): Login failure')
				continue

			else:
				stocks[ticker]['pricehistory'] = data

		# Avg Volume (per minute)
		for key in data['candles']:
			avg_vol += int( key['volume'] )
		stocks[ticker]['avg_volume'] = int(avg_vol / len(data['candles']) )

		# PDC
		yesterday = time_now - datetime.timedelta(days=1)
		yesterday = tda_gobot_helper.fix_timestamp(yesterday)
		yesterday = yesterday.strftime('%Y-%m-%d')

		for key in data['candles']:
			day = datetime.datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone)
			if ( day.strftime('%Y-%m-%d') == yesterday ):

				# Sometimes low/zero EOD volume misses a candle, try a couple EOD candles to be safe
				hm = day.strftime('%H:%M')
				if ( hm == '15:59' or hm == '16:00' ):
					stocks[ticker]['previous_day_close'] = float( key['close'] )

		if ( stocks[ticker]['previous_day_close'] == None ):
			print('Warning: (' + str(ticker) + '): failed to find PDC from pricehistory, falling back to get_pdc()')
			while ( stocks[ticker]['previous_day_close'] == None ):
				stocks[ticker]['previous_day_close'] = tda_gobot_helper.get_pdc(data)
				if ( stocks[ticker]['previous_day_close'] == None ):
					print('Error: (' + str(ticker) + '): get_pdc() returned None, retrying...')
					time.sleep(5)

		time.sleep(2)


# Initialize signal handlers to dump stock history on exit
def graceful_exit(signum, frame):
	print("\nNOTICE: graceful_exit(): received signal: " + str(signum))

	try:
		log_fh.close()
	except:
		pass

	global watchlists
	for wlist in watchlists:
		try:
			tda_api_helper.delete_watchlist_byname(tda_client=tda_client, tda_account=tda_account_number, watchlist_name=wlist)
		except:
			pass

	sys.exit(0)

# Initialize SIGUSR1 signal handler to dump stocks on signal
# Calls sell_stocks() to immediately sell or buy_to_cover any open positions
def siguser1_handler(signum, frame):
	print("\nNOTICE: siguser1_handler(): received signal")
	print("NOTICE: Calling sell_stocks() to exit open positions...\n")

	if ( args.autotrade == True ):
		sell_stocks()

	graceful_exit(None, None)
	sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGUSR1, siguser1_handler)


# Make a trade on gapping stock
def autotrade(ticker=None, direction=None):

	if ( ticker == None or direction == None ):
		return False

	# Set incr_threshold and decr_threshold is scalp_mode==True
	if ( args.scalp_mode == True ):
		args.incr_threshold = 0.1
		args.decr_threshold = 0.25

	# Command to run if we need to purchase/short this stock
	gobot_command = ['./tda-gobot.py', str(ticker), str(args.stock_usd), '--tx_log_dir=TX_LOGS-GAPCHECK',
			 '--decr_threshold='+str(args.decr_threshold), '--incr_threshold='+str(args.incr_threshold)]

	# Short if stock price is going down
	if ( direction == 'DOWN' ):
		gobot_command.append('--short')

	if ( args.fake == True ):
		gobot_command.append('--fake')

	# Check to see if we have a running process
	if ( isinstance(stocks[ticker]['process'], Popen) == True ):
		if ( stocks[ticker]['process'].poll() != None ):
			# process has exited
			stocks[ticker]['process'] = None

		else:
			# Another process is running for this ticker
			return False

	# If process==None then we should be safe to run a gobot instance for this stock
	if ( stocks[ticker]['process'] == None and args.autotrade == True ):
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


def gap_filter( ticker=None, gap_list=[], delta=600 ):

	if ( ticker == None ):
		return False

	if ( len(gap_list) == 0 ):
		return True

	# These events can pile up into volume gap up list, so check to see
	# if this ticker has triggered already within the last ten minutes
	delta = 99999
	for evnt in reversed( gap_list ):

		# Note: this assumes that the 'stock' and 'time' elements are
		#  the first and last item in the event log respectively
		stock = str(evnt).split(',')[0]
		time = str(evnt).split(',')[-1] # This should be a datetime.datetime object

		if ( stock == ticker ):
			cur_time = datetime.datetime.now(mytimezone)
			cur_time = mytimezone.localize(cur_time)

			prev_time = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
			prev_time = mytimezone.localize(prev_time)

			delta = cur_time - prev_time
			delta = delta.total_seconds()

			break

	# Proceed if delta is greater than 10-minutes
	if ( delta > 600 ):
		return True

	return False


# Monitor stock for big jumps in price and volume
# This is the main function called for every stream event that implements all the monitoring logic
def stock_monitor(stream=None, debug=False):

	if ( stream == None ):
		return False

	global prev_timestamp, gap_up_list, gap_down_list, vol_gap_up_list, vwap_list

	time_now = datetime.datetime.now(mytimezone)
	strtime_now = time_now.strftime('%Y-%m-%d %H:%M:%S.%f')

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
	if ( int(stream['timestamp']) == prev_timestamp ):
		return False

	prev_timestamp = int( stream['timestamp'] )

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

	if ( tda_gobot_helper.ismarketopen_US() == False and args.after_hours == False ):
		if ( debug == True ):
			print('Market is closed.')

		return True


	# Iterate through the stock tickers
	# We are interested in significant increases or decreases in price, and significant increases in volume
	for ticker in stocks.keys():

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Wait for some data before making decisions
		if ( len(stocks[ticker]['pricehistory']['candles']) < 10 ):
			continue

		# Get the latest candle open/close prices and volume
		cur_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
		prev_price = float( stocks[ticker]['pricehistory']['candles'][-args.gap_candles]['close'] )

		cur_vol = int( stocks[ticker]['pricehistory']['candles'][-1]['volume'] )
		prev_vol = int( stocks[ticker]['pricehistory']['candles'][-2]['volume'] )

		# Skip if price hasn't changed
		if ( cur_price == prev_price ):
			continue

		# Price Gap Up/Down
		# Check for gap up/down if price changes significantly (>1%)
		price_change = ( abs(cur_price - prev_price) / prev_price ) * 100
		if ( price_change > args.gap_threshold ):

			gap_event =	ticker + ',' + \
					str(round(prev_price, 2)) + ',' + \
					str(round(cur_price, 2)) + ',' + \
					str(round(price_change, 2)) + '%' + ',' + \
					time_now

			if ( cur_price > prev_price ):

				# These events can pile up into gap_up|down_list, so check to see
				# if this ticker has triggered already within the last ten minutes
				if ( len(gap_up_list) == 0 or gap_filter(ticker, gap_up_list) == True ):
					gap_up_list.append(gap_event)

					# Make a trade on gapping stock if args.autotrade is set
					if ( args.autotrade == True ):
						autotrade(ticker, direction='UP')

			else:

				# These events can pile up into gap_up|down_list, so check to see
				# if this ticker has triggered already within the last ten minutes
				if ( len(gap_down_list) == 0 or gap_filter(ticker, gap_down_list) == True ):
					gap_down_list.append(gap_event)

					# Make a trade on gapping stock if args.autotrade is set
					if ( args.autotrade == True ):
						autotrade(ticker, direction='DOWN')


		# Volume Gap Up
		if ( cur_vol > stocks[ticker]['avg_volume'] ):

			vol_change = ( cur_vol / stocks[ticker]['avg_volume'] ) * 100
			if ( vol_change > args.vol_threshold ):

				# Find historical average volume for the current hour
				starttime = int( stocks[ticker]['pricehistory']['candles'][0]['datetime'] )
				endtime = int( stocks[ticker]['pricehistory']['candles'][-1]['datetime'] )

				starttime = datetime.datetime.fromtimestamp(starttime/1000, tz=mytimezone)
				endtime = datetime.datetime.fromtimestamp(endtime/1000, tz=mytimezone)

				delta = time_now - starttime
				delta = delta.days - 1 # Total number of days in pricehistory, but don't count the current day

				last_day = endtime - datetime.timedelta( days=1 ) # Don't count beyond this day
				last_day = last_day.timestamp() * 1000

				cur_hr = time_now.strftime('%-H')
				vol_hr_avg = 0
				count = 0
				for key in stocks[ticker]['pricehistory']['candles']:

					if ( int(key['datetime']) >= last_day ):
						break

					tmp_hr = datetime.datetime.fromtimestamp(int(key['datetime'])/1000, tz=mytimezone).strftime('%-H')
					if ( tmp_hr != cur_hr ):
						continue

					vol_hr_avg += int( key['volume'] )
					count += 1

				vol_hr_avg = vol_hr_avg / count

				gap_event =	ticker + ',' + \
						str(round(prev_vol, 2)) + ',' + \
						str(round(cur_vol, 2)) + ',' + \
						str(round(vol_change, 2)) + '%' + ',' + \
						str(round(vol_hr_avg, 2)) + ',' + \
						time_now.strftime('%Y-%m-%d %H:%M:%S.%f')

				# These events can pile up into volume gap up list, so check to see
				# if this ticker has triggered already within the last ten minutes
				if ( len(vol_gap_up_list) == 0 or gap_filter(ticker, vol_gap_up_list) == True ):
					vol_gap_up_list.append(gap_event)


		# VWAP
		vwap, vwap_up, vwap_down =  tda_algo_helper.get_vwap( stocks[ticker]['pricehistory'] )
		vwap = float( vwap[-1] )

		# Check for case where price and VWAP are above PDC (bullish indicator),
		#  and price is declining toward VWAP.
		if ( cur_price < prev_price and
		     cur_price > vwap and
		     cur_price > stocks[ticker]['previous_day_close'] ):

			# Signal if current price is close to vwap, but only if prev_price was
			#   farther away. This is to try to avoid a lot of signals if both the
			#   current and previous price are hovering around VWAP.
			if ( ((cur_price - vwap) / cur_price) * 100 < args.vwap_threshold and
				((prev_price - vwap) / prev_price) * 100 > args.vwap_threshold ):

				# These events can pile up into vwap_list, so check vwap_list[] to see
				# if this ticker has triggered already within the last ten minutes
				if ( len(vwap_list) == 0 or gap_filter(ticker, vwap_list) == True ):

					vwap_event = 	ticker + ',' + \
							str(round(prev_price, 2)) + ',' + \
							str(round(cur_price, 2)) + ',' + \
							str(round(vwap, 2)) + ',' + \
							time_now.strftime('%Y-%m-%d %H:%M:%S.%f')

					vwap_list.append(vwap_event)

					# Make a trade on gapping stock if args.autotrade is set
					if ( args.autotrade == True ):
						autotrade(ticker, direction='UP')


	# Print results
	red = '\033[0;31m'
	green = '\033[0;32m'
	reset_color = '\033[0m'

	print("\033c")

	# GAP UP
	print('Tickers Gapping ' + green + 'UP' + reset_color)
	print('------------------------------------------------------------------------------------------')
	print('{0:10} {1:15} {2:15} {3:10} {4:10}'.format('Ticker', 'Previous_Price', 'Current_Price', '%Change', 'Time'))

	if ( len(gap_up_list) > 0 ):
		watchlist_name = 'STOCK-MONITOR-GAPUP'
		watchlist_template = { "name": watchlist_name, "watchlistItems": [] }

		for idx,evnt in enumerate( reversed(gap_up_list) ):
			ticker, prev_price, cur_price, pct_change, time = str(evnt).split(',')

			time = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
			time = mytimezone.localize(time)
			strtime = time.strftime('%Y-%m-%d %H:%M:%S.%f')

			color = ''
			if ( time <= time_now - datetime.timedelta(minutes=5) ):
				color = green

			print(color + '{0:10} {1:15} {2:15} {3:10} {4:10}'.format(ticker, prev_price, cur_price, pct_change, strtime) + reset_color)

			instrument = { "instrument": { "symbol": ticker, "assetType": "EQUITY" } }
			watchlist_template['watchlistItems'].append(instrument)

			if ( idx == args.max_tickers ):
				break

		# Update the watchlist with the latest tickers
		try:
			watchlist_id = tda_api_helper.get_watchlist_id(tda_client=tda_client, tda_account=tda_account_number, watchlist_name=watchlist_name)
			ret = tda_client.replace_watchlist(tda_account_number, watchlist_id, watchlist_template)

		except Exception as e:
			print('Error while updating watchlist ' + str(watchlist_name) + ': ' + str(e))
			pass

	else:
		print("\n")


	# GAP DOWN
	print("\n\n")
	print('Tickers Gapping ' + red + 'DOWN' + reset_color)
	print('------------------------------------------------------------------------------------------')
	print('{0:10} {1:15} {2:15} {3:10} {4:10}'.format('Ticker', 'Previous_Price', 'Current_Price', '%Change', 'Time'))

	if ( len(gap_down_list) > 0 ):
		watchlist_name = 'STOCK-MONITOR-GAPDOWN'
		watchlist_template = { "name": watchlist_name, "watchlistItems": [] }

		for idx,evnt in enumerate( reversed(gap_down_list) ):
			ticker, prev_price, cur_price, pct_change, time = str(evnt).split(',')

			time = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
			time = mytimezone.localize(time)
			strtime = time.strftime('%Y-%m-%d %H:%M:%S.%f')

			color = ''
			if ( time <= time_now - datetime.timedelta(minutes=5) ):
				color = red

			print(color + '{0:10} {1:15} {2:15} {3:10} {4:10}'.format(ticker, prev_price, cur_price, pct_change, strtime) + reset_color)

			instrument = { "instrument": { "symbol": ticker, "assetType": "EQUITY" } }
			watchlist_template['watchlistItems'].append(instrument)

			if ( idx == args.max_tickers ):
				break

		# Update the watchlist with the latest tickers
		try:
			watchlist_id = tda_api_helper.get_watchlist_id(tda_client=tda_client, tda_account=tda_account_number, watchlist_name=watchlist_name)
			ret = tda_client.replace_watchlist(tda_account_number, watchlist_id, watchlist_template)

		except Exception as e:
			print('Error while updating watchlist ' + str(watchlist_name) + ': ' + str(e))
			pass

	else:
		print("\n")



	# UNUSUAL VOLUME
	print("\n\n")
	print('Tickers: Unusual Volume')
	print('------------------------------------------------------------------------------------------')
	print('{0:10} {1:15} {2:15} {3:10} {4:10} {5:10}'.format('Ticker', 'Previous_Volume', 'Current_Volume', '%Change', 'Hourly_Avg.', 'Time'))

	if ( len(vol_gap_up_list) > 0 ):
		watchlist_name = 'STOCK-MONITOR-VOLUME'
		watchlist_template = { "name": watchlist_name, "watchlistItems": [] }

		for idx,evnt in enumerate( reversed(vol_gap_up_list) ):
			ticker, prev_price, cur_price, pct_change, hrly_avg, time = str(evnt).split(',')

			time = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
			time = mytimezone.localize(time)
			strtime = time.strftime('%Y-%m-%d %H:%M:%S.%f')

			color = ''
			if ( time <= time_now - datetime.timedelta(minutes=5) ):
				color = green

			print(color + '{0:10} {1:15} {2:15} {3:10} {4:10} {5:10}'.format(ticker, prev_price, cur_price, pct_change, hrly_avg, strtime) + reset_color)

			instrument = { "instrument": { "symbol": ticker, "assetType": "EQUITY" } }
			watchlist_template['watchlistItems'].append(instrument)

			if ( idx == args.max_tickers ):
				break

		# Update the watchlist with the latest tickers
		try:
			watchlist_id = tda_api_helper.get_watchlist_id(tda_client=tda_client, tda_account=tda_account_number, watchlist_name=watchlist_name)
			ret = tda_client.replace_watchlist(tda_account_number, watchlist_id, watchlist_template)

		except Exception as e:
			print('Error while updating watchlist ' + str(watchlist_name) + ': ' + str(e))
			pass

	else:
		print("\n")


	# VWAP
	print("\n\n")
	print('Tickers Approaching VWAP')
	print('------------------------------------------------------------------------------------------')
	print('{0:10} {1:15} {2:15} {3:10} {4:10}'.format('Ticker', 'Previous_Price', 'Current_Price', 'VWAP', 'Time'))

	if ( len(vwap_list) > 0 ):
		watchlist_name = 'STOCK-MONITOR-VWAP'
		watchlist_template = { "name": watchlist_name, "watchlistItems": [] }

		for idx,evnt in enumerate( reversed(vwap_list) ):
			ticker, prev_price, cur_price, vwap, time = str(evnt).split(',')

			time = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')
			time = mytimezone.localize(time)
			strtime = time.strftime('%Y-%m-%d %H:%M:%S.%f')

			color = ''
			if ( time <= time_now - datetime.timedelta(minutes=5) ):
				color = green

			print(color + '{0:10} {1:15} {2:15} {3:10} {4:10}'.format(ticker, prev_price, cur_price, vwap, strtime) + reset_color)

			instrument = { "instrument": { "symbol": ticker, "assetType": "EQUITY" } }
			watchlist_template['watchlistItems'].append(instrument)

			if ( idx == args.max_tickers ):
				break

		# Update the watchlist with the latest tickers
		try:
			watchlist_id = tda_api_helper.get_watchlist_id(tda_client=tda_client, tda_account=tda_account_number, watchlist_name=watchlist_name)
			ret = tda_client.replace_watchlist(tda_account_number, watchlist_id, watchlist_template)

		except Exception as e:
			print('Error while updating watchlist ' + str(watchlist_name) + ': ' + str(e))
			pass


	# Interactive Brokers Short Interest
	if ( args.ib_short == True ):
		time_now = datetime.datetime.now(mytimezone)
		date_ymd = time_now.strftime('%Y-%m-%d')

		global ib_out, ib_err

		# Only perform this check every 30-mins, don't hammer IB servers
		if ( (time_now.strftime('%-M') == 0 or time_now.strftime('%-M') == 30) or ib_out == None):
			ib_command = [str(args.ib_short_cmd), '--short_pct=' + str(args.ib_short_pct), '--ifile=' + str(os.path.dirname(args.ib_short_cmd)) + '/data/usa-' + str(date_ymd) + '.txt'  ]

			try:
				process = Popen(ib_command, stdin=None, stdout=PIPE, stderr=STDOUT, shell=False, text=True)

			except Exception as e:
				print('Exception caught: Popen(): ' + str(e))
				return False

			try:
				ib_out, ib_err = process.communicate(timeout=10)

			except TimeoutExpired:
				process.kill()
				ib_out, ib_err = process.communicate()

			except Exception as e:
				print('Exception caught: Popen.communicate(): ' + str(e))
				return False

		# Example output:
		#  Ticker,Current Avail Shorts,Previous Avail Shorts,Total Volume,Last Price,52WkHigh,52WkLow,Exchange
		#  SGOC,5000,60000,58610658,6.72,29.0,0.77,NASD
		print("\n\n")
		print('Interactive Brokers Short Interest')
		print('------------------------------------------------------------------------------------------')
		print('{0:10} {1:15} {2:15} {3:10} {4:10} {5:15}'.format('Ticker', 'Avail_Shorts', 'Prev_Shorts', 'Volume', 'Last_Price', '52Wk High/Low'))

		if ( ib_out != "" ):

			for line in str(ib_out).split("\n"):

				if ( re.search('Ticker', line) != None ):
					continue
				if ( line == "" ):
					continue

				try:
					ticker, shorts_avail, prev_shorts, volume, last_price, high, low, exchange = line.split(',')

				except Exception as e:
					print('Exception caught: line.split(): ' + str(e))
					continue

				print( '{0:10} {1:15} {2:15} {3:10} {4:10} {5:15}'.format(ticker, shorts_avail, prev_shorts, volume, last_price, high+'/'+low) )


	return True


# MAIN
# Log into tda-api and run the stream client
tda_api_key = os.environ['tda_consumer_key']
tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'

# Initializes and reads from TDA stream API
async def read_stream():
	await asyncio.wait_for( stream_client.login(), 10 )
	await asyncio.wait_for( stream_client.quality_of_service(StreamClient.QOSLevel.EXPRESS), 10 )

	stream_client.add_chart_equity_handler(
		lambda msg: stock_monitor(msg, args.debug) )

	await asyncio.wait_for( stream_client.chart_equity_subs(stocks.keys()), 10 )

	while True:
		await asyncio.wait_for( stream_client.handle_message(), 120 )


# Initialize log file handle
if ( args.autotrade == True ):
	logfile = './logs/gapcheck.log'
	try:
		log_fh = open(logfile, 'a')

	except Exception as e:
		print('Unable to open log file ' + str(logfile) + ', exiting.')
		sys.exit(1)


# Initialize the watchlists
try:
	tda_client = tda_api.auth.client_from_token_file(tda_pickle, tda_api_key)

except Exception as e:
	print('Exception caught: client_from_token_file(): unable to log in using tda-client: ' + str(e))
	sys.exit(0)

for wlist in watchlists:
	try:
		tda_api_helper.delete_watchlist_byname(tda_client, tda_account_number, watchlist_name=wlist)
	except:
		pass

	time.sleep(1)

	watchlist_template['name'] = wlist
	try:
		ret = tda_client.create_watchlist( tda_account_number, watchlist_template )
		if ( ret.status_code != 201 ):
			print('Error: tda_client.create_watchlist(' + str(wlist) + '): returned status code ' + str(ret.status_code))
	except:
		pass


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

