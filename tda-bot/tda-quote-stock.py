#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-quote-stock.py <ticker>
#
# Returns stock information as obtained from TDA's Get Quote API (https://api.tdameritrade.com/v1/marketdata/)
#
# Example: ./tda-quote-stock.py AAPL --pretty

import os, sys
import time, datetime, pytz
import argparse

import robin_stocks.tda as tda

import tda_gobot_helper
import tda_algo_helper


# Parse and check variables
parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=False)
group.add_argument("stock", help='Stock ticker to check', nargs='?', default='', type=str)
group.add_argument("--stocks", help='Stock tickers to check, comma delimited', default='', type=str)

parser.add_argument("-c", "--checkticker", help="Check if ticker is valid", action="store_true")
parser.add_argument("-p", "--pretty", help="Pretty print the stock data", action="store_true")
parser.add_argument("-n", "--lines", help="Number of lines to output (relevant for indicators like vwap, etc.)", default=10, type=int)
parser.add_argument("--skip_check", help="Skip fixup and check of stock ticker", action="store_true")

parser.add_argument("--rawquote", help="Get the raw quote info from the API", action="store_true")
parser.add_argument("--quote", help="Get the latest price quote", action="store_true")
parser.add_argument("--history", help="Get price history", action="store_true")
parser.add_argument("--vwap", help="Get VWAP values", action="store_true")
parser.add_argument("--volatility", help="Get the historical volatility for a stock", action="store_true")
parser.add_argument("--get_instrument", help="Stock ticker to obtain instrument data", action="store_true")

parser.add_argument("--is_market_open", help="Check if US market is open. Use --market_time to specify day/time, or current day/time will be used", action="store_true")
parser.add_argument("--market_datetime", help='Day to check if market is open. Must be in US/Eastern timezone, and in the format "HH-MM-DD hh:mm:ss"', default=None, type=str)

parser.add_argument("--blacklist", help="Blacklist stock ticker for one month", action="store_true")
parser.add_argument("--permanent", help="Blacklist stock ticker permanently", action="store_true")
parser.add_argument("--check_blacklist", help="Blacklist stock ticker for one month", action="store_true")
parser.add_argument("--clean_blacklist", help="Clean blacklist file, remove stale entries", action="store_true")

parser.add_argument("--stats", help="Get N-day high, low, avg. price stats", action="store_true")
parser.add_argument("--freq", help="Frequency to request history data (typically this should be 1, default is None)", default=None, type=int)
parser.add_argument("--p_type", help="Period type to request history data (default: day)", default="day", type=str)
parser.add_argument("--f_type", help="Frequency type to request history data (default: minute)", default="minute", type=str)
parser.add_argument("--period", help="Period to request history data (default: None)", default=None, type=str)
parser.add_argument("--start_date", help="Number of days to subtract from end_date (default: None)", default=None, type=int)
parser.add_argument("--end_date", help="Epoch (in milliseconds) for the end date of date to retrieve (use -1 for most recent) (default: None)", default=None, type=int)
parser.add_argument("--extended_hours", help="If extended trading hours are needed (default: False)", action="store_true")

parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

debug = 0			# Should default to 0 eventually, testing for now
if args.debug:
	debug = 1

mytimezone = pytz.timezone("US/Eastern")

if ( args.end_date == -1 ):
	args.end_date = datetime.datetime.now( mytimezone )
	args.end_date = int( args.end_date.timestamp() * 1000 )
if ( args.start_date != None ):
	end = datetime.datetime.fromtimestamp(float(args.end_date)/1000, tz=mytimezone)
	args.start_date = end - datetime.timedelta( days=args.start_date )
	args.start_date = int( args.start_date.timestamp() * 1000 )

if ( args.start_date == None and args.end_date == None and args.period == None ):
	args.period = 1

# No need to log into TDA just to write to or check the blacklist, unless we need to verify
#  the ticker.
skip_login = False
if ( (args.blacklist == True or args.check_blacklist == True or args.clean_blacklist == True) and args.skip_check == True ):
	skip_login = True

if ( args.clean_blacklist == False and args.is_market_open == False and args.stock == '' and args.stocks == '' ):
	print('tda-quote-stock.py: error: one of the arguments stock --stocks is required')
	sys.exit(0)

# Initialize and log into TD Ameritrade
if ( skip_login == False ):
	from dotenv import load_dotenv
	if ( load_dotenv() != True ):
		print('Error: unable to load .env file')
		exit(1)

	tda_account_number = os.environ["tda_account_number"]
	passcode = os.environ["tda_encryption_passcode"]

	tda_gobot_helper.tda = tda
	tda_gobot_helper.tda_account_number = tda_account_number
	tda_gobot_helper.passcode = passcode

	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure')
		exit(1)

# Fix up and sanity check the stock symbol before proceeding
stock = args.stock
if ( args.stock != '' ):
	if ( args.skip_check == False ):
		stock = tda_gobot_helper.fix_stock_symbol(stock)
		ret = tda_gobot_helper.check_stock_symbol(stock)
		if ( isinstance(ret, bool) and ret == False ):
			print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting', file=sys.stderr)
			exit(1)

		if ( args.checkticker == True ): # --checkticker means we only wanted to validate the stock ticker
			exit(0)

