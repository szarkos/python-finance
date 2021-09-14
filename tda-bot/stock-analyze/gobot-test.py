#!/usr/bin/python3 -u

import sys
import argparse
import datetime, pytz
import pickle
import re

from subprocess import Popen, PIPE, STDOUT

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--ifile", help='Pickle file to read', type=str)
group.add_argument("--print_scenarios", help='Just print the test scenarios and exit (for other scripts that are parsing the results)', action="store_true")

parser.add_argument("--ofile", help='File to output results', type=str, default=None)
parser.add_argument("--all", help='File to output results', action="store_true")
parser.add_argument("--opts", help='Add any additional options for tda-gobot-analyze', default=None, type=str)
parser.add_argument("--debug", help='Enable debug output', action="store_true")

args = parser.parse_args()

mytimezone = pytz.timezone("US/Eastern")


# Test Scenarios
scenarios = {
		'stochrsi_aroonosc_simple_dmi_simple_with_macd_lodhod':		'--rsi_high_limit=95 --rsi_low_limit=15 --variable_exit --lod_hod_check --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 ',
		'stochrsi_mfi_aroonosc_simple_dmi_simple_with_macd_lodhod':	'--rsi_high_limit=95 --rsi_low_limit=15 --variable_exit --lod_hod_check --with_mfi --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 ',
		'stochrsi_mfi_rsi_adx':						'--rsi_high_limit=95 --rsi_low_limit=15 --variable_exit --lod_hod_check --with_mfi --mfi_high_limit=95 --mfi_low_limit=5 --with_rsi --with_adx --adx_threshold=20 ',
}

#scenarios = {	'stochrsi_dmi_simple':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_dmi_simple',
#		'stochrsi_aroonosc_dmi_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_dmi_simple --with_aroonosc'
#}

#scenarios = {	'stochrsi':				'--rsi_high_limit=95 --rsi_low_limit=5',
#		'stochrsi_rsi':				'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi',
#
#		'stochrsi_macd':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_macd',
#		'stochrsi_rsi_macd':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_macd',
#
#		'stochrsi_macd_dmi_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_macd --with_dmi_simple',
#		'stochrsi_rsi_macd_dmi_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_macd --with_dmi_simple',
#
#		'stochrsi_adx_macd':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_macd',
#		'stochrsi_adx_dmi_macd':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_dmi --with_macd',
#		'stochrsi_rsi_adx_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_vpt',
#		'stochrsi_rsi_macd_vpt':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_macd --with_vpt',
#		'stochrsi_adx_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_vpt',
#		'stochrsi_adx_vpt_macd_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_vpt --with_macd_simple',
#		'stochrsi_macd_vpt_dmi_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_macd --with_vpt --with_dmi_simple',
#		'stochrsi_dmi_vpt_macd_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_dmi --with_vpt --with_macd_simple',
#		'stochrsi_rsi_adx_macd':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd',
#		'stochrsi_adx_dmi':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_dmi',
#}

#scenarios = {
#		'stochrsi_rsi_adx_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_vpt',
#		'stochrsi_rsi_adx_vpt_macd_simple':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_vpt --with_macd_simple',
#		'stochrsi_rsi_adx_vpt_dmi_simple':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_vpt --with_dmi_simple',
#
#		'stochrsi_rsi_macd_vpt':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_macd --with_vpt',
#		'stochrsi_rsi_macd_vpt_dmi_simple':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_macd --with_vpt --with_dmi_simple',
#
#		'stochrsi_rsi_dmi_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_dmi --with_vpt',
#		'stochrsi_rsi_dmi_vpt_macd_simple':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_dmi --with_vpt --with_macd_simple',
#
#		'stochrsi_adx_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_vpt',
#		'stochrsi_adx_vpt_dmi_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_vpt --with_dmi_simple',
#		'stochrsi_adx_vpt_macd_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_vpt --with_macd_simple',
#
#		'stochrsi_macd_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_macd --with_vpt',
#		'stochrsi_macd_vpt_dmi_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_macd --with_vpt --with_dmi_simple',
#
#		'stochrsi_dmi_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_dmi --with_vpt',
#		'stochrsi_dmi_vpt_macd_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_dmi --with_vpt --with_macd_simple',
#
#		'stochrsi_rsi_adx_dmi':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi',
#		'stochrsi_rsi_adx_dmi_macd_simple':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi --with_macd_simple',
#
#		'stochrsi_rsi_adx_macd':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd',
#		'stochrsi_rsi_adx_macd_dmi_simple':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd --with_dmi_simple',
#
#		'stochrsi_adx_dmi':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_dmi',
#		'stochrsi_adx_dmi_macd_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_dmi --with_macd_simple',
#
#		'stochrsi_adx_macd':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_macd',
#		'stochrsi_adx_macd_dmi_simple':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_macd --with_dmi_simple'
#}

