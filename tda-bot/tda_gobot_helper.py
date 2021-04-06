#!/usr/bin/python3 -u

import os, sys, fcntl
import time
import re
from datetime import datetime, timedelta
from pytz import timezone
import tulipy as ti
import numpy as np


# Login to tda using a passcode
def tdalogin(passcode=None):

	if ( passcode == None ):
		return False

	enc = tda.login(passcode)
	if ( enc == '' ):
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
def isendofday(mins=5):
	if ( mins < 0 or mins > 60 ):
		return False

	eastern = timezone('US/Eastern') # Observes EST and EDT
	est_time = datetime.now(eastern)

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
def ismarketopen_US():
	eastern = timezone('US/Eastern') # Observes EST and EDT
	est_time = datetime.now(eastern)

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
def log_monitor(ticker=None, percent_change=-1, last_price=-1, net_change=-1, base_price=-1, orig_base_price=-1, stock_qty=-1, sold=False, debug=0, proc_id=None):
	if ( ticker == None ):
		return False

	if ( proc_id == None ):
		try:
			process_id
		except NameError:
			proc_id = '0000'
		else:
			proc_id = process_id

	logfile = './LOGS/' + str(ticker) + '-' + str(proc_id) + '.txt'
	try:
		fh = open( logfile, "wt" )
	except OSError as e:
		if ( debug == 1 ):
			print('Error: log_monitor(): Unable to open file ' + str(logfile) + ', ' + e, file=sys.stderr)
		return False

	# Log format - stock:%change:last_price:net_change:base_price:orig_base_price
	if ( float(last_price) < float(base_price) ):
		percent_change = '-' + str(round(percent_change,2))
	else:
		percent_change = '+' + str(round(percent_change,2))

	if ( net_change < 0 ):
		net_change = '\033[0;31m' + str(net_change) + '\033[0m'
	else:
		net_change = '\033[0;32m' + str(net_change) + '\033[0m'

	msg =	str(ticker)				+ ':' + \
		str(percent_change)			+ ':' + \
		str(round(float(last_price), 3))	+ ':' + \
		str(net_change)				+ ':' + \
		str(round(float(base_price), 3))	+ ':' + \
		str(round(float(orig_base_price), 3))	+ ':' + \
		str(stock_qty)				+ ':' + \
		str(sold)

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
		return False

	last_price = get_lastprice(stock, WarnDelayed=False)
	if ( last_price == False ):
		# Ticker may be invalid
		return False

	return True


# Write a stock blacklist that can be used to avoid wash sales
def write_blacklist(ticker=None, stock_qty=-1, orig_base_price=-1, last_price=-1, net_change=-1, percent_change=-1, debug=1):
	if ( ticker == None ):
		return False

	blacklist = '.stock-blacklist'
	try:
		fh = open( blacklist, "wt" )
	except OSError as e:
		if ( debug == 1 ):
			print('Error: write_blacklist(): Unable to open file ' + str(blacklist) + ', ' + e, file=sys.stderr)
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
		return False

	found = False

	blacklist = '.stock-blacklist'
	try:
		fh = open( blacklist, "rt" )
	except OSError as e:
		if ( debug == 1 ):
			print('Error: check_blacklist(): Unable to open file ' + str(blacklist) + ', ' + e, file=sys.stderr)
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
			time_stamp = datetime.fromtimestamp(time_stamp, tz=mytimezone)
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
		return False

	data,err = tda.stocks.get_quote(ticker, True)
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
		return False, []

	# TDA API is picky, validate start/end dates
	if ( start_date != None and end_date != None):
		try:
			mytimezone
		except:
			mytimezone = timezone("US/Eastern")

		start = int( datetime.fromtimestamp(start_date/1000, tz=mytimezone).strftime('%w') )
		end = int( datetime.fromtimestamp(start_date/1000, tz=mytimezone).strftime('%w') )

		# 0=Sunday, 6=Saturday
		if ( start == 0 or start == 6 or end == 0 or end == 6 ):
			print('Error: get_pricehistory(): start_date or end_date is out of market open and extended hours (weekend)')
			return False, []

	# Example: {'open': 236.25, 'high': 236.25, 'low': 236.25, 'close': 236.25, 'volume': 500, 'datetime': 1616796960000}
	data,err = tda.get_price_history(ticker, p_type, f_type, freq, period, start_date=start_date, end_date=end_date, needExtendedHoursData=needExtendedHoursData, jsonify=True)
	if ( err != None ):
		print('Error: get_price_history(' + str(ticker) + ', ' + str(p_type) + ', ' +
			str(f_type) + ', ' + str(freq) + ', ' + str(period) + ', ' +
			str(start_date) + ', ' + str(end_date) +'): ' + str(err), file=sys.stderr)

		return False, []

	epochs = []
	for key in data['candles']:
		epochs.append(float(key['datetime']))

	return data, epochs


