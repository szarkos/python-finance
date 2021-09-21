#!/usr/bin/python3 -u

# This is a test script to test tda_gobot_helper.get_keylevels().
# It is also helpful for printing the key levels for a stock ticker
#  and optionally plotting them using matplot.
#
# By default the script will check two years of *weekly* candles.

import sys, os
import argparse
import robin_stocks.tda as tda
import tda_gobot_helper


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to check')
parser.add_argument("--no_filter", help='Do not use ATR to filter and reduce noise in the results', action="store_true")
parser.add_argument("--plot", help='Plot the result', action="store_true")
parser.add_argument("--atr_period", help='Plot the result', default=14, type=int)
parser.add_argument("--use_daily", help='Use daily candles instead of weekly', action="store_true")
args = parser.parse_args()


# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
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

filter = True
if ( args.no_filter == True ):
	filter = False

# get_pricehistory() variables
f_type = 'weekly'
if ( args.use_daily == True ):
	f_type = 'daily'

p_type = 'year'
period = '2'
freq = '1'

try:
	pricehistory, epochs = tda_gobot_helper.get_pricehistory(args.stock, p_type, f_type, freq, period, needExtendedHoursData=False)

except Exception as e:
	print('Caught Exception: ' + str(e))
	sys.exit(0)


# Call get_keylevels() and print the result
# If plot==True then a plot will appear before key levels are printed on the screen
long_support = []
long_resistance = []
try:
	long_support,long_resistance = tda_gobot_helper.get_keylevels(pricehistory=pricehistory, atr_period=args.atr_period, filter=filter, plot=args.plot)

except Exception as e:
	print('Caught exception: get_keylevels(' + str(args.stock) + '): ' + str(e))
	sys.exit(1)

if ( isinstance(long_support, bool) and long_support == False ):
	print('Error: get_keylevels(' + str(args.stock) + '): returned False')
	sys.exit(1)

print('Key levels for stock ' + str(args.stock) + ':')
print('Long support: ' + str(long_support))
print('Long resistance: ' + str(long_resistance))


sys.exit(0)