else:
	stock = args.stocks

## Get stock quote and print the results
if ( args.get_instrument == True ):

	# Get the fundamental data from get_quote API
	try:
		data,err = tda.stocks.search_instruments(stock, 'fundamental', True)

	except Exception as e:
		print('Exception caught: ' + str(e))

	if ( err != None ):
		print('Error: search_instruments(' + str(stock) + '): ' + str(err), file=sys.stderr)
		exit(1)
	elif ( data == {} ):
		print('Error: search_instruments(' + str(stock) + '): Empty data set', file=sys.stderr)
		exit(1)

	if ( args.pretty == True ):
		import pprint
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(data)
	else:
		print(data, end='')

	exit(0)


elif ( args.quote == True ):

	try:
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)

	except Exception as e:
		print('Caught Exception: get_lastprice(' + str(ticker) + '): ' + str(e), file=sys.stderr)
		exit(1)

	if ( last_price == False ):
		exit(1)

	print( str(stock) + "\t" + str(last_price))
	exit(0)


# Blacklist a ticker
# Use --permanent to permanently blacklist a ticker
elif ( args.blacklist == True ):
	tda_gobot_helper.write_blacklist(stock, 0, 0, 0, 0, 0, permanent=args.permanent)
	exit(0)

# Check a ticker to see if it is currently blacklisted
elif ( args.check_blacklist == True ):
	print( tda_gobot_helper.check_blacklist(stock) )
	exit(0)

# Check a ticker to see if it is currently blacklisted
elif ( args.clean_blacklist == True ):
	tda_gobot_helper.clean_blacklist(debug=True)
	exit(0)


elif ( args.history == True ):

	# Pull the stock history
	data, epochs = tda_gobot_helper.get_pricehistory(stock, args.p_type, args.f_type, args.freq, args.period, args.start_date, args.end_date, needExtendedHoursData=args.extended_hours, debug=False)
	if ( data == False ):
		exit(1)

	if ( args.pretty == True ):
		for idx,key in enumerate(data['candles']):
			data['candles'][idx]['datetime'] = datetime.datetime.fromtimestamp(float(data['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

		import pprint
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(data)
	else:
		print(data)


	exit(0)


elif ( args.vwap == True ):

	# Pull the stock history
	data, epochs = tda_gobot_helper.get_pricehistory(stock, args.p_type, args.f_type, args.freq, args.period, args.start_date, args.end_date, needExtendedHoursData=True, debug=False)
	if ( data == False ):
		exit(1)

	try:
		vwap, vwap_up, vwap_down =  tda_algo_helper.get_vwap(data)

	except Exception as e:
		print('Caught Exception: get_vwap(' + str(stock) + '): get_vwap(): ' + str(e), file=sys.stderr)
		exit(1)

	if ( isinstance(vwap, bool) and vwap == False ):
		print('Error: get_vwap(' + str(stock) + ') returned false - no data', file=sys.stderr)
		exit(1)

	skip = len(vwap) - args.lines
	date_counter = len(data['candles']) - args.lines
	for i in range(skip, len(vwap), 1):
		date = datetime.datetime.fromtimestamp(float(data['candles'][date_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
		print( str(stock) + "\t" + str(date) + "\t" + str(vwap.loc[i, 'vwap']) )
		date_counter -= 1

	exit(0)


elif ( args.volatility == True ):

	v = tda_algo_helper.get_historic_volatility(stock, period=21)
	print( 'NumPy: ' + str(round(v, 2) * 100 ) + "%\n" )

	v, data = tda_algo_helper.get_historic_volatility_ti(stock, period=21, type='close')
	if ( isinstance(v, bool) and v == False ):
		print('Error: get_historical_volatility(' + str(ticker) + ') returned false - no data', file=sys.stderr)
		exit(1)

	time.sleep(0.5)

	lines = args.lines + 1
	if ( lines > len(v) ):
		lines = len(v)

	print('Tulipy ')
	for i in range(lines, 1, -1):
		date = datetime.datetime.fromtimestamp(float(data['candles'][-i]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
		print( str(stock) + "\t" + str(date) + "\t" + str(v[-i]) )


# Check if market is open
elif ( args.is_market_open == True ):
	if ( args.market_datetime == None ):
		args.market_datetime = datetime.datetime.now( mytimezone )
	else:
		args.market_datetime = datetime.datetime.strptime(args.market_datetime, '%Y-%m-%d %H:%M:%S')
		args.market_datetime = mytimezone.localize(args.market_datetime)

	print( tda_gobot_helper.ismarketopen_US(date=args.market_datetime) )


else:
	args.rawquote = True


if ( args.rawquote == True ):

	try:
		data,err = tda.stocks.get_quotes(stock, True)
	except Exception as e:
		print('Exception caught: ' + str(e))

	if ( err != None ):
		print('Error: get_quote(' + str(stock) + '): ' + str(err), file=sys.stderr)
		exit(1)
	elif ( data == {} ):
		print('Error: get_quote(' + str(stock) + '): Empty data set', file=sys.stderr)
		exit(1)

	if ( args.pretty == True ):
		import pprint
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(data)
	else:
		print(data, end='')



exit(0)
