#!/usr/bin/python3 -u

import os, sys, fcntl, re
import time

from datetime import datetime, timedelta
from pytz import timezone

import tulipy as ti
import numpy as np
import pandas as pd

from func_timeout import func_timeout, FunctionTimedOut

import tda_cndl_helper


# Login to tda using a passcode
def tdalogin(passcode=None):

	if ( passcode == None ):
		print('Error: tdalogin(): passcode is empty', file=sys.stderr)
		return False

	try:
		enc = func_timeout(10, tda.login, args=(passcode,))

	except FunctionTimedOut:
		print('Caught Exception: tdalogin(): timed out after 10 seconds' + str(e))
		return False

	except Exception as e:
		print('Caught Exception: tdalogin(): ' + str(e))
		return False

	if ( enc == '' ):
		print('Error: tdalogin(): tda.login return is empty', file=sys.stderr)
		return False

	return True


# Returns True if it is near the end of the trading day based
#  on the number of minutes from the top of the hour (4:00PM Eastern)
#
# Note: Nasdaq and NYSE open at 9:30AM and close at 4:00PM
#
# Examples:
#   isendofday(5) returns True if it's 5-minutes or less from market close (3:55)
#   isendofday(60) returns True if it's 60-minutes or less from market close (3:00)
def isendofday(mins=5, date=None):
	if ( mins < 0 or mins > 60 ):
		return False

	eastern = timezone('US/Eastern') # Observes EST and EDT

	if ( date == None ):
		est_time = datetime.now(eastern)
	elif ( type(date) is datetime ):
		est_time = date.replace(tzinfo=eastern)
	else:
		print('Error: isendofday(): date must be a datetime object')
		return False

	mins = 60 - int(mins)
	if ( int(est_time.strftime('%-H')) == 15 and int(est_time.strftime('%-M')) >= mins ):
		return True

	return False


# Returns True if it is currently near the beginning of a new trading day
#  Currently returns True if it's 15 minutes from the market open
def isnewday():
	eastern = timezone('US/Eastern') # Observes EST and EDT
	est_time = datetime.now(eastern)
	if ( int(est_time.strftime('%-H')) == 9 ):
		if ( int(est_time.strftime('%-M')) >= 30 and int(est_time.strftime('%-M')) <= 45 ):
			return True

	return False


# Returns True the US markets are open
# Nasdaq and NYSE open at 9:30AM and close at 4:00PM, Monday-Friday
def ismarketopen_US(date=None):
	eastern = timezone('US/Eastern') # Observes EST and EDT

	if ( date == None ):
		est_time = datetime.now(eastern)
	elif ( type(date) is datetime ):
		est_time = date.replace(tzinfo=eastern)
	else:
		print('Error: ismarketopen_US(): date must be a datetime object')
		return False

	# US market holidays - source: http://www.nasdaqtrader.com/trader.aspx?id=calendar
	# I'm hardcoding these dates for now since the other python modules (i.e. python3-holidays)
	#  do not quite line up with these days (i.e. Good Friday is not a federal holiday).

	# 2021-01-01 - New Year's Day
	# 2021-01-18 - Martin Luther King Jr. Day
	# 2021-02-15 - President's Day
	# 2021-04-02 - Good Friday
	# 2021-05-31 - Memorial Day
	# 2021-07-05 - Independence Day
	# 2021-09-06 - Labor Day
	# 2021-11-25 - Thanksgiving
	# 2021-11-26 - This is actually an early close day (1:00PM Eastern)
	# 2021-12-24 - Christmas Eve
	#  Note: 12-25 is on Saturday this year
	holidays = [	'2021-01-01',
			'2021-01-18',
			'2021-02-15',
			'2021-04-02',
			'2021-05-31',
			'2021-07-05',
			'2021-09-06',
			'2021-11-25',
			'2021-11-26',
			'2021-12-24' ]

	if ( est_time.strftime('%Y-%m-%d') ) in holidays:
		return False

	if ( int(est_time.strftime('%w')) != 0 and int(est_time.strftime('%w')) != 6 ): # 0=Sunday, 6=Saturday
		if ( int(est_time.strftime('%-H')) >= 9 ):
			if ( int(est_time.strftime('%-H')) == 9 ):
				if ( int(est_time.strftime('%-M')) < 30 ):
					return False
				else:
					return True
			else:
				if ( int(est_time.strftime('%-H')) <= 15 and int(est_time.strftime('%-M')) <= 59 ):
					return True

	return False


