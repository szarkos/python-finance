#!/usr/bin/python3 -u

import os, fcntl, re
import time
from datetime import datetime
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


# Returns True if it's near the end of the trading day
#  Currently returns true if it's 5-minutes or less from 4:00PM Eastern
# Nasdaq and NYSE open at 9:30AM and close at 4:00PM
def isendofday():
	eastern = timezone('US/Eastern') # Observes EST and EDT
	est_time = datetime.now(eastern)
	if ( int(est_time.strftime('%-H')) == 15 and int(est_time.strftime('%-M')) >= 55 ):
		return True

	## Testing (return true at 10:30AM ET)
#	if ( int(est_time.strftime('%-H')) == 10 and int(est_time.strftime('%-M')) >= 30 ):
#		return True
	## Testing

	return False


# Returns True the US markets are open
# Nasdaq and NYSE open at 9:30AM and close at 4:00PM, Monday-Friday
# FIXME: This will still return True on US holidays
def ismarketopen_US():
	eastern = timezone('US/Eastern') # Observes EST and EDT
	est_time = datetime.now(eastern)
	if ( int(est_time.strftime('%w')) != 0 and int(est_time.strftime('%w')) != 6 ): # 0=Sunday, 6=Saturday
		if ( int(est_time.strftime('%-H')) >= 9 ):
			if ( int(est_time.strftime('%-H')) == 9 ):
				if ( int(est_time.strftime('%-M')) < 30 ):
					return False
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
			print('Error: log_monitor(): Unable to open file ' + str(logfile) + ', ' + e)
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

	msg =	str(ticker)		+ ':' + \
		str(percent_change)	+ ':' + \
		str(last_price)		+ ':' + \
		str(net_change)		+ ':' + \
		str(base_price)		+ ':' + \
		str(orig_base_price)	+ ':' + \
		str(stock_qty)		+ ':' + \
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
		print('Error: get_lastprice(' + str(ticker) + '): ' + str(err))
		return False
	elif ( data == {} ):
		print('Error: get_lastprice(' + str(ticker) + '): Empty data set')
		return False

	if ( WarnDelayed == True and data[ticker]['delayed'] == 'true' ):
		print('Warning: get_lastprice(' + str(ticker) + '): quote data delayed')

	if ( debug == True ):
		print(data)

	# Note: return regularMarketLastPrice if we don't want extended hours pricing
	return float(data[ticker]['lastPrice'])


# Purchase a stock at Market price
#  Ticker = stock ticker
#  Quantity = amount of stock to purchase
#  fillwait = (boolean) wait for order to be filled before returning
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
			print('Error: buy_stock_marketprice(' + str(ticker) + '): attempt ' + str(attempt+1) + ', ' + str(err))
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: buy_stock_marketprice(): Login failure')

			time.sleep(5)
		else:
			break

	order_id = tda.get_order_number(data)
	if ( debug == 1 ):
		print(order_id)
	if ( str(order_id) == '' ):
		print('Error: buy_stock_marketprice('+ str(ticker) + '): Unable to get order ID')
		return False

	data,err = tda.get_order(tda_account_number, order_id, True)
	if ( debug == 1 ):
		print(data)
	if ( err != None ):
		print('Error: buy_stock_marketprice(' + str(ticker) + '): ' + str(err))
		return False

	print('buy_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')
	if ( fillwait == True ):
		while data['filledQuantity'] != quantity :
			time.sleep(10)
			data,err = tda.get_order(tda_account_number, order_id, True)
			if ( debug == True ):
				print(data)

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
			print('Error: sell_stock_marketprice(' + str(ticker) + '): attempt ' + str(attempt+1) + ',  ' + str(err))
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: sell_stock_marketprice(): Login failure')

			time.sleep(5)
		else:
			break

	order_id = tda.get_order_number(data)
	if ( debug == 1 ):
		print(order_id)
	if ( str(order_id) == '' ):
		print('Error: sell_stock_marketprice('+ str(ticker) + '): Unable to get order ID')
		return False

	data,err = tda.get_order(tda_account_number, order_id, True)
	if ( debug == 1 ):
		print(data)
	if ( err != None ):
		print('Error: sell_stock_marketprice(' + str(ticker) + '): ' + str(err))
		return False

	print('buy_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')
	if ( fillwait == True ):
		while data['filledQuantity'] != quantity :
			time.sleep(10)
			data,err = tda.get_order(tda_account_number, order_id, True)
			if ( debug == True ):
				print(data)

		print('sell_stock_marketprice(' + str(ticker) + '): Order completed (Order ID:' + str(order_id) + ')')

	return data


# Return a list with the price history of a given stock
# Useful for calculating various indicators such as RSI
def get_pricehistory(ticker=None, p_type=None, f_type=None, freq=None, period=None, start_date=None, end_date=None, needExtendedHoursData=False, debug=False):

	if ( ticker == None ):
		return False, [], []


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
			print('Error: start_date or end_date is out of market open and extended hours (weekend)')
			return False, [], []


	# Example: {'open': 236.25, 'high': 236.25, 'low': 236.25, 'close': 236.25, 'volume': 500, 'datetime': 1616796960000}
	data,err = tda.get_price_history(ticker, p_type, f_type, freq, period, start_date=start_date, end_date=end_date, needExtendedHoursData=needExtendedHoursData, jsonify=True)
	if ( err != None ):
		print('Error: get_price_history(' + str(ticker) + ', ' + str(p_type) + ', ' +
			str(f_type) + ', ' + str(freq) + ', ' + str(period) + ', ' +
			str(start_date) + ', ' + str(end_date) +'): ' + str(err))

		return False, [], []

	closeprices = []
	epochs = []
	for key in data['candles']:
		closeprices.append(float(key['close']))
		epochs.append(float(key['datetime']))

	return data, closeprices, epochs


# Return numpy array of RSI values for a given price history
def get_rsi(closeprices=None, rsiPeriod=14, debug=False):

	if ( closeprices == None ):
		return False

	# Note: This seems like it would be a good optimization here, but for RSI it seems the more history the better.
	#closeprices = closeprices[len(closePrices) - (rsiPeriod+5):]

	if ( len(closeprices) < rsiPeriod ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Error: len(closeprices) is less than rsiPeriod')
		return False

	# Calculate the RSI for the entire numpy array
	pricehistory = np.array( closeprices )
	rsi = ti.rsi( pricehistory, period=rsiPeriod )

	return rsi

