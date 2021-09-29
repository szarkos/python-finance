#!/usr/bin/python3 -u

import os, sys, re, time

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
	if ( mins < 0 ):
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

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# We're assuming the blacklist file will be in the same path as tda_gobot_helper
	parent_path = os.path.dirname( os.path.realpath(__file__) )
	blacklist = str(parent_path) + '/.stock-blacklist'
	try:
		fh = open( blacklist, "at" )

	except OSError as e:
		print('Error: write_blacklist(): Unable to open file ' + str(blacklist) + ': ' + str(e), file=sys.stderr)
		return False

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
# Returns True if ticker is in the file and time_stamp is < 32 days ago
def check_blacklist(ticker=None, debug=False):
	if ( ticker == None ):
		print('Error: check_blacklist(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# We're assuming the blacklist file will be in the same path as tda_gobot_helper
	parent_path = os.path.dirname( os.path.realpath(__file__) )
	blacklist = str(parent_path) + '/.stock-blacklist'
	if ( os.path.exists(blacklist) == False ):
		if ( debug == True ):
			print('WARNING: check_blacklist(): File ' + str(blacklist) + ' does not exist', file=sys.stderr)

		return True

	try:
		fh = open( blacklist, "rt" )

	except OSError as e:
		print('Error: check_blacklist(): Unable to open file ' + str(blacklist) + ': ' + str(e), file=sys.stderr)
		return False

	found = False
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


# Check stock blacklist to avoid wash sales
# Returns True if ticker is in the file and time_stamp is < 32 days ago
def clean_blacklist(debug=False):

	try:
		mytimezone
	except:
		mytimezone = timezone("US/Eastern")

	# We're assuming the blacklist file will be in the same path as tda_gobot_helper
	parent_path = os.path.dirname( os.path.realpath(__file__) )
	blacklist = str(parent_path) + '/.stock-blacklist'
	if ( os.path.exists(blacklist) == False ):
		if ( debug == True ):
			print('WARNING: check_blacklist(): File ' + str(blacklist) + ' does not exist', file=sys.stderr)

		return True

	try:
		fh = open( blacklist, "rt" )

	except OSError as e:
		print('Error: check_blacklist(): Unable to open file ' + str(blacklist) + ': ' + e, file=sys.stderr)
		return False


	cur_blacklist = []
	time_now = datetime.now(mytimezone)
	for line in fh:
		line = line.rstrip()
		line = re.sub('[\r\n]', "", line)

		if ( re.match('^[\s\t]*#', line) ):
			# For now we're keeping all comments intact
			# Stale comments must be cleaned manually
			cur_blacklist.append(line)
			continue

		else:
			# Comments at the end of each line cannot be supported, strip them
			line = re.sub('[\s\t]*#.*', "", line)
			line = line.replace(" ", "")
			cur_blacklist.append(line)

	fh.close()

	# Process the blacklist, remove any stale entries
	red		= '\033[0;31m'
	green		= '\033[0;32m'
	reset_color	= '\033[0m'
	text_color	= ''

	if ( debug == True ):
		print( '{0:10} {1:15} {2:15}'.format('Ticker', 'Entry Date', 'Expiration Date') )

	for idx,line in enumerate(cur_blacklist):
		if ( re.match('^[\s\t]*#', line) or line == "" ): # Skip comments or blank lines
			continue

		try:
			stock, stock_qty, orig_base_price, last_price, net_change, percent_change, time_stamp = line.split('|', 7)

		except:
			continue

		text_color = green
		time_stamp = datetime.fromtimestamp( int(time_stamp), tz=mytimezone )
		if ( time_stamp + timedelta(days=32) > time_now ):
			# time_stamp is still less than 32 days in the past
			text_color = red

		else:
			# time_stamp is more than 32 days in the past, so we can purge it
			cur_blacklist[idx] = 'DELETED'

		if ( debug == True ):
			expiration = time_stamp + timedelta(days=32)
			print(text_color, end='')

			if ( int(expiration.strftime('%-Y')) > 2200 ):
				# This is a permanently blacklisted ticker
				print( '{0:10} {1:15} {2:15}'.format(stock, '----------', 'permanent'), end='' )
			else:
				print( '{0:10} {1:15} {2:15}'.format(stock, time_stamp.strftime('%Y-%m-%d'), expiration.strftime('%Y-%m-%d')), end='' )

			print(reset_color)


	# Print out the blacklist file with the remaining valid entries
	try:
		fh = open( blacklist, "wt" )

	except OSError as e:
		print('Error: write_blacklist(): Unable to open file ' + str(blacklist) + ': ' + str(e), file=sys.stderr)
		return False

	if ( os.name != 'nt' ):
		import fcntl
		fcntl.lockf( fh, fcntl.LOCK_EX )

	for line in cur_blacklist:
		if ( line == 'DELETED' ):
			continue

		print( line, file=fh, flush=True )

	fh.close()

	return True


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
	elif ( day == 1 and ismarketopen_US(date) == False ):
		# It Monday, but market is closed (i.e. Labor Day),
		#  move timestamp back to previous Friday
		date = date - timedelta( days=3 )

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


# Return the N-period simple moving average (SMA)
def get_sma(pricehistory=None, period=200, debug=False):

	if ( pricehistory == None ):
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Put pricehistory data into a numpy array
	prices = []
	for key in pricehistory['candles']:
		prices.append( float(key['close']) )

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
def get_ema(pricehistory=None, period=50, debug=False):

	if ( pricehistory == None ):
		return False

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	# Put pricehistory data into a numpy array
	prices = []
	for key in pricehistory['candles']:
		prices.append( float(key['close']) )

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


