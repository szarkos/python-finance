#!/usr/bin/python3 -u

import os, sys, re, time
from datetime import datetime, timedelta
from pytz import timezone

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

	# Early close (1PM) days
	early_close = [	'2021-07-02',
			'2021-11-26',
			'2021-12-23',

			# 2022
			'2022-07-01',
			'2022-11-25',
			'2022-12-23',

			# 2023
			'2023-07-03',
			'2023-11-24',
			'2023-12-22',

			# 2024
			'2024-07-03',
			'2024-11-29',
			'2024-12-24' ]

	mins = 60 - int(mins)

	# Check early close holidays (1:00PM Eastern)
	if ( est_time.strftime('%Y-%m-%d') ) in early_close:
		if ( int(est_time.strftime('%-H')) == 12 and int(est_time.strftime('%-M')) >= mins ):
			return True

	elif ( int(est_time.strftime('%-H')) == 15 and int(est_time.strftime('%-M')) >= mins ):
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
#  The safe_open option does not return True until 45-minutes after standard market hours open
#  to avoid volatility.
# Extended hours for TDA are 2.5 hours before and after standard market hours
#  Note: safe_open does not apply to extended hours
def ismarketopen_US(date=None, safe_open=False, check_day_only=False, extended_hours=False ):
	eastern = timezone('US/Eastern') # Observes EST and EDT

	if ( date == None ):
		est_time = datetime.now(eastern)
	elif ( type(date) is datetime ):
		est_time = date.replace(tzinfo=eastern)
	else:
		print('Error: ismarketopen_US(): date must be a datetime object')
		return False

	# US market holidays - source: https://www.marketbeat.com/stock-market-holidays/
	# TDA API doesn't provide this, so I'm hardcoding these dates for now.
	# Holidays:
	#   New Year's Day
	#   Martin Luther King Jr. Day
	#   President's Day
	#   Good Friday
	#   Memorial Day
	#   Early Close (1:00PM Eastern)
	#   Independence Day
	#   Labor Day
	#   Thanksgiving
	#   Early Close (1:00PM Eastern)
	#   Early Close (1:00PM Eastern)
	#   Christmas Eve
	holidays = [	'2021-01-01',
			'2021-01-18',
			'2021-02-15',
			'2021-04-02',
			'2021-05-31',
			'2021-07-05',
			'2021-09-06',
			'2021-11-25',
			'2021-12-24',

			# 2022
			'2022-01-17',
			'2022-02-21',
			'2022-04-15',
			'2022-05-30',
			'2022-07-04',
			'2022-09-05',
			'2022-11-24',
			'2022-12-26',

			# 2023
			'2023-01-02',
			'2023-01-16',
			'2023-02-20',
			'2023-04-07',
			'2023-05-29',
			'2023-07-04',
			'2023-09-04',
			'2023-11-23',
			'2023-12-25',

			# 2024
			'2024-01-01',
			'2024-01-15',
			'2024-02-19',
			'2024-03-29',
			'2024-05-27',
			'2024-07-04',
			'2024-09-02',
			'2024-11-28',
			'2024-12-25' ]

	early_close = [	'2021-07-02',
			'2021-11-26',
			'2021-12-23',

			# 2022
			'2022-07-01',
			'2022-11-25',
			'2022-12-23',

			# 2023
			'2023-07-03',
			'2023-11-24',
			'2023-12-22',

			# 2024
			'2024-07-03',
			'2024-11-29',
			'2024-12-24' ]

	# Return false if it's a holiday
	if ( est_time.strftime('%Y-%m-%d') ) in holidays:
		return False
	if ( int(est_time.strftime('%w')) == 0 or int(est_time.strftime('%w')) == 6 ): # 0=Sunday, 6=Saturday
		return False
	if ( check_day_only == True ):
		return True

	if ( int(est_time.strftime('%w')) != 0 and int(est_time.strftime('%w')) != 6 ): # 0=Sunday, 6=Saturday

		# Extended market hours (07:00-18:30 Eastern)
		if ( extended_hours == True ):
			if ( int(est_time.strftime('%-H')) >= 7 ):
				if ( int(est_time.strftime('%-H')) < 18 ):
					return True

				elif ( int(est_time.strftime('%-H')) == 18 and int(est_time.strftime('%-M')) <= 30 ):
					return True

		# Standard market hours (09:30-16:00 Eastern)
		else:
			if ( int(est_time.strftime('%-H')) >= 9 ):
				if ( int(est_time.strftime('%-H')) == 9 ):

					# Do not return True until after 10AM EST to avoid some of the volatility of the open
					if ( isinstance(safe_open, bool) and safe_open == True ):
						return False

					if ( int(est_time.strftime('%-M')) >= 30 ):
						return True
					else:
						return False

				elif ( int(est_time.strftime('%-H')) == 10 ):

					# Do not return True until after 10:15AM to void some of the volatility of the open
					if ( isinstance(safe_open, bool) and safe_open == True ):
						if ( int(est_time.strftime('%-M')) >= 15 ):
							return True
						else:
							return False

				# Check early close holidays (1:00PM Eastern)
				if ( est_time.strftime('%Y-%m-%d') ) in early_close:
					if ( int(est_time.strftime('%-H')) <= 12 and int(est_time.strftime('%-M')) <= 59 ):
						return True

				# Otherwise consider 3:59 Eastern to be closing time
				elif ( int(est_time.strftime('%-H')) <= 15 and int(est_time.strftime('%-M')) <= 59 ):
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
# Or if permaban_only=True, then only returns True for permanently blacklisted stocks
def check_blacklist(ticker=None, permaban_only=False, debug=False):
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

			# Return True of the stock was permanently banned
			if ( time_stamp == '9999999999' ):
				return True

			if ( permaban_only == True ):
				return False

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
					data,err = func_timeout(5, tda.stocks.get_quotes, args=(str(query), True))

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
				data,err = func_timeout(5, tda.stocks.get_quotes, args=(str(stock), True))

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

	# Get a quote for a single stock ticker
	else:
		try:
			data,err = func_timeout(5, tda.stocks.get_quote, args=(str(stock), True))

		except FunctionTimedOut:
			print('Caught Exception: get_quotes(' + str(stock) + '): tda.stocks.get_quote(): timed out after 10 seconds', file=sys.stderr)
			return False
		except Exception as e:
			print('Caught Exception: get_quotes(' + str(stock) + '): tda.stocks.get_quote(): ' + str(e), file=sys.stderr)
			return False

		if ( err != None ):
			print('Error: get_quotes(' + str(stock) + '): tda.stocks.get_quote(): ' + str(err), file=sys.stderr)
			return False
		elif ( data == {} ):
			print('Error: get_quotes(' + str(stock) + '): tda.stocks.get_quote(): Empty data set', file=sys.stderr)
			return False

		return data

	return False


