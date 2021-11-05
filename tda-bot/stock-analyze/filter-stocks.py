#!/usr/bin/python3 -u

# Command-line options:
#  ./filter-stocks.py --stocks=<comma separated list of tickers>
#
import os, sys
import re
import datetime
import pickle
import argparse

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper
import tda_algo_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='Stock tickers to check, comma delimited', default='', required=True, type=str)
parser.add_argument("--blacklist", help="Filter out blacklisted stocks", action="store_true")
parser.add_argument("--min_natr", help='Print out the stocks that have a daily NATR greater than or equal to this value', default=None, type=float)
parser.add_argument("--natr_start_day", help='Start day to begin processing min_natr', default=None, type=str)
parser.add_argument("--high_volatility", help="Filter out stocks whose 52-week high is more than 2x the 52-week low", action="store_true")
parser.add_argument("--verbose", help="Enable verbose output", action="store_true")
parser.add_argument("--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

if ( args.stocks == '' ):
	sys.exit(0)

tickers = re.sub('[\s\t]', '', args.stocks)
tickers = tickers.split(',')

print()

# Check a ticker to see if it is currently blacklisted
if ( args.blacklist == True ):
	arr_size = len(tickers)
	for idx,sym in enumerate( tickers ):
		if ( tda_gobot_helper.check_blacklist(sym) == True ):
			continue

		print(str(sym), end='')
		if ( idx < arr_size-1 ):
			print(',', end='')

# Min NATR
elif ( args.min_natr != None ):

	natr_period	= 3 # Use 3-day period to calculate NATR
	natr_stocks	= []

	for sym in tickers:
		try:
			with open('./daily-csv/' + str(sym) + '-daily-2019-2021.pickle', 'rb') as handle:
				data_daily = handle.read()
				data_daily = pickle.loads(data_daily)

		except Exception as e:
			print('Unable to read daily candle file (./daily_csv/' + str(sym) + '-daily-2019-2021.pickle): ' + str(e), file=sys.stderr)
			continue


		# Daily candle files typically contain two years of data, so we can use natr_start_day
		#  to only look at a more recent set of candles.
		if ( args.natr_start_day != None ):
			try:
				min_day = datetime.datetime.strptime(args.natr_start_day, '%Y-%m-%d')

			except Exception as e:
				print('Caught exception: ' + str(e), file=sys.stderr)
				continue

		else:
			min_day = datetime.datetime.fromtimestamp(int(data_daily['candles'][0]['datetime'])/1000)

		# Calculate the NATR
		atr_d   = []
		natr_d  = []
		try:
			atr_d, natr_d = tda_algo_helper.get_atr( pricehistory=data_daily, period=natr_period )

		except Exception as e:
			print('Caught exception: get_atr(' + str(sym) + '): ' + str(e), file=sys.stderr)

		# Count any day where the tickers has an NATR higher than min_natr
		count = 0
		for idx in range(0, len(data_daily['candles'])):
			if ( idx < 2 ):
				continue

			day = datetime.datetime.fromtimestamp(int(data_daily['candles'][idx]['datetime'])/1000)
			if ( day < min_day ):
				continue

			if ( natr_d[idx-(natr_period-1)] >= args.min_natr ):
				count += 1

		if ( args.verbose == True ):
			print(str(sym) + ': ' + str(count))

		if ( count > 0 ):
			natr_stocks.append(sym)

	print( ','.join(natr_stocks) )
	sys.exit(0)


# Filter high-volatility stocks
elif ( args.high_volatility == True ):

	import robin_stocks.tda as tda

	# Initialize and log into TD Ameritrade
	from dotenv import load_dotenv
	if ( load_dotenv(dotenv_path=parent_path+'/../.env') != True ):
		print('Error: unable to load .env file')
		sys.exit(1)

	tda_account_number = os.environ["tda_account_number"]
	passcode = os.environ["tda_encryption_passcode"]

	tda_gobot_helper.tda = tda
	tda_gobot_helper.tda_account_number = tda_account_number
	tda_gobot_helper.passcode = passcode

	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure')
		sys.exit(1)

	try:
		data,err = tda.stocks.get_quotes(args.stocks, True)

	except Exception as e:
		print('Exception caught: ' + str(e))

	if ( err != None ):
		print('Error: get_quotes(' + str(args.stocks) + '): ' + str(err), file=sys.stderr)
		sys.exit(1)
	elif ( data == {} ):
		print('Error: get_quotes(' + str(args.stocks) + '): Empty data set', file=sys.stderr)
		sys.exit(1)

	list = ''
	for ticker in data:
		low = float( data[ticker]['52WkLow'] )
		cur = float( data[ticker]['lastPrice'] )

		# Compare the current price to the 52-week low
		# Remove the stock if the current price is more than twice the 52-week low
		if ( cur < low * 2):
			list += str(ticker) + ','

	list = list.strip(',')
	print(list)


print()
sys.exit(0)

