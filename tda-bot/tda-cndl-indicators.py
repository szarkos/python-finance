#!/usr/bin/python3 -u

import os, sys
import datetime, pytz
from itertools import compress
import argparse

import robin_stocks.tda as tda
import tda_gobot_helper

import talib
import numpy as np
import pandas as pd


parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
args = parser.parse_args()


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

stock = args.stock

mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone


time_now = datetime.datetime.now( mytimezone )
#time_now = datetime.datetime.strptime('2021-04-09 15:59:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=mytimezone)
time_prev = time_now - datetime.timedelta( minutes=(128 * 8) ) # Subtract enough time to ensure we get an RSI for the current period
time_now_epoch = int( time_now.timestamp() * 1000 )
time_prev_epoch = int( time_prev.timestamp() * 1000 )

data, epochs = tda_gobot_helper.get_pricehistory(stock, 'day', 'minute', '1', None, time_prev_epoch, time_now_epoch, needExtendedHoursData=False, debug=True)

prices = np.array([[1,1,1,1,1,1]])
for key in data['candles']:
	#datetime.datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f'))
	key['datetime'] = float(key['datetime']/1000)
	prices = np.append( prices, [[float(key['close']), float(key['high']), float(key['low']), float(key['open']),
			    float(key['datetime']), float(key['volume'])]], axis=0 )
prices = np.delete(prices, 0, axis=0)

df = pd.DataFrame(data=prices, columns=['close', 'high', 'low', 'open', 'datetime', 'volume'], dtype='float64')

# time column is converted to "YYYY-mm-dd hh:mm:ss" ("%Y-%m-%d %H:%M:%S")
posix_time = pd.to_datetime(df['datetime'], unit='s')

# append posix_time
df.insert(0, "Date", posix_time)

# drop unix time stamp
df.drop("datetime", axis = 1, inplace = True)

df.Date = df.Date.dt.tz_localize('UTC').dt.tz_convert('US/Eastern')

# 1) Three line strike, bearish - acts as reverse upward 84% of time
# 2) Three line strike, bullish - reversal from rising to a downward trend (65%)
# 3) Three black crows, bearish reversal (78%)
# 4) Evening star, bearish reversal (72%)
# 5) Upside Tasuki, bullish continuation (57%) - 57% is near random :(
# 6) Hammer inverted, bearish continuation (65%)
# 7) Matching low, bearish continuation (61%)
# 8) Abandonded baby, bullish reversal (70%)
# 9) Two black gapping, bearish continuation (68%)
# 10) Breakaway bearish, bearish reversal (63%)

