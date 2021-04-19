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


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("-c", "--checkticker", help="Check if ticker is valid", action="store_true")
parser.add_argument("-p", "--pretty", help="Pretty print the stock data", action="store_true")
parser.add_argument("-n", "--lines", help="Number of lines to output (relevant for indicators like vwap, rsi, etc.)", default=10, type=int)

parser.add_argument("--rawquote", help="Get the raw quote info from the API", action="store_true")
parser.add_argument("--quote", help="Get the latest price quote", action="store_true")
parser.add_argument("--history", help="Get price history", action="store_true")
parser.add_argument("--vwap", help="Get VWAP values", action="store_true")
parser.add_argument("--rsi", help="Get RSI values", action="store_true")
parser.add_argument("--stochrsi", help="Get stochastic RSI values", action="store_true")

parser.add_argument("--rsi_period", help="RSI period (default: 14)", default=14, type=int)
parser.add_argument("--stochrsi_period", help="Stoch RSI period (default: 128)", default=128, type=int)
parser.add_argument("--rsi_slow", help="RSI slow period (default: 3)", default=3, type=int)
parser.add_argument("--rsi_k_period", help="RSI K period (default: 128)", default=128, type=int)
parser.add_argument("--rsi_d_period", help="RSI D period (default: 3)", default=3, type=int)
parser.add_argument("--rsi_type", help="RSI calc type (default: ohlc4)", default="ohlc4", type=str)

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

stock = args.stock
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

# Initialize and log into TD Ameritrade
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
stock = tda_gobot_helper.fix_stock_symbol(stock)
if ( tda_gobot_helper.check_stock_symbol(stock) != True ):
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting', file=sys.stderr)
	exit(1)

if ( args.checkticker == True ): # --checkticker means we only wanted to validate the stock ticker
	exit(0)

## Get stock quote and print the results
time.sleep(0.2) # avoid hammering the API


if ( args.quote == True ):

	try:
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)

	except Exception as e:
		print('Caught Exception: get_lastprice(' + str(ticker) + '): ' + str(e), file=sys.stderr)
		exit(1)

	if ( last_price == False ):
		exit(1)

	print( str(stock) + "\t" + str(last_price))
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
		vwap = tda_gobot_helper.get_vwap(data)

	except Exception as e:
		print('Caught Exception: rsi_analyze(' + str(stock) + '): get_vwap(): ' + str(e), file=sys.stderr)
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


elif ( args.rsi == True ):

	# Pull the stock history
	data, epochs = tda_gobot_helper.get_pricehistory(stock, args.p_type, args.f_type, args.freq, args.period, args.end_date, args.start_date, needExtendedHoursData=True, debug=False)
	if ( data == False ):
		exit(1)

	try:
		rsi = tda_gobot_helper.get_rsi(data, args.rsi_period, args.rsi_type, debug=False)

	except Exception as e:
		print('Caught Exception: rsi_analyze(' + str(stock) + '): get_rsi(): ' + str(e), file=sys.stderr)
		exit(1)

	if ( isinstance(rsi, bool) and rsi == False ):
		print('Error: get_rsi(' + str(stock) + ') returned false - no data', file=sys.stderr)
		exit(1)

	for i in range(args.lines+1, 1, -1):
		date = datetime.datetime.fromtimestamp(float(data['candles'][-i]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
		print( str(stock) + "\t" + str(date) + "\t" + str(rsi[-i]) )

	exit(0)


elif (args.stochrsi == True ):

	# Pull the stock history
	data, epochs = tda_gobot_helper.get_pricehistory(stock, args.p_type, args.f_type, args.freq, args.period, args.start_date, args.end_date, needExtendedHoursData=True, debug=False)
	if ( data == False ):
		exit(1)

	try:
		stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(data, rsi_period=args.rsi_period, stochrsi_period=args.stochrsi_period, type=args.rsi_type, slow_period=args.rsi_slow, rsi_k_period=args.rsi_k_period, rsi_d_period=args.rsi_d_period, debug=False)

	except:
		print('Caught Exception: rsi_analyze(' + str(stock) + '): get_stochrsi(): ' + str(e), file=sys.stderr)
		exit(1)

	if ( isinstance(stochrsi, bool) and stochrsi == False ):
		print('Error: get_stochrsi(' + str(stock) + ') returned false - no data', file=sys.stderr)
		exit(1)

	for i in range(args.lines+1, 1, -1):
		date = datetime.datetime.fromtimestamp(float(data['candles'][-i]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
		print( str(stock) + "\t" + str(date) + "\t" + str(stochrsi[-i]) + "\t" + str(rsi_k[-i]) + "\t" + str(rsi_d[-i]) )

	exit(0)


else:
	args.rawquote = True


if ( args.rawquote == True ):
	data,err = tda.stocks.get_quote(stock, True)
	if ( err != None ):
		print('Error: get_quote(' + str(stock) + '): ' + str(err), file=sys.stderr)
		exit(1)
	elif ( data == {} ):
		print('Error: get_quote(' + str(stock) + '): Empty data set', file=sys.stderr)
		exit(1)

	if ( data[stock]['delayed'] == 'true' ):
		print('Warning: get_quote(' + str(stock) + '): quote data delayed')

	if ( args.pretty == True ):
		import pprint
		pp = pprint.PrettyPrinter(indent=4)
		pp.pprint(data)
	else:
		print(data)



exit(0)
