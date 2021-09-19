#!/usr/bin/python3 -u

# Helper functions for Alpha Vantage API
# https://www.alphavantage.co/documentation/

import os, sys, re
import datetime, pytz
import requests

# Obtain API key for Alpha Vantage
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: av_gobot_helper: unable to load .env file')
        sys.exit(1)

try:
	av_api_key = os.environ["av_api_key"]
except:
	print('Error: av_gobot_helper: API key required. Unable to read "av_api_key" from .env file.')
	sys.exit(1)


# Return daily candles - date, daily open, daily high, daily low, daily close, daily volume
# outputsize = compact | full
def av_get_day_pricehistory(ticker=None, outputsize='compact', debug=False):

	if ( ticker == None ):
		print('Error: av_get_day_pricehistory(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		av_api_key
	except:
		print('Error: av_get_day_pricehistory(): API key not defined.')
		return False

	base_url = 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY'
	base_url = base_url + '&symbol=' + str(ticker)
	base_url = base_url + '&outputsize=' + str(outputsize)
	base_url = base_url + '&datatype=' + 'csv'
	base_url = base_url + '&apikey=' + str(av_api_key)

	try:
		data = requests.get(url=base_url)
		data.raise_for_status()

	except Exception as e:
		print('Error: av_get_intraday_pricehistory(' + str(ticker) + '): error downloading data: ' + str(e))

	data = data.content.decode()

	ph = {}
	ph['candles'] = []
	time = open = high = low = close = volume = ''
	for line in reversed( data.split('\r\n') ):
		if ( line == 'timestamp,open,high,low,close,volume' or line == '' ):
			continue

		try:
			time, open, high, low, close, volume = line.split(',', 6)

		except Exception as e:
			print('Error: av_get_day_pricehistory(' + str(ticker) + '): error parsing candle data: ' + str(e))
			return False

		ph['candles'].append( {	'open':		open,
					'high':		high,
					'low':		low,
					'close':	close,
					'volume':	volume,
					'datetime':	time } )

		ph['symbol'] = str(ticker)

	return ph


# Return intraday candles - 1min, 5min, 15min, 30min or 60min intervals
# interval = 1min, 5min, 15min, 30min, 60min
# slice = year1month1, year1month2, year1month3, ..., year1month11, year1month12, year2month1, year2month2, year2month3, ..., year2month11, year2month12
# adjusted = True|False
def av_get_intraday_pricehistory(ticker=None, interval='1min', slice='year1month1', adjusted=False, debug=False):

	if ( ticker == None ):
		print('Error: av_get_intraday_pricehistory(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		av_api_key
	except:
		print('Error: av_get_intraday_pricehistory(): API key not defined.')
		return False

	mytimezone = pytz.timezone("US/Eastern")

	base_url = 'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY_EXTENDED'
	base_url = base_url + '&symbol=' + str(ticker)
	base_url = base_url + '&interval=' + str(interval)
	base_url = base_url + '&slice=' + str(slice)
	base_url = base_url + '&adjusted=' + str(adjusted).lower()
	base_url = base_url + '&apikey=' + str(av_api_key)

	try:
		data = requests.get(url=base_url)
		data.raise_for_status()

	except Exception as e:
		print('Error: av_get_intraday_pricehistory(' + str(ticker) + '): error downloading data: ' + str(e))

	data = data.content.decode()

	ph = {}
	ph['candles'] = []
	time = open = high = low = close = volume = ''
	for line in reversed( data.split('\r\n') ):
		if ( line == 'time,open,high,low,close,volume' or line == '' ):
			continue

		try:
			time, open, high, low, close, volume = line.split(',', 6)

		except Exception as e:
			print('Error: av_get_intraday_pricehistory(' + str(ticker) + '): error parsing candle data: ' + str(e))
			return False

		time = datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
		time = mytimezone.localize(time)
		time = int( time.timestamp() * 1000 )

		ph['candles'].append( {	'open':		open,
					'high':		high,
					'low':		low,
					'close':	close,
					'volume':	volume,
					'datetime':	time } )

		ph['symbol'] = str(ticker)


	return ph


# Returns moving average (SMA or EMA) calculation
# interval = 1min, 5min, 15min, 30min, 60min, daily, weekly, monthly
# time_period = nn (default: 200)
# series_type = close, open, high, low (default: close)
def av_get_ma(ticker=None, ma_type='sma', interval='daily', time_period=200, series_type='close', debug=False):

	if ( ticker == None ):
		print('Error: av_get_ma(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		av_api_key
	except:
		print('Error: av_get_ma(): API key not defined.')
		return False

	ma_type = str(ma_type).upper()
	if ( ma_type != 'SMA' and ma_type != 'EMA' ):
		print('Error: av_get_ma(' + str(ticker) + '): ma_type "' + str(ma_type) + '" is not supported', file=sys.stderr)
		return False

	base_url = 'https://www.alphavantage.co/query?function=' + str(ma_type)
	base_url = base_url + '&symbol=' + str(ticker)
	base_url = base_url + '&interval=' + str(interval)
	base_url = base_url + '&time_period=' + str(time_period)
	base_url = base_url + '&series_type=' + str(series_type)
	base_url = base_url + '&datatype=' + 'csv'
	base_url = base_url + '&apikey=' + str(av_api_key)

	try:
		data = requests.get(url=base_url)
		data.raise_for_status()

	except Exception as e:
		print('Error: av_get_ma(' + str(ticker) + '): error downloading data: ' + str(e))

	data = data.content.decode()

	ma = {}
	ma['moving_avg'] = {}
	time = mavg = ''
	for line in reversed( data.split('\r\n') ):
		if ( line == 'time,' + ma_type or line == '' ):
			continue

		try:
			time, mavg = line.split(',', 2)

		except Exception as e:
			print('Error: av_get_ma(' + str(ticker) + '): error parsing moving average data: ' + str(e))
			return False

		time = re.sub( '\s.*$', '', time )
		ma['moving_avg'][time] = mavg

	ma['ma_type'] = str(ma_type)
	ma['symbol'] = str(ticker)

	return ma


# Get historical earnings information for a single ticker
# Use type='raw' for all the data, or type='reported' to just return a
#  list of 'reportedDate' entries from 'quarterlyEarnings'
def av_get_earnings(ticker=None, type='reported', debug=False):

	if ( ticker == None ):
		print('Error: av_get_earnings(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		av_api_key

	except:
		print('Error: av_get_earnings(): API key not defined.')
		return False

	base_url = 'https://www.alphavantage.co/query?function=EARNINGS'
	base_url = base_url + '&symbol=' + str(ticker)
	base_url = base_url + '&apikey=' + str(av_api_key)

	try:
		data = requests.get( url=base_url )
		data.raise_for_status()
		data = data.json()

	except Exception as e:
		print('Error: av_get_earnings(' + str(ticker) + '): error downloading data: ' + str(e))

	if ( debug == True ):
		print(data)

	if ( type == 'raw' ):
		return(data)

	elif ( type == 'reported' ):
		reported_dates = []
		for entry in data['quarterlyEarnings']:

			# Skip dates from before 2020
			# If for some reason anyone ever needs all the dates back to the 90s,
			#  then they can just request the raw data.
			if ( re.match('202[0-9]\-', entry['reportedDate']) != None ):
				reported_dates.append(entry['reportedDate'])

		return reported_dates

	return False


# Get future earnings calendar
# Leave ticker=None to get a full calendar for all known stock tickers.
# 'period' is in months
def av_get_earnings_calendar(ticker=None, period=3, debug=False):

	try:
		av_api_key

	except:
		print('Error: av_get_earnings_calendar(): API key not defined.')
		return False

	base_url = 'https://www.alphavantage.co/query?function=EARNINGS_CALENDAR'
	base_url = base_url + '&horizon=' + str(period) + 'month'
	base_url = base_url + '&apikey=' + str(av_api_key)

	if ( ticker != None ):
		base_url = base_url + '&symbol=' + str(ticker)

	try:
		data = requests.get(url=base_url)
		data.raise_for_status()

	except Exception as e:
		print('Error: av_get_earnings_calendar(' + str(ticker) + '): error downloading data: ' + str(e))

	data = data.content.decode()

	if ( debug == True ):
		print(data)

	# This endpoint returns only CSV data rather than json
	earnings_dates = {}
	symbol = name = report_date = fiscal_date_ending = estimate = currency = ''
	for line in data.split('\r\n'):
		if ( line == 'symbol,name,reportDate,fiscalDateEnding,estimate,currency' or line == '' ):
			continue

		try:
			symbol, name, report_date, fiscal_date_ending, estimate, currency = line.split(',', 6)

		except Exception as e:
			print('Error: av_get_earnings_calendar(' + str(ticker) + '): error parsing data: ' + str(e))
			return False

		if ( ticker == None ):
			newdate = { symbol: report_date }
			earnings_dates.update( newdate )

		else:
			if ( len(earnings_dates) == 0 ):
				earnings_dates[symbol] = []

			earnings_dates[symbol].append( report_date )


	return earnings_dates