# Write logs for each ticker for live monitoring of the stock performance
def log_monitor(ticker=None, percent_change=-1, last_price=-1, net_change=-1, base_price=-1, orig_base_price=-1, stock_qty=-1, sold=False, short=False, proc_id=None, debug=0):
	if ( ticker == None ):
		print('Error: log_monitor(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	if ( proc_id == None ):
		try:
			proc_id = process_id
		except NameError:
			proc_id = '0000'

	logfile = './LOGS/' + str(ticker) + '-' + str(proc_id) + '.txt'
	try:
		fh = open( logfile, "wt" )

	except OSError as e:
		print('Error: log_monitor(): Unable to open file ' + str(logfile) + ': ' + e, file=sys.stderr)
		return False

	# Log format - stock:%change:last_price:net_change:base_price:orig_base_price
	if ( float(last_price) < float(base_price) ):
		percent_change = '-' + str(round(percent_change,2))
	else:
		percent_change = '+' + str(round(percent_change,2))

	red = '\033[0;31m'
	green = '\033[0;32m'
	reset_color = '\033[0m'
	text_color = green

	if ( (net_change < 0 and short == False) or (net_change > 0 and short == True) ):
		text_color = red
	net_change = text_color + str(net_change) + reset_color

	msg =	str(ticker)				+ ':' + \
		str(percent_change)			+ ':' + \
		str(round(float(last_price), 3))	+ ':' + \
		str(net_change)				+ ':' + \
		str(round(float(base_price), 3))	+ ':' + \
		str(round(float(orig_base_price), 3))	+ ':' + \
		str(stock_qty)				+ ':' + \
		str(sold)				+ ':' + \
		str(short)

	fcntl.lockf( fh, fcntl.LOCK_EX )
	print( msg, file=fh, flush=True )
	fcntl.lockf( fh, fcntl.LOCK_UN )

	fh.close()

	return True


# Fix up stock symbol if needed
def fix_stock_symbol(stock=None):
	if ( stock == None ):
		return None

	# Some NYSE stock symbols come through as XXpX (preferred shares)
	#  TDA API will not resolve these as-is, so swap the 'p' for a '-'
	if ( re.search(r'p', stock) != None ):
		stock = re.sub( r'p', r'-', stock )

	return str(stock).upper()


# Check that we can query using a stock symbol
def check_stock_symbol(stock=None):
	if ( stock == None ):
		print('Error: check_stock_symbol(' + str(stock) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		last_price = get_lastprice(stock, WarnDelayed=False)

	except Exception as e:
		print('Caught Exception: get_lastprice(' + str(ticker) + '): ' + str(e))
		return False

	if ( last_price == False ):
		# Ticker may be invalid
		return False

	return True


# Write a stock blacklist that can be used to avoid wash sales
def write_blacklist(ticker=None, stock_qty=-1, orig_base_price=-1, last_price=-1, net_change=-1, percent_change=-1, debug=1):
	if ( ticker == None ):
		print('Error: write_blacklist(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	blacklist = '.stock-blacklist'
	try:
		fh = open( blacklist, "wt" )

	except OSError as e:
		print('Error: write_blacklist(): Unable to open file ' + str(blacklist) + ': ' + e, file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	time_now = round( datetime.now(mytimezone).timestamp() )

	# Log format - stock|stock_qty|orig_base_price|last_price|net_change|percent_change|timestamp
	if ( float(last_price) < float(orig_base_price) ):
		percent_change = '-' + str(round(percent_change,2))
	else:
		percent_change = '+' + str(round(percent_change,2))

	msg =	str(ticker)		+ '|' + \
		str(stock_qty)		+ '|' + \
		str(orig_base_price)	+ '|' + \
		str(last_price)		+ '|' + \
		str(net_change)		+ '|' + \
		str(percent_change)	+ '|' + \
		str(time_now)

	fcntl.lockf( fh, fcntl.LOCK_EX )
	print( msg, file=fh, flush=True )
	fcntl.lockf( fh, fcntl.LOCK_UN )

	fh.close()

	return True


# Check stock blacklist to avoid wash sales
# Returns True if ticker is in the file and time_stamp is < 30 days ago
def check_blacklist(ticker=None, debug=1):
	if ( ticker == None ):
		print('Error: check_blacklist(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	found = False

	blacklist = '.stock-blacklist'
	try:
		fh = open( blacklist, "rt" )
	except OSError as e:
		print('Error: check_blacklist(): Unable to open file ' + str(blacklist) + ': ' + e, file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	time_now = datetime.now(mytimezone)
	for line in fh:
		if ( re.match(r'[\s\t]*#', line) ):
			continue

		line = line.replace(" ", "")
		line = line.rstrip()

		try:
			stock, stock_qty, orig_base_price, last_price, net_change, percent_change, time_stamp = line.split('|', 7)
		except:
			continue

		if ( str(stock) == str(ticker) ):
			time_stamp = datetime.fromtimestamp(float(time_stamp), tz=mytimezone)
			if ( time_stamp + timedelta(days=31) > time_now ):
				# time_stamp is less than 30 days in the past
				found = True
				break

			# Note that we keep processing the file as it could contain duplicate
			#  entries for each ticker, since we're only appending to this file
			#  and not re-writing it.

	fh.close()

	return found


# Get the lastPrice for a stock ticker
# Notes:
#  - Global object "tda" needs to exist, and tdalogin() should be called first.
#  - Returns lastPrice, which is the last price *including* extended hours.
#    If we want the latest market price we should look at regularMarketLastPrice.
def get_lastprice(ticker=None, WarnDelayed=True, debug=False):

	if ( ticker == None ):
		print('Error: get_lastprice(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		#data,err = tda.stocks.get_quote(ticker, True)
		data,err = func_timeout(10, tda.stocks.get_quote, args=(ticker, True))

	except FunctionTimedOut:
		print('Caught Exception: get_lastprice(' + str(ticker) + '): tda.stocks.get_quote(): timed out after 10 seconds')
		return False

	except Exception as e:
		print('Caught Exception: get_lastprice(' + str(ticker) + '): tda.stocks.get_quote(): ' + str(e))
		return False

	if ( err != None ):
		print('Error: get_lastprice(' + str(ticker) + '): ' + str(err), file=sys.stderr)
		return False
	elif ( data == {} ):
		print('Error: get_lastprice(' + str(ticker) + '): Empty data set', file=sys.stderr)
		return False

	if ( WarnDelayed == True and data[ticker]['delayed'] == 'true' ):
		print('Warning: get_lastprice(' + str(ticker) + '): quote data delayed')

	if ( debug == True ):
		print(data)

	# Note: return regularMarketLastPrice if we don't want extended hours pricing
	return float(data[ticker]['lastPrice'])


# Return a list with the price history of a given stock
# Useful for calculating various indicators such as RSI
def get_pricehistory(ticker=None, p_type=None, f_type=None, freq=None, period=None, start_date=None, end_date=None, needExtendedHoursData=False, debug=False):

	if ( ticker == None ):
		print('Error: get_pricehistory(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False, []

	# TDA API is picky, validate start/end dates
	if ( start_date != None and end_date != None):
		try:
			mytimezone
		except:
			mytimezone = timezone("US/Eastern")

		start = int( datetime.fromtimestamp(start_date/1000, tz=mytimezone).strftime('%w') )
		end = int( datetime.fromtimestamp(end_date/1000, tz=mytimezone).strftime('%w') )

		# 0=Sunday, 6=Saturday
		if ( start == 0 or start == 6 or end == 0 or end == 6 ):
			print('Error: get_pricehistory(' + str(ticker) + '): start_date or end_date is out of market open and extended hours (weekend)')
			return False, []

	# Example: {'open': 236.25, 'high': 236.25, 'low': 236.25, 'close': 236.25, 'volume': 500, 'datetime': 1616796960000}
	try:
		data = err = ''
		#data,err = tda.get_price_history(ticker, p_type, f_type, freq, period, start_date=start_date, end_date=end_date, needExtendedHoursData=needExtendedHoursData, jsonify=True)
		data,err = func_timeout(10, tda.get_price_history, args=(ticker, p_type, f_type, freq, period, start_date, end_date, needExtendedHoursData, True))

	except FunctionTimedOut:
		print('Caught Exception: get_pricehistory(' + str(ticker) + '): tda.get_price_history() timed out after 10 seconds')
		return False, []

	except Exception as e:
		print('Caught Exception: get_pricehistory(' + str(ticker) + '): ' + str(e))
		return False, []

	if ( err != None ):
		print('Error: get_price_history(' + str(ticker) + ', ' + str(p_type) + ', ' +
			str(f_type) + ', ' + str(freq) + ', ' + str(period) + ', ' +
			str(start_date) + ', ' + str(end_date) +'): ' + str(err), file=sys.stderr)

		return False, []

	# Populate epochs[] and check for duplicate timestamps
	epochs = []
	seen = {}
	dup = {}
	for idx,key in enumerate(data['candles']):
		epochs.append(float(key['datetime']))

		if key['datetime'] not in seen:
			seen[key['datetime']] = 1
		else:
			dup[key['datetime']] += 1

	if ( len( dup.items() ) > 0 ):
		print("\nWARNING: get_pricehistory(" + str(ticker) + "(: DUPLICATE TIMESTAMPS DETECTED\n", file=sys.stderr)

	return data, epochs


# Calculate the high, low and average stock price based on hourly data
def get_price_stats_hourly(ticker=None, days=10, debug=False):

	if ( ticker == None ):
		print('Error: get_price_stats(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False, 0, 0

	if ( int(days) > 10 ):
		days = 10 # TDA API only allows 10-days of 1-minute data

	try:
		data, epochs = get_pricehistory(ticker, 'day', 'minute', '1', days, needExtendedHoursData=True, debug=False)

	except Exception as e:
		print('Caught Exception: get_price_stats(' + str(ticker) + '): ' + str(e))

	if ( data == False ):
		print('Error: get_price_stats(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False, 0, 0

	high = avg = 0
	low = 999999
	for key in data['candles']:
		avg += float(key['close'])
		if ( float(key['close']) > high ):
			high = float(key['close'])
		if ( float(key['close']) < low ):
			low = float(key['close'])

	avg = round(avg / int(len(data['candles'])), 4)

	# Return the high, low and average stock price
	return high, low, avg


# Calculate the high, low and average stock price
def get_price_stats(ticker=None, days=100, debug=False):

	if ( ticker == None ):
		print('Error: get_price_stats(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False, 0, 0

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	end_date = datetime.now( mytimezone )
	start_date = end_date - timedelta( days=days )

	# Make sure start and end dates don't land on a weekend
	# 0=Sunday, 6=Saturday
	start = int( start_date.strftime('%w') )
	end = int( end_date.strftime('%w') )
	if ( start == 0 ):
		start_date = start_date + timedelta( days=1 )
	elif ( start == 6 ):
		start_date = start_date + timedelta( days=2 )
	if ( end == 0 ):
		end_date = end_date + timedelta( days=1 )
	elif ( end == 6 ):
		end_date = end_date + timedelta( days=2 )

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		data, epochs = get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

	except Exception as e:
		print('Caught Exception: get_price_stats(' + str(ticker) + '): ' + str(e))

	if ( data == False ):
		print('Error: get_price_stats(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False, 0, 0

	high = avg = 0
	low = 999999
	for key in data['candles']:
		avg += float(key['close'])
		if ( float(key['close']) > high ):
			high = float(key['close'])
		if ( float(key['close']) < low ):
			low = float(key['close'])

	avg = float( round(avg / int(len(data['candles'])), 4) )

	# Return the high, low and average stock price
	return high, low, avg


# Return the N-day simple moving average (SMA) (default: 200-day)
def get_sma(ticker=None, period=200, debug=False):

	days = 730	# Number of days to request from API. This needs to be larger
			#  than period because we're subtracting days from start_date,
			#  which will include weekends/holidays.

	if ( ticker == None ):
		print('Error: get_sma(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	end_date = datetime.now( mytimezone )
	start_date = end_date - timedelta( days=days )

	# Make sure start and end dates don't land on a weekend
	# 0=Sunday, 6=Saturday
	start = int( start_date.strftime('%w') )
	end = int( end_date.strftime('%w') )
	if ( start == 0 ):
		start_date = start_date + timedelta( days=1 )
	elif ( start == 6 ):
		start_date = start_date + timedelta( days=2 )
	if ( end == 0 ):
		end_date = end_date + timedelta( days=1 )
	elif ( end == 6 ):
		end_date = end_date + timedelta( days=2 )

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		pricehistory, epochs = get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

	except Exception as e:
		print('Caught Exception: get_sma(' + str(ticker) + '): ' + str(e))

	if ( pricehistory == False ):
		print('Error: get_sma(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print('Error: get_sma(' + str(ticker) + '): len(pricehistory) is less than period (' + str(len(pricehistory['candles'])) + ')')

	# Put pricehistory data into a numpy array
	prices = []
	for key in pricehistory['candles']:
		prices.append( float(key['close']) )

	prices = np.array( prices )

	# Get the N-day SMA
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

	return tuple(sma), pricehistory


# Return the N-day simple moving average (eMA) (default: 50-day)
def get_ema(ticker=None, period=50, debug=False):

	days = 365	# Number of days to request from API. This needs to be larger
			#  than period because we're subtracting days from start_date,
			#  which will include weekends/holidays.

	if ( ticker == None ):
		print('Error: get_ema(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	end_date = datetime.now( mytimezone )
	start_date = end_date - timedelta( days=days )

	# Make sure start and end dates don't land on a weekend
	# 0=Sunday, 6=Saturday
	start = int( start_date.strftime('%w') )
	end = int( end_date.strftime('%w') )
	if ( start == 0 ):
		start_date = start_date + timedelta( days=1 )
	elif ( start == 6 ):
		start_date = start_date + timedelta( days=2 )
	if ( end == 0 ):
		end_date = end_date + timedelta( days=1 )
	elif ( end == 6 ):
		end_date = end_date + timedelta( days=2 )

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		pricehistory, epochs = get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

	except Exception as e:
		print('Caught Exception: get_ema(' + str(ticker) + '): ' + str(e))

	if ( pricehistory == False ):
		print('Error: get_ema(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False

	if ( len(pricehistory['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print('Error: get_ema(' + str(ticker) + '): len(pricehistory) is less than period (' + str(len(pricehistory['candles'])) + ')')

	# Put pricehistory data into a numpy array
	prices = []
	for key in pricehistory['candles']:
		prices.append( float(key['close']) )

	prices = np.array( prices )

	# Get the N-day EMA
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

	return tuple(ema), pricehistory


# Purchase a stock at Market price
#  Ticker = stock ticker
#  Quantity = amount of stock to purchase
#  fillwait = (boolean) wait for order to be filled before returning
#
# Notes:
#  - Global object "tda" needs to exist, and tdalogin() should be called first.
def buy_stock_marketprice(ticker=None, quantity=None, fillwait=True, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	ticker = str(ticker).upper()
	num_attempts = 3 # Number of attempts to buy the stock in case of failure

	order = {
		"orderType": "MARKET",
		"session": "NORMAL",
		"duration": "DAY",
		"orderStrategyType": "SINGLE",
		"orderLegCollection": [ {
			"instruction": "BUY",
			"quantity": quantity,
			"instrument": {
				"symbol": ticker,
				"assetType": "EQUITY"
			}
		} ]
	}

	# Try to buy the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = tda.place_order(tda_account_number, order, True)
			if ( debug == 1 ):
				print('DEBUG: buy_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except Exception as e:
			print('Caught Exception: buy_stock_marketprice(' + str(ticker) + '): tda.place_order(): ' + str(e))
			return False

		if ( err != None ):
			print('Error: buy_stock_marketprice(' + str(ticker) + '): tda.place_order(): attempt ' + str(attempt+1) + ', ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: buy_stock_marketprice(): tdalogin(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = tda.get_order_number(data)
		if ( debug == 1 ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: buy_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: buy_stock_marketprice('+ str(ticker) + '): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = tda.get_order(tda_account_number, order_id, True)
		if ( debug == 1 ):
			print(data)

	except Exception as e:
		print('Caught Exception: buy_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: buy_stock_marketprice(' + str(ticker) + '): ' + str(err), file=sys.stderr)
		return False

	print('buy_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(10):
			try:
				data,err = tda.get_order(tda_account_number, order_id, True)
				if ( debug == True ):
					print(data)

			except Exception as e:
				print('Caught Exception: buy_stock_marketprice(' + str(ticker) + '): tda.get_order() in fillwait loop: ' + str(e))

			if ( err != None ):
				print('Error: buy_stock_marketprice(' + str(ticker) + '): problem in fillwait loop: ' + str(err), file=sys.stderr)
				continue

			if ( data['filledQuantity'] == quantity ):
				break

		print('buy_stock_marketprice(' + str(ticker) + '): Order completed (Order ID:' + str(order_id) + ')')

	return data


# Sell a stock at Market price
#  Ticker = stock ticker
#  Quantity = amount of stock to purchase
#  fillwait = (boolean) wait for order to be filled before returning
# Notes:
#  - Global object "tda" needs to exist, and tdalogin() should be called first.
def sell_stock_marketprice(ticker=None, quantity=-1, fillwait=True, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	ticker = str(ticker).upper()
	num_attempts = 3 # Number of attempts to sell the stock in case of failure

	order = {
		"orderType": "MARKET",
		"session": "NORMAL",
		"duration": "DAY",
		"orderStrategyType": "SINGLE",
		"orderLegCollection": [ {
			"instruction": "SELL",
			"quantity": quantity,
			"instrument": {
				"symbol": ticker,
				"assetType": "EQUITY"
			}
		} ]
	}


	# Try to sell the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = tda.place_order(tda_account_number, order, True)
			if ( debug == 1 ):
				print('DEBUG: sell_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except Exception as e:
			print('Caught Exception: sell_stock_marketprice(' + str(ticker) + '): tda.place_order(): ' + str(e))
			return False

		if ( err != None ):
			print('Error: sell_stock_marketprice(' + str(ticker) + '): tda.place_order(): attempt ' + str(attempt+1) + ',  ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: sell_stock_marketprice(): tdalogin(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = tda.get_order_number(data)
		if ( debug == 1 ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: sell_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: sell_stock_marketprice('+ str(ticker) + '): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = tda.get_order(tda_account_number, order_id, True)
		if ( debug == 1 ):
			print(data)

	except Exception as e:
		print('Caught Exception: sell_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: sell_stock_marketprice(' + str(ticker) + '): ' + str(err), file=sys.stderr)
		return False

	print('sell_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(10):
			try:
				data,err = tda.get_order(tda_account_number, order_id, True)
				if ( debug == True ):
					print(data)

			except Exception as e:
				print('Caught Exception: sell_stock_marketprice(' + str(ticker) + '): tda.get_order() in fillwait loop: ' + str(e))

			if ( err != None ):
				print('Error: sell_stock_marketprice(' + str(ticker) + '): problem in fillwait loop: ' + str(err), file=sys.stderr)
				continue

			if ( data['filledQuantity'] == quantity ):
				break

		print('sell_stock_marketprice(' + str(ticker) + '): Order completed (Order ID:' + str(order_id) + ')')

	return data


# Short sell a stock
#  Ticker = stock ticker
#  Quantity = amount of stock to sell short
#  fillwait = (boolean) wait for order to be filled before returning
def short_stock_marketprice(ticker=None, quantity=None, fillwait=True, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	ticker = str(ticker).upper()
	num_attempts = 3 # Number of attempts to buy the stock in case of failure
	order = {
		"orderType": "MARKET",
		"session": "NORMAL",
		"duration": "DAY",
		"orderStrategyType": "SINGLE",
		"orderLegCollection": [ {
			"instruction": "SELL_SHORT",
			"quantity": quantity,
			"instrument": {
				"symbol": ticker,
				"assetType": "EQUITY"
			}
		} ]
	}

	# Try to buy the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = tda.place_order(tda_account_number, order, True)
			if ( debug == 1 ):
				print('DEBUG: short_stock_marketprice(' + str(ticker) + '): tda.place_order(): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except Exception as e:
			print('Caught Exception: short_stock_marketprice(' + str(ticker) + ': tda.place_order(): ' + str(e))
			return False

		if ( err != None ):
			print('Error: short_stock_marketprice(' + str(ticker) + '): tda.place_order(): attempt ' + str(attempt+1) + ', ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: short_stock_marketprice(): tdalogin(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = tda.get_order_number(data)
		if ( debug == 1 ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: short_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = tda.get_order(tda_account_number, order_id, True)
		if ( debug == 1 ):
			print(data)

	except Exception as e:
		print('Caught Exception: short_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(err), file=sys.stderr)
		return False

	# Check if we were unable to short this stock
	if ( data['status'] == 'AWAITING_MANUAL_REVIEW' ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): tda.get_order(): returned status indicates that stock is not available for shorting', file=sys.stderr)
		return False

	print('short_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and float(data['filledQuantity']) != float(quantity) ):
		while time.sleep(10):
			try:
				data,err = tda.get_order(tda_account_number, order_id, True)
				if ( debug == True ):
					print(data)

			except Exception as e:
				print('Caught Exception: short_stock_marketprice(' + str(ticker) + '): tda.get_order() in fillwait loop: ' + str(e))

			if ( err != None ):
				print('Error: short_stock_marketprice(' + str(ticker) + '): tda.get_order() problem in fillwait loop: ' + str(err), file=sys.stderr)
				continue
			if ( float(data['filledQuantity']) == float(quantity) ):
				break

		print('short_stock_marketprice(' + str(ticker) + '): Order completed (Order ID:' + str(order_id) + ')')

	return data


# Buy to cover (market) a stock we previously sold short
#  Ticker = stock ticker
#  Quantity = amount of stock to buy-to-cover
#  fillwait = (boolean) wait for order to be filled before returning
def buytocover_stock_marketprice(ticker=None, quantity=-1, fillwait=True, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	ticker = str(ticker).upper()
	num_attempts = 3 # Number of attempts to sell the stock in case of failure

	order = {
		"orderType": "MARKET",
		"session": "NORMAL",
		"duration": "DAY",
		"orderStrategyType": "SINGLE",
		"orderLegCollection": [ {
			"instruction": "BUY_TO_COVER",
			"quantity": quantity,
			"instrument": {
				"symbol": ticker,
				"assetType": "EQUITY"
			}
		} ]
	}

	# Try to sell the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = tda.place_order(tda_account_number, order, True)
			if ( debug == 1 ):
				print('DEBUG: buytocover_stock_marketprice(' + str(ticker) + '): tda.place_order(): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except Exception as e:
			print('Caught Exception: buytocover_stock_marketprice(' + str(ticker) + '): tda.place_order(): ' + str(e))
			return False

		if ( err != None ):
			print('Error: buytocover_stock_marketprice(' + str(ticker) + '): tda.place_order(): attempt ' + str(attempt+1) + ',  ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: buytocover_stock_marketprice(): tdalogin(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = tda.get_order_number(data)
		if ( debug == 1 ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: buytocover_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: buytocover_stock_marketprice('+ str(ticker) + '): tda.get_order_number(): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = tda.get_order(tda_account_number, order_id, True)
		if ( debug == 1 ):
			print(data)

	except Exception as e:
		print('Caught Exception: buytocover_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: buytocover_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(err), file=sys.stderr)
		return False

	print('buytocover_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(10):
			try:
				data,err = tda.get_order(tda_account_number, order_id, True)
				if ( debug == True ):
					print(data)

			except Exception as e:
				print('Caught Exception: buytocover_stock_marketprice(' + str(ticker) + '): tda.get_order() in fillwait loop: ' + str(e))

			if ( err != None ):
				print('Error: buytocover_stock_marketprice(' + str(ticker) + '): problem in fillwait loop: ' + str(err), file=sys.stderr)
				continue
			if ( data['filledQuantity'] == quantity ):
				break

		print('buytocover_stock_marketprice(' + str(ticker) + '): Order completed (Order ID:' + str(order_id) + ')')

	return data


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
	if ( pricehistory['symbol'] ):
		ticker = pricehistory['symbol']

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


# Return numpy array of Stochastic RSI values for a given price history.
# Reference: https://tulipindicators.org/stochrsi
# 'pricehistory' should be a data list obtained from get_pricehistory()
def get_stochrsi(pricehistory=None, rsi_period=14, stochrsi_period=128, type='close', rsi_d_period=3, rsi_k_period=14, slow_period=3, debug=False):

	if ( pricehistory == None ):
		print('Error: get_stochrsi(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False, [], []

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
		print('Error: get_stochrsi(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False, [], []

	if ( len(prices) < rsi_period * 2 ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_stochrsi(' + str(ticker) + '): len(pricehistory) is less than rsi_period - is this a new stock ticker?', file=sys.stderr)

	# ti.stochrsi
	try:
		np_prices = np.array( prices )
		stochrsi = ti.stochrsi( np_prices, period=rsi_period )

	except Exception as e:
		print( 'Caught Exception: get_stochrsi(' + str(ticker) + '): ti.stochrsi(): ' + str(e) + ', len(pricehistory)=' + str(len(pricehistory['candles'])) )
		return False, [], []

	# ti.rsi + ti.stoch
	# Use ti.stoch() to get k and d values
	#   K measures the strength of the current move relative to the range of the previous n-periods
	#   D is a simple moving average of the K
	try:
		rsi = get_rsi( pricehistory, rsi_period=stochrsi_period, type=type )
		k, d = ti.stoch( rsi, rsi, rsi, rsi_k_period, slow_period, rsi_d_period )

	except Exception as e:
		print( 'Caught Exception: get_stochrsi(' + str(ticker) + '): ti.stoch(): ' + str(e) + ', len(pricehistory)=' + str(len(pricehistory['candles'])) )
		return False, [], []

	return stochrsi, k, d


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
	if ( pricehistory['symbol'] ):
		ticker = pricehistory['symbol']

	if ( type == None ):
		high = low = close = []
		for key in pricehistory['candles']:
			high.append(float(key['high']))
			low.append(float(key['low']))
			close.append(float(key['close']))

	elif ( type == 'hlc3' ):
		high = low = close = []
		for key in pricehistory['candles']:
			close.append( (float(key['high']) + float(key['low']) + float(key['close'])) / 3 )
		high = low = close

	elif ( type == 'hlc4' ):
		high = low = close = []
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
def get_vwap(pricehistory=None, debug=False):

	if ( pricehistory == None ):
		return False

	prices = np.array([[1,1,1]])
	try:
		ticker = pricehistory['symbol']
		for key in pricehistory['candles']:
			price = ( float(key['high']) + float(key['low']) + float(key['close']) ) / 3
			prices = np.append( prices, [[float(key['datetime']), price, float(key['volume'])]], axis=0 )

	except Exception as e:
		print('Caught Exception: get_vwap(' + str(ticker) + '): ' + str(e))
		return False

	# Remove the first value used to initialize np array
	prices = np.delete(prices, 0, axis=0)

	columns = ['DateTime', 'AvgPrice', 'Volume']
	df = pd.DataFrame(data=prices, columns=columns)
	q = df.Volume.values
	p = df.AvgPrice.values

	# vwap = Cumulative(Typical Price x Volume) / Cumulative(Volume)
	vwap = df.assign(vwap=(p * q).cumsum() / q.cumsum())

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(vwap)

	return vwap


# Return an N-day analysis for a stock ticker using the RSI algorithm
# Returns a comma-delimited log of each sell/buy/short/buy-to-cover transaction
#   price, sell_price, net_change, bool(short), bool(success), vwap, rsi, stochrsi, purchase_time, sell_time = result.split(',', 10)
def rsi_analyze( pricehistory=None, ticker=None, rsi_period=14, stochrsi_period=14, rsi_type='close', rsi_slow=3, rsi_k_period=14, rsi_d_period=3, rsi_low_limit=30, rsi_high_limit=70,
		 stoploss=False, incr_percent_threshold=1, decr_percent_threshold=2, hold_overnight=False,
		 noshort=False, shortonly=False, no_use_resistance=False, debug=False ):

	if ( ticker == None or pricehistory == None ):
		print('Error: rsi_analyze(' + str(ticker) + '): Either pricehistory or ticker is empty', file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# Get RSI
	# With 10-day/1-min history there should be ~3900 datapoints in pricehistory['candles'] (6.5hrs * 60mins * 10days)
	# Therefore, with an rsi_period of 14, get_rsi() will return a list of 3886 items
	try:
		rsi = get_rsi(pricehistory, rsi_period, rsi_type, debug=False)

	except Exception as e:
		print('Caught Exception: rsi_analyze(' + str(ticker) + '): get_rsi(): ' + str(e))
		return False

	if ( isinstance(rsi, bool) and rsi == False ):
		print('Error: get_rsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
		return False

	if ( len(rsi) != len(pricehistory['candles']) - rsi_period ):
		print('Warning, unexpected length of rsi (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(rsi)=' + str(len(rsi)) + ')')


	# Get stochactic RSI
	try:
		stochrsi, rsi_k, rsi_d = get_stochrsi(pricehistory, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

	except:
		print('Caught Exception: rsi_analyze(' + str(ticker) + '): get_stochrsi(): ' + str(e))
		return False

	if ( isinstance(stochrsi, bool) and stochrsi == False ):
		print('Error: get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
		return False

	# If using the same 1-minute data, the len of stochrsi will be rsi_period * (rsi_period * 2) - 1
	if ( len(stochrsi) != len(pricehistory['candles']) - (rsi_period * 2 - 1) ):
		print('Warning, unexpected length of stochrsi (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(stochrsi)=' + str(len(stochrsi)) + ')')

	# Get the VWAP data
	try:
		vwap = get_vwap(pricehistory)

	except Exception as e:
		print('Caught Exception: rsi_analyze(' + str(ticker) + '): get_vwap(): ' + str(e))
		return False

	if ( isinstance(vwap, bool) and vwap == False ):
		print('Error: get_vwap(' + str(ticker) + ') returned false - no data', file=sys.stderr)
		return False
	if ( debug == True ):
		if ( len(vwap) != len(pricehistory['candles']) ):
			print('Warning, unexpected length of vwap (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(vwap)=' + str(len(vwap)) + ')')

	# Get general information about the stock that we can use later
	# I.e. volatility, resistance, etc.
	three_week_high = three_week_low = three_week_avg = -1
	twenty_week_high = twenty_week_low = twenty_week_avg = -1
	try:
		# 3-week high / low / average
		three_week_high, three_week_low, three_week_avg = get_price_stats(ticker, days=15)

	except Exception as e:
		print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

	time.sleep(0.5)
	try:
		# 20-week high / low / average
		twenty_week_high, twenty_week_low, twenty_week_avg = get_price_stats(ticker, days=100)

	except Exception as e:
		print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

	# SMA200 and EMA50
	# Determine if the stock is bearish or bullish based on SMA/EMA
	sma, p_history = get_sma(ticker, 200, False)
	ema, p_history = get_ema(ticker, 50, False)

	isbull = False
	isbear = True
	if ( float(ema[-1]) > float(sma[-1]) ):
		isbull = True
		isbear = False
	del(p_history)


	# Run through the RSI values and log the results
	results = []
	prev_rsi = -1
	stochrsi_idx = len(rsi) - len(stochrsi) + 1	# Used to index stochrsi[] below
	c_counter = int(rsi_period) - 1 - 1		# Candle counter - because rsi[] is smaller than the full dataset,
							# this represents the index of pricehistory['candles'] when iterating through rsi[]
							# Note: the extra -1 is because of "c_counter += 1" right at the top of the loop

	buy_signal = False
	sell_signal = False
	short_signal = False
	buy_to_cover_signal = False

	signal_mode = 'buy'
	if ( shortonly == True ):
		signal_mode = 'short'

	# Main loop
	for idx,cur_rsi in enumerate(rsi):
		c_counter += 1

		if ( prev_rsi == -1 ):
			prev_rsi = cur_rsi

		# Fix stochrsi since it's shorter than the rsi array
		if ( idx <= stochrsi_idx - 1 ):
			# We can't reference stochrsi[idx] yet since
			#  there is no data for this time period
			srsi = -1
		else:
			srsi = float(stochrsi[idx-stochrsi_idx])

		# Ignore pre-post market since we cannot trade during those hours
		date = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone)
		if ( ismarketopen_US(date) != True ):
			continue


		# BUY mode
		if ( signal_mode == 'buy' ):
			short = False

			# If hold_overnight=False don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and isendofday(60, date) ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				prev_rsi = cur_rsi
				continue

			# Jump to short mode if StochRSI K and D are already above rsi_high_limit
			# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi > rsi_high_limit and noshort == False ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				signal_mode = 'short'
				continue

			# Monitor RSI
			if ( prev_rsi < rsi_low_limit and cur_rsi > prev_rsi ):
				if ( cur_rsi >= rsi_low_limit ):
					buy_signal = True

			# BUY SIGNAL
			if ( buy_signal == True ):
				purchase_price = float(pricehistory['candles'][c_counter]['close'])

				if ( no_use_resistance == False ):
					# Final sanity checks should go here
					if ( purchase_price >= twenty_week_high ):
						# This is not a good bet
						twenty_week_high = float(purchase_price)
						print('Stock ' + str(ticker) + ' buy signal indicated, but last price (' + str(purchase_price) + ') is already above the 20-week high (' + str(twenty_week_high) + ')')
						prev_rsi = cur_rsi
						buy_signal = False
						continue

					elif ( ( abs(float(purchase_price) / float(twenty_week_high) - 1) * 100 ) < 1.5 ):
						# Current high is within 1% of 20-week high, not a good bet
						print('Stock ' + str(ticker) + ' buy signal indicated, but last price (' + str(purchase_price) + ') is already within 1.5% of the 20-week high (' + str(twenty_week_high) + ')')
						prev_rsi = cur_rsi
						buy_signal = False
						continue

				base_price = purchase_price

				purchase_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(purchase_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(prev_rsi)+'/'+str(cur_rsi) + ',' + str(srsi) + ',' +
						str(purchase_time) )

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				signal_mode = 'sell'


		# SELL mode
		if ( signal_mode == 'sell' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and isendofday(5, date) ):
				sell_signal = True

			# Monitor cost basis
			if ( stoploss == True ):
				last_price = float(pricehistory['candles'][c_counter]['close'])

				percent_change = 0
				if ( float(last_price) < float(base_price) ):
					percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

					# SELL the security if we are using a trailing stoploss
					if ( percent_change >= decr_percent_threshold ):

						# Sell
						sell_price = float(pricehistory['candles'][c_counter]['close'])
						sell_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

						# sell_price,bool(short),vwap,rsi,stochrsi,sell_time
						results.append( str(sell_price) + ',' + str(short) + ',' +
								str(vwap.loc[c_counter,'vwap']) + ',' + str(prev_rsi)+'/'+str(cur_rsi) + ',' + str(srsi) + ',' +
								str(sell_time) )

						prev_rsi = cur_rsi = -1
						signal_mode = 'buy'
						continue

				elif ( float(last_price) > float(base_price) ):
					percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

					if ( percent_change >= incr_percent_threshold ):
						base_price = last_price

			# End stoploss monitor

			# Monitor RSI
			if ( prev_rsi > rsi_high_limit and cur_rsi < prev_rsi ):
				if ( cur_rsi <= rsi_high_limit ):
					sell_signal = True

			if ( sell_signal == True ):

				# SELL SIGNAL
				sell_price = float(pricehistory['candles'][c_counter]['close'])
				sell_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				# sell_price,bool(short),vwap,rsi,stochrsi,sell_time
				results.append( str(sell_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(prev_rsi)+'/'+str(cur_rsi) + ',' + str(srsi) + ',' +
						str(sell_time) )

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False

				if ( noshort == False ):
					short_signal = True
					signal_mode = 'short'
					continue
				else:
					signal_mode = 'buy'


		# SELL SHORT mode
		if ( signal_mode == 'short' ):
			short = True

			# If hold_overnight=False don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and isendofday(60, date) ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				prev_rsi = cur_rsi
				continue

			# Jump to buy mode if RSI is already below rsi_low_limit
			if ( cur_rsi < rsi_low_limit  ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				signal_mode = 'buy'
				continue

			# Monitor RSI
			if ( prev_rsi > rsi_high_limit and cur_rsi < prev_rsi ):
				if ( cur_rsi <= rsi_high_limit ):
					short_signal = True

			# SHORT SIGNAL
			if ( short_signal == True ):
				short_price = float(pricehistory['candles'][c_counter]['close'])
				if ( no_use_resistance == False ):

					# Final sanity checks should go here
					if ( float(short_price) <= float(twenty_week_low) ):
						# This is not a good bet
						twenty_week_low = float(short_price)
						print('Stock ' + str(ticker) + ' short signal indicated, but last price (' + str(short_price) + ') is already below the 20-week low (' + str(twenty_week_low) + ')')
						short_signal = False
						prev_rsi = cur_rsi
						continue

					elif ( ( abs(float(twenty_week_low) / float(short_price) - 1) * 100 ) < 1.5 ):
						# Current low is within 1.5% of 20-week low, not a good bet
						print('Stock ' + str(ticker) + ' short signal indicated, but last price (' + str(short_price) + ') is already within 1.5% of the 20-week low (' + str(twenty_week_low) + ')')
						short_signal = False
						prev_rsi = cur_rsi
						continue

				base_price = short_price
				short_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(short_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(prev_rsi)+'/'+str(cur_rsi) + ',' + str(srsi) + ',' +
						str(short_time) )

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				signal_mode = 'buy_to_cover'


		# BUY-TO-COVER mode
		if ( signal_mode == 'buy_to_cover' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and isendofday(5, date) ):
				buy_to_cover_signal = True

			# Monitor cost basis
			if ( stoploss == True ):
				last_price = float(pricehistory['candles'][c_counter]['close'])

				percent_change = 0
				if ( float(last_price) < float(base_price) ):
					percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

					if ( percent_change >= incr_percent_threshold ):
						base_price = last_price

				elif ( float(last_price) > float(base_price) ):
					percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

					# Buy-to-cover the security if we are using a trailing stoploss
					if ( percent_change >= decr_percent_threshold ):

						# Buy-to-cover
						buy_to_cover_price = float(pricehistory['candles'][c_counter]['close'])
						buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

						results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
								str(vwap.loc[c_counter,'vwap']) + ',' + str(prev_rsi)+'/'+str(cur_rsi) + ',' + str(srsi) + ',' +
								str(buy_to_cover_time) )

						prev_rsi = cur_rsi = -1

						if ( shortonly == True ):
							signal_mode = 'short'
						else:
							signal_mode = 'buy'

			# End stoploss monitor

			# Monitor RSI
			if ( prev_rsi < rsi_low_limit and cur_rsi > prev_rsi ):
				if ( cur_rsi >= rsi_low_limit ):
					buy_to_cover_signal = True

			if ( buy_to_cover_signal == True ):

				# BUY-TO-COVER SIGNAL
				buy_to_cover_price = float(pricehistory['candles'][c_counter]['close'])
				buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(prev_rsi)+'/'+str(cur_rsi) + ',' + str(srsi) + ',' +
						str(buy_to_cover_time) )

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				if ( shortonly == True ):
					signal_mode = 'short'
				else:
					buy_signal = True
					signal_mode = 'buy'
					continue

		prev_rsi = cur_rsi

	return results


# Return an N-day analysis for a stock ticker using the Stochastic RSI algorithm
#
# For this analysis, instead of monitoring just the RSI value we monitor the stochastics for RSI:
#   K measures the strength of the current move relative to the range of the previous n-periods
#   D is a simple moving average of the K
#
# nocrossover = True
#   Changes the algorithm so that k and d crossovers will not generate a signal
# crossover_only = True
#   Modifies the algorithm so that only k and d crossovers will generate a signal
#
# Returns a comma-delimited log of each sell/buy/short/buy-to-cover transaction
#   price, sell_price, net_change, bool(short), bool(success), vwap, rsi, stochrsi, purchase_time, sell_time = result.split(',', 10)
def stochrsi_analyze( pricehistory=None, ticker=None, rsi_period=14, stochrsi_period=14, rsi_type='close', rsi_slow=3, rsi_low_limit=20, rsi_high_limit=80, rsi_k_period=14, rsi_d_period=3,
			stoploss=False, incr_percent_threshold=1, decr_percent_threshold=2, nocrossover=False, crossover_only=False, hold_overnight=False,
			noshort=False, shortonly=False, no_use_resistance=False, debug=False ):

	if ( ticker == None or pricehistory == None ):
		print('Error: stochrsi_analyze(' + str(ticker) + '): Either pricehistory or ticker is empty', file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# Get RSI
	# With 10-day/1-min history there should be ~3900 datapoints in data['candles'] (6.5hrs * 60mins * 10days)
	# Therefore, with an rsi_period of 14, get_rsi() will return a list of 3886 items
	try:
		rsi = get_rsi(pricehistory, rsi_period, rsi_type, debug=False)

	except Exception as e:
		print('Caught Exception: rsi_analyze(' + str(ticker) + '): get_rsi(): ' + str(e))
		return False

	if ( isinstance(rsi, bool) and rsi == False ):
		print('Error: get_rsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
		return False

	if ( len(rsi) != len(pricehistory['candles']) - rsi_period ):
		print('Warning, unexpected length of rsi (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(rsi)=' + str(len(rsi)) + ')')

	# Get stochastic RSI
	try:
		stochrsi, rsi_k, rsi_d = get_stochrsi(pricehistory, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

	except:
		print('Caught Exception: rsi_analyze(' + str(ticker) + '): get_stochrsi(): ' + str(e))
		return False

	if ( isinstance(stochrsi, bool) and stochrsi == False ):
		print('Error: get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
		return False

	# If using the same 1-minute data, the len of stochrsi will be (stochrsi_period * 2 - 1)
	# len(rsi_k) should be (stochrsi_period * 2 - rsi_d_period)
	if ( len(stochrsi) != len(pricehistory['candles']) - (rsi_period * 2 - 1) ):
		print( 'Warning, unexpected length of stochrsi (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(stochrsi)=' + str(len(stochrsi)) + ')' )

	if ( len(rsi_k) != len(pricehistory['candles']) - stochrsi_period * 2 - rsi_d_period ):
		print( 'Warning, unexpected length of rsi_k (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(rsi_k)=' + str(len(rsi_k)) + ')' )
	if ( len(rsi_k) != len(rsi_d) ):
		print( 'Warning, unexpected length of rsi_k (pricehistory[candles]=' + str(len(pricehistory['candles'])) +
			', len(rsi_k)=' + str(len(stochrsi)) + '), len(rsi_d)=' + str(len(rsi_d)) + ')' )

	# Get the VWAP data
	try:
		vwap = get_vwap(pricehistory)

	except Exception as e:
		print('Caught Exception: rsi_analyze(' + str(ticker) + '): get_vwap(): ' + str(e))
		return False

	if ( isinstance(vwap, bool) and vwap == False ):
		print('Error: get_vwap(' + str(ticker) + ') returned false - no data', file=sys.stderr)
		return False
	if ( debug == True ):
		if ( len(vwap) != len(pricehistory['candles']) ):
			print('Warning, unexpected length of vwap (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(vwap)=' + str(len(vwap)) + ')')


	# Get general information about the stock that we can use later
	# I.e. volatility, resistance, etc.
	three_week_high = three_week_low = three_week_avg = -1
	twenty_week_high = twenty_week_low = twenty_week_avg = -1
	try:
		# 3-week high / low / average
		three_week_high, three_week_low, three_week_avg = get_price_stats(ticker, days=15)

	except Exception as e:
		print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

	time.sleep(0.5)
	try:
		# 20-week high / low / average
		twenty_week_high, twenty_week_low, twenty_week_avg = get_price_stats(ticker, days=100)

	except Exception as e:
		print('Warning: get_price_stats(' + str(ticker) + '): ' + str(e))

	# SMA200 and EMA50
	# Determine if the stock is bearish or bullish based on SMA/EMA
	sma, p_history = get_sma(ticker, 200, False)
	ema, p_history = get_ema(ticker, 50, False)

	isbull = False
	isbear = True
	if ( float(ema[-1]) > float(sma[-1]) ):
		isbull = True
		isbear = False
	del(p_history)


	# Run through the RSI values and log the results
	results = []
	prev_rsi_k = 0
	stochrsi_idx = len(stochrsi) - len(rsi_k) - 1	# Used to index stochrsi[] below
	c_counter = int(stochrsi_period)*2 + 1 - 1	# Candle counter - because rsi[] is smaller than the full dataset,
							# this represents the index of pricehistory['candles'] when iterating through rsi[]
							# Note: the extra -1 is because of "c_counter += 1" right at the top of the loop
	buy_signal = False
	sell_signal = False
	short_signal = False
	buy_to_cover_signal = False

	orig_nocrossover = nocrossover

	signal_mode = 'buy'
	if ( shortonly == True ):
		signal_mode = 'short'

	# Main loop
	for idx,cur_rsi_k in enumerate(rsi_k):

		c_counter += 1
		cur_rsi_d = rsi_d[idx]
		prev_rsi_d = rsi_d[idx-1]

###########
#		# For the purposes of analyzing, we need to chop down pricehistory so that candle_analyze_reversal() only gets
#		#  the history up until the minute that we are currently analyzing. For live use we can just pass pricehistory as-is.
#		ph = {}
#		ph['candles'] = []
#		for i in range( 0, c_counter, 1 ):
#			ph['candles'].append( { 'open': pricehistory['candles'][i]['open'], 'high': pricehistory['candles'][i]['high'],
#						'low': pricehistory['candles'][i]['low'], 'close': pricehistory['candles'][i]['close'],
#						'volume': pricehistory['candles'][i]['volume'], 'datetime': pricehistory['candles'][i]['datetime']} )
#
#		ph['symbol'] = pricehistory['symbol']
#		ph['empty'] = pricehistory['empty']
#
#		ret = tda_cndl_helper.candle_analyze_reversal(ph, candle_pattern='bull', num_candles=10, debug=True)
#		if ( ret == True ):
#			print(ret)
#		ret = tda_cndl_helper.candle_analyze_reversal(ph, candle_pattern='bear', num_candles=10, debug=True)
#		if ( ret == True ):
#			print(ret)
###########


		# stochrsi[] is a bit larger than rsi_k that we are looping through
		srsi = float(stochrsi[idx+stochrsi_idx])

		# Ignore pre-post market since we cannot trade during those hours
		date = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone)
		if ( ismarketopen_US(date) != True ):
			continue


		# BUY mode
		if ( signal_mode == 'buy' ):
			short = False

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and isendofday(60, date) ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				prev_rsi_k = cur_rsi_k
				continue

			# Jump to short mode if StochRSI K and D are already above rsi_high_limit
			# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit and noshort == False ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				signal_mode = 'short'
				continue

			if ( (cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit) and nocrossover == False ):

				# Monitor if K and D intercect
				# A buy signal occurs when an increasing %K line crosses above the %D line in the oversold region.
				#  or if the %K line crosses below the rsi limit
				if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
					buy_signal = True

			elif ( (prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k) and crossover_only == False ):
				if ( cur_rsi_k >= rsi_low_limit ):
					buy_signal = True

			if ( buy_signal == True ):
				purchase_price = float(pricehistory['candles'][c_counter]['close'])
				if ( no_use_resistance == False ):

					# Final sanity checks should go here
					if ( purchase_price >= twenty_week_high ):
						# This is not a good bet
						twenty_week_high = float(purchase_price)
						print('Stock ' + str(ticker) + ' buy signal indicated, but last price (' + str(purchase_price) + ') is already above the 20-week high (' + str(twenty_week_high) + ')')
						prev_rsi_k = cur_rsi_k
						buy_signal = False
						continue

					elif ( ( abs(float(purchase_price) / float(twenty_week_high) - 1) * 100 ) < 1.5 ):
						# Current high is within 1.5% of 20-week high, not a good bet
						print('Stock ' + str(ticker) + ' buy signal indicated, but last price (' + str(purchase_price) + ') is already within 1.5% of the 20-week high (' + str(twenty_week_high) + ')')
						prev_rsi_k = cur_rsi_k
						buy_signal = False
						continue

				# BUY SIGNAL
				base_price = purchase_price
				purchase_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(purchase_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' + str(srsi) + ',' +
						str(purchase_time) )

				nocrossover = orig_nocrossover # Reset in case we stoplossed earlier

				sell_signal = buy_signal = False
				signal_mode = 'sell'


		# SELL mode
		if ( signal_mode == 'sell' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and isendofday(5, date) ):
				sell_signal = True

			# Monitor cost basis
			if ( stoploss == True ):
				last_price = float(pricehistory['candles'][c_counter]['close'])

				percent_change = 0
				if ( float(last_price) < float(base_price) ):
					percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

					# SELL the security if we are using a trailing stoploss
					if ( percent_change >= decr_percent_threshold ):

						# Sell
						sell_price = float(pricehistory['candles'][c_counter]['close'])
						sell_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

						# sell_price,bool(short),vwap,rsi,stochrsi,sell_time
						results.append( str(sell_price) + ',' + str(short) + ',' +
								str(vwap.loc[c_counter,'vwap']) + ',' + str(cur_rsi_k)+'/'+str(cur_rsi_d) + ',' + str(srsi) + ',' +
								str(sell_time) )

						buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
						prev_rsi_k = cur_rsi_k
						signal_mode = 'buy'

						nocrossover = True # Stock is dipping, disable crossover for this next cycle

						continue

				elif ( float(last_price) > float(base_price) ):
					percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

					if ( percent_change >= incr_percent_threshold ):
						base_price = last_price

			# End stoploss monitor

			# Monitor RSI
			if ( (cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit) and nocrossover == False ):

				# Monitor if K and D intercect
				# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region
				if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
					sell_signal = True

			elif ( (prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k) and crossover_only == False ):
				if ( cur_rsi_k <= rsi_high_limit ):
					sell_signal = True

			if ( sell_signal == True ):

				# Sell
				sell_price = float(pricehistory['candles'][c_counter]['close'])
				sell_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				# sell_price,bool(short),vwap,rsi,stochrsi,sell_time
				results.append( str(sell_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(cur_rsi_k)+'/'+str(cur_rsi_d) + ',' + str(srsi) + ',' +
						str(sell_time) )

				buy_signal = sell_signal = False

				if ( noshort == False ):
					short_signal = True
					signal_mode = 'short'
					continue
				else:
					signal_mode = 'buy'


		# SELL SHORT mode
		if ( signal_mode == 'short' ):
			short = True

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and isendofday(60, date) ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				prev_rsi_k = cur_rsi_k
				continue

			# Jump to buy mode if StochRSI K and D are already below rsi_low_limit
			if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				signal_mode = 'buy'
				continue

			if ( (cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit) and nocrossover == False ):

				# Monitor if K and D intercect
				# A sell-short signal occurs when a decreasing %K line crosses below the %D line in the overbought region
				if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
					short_signal = True

			elif ( (prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k) and crossover_only == False ):
				if ( cur_rsi_k <= rsi_high_limit ):
					short_signal = True

			if ( short_signal == True ):
				short_price = float(pricehistory['candles'][c_counter]['close'])
				if ( no_use_resistance == False ):

					# Final sanity checks should go here
					if ( float(short_price) <= float(twenty_week_low) ):
						# This is not a good bet
						twenty_week_low = float(short_price)
						print('Stock ' + str(ticker) + ' short signal indicated, but last price (' + str(short_price) + ') is already below the 20-week low (' + str(twenty_week_low) + ')')
						short_signal = False
						prev_rsi_k = cur_rsi_k
						continue

					elif ( ( abs(float(twenty_week_low) / float(short_price) - 1) * 100 ) < 1.5 ):
						# Current low is within 1.5% of 20-week low, not a good bet
						print('Stock ' + str(ticker) + ' short signal indicated, but last price (' + str(short_price) + ') is already within 1.5% of the 20-week low (' + str(twenty_week_low) + ')')
						short_signal = False
						prev_rsi_k = cur_rsi_k
						continue

				# Short
				base_price = short_price

				short_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
				results.append( str(short_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(cur_rsi_k)+'/'+str(cur_rsi_d) + ',' + str(srsi) + ',' +
						str(short_time) )

				nocrossover = orig_nocrossover # Reset in case we stoplossed earlier

				short_signal = buy_to_cover_signal = False
				signal_mode = 'buy_to_cover'


		# BUY-TO-COVER mode
		if ( signal_mode == 'buy_to_cover' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and isendofday(5, date) ):
				buy_to_cover_signal = True

			# Monitor cost basis
			if ( stoploss == True ):
				last_price = float(pricehistory['candles'][c_counter]['close'])

				percent_change = 0
				if ( float(last_price) > float(base_price) ):
					percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

					# Buy-to-cover the security if we are using a trailing stoploss
					if ( percent_change >= decr_percent_threshold ):

						# Buy-to-cover
						buy_to_cover_price = float(pricehistory['candles'][c_counter]['close'])
						buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

						results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
								str(vwap.loc[c_counter,'vwap']) + ',' + str(cur_rsi_k)+'/'+str(cur_rsi_d) + ',' + str(srsi) + ',' +
								str(buy_to_cover_time) )

						buy_signal = sell_signal = short_signal = buy_to_cover_signal = False

						nocrossover = True # Stock is rising, disable crossover for this next cycle

						if ( shortonly == True ):
							signal_mode = 'short'
						else:
							prev_rsi_k = cur_rsi_k
							signal_mode = 'buy'
							continue

				elif ( float(last_price) < float(base_price) ):
					percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

					if ( percent_change >= incr_percent_threshold ):
						base_price = last_price

			# End stoploss monitor

			# Monitor RSI
			if ( (cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit) and nocrossover == False ):

				# Monitor if K and D intercect
				# A buy-to-cover signal occurs when an increasing %K line crosses above the %D line in the oversold region.
				if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
					buy_to_cover_signal = True

			elif ( (prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k) and crossover_only == False):
				if ( cur_rsi_k >= rsi_low_limit ):
					buy_to_cover_signal = True

			if ( buy_to_cover_signal == True ):

				# Buy-to-cover
				buy_to_cover_price = float(pricehistory['candles'][c_counter]['close'])
				buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][c_counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
						str(vwap.loc[c_counter,'vwap']) + ',' + str(cur_rsi_k)+'/'+str(cur_rsi_d) + ',' + str(srsi) + ',' +
						str(buy_to_cover_time) )

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				if ( shortonly == True ):
					signal_mode = 'short'
				else:
					buy_signal = True
					signal_mode = 'buy'
					continue

		prev_rsi_k = cur_rsi_k

	# End main loop

	return results


