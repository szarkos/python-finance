#!/usr/bin/python3 -u

#import os, sys
import time
import re
from datetime import datetime, timedelta
from pytz import timezone

from itertools import compress
import talib
import numpy as np
import pandas as pd


# Candlestick Indicators
#
# Notes:
#  - CDLIDENTICAL3CROWS_Bear is wierd because it indicates a downturn,
#      but that's pretty obvious because it's three big downward candles in a row.
#  - Engulfing signals are very common and usually correct, but trend is short lasting.

# List of candle indicators that suggest a reversal from bear->bull
candle_rankings_bullish_reversals = {
	'CDL3LINESTRIKE_Bull': 1,
	'CDLABANDONEDBABY_Bull': 9,
	'CDLPIERCING_Bull': 13,
	'CDL3INSIDE_Bull': 20,
	'CDLMORNINGDOJISTAR_Bull': 25,
	'CDLXSIDEGAP3METHODS_Bear': 26,
	'CDLTRISTAR_Bull': 28,
	'CDLENGULFING_Bull': 84,
	'NO_PATTERN': 999
}

# List of candle indicators that suggest a reversal from bull->bear
#
# CDLXSIDEGAP3METHODS_Bull' and 'Bear' are reversed because in theory these
#   indicate a bull/bear continuation, but really indicates a bearish reversal
candle_rankings_bearish_reversals = {
	'CDL3LINESTRIKE_Bear': 2,
	'CDL3BLACKCROWS_Bear': 3,
	'CDLEVENINGSTAR_Bear': 4,
	'CDLBREAKAWAY_Bear': 11,
	'CDLDARKCLOUDCOVER_Bear': 22,
	'CDLIDENTICAL3CROWS_Bear': 24,
	'CDLXSIDEGAP3METHODS_Bull': 27,
	'CDLEVENINGDOJISTAR_Bull': 30,
	'CDLEVENINGDOJISTAR_Bear': 30,
	'CDLENGULFING_Bear': 91,
	'NO_PATTERN': 999
}