# Fix the timestamp for get_pricehistory()
# TDA API is very picky and may reject requests with timestamps that are
#  outside normal or extended hours
def fix_timestamp(date=None, check_day_only=False, debug=False):

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
	elif ( day == 1 and ismarketopen_US(date=date, check_day_only=check_day_only) == False ):
		# It's Monday, but market is closed (i.e. Labor Day),
		#  move timestamp back to previous Friday
		date = date - timedelta( days=3 )
	elif ( day == 4 and ismarketopen_US(date=date, check_day_only=check_day_only) == False ):
		# Thanksgiving
		date = date - timedelta( days=2 )
	elif ( day == 5 and ismarketopen_US(date=date, check_day_only=check_day_only) == False ):
		# Good Friday
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
			if key['datetime'] not in dup:
				dup[key['datetime']] = 1
			else:
				dup[key['datetime']] += 1

	if ( len( dup.items() ) > 0 ):
		print("\nWARNING: get_pricehistory(" + str(ticker) + "): DUPLICATE TIMESTAMPS DETECTED\n", file=sys.stderr)
		return False, []

	return data, epochs


# Translate 1-minute candles to 2+ minute candles
# Default translates to 5-minute candles
def translate_1m(pricehistory=None, candle_type=5):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: translate_1m(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	new_pricehistory = { 'candles': [], 'ticker': ticker }
	for idx,key in enumerate(pricehistory['candles']):
		if ( idx == 0 ):
			continue

		cndl_num = idx + 1
		if ( cndl_num % candle_type == 0 ):
			open_p  = float( pricehistory['candles'][idx - (candle_type-1)]['open'] )
			close   = float( pricehistory['candles'][idx]['close'] )
			high    = float( pricehistory['candles'][idx]['high'] )
			low     = float( pricehistory['candles'][idx]['low'] )
			volume  = int( pricehistory['candles'][idx]['close'] )

			for i in range((candle_type-1), 0, -1):
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

			new_pricehistory['candles'].append(newcandle)

	return new_pricehistory


# Translate candle data to Heikin Ashi
def translate_heikin_ashi(pricehistory=None):

	ticker = ''
	try:
		ticker = pricehistory['symbol']
	except:
		pass

	if ( pricehistory == None ):
		print('Error: translate_heikin_ashi(' + str(ticker) + '): pricehistory is empty', file=sys.stderr)
		return False

	# Heikin Ashi candles formula
	#  haOpen = [haOpen(Previous Bar) + haClose(Previous Bar)]/2
	#  haClose = (open+high+low+close)/4
	#  haLow = Min(low, haOpen, haClose)
	#  haHigh = Max(high, haOpen, haClose)
	hacandles = []
	for idx,key in enumerate(pricehistory['candles']):
		key['open']	= float( key['open'] )
		key['high']	= float( key['high'] )
		key['low']	= float( key['low'] )
		key['close']	= float( key['close'] )
		key['volume']	= int( key['volume'] )
		key['datetime']	= int( key['datetime'] )

		if ( idx == 0 ):
			ha_open = key['open']
		else:
			ha_open = ( hacandles[idx-1]['open'] + hacandles[idx-1]['close'] ) / 2

		ha_close	= ( key['open'] + key['high'] + key['low'] + key['close'] ) / 4
		ha_high		= max( key['high'], ha_open, ha_close )
		ha_low		= min( key['low'], ha_open, ha_close )

		if ( ha_close > 1 ):
			ha_open		= round( ha_open, 2 )
			ha_high		= round( ha_high, 2 )
			ha_low		= round( ha_low, 2 )
			ha_close	= round( ha_close, 2 )

		hacandles.append ( {	'open':		ha_open,
					'high':		ha_high,
					'low':		ha_low,
					'close':	ha_close,
					'volume':	key['volume'],
					'datetime':	key['datetime'] } )

	pricehistory.update({ 'hacandles': hacandles })

	return pricehistory


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


# Return information about a previously placed TDA order
def get_order(order_id=None, account_number=None, passcode=None, debug=False):

	if ( order_id == None or passcode == None ):
		return False

	if ( account_number == None ):
		try:
			account_number = int( tda_account_number )
		except:
			print('Error: get_order(' + str(order_id) + '): invalid account number: ' + str(account_number), file=sys.stderr)
			return False
	else:
		try:
			account_number = int( account_number )
		except:
			print('Error: get_order(' + str(order_id) + '): account number must be an integer: ' + str(account_number), file=sys.stderr)
			return False

	# Make sure we are logged into TDA
	try:
		if ( tdalogin(passcode) != True ):
			print('Error: get_order(' + str(order_id) + '): tdalogin(): login failure', file=sys.stderr)

	except Exception as e:
		print('Error: get_order(' + str(order_id) + '): tdalogin(): ' + str(e), file=sys.stderr)

	# Get order information to determine if it was filled
	data	= None
	err	= None
	try:
		data, err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
		if ( debug == True ):
			print( data )

	except Exception as e:
		print('Caught Exception: get_order(' + str(order_id) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: get_order(' + str(order_id) + '): tda.get_order(): ' + str(err), file=sys.stderr)
		return False

	return data


# Cancel a previously placed TDA order
def cancel_order(order_id=None, account_number=None, passcode=None, debug=False):

	if ( order_id == None or passcode == None ):
		return False

	if ( account_number == None ):
		try:
			account_number = int( tda_account_number )
		except:
			print('Error: cancel_order(' + str(order_id) + '): invalid account number: ' + str(account_number), file=sys.stderr)
			return False
	else:
		try:
			account_number = int( account_number )
		except:
			print('Error: cancel_order(' + str(order_id) + '): account number must be an integer: ' + str(account_number), file=sys.stderr)
			return False

	# Make sure we are logged into TDA
	try:
		if ( tdalogin(passcode) != True ):
			print('Error: cancel_order(' + str(order_id) + '): tdalogin(): login failure', file=sys.stderr)

	except Exception as e:
		print('Error: cancel_order(' + str(order_id) + '): tdalogin(): ' + str(e), file=sys.stderr)

	# Get order information to determine if it was filled
	data	= None
	err	= None
	try:
		data, err = func_timeout(5, tda.cancel_order, args=(account_number, order_id, True))
		if ( debug == True ):
			print( data )

	except Exception as e:
		print('Caught Exception: cancel_order(' + str(order_id) + '): tda.cancel_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: cancel_order(' + str(order_id) + '): tda.cancel_order(): ' + str(err), file=sys.stderr)
		return False

	return data


# Purchase a stock at Market price
#  Ticker = stock ticker
#  Quantity = amount of stock to purchase
#  fillwait = (boolean) wait for order to be filled before returning
#
# Notes:
#  - Global object "tda" needs to exist, and tdalogin() should be called first.
def buy_stock_marketprice(ticker=None, quantity=None, fillwait=True, account_number=None, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	if ( account_number == None ):
		try:
			account_number = int( tda_account_number )
		except:
			print('Error: buy_stock_marketprice(' + str(ticker) + '): invalid account number: ' + str(account_number), file=sys.stderr)
			return False
	else:
		try:
			account_number = int( account_number )
		except:
			print('Error: buy_stock_marketprice(' + str(ticker) + '): account number must be an integer: ' + str(account_number), file=sys.stderr)
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
			data, err = func_timeout(5, tda.place_order, args=(account_number, order, True))
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
		tdalogin(passcode)
		data,err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
		if ( debug == True ):
			print(data)

	except Exception as e:
		print('Caught Exception: buy_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: buy_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(err), file=sys.stderr)

	print('buy_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
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
def sell_stock_marketprice(ticker=None, quantity=None, fillwait=True, account_number=None, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	if ( account_number == None ):
		try:
			account_number = int( tda_account_number )
		except:
			print('Error: sell_stock_marketprice(' + str(ticker) + '): invalid account number: ' + str(account_number), file=sys.stderr)
			return False
	else:
		try:
			account_number = int( account_number )
		except:
			print('Error: sell_stock_marketprice(' + str(ticker) + '): account number must be an integer: ' + str(account_number), file=sys.stderr)
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
			data, err = func_timeout(5, tda.place_order, args=(account_number, order, True))
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
		tdalogin(passcode)
		data, err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
		if ( debug == True ):
			print(data)

	except Exception as e:
		print('Caught Exception: sell_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: sell_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(err), file=sys.stderr)

	print('sell_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
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
def short_stock_marketprice(ticker=None, quantity=None, fillwait=True, account_number=None, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	if ( account_number == None ):
		try:
			account_number = int( tda_account_number )
		except:
			print('Error: short_stock_marketprice(' + str(ticker) + '): invalid account number: ' + str(account_number), file=sys.stderr)
			return False
	else:
		try:
			account_number = int( account_number )
		except:
			print('Error: short_stock_marketprice(' + str(ticker) + '): account number must be an integer: ' + str(account_number), file=sys.stderr)
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
			data, err = func_timeout(5, tda.place_order, args=(account_number, order, True))
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
		tdalogin(passcode)
		data, err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
		if ( debug == True ):
			print(data)

	except Exception as e:
		print('Caught Exception: short_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(err), file=sys.stderr)

	# Check if we were unable to short this stock
	if ( data['status'] == 'AWAITING_MANUAL_REVIEW' or data['status'] == 'REJECTED' ):
		print('Error: short_stock_marketprice(' + str(ticker) + '): tda.get_order(): returned status indicates that stock is not available for shorting', file=sys.stderr)
		return False

	print('short_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and float(data['filledQuantity']) != float(quantity) ):
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
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
def buytocover_stock_marketprice(ticker=None, quantity=None, fillwait=True, account_number=None, debug=False):

	if ( ticker == None or quantity == None ):
		return False

	if ( account_number == None ):
		try:
			account_number = int( tda_account_number )
		except:
			print('Error: buytocover_stock_marketprice(' + str(ticker) + '): invalid account number: ' + str(account_number), file=sys.stderr)
			return False
	else:
		try:
			account_number = int( account_number )
		except:
			print('Error: buytocover_stock_marketprice(' + str(ticker) + '): account number must be an integer: ' + str(account_number), file=sys.stderr)
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
			data, err = func_timeout(5, tda.place_order, args=(account_number, order, True))
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
		tdalogin(passcode)
		data, err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
		if ( debug == True ):
			print(data)

	except Exception as e:
		print('Caught Exception: buytocover_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(e))
		return data

	if ( err != None ):
		print('Error: buytocover_stock_marketprice(' + str(ticker) + '): tda.get_order(): ' + str(err), file=sys.stderr)

	print('buytocover_stock_marketprice(' + str(ticker) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
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


# Buy/Close(sell) call or put options
# Required options:
#  - contract: option contract ticker name
#  - quantity: number of option contracts to buy/sell
#  - instruction: 'buy' or 'buy_to_open' / 'sell' or 'sell_to_close'
def buy_sell_option(contract=None, quantity=None, limit_price=None, instruction=None, fillwait=True, account_number=None, debug=False):

	try:
		assert contract		!= None
		assert quantity		!= None
		assert instruction	!= None
		instruction		= str(instruction).upper()

	except Exception as e:
		print('Caught exception: buy_sell_option(' + str(contract) + '): ' + str(e), file=sys.stderr)
		return False

	if ( account_number == None ):
		try:
			account_number = int( tda_account_number )
		except:
			print('Error: buy_sell_option(' + str(contract) + '): invalid account number: ' + str(account_number), file=sys.stderr)
			return False
	else:
		try:
			account_number = int( account_number )
		except:
			print('Error: buy_sell_option(' + str(contract) + '): account number must be an integer: ' + str(account_number), file=sys.stderr)
			return False

	contract	= str(contract).upper()
	num_attempts	= 3 # Number of attempts to sell the stock in case of failure

	order = {
		"complexOrderStrategyType": "NONE",
		"orderType": "MARKET",
		"session": "NORMAL",
		"duration": "DAY",
		"orderStrategyType": "SINGLE",
		"orderLegCollection": [ {
			"instruction": "",
			"quantity": quantity,
			"instrument": {
				"symbol": contract,
				"assetType": "OPTION"
			}
		} ]
	}

	# Either buy or close options
	if ( instruction == 'BUY' or instruction == 'BUY_TO_OPEN' ):
		order['orderLegCollection'][0]['instruction'] = 'BUY_TO_OPEN'

	elif ( instruction == 'SELL' or instruction == 'SELL_TO_CLOSE' ):
		order['orderLegCollection'][0]['instruction'] = 'SELL_TO_CLOSE'

	else:
		print('Error: buy_sell_option(' + str(contract) + '): invalid instruction: ' + str(instruction), file=sys.stderr)
		return False

	# Switch to limit order if limit_price is set
	if ( limit_price != None ):
		try:
			limit_price = float( limit_price )
		except:
			print('Error: buy_sell_option(' + str(contract) + '): invalid limit_price: ' + str(limit_price), file=sys.stderr)
			return False
		else:
			order['orderType']	= 'LIMIT'
			order['price']		= limit_price


	# Make sure we are logged into TDA
	if ( tdalogin(passcode) != True ):
		print('Error: buy_sell_option(' + str(contract) + '): tdalogin(): login failure', file=sys.stderr)

	# Try to buy/sell the option num_attempts tries or return False
	for attempt in range(num_attempts):
		try:
			data, err = func_timeout(5, tda.place_order, args=(account_number, order, True))
			if ( debug == True ):
				print('DEBUG: buy_sell_option(): tda.place_order(' + str(contract) + '): attempt ' + str(attempt+1))
				print(order)
				print(data)
				print(err)

		except FunctionTimedOut:
			print('Caught Exception: buy_sell_option(' + str(contract) + '): tda.place_order(): timed out after 5 seconds')
			err = 'Timed Out'

		except Exception as e:
			print('Caught Exception: buy_sell_option(' + str(contract) + '): tda.place_order(): ' + str(e))
			return False

		if ( err != None ):
			print('Error: buy_sell_option(' + str(contract) + '): tda.place_order(): attempt ' + str(attempt+1) + ',  ' + str(err), file=sys.stderr)
			if ( attempt == num_attempts-1 ):
				return False

			# Try to log in again
			if ( tdalogin(passcode) != True ):
				print('Error: buy_sell_option(): tdalogin(): Login failure', file=sys.stderr)

			time.sleep(2)
		else:
			break

	# Get the order number to feed to tda.get_order
	try:
		order_id = func_timeout(5, tda.get_order_number, args=(data,))
		if ( debug == True ):
			print(order_id)

	except Exception as e:
		print('Caught Exception: buy_sell_option(' + str(contract) + '): tda.get_order_number(): ' + str(e))
		return None

	if ( str(order_id) == '' ):
		print('Error: buy_sell_option('+ str(contract) + '): tda.get_order_number(): Unable to get order ID', file=sys.stderr)
		return None

	# Get order information to determine if it was filled
	try:
		tdalogin(passcode)
		data, err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
		if ( debug == True ):
			print(data)

	except Exception as e:
		print('Caught Exception: buy_sell_option(' + str(contract) + '): tda.get_order(): ' + str(e))
		return order_id

	if ( err != None ):
		print('Error: buy_sell_option(' + str(contract) + '): tda.get_order(): ' + str(err), file=sys.stderr)

	print('buy_sell_option(' + str(contract) + '): Order successfully placed (Order ID:' + str(order_id) + ')')

	# Loop and wait for order to be filled if fillwait==True
	if ( fillwait == True and data['filledQuantity'] != quantity ):
		while time.sleep(5):
			try:
				data,err = func_timeout(5, tda.get_order, args=(account_number, order_id, True))
				if ( debug == True ):
					print(data)

			except Exception as e:
				print('Caught Exception: buy_sell_option(' + str(contract) + '): tda.get_order() in fillwait loop: ' + str(e))

			if ( err != None ):
				print('Error: buy_sell_option(' + str(contract) + '): problem in fillwait loop: ' + str(err), file=sys.stderr)
				continue
			if ( data['filledQuantity'] == quantity ):
				break

		print('buy_sell_option(' + str(contract) + '): Order completed (Order ID:' + str(order_id) + ')')

	return order_id


# Get option chain information
#
# - contract_type (Optional[str]) – Type of contracts to return in the chain. Can be CALL, PUT, or ALL. Default is ALL.
# - strike_count (Optional[str]) – The number of strikes to return above and below the at-the-money price.
# - include_quotes (Optional[str]) – Include quotes for options in the option chain. Can be TRUE or FALSE. Default is FALSE.
# - strategy (Optional[str]) – Passing a value returns a Strategy Chain. Possible values are SINGLE, ANALYTICAL (allows use of
#   the volatility, underlyingPrice, interestRate, and daysToExpiration params to calculate theoretical values),
#   COVERED, VERTICAL, CALENDAR, STRANGLE, STRADDLE, BUTTERFLY, CONDOR, DIAGONAL, COLLAR, or ROLL. Default is SINGLE.
# - interval (Optional[str]) – Strike interval for spread strategy chains (see strategy param).
# - strike_price (Optional[str]) – Provide a strike price to return options only at that strike price.
# - range_value
#	ITM: In-the-money
#	NTM: Near-the-money
#	OTM: Out-of-the-money
#	SAK: Strikes Above Market
#	SBK: Strikes Below Market
#	SNK: Strikes Near Market
#	ALL: All Strikes (DEFAULT)
# - from_date (Optional[str]) – Only return expirations after this date. For strategies, expiration refers
#   to the nearest term expiration in the strategy. Valid ISO-8601 formats are: yyyy-MM-dd and yyyy-MM-dd’T’HH:mm:ssz.
# - to_date (Optional[str]) – Only return expirations before this date. For strategies, expiration refers to the nearest
#   term expiration in the strategy. Valid ISO-8601 formats are: yyyy-MM-dd and yyyy-MM-dd’T’HH:mm:ssz.
# - volatility (Optional[str]) – Volatility to use in calculations. Applies only to ANALYTICAL strategy chains (see strategy param).
# - underlying_price (Optional[str]) – Underlying price to use in calculations. Applies only to ANALYTICAL strategy chains (see strategy param).
# - interest_rate (Optional[str]) – Interest rate to use in calculations. Applies only to ANALYTICAL strategy chains (see strategy param).
# - days_to_expiration (Optional[str]) – Days to expiration to use in calculations. Applies only to ANALYTICAL strategy chains (see strategy param).
# - exp_month (Optional[str]) – Return only options expiring in the specified month. Month is given in the three character format.
#   Example: JAN. Default is ALL.
# - option_type (Optional[str]) – Type of contracts to return. Default is ALL. Possible values are:
#	S: Standard contracts
#	NS: Non-standard contracts
#	ALL: All contracts (DEFAULT)
# - jsonify (Optional[str]) – If set to False, will return the raw response object. If set to True, will return a dictionary parsed using the JSON format.
def get_option_chains(ticker=None, contract_type='ALL', strike_count='10', include_quotes='FALSE', strategy='SINGLE', interval=None,
			strike_price=None, range_value='ALL', from_date=None, to_date=None, volatility=None, underlying_price=None,
			interest_rate=None, days_to_expiration=None, exp_month='ALL', option_type='ALL', jsonify=True ):

	if ( ticker == None ):
		print('Error: get_option_chains(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		all_args = {	'contract_type':	contract_type,
				'strike_count':		strike_count,
				'include_quotes':	include_quotes,
				'strategy':		strategy,
				'interval':		interval,
        	                'strike_price':		strike_price,
				'range_value':		range_value,
				'from_date':		from_date,
				'to_date':		to_date,
				'volatility':		volatility,
				'underlying_price':	underlying_price,
        	                'interest_rate':	interest_rate,
				'days_to_expiration':	days_to_expiration,
				'exp_month':		exp_month,
				'option_type':		option_type,
				'jsonify':		jsonify }

		data, err = func_timeout(5, tda.stocks.get_option_chains, args=(ticker,), kwargs=all_args )

	except FunctionTimedOut:
		print('Caught Exception: get_option_chains(' + str(ticker) + '): tda.stocks.get_option_chains(): timed out after 10 seconds', file=sys.stderr)
		return False
	except Exception as e:
		print('Caught Exception: get_option_chains(' + str(ticker) + '): tda.stocks.get_option_chains(): ' + str(e), file=sys.stderr)
		return False

	if ( err != None ):
		print('Error: get_option_chains(' + str(ticker) + '): tda.stocks.get_option_chains(): ' + str(err), file=sys.stderr)
		return False
	elif ( data == {} ):
		print('Error: get_option_chains(' + str(ticker) + '): tda.stocks.get_option_chains(): Empty data set', file=sys.stderr)
		return False

	return data


