#!/usr/bin/python3 -u

# This is a test script to test tda_gobot_helper.get_keylevels().
# It is also helpful for printing the key levels for a stock ticker
#  and optionally plotting them using matplot.
#
# By default the script will check two years of *weekly* candles.

import sys, os
from datetime import datetime, timedelta
import pytz
import argparse
import re

from collections import OrderedDict

import robin_stocks.tda as tda
import tda_gobot_helper
import tda_algo_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to check', type=str)
parser.add_argument("--no_filter", help='Do not use ATR to filter and reduce noise in the results', action="store_true")
parser.add_argument("--plot", help='Plot the result', action="store_true")
parser.add_argument("--atr_period", help='ATR period to use when filtering results', default=14, type=int)
parser.add_argument("--use_daily", help='Use daily candles instead of weekly', action="store_true")

parser.add_argument("--weekly_threshold", help='Count threshold when outputing weekly unfiltered results (Default: 2)', default=2, type=int)
parser.add_argument("--daily_threshold", help='Count threshold when outputing daily unfiltered results (Default: 8)', default=8, type=int)
parser.add_argument("--time_addinity", help='Do not filter based on weekly/daily count threshold if previous occurance of the keylevel is less than this number of days from today (Default: 21)', default=21, type=int)

parser.add_argument("--tos_indicator", help='Output a valid ThinkOrSwim indicator', action="store_true")

args = parser.parse_args()

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file')
	sys.exit(1)

tda_account_number			= int( os.environ["tda_account_number"] )
passcode				= os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda			= tda
tda_gobot_helper.tda_account_number	= tda_account_number
tda_gobot_helper.passcode		= passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure')
	sys.exit(1)

mytimezone	= pytz.timezone("US/Eastern")
time_now	= datetime.now(mytimezone)

# get_pricehistory() for weekly and daily candles
p_type	= 'year'
period	= '2'
freq	= '1'

try:
	pricehistory_weekly, epochs = tda_gobot_helper.get_pricehistory(args.stock, p_type, 'weekly', freq, period, needExtendedHoursData=False)
	pricehistory_daily, epochs = tda_gobot_helper.get_pricehistory(args.stock, p_type, 'daily', freq, period, needExtendedHoursData=False)

except Exception as e:
	print('Caught Exception: get_pricehistory(' + str(ticker) + '): ' + str(e), file=sys.stderr)
	sys.exit(1)

# get_pricehistory() for 1-minute candles, used to calculate the daily volume profile
p_type	= 'day'
period	= None
f_type	= 'minute'
freq	= '1'

time_now	= datetime.now( mytimezone )
time_prev	= time_now - timedelta( days=4 )

# Make sure start and end dates don't land on a weekend
#  or outside market hours
time_now	= tda_gobot_helper.fix_timestamp(time_now)
time_prev	= tda_gobot_helper.fix_timestamp(time_prev)

time_now_epoch	= int( time_now.timestamp() * 1000 )
time_prev_epoch	= int( time_prev.timestamp() * 1000 )

