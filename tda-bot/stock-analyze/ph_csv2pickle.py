#!/usr/bin/python3 -u

# Parse the monthly data from alphavantage, format it as a
#  TDA dict, and output data as a pickle data file.
# https://www.alphavantage.co/documentation/#intraday-extended

import sys
import argparse
import datetime
import pytz

import pickle
import re

parser = argparse.ArgumentParser()
parser.add_argument("ifile", help='CSV file to read', type=str)
parser.add_argument("ofile", help='Pickle file to write (default is ifile with .pickle extension', nargs='?', default=None, type=str)
args = parser.parse_args()

mytimezone = pytz.timezone("US/Eastern")

ticker = re.sub('^.*\/', '', args.ifile)
ticker = re.sub('\-.*$', '', ticker)

pricehistory = {'candles':	[],
		'symbol':	str(ticker),
		'empty':	'False'
}

try:

	with open(args.ifile, 'r') as handle:
		for line in handle:
			line = re.sub('[\r\n]*', '', line)

			# Log format:
			# time,open,high,low,close,volume
			# 2021-03-12 19:51:00,31.44,31.45,31.44,31.45,350
			time,open,high,low,close,volume = line.split(',')

			if ( time == 'time' ):
				continue

			time = int( datetime.datetime.strptime(time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=mytimezone).timestamp() * 1000 )
			candle_data = { 'open':		open,
					'high':		high,
					'low':		low,
					'close':	close,
					'volume':	volume,
					'datetime':	time }

			pricehistory['candles'].append(candle_data)

	handle.close()
	del time,open,high,low,close,volume

except Exception as e:
	print('Error opening file ' + str(args.ifile) + ': ' + str(e))
	sys.exit(1)

# Sanity check that candle entries are properly ordered
prev_time = 0
for key in pricehistory['candles']:
	time = int( key['datetime'] )
	if ( prev_time != 0 ):
		if ( time < prev_time ):
			print('(' + str(ticker) + '): Error: timestamps out of order!')

	prev_time = time

if ( args.ofile == None ):
	args.ofile = re.sub('\.csv', '', args.ifile)
	args.ofile = str(args.ofile) + '.pickle'

try:
	file = open(args.ofile, "wb")
	pickle.dump(pricehistory, file)
	file.close()

except Exception as e:
	print('Unable to write to file ' + str(args.ofile) + ': ' + str(e))


sys.exit(0)