# Analyze candles based on pricehistory
# Pattern is the type of reversal pattern to check ('bull' or 'bear')
# tda_cndl_helper.candle_analyze_reversal(data, candle_pattern='bull', debug=True)
def candle_analyze_reversal(pricehistory=None, candle_pattern=None, debug=False):

	ticker = ''
	if ( pricehistory['symbol'] ):
		ticker = pricehistory['symbol']

	if ( pricehistory == None ):
		print('Error: candle_analyze_reversal(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False
	if ( candle_pattern == None ):
		print('Error: candle_analyze_reversal(' + str(ticker) + '): you must specify what type of reversal pattern to check ("bull" or "bear")', file=sys.stderr)
		return False

	# Set timezone
	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# Caller will ask what type of reversal pattern they want to check for
	candle_pattern = str(candle_pattern).lower()
	if ( candle_pattern == 'bull' ):
		candle_rankings = candle_rankings_bullish_reversals
	elif ( candle_pattern == 'bear' ):
		candle_rankings = candle_rankings_bearish_reversals
	else:
		print('Error: candle_analyze_reversal(' + str(ticker) + '): unsupported pattern ' + str(candle_pattern), file=sys.stderr)


	# Put the pricehistory dict into a pandas dataframe
	# We only really want the last ten (or so) candles
	skip = int(len(pricehistory['candles'])) - 11
	prices = np.array([[1,1,1,1,1,1]])

	for idx,key in enumerate(pricehistory['candles']):
		if ( idx < skip ):
			continue

		# Skip the last element
		# We will revisit the last candle in pricehistory['candles'] to confirm any indicators tulip finds
		if ( idx == len(pricehistory['candles']) - 1):
			continue

		prices = np.append( prices, [[float(key['close']), float(key['high']), float(key['low']), float(key['open']),
					float(key['datetime'])/1000, float(key['volume'])]], axis=0 )


	prices = np.delete(prices, 0, axis=0)
	df = pd.DataFrame(data=prices, columns=['close', 'high', 'low', 'open', 'datetime', 'volume'], dtype='float64')

	# Time column is converted to "YYYY-mm-dd hh:mm:ss" ("%Y-%m-%d %H:%M:%S")
	posix_time = pd.to_datetime(df['datetime'], unit='s')
	df.insert(0, "Date", posix_time)
	df.drop("datetime", axis = 1, inplace = True)
	df.Date = df.Date.dt.tz_localize(tz='UTC').dt.tz_convert(tz=mytimezone)

	# Use ta-lib to check for candle patterns
	open = df['open']
	high = df['high']
	low = df['low']
	close = df['close']

	candle_names = []
	for pattern in candle_rankings:

		if ( pattern == 'NO_PATTERN' ):
			continue

		pattern = re.sub( '_Bull', '', pattern )
		pattern = re.sub( '_Bear', '', pattern )

		candle_names.append(pattern)
		df[pattern] = getattr(talib, pattern)(open, high, low, close)

	# Populate the dataframe
	df['candlestick_pattern'] = np.nan
	df['candlestick_match_count'] = np.nan
	for index, row in df.iterrows():

		# No pattern found
		if ( len(row[candle_names]) - sum(row[candle_names] == 0) == 0 ):
			df.loc[index,'candlestick_pattern'] = "NO_PATTERN"
			df.loc[index, 'candlestick_match_count'] = 0

		# Single pattern found
		elif ( len(row[candle_names]) - sum(row[candle_names] == 0) == 1 ):

			# Bull pattern 100 or 200
			if any(row[candle_names].values > 0):
				pattern = list(compress(row[candle_names].keys(), row[candle_names].values != 0))[0] + '_Bull'
				if ( pattern not in candle_rankings ):
					pattern = 'NO_PATTERN'

				df.loc[index, 'candlestick_pattern'] = pattern
				df.loc[index, 'candlestick_match_count'] = 1

			# Bear pattern -100 or -200
			else:
				pattern = list(compress(row[candle_names].keys(), row[candle_names].values != 0))[0] + '_Bear'
				if ( pattern not in candle_rankings ):
					pattern = 'NO_PATTERN'

				df.loc[index, 'candlestick_pattern'] = pattern
				df.loc[index, 'candlestick_match_count'] = 1

		# Multiple patterns matched -- select best performance
		else:

			# Filter out pattern names from bool list of values
			patterns = list(compress(row[candle_names].keys(), row[candle_names].values != 0))
			container = []
			for pattern in patterns:
				if ( row[pattern] > 0 ):
					if ( pattern + '_Bull' in candle_rankings ):
						container.append(pattern + '_Bull')
					else:
						container.append('NO_PATTERN')

				else:
					if ( pattern + '_Bear' in candle_rankings ):
						container.append(pattern + '_Bear')
					else:
						container.append('NO_PATTERN')

			rank_list = [candle_rankings[p] for p in container]

			if ( len(rank_list) == len(container) ):
				rank_index_best = rank_list.index(min(rank_list))
				df.loc[index, 'candlestick_pattern'] = container[rank_index_best]
				df.loc[index, 'candlestick_match_count'] = len(container)

	df.drop(candle_names, axis = 1, inplace = True)

#	if ( debug == True ):
#		pd.set_option('display.max_rows', None)
#		pd.set_option('display.max_columns', None)
#		pd.set_option('display.width', None)
#		pd.set_option('display.max_colwidth', None)
#		print(df)

	# Check the last element of dataframe
	# Return True if the last candle confirms the bull or bearish reversal, otherwise return False
	idx = len(df['Date']) - 1
	prev_date = df['Date'][idx].strftime('%Y-%m-%d %H:%M:%S.%f')
	last_pattern = df['candlestick_pattern'].tail(n=1).values[0]

	if ( last_pattern == 'NO_PATTERN' ):
		return False

	if ( debug == True ):
		print('DEBUG: candle_analyze_reversal(' + str(ticker) + '): pattern found: ' + str(last_pattern) + ' at ' + str(prev_date))

	if ( candle_pattern == 'bull' ):
		if ( float(pricehistory['candles'][-1]['close']) > float(pricehistory['candles'][-2]['close']) ):

			if ( debug == True ):
				cur_date = datetime.fromtimestamp(float(pricehistory['candles'][-1]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				print('DEBUG: candle_analyze_reversal(' + str(ticker) + '): ' + str(candle_pattern) + ' pattern (' + str(last_pattern) + ') confirmed')
				print('DEBUG: Previous Close (' + str(prev_date) + '): ' + str(pricehistory['candles'][-2]['close']) +
					' Current Close (' + str(cur_date) + '): ' + str(pricehistory['candles'][-1]['close']) )

				return True

	elif ( candle_pattern == 'bear' ):
		if ( float(pricehistory['candles'][-1]['close']) < float(pricehistory['candles'][-2]['close']) ):

			if ( debug == True ):
				cur_date = datetime.fromtimestamp(float(pricehistory['candles'][-1]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				print('DEBUG: candle_analyze_reversal(' + str(ticker) + '): ' + str(candle_pattern) + ' pattern (' + str(last_pattern) + ') confirmed')
				print('DEBUG: Previous Close (' + str(prev_date) + '): ' + str(pricehistory['candles'][-2]['close']) +
					' Current Close (' + str(cur_date) + '): ' + str(pricehistory['candles'][-1]['close']) )

			return True


	# Pattern found but not confirmed
	return False

