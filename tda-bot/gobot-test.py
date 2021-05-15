#!/usr/bin/python3 -u

import sys
import argparse
import datetime, pytz
import pickle
import re

from subprocess import Popen, PIPE, STDOUT

parser = argparse.ArgumentParser()
parser.add_argument("--ifile", help='Pickle file to read', required=True, type=str)
parser.add_argument("--ofile", help='File to output results', required=True, type=str)
parser.add_argument("--all", help='File to output results', action="store_true")
args = parser.parse_args()

mytimezone = pytz.timezone("US/Eastern")

try:
	with open(args.ifile, 'rb') as handle:
		pricehistory = handle.read()
		pricehistory = pickle.loads(pricehistory)

except Exception as e:
	print('Error opening file ' + str(args.ifile) + ': ' + str(e))
	exit(1)

# Sanity check the data
prev_time = 0
for key in pricehistory['candles']:
	time = int( key['datetime'] )
	if ( prev_time != 0 ):
		if ( time < prev_time ):
			print('(' + str(ticker) + '): Error: timestamps out of order!')
			exit(-1)

	prev_time = time

try:
	ticker = pricehistory['symbol']

except:
	print('Error: pricehistory does not contain ticker symbol')
	exit(-1)

# Test Scenarios
scenarios = {   'stochrsi_rsi':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi',
		'stochrsi_rsi_adx':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx',
		'stochrsi_rsi_dmi':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_dmi',
		'stochrsi_rsi_macd':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_macd',
		'stochrsi_rsi_aroonosc':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_aroonosc',
		'adx':				'--with_adx',

		'stochrsi_rsi_adx_dmi':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi',
		'stochrsi_rsi_adx_macd':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd',
		'stochrsi_rsi_adx_aroonosc':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_aroonosc',

		'stochrsi_rsi_adx_dmi_macd':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi --with_macd',
		'stochrsi_rsi_adx_dmi_aroonosc':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi --with_aroonosc',
		'stochrsi_rsi_adx_macd_aroonosc':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd --with_aroonosc',

		'stochrsi_rsi_adx_macd_dmi_aroonosc':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd --with_dmi --with_aroonosc'
}

start_date = ''
if ( args.all == False ):
	yesterday = datetime.datetime.now(mytimezone) - datetime.timedelta(days=1)
	yesterday = yesterday.strftime('%Y-%m-%d')

	start_date = ' --start_date=' + str(yesterday)

# Run the data through all available test scenarios
for key in scenarios:

	command = './tda-gobot-analyze.py ' + str(ticker) + ' --algo=stochrsi-new --no_use_resistance --stoploss --incr_threshold=0.5 --decr_threshold=1 --verbose ' + '--ifile=' + str(args.ifile) + str(start_date) + ' ' + str(scenarios[key])
	outfile = str(args.ofile) + '-' + str(key)

	try:
		process = Popen( command, stdin=None, stdout=PIPE, stderr=STDOUT, shell=True )
		output, err = process.communicate()

	except Exception as e:
		print('Error: unable to open file ' + str(args.ifile) + ': ' + str(e))
		exit(1)

	try:
		file = open(outfile, "wb")
		file.write(output)
		file.close()

	except Exception as e:
		print('Unable to write to file ' + str(args.ofile) + ': ' + str(e))


sys.exit(0)
