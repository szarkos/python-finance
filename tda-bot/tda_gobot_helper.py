#!/usr/bin/python3 -u

import os, sys, re, time
from collections import OrderedDict

from datetime import datetime, timedelta
from pytz import timezone

import numpy as np
import pandas as pd
import tulipy as ti

from func_timeout import func_timeout, FunctionTimedOut


# Login to tda using a passcode
def tdalogin(passcode=None):

	if ( passcode == None ):
		print('Error: tdalogin(): passcode is empty', file=sys.stderr)
		return False

	try:
		enc = func_timeout(5, tda.login, args=(passcode,))

	except FunctionTimedOut:
		print('Caught Exception: tdalogin(): timed out after 10 seconds')
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
def ismarketopen_US(date=None, safe_open=False):
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

				# Do not return True until after 10AM EST to avoid some of the volatility of the open
				if ( isinstance(safe_open, bool) and safe_open == True ):
					return False

				if ( int(est_time.strftime('%-M')) >= 30 ):
					return True
				else:
					return False

			if ( int(est_time.strftime('%-H')) == 10 ):

				# Do not return True until after 10:15AM to void some of the volatility of the open
				if ( isinstance(safe_open, bool) and safe_open == True ):
					if ( int(est_time.strftime('%-M')) >= 15 ):
						return True
					else:
						return False

			if ( int(est_time.strftime('%-H')) <= 15 and int(est_time.strftime('%-M')) <= 59 ):
				return True

	return False


