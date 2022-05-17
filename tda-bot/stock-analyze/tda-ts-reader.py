#!/usr/bin/python3 -u

# Read in Level2 and Time and Sales data collected via TD Ameritrade's streaming API,
#  collect data about each trade (bid/ask/volume/etc.) and dump it to a file to use
#  later for backtesting.
#
# This is a time-consuming process to parse and organize an entire day of level2 and
#  time/sales data, so we use this tool to perform that process once so that the
#  backtesting tool(s) can consume the data quickly.
#
# Example:
#  $ ./tda-ts-reader.py --ts_ifile TX_LOGS_v2/2022-04-22/SPY_ets-2022-04-22.pickle.xz \
#                       --l2_ifile TX_LOGS_v2/2022-04-22/SPY_level2-2022-04-22.pickle.xz \
#                       --ofile ts-processed_2022-04-22.pickle.xz

import sys, re
import argparse
import lzma
import pickle
from datetime import datetime
import pytz
import numpy as np

from collections import OrderedDict

parser = argparse.ArgumentParser()
parser.add_argument("--ts_ifile", help='Time and sales file to import from streaming client (i.e. SPY_ets-2022-04-22.pickle.xz)', required=True, type=str)
parser.add_argument("--l2_ifile", help='Level2 file to import from streaming client (i.e. SPY_level2-2022-04-22.pickle.xz)', required=True, type=str)
parser.add_argument("--ofile", help='Output file', required=True, type=str)
args = parser.parse_args()

mytimezone = pytz.timezone("US/Eastern")

print('Loading data files... ')
try:
	# Time and sales data file
	if ( re.search('\.xz$', args.ts_ifile) != None ):
		with lzma.open(args.ts_ifile, 'rb') as handle:
			ets = handle.read()
			ets = pickle.loads(ets)

	else:
		with open(args.ts_ifile, 'rb') as handle:
			ets = handle.read()
			ets = pickle.loads(ets)

	# Level2 data file
	if ( re.search('\.xz$', args.l2_ifile) != None ):
		with lzma.open(args.l2_ifile, 'rb') as handle:
			l2 = handle.read()
			l2 = pickle.loads(l2)

	else:
		with open(args.l2_ifile, 'rb') as handle:
			l2 = handle.read()
			l2 = pickle.loads(l2)

except Exception as e:
	print('Error opening file: ' + str(e))
	sys.exit(1)


# Process time and sales data
print('Processing all time and sales data. This may take some time...')


# Find all the available datetimes in the Level2 data
# We will use this to match timestamps between the Level2 data and the
#  time/sales data
dts = list( l2.keys() )
for i in range( len(dts) ):
	dts[i] = int( dts[i] )
dts.sort()
dts = np.array( dts )

