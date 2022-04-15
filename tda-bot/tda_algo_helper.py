#!/usr/bin/python3 -u

import os, sys
from datetime import datetime, timedelta
from pytz import timezone

from collections import OrderedDict

import numpy as np
import pandas as pd
import tulipy as ti
import talib

import tda_gobot_helper


# Return the N-period simple moving average (SMA)
def get_sma(pricehistory=None, period=200, type='close', debug=False):

	if ( pricehistory == None ):
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Put pricehistory data into a numpy array
	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(int(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	prices = np.array( prices )

	# Get the N-day SMA
	sma = []
	try:
		sma = ti.sma(prices, period=period)

	except Exception as e:
		print('Caught Exception: get_sma(' + str(ticker) + '): ti.sma(): ' + str(e))
		return False

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(sma)

	return sma


# Return the N-period exponential moving average (EMA)
def get_ema(pricehistory=None, period=50, type='close', debug=False):

	if ( pricehistory == None ):
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Put pricehistory data into a numpy array
	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(int(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	prices = np.array( prices )

	# Get the N-day EMA
	ema = []
	try:
		ema = ti.ema(prices, period=period)

	except Exception as e:
		print('Caught Exception: get_ema(' + str(ticker) + '): ti.ema(): ' + str(e))
		return False

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(ema)

	return ema



# Generic function that returns the requested moving average.
#  - Most moving average functions only require a lookback period and a set of prices (type).
#  - VWMA also requires volume
#  - MAMA requires mama_fastlimit and mama_slowlimit
#  - VIDYA requires period, short period and alpha
#
# Supported input data types: close, high, low, open, volume, hl2, hlc3 (default), ohlc4
#
# Supported ma_types:
#	kama	= Kaufman Adaptive Moving Average (default)
#	dema	= Double Exponential Moving Average
# 	hma	= Hull Moving Average
#	tema	= Triple Exponential Moving Average
#	mama	= Mesa adaptive moving average
#	frama	= Fractal moving average
#	trima	= Triangular Moving Average
#	vidya	= Variable Index Dynamic Average
#	vwma	= Volume Weighted Moving Average
#	wma	= Weighted Moving Average
#	zlema	= Zero-Lag Exponential Moving Average
#
def get_alt_ma(pricehistory=None, period=50, ma_type='kama', type='hlc3', mama_fastlimit=0.5, mama_slowlimit=0.05, short_period=2, alpha=0.2, debug=False):

	if ( pricehistory == None ):
		return []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Put pricehistory data into a numpy array
	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(int(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	prices = np.array( prices )

	# Genereate the requested moving average
	ma = []

	# Simple moving average
	if ( ma_type == 'sma' ):
		try:
			ma = ti.sma(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.sma(): ' + str(e), file=sys.stderr)
			return False

	# Exponential moving average
	elif ( ma_type == 'ema' ):
		try:
			ma = ti.ema(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.ema(): ' + str(e), file=sys.stderr)
			return False

	# Kaufman Adaptive Moving Average
	# The Kaufman Adaptive Moving Average tries to adjust its smoothing to match the current market condition
	# It adapts to a fast moving average when prices are moving steadily in one direction and a slow moving
	#   average when the market exhibits a lot of noise.
	elif ( ma_type == 'kama' ):
		try:
			ma = ti.kama(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.kama(): ' + str(e), file=sys.stderr)
			return False

	# Double Exponential Moving Average
	# The Double Exponential Moving Average is similar to the Exponential Moving Average, but provides less lag
	elif ( ma_type == 'dema' ):
		try:
			ma = ti.dema(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.dema(): ' + str(e), file=sys.stderr)
			return False

	# Hull Moving Average modifies Weighted Moving Average to greatly reduce lag
	elif ( ma_type == 'hma' ):
		try:
			ma = ti.hma(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.hma(): ' + str(e), file=sys.stderr)
			return False

	# The Triple Exponential Moving Average is similar to the Exponential Moving Average or the Double Exponential
	#   Moving Average, but provides even less lag
	elif ( ma_type == 'tema' ):
		try:
			ma = ti.tema(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.tema(): ' + str(e), file=sys.stderr)
			return False

	# The Triangular Moving Average is similar to the Simple Moving Average but instead places more weight on the
	#   middle portion of the smoothing period and less weight on the newest and oldest bars in the period
	elif ( ma_type == 'trima' ):
		try:
			ma = ti.trima(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.trima(): ' + str(e), file=sys.stderr)
			return False

	# The Weighted Moving Average is similar to the Simple Moving Average but instead places more weight on more
	#   recent bars in the smoothing period and less weight on the oldest bars in the period
	elif ( ma_type == 'wma' ):
		try:
			ma = ti.wma(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.wma(): ' + str(e), file=sys.stderr)
			return False

	# Zero-Lag Exponential Moving Average modifies a Exponential Moving Average to greatly reduce lag
	elif ( ma_type == 'zlema' ):
		try:
			ma = ti.zlema(prices, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.zlema(): ' + str(e), file=sys.stderr)
			return False

	# The Volume Weighted Moving Average is simalair to a Simple Moving Average, but it weights each bar by its volume
	elif ( ma_type == 'vwma' ):
		volume = []
		for key in pricehistory['candles']:
			# Note: in python the volume is essentially an "int" type, but ti.vwma expects 'float64_t' type
			#   for volume data instead of 'long'
			volume.append( float(key['volume']) )
		volume = np.array( volume )

		try:
			ma = ti.vwma(prices, volume, period=period)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.vwma(): ' + str(e), file=sys.stderr)
			return False

	# MESA Adaptive Moving Average (MAMA)
	# This option returns a tuple (mama, fama)
	elif ( ma_type == 'mama' ):
		mama = []
		fama = []
		try:
			mama, fama = talib.MAMA( prices, fastlimit=mama_fastlimit, slowlimit=mama_slowlimit )

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): talib.MAMA(): ' + str(e), file=sys.stderr)
			return False

		# Lengths of mama/fama are already the same as prices[] and pricehistory['candles']
		return mama, fama

	# Fractal moving average
	elif ( ma_type == 'frama' ):
		frama = []
		try:
			#mama, fama = talib.MAMA( prices, fastlimit=mama_fastlimit, slowlimit=mama_slowlimit )
			frama = get_frama( pricehistory=pricehistory, type=type, period=period )

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): talib.MAMA(): ' + str(e), file=sys.stderr)
			return False

		# Lengths of mama/fama are already the same as prices[] and pricehistory['candles']
		return frama

	# VIDYA - Variable Index Dynamic Average
	elif ( ma_type == 'vidya' ):
		ma = []
		try:
			ma = ti.vidya(prices, short_period, period, alpha)

		except Exception as e:
			print('Caught Exception: get_alt_ma(' + str(ticker) + '): ti.vidya(): ' + str(e), file=sys.stderr)
			return False

	else:
		print('Error: unknown ma_type "' + str(ma_type) + '"', file=sys.stderr)
		return False

	# Normalize the size of the result to match the input size
	if ( len(ma) != len(pricehistory['candles']) ):
		tmp = []
		for i in range(0, len(pricehistory['candles']) - len(ma)):
			tmp.append(0)
		ma = tmp + list(ma)

	# Handle inf/-inf data points
	ma = np.nan_to_num(ma, copy=True)


	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(ma)

	return ma


# John Ehlers's Fractal Adaptive Moving Average (FRAMA)
#  https://mesasoftware.com/papers/papers/FRAMA.pdf
#
# Note: This implements frama, but you may be better off using
#  get_alt_ma with matype='mama', wich will return both mama and fama (frama)
def get_frama(pricehistory=None, type='hl2', period=20, fastma=1, slowma=198, plot=False, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_frama(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_frama(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_frama(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)


	# Calculate the Fractal Adaptive MA
	prices		= np.array( prices )
	period		= int(period / 2) * 2
	prev_dimen	= 0
	frama		= []
	for i in range( 0, len(prices) ):

		# Use prices[i] for the first few iterations
		if ( i < period * 2 ):
			frama.append( prices[i] )
			continue

		# Split the input into two arrays
		b1 = prices[i - (2 * period):1 - period]
		b2 = prices[i - period:i]

		# N1
		H1 = np.max(b1)
		L1 = np.min(b1)
		N1 = (H1 - L1) / period

		# N2
		H2 = np.max(b2)
		L2 = np.min(b2)
		N2 = (H2 - L2) / period

		# N3
		H  = np.max([H1, H2])
		L  = np.min([L1, L2])
		N3 = (H - L) / (period * 2)

		# Calculate fractal dimension
		dimen = prev_dimen
		if ( N1 > 0 and N2 > 0 and N3 > 0 ):
			dimen		= ( np.log(N1 + N2) - np.log(N3) ) / np.log(2)
			prev_dimen	= dimen

		# Calculate lowpass filter factor
		# Modified FRAMA so we can specify fastma and slowma
		#  http://etfhq.com/blog/2010/09/30/fractal-adaptive-moving-average-frama/
		alpha = np.exp( np.log(2 / (slowma + 1)) * (dimen - 1) )
		if ( alpha < 0.01 ):
			alpha = 0.01
		elif ( alpha > 1 ):
			alpha = 1

		N = (2 - alpha) / alpha
		N = ((slowma - fastma) * ((N - 1) / (slowma - 1))) + fastma

		alpha = 2 / (N + 1)
		if ( alpha < 2 / (slowma + 1) ):
			alpha = 2 / (slowma + 1)
		elif ( alpha > 1 ):
			alpha = 1

		# Finally, filter the input data
		frama.append( alpha * prices[i] + (1 - alpha) * frama[i-1] )

	# Plot
	if ( plot == True ):
		import matplotlib.pyplot as plt

		plt.title('Fractal Adaptive Moving Average (' + str(ticker) + ')')
		plt.plot(prices, color='k', label='Prices')
		plt.plot(frama, color='y', Label='FRAMA')
		plt.legend(['Prices', 'FRAMA'], loc = 'upper left')
		plt.show()

	return frama


# Use Tulipy to calculate the N-day historic volatility (default: 30-days)
def get_historic_volatility_ti(ticker=None, period=21, type='close', debug=False):

	days = period * 2 # Number of days to request from API.

	if ( ticker == None ):
		print('Error: get_historic_volatility(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False, []

	try:
		assert mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	end_date = datetime.now( mytimezone )
	start_date = end_date - timedelta( days=days )

	# Make sure start and end dates don't land on a weekend
	#  or outside market hours
	end_date = tda_gobot_helper.fix_timestamp(end_date)
	start_date = tda_gobot_helper.fix_timestamp(start_date)

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		pricehistory, epochs = tda_gobot_helper.get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

	except Exception as e:
		print('Caught Exception: get_historic_volatility(' + str(ticker) + '): ' + str(e))

	if ( pricehistory == False ):
		print('Error: get_historic_volatility(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False, []

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print('Error: get_historic_volatility(' + str(ticker) + '): len(pricehistory) is less than period (' + str(len(pricehistory['candles'])) + ')')

	# Put pricehistory data into a numpy array
	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	prices = np.array( prices )

	# Get the N-day historical volatility
	try:
		v = ti.volatility(prices, period=period)

	except Exception as e:
		print('Caught Exception: get_historic_volatility(' + str(ticker) + '): ti.volatility(): ' + str(e))
		return False, []

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(ema)

	return tuple(v), pricehistory


def get_historic_volatility(ticker=None, period=21, type='close', debug=False):

	days = period	# Number of days to request from API.
	trade_days = 252

	if ( ticker == None ):
		print('Error: get_historic_volatility(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		assert mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	end_date = datetime.now( mytimezone )
	start_date = end_date - timedelta( days=days )

	# Make sure start and end dates don't land on a weekend
	#  or outside market hours
	end_date = tda_gobot_helper.fix_timestamp(end_date)
	start_date = tda_gobot_helper.fix_timestamp(start_date)

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		pricehistory, epochs = tda_gobot_helper.get_pricehistory(ticker, 'day', 'minute', '1', start_date=start_date, end_date=end_date, needExtendedHoursData=True)

	except Exception as e:
		print('Caught Exception: get_historic_volatility(' + str(ticker) + '): ' + str(e))

	if ( pricehistory == False ):
		print('Error: get_historic_volatility(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print('Warning: get_historic_volatility(' + str(ticker) + '): len(pricehistory) is less than period (' + str(len(pricehistory['candles'])) + ')')

	# Put pricehistory data into a numpy array
	prices = np.array([[1,1]])
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			price = float(key['close'])
			prices = np.append( prices, [[float(key['datetime'])/1000, price ]], axis=0 )

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			price = float(key['high'])
			prices = np.append( prices, [[float(key['datetime'])/1000, price ]], axis=0 )

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			price = float(key['low'])
			prices = np.append( prices, [[float(key['datetime'])/1000, price ]], axis=0 )

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			price = float(key['open'])
			prices = np.append( prices, [[float(key['datetime'])/1000, price ]], axis=0 )

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			price = (float(key['high']) + float(key['low'])) / 2
			prices = np.append( prices, [[float(key['datetime'])/1000, price ]], axis=0 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			price = (float(key['high']) + float(key['low']) + float(key['close'])) / 3
			prices = np.append( prices, [[float(key['datetime'])/1000, price ]], axis=0 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			price =  (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4
			prices = np.append( prices, [[float(key['datetime'])/1000, price ]], axis=0 )

	# Remove the first value used to initialize np array
	prices = np.delete(prices, 0, axis=0)
	df = pd.DataFrame(data=prices, columns=['DateTime', 'Price'])

	posix_time = pd.to_datetime(df['DateTime'], unit='s')
	df.insert(0, "Date", posix_time)
	df.drop("DateTime", axis = 1, inplace = True)

	df = df.set_index(pd.DatetimeIndex(df['Date'].values))
	df.Date = df.Date.dt.tz_localize(tz='UTC').dt.tz_convert(tz=mytimezone)
	df.drop(columns=['Date'], axis=1, inplace=True)

	# Calculate daily logarithmic return
	df['returns'] = (np.log(df.Price / df.Price.shift(-1)))

	# Calculate daily standard deviation of returns
	daily_std = np.std(df.returns)

	# Annualized daily standard deviation
	volatility = daily_std * trade_days ** 0.5

	# This works too...
	#
	# Show the daily simple return
	# ( new_price / old_price ) - 1
	#returns = df.pct_change()

	# Create and show the annualized covariance matrix
	#cov_matrix_annual = returns.cov() * trade_days

	# Variance
	#weights = np.array([1.0])
	#variance = np.dot( weights.T, np.dot(cov_matrix_annual, weights))

	# Volatility (standard deviation)
	#volatility = np.sqrt(variance)

	return volatility


# Return the Average True Range (ATR) and Normalized Average True Range (NATR)
# https://www.investopedia.com/terms/a/atr.asp
def get_atr(pricehistory=None, period=14, debug=False):

	if ( pricehistory == None ):
		return False, []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print( 'Warning: get_atr(' + str(ticker) + ', ' + str(period) + '): len(pricehistory) is less than period (' +
			str(len(pricehistory['candles'])) + ') - unable to calculate ATR/NATR')
		return False, []

	# Put pricehistory data into a numpy array
	high = []
	low = []
	close = []
	for key in pricehistory['candles']:
		high.append( float(key['high']) )
		low.append( float(key['low']) )
		close.append( float(key['close']) )

	high = np.array( high )
	low = np.array( low )
	close = np.array( close )

	# Get the N-day ATR / NATR
	atr = []
	natr = []
	try:
		atr = ti.atr(high, low, close, period=period)
		#atr = talib.ATR(high, low, close, timeperiod=period)
		#atr = np.nan_to_num(atr, copy=True)

	except Exception as e:
		print('Caught Exception: get_atr(' + str(ticker) + '): ti.atr(): ' + str(e))
		return False, []

	try:
		natr = ti.natr(high, low, close, period=period)

	except Exception as e:
		print('Caught Exception: get_atr(' + str(ticker) + '): ti.natr(): ' + str(e))
		return False, []

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(atr)
		print(natr)

	return atr, natr


# Return the Average Directional Index (ADX), as well as the negative directional indicator (-DI)
#  and the positive directional indicator (+DI).
#
# If the +DI line crosses above the -DI line and the ADX is above 20, or ideally above 25,
#  then that is a potential signal to buy.
#
# https://www.investopedia.com/terms/a/adx.asp
# https://tulipindicators.org/di
# https://tulipindicators.org/adx
# https://tulipindicators.org/aroon
def get_adx(pricehistory=None, period=14, debug=False):

	if ( pricehistory == None ):
		return False, [], []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print( 'Warning: get_adx(' + str(ticker) + ', ' + str(period) + '): len(pricehistory) is less than period (' +
			str(len(pricehistory['candles'])) + ') - unable to calculate ADX/-DI/+DI')
		return False, [], []

	# Put pricehistory data into a numpy array
	high = []
	low = []
	close = []
	try:
		for key in pricehistory['candles']:
			high.append( float(key['high']) )
			low.append( float(key['low']) )
			close.append( float(key['close']) )

	except Exception as e:
		print('Caught Exception: get_adx(' + str(ticker) + '): while populating numpy arrays: ' + str(e))
		return False, [], []

	high = np.array( high )
	low = np.array( low )
	close = np.array( close )

	# Get the N-day ADX / -DI / +DI
	adx = []
	plus_di = []
	minus_di = []
	try:
		adx = ti.adx(high, low, close, period=period)

	except Exception as e:
		print('Caught Exception: get_adx(' + str(ticker) + '): ti.adx(): ' + str(e))
		return False, [], []

	try:
		plus_di, minus_di = ti.di(high, low, close, period=period)

	except Exception as e:
		print('Caught Exception: get_adx(' + str(ticker) + '): ti.di(): ' + str(e))
		return False, [], []

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(adx)
		print(plus_di)
		print(minus_di)

	return tuple(adx), tuple(plus_di), tuple(minus_di)


# Volume Price Trend
# VPT = Previous VPT + Volume x (Today’s Close – Previous Close) / Previous Close
def get_vpt(pricehistory=None, period=128, debug=False):

	if ( pricehistory == None ):
		return False, []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print( 'Warning: get_vpt(' + str(ticker) + ', ' + str(period) + '): len(pricehistory) is less than period (' +
			str(len(pricehistory['candles'])) + ') - unable to calculate VPT')
		return False, []

	vpt = []
	vpt_sum = 0
	for idx,key in enumerate(pricehistory['candles']):
		if ( idx == 0 ):
			vpt.append(0)
			continue

		cur_volume = float( pricehistory['candles'][idx]['volume'] )
		cur_close = float( pricehistory['candles'][idx]['close'] )
		prev_close = float( pricehistory['candles'][idx-1]['close'] )

		# Avoid division by 0 errors
		if ( prev_close == 0 ):
			prev_close = cur_close

		vpt_sum = vpt_sum + ( cur_volume * ((cur_close - prev_close) / prev_close) )
		vpt.append(vpt_sum)

	# Get the vpt signal line
	vpt = np.array( vpt )
	vpt_sma = []
	try:
		vpt_sma = ti.sma(vpt, period=period)

	except Exception as e:
		print('Caught Exception: get_vpt(' + str(ticker) + '): ti.sma(): ' + str(e))
		return False, []

	return vpt, vpt_sma


# Return the Aroon Oscillator value
# https://tulipindicators.org/aroon
def get_aroon_osc(pricehistory=None, period=25, debug=False):

	if ( pricehistory == None ):
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print( 'Warning: get_aroon_osc(' + str(ticker) + ', ' + str(period) + '): len(pricehistory) is less than period (' +
			str(len(pricehistory['candles'])) + ') - unable to calculate the aroon oscillator')
		return False

	# Put pricehistory data into a numpy array
	high = []
	low = []
	try:
		for key in pricehistory['candles']:
			high.append( float(key['high']) )
			low.append( float(key['low']) )

	except Exception as e:
		print('Caught Exception: get_aroon_osc(' + str(ticker) + '): while populating numpy arrays: ' + str(e))
		return False

	high = np.array( high )
	low = np.array( low )

	# Get the N-day ADX / -DI / +DI
	aroonosc = []
	try:
		aroonosc = ti.aroonosc(high, low, period=period)

	except Exception as e:
		print('Caught Exception: get_aroon_osc(' + str(ticker) + '): ti.aroonosc(): ' + str(e))
		return False

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(aroonosc)

	return tuple(aroonosc)


# Return numpy array of RSI (Relative Strength Index) values for a given price history.
# Reference: https://tulipindicators.org/rsi
# 'pricehistory' should be a data list obtained from get_pricehistory()
# Supports the following calculation types:
#   close	[default]
#   high
#   low
#   open
#   volume
#   hl2		[(H+L) / 2]
#   hlc3	[(H+L+C) / 3]
#   ohlc4	[(O+H+L+C) / 4]
def get_rsi(pricehistory=None, rsi_period=14, type='close', debug=False):

	if ( pricehistory == None ):
		print('Error: get_rsi(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_rsi(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False

	if ( len(prices) < rsi_period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Error: get_rsi(' + str(ticker) + '): len(prices) is less than rsi_period - is this a new stock ticker?', file=sys.stderr)
		return False

	# Calculate the RSI for the entire numpy array
	try:
		pricehistory = np.array( prices )
		rsi = ti.rsi( pricehistory, period=rsi_period )

	except Exception as e:
		print('Caught Exception: get_rsi(' + str(ticker) + '): ' + str(e))
		return False

	return rsi


# Return array of MFI (Money Flow Index) values for a given price/volume history.
# Reference: https://tulipindicators.org/mfi
# 'pricehistory' should be a data list obtained from get_pricehistory()
# By default MFI takes as input the high, low, close and volume of each candle
def get_mfi(pricehistory=None, period=14, debug=False):

	if ( pricehistory == None ):
		print('Error: get_mfi(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	high	= []
	low	= []
	close	= []
	volume	= []
	for key in pricehistory['candles']:
		high.append(	float(key['high'])	)
		low.append(	float(key['low'])	)
		close.append(	float(key['close'])	)
		volume.append(	float(key['volume'])	)

	if ( len(high) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Error: get_mfi(' + str(ticker) + '): len(prices) is less than period - is this a new stock ticker?', file=sys.stderr)
		return False

	try:
		high	= np.array( high )
		low	= np.array( low )
		close	= np.array( close )
		volume	= np.array( volume )

	except Exception as e:
		print('Caught Exception: get_mfi(' + str(ticker) + ') while generating numpy arrays: ' + str(e))
		return False

	# Calculate the MFI
	try:
		mfi = ti.mfi( high, low, close, volume, period=period )

	except Exception as e:
		print('Caught Exception: get_mfi(' + str(ticker) + '): ' + str(e))
		return False

	return mfi


# Return numpy array of Stochastic RSI values for a given price history.
# Reference: https://tulipindicators.org/stochrsi
# 'pricehistory' should be a data list obtained from get_pricehistory()
def get_stochrsi(pricehistory=None, rsi_period=14, stochrsi_period=128, type='close', rsi_d_period=3, rsi_k_period=128, slow_period=3, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_stochrsi(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, [], []

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_stochrsi(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False, [], []

	if ( len(prices) < stochrsi_period * 2 ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_stochrsi(' + str(ticker) + '): len(pricehistory) is less than stochrsi_period - is this a new stock ticker?', file=sys.stderr)

	prices = np.array( prices )

	# ti.stochrsi
	try:
		stochrsi = ti.stochrsi( prices, period=rsi_period )

	except Exception as e:
		print( 'Caught Exception: get_stochrsi(' + str(ticker) + '): ti.stochrsi(): ' + str(e) + ', len(pricehistory)=' + str(len(pricehistory['candles'])) )
		return False, [], []

	# ti.rsi + ti.stoch
	# Use ti.stoch() to get k and d values
	#   K measures the strength of the current move relative to the range of the previous n-periods
	#   D is a simple moving average of the K
	k = []
	d = []
	try:
		#rsi = ti.rsi( prices, period=stochrsi_period )
		rsi = talib.RSI( prices, timeperiod=stochrsi_period )
		rsi[np.isnan(rsi)] = 0

		k, d = ti.stoch( rsi, rsi, rsi, rsi_k_period, slow_period, rsi_d_period )
		#k, d = talib.STOCH( rsi, rsi, rsi, fastk_period=rsi_k_period, slowk_period=slow_period, slowk_matype=0, slowd_period=rsi_d_period, slowd_matype=0 )

	except Exception as e:
		print( 'Caught Exception: get_stochrsi(' + str(ticker) + '): ti.stoch(): ' + str(e) + ', len(pricehistory)=' + str(len(pricehistory['candles'])) )
		return False, [], []

	return stochrsi, k, d


# Return numpy array of Stochastic RSI values for a given price history.
# Reference: https://tulipindicators.org/stochrsi
# 'pricehistory' should be a data list obtained from get_pricehistory()
def get_stochmfi(pricehistory=None, mfi_period=14, mfi_k_period=128, mfi_d_period=3, slow_period=3, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_stochmfi(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, []

	# get_mfi + ti.stoch
	# Use ti.stoch() to get k and d values
	#   K measures the strength of the current move relative to the range of the previous n-periods
	#   D is a simple moving average of the K
	mfi = []
	mfi_k = []
	mfi_d = []
	try:
		mfi = get_mfi(pricehistory, period=mfi_period)
		mfi_k, mfi_d = ti.stoch( mfi, mfi, mfi, mfi_k_period, slow_period, mfi_d_period )

	except Exception as e:
		print( 'Caught Exception: get_stochmfi(' + str(ticker) + '): ti.stoch(): ' + str(e) + ', len(pricehistory)=' + str(len(pricehistory['candles'])) )
		return False, []

	return mfi_k, mfi_d


# Return numpy array of Stochastic Oscillator values for a given price history.
# Reference: https://tulipindicators.org/stoch
# 'pricehistory' should be a data list obtained from get_pricehistory()
#
# K measures the strength of the current move relative to the range of the previous n-periods
# D is a simple moving average of the K
def get_stoch_oscillator(pricehistory=None, type=None, k_period=14, d_period=3, slow_period=1, debug=False):

	if ( pricehistory == None ):
		print('Error: get_stoch_oscillator(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( type == None ):
		high = []
		low = []
		close = []
		for key in pricehistory['candles']:
			high.append(float(key['high']))
			low.append(float(key['low']))
			close.append(float(key['close']))

	elif ( type == 'hlc3' ):
		high = []
		low = []
		close = []
		for key in pricehistory['candles']:
			close.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )
		high = low = close

	elif ( type == 'hlc4' ):
		high = []
		low = []
		close = []
		for key in pricehistory['candles']:
			close.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )
		high = low = close

	else:
		# Undefined type
		print('Error: get_stoch_oscillator(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False, []

	try:
		high = np.array( high )
		low = np.array( low )
		close = np.array( close )
		fastk, fastd = ti.stoch( high, low, close, k_period, slow_period, d_period )

	except Exception as e:
		print('Caught Exception: get_stoch_oscillator(' + str(ticker) + '): ' + str(e))
		return False, []

	return fastk, fastd


# Takes the pricehistory and returns a pandas dataframe with the VWAP
# Example:
#   data, epochs = tda_gobot_helper.get_pricehistory(stock, 'day', 'minute', '1', 1, needExtendedHoursData=True, debug=False)
#   tda_gobot_helper.get_vwap(data)
#
# I'm honestly not sure I'm doing this right :)
#
#  1) Calculate the Typical Price for the period. [(High + Low + Close)/3)]
#  2) Multiply the Typical Price by the period Volume (Typical Price x Volume)
#  3) Create a Cumulative Total of Typical Price. Cumulative(Typical Price x Volume)
#  4) Create a Cumulative Total of Volume. Cumulative(Volume)
#  5) Divide the Cumulative Totals
#
#  VWAP = Cumulative(Typical Price x Volume) / Cumulative(Volume)
#
# day - since vwap is a daily indicator, by default we start the calculation on the current
#	day and skip any pricehistory candles before it. When backtesting historic data, 'day'
#	should be a date string (2021-05-21).
# end_timestamp = the last timestamp of the day, used for backtesting historic data.
# use_bands = calculate the stddev bands if desired. In some cases these are not needed and
#	skipping this step saves time.
# num_stddev = the standard deviation to use for the bands
def get_vwap(pricehistory=None, day='today', end_timestamp=None, use_bands=True, num_stddev=2, debug=False):

	if ( pricehistory == None ):
		return False, [], []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	try:
		assert mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	if ( day != None ):
		if ( day == 'today' ):
			today = datetime.now(mytimezone).strftime('%Y-%m-%d')
		else:
			today = day # must be in %Y-%m-%d format or we'll choke later

		day_start = datetime.strptime(str(today) + ' 01:00:00', '%Y-%m-%d %H:%M:%S')
		day_start = mytimezone.localize(day_start)
		day_start = int( day_start.timestamp() * 1000 )

	# Calculate VWAP
	prices = np.array([[1,1,1]])
	for key in pricehistory['candles']:
		if ( day != None and float(key['datetime']) < day_start ):
			continue

		price = ( float(key['high']) + float(key['low']) + float(key['close']) ) / 3
		prices = np.append( prices, [[float(key['datetime']), price, float(key['volume'])]], axis=0 )

		if ( end_timestamp != None ):
			if ( float(key['datetime']) >= float(end_timestamp) ):
				break

	# Remove the first value used to initialize np array
	prices = np.delete(prices, 0, axis=0)

	columns = ['DateTime', 'AvgPrice', 'Volume']
	df = pd.DataFrame(data=prices, columns=columns)
	q = df.Volume.values
	p = df.AvgPrice.values

	# Check for 0 values in q (volume), which would mess up our vwap calculation below
	for idx,val in enumerate(q):
		if ( val == 0 ):
			q[idx] = 1
	for idx,val in enumerate(p):
		if ( val == 0 or str(val) == '.0' ):
			p[idx] = p[-5] # arbitrary price value

	# vwap = Cumulative(Typical Price x Volume) / Cumulative(Volume)
	try:
		vwap = df.assign(vwap=(p * q).cumsum() / q.cumsum())

	except Exception as e:
		print('Caught exception: get_vwap(' + str(ticker) + '): ' + str(e), file=sys.stderr)
		return False, [], []

	vwap = vwap['vwap'].to_numpy()
	if ( use_bands == False ):
		return vwap, [], []

	# Calculate the standard deviation for each bar and the upper/lower bands
	vwap_up = []
	vwap_down = []
	vwap_sum = float(0)
	vwap_stddev_cumsum = float(0)

	for idx,val in enumerate(vwap):
		vwap_sum += val
		vwap_avg = vwap_sum / (idx + 1)
		vwap_stddev_cumsum += (val - vwap_avg) ** 2

		stdev = np.sqrt( vwap_stddev_cumsum / (idx + 1) )

		vwap_up.append( val + stdev * num_stddev )
		vwap_down.append( val - stdev * num_stddev )

	if ( debug == True ):
		idx = 0
		for key in pricehistory['candles']:
			if ( day == True and float(key['datetime']) < day_start ):
				continue

			date = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
			print( 'Date: ' + str(date) +
				', VWAP: ' + str(vwap[idx]) +
				', VWAP_UP: ' + str(vwap_up[idx]) +
				', VWAP_DOWN: ' + str(vwap_down[idx]) )

			idx += 1

	return vwap, vwap_up, vwap_down


# Calculate Bollinger Bands
def get_bbands(pricehistory=None, type='hlc3', period=20, stddev=2, matype=0, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_bbands(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, [], []

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_bbands(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False, [], []

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_bbands(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)

	# ti.bbands
	bbands_lower	= []
	bbands_middle	= []
	bbands_upper	= []
	try:
		#prices = np.array( prices )
		#bbands_lower, bbands_middle, bbands_upper = ti.bbands(prices, period, stddev)

		df = pd.DataFrame(data=prices, columns = ['prices'])
		bbands_upper, bbands_middle, bbands_lower = talib.BBANDS(df['prices'], timeperiod=period, nbdevup=stddev, nbdevdn=stddev, matype=matype)

	except Exception as e:
		print( 'Caught Exception: get_bbands(' + str(ticker) + '): ti.bbands(): ' + str(e) + ', len(pricehistory)=' + str(len(pricehistory['candles'])) )
		return False, [], []

	# Normalize the size of bbands_*[] to match the input size
	bbands_lower	= list( bbands_lower.fillna(0).values )
	bbands_middle	= list( bbands_middle.fillna(0).values )
	bbands_upper	= list( bbands_upper.fillna(0).values )

	# Tulipy:
	#tmp = []
	#for i in range(0, period - 1):
	#	tmp.append(0)
	#
	#bbands_lower	= tmp + list(bbands_lower)
	#bbands_middle	= tmp + list(bbands_middle)
	#bbands_upper	= tmp + list(bbands_upper)

	return bbands_lower, bbands_middle, bbands_upper


# Calculate the Keltner channel upper, middle and lower lines
def get_kchannels(pricehistory=None, type='hlc3', period=20, matype='ema', atr_period=None, atr_multiplier=1.5, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_kchannels(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, [], []

	if ( atr_period == None ):
		atr_period = period

	# Keltner Channel Middle Line	= MA
	# Keltner Channel Upper Band	= MA+2∗ATR
	# Keltner Channel Lower Band	= MA−2∗ATR
	ma	= []
	fama	= []
	atr	= []
	natr	= []
	try:
		if ( matype == 'mama' ):
			ma, fama = get_alt_ma(pricehistory=pricehistory, period=period, ma_type=matype, type=type)
		else:
			ma = get_alt_ma(pricehistory=pricehistory, period=period, ma_type=matype, type=type)

	except Exception as e:
		print('Error: get_kchannel(' + str(ticker) + '): unable to calculate EMA: ' + str(e))
		return False, [], []

	try:
		atr, natr = get_atr( pricehistory, period=atr_period )

	except Exception as e:
		print('Error: get_kchannel(' + str(ticker) + '): unable to calculate ATR: ' + str(e))
		return False, [], []

	# Normalize the size of ma[] and atr[] to match the input size
	tmp = []
	for i in range(0, atr_period - 1):
		tmp.append(0)
	atr = tmp + list(atr)

	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(ma)):
		tmp.append(0)
	ma = tmp + list(ma)

	# Calculate the upper/lower values
	kchannel_mid	= ma
	kchannel_upper	= []
	kchannel_lower	= []
	for idx in range(0, len(ma)):
		kchannel_upper.append(ma[idx] + (atr[idx] * atr_multiplier) )
		kchannel_lower.append(ma[idx] - (atr[idx] * atr_multiplier) )

	return kchannel_lower, kchannel_mid, kchannel_upper


# Get MACD
def get_macd(pricehistory=None, short_period=12, long_period=26, signal_period=9, debug=False):

	if ( pricehistory == None ):
		return False, [], []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( len(pricehistory['candles']) < short_period ):
		# Possibly this ticker is too new, not enough history
		print( 'Warning: get_macd(' + str(ticker) + ', ' + str(period) + '): len(pricehistory) is less than short_period (' +
			str(len(pricehistory['candles'])) + ') - unable to calculate MACD')
		return False, [], []

	# Put pricehistory close prices into a numpy array
	prices = []
	try:
		for key in pricehistory['candles']:
			prices.append( float(key['close']) )

		prices = np.array( prices )

	except Exception as e:
		print('Caught Exception: get_macd(' + str(ticker) + '): ' + str(e))
		return False, [], []

	# Calculate the macd, macd_signal and histogram
	try:
		macd, macd_signal, macd_histogram = ti.macd(prices, short_period, long_period, signal_period)

	except Exception as e:
		print('Caught Exception: get_macd(' + str(ticker) + '): ti.macd(): ' + str(e))
		return False, [], []

	if ( debug == True ):
		print(macd)
		print(macd_signal)
		print(macd_histogram)

	return macd, macd_signal, macd_histogram


# Choppiness Index
def get_chop_index(pricehistory=None, period=20, debug=False):

	if ( pricehistory == None ):
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Put pricehistory data into a numpy array
	high = []
	low = []
	for key in pricehistory['candles']:
		high.append( float(key['high']) )
		low.append( float(key['low']) )

	high = np.array( high )
	low = np.array( low )

	# Get ATR
	atr = []
	natr = []
	try:
		atr, natr = get_atr(pricehistory, period=period)

	except Exception as e:
		print('Caught Exception: get_chop_index(' + str(ticker) + '): ' + str(e))
		return False

	# Initialize all the arrays we'll need
	atr = np.array(atr)
	atr_sum = np.array(atr)
	atr_ratio = np.array(atr)
	high_low_range = np.array(atr)
	chop = np.array(atr)

	# Calculate the sum of ATR values
	for i in range(len(atr)):
		atr_sum[i] = atr[i - period + 1:i + 1].sum()

	# Calculate the high/low range
	for i in range(len(high)):
		try:
			high_low_range[i] = max(high[i - period + 1:i + 1], default=0) - min(low[i - period + 1:i + 1], default=0)
		except:
			pass

	# Calculate the ATR/range ratio
	with np.errstate( divide='ignore', invalid='ignore' ):
		atr_ratio[:] = atr_sum[:] / high_low_range[:]

	atr_ratio[np.isnan(atr_ratio)] = -1

	# Calculate the Choppiness Index
	for i in range(len(atr_ratio)):
		if ( atr_ratio[i] == 0 or atr_ratio[i] == -1 ):
			continue
		chop[i] = 100 * np.log(atr_ratio[i]) * (1 / np.log(period))

	return list(chop)


# Supertrend index
def get_supertrend(pricehistory=None, multiplier=3, atr_period=128):

	if ( pricehistory == None ):
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	atr	= []
	natr	= []
	try:
		atr, natr = get_atr(pricehistory=pricehistory, period=atr_period)

	except Exception as e:
		print('Caught exception: get_supertrend(' + str(ticker) + '): ' + str(e))
		return False

	# Ensure length of atr[] matches length of pricehistory['candles']
	atr = list(atr)
	filler = len(pricehistory['candles']) - len(atr)
	for i in range(filler):
		atr.insert(0,0)

	# Calculate the initial upper/lower bands
	avg_price	= 0
	upper_band	= []
	lower_band	= []
	for i in range(0, len(pricehistory['candles'])):
		cur_high = float( pricehistory['candles'][i]['high'] )
		cur_low = float( pricehistory['candles'][i]['low'] )

		# Average Price
		avg_price = (cur_high + cur_low) / 2

		# Basic Upper Band
		upper_band.append( avg_price + (multiplier * atr[i]) )

		# Lower Band
		lower_band.append( avg_price - (multiplier * atr[i]) )

	# Final Upper Band
	final_upper = []
	for i in range(0, len(pricehistory['candles'])):
		prev_close = float( pricehistory['candles'][i-1]['close'] )

		if ( i == 0 ):
			final_upper.append(0)

		else:
			if ( upper_band[i] < final_upper[i-1] or prev_close > final_upper[i-1] ):
				final_upper.append( upper_band[i] )

			else:
				final_upper.append( final_upper[i-1] )

	# Final Lower Band
	final_lower = []
	for i in range(0, len(pricehistory['candles'])):
		prev_close = float( pricehistory['candles'][i-1]['close'] )

		if ( i == 0 ):
			final_lower.append(0)

		else:
			if ( lower_band[i] > final_lower[i-1] or prev_close < final_lower[i-1] ):
				final_lower.append(lower_band[i])

			else:
				final_lower.append(final_lower[i-1])

	# SuperTrend
	supertrend = []
	for i in range(0, len(pricehistory['candles'])):
		cur_close = float( pricehistory['candles'][i]['close'] )

		if ( i == 0 ):
			supertrend.append(0)

		elif ( supertrend[i-1] == final_upper[i-1] and cur_close <= final_upper[i] ):
			supertrend.append(final_upper[i])

		elif ( supertrend[i-1] == final_upper[i-1] and cur_close > final_upper[i] ):
			supertrend.append(final_lower[i])

		elif ( supertrend[i-1] == final_lower[i-1] and cur_close >= final_lower[i] ):
			supertrend.append(final_lower[i])

		elif ( supertrend[i-1] == final_lower[i-1] and cur_close < final_lower[i] ):
			 supertrend.append(final_upper[i])


	return supertrend


# Return the key levels for a stock
# Preferably uses weekly candle data for pricehistory
# If filter=True, we use ATR to help filter the data and remove key levels that are
#   within one ATR from eachother
# If plot=True we will attempt to plot the keylevels as candles
def get_keylevels(pricehistory=None, atr_period=14, filter=True, plot=False, debug=False):

	if ( pricehistory == None ):
		return False, []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Determine if level is a support pivot based on five-candle fractal
	def is_support(df, i, filter=True):
		support = False
		try:

			# Use five-candle fractal
			support_1 =	df['low'][i] <= df['low'][i-1] and \
					df['low'][i] <= df['low'][i+1] and \
					df['low'][i+1] <= df['low'][i+2] and \
					df['low'][i-1] <= df['low'][i-2]


			# Test four-candle fractals
			support_2 =	df['low'][i] <= df['low'][i-1] and \
					df['low'][i] <= df['low'][i+1] and \
					df['low'][i+1] <= df['low'][i+2]

			support_3 =	df['low'][i] <= df['low'][i-1] and \
					df['low'][i] <= df['low'][i+1] and \
					df['low'][i-1] <= df['low'][i-2]

		except Exception as e:
			print('Exception caught: get_keylevels(' + str(ticker) + '): is_support(): ' + str(e) + '. Ignoring level (' + str(df['low'][i]) + ').' )
			return False, []

		if ( support_1 == True or support_2 == True or support_3 == True ):
			return True

		return False

	# Determine if level is a resistance pivot based on five-candle fractal
	def is_resistance(df, i, filter=True):
		resistance = False
		try:

			# Use five-candle fractal
			resistance_1 =	df['high'][i] >= df['high'][i-1] and \
					df['high'][i] >= df['high'][i+1] and \
					df['high'][i+1] >= df['high'][i+2] and \
					df['high'][i-1] >= df['high'][i-2]


			# Test four-candle fractals
			resistance_2 =	df['high'][i] >= df['high'][i-1] and \
					df['high'][i] >= df['high'][i+1] and \
					df['high'][i+1] >= df['high'][i+2]

			resistance_3 =	df['high'][i] >= df['high'][i-1] and \
					df['high'][i] >= df['high'][i+1] and \
					df['high'][i-1] >= df['high'][i-2]

		except Exception as e:
			print('Exception caught: get_keylevels(' + str(ticker) + '): is_resistance(): ' + str(e) + '. Ignoring level (' + str(df['high'][i]) + ').' )
			return False, []

		if ( resistance_1 == True or resistance_2 == True or resistance_3 == True ):
			return True

		return False

	# Reduce noise by eliminating levels that are close to levels that
	#   have already been discovered
	def check_atr_level( lvl=None, atr=1, levels=[] ):
		levels_t = []
		if ( len(levels) > 0 and isinstance(levels[0], tuple) ):
			for i in levels:
				levels_t.append(i[0])

		return np.sum( [abs(lvl - x) < atr for x in levels_t] ) == 0


	# Need to massage the data to ensure matplotlib works
	if ( plot == True ):
		try:
			assert mytimezone
		except:
			mytimezone = timezone("US/Eastern")

		ph = []
		for key in pricehistory['candles']:

			d = {	'Date':		datetime.fromtimestamp(int(key['datetime'])/1000, tz=mytimezone),
				'open':		float( key['open'] ),
				'high':		float( key['high'] ),
				'low':		float( key['low'] ),
				'close':	float( key['close'] ),
				'volume':	float( key['volume'] ),
				'datetime':	int( key['datetime'] ) }

			ph.append(d)

		df = pd.DataFrame(data=ph, columns = ['Date', 'open', 'high', 'low', 'close', 'volume', 'datetime'])
		df = df.loc[:,['Date', 'open', 'high', 'low', 'close', 'volume', 'datetime']]

	else:
		df = pd.DataFrame(data=pricehistory['candles'], columns = ['open', 'high', 'low', 'close', 'volume', 'datetime'])

	# Process all candles and check for five-candle fractal levels, and append them to long_support[] or long_resistance[]
	long_support = []
	long_resistance = []
	plot_support_levels = []
	plot_resistance_levels = []
	for i in range( 2, df.shape[0]-2 ):

		# SUPPORT
		if ( is_support(df, i, filter) ):
			lvl	= float( df['low'][i] )
			dt	= int( df['datetime'][i] )
			if ( filter == False ):
				long_support.append( (lvl, dt) )
				if ( plot == True ):
					plot_support_levels.append( (i, lvl) )

				continue

			# Find the average true range for this particular time period, which we
			#  will pass to check_atr_level() to reduce noise
			#
			# Alternative solution:
			#   atr = np.mean( df['high'] - df['low'] )
			atr = []
			tmp_ph = { 'candles': [], 'ticker': ticker }
			if ( i < atr_period + 1 ):
				for idx in range( 0, atr_period + 1 ):
					tmp_ph['candles'].append( pricehistory['candles'][idx] )

			else:
				for idx in range( 0, i ):
					tmp_ph['candles'].append( pricehistory['candles'][idx] )

			try:
				atr, natr = get_atr(pricehistory=tmp_ph, period=atr_period)

			except Exception as e:
				print('Exception caught: get_keylevels(' + str(ticker) + '): get_atr(): ' + str(e) + '. Falling back to np.mean().')
				atr.append( np.mean(df['high'] - df['low']) )

			# Check if this level is at least one ATR value away from a previously
			#   discovered level
			if ( check_atr_level(lvl, atr[-1], long_support) ):
				long_support.append( (lvl, dt) )
				if ( plot == True ):
					plot_support_levels.append( (i, lvl) )

		# RESISTANCE
		elif ( is_resistance(df, i, filter) ):
			lvl	= float( df['high'][i] )
			dt	= int( df['datetime'][i] )
			if ( filter == False ):
				long_resistance.append( (lvl, dt) )
				if ( plot == True ):
					plot_resistance_levels.append( (i, lvl) )

				continue

			# Find the average true range for this particular time period, which we
			#  will pass to check_atr_level() to reduce noise
			#
			# Alternative solution:
			#   atr = np.mean( df['high'] - df['low'] )
			atr = []
			tmp_ph = { 'candles': [], 'ticker': ticker }
			if ( i < atr_period + 1 ):
				for idx in range( 0, atr_period + 1 ):
					tmp_ph['candles'].append( pricehistory['candles'][idx] )
			else:
				for idx in range( 0, i ):
					tmp_ph['candles'].append( pricehistory['candles'][idx] )

			try:
				atr, natr = get_atr(pricehistory=tmp_ph, period=atr_period)

			except Exception as e:
				print('Exception caught: get_keylevels(' + str(ticker) + '): get_atr(): ' + str(e) + '. Falling back to np.mean().')
				atr.append( np.mean(float(df['high']) - float(df['low'])) )

			# Check if this level is at least one ATR value away from a previously
			#   discovered level
			if ( check_atr_level(lvl, atr[-1], long_resistance) ):
				long_resistance.append( (lvl, dt) )
				if ( plot == True ):
					plot_resistance_levels.append( (i, lvl) )


	# Iterate through long_support and long_resistance and count how many times
	#  a keylevel has been hit (within 1.5%). We can use the later to help
	#  gauge importance.
	long_support_new	= []
	for idx in range( len(long_support) ):
		lvl	= long_support[idx][0]
		dt	= long_support[idx][1]
		count	= 1
		for idx2 in range( idx, len(long_support) ):
			if ( idx == idx2 ):
				continue

			lvl2 = long_support[idx2][0]
			if ( abs(lvl / lvl2 - 1) * 100 < 1.5 ):
				count += 1

		long_support_new.append( (lvl, dt, count) )

	long_resistance_new	= []
	for idx in range( len(long_resistance) ):
		lvl	= long_resistance[idx][0]
		dt	= long_resistance[idx][1]
		count	= 1
		for idx2 in range( idx, len(long_resistance) ):
			if ( idx == idx2 ):
				continue

			lvl2 = long_resistance[idx2][0]
			if ( abs(lvl / lvl2 - 1) * 100 < 1.5 ):
				count += 1

		long_resistance_new.append( (lvl, dt, count) )


	# Plot the result if requested
	if ( plot == True ):
		from mplfinance.original_flavor import candlestick_ohlc
		import matplotlib.dates as mpl_dates
		import matplotlib.pyplot as plt

		plt.rcParams['figure.figsize'] = [12, 7]
		plt.rc('font', size=14)

		df['Date'] = df['Date'].apply(mpl_dates.date2num)

		fig, ax = plt.subplots()
		candlestick_ohlc( ax, df.values, width=0.6, colorup='green', colordown='red', alpha=0.8 )

		date_format = mpl_dates.DateFormatter('%d-%m-%Y')
		ax.xaxis.set_major_formatter(date_format)
		fig.autofmt_xdate()

		fig.tight_layout()

		for level in plot_support_levels:
			plt.hlines(level[1], xmin=df['Date'][level[0]], xmax=max(df['Date']), colors='blue')
		for level in plot_resistance_levels:
			plt.hlines(level[1], xmin=df['Date'][level[0]], xmax=max(df['Date']), colors='red')

		plt.show()


	return long_support_new, long_resistance_new


# Calculate the rate of change
def get_roc(pricehistory=None, type='hlc3', period=50, calc_percentage=False, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_roc(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_roc(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_roc(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)

	roc = []
	try:
		prices = np.array( prices )
		roc = ti.roc( prices, period=period )

	except Exception as e:
		print('Error: get_roc(' + str(ticker) + '): unable to calculate rate of change: ' + str(e))
		return False

	# Unlike other tools, ti.roc() does not multiply the rate-of-change by 100 to produce a percentage.
	#  That usually doesn't matter, but sometimes it's desirable.
	if ( calc_percentage == True ):
		for i in range( len(roc) ):
			roc[i] = roc[i] * 100

	# Handle inf/-inf data points
	roc = np.nan_to_num(roc, copy=True)

	# Normalize the size of roc[] to match the input size
	tmp = []
	for i in range(0, period):
		tmp.append(0)
	roc = tmp + list(roc)

	return roc


# Momentum indicator
def get_momentum(pricehistory=None, type='hl2', period=12, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_momentum(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, [], []

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_momentum(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False, [], []

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_momentum(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)

	mom		= []
	trix		= []
	trix_signal	= []
	try:
		prices		= np.array( prices )
		mom		= ti.mom( prices, period=period )
		trix		= ti.trix( prices, period=period )

		mom		= np.nan_to_num(mom)
		trix		= np.nan_to_num(trix)

		trix_signal	= ti.ema(trix, period=3)

	except Exception as e:
		print('Error: get_momentum(' + str(ticker) + '): unable to calculate rate of change: ' + str(e))
		return False, [], []

	# Normalize the size of the arrays to match the input size
	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(mom)):
		tmp.append(0)
	mom = tmp + list(mom)

	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(trix)):
		tmp.append(0)
	trix = tmp + list(trix)

	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(trix_signal)):
		tmp.append(0)
	trix_signal = tmp + list(trix_signal)

	return mom, trix, trix_signal


# Momentum indicator
def get_trix_altma(pricehistory=None, ma_type='kama', type='hl2', period=24, signal_ma='ema', signal_period=3, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_trix_altma(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, []

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_trix_altma(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False, []

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_momentum(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)

	trix		= []
	trix_signal	= []
	try:
		prices	= np.array( prices )
		prices	= np.log( prices )

		# Step 1 - get the moving average of the log() of the prices
		ph = { 'candles': [] }
		for i in range( len(prices) ):
			ph['candles'].append( { 'close': prices[i] } )

		trix = get_alt_ma( ph, ma_type=ma_type, period=period, type='close' )

		# Step 2 - get the moving average of the results
		ph = { 'candles': [] }
		for i in range( len(trix) ):
			ph['candles'].append( { 'close': trix[i] } )

		trix = get_alt_ma( ph, ma_type=ma_type, period=period, type='close' )

		# Step 3 - One more time
		ph = { 'candles': [] }
		for i in range(len(trix)):
			ph['candles'].append( { 'close': trix[i] } )

		trix = get_alt_ma( ph, ma_type=ma_type, period=period, type='close' )
		trix = np.nan_to_num( trix )

		# Step 4 - The indicator should oscillate across a zero line
		for i in range( len(trix) ):
			try:
				trix[i] = (trix[i] - tr[i-1]) * 100
			except:
				pass

		# Step 5 - Generate the signal line
		ph = { 'candles': [] }
		for i in range( len(trix) ):
			ph['candles'].append( { 'close': trix[i] } )

		trix_signal = get_alt_ma( ph, ma_type=signal_ma, period=signal_period, type='close' )

	except Exception as e:
		print('Error: get_momentum(' + str(ticker) + '): unable to calculate rate of change: ' + str(e))
		return False, []

	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(trix)):
		tmp.append(0)
	trix = tmp + list(trix)

	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(trix_signal)):
		tmp.append(0)
	trix_signal = tmp + list(trix_signal)

	return trix, trix_signal


# John Ehlers' MESA sine wave
def get_mesa_sine(pricehistory=None, type='hl2', period=25, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_mesa_sine(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_mesa_sine(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_mesa_sine(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)


	# MESA sine wave calculations
	import math
	sign = lambda x: math.copysign(1, x)

	sine_out = []
	lead_out = []
	for idx,key in enumerate(pricehistory['candles']):
		try:
			assert idx > period
		except:
			continue

		price		= float(0)
		sine		= float(0)
		lead		= float(0)

		real_part	= 0
		imag_part	= 0
		for i in range(period):
			real_part	= real_part + prices[idx-i] * math.cos( 2 * math.pi * (i+1) / period )
			imag_part	= imag_part + prices[idx-i] * math.sin( 2 * math.pi * (i+1) / period )

		phase1 = 0
		if ( abs(real_part) > 0.001 ):
			phase1 = math.atan( imag_part / real_part )
		else:
			phase1 = ( math.pi / 2 * sign(imag_part) )

		phase2 = phase1
		if ( real_part < 0 ):
			phase2 = phase1 + math.pi

		phase = phase2
		if ( phase2 < 0 ):
			phase = phase2 + 2 * math.pi

		elif ( phase2 > 2 * math.pi ):
			phase = phase2 - 2 * math.pi

		sine	= math.cos( phase )
		lead	= math.cos( phase + math.pi / 4 )

		sine_out.append(sine)
		lead_out.append(lead)

	# Normalize the size of sine_out[] and lead_out[] to match the input size
	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(sine_out) ):
		tmp.append(0)
	sine_out = tmp + list(sine_out)
	lead_out = tmp + list(lead_out)

	return sine_out, lead_out


# John Ehlers's Empirical Mode Decomposition (EMD)
# https://mesasoftware.com/papers/EmpiricalModeDecomposition.pdf
# "If the trend is above the upper threshold the market is in an uptrend. If the trend is
# below the lower threshold the market is in a downtrend. When the trend falls between
# the two threshold levels the market is in a cycle mode."
#
# "The setting of the fraction of the averaged peaks and valleys to be used to
# establish the thresholds is somewhat subjective and can be adjusted to fit your
# trading style. Personally, we prefer to trade in the cycle mode and therefore
# tend to set the thresholds relatively far apart. In this way one can stop swing
# trading when the market is clearly in a trend."
def get_mesa_emd(pricehistory=None, type='hl2', period=20, delta=0.5, fraction=0.1, plot=False, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_mesa_emd(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	prices = []
	if ( type == 'close' ):
		for key in pricehistory['candles']:
			prices.append(float(key['close']))

	elif ( type == 'high' ):
		for key in pricehistory['candles']:
			prices.append(float(key['high']))

	elif ( type == 'low' ):
		for key in pricehistory['candles']:
			prices.append(float(key['low']))

	elif ( type == 'open' ):
		for key in pricehistory['candles']:
			prices.append(float(key['open']))

	elif ( type == 'volume' ):
		for key in pricehistory['candles']:
			prices.append(float(key['volume']))

	elif ( type == 'hl2' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low'])) / 2 )

	elif ( type == 'hlc3' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )

	elif ( type == 'ohlc4' ):
		for key in pricehistory['candles']:
			prices.append( (float(key['open']) + float(key['high']) + float(key['low']) + float(key['close'])) / 4 )

	else:
		# Undefined type
		print('Error: get_mesa_emd(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_mesa_emd(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)

	# EMD calculations
	import math

	def average( data=None, period=0 ):
		mean = 0
		for i in range( -period, 0 ):
			mean += data[i]
		return mean / period

	alpha		= float(0)
	beta		= float(0)
	gamma		= float(0)
	bp		= float(0)
	bp_hist		= []
	mean		= []

	peak		= float(0)
	valley		= float(0)
	avg_peak	= []
	avg_valley	= []
	peak_hist	= []
	valley_hist	= []

	beta		= math.cos(360 / period)
	gamma		= 1 / math.cos( 720 * delta / period )
	alpha		= gamma - math.sqrt(gamma * gamma - 1 )

	# https://www.quantconnect.com/forum/discussion/941/john-ehlers-empirical-mode-decomposition/p1
	# The code from the link above uses math.pi for some reason, which is different from Ehlers's paper
	#beta   = math.cos(2 * math.pi / period)
	#gamma  = 1 / math.cos(4 * math.pi * delta / period)
	#alpha  = gamma - math.sqrt(math.pow(gamma, 2) - 1)

	for idx in range( len(prices) ):
		try:
			assert idx > 1
		except:
			continue

		if ( len(bp_hist) > 1 ):
			bp = 0.5 * (1 - alpha) * (prices[idx] - prices[idx-2]) + beta * (1 + alpha) * bp_hist[-1] - alpha * bp_hist[-2]
		else:
			bp = 0.5 * (1 - alpha) * (prices[idx] - prices[idx-2])

		bp_hist.append(bp)

		if ( len(bp_hist) > period*2-1 ):
			mean.append( average(bp_hist, period*2) )

	# Normalize mean
	tmp = []
	for i in range(0, len(prices) - len(mean)):
		tmp.append(0)
	mean = tmp + list(mean)

	# Calculate the peaks and valleys, and then average them to produce a moving average
	for idx in range( len(bp_hist) ):
		try:
			assert idx > 2
		except:
			continue

		peak = valley = 0
		if ( len(peak_hist) > 1 ):
			peak = peak_hist[-1]
			valley = valley_hist[-1]

		if ( bp_hist[idx-1] > bp_hist[idx] and bp_hist[idx-1] > bp_hist[idx-2] ):
			peak = bp_hist[idx-1]
		elif ( bp_hist[idx-1] < bp_hist[idx] and bp_hist[idx-1] < bp_hist[idx-2] ):
			valley = bp_hist[idx-1]

		peak_hist.append(peak)
		valley_hist.append(valley)

		if ( len(peak_hist) > 50 ):
			avg_peak.append( fraction * average(peak_hist, 50) )
			avg_valley.append( fraction * average(valley_hist, 50) )

	# Normalize avg_peak and avg_valley
	tmp = []
	for i in range(0, len(prices) - len(avg_peak)):
		tmp.append(0)
	avg_peak	= tmp + list(avg_peak)
	avg_valley	= tmp + list(avg_valley)

	# Plot
	if ( plot == True ):
		import matplotlib.pyplot as plt

		plt.title('Empirical Mode Decomposition (' + str(ticker) + ')')
		plt.plot(mean, label='Trend')
		plt.plot(avg_peak, label='Avg_Peak')
		plt.plot(avg_valley, label='Avg_Valley')
		plt.legend(['Trend', 'Avg_Peak', 'Avg_Valley'], loc = 'upper left')
		plt.show()

	# Print comma-delimited data for debugging
	if ( debug == True ):
		try:
			assert mytimezone
		except:
			mytimezone = timezone("US/Eastern")

		dt = []
		for key in pricehistory['candles']:
			tmp = datetime.fromtimestamp(int(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S')
			dt.append(tmp)

		for i in range(len(dt)):
			print(str(dt[i]) + ',' + str(mean[i])  + ',' + str(avg_peak[i])  + ',' + str(avg_valley[i]))


	return mean, avg_peak, avg_valley


# Fisher Transform
def get_fisher_transform(pricehistory=None, period=20, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_fisher_transform(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, []

	# Fisher transform takes two arrays that contain the high and low prices
	high_p	= []
	low_p	= []
	for key in pricehistory['candles']:
		high_p.append( float(key['high']) )
		low_p.append( float(key['low']) )

	if ( len(high_p) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_fisher_transform(' + str(ticker) + '): len(pricehistory[candles]) is less than period - is this a new stock ticker?', file=sys.stderr)
		return [], []

	# Calculate the Fisher transform
	fisher		= []
	fisher_signal	= []
	try:
		high_p	= np.array( high_p )
		low_p	= np.array( low_p )

		fisher, fisher_signal = ti.fisher(high_p, low_p, period)

	except Exception as e:
		print('Error: get_fisher_transform(' + str(ticker) + '): unable to calculate fisher transform: ' + str(e))
		return False, []

	# Normalize the size of returned arrays[] to match the input size
	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(fisher)):
		tmp.append(0)
	fisher		= tmp + list(fisher)
	fisher_signal	= tmp + list(fisher_signal)

	return fisher, fisher_signal


# Fisher transform based on John Ehlers's EasyLanguage code
#  https://www.mesasoftware.com/papers/UsingTheFisherTransform.pdf
#
# MaxH = Highest(Price, Len);
# MinL = Lowest(Price, Len);
# Value1 = .33*2*((Price - MinL)/(MaxH - MinL) - .5) + .67*Value1[1];
# If Value1 > .99 then Value1 = .999;
# If Value1 < -.99 then Value1 = -.999;
# Fish = .5*Log((1 + Value1)/(1 - Value1)) + .5*Fish[1];
#
# Hey, it turns out this code produces the exact same output as the function
#  above, get_fisher_transform(). I didn't know that, I thought Ehlers was
#  doing something a bit different so wasted some time rewriting it based on
#  his paper, lol.
def get_mesa_fisher_transform(pricehistory=None, period=20, debug=False):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: get_fisher_transform(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, []

	# Calculate the Fisher transform
	import math

	n_val		= []
	fisher		= []
	fisher_signal	= []
	for idx,key in enumerate(pricehistory['candles']):
		try:
			assert idx > period - 1
		except:
			continue

		if ( len(fisher) == 0 ):
			n_val.append(1)
			fisher.append(1)
			continue

		high_p	= 0
		low_p	= 0
		hl2	= []
		for i in range(idx, idx-period, -1):
			hl2.append( (pricehistory['candles'][i]['high'] + pricehistory['candles'][i]['low']) / 2 )

		high_p	= max(hl2)
		low_p	= min(hl2)
		cur_hl2	= ( pricehistory['candles'][idx]['high'] + pricehistory['candles'][idx]['low'] ) / 2

		n_val.append( 0.33 * 2 * ( (cur_hl2 - low_p)/(high_p - low_p) - 0.5 ) + 0.67 * n_val[-1] )

		if ( n_val[-1] > 0.99 ):
			n_val[-1] = 0.999
		elif ( n_val[-1] < -0.99 ):
			n_val[-1] = -0.999

		fisher.append( 0.5 * math.log( (1 + n_val[-1])/(1 - n_val[-1]) ) + 0.5 * fisher[-1] )

	for i in range(len(fisher)):
		if ( i == 0 ):
			continue

		fisher_signal.append(fisher[i-1])


	# Normalize the size of returned arrays[] to match the input size
	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(fisher)):
		tmp.append(0)
	fisher = tmp + list(fisher)

	tmp = []
	for i in range(0, len(pricehistory['candles']) - len(fisher_signal)):
		tmp.append(0)
	fisher_signal = tmp + list(fisher_signal)


	return fisher, fisher_signal


# Calculate and return the Market Profile (Volume Profile)
# close_type: close, hl2 (default), hlc3, ohlc4
# mp_mode: vol (volume, default), tpo (trade price opportunity)
# tick_size: 0.01 (default), market_profile module default is actually 0.05
def get_market_profile(pricehistory=None, close_type='hl2', mp_mode='vol', tick_size=0.01, debug=False):

	if ( pricehistory == None ):
		print('Error: get_market_profile(): pricehistory is empty', file=sys.stderr)
		return False

	ticker = ''
	try:
		ticker = str( pricehistory['symbol'] )
	except:
		pass

	try:
		assert mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	try:
		float( tick_size )
	except Exception as e:
		print('Error: get_market_profile(): tick_size must be a number', file=sys.stderr)
		return False

	if ( mp_mode != 'vol' and mp_mode != 'tpo' ):
		print('Error: get_market_profile(): mode must be either "vol" or "tpo"', file=sys.stderr)
		return False

	# Import the market_profile module (pip3 install marketprofile)
	from market_profile import MarketProfile

	mprofile = OrderedDict()
	for key in pricehistory['candles']:
		open		= float( key['open'] )
		high		= float( key['high'] )
		low		= float( key['low'] )
		close		= float( key['close'] )
		volume		= int( key['volume'] )
		dt		= int( key['datetime'] / 1000 )

		if ( close_type == 'hl2' ):
			close = (high + low) / 2
		elif ( close_type == 'hlc3' ):
			close = (high + low + close ) / 3
		elif ( close_type == 'ohlc4' ):
			close = (open + high + low + close ) / 4
		elif ( close_type == 'close' ):
			pass
		else:
			return False

		day = datetime.fromtimestamp(dt, tz=mytimezone).strftime('%Y-%m-%d')
		if ( day not in mprofile ):
			mprofile[day] = { 'p_history': np.array([[1,1,1,1,1,1]]) }

		mprofile[day]['p_history'] = np.append( mprofile[day]['p_history'], [[dt,open,high,low,close,volume]], axis=0 )

	for day in mprofile.keys():
		mprofile[day]['p_history']	= np.delete( mprofile[day]['p_history'], 0, axis=0 )
		mprofile[day]['p_history']	= pd.DataFrame( data=mprofile[day]['p_history'], columns=['datetime', 'Open', 'High', 'Low', 'Close', 'Volume'] )
		posix_time			= pd.to_datetime( mprofile[day]['p_history']['datetime'], unit='s' )

		mprofile[day]['p_history'].insert( 0, "Date", posix_time )
		mprofile[day]['p_history'].drop( "datetime", axis = 1, inplace = True )

		mprofile[day]['p_history']	= mprofile[day]['p_history'].set_index( pd.DatetimeIndex(mprofile[day]['p_history']['Date'].values) )
		mprofile[day]['p_history'].Date	= mprofile[day]['p_history'].Date.dt.tz_localize(tz='UTC').dt.tz_convert(tz=mytimezone)
		mprofile[day]['p_history'].drop( columns=['Date'], axis=1, inplace=True )

	# Create MarketProfile object and populate the mprofile
	for day in mprofile.keys():
		mp		= MarketProfile( mprofile[day]['p_history'], tick_size=tick_size, mode='vol' )
		mp_slice	= mp[ mprofile[day]['p_history'].index.min():mprofile[day]['p_history'].index.max() ]

		mprofile[day]['val']			= mp_slice.value_area[0]
		mprofile[day]['vah']			= mp_slice.value_area[1]
		mprofile[day]['profile']		= mp_slice.profile
		mprofile[day]['initial_balance']	= mp_slice.initial_balance()
		mprofile[day]['open_range']		= mp_slice.open_range()
		mprofile[day]['poc_price']		= mp_slice.poc_price
		mprofile[day]['profile_range']		= mp_slice.profile_range
		mprofile[day]['balanced_target']	= mp_slice.balanced_target
		mprofile[day]['low_value_nodes']	= mp_slice.low_value_nodes
		mprofile[day]['high_value_nodes']	= mp_slice.high_value_nodes


	return mprofile

