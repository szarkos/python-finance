#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-buy-stock.py <ticker> <investment-in-usd> [--short]

import robin_stocks.tda as tda
import os, sys
import argparse
import tda_gobot_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=-1, type=float)
parser.add_argument("--account_number", help='Account number to use (default: None)', default=None, type=int)
parser.add_argument("--force", help='Force purchase of the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--notmarketclosed", help="Cancel order and exit if US stock market is closed", action="store_true")
parser.add_argument("--no_fill_wait", help="Do not wait for the order to be filled", action="store_true")
parser.add_argument("--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

debug = 1			# Should default to 0 eventually, testing for now
if args.debug:
	debug = 1

if ( args.stock_usd == -1 ):
	print('Error: please enter stock amount (USD) to invest')
	sys.exit(1)

fillwait = True
if ( args.no_fill_wait == True ):
	fillwait = False

stock		= args.stock
stock_usd	= args.stock_usd

if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
	print('Canceled order to purchase $' + str(stock_usd) + ' of stock ' + str(stock) + ', because market is closed and --notmarketclosed was set')
	sys.exit(1)


# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file')
	sys.exit(1)

try:
        if ( args.account_number != None ):
                tda_account_number = args.account_number
        else:
                tda_account_number = int( os.environ["tda_account_number"] )

except:
        print('Error: account number not found, exiting.')
        sys.exit(1)

passcode				= os.environ["tda_encryption_passcode"]
tda_gobot_helper.tda			= tda
tda_gobot_helper.tda_account_number	= tda_account_number
tda_gobot_helper.passcode 		= passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure')
	sys.exit(1)

# Fix up and sanity check the stock symbol before proceeding
stock = tda_gobot_helper.fix_stock_symbol(stock)
ret = tda_gobot_helper.check_stock_symbol(stock)
if ( isinstance(ret, bool) and ret == False ):
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
	sys.exit(1)

if ( tda_gobot_helper.check_blacklist(stock) == True ):
	if ( args.force == False ):
		print('(' + str(stock) + ') Error: stock ' + str(stock) + ' found in blacklist file, exiting.')
		sys.exit(1)
	else:
		print('(' + str(stock) + ') Warning: stock ' + str(stock) + ' found in blacklist file.')

# Calculate stock quantity from investment amount
last_price = 0
last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
if ( isinstance(last_price, bool) and last_price == False ):
	print('Error: get_lastprice(' + str(stock) + ') returned False')
	sys.exit(1)

stock_qty = int( float(stock_usd) / float(last_price) )

# Purchase stock, set orig_base_price to the price that we purchases the stock
if ( tda_gobot_helper.ismarketopen_US() == True ):
	if ( args.short == True ):
		print('SHORTING ' + str(stock_qty) + ' shares of ' + str(stock))
		data = tda_gobot_helper.short_stock_marketprice(stock, stock_qty, fillwait=fillwait, account_number=tda_account_number, debug=True)
		if ( data == False ):
			print('Error: Unable to short "' + str(stock) + '"', file=sys.stderr)
			sys.exit(1)

	else:
		print('PURCHASING ' + str(stock_qty) + ' shares of ' + str(stock))
		data = tda_gobot_helper.buy_stock_marketprice(stock, stock_qty, fillwait=fillwait, account_number=tda_account_number, debug=True)
		if ( data == False ):
			print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
			sys.exit(1)

	if ( data != False ):
		print('Success!')

else:
	print('Error: stock ' + str(stock) + ' not purchased because market is closed, exiting.')
	sys.exit(1)


sys.exit(0)
