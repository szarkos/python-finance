#!/usr/bin/python3 -u

# Helper functions for Alpha Vantage API
# https://www.alphavantage.co/documentation/

import os, sys
import datetime, pytz

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


# Return intraday candles - 1min, 5min, 15min, 30min or 60min intervals
# interval = 1min, 5min, 15min, 30min, 60min
# slice = year1month1, year1month2, year1month3, ..., year1month11, year1month12, year2month1, year2month2, year2month3, ..., year2month11, year2month12
# adjusted = True|False
def av_get_intraday_pricehistory(ticker=None, interval='1min', slice='year1month1', adjusted=False, debug=False):

	import requests

	if ( ticker == None ):
		print('Error: av_get_pricehistory(' + str(ticker) + '): ticker is empty', file=sys.stderr)
		return False

	try:
		av_api_key
	except:
		print('Error: av_get_pricehistory(): API key not defined.')
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

