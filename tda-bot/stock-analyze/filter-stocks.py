#!/usr/bin/python3 -u

# Command-line options:
#  ./filter-stocks.py --stocks=<comma separated list of tickers>
#
import os, sys
import re
import argparse

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='Stock tickers to check, comma delimited', default='', required=True, type=str)
parser.add_argument("--blacklist", help="Filter out blacklisted stocks", action="store_true")
parser.add_argument("--high_volatility", help="Filter out stocks whose 52-week high is more than 2x the 52-week low", action="store_true")
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
		print('Error: get_quote(' + str(stock) + '): ' + str(err), file=sys.stderr)
		sys.exit(1)
	elif ( data == {} ):
		print('Error: get_quote(' + str(stock) + '): Empty data set', file=sys.stderr)
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