# Calculate the high, low and average stock price
def get_price_stats(ticker=None, days=10, debug=False):

	if ( ticker == None ):
		return False, 0, 0
	if ( int(days) > 10 ):
		days = 10 # TDA API only allows 10-days of 1-minute data

	data, epochs = get_pricehistory(ticker, 'day', 'minute', '1', days, needExtendedHoursData=True, debug=False)
	if ( data == False ):
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
		data, err = tda.place_order(tda_account_number, order, True)
		if ( debug == 1 ):
			print('DEBUG: buy_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
			print(order)
			print(data)
			print(err)

		if ( err != None ):
			print('Error: buy_stock_marketprice(' + str(ticker) + '): attempt ' + str(attempt+1) + ', ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: buy_stock_marketprice(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	order_id = tda.get_order_number(data)
	if ( debug == 1 ):
		print(order_id)
	if ( str(order_id) == '' ):
		print('Error: buy_stock_marketprice('+ str(ticker) + '): Unable to get order ID', file=sys.stderr)
		return False

	data,err = tda.get_order(tda_account_number, order_id, True)
	if ( debug == 1 ):
		print(data)
	if ( err != None ):
		print('Error: buy_stock_marketprice(' + str(ticker) + '): ' + str(err), file=sys.stderr)
		return False

	print('buy_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(10):
			data,err = tda.get_order(tda_account_number, order_id, True)
			if ( debug == True ):
				print(data)
			if ( err != None ):
				print('Error: buy_stock_marketprice(' + str(ticker) + '): problem in fillwait loop, ' + str(err), file=sys.stderr)
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
		data, err = tda.place_order(tda_account_number, order, True)
		if ( debug == 1 ):
			print('DEBUG: sell_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
			print(order)
			print(data)
			print(err)

		if ( err != None ):
			print('Error: sell_stock_marketprice(' + str(ticker) + '): attempt ' + str(attempt+1) + ',  ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: sell_stock_marketprice(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	order_id = tda.get_order_number(data)
	if ( debug == 1 ):
		print(order_id)
	if ( str(order_id) == '' ):
		print('Error: sell_stock_marketprice('+ str(ticker) + '): Unable to get order ID', file=sys.stderr)
		return False

	data,err = tda.get_order(tda_account_number, order_id, True)
	if ( debug == 1 ):
		print(data)
	if ( err != None ):
		print('Error: sell_stock_marketprice(' + str(ticker) + '): ' + str(err), file=sys.stderr)
		return False

	print('sell_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(10):
			data,err = tda.get_order(tda_account_number, order_id, True)
			if ( debug == True ):
				print(data)
			if ( err != None ):
				print('Error: sell_stock_marketprice(' + str(ticker) + '): problem in fillwait loop, ' + str(err), file=sys.stderr)
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
		data, err = tda.place_order(tda_account_number, order, True)
		if ( debug == 1 ):
			print('DEBUG: short_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
			print(order)
			print(data)
			print(err)

		if ( err != None ):
			print('Error: short_stock_marketprice(' + str(ticker) + '): attempt ' + str(attempt+1) + ', ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: short_stock_marketprice(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	order_id = tda.get_order_number(data)
	if ( debug == 1 ):
		print(order_id)
	if ( str(order_id) == '' ):
		print('Error: short_stock_marketprice('+ str(ticker) + '): Unable to get order ID', file=sys.stderr)
		return False

	data,err = tda.get_order(tda_account_number, order_id, True)
	if ( debug == 1 ):
		print(data)
	if ( err != None ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): ' + str(err), file=sys.stderr)
		return False

	print('short_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(10):
			data,err = tda.get_order(tda_account_number, order_id, True)
			if ( debug == True ):
				print(data)
			if ( err != None ):
				print('Error: short_stock_marketprice(' + str(ticker) + '): problem in fillwait loop, ' + str(err), file=sys.stderr)
				continue
			if ( data['filledQuantity'] == quantity ):
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
		data, err = tda.place_order(tda_account_number, order, True)
		if ( debug == 1 ):
			print('DEBUG: buytocover_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
			print(order)
			print(data)
			print(err)

		if ( err != None ):
			print('Error: buytocover_stock_marketprice(' + str(ticker) + '): attempt ' + str(attempt+1) + ',  ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: buytocover_stock_marketprice(): Login failure', file=sys.stderr)

			time.sleep(5)
		else:
			break

	order_id = tda.get_order_number(data)
	if ( debug == 1 ):
		print(order_id)
	if ( str(order_id) == '' ):
		print('Error: buytocover_stock_marketprice('+ str(ticker) + '): Unable to get order ID', file=sys.stderr)
		return False

	data,err = tda.get_order(tda_account_number, order_id, True)
	if ( debug == 1 ):
		print(data)
	if ( err != None ):
		print('Error: buytocover_stock_marketprice(' + str(ticker) + '): ' + str(err), file=sys.stderr)
		return False

	print('buytocover_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(10):
			data,err = tda.get_order(tda_account_number, order_id, True)
			if ( debug == True ):
				print(data)
			if ( err != None ):
				print('Error: buytocover_stock_marketprice(' + str(ticker) + '): problem in fillwait loop, ' + str(err), file=sys.stderr)
				continue
			if ( data['filledQuantity'] == quantity ):
				break

		print('buytocover_stock_marketprice(' + str(ticker) + '): Order completed (Order ID:' + str(order_id) + ')')

	return data


# Return numpy array of RSI values for a given price history.
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
		return False

	if ( len(prices) < rsi_period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Error: get_rsi(): len(pricehistory) is less than rsi_period - is this a new stock ticker?', file=sys.stderr)
		return False

	# Calculate the RSI for the entire numpy array
	pricehistory = np.array( prices )
	rsi = ti.rsi( pricehistory, period=rsi_period )

	return rsi


# Return numpy array of Stochastic RSI values for a given price history.
# 'pricehistory' should be a data list obtained from get_pricehistory()
def get_stochrsi(pricehistory=None, rsi_period=14, type='close', debug=False):

	if ( pricehistory == None ):
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
		return False

	if ( len(prices) < rsi_period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Error: get_stochrsi(): len(pricehistory) is less than rsi_period - is this a new stock ticker?', file=sys.stderr)
		return False

	pricehistory = np.array( prices )
	stochrsi = ti.stochrsi( pricehistory, period=rsi_period )

	return stochrsi


# Return an N-day analysis for a stock ticker using the RSI algorithm
def rsi_analyze(ticker=None, days=10, rsi_period=14, rsi_type='close', rsi_low_limit=30, rsi_high_limit=70, debug=False):

	if ( ticker == None ):
		return False
	if ( int(days) > 10 ):
		days = 10 # TDA API only allows 10-days of 1-minute daily data

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# Pull the 1-minute stock history
	# Note: Not asking for extended hours for now since our bot doesn't even trade after hours
	data, epochs = get_pricehistory(ticker, 'day', 'minute', '1', days, needExtendedHoursData=False, debug=False)
	if ( data == False ):
		return False
	if ( int(len(data['candles'])) <= rsi_period ):
		print('Not enough data - returned candles=' + str(len(data['candles'])) + ', rsi_period=' + str(rsi_period))
		exit(0)

	# With 10-day/1-min history there should be ~3900 datapoints in data['candles'] (6.5hrs * 60mins * 10days)
	# Therefore, with an rsi_period of 14, get_rsi() will return a list of 3886 items
	rsi = get_rsi(data, rsi_period, rsi_type, debug=False)
	if ( isinstance(rsi, bool) and rsi == False ):
		print('Error: get_rsi() returned false - no data', file=sys.stderr)
		return False
	if ( debug == True ):
		if ( len(rsi) != len(data['candles']) - rsi_period ):
			print('Warning, unexpected length of rsi (data[candles]=' + str(len(data['candles'])) + ', rsi=' + str(len(rsi)) + ')')

	# Run through the RSI values and log the results
	results = []
	prev_rsi = 0
	counter = 13
	signal_mode = 'buy'
	for cur_rsi in rsi:

		if ( prev_rsi == 0 ):
			prev_rsi = cur_rsi

		if ( signal_mode == 'buy' ):
			if ( prev_rsi < rsi_low_limit and cur_rsi > prev_rsi ):
				if ( cur_rsi >= rsi_low_limit ):
					# Buy
					purchase_price = float(data['candles'][counter]['close'])
					purchase_time = datetime.fromtimestamp(float(data['candles'][counter]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
					signal_mode = 'sell'

		if ( signal_mode == 'sell' ):
			if ( prev_rsi > rsi_high_limit and cur_rsi < prev_rsi ):
				if ( cur_rsi <= rsi_high_limit ):
					# Sell
					sell_price = float(data['candles'][counter]['close'])
					net_change = sell_price - purchase_price
					sell_time = datetime.fromtimestamp(float(data['candles'][counter]['datetime'])/1000, tz=mytimezone)
					results.append( str(purchase_price) + ',' + str(sell_price) + ',' + str(net_change) + ',' +
						str(purchase_time) + ',' + str(sell_time.strftime('%Y-%m-%d %H:%M:%S.%f')) )
					signal_mode = 'buy'

		prev_rsi = cur_rsi
		counter += 1

	return results

