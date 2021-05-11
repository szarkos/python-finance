#!/usr/bin/python3 -u

import os, sys, signal
import time, datetime, pytz, random
import argparse
import pickle
import re
import tda_gobot_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("--ifile", help='File that contains the price history of a stock', required=True, type=str)
parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
args = parser.parse_args()

args.debug = True

# Set timezone
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone

if ( args.ifile != None ):
	try:
		with open(args.ifile, 'rb') as handle:
			data = handle.read()
			data = pickle.loads(data)

	except Exception as e:
		print('Error opening file ' + str(args.ifile) + ': ' + str(e))
		exit(1)

ticker = re.sub('\.data', '', args.ifile)
ticker = re.sub('^.+/', '', ticker)

# Calculate the average volume for the stock
avg_volume = 0
for candle in data['candles']:
	avg_volume += float(candle['volume'])
avg_volume = avg_volume / len(data['candles'])

for idx,candle in enumerate(data['candles']):

	if ( idx < 11 ):
		continue

	# Look back ten candles
	#  - If the open/close prices are 1% or higher, look forward to the next three candles
	#    and determine if it would have been good to buy or short the stock.
	#  - Use idx-10 for open price, and idx-8 for close - essentially combining multiple candles
	#    since we often get at least two candles/minute using the streams API.
	#  - Do the same with volume to combine candles.
	open_price = float(data['candles'][idx-10]['open'])
	close_price = float(data['candles'][idx-8]['open'])
	volume = float(data['candles'][idx-10]['volume']) + float(data['candles'][idx-8]['volume'])

	# Skip if price hasn't changed
	if ( open_price == close_price ):
		continue

	price_change = float(0)
	max_gain = float(0)
	if ( close_price > open_price ):
		# Bull
		direction = 'UP'
		price_change = ( (close_price - open_price) / close_price ) * 100
	else:
		# Bear
		direction = 'DOWN'
		price_change = ( (open_price - close_price) / open_price ) * 100

	# Check if price and volume change significantly (price > 1%, volume > 20%)
	if ( price_change > 1.5 and volume > avg_volume ):
#		if ( ((volume - avg_volume) / avg_volume) * 100 < 75 ):
		if ( volume < avg_volume * 10 ):
			continue

		time_now = datetime.datetime.fromtimestamp(float(data['candles'][idx-4]['datetime'])/1000, tz=mytimezone)

		# Cut out early morning or after hour trades
		if ( int(time_now.strftime('%-H')) < 10 or ( int(time_now.strftime('%-H')) == 10 and int(time_now.strftime('%-M')) < 30 ) ):
			continue
		if ( int(time_now.strftime('%-H')) > 16 ):
			continue

		time_now = time_now.strftime('%Y-%m-%d %H:%M:%S.%f')
		print( '(' + str(ticker) + '): Gap ' + str(direction).upper() + ' detected (' + str(time_now) + ')' )
		print( 'Open Price: ' + str(round(open_price, 2)) + ', ' +
			'Close Price: ' + str(round(close_price, 2)) +
			' (' + str(round(price_change, 2)) + '%)' +
			', Volume: ' + str(volume))

		success = 0
		for x in range(9, -1, -1):
			next_open = float(data['candles'][idx-x]['open'])
			next_close = float(data['candles'][idx-x]['close'])
			next_vol = float(data['candles'][idx-x]['volume'])

			print( 'Open Price: ' + str(round(next_open, 2)) + ', ' +
				'Close Price: ' + str(round(next_close, 2)) )

			if ( direction == 'UP' ):
				if ( next_close > next_open ):
					success += 1
					max_gain = next_close - close_price
#				else:
#					max_gain = next_close - close_price
#					break

			elif ( direction == 'DOWN' ):
				if ( next_close < next_open ):
					success += 1
					max_gain = close_price - next_close
#				else:
#					max_gain = close_price - next_close
#					break

		print('(' + str(ticker) + '): ' + str(time_now) + ' Detected ' + str(success) + ' successful candles after initial detection (' + str(direction) + '). Max gain: ' + str(round(max_gain, 2)))
		if ( max_gain < 0 ):
			print('Average volume: ' + str(avg_volume) + ', Initial volume: ' + str(volume) + ', Last volume: ' + str(next_vol))

		print()


sys.exit(0)

