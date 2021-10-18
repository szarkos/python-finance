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

parser.add_argument("--scenarios", help='List of scenarios to test, comma-delimited. By default all scenarios listed in this script will be used.', type=str, default=None)
parser.add_argument("--ofile", help='File to output results', type=str, default=None)
parser.add_argument("--opts", help='Add any additional options for tda-gobot-analyze', default=None, type=str)
parser.add_argument("--debug", help='Enable debug output', action="store_true")
args = parser.parse_args()

mytimezone = pytz.timezone("US/Eastern")

# Standard options for all scenarios
std_opts = ' --algo=stochrsi-new --stoploss --skip_check --incr_threshold=0.5 --decr_threshold=0.4 --exit_percent=1 --verbose --stock_usd=5000 ' + \
		' --variable_exit --lod_hod_check --use_natr_resistance '

# Test Scenarios
scenarios = {	# Daily test, called from automation. Comment to disable the automation.
		'standard_daily_test':						'--rsi_high_limit=85 --rsi_low_limit=15 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 --stochrsi_offset=6 --daily_atr_period=3 --min_intra_natr=0.15 --min_daily_natr=1.5 --with_supertrend --supertrend_min_natr=2 --supertrend_atr_period=70',


		# Loud, not used but good baseline
		'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx':		'--rsi_high_limit=85 --rsi_low_limit=15 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 --stochrsi_offset=3 --daily_atr_period=7 --min_intra_natr=0.15 --min_daily_natr=1.5 --use_natr_resistance ',

#		'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx':		'--rsi_high_limit=95 --rsi_low_limit=15 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 ',

		# Good results but fewer trades
#		'stochrsi_mfi_aroonosc_simple_dmi_simple_with_macd_adx':	'--rsi_high_limit=95 --rsi_low_limit=15 --with_mfi --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 ',

		# Very good results but very few trades
#		'stochrsi_mfi_aroonosc_simple_adx_lowperiod':			'--rsi_high_limit=95 --rsi_low_limit=15 --with_mfi --mfi_high_limit=95 --mfi_low_limit=5 --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=20 --adx_period=48 ',

		# Similar to above without mfi, decent results (60 percentile daily win rate) but more trades
		# Currently not used, needs more testing
#		'stochrsi_aroonosc_simple_adx_lowperiod':			'--rsi_high_limit=95 --rsi_low_limit=15 --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=20 --adx_period=48 ',

		# Decent results (60 percentile)
#		'stochrsi_mfi_rsi_adx':						'--rsi_high_limit=95 --rsi_low_limit=15 --with_mfi --mfi_high_limit=95 --mfi_low_limit=5 --with_rsi --with_adx --adx_threshold=20 ',

}

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

if (args.print_scenarios == True ):
	for key in scenarios:
		print(key, end=' ')
	print()
	sys.exit(0)

# Check if --scenarios is set and includes valid test names
if ( args.scenarios != None ):
	try:
		valid_scenarios = args.scenarios.split(',')
	except Exception as e:
		print('Caught exception: ' + str(e) )
		sys.exit(1)

	for idx,s in enumerate(valid_scenarios):
		if ( s not in scenarios ):
			print('Error: scenario "' + str(s) + '" not listed in global scenarios list, ignoring.', file=sys.stderr)
			valid_scenarios[idx] = ''

	valid_scenarios = [x for x in valid_scenarios if x != '']
	if ( len(valid_scenarios) == 0 ):
		print('Error: no valid scenarios found, exiting.', file=sys.stderr)
		sys.exit(1)


# Grab OHLCV data from pickle file
try:
	with open(args.ifile, 'rb') as handle:
		pricehistory = handle.read()
		pricehistory = pickle.loads(pricehistory)

except Exception as e:
	print('Error opening file ' + str(args.ifile) + ': ' + str(e), file=sys.stderr)
	exit(1)

# Sanity check the data
# Check order of timestamps
prev_time = 0
for key in pricehistory['candles']:
	time = int( key['datetime'] )
	if ( prev_time != 0 ):
		if ( time < prev_time ):
			print('(' + str(ticker) + '): Error: timestamps out of order!', file=sys.stderr)
			exit(-1)

	prev_time = time

# Check if pricehistory['symbol'] is set
try:
	ticker = pricehistory['symbol']

except:
	print('Error: pricehistory does not contain ticker symbol', file=sys.stderr)
	exit(-1)

# Additional arguments to tda-gobot-analyze
opts = ''
if ( args.opts != None ):
	opts = args.opts

# Run the data through all available test scenarios
for key in scenarios:

	if ( args.scenarios != None and key not in valid_scenarios ):
		continue

	command = './tda-gobot-analyze.py ' + str(ticker) + ' ' + str(std_opts) + ' ' + str(opts) + ' --ifile=' + str(args.ifile) + ' ' + str(scenarios[key])
	outfile = str(args.ofile) + '-' + str(key)

	if ( args.debug == True ):
		print('Command: ' + str(command))

	try:
		process = Popen( command, stdin=None, stdout=PIPE, stderr=STDOUT, shell=True )
		output, err = process.communicate()

	except Exception as e:
		print('Error: unable to open file ' + str(args.ifile) + ': ' + str(e), file=sys.stderr)
		exit(1)

	try:
		file = open(outfile, "wb")
		file.write(output)
		file.close()

	except Exception as e:
		print('Unable to write to file ' + str(args.ofile) + ': ' + str(e), file=sys.stderr)


sys.exit(0)
