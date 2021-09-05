#!/usr/bin/python3 -u

# Command-line options:
#  ./filter-blacklist.py --stocks=<comma separated list of tickers>
#
import os,sys
import re
import argparse

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='Stock tickers to check, comma delimited', default='', required=True, type=str)
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

if ( args.stocks == '' ):
	sys.exit(0)

tickers = re.sub('[\s\t]', '', args.stocks)
tickers = tickers.split(',')

print()

# Check a ticker to see if it is currently blacklisted
arr_size = len(tickers)
for idx,sym in enumerate( tickers ):
	if ( tda_gobot_helper.check_blacklist(sym) == True ):
		continue

	print(str(sym), end='')
	if ( idx < arr_size-1 ):
		print(',', end='')

print()