ets_data = OrderedDict()
for tx in ets:

	trade_time	= int( tx['TRADE_TIME'] )
	last_price	= float( tx['LAST_PRICE'] )
	last_size	= float( tx['LAST_SIZE'] )

	# Time and sales stream does not include bid/ask prices, only last_price and volume.
	#  Therefore, we will need to find the closest level2 entry that matches the data
	#  from the time and sales stream so we can determine volume of trades that were
	#  matched closer to bid or ask (or neutral).
	#
	#  The ability to determine if a trade was made closer to the bid or ask is essential,
	#   but unfortunately this is a time-consuming operation when processing a full day of
	#   time and sale data.
	cur_bid_price	= None
	cur_ask_price	= None
	if ( trade_time in l2 ):
		cur_bid_price = max( l2[trade_time]['bids'].keys() )
		cur_ask_price = min( l2[trade_time]['asks'].keys() )

	else:

		try:
			# Find the smallest timestamp from Level 2 data that matches the timestamp
			#  from time and sales without going above the timestamp from time and sales
			dt = dts[dts > trade_time].min()

		except:
			# Fall back to just find the closest timestamp from Level 2 data that matches
			#  the timestamp from time and sales
			dt = (np.abs(dts - trade_time)).argmin()

		# The data is probably not reliable if the timestamps are too far apart
		if ( abs(dt - trade_time) > 1000 ):
			continue

		cur_bid_price = max( l2[dt]['bids'].keys() )
		cur_ask_price = min( l2[dt]['asks'].keys() )

	# We now have:
	#   - trade_time
	#   - last_price
	#   - last_size
	#   - bid_price
	#   - ask_price
	if trade_time not in ets_data:
		num_trades		= 1
		all_sizes		= []
		dt_string		= datetime.fromtimestamp(trade_time/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S')
		ets_data[trade_time]	= {	'dt_string':		dt_string,
						'size':			0,
						'at_ask':		0,
						'at_bid':		0,
						'neutral_vol':		0,
						'uptick_vol':		0,
						'downtick_vol':		0,
						'num_trades':		0,
						'avg_size':		0,
						'high_price':		0,
						'low_price':		9999999,
						'span_trade_up':	0,
						'span_trade_down':	0,
						'span_trade_up_vol':	0,
						'span_trade_down_vol':	0 }
	else:
		num_trades += 1

	ets_data[trade_time]['size']		+= last_size
	ets_data[trade_time]['num_trades']	= num_trades

	all_sizes.append( last_size )
	ets_data[trade_time]['avg_size']	= sum( all_sizes ) / len( all_sizes )

	if ( re.search('^\d{1,}\.\d{3,}$', str(last_price)) != None ):
		if ( last_price <= cur_bid_price ):
			ets_data[trade_time]['span_trade_down']		+= 1
			ets_data[trade_time]['span_trade_down_vol']	+= last_size

		elif ( last_price >= cur_ask_price ):
			ets_data[trade_time]['span_trade_up']		+= 1
			ets_data[trade_time]['span_trade_up_vol']	+= last_size

	# Get the high/low candle
	if ( last_price < ets_data[trade_time]['low_price'] ):
		 ets_data[trade_time]['low_price'] = last_price

	if ( last_price > ets_data[trade_time]['high_price'] ):
		ets_data[trade_time]['high_price'] = last_price

	# Get the uptick/downticks
	# It seems some algos ensure the trade settles at 0.0001 away from the bid or ask
	#  price, I suppose to make the tx appear that it occurred just within the bid/ask
	#  zone. So check this so we can be sure include those as at_bid or at_ask instead
	#  of neutral.
	if ( last_price <= cur_bid_price or abs(last_price - cur_bid_price) == 0.0001 ):
		ets_data[trade_time]['at_bid']		+= 1
		ets_data[trade_time]['downtick_vol']	+= last_size

	elif ( last_price >= cur_ask_price or abs(last_price - cur_ask_price) == 0.0001 ):
		ets_data[trade_time]['at_ask']		+= 1
		ets_data[trade_time]['uptick_vol']	+= last_size

	else:
		ets_data[trade_time]['neutral_vol']	+= last_size

#	if ( last_size > 3000 ):
#		print(ets_data[trade_time]['dt_string'] + ' | ' + str(last_size) + ' | ' + str(last_price) + ' | ' + str(cur_bid_price) + ' | ' + str(cur_ask_price) )


#	elif ( last_price == (cur_ask_price - cur_bid_price) / 2 ):
#		ets_data[trade_time]['neutral_vol']		+= last_size
#
#	elif ( cur_ask_price - last_price < last_price - cur_bid_price ):
#		ets_data[trade_time]['at_bid']		+= 1
#		ets_data[trade_time]['downtick_vol']	+= last_size
#
#	elif ( cur_ask_price - last_price > last_price - cur_bid_price ):
#		ets_data[trade_time]['at_ask']		+= 1
#		ets_data[trade_time]['uptick_vol']	+= last_size


# Done, write out results.
print('Writing out results to ' + str(args.ofile) + '...')
try:
	if ( re.search('\.xz$', args.ofile) == None ):
		args.ofile = args.ofile + '.xz'

	with lzma.open(args.ofile, 'wb') as handle:
		pickle.dump(ets_data, handle)
		handle.flush()

except Exception as e:
	print('Error opening file for writing: ' + str(e))
	sys.exit(1)


sys.exit(0)

