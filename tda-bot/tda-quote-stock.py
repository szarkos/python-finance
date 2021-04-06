#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-quote-stock.py <ticker>
#
# Returns stock information as obtained from TDA's Get Quote API (https://api.tdameritrade.com/v1/marketdata/)
#
# Example: ./tda-quote-stock.py AAPL --pretty

import robin_stocks.tda as tda
import os, sys, time
import argparse
import tda_gobot_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("-c", "--checkticker", help="Check if ticker is valid", action="store_true")
parser.add_argument("-p", "--pretty", help="Pretty print the stock data", action="store_true")
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

debug = 0			# Should default to 0 eventually, testing for now
if args.debug:
	debug = 1

stock = args.stock

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
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
	exit(1)

if ( args.checkticker == True ): # --checkticker means we only wanted to validate the stock ticker
	exit(0)


## Get stock quote and print the results
time.sleep(0.2) # avoid hammering the API
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