#scenarios = {   'stochrsi_rsi_vpt':				'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_vpt',
#		'stochrsi_rsi_adx_vpt':				'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_vpt',
#		'stochrsi_rsi_dmi_vpt':				'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_dmi --with_vpt',
#		'stochrsi_rsi_macd_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_macd --with_vpt',
#		'stochrsi_rsi_aroonosc_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_aroonosc --with_vpt',
#
#		'stochrsi_rsi_adx_dmi_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi --with_vpt',
#		'stochrsi_rsi_adx_macd_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd --with_vpt',
#		'stochrsi_rsi_adx_aroonosc_vpt':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_aroonosc --with_vpt',
#
#		'stochrsi_vpt':					'--rsi_high_limit=95 --rsi_low_limit=5 --with_vpt',
#		'stochrsi_adx_vpt':				'--rsi_high_limit=95 --rsi_low_limit=5 --with_adx --with_vpt',
#		'stochrsi_dmi_vpt':				'--rsi_high_limit=95 --rsi_low_limit=5 --with_dmi --with_vpt',
#		'stochrsi_macd_vpt':				'--rsi_high_limit=95 --rsi_low_limit=5 --with_macd --with_vpt',
#		'stochrsi_aroonosc_vpt':			'--rsi_high_limit=95 --rsi_low_limit=5 --with_aroonosc --with_vpt',
#
#		'stochrsi_rsi_adx_dmi_macd_vpt':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi --with_macd --with_vpt',
#		'stochrsi_rsi_adx_dmi_aroonosc_vpt':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_dmi --with_aroonosc --with_vpt',
#		'stochrsi_rsi_adx_macd_aroonosc_vpt':		'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd --with_aroonosc --with_vpt',
#		'stochrsi_rsi_adx_macd_dmi_aroonosc_vpt':	'--rsi_high_limit=95 --rsi_low_limit=5 --with_rsi --with_adx --with_macd --with_dmi --with_aroonosc --with_vpt'
#}

if (args.print_scenarios == True ):
	for key in scenarios:
		print(key, end=' ')
	print()
	exit(0)


try:
	with open(args.ifile, 'rb') as handle:
		pricehistory = handle.read()
		pricehistory = pickle.loads(pricehistory)

except Exception as e:
	print('Error opening file ' + str(args.ifile) + ': ' + str(e))
	exit(1)


start_date = ''
if ( args.all == False ):
	yesterday = datetime.datetime.now(mytimezone) - datetime.timedelta(days=1)
	if ( int(yesterday.strftime('%w')) == 0 ): # Sunday
		yesterday = yesterday - datetime.timedelta(days=2)
	elif ( int(yesterday.strftime('%w')) == 6 ): # Saturday
		yesterday = yesterday - datetime.timedelta(days=1)

	last_candle = int(pricehistory['candles'][-1]['datetime']) / 1000
	start_timestamp = int( yesterday.timestamp() )
	if ( last_candle < start_timestamp ):
		print('Error: timestamp on the last candle (' + str(last_candle) + ') is before start_time (' + str(start_timestamp) + ')')
		exit(-1)

	start_date = ' --start_date=' + str(yesterday)

# Sanity check the data
# Check order of timestamps
prev_time = 0
for key in pricehistory['candles']:
	time = int( key['datetime'] )
	if ( prev_time != 0 ):
		if ( time < prev_time ):
			print('(' + str(ticker) + '): Error: timestamps out of order!')
			exit(-1)

	prev_time = time

# Check if pricehistory['symbol'] is set
try:
	ticker = pricehistory['symbol']

except:
	print('Error: pricehistory does not contain ticker symbol')
	exit(-1)

# Additional arguments to tda-gobot-analyze
opts = ''
if ( args.opts != None ):
	opts = args.opts


# Run the data through all available test scenarios
for key in scenarios:

#	command = './tda-gobot-analyze.py ' + str(ticker) + ' --algo=stochrsi-new --no_use_resistance --stoploss --incr_threshold=0.5 --decr_threshold=0.4 --verbose ' + \
	command = './tda-gobot-analyze.py ' + str(ticker) + ' --algo=stochrsi-new --stoploss --skip_check --incr_threshold=0.5 --decr_threshold=0.4 --exit_percent=1 --verbose --stock_usd=5000 ' + \
			str(opts) + ' --ifile=' + str(args.ifile) + ' ' + str(start_date) + ' ' + str(scenarios[key])

	outfile = str(args.ofile) + '-' + str(key)

	if ( args.debug == True ):
		print('Command: ' + str(command))

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