candle_rankings = {
'CDL3LINESTRIKE_Bull': 1,
'CDL3LINESTRIKE_Bear': 2,
'CDL3BLACKCROWS_Bull': 3,
'CDL3BLACKCROWS_Bear': 3,
'CDLEVENINGSTAR_Bull': 4,
'CDLEVENINGSTAR_Bear': 4,
'CDLTASUKIGAP_Bull': 5,
'CDLTASUKIGAP_Bear': 5,
'CDLINVERTEDHAMMER_Bull': 6,
'CDLINVERTEDHAMMER_Bear': 6,
'CDLMATCHINGLOW_Bull': 7,
'CDLMATCHINGLOW_Bear': 7,
'CDLABANDONEDBABY_Bull': 8,
'CDLABANDONEDBABY_Bear': 8,
'CDLBREAKAWAY_Bull': 10,
'CDLBREAKAWAY_Bear': 10,
'CDLMORNINGSTAR_Bull': 12,
'CDLMORNINGSTAR_Bear': 12,
'CDLPIERCING_Bull': 13,
'CDLPIERCING_Bear': 13,
'CDLSTICKSANDWICH_Bull': 14,
'CDLSTICKSANDWICH_Bear': 14,
'CDLTHRUSTING_Bull': 15,
'CDLTHRUSTING_Bear': 15,
'CDLINNECK_Bull': 17,
'CDLINNECK_Bear': 17,
'CDL3INSIDE_Bull': 20,
'CDL3INSIDE_Bear': 56,
'CDLHOMINGPIGEON_Bull': 21,
'CDLHOMINGPIGEON_Bear': 21,
'CDLDARKCLOUDCOVER_Bull': 22,
'CDLDARKCLOUDCOVER_Bear': 22,
'CDLIDENTICAL3CROWS_Bull': 24,
'CDLIDENTICAL3CROWS_Bear': 24,
'CDLMORNINGDOJISTAR_Bull': 25,
'CDLMORNINGDOJISTAR_Bear': 25,
'CDLXSIDEGAP3METHODS_Bull': 27,
'CDLXSIDEGAP3METHODS_Bear': 26,
'CDLTRISTAR_Bull': 28,
'CDLTRISTAR_Bear': 76,
'CDLGAPSIDESIDEWHITE_Bull': 46,
'CDLGAPSIDESIDEWHITE_Bear': 29,
'CDLEVENINGDOJISTAR_Bull': 30,
'CDLEVENINGDOJISTAR_Bear': 30,
'CDL3WHITESOLDIERS_Bull': 32,
'CDL3WHITESOLDIERS_Bear': 32,
'CDLONNECK_Bull': 33,
'CDLONNECK_Bear': 33,
'CDL3OUTSIDE_Bull': 34,
'CDL3OUTSIDE_Bear': 39,
'CDLRICKSHAWMAN_Bull': 35,
'CDLRICKSHAWMAN_Bear': 35,
'CDLSEPARATINGLINES_Bull': 36,
'CDLSEPARATINGLINES_Bear': 40,
'CDLLONGLEGGEDDOJI_Bull': 37,
'CDLLONGLEGGEDDOJI_Bear': 37,
'CDLHARAMI_Bull': 38,
'CDLHARAMI_Bear': 72,
'CDLLADDERBOTTOM_Bull': 41,
'CDLLADDERBOTTOM_Bear': 41,
'CDLCLOSINGMARUBOZU_Bull': 70,
'CDLCLOSINGMARUBOZU_Bear': 43,
'CDLTAKURI_Bull': 47,
'CDLTAKURI_Bear': 47,
'CDLDOJISTAR_Bull': 49,
'CDLDOJISTAR_Bear': 51,
'CDLHARAMICROSS_Bull': 50,
'CDLHARAMICROSS_Bear': 80,
'CDLADVANCEBLOCK_Bull': 54,
'CDLADVANCEBLOCK_Bear': 54,
'CDLSHOOTINGSTAR_Bull': 55,
'CDLSHOOTINGSTAR_Bear': 55,
'CDLMARUBOZU_Bull': 71,
'CDLMARUBOZU_Bear': 57,
'CDLUNIQUE3RIVER_Bull': 60,
'CDLUNIQUE3RIVER_Bear': 60,
'CDL2CROWS_Bull': 61,
'CDL2CROWS_Bear': 61,
'CDLBELTHOLD_Bull': 62,
'CDLBELTHOLD_Bear': 63,
'CDLHAMMER_Bull': 65,
'CDLHAMMER_Bear': 65,
'CDLHIGHWAVE_Bull': 67,
'CDLHIGHWAVE_Bear': 67,
'CDLSPINNINGTOP_Bull': 69,
'CDLSPINNINGTOP_Bear': 73,
'CDLUPSIDEGAP2CROWS_Bull': 74,
'CDLUPSIDEGAP2CROWS_Bear': 74,
'CDLGRAVESTONEDOJI_Bull': 77,
'CDLGRAVESTONEDOJI_Bear': 77,
'CDLHIKKAKEMOD_Bull': 82,
'CDLHIKKAKEMOD_Bear': 81,
'CDLHIKKAKE_Bull': 85,
'CDLHIKKAKE_Bear': 83,
'CDLENGULFING_Bull': 84,
'CDLENGULFING_Bear': 91,
'CDLMATHOLD_Bull': 86,
'CDLMATHOLD_Bear': 86,
'CDLHANGINGMAN_Bull': 87,
'CDLHANGINGMAN_Bear': 87,
'CDLRISEFALL3METHODS_Bull': 94,
'CDLRISEFALL3METHODS_Bear': 89,
'CDLKICKING_Bull': 96,
'CDLKICKING_Bear': 102,
'CDLDRAGONFLYDOJI_Bull': 98,
'CDLDRAGONFLYDOJI_Bear': 98,
'CDLCONCEALBABYSWALL_Bull': 101,
'CDLCONCEALBABYSWALL_Bear': 101,
'CDL3STARSINSOUTH_Bull': 103,
'CDL3STARSINSOUTH_Bear': 103,
'CDLDOJI_Bull': 104,
'CDLDOJI_Bear': 104,
'CDLCOUNTERATTACK_Bull': 104,
'CDLCOUNTERATTACK_Bear': 104,
'CDLLONGLINE_Bull': 104,
'CDLLONGLINE_Bear': 104,
'CDLSHORTLINE_Bull': 104,
'CDLSHORTLINE_Bear': 104,
'CDLSTALLEDPATTERN_Bull': 104,
'CDLSTALLEDPATTERN_Bear': 104,
'CDLKICKINGBYLENGTH_Bull': 104,
'CDLKICKINGBYLENGTH_Bear': 104
}