try:
	pricehistory_1min, epochs = tda_gobot_helper.get_pricehistory(args.stock, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

except Exception as e:
	print('Caught Exception: get_pricehistory(' + str(ticker) + '): ' + str(e), file=sys.stderr)
	sys.exit(1)


# Call get_keylevels() and print the result
# If plot==True then a plot will appear before key levels are printed on the screen
long_support_filtered		= []
long_resistance_filtered	= []
long_support_unfiltered		= []
long_resistance_unfiltered	= []
long_support_daily_filtered	= []
long_resistance_daily_filtered	= []

kl = dt = count = 0
try:
	long_support_filtered, long_resistance_filtered			= tda_algo_helper.get_keylevels(pricehistory=pricehistory_weekly, atr_period=args.atr_period, filter=True, plot=args.plot)
	long_support_unfiltered, long_resistance_unfiltered		= tda_algo_helper.get_keylevels(pricehistory=pricehistory_weekly, atr_period=args.atr_period, filter=False, plot=args.plot)

	long_support_daily_filtered, long_resistance_daily_filtered	= tda_algo_helper.get_keylevels(pricehistory=pricehistory_daily, atr_period=args.atr_period, filter=True, plot=args.plot)
	long_support_daily_unfiltered, long_resistance_daily_unfiltered	= tda_algo_helper.get_keylevels(pricehistory=pricehistory_daily, atr_period=args.atr_period, filter=False, plot=args.plot)

except Exception as e:
	print('Caught exception: get_keylevels(' + str(args.stock) + '): ' + str(e))
	sys.exit(1)

if ( isinstance(long_support_filtered, bool) or isinstance(long_support_unfiltered, bool) or
		isinstance(long_support_daily_filtered, bool) or isinstance(long_support_daily_unfiltered, bool) ):
	print('Error: get_keylevels(' + str(args.stock) + '): returned False')
	sys.exit(1)

# Set long_support/long_resistance based on whether the user requested
#  weekly or daily candles, filtered or unfiltered results
if ( args.use_daily == True ):
	long_support	= long_support_daily_filtered
	long_resistance	= long_resistance_daily_filtered
	if ( args.no_filter == True ):
		long_support	= long_support_daily_unfiltered
		long_resistance	= long_resistance_daily_unfiltered

else:
	long_support	= long_support_filtered
	long_resistance	= long_resistance_filtered
	if ( args.no_filter == True ):
		long_support	= long_support_unfiltered
		long_resistance	= long_resistance_unfiltered

# Get Value Area High (VAH) and Value Area Low (VAL) from the most recent trading day
date_1 = date_2 = None
val_1 = vah_1 = val_2 = vah_2 = None
if ( re.search('\$', args.stock) != None and pricehistory_1min['candles'][-1]['volume'] == 0 ):
	# Indicators will not have volume information along with OHLC data, so we cannot
	#  calculate the Volume Profile (Market Profile)
	print('Ticker ' + str(args.stock) + ' appears to be an indicator with no volume information, skipping Volume Profile', file=sys.stderr)

else:
	try:
		mprofile = OrderedDict()
		mprofile = tda_algo_helper.get_market_profile(pricehistory=pricehistory_1min, close_type='hl2', mp_mode='vol', tick_size=0.01)

	except Exception as e:
		print('Caught Exception: get_market_profile(' + str(args.stock) + '): ' + str(e), file=sys.stderr)
		sys.exit(1)

	#last_date = next(reversed(mprofile))
	date_1	= list(mprofile.keys())[-1]
	date_2	= list(mprofile.keys())[-2]
	val_1	= mprofile[date_1]['val']
	vah_1	= mprofile[date_1]['vah']
	val_2	= mprofile[date_2]['val']
	vah_2	= mprofile[date_2]['vah']


# Print the results or output a ToS indicator
if ( args.tos_indicator == False ):

	print('Key levels for stock ' + str(args.stock))
	print('Long support:')
	tmp = {}
	for kl,dt,count in long_support:
		tmp[dt] = ( kl,count )

	for dt in sorted( tmp.keys() ):
		kl	= tmp[dt][0]
		count	= tmp[dt][1]
		dt	= datetime.fromtimestamp(int(dt)/1000, tz=mytimezone).strftime('%Y-%m-%d')
		print(str(dt) + ': ' + str(kl) + ' (' + str(count) + ')')

	print()
	print('Long resistance:')
	tmp = {}
	for kl,dt,count in long_resistance:
		tmp[dt] = ( kl,count )

	for dt in sorted( tmp.keys() ):
		kl	= tmp[dt][0]
		count	= tmp[dt][1]
		dt = datetime.fromtimestamp(int(dt)/1000, tz=mytimezone).strftime('%Y-%m-%d')
		print(str(dt) + ': ' + str(kl) + ' (' + str(count) + ')')


	print()
	print('VAH (' + str(last_date) + '): ' + str(vah))
	print('VAL (' + str(last_date) + '): ' + str(val))

# ToS indicator
else:

	# Weekly Filtered
	print( '# Key levels for stock ' + str(args.stock) )
	print( '# Generated by tda-keylevels.py' + "\n" )

	print( '# WEEKLY FILTERED SUPPORT AND RESISTANCE' )
	tmp = {}
	for kl,dt,count in long_support_filtered+long_resistance_filtered:
		tmp[dt] = ( kl,count )

	counter = 1
	for dt in sorted( tmp.keys() ):
		kl = tmp[dt][0]
		print( 'plot wf_' + str(counter) + ' = ' + str(kl) + ';' )
		print( 'wf_' + str(counter) + '.SetDefaultColor(GetColor(5));' ) # Red color
		counter += 1

	# Weekly Unfiltered
	print( "\n" )
	print( '# WEEKLY UNFILTERED WITH MULTIPLE HITS (Threshold: ' + str(args.weekly_threshold) + ')' )
	tmp = {}
	for kl,dt,count in long_support_unfiltered+long_resistance_unfiltered:
		tmp[dt] = ( kl,count )

	counter = 1
	for dt in sorted( tmp.keys() ):
		kl	= tmp[dt][0]
		count	= tmp[dt][1]
		dt	= datetime.fromtimestamp(int(dt)/1000, tz=mytimezone)
		if ( count >= args.weekly_threshold or dt > time_now - timedelta(days=30) ):
			print( 'plot wu_' + str(counter) + ' = ' + str(kl) + '; # (' + str(count) + ')' )
			print( 'wu_' + str(counter) + '.SetDefaultColor(GetColor(0));' ) # Pinkish color
			counter += 1

	# Daily
	print( "\n" )
	print( '# DAILY UNFILTERED WITH MULTIPLE HITS (Threshold: ' + str(args.daily_threshold) + ')' )
	tmp = {}
	for kl,dt,count in long_support_daily_unfiltered+long_resistance_daily_unfiltered:
		tmp[dt] = ( kl,count )

	counter = 1
	for dt in sorted( tmp.keys() ):
		kl	= tmp[dt][0]
		count	= tmp[dt][1]
		dt	= datetime.fromtimestamp(int(dt)/1000, tz=mytimezone)
		if ( count >= args.daily_threshold or dt > time_now - timedelta(days=30) ):
			print( 'plot du_' + str(counter) + ' = ' + str(kl) + '; # (' + str(count) + ')' )
			print( 'du_' + str(counter) + '.SetDefaultColor(CreateColor(140, 0, 0));' ) # DARK red color
			counter += 1

	# Skip volume profile if we do not have any data (i.e. processing an indicator like $SPX.X)
	if ( date_1 == None ):
		sys.exit(0)

	# Volume Profile VAH/VAL
	print( "\n" )
	print( '# Value Area High (VAH) and Value Area Low (VAL) from last')
	print( '#  two previous trading days (' + str(date_1) + ' / ' + str(date_2) + ')' )
	print( 'plot vah_1 = ' + str(vah_1) )
	print( 'vah_1.SetDefaultColor(CreateColor(255, 35, 0));' ) # Orange
	print( 'plot val_1 = ' + str(val_1) )
	print( 'val_1.SetDefaultColor(CreateColor(255, 35, 0));' )
	print()

	# Two-day VAH/VAL paint with dashed lines
	print( 'plot vah_2 = ' + str(vah_2) + ';' )
	print( 'vah_2.SetDefaultColor(CreateColor(255, 35, 0));' )
	print( 'vah_2.SetPaintingStrategy(PaintingStrategy.DASHES);' )
	print( 'plot val_2 = ' + str(val_2) + ';' )
	print( 'val_2.SetDefaultColor(CreateColor(255, 35, 0));' )
	print( 'val_2.SetPaintingStrategy(PaintingStrategy.DASHES);' )
	print()


sys.exit(0)