# Write logs for each ticker for live monitoring of the stock performance
def log_monitor(ticker=None, percent_change=-1, last_price=-1, net_change=-1, base_price=-1, orig_base_price=-1, stock_qty=-1, sold=False, short=False, proc_id=None, tx_log_dir='TX_LOGS', debug=False):

	if ( ticker == None ):
		print('Error: log_monitor(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	if ( proc_id == None ):
		try:
			proc_id = process_id
		except NameError:
			proc_id = '0000'

	logfile = './' + str(tx_log_dir) + '/' + str(ticker) + '-' + str(proc_id) + '.txt'
	try:
		if ( os.path.isdir('./' + tx_log_dir) == False ):
			os.mkdir('./' + tx_log_dir, mode=0o755)

	except OSError as e:
		print('Error: log_monitor(): Unable to make directory ./' + str(tx_log_dir) + ': ' + e, file=sys.stderr)
		return False

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

	if ( os.name != 'nt' ):
		import fcntl

		fcntl.lockf( fh, fcntl.LOCK_EX )
		print( msg, file=fh, flush=True )
		fcntl.lockf( fh, fcntl.LOCK_UN )

	else:
		print( msg, file=fh, flush=True )

	fh.close()

	return True


# Fix up stock symbol if needed
def fix_stock_symbol(stock=None):
	if ( stock == None ):
		return None

	stock_list = []
	for ticker in stock.split(','):

		# Some NYSE stock symbols come through as XXpX (preferred shares)
		#  TDA API will not resolve these as-is, so swap the 'p' for a '-'
		if ( re.search(r'p', ticker) != None ):
			ticker = re.sub( r'p', r'-', ticker )

		stock_list.append(str(ticker).upper())

	return ','.join(stock_list)


# Check that we can query using a stock symbol
# Returns True or False if querying for a single stock ticker
# If passing multiple stocks -
#   - The 'stock' string must be comma-delimited with no spaces (per the API)
#   - Returns a comma-delimited string of stocks that were queryable (so bad tickers are simply removed)
def check_stock_symbol(stock=None):
	if ( stock == None ):
		print('Error: check_stock_symbol(' + str(stock) + '): ticker is empty', file=sys.stderr)
		return False

	# Multiple stock check
	if ( re.search(',', stock) ):

		# Split the request in batches of 100
		if ( len(stock.split(',')) > 100 ):
			maxq = 100
			stocks = ''

			all_stocks = stock.split(',')
			all_stocks = [all_stocks[i:i + maxq] for i in range(0, len(all_stocks), maxq)]

			for query in all_stocks:

				query = ','.join(query)
				try:
					data,err = func_timeout(10, tda.stocks.get_quotes, args=(str(query), True))

				except FunctionTimedOut:
					print('Caught Exception: check_stock_symbol(' + str(query) + '): tda.stocks.get_quotes(): timed out after 10 seconds', file=sys.stderr)
					return False
				except Exception as e:
					print('Caught Exception: check_stock_symbol(' + str(query) + '): tda.stocks.get_quotes(): ' + str(e), file=sys.stderr)
					return False

				if ( err != None ):
					print('Error: check_stock_symbol(' + str(query) + '): tda.stocks.get_quotes(): ' + str(err), file=sys.stderr)
					return False
				elif ( data == {} ):
					print('Error: check_stock_symbol(' + str(query) + '): tda.stocks.get_quotes(): Empty data set', file=sys.stderr)
					return False

				stocks += ',' + ','.join(list(data.keys()))

			stocks = re.sub('^,', '', stocks)
			stocks = re.sub(',$', '', stocks)

			return stocks

		else:
			try:
				data,err = func_timeout(10, tda.stocks.get_quotes, args=(str(stock), True))

			except FunctionTimedOut:
				print('Caught Exception: check_stock_symbol(' + str(stock) + '): tda.stocks.get_quotes(): timed out after 10 seconds', file=sys.stderr)
				return False
			except Exception as e:
				print('Caught Exception: check_stock_symbol(' + str(stock) + '): tda.stocks.get_quotes(): ' + str(e), file=sys.stderr)
				return False

			if ( err != None ):
				print('Error: get_lastprice(' + str(stock) + '): ' + str(err), file=sys.stderr)
				return False
			elif ( data == {} ):
				print('Error: get_lastprice(' + str(stock) + '): Empty data set', file=sys.stderr)
				return False

			stocks = ','.join(list(data.keys()))

			return stocks


	# Single stock check
	else:

		try:
			last_price = get_lastprice(stock, WarnDelayed=False)

		except Exception as e:
			print('Caught Exception: get_lastprice(' + str(stock) + '): ' + str(e), file=sys.stderr)
			return False

		if ( last_price == False ):
			# Ticker may be invalid
			return False

		return stock

	return False


# Write a stock blacklist that can be used to avoid wash sales
def write_blacklist(ticker=None, stock_qty=-1, orig_base_price=-1, last_price=-1, net_change=-1, percent_change=-1, permanent=False, debug=False):

	if ( ticker == None ):
		print('Error: write_blacklist(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	# We're assuming the blacklist file will be in the same path as tda_gobot_helper
	parent_path = os.path.dirname( os.path.realpath(__file__) )
	blacklist = str(parent_path) + '/.stock-blacklist'
	try:
		fh = open( blacklist, "at" )

	except OSError as e:
		print('Error: write_blacklist(): Unable to open file ' + str(blacklist) + ': ' + e, file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	time_now = 9999999999
	if ( permanent == False ):
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

	if ( os.name != 'nt' ):
		import fcntl

		fcntl.lockf( fh, fcntl.LOCK_EX )
		print( msg, file=fh, flush=True )
		fcntl.lockf( fh, fcntl.LOCK_UN )

	else:
		print( msg, file=fh, flush=True )

	fh.close()

	return True


# Check stock blacklist to avoid wash sales
# Returns True if ticker is in the file and time_stamp is < 30 days ago
def check_blacklist(ticker=None, debug=1):
	if ( ticker == None ):
		print('Error: check_blacklist(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	found = False

	# We're assuming the blacklist file will be in the same path as tda_gobot_helper
	parent_path = os.path.dirname( os.path.realpath(__file__) )
	blacklist = str(parent_path) + '/.stock-blacklist'
	if ( os.path.exists(blacklist) == False ):
		print('WARNING: check_blacklist(): File ' + str(blacklist) + ' does not exist', file=sys.stderr)
		return True

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
			if ( time_stamp + timedelta(days=32) > time_now ):

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
		data,err = func_timeout(4, tda.stocks.get_quote, args=(ticker, True))

	except FunctionTimedOut:
		print('Caught Exception: get_lastprice(' + str(ticker) + '): tda.stocks.get_quote(): timed out after 4 seconds')
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


# Return the quote information for one or more stock tickers
# This can be a little tricky as TDA's API sometimes truncates large queries, so we need to break
#  up the list of tickers into multiple queries.
def get_quotes(stock=None):
	if ( stock == None ):
		print('Error: get_quotes(' + str(stock) + '): ticker is empty', file=sys.stderr)
		return False

	# Get quotes for multiple stocks
	if ( re.search(',', stock) ):

		# Split the request in batches of 100
		if ( len(stock.split(',')) > 100 ):
			maxq = 100
			stocks = {}

			all_stocks = stock.split(',')
			all_stocks = [all_stocks[i:i + maxq] for i in range(0, len(all_stocks), maxq)]

			for query in all_stocks:

				query = ','.join(query)
				try:
					data,err = func_timeout(10, tda.stocks.get_quotes, args=(str(query), True))

				except FunctionTimedOut:
					print('Caught Exception: get_quotes(' + str(query) + '): tda.stocks.get_quotes(): timed out after 10 seconds', file=sys.stderr)
					return False
				except Exception as e:
					print('Caught Exception: get_quotes(' + str(query) + '): tda.stocks.get_quotes(): ' + str(e), file=sys.stderr)
					return False

				if ( err != None ):
					print('Error: get_quotes(' + str(query) + '): tda.stocks.get_quotes(): ' + str(err), file=sys.stderr)
					return False
				elif ( data == {} ):
					print('Error: get_quotes(' + str(query) + '): tda.stocks.get_quotes(): Empty data set', file=sys.stderr)
					return False

				stocks.update(data)

			return stocks

		else:
			try:
				data,err = func_timeout(10, tda.stocks.get_quotes, args=(str(stock), True))

			except FunctionTimedOut:
				print('Caught Exception: get_quotes(' + str(stock) + '): tda.stocks.get_quotes(): timed out after 10 seconds', file=sys.stderr)
				return False
			except Exception as e:
				print('Caught Exception: get_quotes(' + str(stock) + '): tda.stocks.get_quotes(): ' + str(e), file=sys.stderr)
				return False

			if ( err != None ):
				print('Error: get_quotes(' + str(stock) + '): tda.stocks.get_quotes(): ' + str(err), file=sys.stderr)
				return False
			elif ( data == {} ):
				print('Error: get_quotes(' + str(stock) + '): tda.stocks.get_quotes(): Empty data set', file=sys.stderr)
				return False

			return data

	return False


# Fix the timestamp for get_pricehistory()
# TDA API is very picky and may reject requests with timestamps that are
#  outside normal or extended hours
def fix_timestamp(date=None, debug=False):

	if ( date == None or isinstance(date, datetime) == False ):
		return None

	try:
		mytimezone

	except:
		mytimezone = timezone("US/Eastern")

	finally:
		date = date.replace(tzinfo=mytimezone)

	# Make sure start and end dates don't land on a weekend
	# 0=Sunday, 6=Saturday
	day = int( date.strftime('%w') )
	if ( day == 0 ):
		date = date - timedelta( days=2 )
	elif ( day == 6 ):
		date = date - timedelta( days=1 )

	# Make sure start_end dates aren't outside regular hours
	# We could use extended hours here, but we assume regular hours
	#  since "needExtendedHoursData=True" is the default
	hour = int( date.strftime('%-H') )
	if ( hour >= 16 ):
		date = date - timedelta( hours=hour-15 )
	elif ( hour >= 0 and hour <= 10 ):
		date = date + timedelta( hours=10-hour )

	return date


# Return a list with the price history of a given stock
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
	data = err = ''
	try:
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
def get_price_stats_hourly(ticker=None, days=10, extended_hours=True, debug=False):

	if ( ticker == None ):
		print('Error: get_price_stats(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False, 0, 0, 0

	if ( int(days) > 10 ):
		days = 10 # TDA API only allows 10-days of 1-minute data

	try:
		data, epochs = get_pricehistory(ticker, 'day', 'minute', '1', days, needExtendedHoursData=extended_hours, debug=debug)

	except Exception as e:
		print('Caught Exception: get_price_stats(' + str(ticker) + '): ' + str(e))

	if ( data == False ):
		print('Error: get_price_stats(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False, 0, 0, 0

	high = avg = avg_vol = float(0)
	low = 999999
	for key in data['candles']:
		avg += float(key['close'])
		avg_vol += float(key['volume'])

		if ( float(key['close']) > high ):
			high = float(key['close'])
		if ( float(key['close']) < low ):
			low = float(key['close'])

	avg = round(avg / len(data['candles']), 4)
	avg_vol = round(avg_vol / len(data['candles']), 0)

	# Return the high, low and average stock price
	return high, low, avg, int(avg_vol)


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
	#  or outside market hours
	end_date = fix_timestamp(end_date)
	start_date = fix_timestamp(start_date)

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		data, epochs = get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

	except Exception as e:
		print('Caught Exception: get_price_stats(' + str(ticker) + '): ' + str(e))

	if ( data == False ):
		if ( debug == True ):
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


# Get previous day close
def get_pdc(pricehistory=None, debug=False):

	if ( pricehistory == None ):
		return None

	ticker = ''
	try:
		ticker = pricehistory['symbol']

	except Exception as e:
		print('(' + str(ticker) + '): Exception caught: ' + str(e))
		return None

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	today = pricehistory['candles'][-1]['datetime']
	today = datetime.fromtimestamp(float(today)/1000, tz=mytimezone)

	yesterday = today - timedelta(days=1)
	yesterday = fix_timestamp(yesterday)
	yesterday = yesterday.strftime('%Y-%m-%d')

	today = today.strftime('%Y-%m-%d')

	pdc = None
	try:
		from pandas_datareader import data as web

		pdc = func_timeout( 10, web.DataReader, args=(ticker,), kwargs={'data_source': 'yahoo', 'start': yesterday, 'end': yesterday} )
		pdc = pdc['Adj Close']
		pdc = pdc.values[0]

	except FunctionTimedOut:
		print('(' + str(ticker) + '): Exception caught: get_pdc(): web.DataReader timed out')
		return None

	except Exception as e:
		print('(' + str(ticker) + '): Exception caught: ' + str(e))
		return None

	return float(pdc)


# Return the N-day simple moving average (SMA) (default: 200-day)
def get_sma(ticker=None, period=200, debug=False):

	days = 730	# Number of days to request from API. This needs to be larger
			#  than period because we're subtracting days from start_date,
			#  which will include weekends/holidays.

	if ( ticker == None ):
		print('Error: get_sma(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False, []

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	end_date = datetime.now( mytimezone )
	start_date = end_date - timedelta( days=days )

	# Make sure start and end dates don't land on a weekend
	#  or outside market hours
	end_date = fix_timestamp(end_date)
	start_date = fix_timestamp(start_date)

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		ph, epochs = get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

	except Exception as e:
		print('Caught Exception: get_sma(' + str(ticker) + '): ' + str(e))

	if ( ph == False ):
		print('Error: get_sma(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False, []

	if ( len(ph['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print( 'Warning: get_sma(' + str(ticker) + ', ' + str(period) + '): len(ph) is less than period (' +
			str(len(ph['candles'])) + ') - unable to calculate SMA')
		return False, []

	# Put pricehistory data into a numpy array
	prices = []
	for key in ph['candles']:
		prices.append( float(key['close']) )

	prices = np.array( prices )

	# Get the N-day SMA
	try:
		sma = ti.sma(prices, period=period)

	except Exception as e:
		print('Caught Exception: get_sma(' + str(ticker) + '): ti.sma(): ' + str(e))
		return False, []

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(sma)

	return tuple(sma), ph


# Return the N-day simple moving average (eMA) (default: 50-day)
def get_ema(ticker=None, period=50, debug=False):

	days = 365	# Number of days to request from API. This needs to be larger
			#  than period because we're subtracting days from start_date,
			#  which will include weekends/holidays.

	if ( ticker == None ):
		print('Error: get_ema(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False, []

	try:
		assert mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	end_date = datetime.now( mytimezone )
	start_date = end_date - timedelta( days=days )

	# Make sure start and end dates don't land on a weekend
	#  or outside market hours
	end_date = fix_timestamp(end_date)
	start_date = fix_timestamp(start_date)

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		ph, epochs = get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

	except Exception as e:
		print('Caught Exception: get_ema(' + str(ticker) + '): ' + str(e))

	if ( ph == False ):
		print('Error: get_ema(' + str(ticker) + '): get_pricehistory() returned False', file=sys.stderr)
		return False, []

	if ( len(ph['candles']) < period ):
		# Possibly this ticker is too new, not enough history
		print( 'Error: get_ema(' + str(ticker) + ', ' + str(period) + '): len(ph) is less than period (' +
			str(len(ph['candles'])) + ') - unable to calculate EMA')
		return False, []

	# Put pricehistory data into a numpy array
	prices = []
	for key in ph['candles']:
		prices.append( float(key['close']) )

	prices = np.array( prices )

	# Get the N-day EMA
	try:
		ema = ti.ema(prices, period=period)

	except Exception as e:
		print('Caught Exception: get_ema(' + str(ticker) + '): ti.ema(): ' + str(e))
		return False, []

	if ( debug == True ):
		pd.set_option('display.max_rows', None)
		pd.set_option('display.max_columns', None)
		pd.set_option('display.width', None)
		pd.set_option('display.max_colwidth', None)
		print(ema)

	return tuple(ema), ph


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
	end_date = fix_timestamp(end_date)
	start_date = fix_timestamp(start_date)

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		pricehistory, epochs = get_pricehistory(ticker, 'year', 'daily', '1', start_date=start_date, end_date=end_date)

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
	end_date = fix_timestamp(end_date)
	start_date = fix_timestamp(start_date)

	start_date = int( start_date.timestamp() * 1000 )
	end_date = int( end_date.timestamp() * 1000 )

	try:
		pricehistory, epochs = get_pricehistory(ticker, 'day', 'minute', '1', start_date=start_date, end_date=end_date, needExtendedHoursData=True)

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
	try:
		rsi = ti.rsi( prices, period=stochrsi_period )
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
	ticker = pricehistory['symbol']
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
		print('Caught exception: get_vwap(' + str(pricehistory['symbol']) + '): ' + str(e), file=sys.stderr)
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
def get_bbands(pricehistory=None, type=None, period=128, stddev=2, debug=False):

	if ( pricehistory == None ):
		print('Error: get_bbands(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
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
		print('Error: get_bbands(' + str(ticker) + '): Undefined type "' + str(type) + '"', file=sys.stderr)
		return False, [], []

	if ( len(prices) < period ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Warning: get_bbands(' + str(ticker) + '): len(pricehistory) is less than period - is this a new stock ticker?', file=sys.stderr)

	# ti.bbands
	bbands_lower = []
	bbands_middle = []
	bbands_upper = []
	try:
		np_prices = np.array( prices )
		bbands_lower, bbands_middle, bbands_upper = ti.bbands(prices, period, stddev)

	except Exception as e:
		print( 'Caught Exception: get_bbands(' + str(ticker) + '): ti.bbands(): ' + str(e) + ', len(pricehistory)=' + str(len(pricehistory['candles'])) )
		return False, [], []

	return bbands_lower, bbands_middle, bbands_upper


# Get MACD
def get_macd(pricehistory=None, short_period=12, long_period=26, signal_period=9, debug=False):

	if ( pricehistory == None ):
		return False, [], []

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

	return tuple(macd), tuple(macd_signal), tuple(macd_histogram)


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

	# Make sure we are logged into TDA
	if ( tdalogin(passcode) != True ):
		print('Error: buy_stock_marketprice(' + str(ticker) + '): tdalogin(): login failure', file=sys.stderr)

	# Try to buy the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = func_timeout(5, tda.place_order, args=(tda_account_number, order, True))
			if ( debug == True ):
				print('DEBUG: buy_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except FunctionTimedOut:
			print('Caught Exception: buy_stock_marketprice(' + str(ticker) + '): tda.place_order(): timed out after 5 seconds')
			err = 'Timed Out'

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

			time.sleep(2)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = func_timeout(5, tda.get_order_number, args=(data,))
		if ( debug == True ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: buy_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: buy_stock_marketprice('+ str(ticker) + '): tda.get_order_number(): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
		if ( debug == True ):
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
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
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

	# Make sure we are logged into TDA
	if ( tdalogin(passcode) != True ):
		print('Error: sell_stock_marketprice(' + str(ticker) + '): tdalogin(): login failure', file=sys.stderr)

	# Try to sell the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = func_timeout(5, tda.place_order, args=(tda_account_number, order, True))
			if ( debug == True ):
				print('DEBUG: sell_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except FunctionTimedOut:
			print('Caught Exception: sell_stock_marketprice(' + str(ticker) + '): tda.place_order(): timed out after 5 seconds')
			err = 'Timed Out'

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

			time.sleep(2)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = func_timeout(5, tda.get_order_number, args=(data,))
		if ( debug == True ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: sell_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: sell_stock_marketprice('+ str(ticker) + '): tda.get_order_number(): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
		if ( debug == True ):
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
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
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

	# Make sure we are logged into TDA
	if ( tdalogin(passcode) != True ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): tdalogin(): login failure', file=sys.stderr)

	# Try to buy the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = func_timeout(5, tda.place_order, args=(tda_account_number, order, True))
			if ( debug == True ):
				print('DEBUG: sell_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except FunctionTimedOut:
			print('Caught Exception: short_stock_marketprice(' + str(ticker) + '): tda.place_order(): timed out after 5 seconds')
			err = 'Timed Out'

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

			time.sleep(2)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = func_timeout(5, tda.get_order_number, args=(data,))
		if ( debug == True ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: short_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
		if ( debug == True ):
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
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
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

	# Make sure we are logged into TDA
	if ( tdalogin(passcode) != True ):
		print('Error: buytocover_stock_marketprice(' + str(ticker) + '): tdalogin(): login failure', file=sys.stderr)

	# Try to sell the stock num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			#data, err = tda.place_order(tda_account_number, order, True)
			data, err = func_timeout(5, tda.place_order, args=(tda_account_number, order, True))
			if ( debug == True ):
				print('DEBUG: buytocover_stock_marketprice(): tda.place_order(' + str(ticker) + '): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except FunctionTimedOut:
			print('Caught Exception: buytocover_stock_marketprice(' + str(ticker) + '): tda.place_order(): timed out after 5 seconds')
			err = 'Timed Out'

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

			time.sleep(2)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = func_timeout(5, tda.get_order_number, args=(data,))
		if ( debug == True ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: buytocover_stock_marketprice(' + str(ticker) + '): tda.get_order_number(): ' + str(e))
		return data

	if ( str(order_id) == '' ):
		print('Error: buytocover_stock_marketprice('+ str(ticker) + '): tda.get_order_number(): Unable to get order ID', file=sys.stderr)
		return data

	# Get order information to determine if it was filled
	try:
		data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
		if ( debug == True ):
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
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(tda_account_number, order_id, True))
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


# Return the key levels for a stock
# Preferably uses weekly candle data for pricehistory
# If filter=True, we use ATR to help filter the data and remove key levels that are
#  within one ATR from eachother
def get_keylevels(pricehistory=None, atr_period=14, filter=True, plot=False, debug=False):

	if ( pricehistory == None ):
		return False, []

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Determine if level is a support pivot based on five-candle fractal
	def is_support(df, i):
		support = False
		try:
			support =	df['low'][i] <= df['low'][i-1] and \
					df['low'][i] <= df['low'][i+1] and \
					df['low'][i+1] <= df['low'][i+2] and \
					df['low'][i-1] <= df['low'][i-2]

		except Exception as e:
			print('Exception caught: get_keylevels(' + str(ticker) + '): is_support(): ' + str(e) + '. Ignoring level (' + str(df['low'][i]) + ').' )
			return False, []

		return support

	# Determine if level is a resistance pivot based on five-candle fractal
	def is_resistance(df, i):
		resistance = False
		try:
			resistance =	df['high'][i] >= df['high'][i-1] and \
					df['high'][i] >= df['high'][i+1] and \
					df['high'][i+1] >= df['high'][i+2] and \
					df['high'][i-1] >= df['high'][i-2]
		except Exception as e:
			print('Exception caught: get_keylevels(' + str(ticker) + '): is_resistance(): ' + str(e) + '. Ignoring level (' + str(df['high'][i]) + ').' )
			return False, []

		return resistance

	# Reduce noise by eliminating levels that are close to levels that
	#   have already been discovered
	def check_atr_level( lvl=None, atr=1, levels=[] ):
		return np.sum( [abs(lvl - x) < atr for x in levels] ) == 0


	# Need to massage the data to ensure matplotlib works
	if ( plot == True ):
		try:
			assert mytimezone
		except:
			mytimezone = timezone("US/Eastern")

		ph = []
		for key in pricehistory['candles']:

			d = {	'Date':		datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone),
				'open':		float( key['open'] ),
				'high':		float( key['high'] ),
				'low':		float( key['low'] ),
				'close':	float( key['close'] ),
				'volume':	float( key['volume'] ) }

			ph.append(d)

		df = pd.DataFrame(data=ph, columns = ['Date', 'open', 'high', 'low', 'close', 'volume'])
		df = df.loc[:,['Date', 'open', 'high', 'low', 'close', 'volume']]

	else:
		df = pd.DataFrame(data=pricehistory['candles'], columns = ['open', 'high', 'low', 'close', 'volume', 'datetime'])

	# Process all candles and check for five-candle fractal levels, and append them to long_support[] or long_resistance[]
	long_support = []
	long_resistance = []
	plot_support_levels = []
	plot_resistance_levels = []
	for i in range( 2, df.shape[0]-2 ):

		# SUPPORT
		if ( is_support(df, i) ):
			lvl = float( df['low'][i] )

			if ( filter == False ):
				long_support.append(lvl)

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
				long_support.append(lvl)

				if ( plot == True ):
					plot_support_levels.append( (i, lvl) )


		# RESISTANCE
		elif ( is_resistance(df, i) ):
			lvl = float( df['high'][i] )

			if ( filter == False ):
				long_resistance.append(lvl)

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
				long_resistance.append(lvl)

				if ( plot == True ):
					plot_resistance_levels.append( (i, lvl) )


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


	return long_support, long_resistance


# Like stochrsi_analyze(), but sexier
def stochrsi_analyze_new( pricehistory=None, ticker=None, rsi_period=14, stochrsi_period=128, rsi_type='close', rsi_slow=3, rsi_low_limit=20, rsi_high_limit=80, rsi_k_period=128, rsi_d_period=3,
			  stoploss=False, incr_threshold=1, decr_threshold=1.5, hold_overnight=False, exit_percent=None, strict_exit_percent=False, vwap_exit=False, quick_exit=False,
			  variable_exit=False, no_use_resistance=False, price_resistance_pct=1, price_support_pct=1,
			  with_rsi=False, with_adx=False, with_dmi=False, with_aroonosc=False, with_macd=False, with_vwap=False, with_vpt=False, with_mfi=False,
			  with_dmi_simple=False, with_macd_simple=False, aroonosc_with_macd_simple=False, aroonosc_with_vpt=False, aroonosc_secondary_threshold=70,
			  vpt_sma_period=72, adx_period=92, di_period=48, atr_period=14, adx_threshold=25, mfi_period=14, aroonosc_period=48,
			  mfi_low_limit=20, mfi_high_limit=80,
			  check_ma=False, noshort=False, shortonly=False, safe_open=True, start_date=None, weekly_ph=None, keylevel_strict=False,
			  debug=False, debug_all=False ):

	if ( ticker == None or pricehistory == None ):
		print('Error: stochrsi_analyze(' + str(ticker) + '): Either pricehistory or ticker is empty', file=sys.stderr)
		return False

	try:
		assert mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# If set, turn start_date into a datetime object
	if ( start_date != None ):
		start_date = datetime.strptime(start_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
		start_date = mytimezone.localize(start_date)

	# Get stochastic RSI
	try:
		stochrsi, rsi_k, rsi_d = get_stochrsi(pricehistory, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi(): ' + str(e))
		return False

	if ( isinstance(stochrsi, bool) and stochrsi == False ):
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi() returned false - no data', file=sys.stderr)
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

	# Get RSI
	try:
		rsi = get_rsi(pricehistory, rsi_period, rsi_type, debug=False)
	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_rsi(): ' + str(e))
		return False

	# Get MFI
	try:
		mfi = get_mfi(pricehistory, period=mfi_period)
		mfi_2x = get_mfi(pricehistory, period=24)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_mfi(): ' + str(e))

	# Average True Range (ATR)
	# We use 5-minute candles to calculate the ATR
	pricehistory_5m = { 'candles': [], 'ticker': ticker }
	for idx,key in enumerate(pricehistory['candles']):
		if ( idx == 0 ):
			continue

		cndl_num = idx + 1
		if ( cndl_num % 5 == 0 ):
			open_p	= float( pricehistory['candles'][idx - 4]['open'] )
			close	= float( pricehistory['candles'][idx]['close'] )
			high	= 0
			low	= 9999
			volume	= 0

			for i in range(4,0,-1):
				volume += int( pricehistory['candles'][idx-i]['volume'] )

				if ( high < float(pricehistory['candles'][idx-i]['high']) ):
					high = float( pricehistory['candles'][idx-i]['high'] )

				if ( low > float(pricehistory['candles'][idx-i]['low']) ):
					low = float( pricehistory['candles'][idx-i]['low'] )

			newcandle = {	'open':		open_p,
					'high':		high,
					'low':		low,
					'close':	close,
					'volume':	volume,
					'datetime':	pricehistory['candles'][idx]['datetime'] }

			pricehistory_5m['candles'].append(newcandle)

	del(open_p, high, low, close, volume, newcandle)

	# Calculate the ATR
	atr = []
	natr = []
	try:
		atr, natr = get_atr( pricehistory=pricehistory_5m, period=atr_period )

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_atr(): ' + str(e))
		return False


	# ADX, +DI, -DI
	# We now use different periods for adx and plus/minus_di
	if ( with_dmi == True and with_dmi_simple == True ):
		with_dmi_simple = False

	adx = []
	plus_di = []
	minus_di = []
	try:
		adx, plus_di, minus_di = get_adx(pricehistory, period=di_period)
		adx, plus_di_adx, minus_di_adx = get_adx(pricehistory, period=adx_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_adx(): ' + str(e))
		return False

	# Aroon Oscillator
	# aroonosc_with_macd_simple implies that macd_simple will be enabled or disabled based on the
	#  level of the aroon oscillator (i.e. < aroonosc_secondary_threshold then use macd_simple)
	if ( aroonosc_with_macd_simple == True ):
		with_aroonosc = True
		with_macd = False
		with_macd_simple = False

	aroonosc = []
	aroonosc_92 = []
	try:
		aroonosc = get_aroon_osc(pricehistory, period=aroonosc_period)
		aroonosc_92 = get_aroon_osc(pricehistory, period=92)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_aroon_osc(): ' + str(e))
		return False

	# MACD - 48, 104, 36
	macd_offset = 0.006
	if ( with_macd == True and with_macd_simple == True):
		with_macd_simple = False

	macd = []
	macd_signal = []
	macd_histogram = []
	try:
		macd, macd_avg, macd_histogram = get_macd(pricehistory, short_period=48, long_period=104, signal_period=36)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_macd(): ' + str(e))
		return False

	# Calculate vwap and/or vwap_exit
	if ( with_vwap == True or vwap_exit == True or no_use_resistance == False ):
		vwap_vals = OrderedDict()
		days = OrderedDict()

		# Create a dict containing all the days and timestamps for which we need vwap data
		prev_day = ''
		prev_timestamp = ''
		for key in pricehistory['candles']:

			day = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
			if day not in days:
				days[day] = { 'start': key['datetime'], 'end': '', 'timestamps': [] }
				if ( prev_day != '' ):
					days[prev_day]['end'] = prev_timestamp

			prev_day = day
			prev_timestamp = key['datetime']
			days[day]['timestamps'].append(key['datetime'])

		days[day]['end'] = prev_timestamp

		# Calculate the VWAP data for each day in days{}
		for key in days:
			try:
				vwap, vwap_up, vwap_down = get_vwap(pricehistory, day=key, end_timestamp=days[key]['end'], num_stddev=2)

			except Exception as e:
				print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_vwap(): ' + str(e), file=sys.stderr)
				return False

			if ( len(vwap) != len(days[key]['timestamps']) ):
				print('WARNING: len(vwap) != len(days[key][timestamps]): ' + str(len(vwap)) + ', ' + str(len(days[key]['timestamps'])))

			for idx,val in enumerate(vwap):
				vwap_vals.update( { days[key]['timestamps'][idx]: {
							'vwap': float(val),
							'vwap_up': float(vwap_up[idx]),
							'vwap_down': float(vwap_down[idx]) }
						} )

	# VPT - Volume Price Trend
	vpt = []
	vpt_sma = []
	try:
		vpt, vpt_sma = get_vpt(pricehistory, period=vpt_sma_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_vpt(): ' + str(e))
		return False

	# Resistance / Support
	if ( no_use_resistance == False ):

		price_resistance_pct = price_resistance_pct
		price_support_pct = price_support_pct

		# Day stats
		pdc = OrderedDict()
		for key in pricehistory['candles']:

			today = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone)
			time = today.strftime('%H:%M')

			yesterday = today - timedelta(days=1)
			yesterday = fix_timestamp(yesterday)

			today = today.strftime('%Y-%m-%d')
			yesterday = yesterday.strftime('%Y-%m-%d')

			if ( today not in pdc ):
				pdc[today] = {  'open':		0,
						'high':		0,
						'low':		100000,
						'close':	0,
						'pdc':		0 }

			if ( yesterday in pdc ):
				pdc[today]['pdc'] = float(pdc[yesterday]['close'])

			if ( float(key['close']) > pdc[today]['high'] ):
				pdc[today]['high'] = float(key['close'])

			if ( float(key['close']) < pdc[today]['low'] ):
				pdc[today]['low'] = float(key['close'])

			if ( time == '09:30'):
				pdc[today]['open'] = float(key['open'])

			elif ( time == '16:00'):
				pdc[today]['close'] = float(key['close'])

		# Key levels
		if ( weekly_ph == None ):

			# get_pricehistory() variables
			p_type = 'year'
			period = '2'
			f_type = 'weekly'
			freq = '1'
			weekly_ph, ep = get_pricehistory(ticker, p_type, f_type, freq, period, needExtendedHoursData=False)

		long_support, long_resistance = get_keylevels(weekly_ph, filter=False)

		# Three/Twenty week high/low
#		three_week_high = three_week_low = three_week_avg = -1
		twenty_week_high = twenty_week_low = twenty_week_avg = -1

#		try:
#			# 3-week high / low / average
#			three_week_high, three_week_low, three_week_avg = get_price_stats(ticker, days=15)
#
#		except Exception as e:
#			print('Warning: stochrsi_analyze_new(' + str(ticker) + '): get_price_stats(): ' + str(e))
#
#		try:
#			# 20-week high / low / average
#			twenty_week_high, twenty_week_low, twenty_week_avg = get_price_stats(ticker, days=100)
#
#		except Exception as e:
#			print('Warning: stochrsi_analyze_new(' + str(ticker) + '): get_price_stats(): ' + str(e))

	# Check the SMA and EMA to see if stock is bearish or bullish
	sma = {}
	ema = {}
	if ( check_ma == True ):
		import av_gobot_helper
		sma = av_gobot_helper.av_get_ma(ticker, ma_type='sma', time_period=200)
		ema = av_gobot_helper.av_get_ma(ticker, ma_type='ema', time_period=50)


	# Run through the RSI values and log the results
	results				= []

	rsi_idx				= len(pricehistory['candles']) - len(rsi_k)
	r_idx				= len(pricehistory['candles']) - len(rsi)

	mfi_idx				= len(pricehistory['candles']) - len(mfi)
	mfi_2x_idx			= len(pricehistory['candles']) - len(mfi_2x)

	adx_idx				= len(pricehistory['candles']) - len(adx)
	di_idx				= len(pricehistory['candles']) - len(plus_di)

	aroonosc_idx			= len(pricehistory['candles']) - len(aroonosc)
	aroonosc_92_idx			= len(pricehistory['candles']) - len(aroonosc_92)
	macd_idx			= len(pricehistory['candles']) - len(macd)

	buy_signal			= False
	sell_signal			= False
	short_signal			= False
	buy_to_cover_signal		= False

	final_buy_signal		= False
	final_sell_signal		= False
	final_short_signal		= False
	final_buy_to_cover_signal	= False

	exit_percent_signal		= False

	rsi_signal			= False
	adx_signal			= False
	dmi_signal			= False
	macd_signal			= False
	aroonosc_signal			= False
	vwap_signal			= False
	vpt_signal			= False
	mfi_signal			= False
	resistance_signal		= False

	plus_di_crossover		= False
	minus_di_crossover		= False
	macd_crossover			= False
	macd_avg_crossover		= False

	orig_incr_threshold		= incr_threshold
	orig_decr_threshold		= decr_threshold
	orig_exit_percent		= exit_percent

	first_day			= datetime.fromtimestamp(float(pricehistory['candles'][0]['datetime'])/1000, tz=mytimezone)
	start_day			= first_day + timedelta( days=1 )
	start_day_epoch			= int( start_day.timestamp() * 1000 )

	last_hour_threshold		= 0.2 # Last hour trading threshold

	signal_mode = 'buy'
	if ( shortonly == True ):
		signal_mode = 'short'

	# Main loop
	for idx,key in enumerate(pricehistory['candles']):

		# Skip the first day of data
		if ( float(pricehistory['candles'][idx]['datetime']) < start_day_epoch ):
			continue

		try:
			assert idx - rsi_idx >= 1
			assert idx - mfi_idx >= 1
			assert idx - adx_idx >= 0
			assert idx - di_idx >= 1
			assert idx - macd_idx >= 1
			assert idx - aroonosc_idx >= 0

		except:
			continue

		# Indicators current values
		cur_rsi_k = rsi_k[idx - rsi_idx]
		prev_rsi_k = rsi_k[(idx - rsi_idx) - 1]

		cur_rsi_d = rsi_d[idx - rsi_idx]
		prev_rsi_d = rsi_d[(idx - rsi_idx) - 1]

		cur_r = rsi[idx - r_idx]

		cur_mfi = mfi[idx - mfi_idx]
		prev_mfi = mfi[(idx - mfi_idx) - 1]
		cur_mfi_2x = mfi_2x[idx - mfi_2x_idx]
		prev_mfi_2x = mfi_2x[(idx - mfi_2x_idx) - 1]

		# Additional indicators
		cur_adx = adx[idx - adx_idx]
		cur_plus_di = plus_di[idx - di_idx]
		prev_plus_di = plus_di[(idx - di_idx) - 1]
		cur_minus_di = minus_di[idx - di_idx]
		prev_minus_di = minus_di[(idx - di_idx) - 1]

		cur_macd = macd[idx - macd_idx]
		prev_macd = macd[(idx - macd_idx) - 1]

		cur_macd_avg = macd_avg[idx - macd_idx]
		prev_macd_avg = macd_avg[(idx - macd_idx) - 1]

		cur_aroonosc = aroonosc[idx - aroonosc_idx]
		cur_aroonosc_92 = aroonosc_92[idx - aroonosc_92_idx]

		cur_vpt = vpt[idx]
		prev_vpt = vpt[idx-1]

		cur_vpt_sma = vpt_sma[idx - vpt_sma_period]
		prev_vpt_sma = vpt_sma[idx - vpt_sma_period]

		cur_atr = atr[int(idx / 5) - atr_period]
		cur_natr = natr[int(idx / 5) - atr_period]

		# Ignore pre-post market since we cannot trade during those hours
		# Also skip all candles until start_date if it is set
		date = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone)
		if ( ismarketopen_US(date, safe_open=safe_open) != True ):
			continue
		elif ( start_date != None and date < start_date ):
			continue

		# Check SMA/EMA to see if stock is bullish or bearish
		if ( check_ma == True ):
			cur_day = date.strftime('%Y-%m-%d')

			try:
				cur_sma = sma['moving_avg'][cur_day]
				cur_ema = ema['moving_avg'][cur_day]

			except Exception as e:
				cur_sma = 0
				cur_ema = 0

			if ( cur_sma <= cur_ema ):
				# Stock is bullish, disable shorting for now
				noshort = True
				if ( signal_mode == 'short' ):
					signal_mode = 'buy'

			elif ( cur_sma > cur_ema ):
				# Stock is bearish, allow shorting
				noshort = False


		# BUY mode
		if ( signal_mode == 'buy' ):
			short = False

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and isendofday(60, date) ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				final_sell_signal = final_buy_signal = False

				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				continue

			# Jump to short mode if StochRSI K and D are already above rsi_high_limit
			# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit and noshort == False ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				final_sell_signal = final_buy_signal = False

				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				signal_mode = 'short'
				continue

			# Check StochRSI
			if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit ):

				# Monitor if K and D intersect
				# A buy signal occurs when an increasing %K line crosses above the %D line in the oversold region.
				#  or if the %K line crosses below the rsi limit
				if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
					buy_signal = True

			elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
				if ( cur_rsi_k >= rsi_low_limit ):
					buy_signal = True

			elif ( cur_rsi_k > rsi_signal_cancel_low_limit and cur_rsi_d > rsi_signal_cancel_low_limit ):
				adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False
				buy_signal = False


			# Secondary Indicators
			# RSI signal
			rsi_signal = False
			if ( cur_r < 25 ):
				rsi_signal = True

			# ADX signal
			adx_signal = False
			if ( cur_adx >= adx_threshold ):
				adx_signal = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
				plus_di_crossover = True
				minus_di_crossover = False
			elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
				plus_di_crossover = False
				minus_di_crossover = True

			dmi_signal = False
			if ( cur_plus_di > cur_minus_di ):
				if ( with_dmi_simple == True ):
					dmi_signal = True
				elif ( plus_di_crossover == True ):
					dmi_signal = True

			# Aroon oscillator signals
			# Values closer to 100 indicate an uptrend
			#
			# SAZ - 2021-08-29: Higher volatility stocks seem to work better with a longer
			# Aroon Oscillator period value.
			aroonosc_signal = False
			if ( cur_natr > 0.24 ):
				cur_aroonosc = cur_aroonosc_92

			if ( cur_aroonosc > 60 ):
				aroonosc_signal = True

				if ( aroonosc_with_vpt == True ):
					if ( cur_aroonosc <= aroonosc_secondary_threshold ):
						with_vpt = True
					else:
						with_vpt = False

				# Enable macd_simple if the aroon oscillator is less than aroonosc_secondary_threshold
				if ( aroonosc_with_macd_simple == True ):
					with_macd_simple = False
					if ( cur_aroonosc <= aroonosc_secondary_threshold ):
						with_macd_simple = True

			# MFI signal
			if ( prev_mfi > mfi_low_limit and cur_mfi < mfi_low_limit ):
				mfi_signal = False
			elif ( prev_mfi < mfi_low_limit and cur_mfi >= mfi_low_limit ):
				mfi_signal = True

			# MACD crossover signals
			if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
				macd_crossover = True
				macd_avg_crossover = False
			elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
				macd_crossover = False
				macd_avg_crossover = True

			macd_signal = False
			if ( cur_macd > cur_macd_avg and cur_macd - cur_macd_avg > macd_offset ):
				if ( with_macd_simple == True ):
					macd_signal = True
				elif ( macd_crossover == True ):
					macd_signal = True

			# VWAP
			# This is the most simple/pessimistic approach right now
			if ( with_vwap == True ):
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_price = float(pricehistory['candles'][idx]['close'])

				vwap_signal = False
				if ( cur_price < cur_vwap ):
					vwap_signal = True

			# VPT
			# Buy signal - VPT crosses above vpt_sma
			if ( prev_vpt < prev_vpt_sma and cur_vpt > cur_vpt_sma ):
				vpt_signal = True

			# Cancel signal if VPT crosses back over
			elif ( cur_vpt < cur_vpt_sma ):
				vpt_signal = False

			# Resistance
			if ( no_use_resistance == False ):

				resistance_signal = True

				# PDC
				today = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
				prev_day_close = 0
				if ( today in pdc ):
					prev_day_close = pdc[today]['pdc']

				if ( prev_day_close != 0 ):

					cur_price = float(pricehistory['candles'][idx]['close'])
					if ( abs((prev_day_close / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to PDC
						# Next check average of last 15 (minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was below PDC then PDC is resistance
						# If average was above PDC then PDC is support
						if ( avg < prev_day_close ):
							resistance_signal = False

				# VWAP
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_price = float(pricehistory['candles'][idx]['close'])
				if ( abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

					# Current price is very close to VWAP
					# Next check average of last 15 (1-minute) candles
					avg = 0
					for i in range(15, 0, -1):
						avg += float( pricehistory['candles'][idx-i]['close'] )
					avg = avg / 15

					# If average was below VWAP then VWAP is resistance
					# If average was above VWAP then VWAP is support
					if ( avg < cur_vwap ):
						resistance_signal = False

				# Key Levels
				# Check if price is near historic key level
				cur_price = float(pricehistory['candles'][idx]['close'])
				near_keylevel = False
				for lvl in long_support + long_resistance:
					if ( abs((lvl / cur_price - 1) * 100) <= price_support_pct ):
						near_keylevel = True

						# Current price is very close to a key level
						# Next check average of last 15 (1-minute) candles
						#
						# If last 15 candles average above key level, then key level is support
						# otherwise it is resistance
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was below key level then key level is resistance
						# Therefore this is not a great buy
						if ( avg < lvl ):
							resistance_signal = False
							break

				# If keylevel_strict is True then only buy the stock if price is near a key level
				# Otherwise reject this buy to avoid getting chopped around between levels
				if ( keylevel_strict == True and near_keylevel == False ):
					resistance_signal = False

				# End Key Levels


				# 20-week high
#				purchase_price = float(pricehistory['candles'][idx]['close'])
#				if ( purchase_price >= twenty_week_high ):
#					# This is not a good bet
#					twenty_week_high = float(purchase_price)
#					resistance_signal = False
#
#				elif ( ( abs(float(purchase_price) / float(twenty_week_high) - 1) * 100 ) < price_resistance_pct ):
#					# Current high is within price_resistance_pct of 20-week high, not a good bet
#					resistance_signal = False

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( buy_signal == True ):
				final_buy_signal = True
				if ( with_rsi == True and rsi_signal != True ):
					final_buy_signal = False

				if ( with_mfi == True and mfi_signal != True ):
					final_buy_signal = False

				if ( with_adx == True and adx_signal != True ):
					final_buy_signal = False

				if ( (with_dmi == True or with_dmi_simple == True) and dmi_signal != True ):
					final_buy_signal = False

				if ( with_aroonosc == True and aroonosc_signal != True ):
					final_buy_signal = False

				if ( (with_macd == True or with_macd_simple == True) and macd_signal != True ):
					final_buy_signal = False

				if ( with_vwap == True and vwap_signal != True ):
					final_buy_signal = False

				if ( with_vpt == True and vpt_signal != True ):
					final_buy_signal = False

				if ( no_use_resistance == False and resistance_signal != True ):
					final_buy_signal = False

			# BUY SIGNAL
			if ( buy_signal == True and final_buy_signal == True ):
				purchase_price = float(pricehistory['candles'][idx]['close'])
				base_price = purchase_price
				purchase_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(purchase_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(purchase_time) )

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(purchase_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
					print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) + ' signal: ' + str(dmi_signal))
					print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
					print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
					print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))
					print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
					print('(' + str(ticker) + '): BUY signal: ' + str(buy_signal) + ', Final BUY signal: ' + str(final_buy_signal))
				# DEBUG

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				final_sell_signal = final_buy_signal = False
				exit_percent_signal = False

				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				signal_mode = 'sell'

				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( variable_exit == True ):
					if ( cur_natr < incr_threshold ):

						# The normalized ATR is below incr_threshold. This means the stock is less
						#  likely to get to incr_threshold from our purchase price, and is probably
						#  even farther away from exit_percent (if it is set). So we adjust these parameters
						#  to increase the likelihood of a successful trade.
						#
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( incr_threshold > cur_natr * 2 ):
							incr_threshold = cur_natr * 2
						else:
							incr_threshold = cur_natr

						if ( decr_threshold > cur_natr * 2 ):
							decr_threshold = cur_natr * 2

						if ( exit_percent != None ):
							if ( exit_percent > cur_natr * 4 ):
								exit_percent = cur_natr * 2

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG


		# SELL mode
		if ( signal_mode == 'sell' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and isendofday(5, date) ):
				sell_signal = True

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( isendofday(60, date) == True and hold_overnight == False ):
				last_price = float( pricehistory['candles'][idx]['close'] )
				if ( last_price > purchase_price ):
					percent_change = abs( purchase_price / last_price - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						sell_signal = True

			# Monitor cost basis
			last_price = float(pricehistory['candles'][idx]['close'])
			percent_change = 0
			if ( float(last_price) < float(base_price) ):
				percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

				# SELL the security if we are using a trailing stoploss
				if ( percent_change >= decr_threshold and stoploss == True ):

					# Sell
					sell_price = float(pricehistory['candles'][idx]['close'])
					sell_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

					# sell_price,bool(short),rsi,stochrsi,sell_time
					results.append( str(sell_price) + ',' + str(short) + ',' +
							str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
							str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(sell_time) )

					buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
					final_buy_signal = final_sell_signal = final_short_signal = final_buy_to_cover_signal = False
					exit_percent_signal = False

					rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
					plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

					purchase_price	= 0
					base_price	= 0
					incr_threshold	= orig_incr_threshold
					decr_threshold	= orig_decr_threshold
					exit_percent	= orig_exit_percent

					signal_mode = 'short'
					continue

			elif ( float(last_price) > float(base_price) ):
				percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100
				if ( percent_change >= incr_threshold ):
					base_price = last_price
					decr_threshold = incr_threshold / 2

			# End cost basis / stoploss monitor

			# Additional exit strategies
			# Sell if exit_percent is specified
			if ( exit_percent != None and float(last_price) > float(purchase_price) ):
				total_percent_change = abs( float(purchase_price) / float(last_price) - 1 ) * 100

				# If exit_percent has been hit, we will sell at the first RED candle
				#  unless --quick_exit was set.
				if ( exit_percent_signal == True ):
					if ( float(pricehistory['candles'][idx]['close']) < float(pricehistory['candles'][idx]['open']) ):
						sell_signal = True

				elif ( total_percent_change >= exit_percent ):
					exit_percent_signal = True
					if ( quick_exit == True ):
						sell_signal = True

			# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
			if ( vwap_exit == True ):
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_vwap_up = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap_up']
				if ( cur_vwap > purchase_price ):
					if ( last_price >= ((cur_vwap - purchase_price) / 2) + purchase_price ):
						sell_signal = True

				elif ( cur_vwap < purchase_price ):
					if ( last_price >= ((cur_vwap_up - cur_vwap) / 2) + cur_vwap ):
						sell_signal = True


			# Monitor RSI for SELL signal
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( strict_exit_percent == False and exit_percent_signal == False ):
				if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit ):

					# Monitor if K and D intercect
					# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region
					if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
						sell_signal = True

				elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
					if ( cur_rsi_k <= rsi_high_limit ):
						sell_signal = True

			if ( sell_signal == True ):

				# Sell
				sell_price = float(pricehistory['candles'][idx]['close'])
				sell_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				# sell_price,bool(short),rsi,stochrsi,sell_time
				results.append( str(sell_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(sell_time) )

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				final_buy_signal = final_sell_signal = final_short_signal = final_buy_to_cover_signal = False
				exit_percent_signal = False

				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				purchase_price	= 0
				base_price	= 0
				incr_threshold	= orig_incr_threshold
				decr_threshold	= orig_decr_threshold
				exit_percent	= orig_exit_percent

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
				final_buy_signal = final_sell_signal = final_short_signal = final_buy_to_cover_signal = False

				adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				continue

			# Jump to buy mode if StochRSI K and D are already below rsi_low_limit
			if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit ):
				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				final_buy_signal = final_sell_signal = final_short_signal = final_buy_to_cover_signal = False

				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				signal_mode = 'buy'
				continue

			# Monitor RSI
			if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit ):

				# Monitor if K and D intercect
				# A sell-short signal occurs when a decreasing %K line crosses below the %D line in the overbought region
				if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
					short_signal = True

			elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
				if ( cur_rsi_k <= rsi_high_limit ):
					short_signal = True

			elif ( cur_rsi_k < rsi_signal_cancel_high_limit and cur_rsi_d < rsi_signal_cancel_high_limit ):
				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False
				short_signal = False


			# Secondary Indicators
			# RSI signal
			rsi_signal = False
			if ( cur_r > 75 ):
				rsi_signal = True

			# ADX signal
			adx_signal = False
			if ( cur_adx > adx_threshold ):
				adx_signal = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
				plus_di_crossover = True
				minus_di_crossover = False
			elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
				plus_di_crossover = False
				minus_di_crossover = True

			dmi_signal = False
			if ( cur_plus_di < cur_minus_di ):
				if ( with_dmi_simple == True ):
					dmi_signal = True
				elif ( minus_di_crossover == True ):
					dmi_signal = True

			# Aroon oscillator signals
			# Values closer to -100 indicate a downtrend
			aroonosc_signal = False
			if ( cur_natr > 0.24 ):
				cur_aroonosc = cur_aroonosc_92

			if ( cur_aroonosc < -60 ):
				aroonosc_signal = True

				# Enable macd_simple if the aroon oscillitor is greater than -aroonosc_secondary_threshold
				if ( aroonosc_with_macd_simple == True ):
					with_macd_simple = False
					if ( cur_aroonosc >= -aroonosc_secondary_threshold ):
						with_macd_simple = True

			# MFI signal
			if ( prev_mfi < mfi_high_limit and cur_mfi > mfi_high_limit ):
				mfi_signal = False
			elif ( prev_mfi > mfi_high_limit and cur_mfi <= mfi_high_limit ):
				mfi_signal = True

			# MACD crossover signals
			if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
				macd_crossover = True
				macd_avg_crossover = False
			elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
				macd_crossover = False
				macd_avg_crossover = True

			macd_signal = False
			if ( cur_macd < cur_macd_avg and cur_macd_avg - cur_macd > macd_offset ):
				if ( with_macd_simple == True ):
					macd_signal = True
				elif ( macd_avg_crossover == True ):
					macd_signal = True

			# VWAP
			# This is the most simple/pessimistic approach right now
			if ( with_vwap == True ):
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_price = float(pricehistory['candles'][idx]['close'])
				if ( cur_price > cur_vwap ):
					vwap_signal = True

			# VPT
			if ( with_vpt == True ):
				# Short signal - VPT crosses below vpt_sma
				if ( prev_vpt > prev_vpt_sma and cur_vpt < cur_vpt_sma ):
					vpt_signal = True

				# Cancel signal if VPT cross back over
				elif ( cur_vpt > cur_vpt_sma ):
					vpt_signal = False

			# Resistance
			if ( no_use_resistance == False ):

				resistance_signal = True

				# PDC
				today = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
				prev_day_close = 0
				if ( today in pdc ):
					prev_day_close = pdc[today]['pdc']

				if ( prev_day_close != 0 ):

					cur_price = float(pricehistory['candles'][idx]['close'])
					if ( abs((prev_day_close / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to PDC
						# Next check average of last 15 (minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was below PDC then PDC is resistance (good for short)
						# If average was above PDC then PDC is support (bad for short)
						if ( avg > prev_day_close ):
							resistance_signal = False

				# VWAP
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_price = float(pricehistory['candles'][idx]['close'])
				if ( abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

					# Current price is very close to VWAP
					# Next check average of last 15 (1-minute) candles
					avg = 0
					for i in range(15, 0, -1):
						avg += float( pricehistory['candles'][idx-i]['close'] )
					avg = avg / 15

					# If average was below VWAP then VWAP is resistance (good for short)
					# If average was above VWAP then VWAP is support (bad for short)
					if ( avg > cur_vwap ):
						resistance_signal = False

				# Key Levels
				# Check if price is near historic key level
				cur_price = float(pricehistory['candles'][idx]['close'])
				near_keylevel = False
				for lvl in long_support + long_resistance:
					if ( abs((lvl / cur_price - 1) * 100) <= price_resistance_pct ):
						near_keylevel = True

						# Current price is very close to a key level
						# Next check average of last 15 (1-minute) candles
						#
						# If last 15 candles average below key level, then key level is resistance
						# otherwise it is support
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was above key level then key level is support
						# Therefore this is not a good short
						if ( avg > lvl ):
							resistance_signal = False
							break

				# If keylevel_strict is True then only short the stock if price is near a key level
				# Otherwise reject this short altogether to avoid getting chopped around between levels
				if ( keylevel_strict == True and near_keylevel == False ):
					resistance_signal = False

				# End Key Levels

				# High / low resistance
#				short_price = float(pricehistory['candles'][idx]['close'])
#				if ( float(short_price) <= float(twenty_week_low) ):
#					# This is not a good bet
#					twenty_week_low = float(short_price)
#					resistance_signal = False
#
#				elif ( ( abs(float(twenty_week_low) / float(short_price) - 1) * 100 ) < price_support_pct ):
#					# Current low is within price_support_pct of 20-week low, not a good bet
#					resistance_signal = False

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( short_signal == True ):
				final_short_signal = True
				if ( with_rsi == True and rsi_signal != True ):
					final_short_signal = False

				if ( with_mfi == True and mfi_signal != True ):
					final_short_signal = False

				if ( with_adx == True and adx_signal != True ):
					final_short_signal = False

				if ( (with_dmi == True or with_dmi_simple == True) and dmi_signal != True ):
					final_short_signal = False

				if ( with_aroonosc == True and aroonosc_signal != True ):
					final_short_signal = False

				if ( (with_macd == True or with_macd_simple == True) and macd_signal != True ):
					final_short_signal = False

				if ( with_vwap == True and vwap_signal != True ):
					final_short_signal = False

				if ( with_vpt == True and vpt_signal != True ):
					final_short_signal = False

				if ( no_use_resistance == False and resistance_signal != True ):
					final_short_signal = False

			# SHORT SIGNAL
			if ( short_signal == True and final_short_signal == True ):
				short_price = float(pricehistory['candles'][idx]['close'])
				base_price = short_price
				short_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(short_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(short_time) )

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(short_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
					print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) + ' signal: ' + str(dmi_signal))
					print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
					print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
					print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))
					print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
					print('(' + str(ticker) + '): SHORT signal: ' + str(short_signal) + ', Final SHORT signal: ' + str(final_short_signal))
				# DEBUG

				sell_signal = buy_signal = short_signal = buy_to_cover_signal = False
				final_buy_signal = final_sell_signal = final_short_signal = final_buy_to_cover_signal = False
				exit_percent_signal = False

				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				signal_mode = 'buy_to_cover'

				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( variable_exit == True ):
					if ( cur_natr < incr_threshold ):

						# The normalized ATR is below incr_threshold. This means the stock is less
						#  likely to get to incr_threshold from our purchase price, and is probably
						#  even farther away from exit_percent (if it is set). So we adjust these parameters
						#  to increase the likelihood of a successful trade.
						#
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( incr_threshold > cur_natr * 2 ):
							incr_threshold = cur_natr * 2
						else:
							incr_threshold = cur_natr

						if ( decr_threshold > cur_natr * 2 ):
							decr_threshold = cur_natr * 2

						if ( exit_percent != None ):
							if ( exit_percent > cur_natr * 4 ):
								exit_percent = cur_natr * 2

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG


		# BUY-TO-COVER mode
		if ( signal_mode == 'buy_to_cover' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and isendofday(5, date) ):
				buy_to_cover_signal = True

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( isendofday(60, date) == True and hold_overnight == False ):
				last_price = float( pricehistory['candles'][idx]['close'] )
				if ( last_price < short_price ):
					percent_change = abs( short_price / last_price - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						sell_signal = True

			# Monitor cost basis
			last_price = float(pricehistory['candles'][idx]['close'])
			percent_change = 0
			if ( float(last_price) > float(base_price) ):
				percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

				# Buy-to-cover the security if we are using a trailing stoploss
				if ( percent_change >= decr_threshold and stoploss == True ):

					# Buy-to-cover
					buy_to_cover_price = float(pricehistory['candles'][idx]['close'])
					buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

					results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
							str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
							str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(buy_to_cover_time) )

					buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
					final_buy_signal = final_sell_signal = final_short_signal = final_buy_to_cover_signal = False
					exit_percent_signal = False

					rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
					plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

					short_price	= 0
					base_price	= 0
					incr_threshold	= orig_incr_threshold
					decr_threshold	= orig_decr_threshold
					exit_percent	= orig_exit_percent

					if ( shortonly == True ):
						signal_mode = 'short'
					else:
						signal_mode = 'buy'
						continue

			elif ( float(last_price) < float(base_price) ):
				percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100
				if ( percent_change >= incr_threshold ):
					base_price = last_price
					decr_threshold = incr_threshold / 2

			# End cost basis / stoploss monitor


			# Additional exit strategies
			# Sell if exit_percent is specified
			if ( exit_percent != None and float(last_price) < float(short_price) ):

				total_percent_change = abs( float(last_price) / float(short_price) - 1 ) * 100

				# If exit_percent has been hit, we will sell at the first GREEN candle
				#  unless quick_exit was set.
				if ( exit_percent_signal == True ):
					if ( float(pricehistory['candles'][idx]['close']) > float(pricehistory['candles'][idx]['open']) ):
						buy_to_cover_signal = True

				elif ( total_percent_change >= float(exit_percent) ):
					exit_percent_signal = True
					if ( quick_exit == True ):
						buy_to_cover_signal = True

			# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
			if ( vwap_exit == True ):

				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_vwap_down = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap_down']
				if ( cur_vwap < short_price ):
					if ( last_price <= ((short_price - cur_vwap) / 2) + cur_vwap ):
						buy_to_cover_signal = True

				elif ( cur_vwap > short_price ):
					if ( last_price <= ((cur_vwap - cur_vwap_down) / 2) + cur_vwap_down ):
						buy_to_cover_signal = True


			# Monitor RSI for BUY_TO_COVER signal
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( strict_exit_percent == False and exit_percent_signal == False ):
				if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit ):

					# Monitor if K and D intercect
					# A buy-to-cover signal occurs when an increasing %K line crosses above the %D line in the oversold region.
					if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
						buy_to_cover_signal = True

				elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
					if ( cur_rsi_k >= rsi_low_limit ):
						buy_to_cover_signal = True

			# BUY-TO-COVER
			if ( buy_to_cover_signal == True ):

				buy_to_cover_price = float(pricehistory['candles'][idx]['close'])
				buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(buy_to_cover_time) )

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				final_buy_signal = final_sell_signal = final_short_signal = final_buy_to_cover_signal = False
				exit_percent_signal = False

				rsi_signal = mfi_signal = adx_signal = dmi_signal = aroonosc_signal = macd_signal = vwap_signal = vpt_signal = resistance_signal = False
				plus_di_crossover = minus_di_crossover = macd_crossover = macd_avg_crossover = False

				short_price	= 0
				base_price	= 0
				incr_threshold	= orig_incr_threshold
				decr_threshold	= orig_decr_threshold
				exit_percent	= orig_exit_percent

				if ( shortonly == True ):
					signal_mode = 'short'
				else:
					buy_signal = True
					signal_mode = 'buy'
					continue

	# End main loop

	return results