# patterns not found in the patternsite.com
#exclude_items = ('CDLCOUNTERATTACK',
#		 'CDLLONGLINE',
#		 'CDLSHORTLINE',
#		 'CDLSTALLEDPATTERN',
#		 'CDLKICKINGBYLENGTH')

# extract OHLC
open = df['open']
high = df['high']
low = df['low']
close = df['close']

# create columns for each pattern
candle_names = talib.get_function_groups()['Pattern Recognition']
#candle_names = [candle for candle in candle_names if candle not in exclude_items]

for candle in candle_names:
	# df["CDL3LINESTRIKE"] = talib.CDL3LINESTRIKE(op, hi, lo, cl)
	df[candle] = getattr(talib, candle)(open, high, low, close)


df['candlestick_pattern'] = np.nan
df['candlestick_match_count'] = np.nan

for index, row in df.iterrows():

	# no pattern found
	if len(row[candle_names]) - sum(row[candle_names] == 0) == 0:
		df.loc[index,'candlestick_pattern'] = "NO_PATTERN"
		df.loc[index, 'candlestick_match_count'] = 0

	# single pattern found
	elif len(row[candle_names]) - sum(row[candle_names] == 0) == 1:
		# bull pattern 100 or 200
		if any(row[candle_names].values > 0):
			pattern = list(compress(row[candle_names].keys(), row[candle_names].values != 0))[0] + '_Bull'
			df.loc[index, 'candlestick_pattern'] = pattern
			df.loc[index, 'candlestick_match_count'] = 1

		# bear pattern -100 or -200
		else:
			pattern = list(compress(row[candle_names].keys(), row[candle_names].values != 0))[0] + '_Bear'
			df.loc[index, 'candlestick_pattern'] = pattern
			df.loc[index, 'candlestick_match_count'] = 1

	# multiple patterns matched -- select best performance
	else:
		# filter out pattern names from bool list of values
		patterns = list(compress(row[candle_names].keys(), row[candle_names].values != 0))
		container = []
		for pattern in patterns:
			if row[pattern] > 0:
				container.append(pattern + '_Bull')
			else:
				container.append(pattern + '_Bear')

		rank_list = [candle_rankings[p] for p in container]

		if len(rank_list) == len(container):
			rank_index_best = rank_list.index(min(rank_list))
			df.loc[index, 'candlestick_pattern'] = container[rank_index_best]
			df.loc[index, 'candlestick_match_count'] = len(container)

# clean up candle columns
#cols_to_drop = candle_names + list(exclude_items)
df.drop(candle_names, axis = 1, inplace = True)


pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)
print(df)




