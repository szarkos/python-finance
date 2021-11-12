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
std_opts = ' --algo=stochrsi-new --stoploss --skip_check --incr_threshold=0.5 --exit_percent=1 --verbose --stock_usd=25000 ' + \
		' --variable_exit --lod_hod_check --check_volume --decr_threshold=1.6 --exit_percent=0.5 --daily_atr_period=3 ' #--use_natr_resistance

# Test Scenarios
scenarios = {
		# Daily test, called from automation. Comment to disable the automation.
                'stochrsi_standard_daily_test':                                 '--rsi_high_limit=75 --rsi_low_limit=25 --stochrsi_offset=6 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
                                                                                 --use_natr_resistance --min_intra_natr=0.15 --min_daily_natr=3 --with_supertrend --supertrend_min_natr=2 ',

                'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx_standard':   '--rsi_high_limit=75 --rsi_low_limit=25 --stochrsi_offset=3 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
                                                                                 --use_natr_resistance --min_intra_natr=0.15 --min_daily_natr=6 ',

		# Squeeze tests
		#       kama    = Kaufman Adaptive Moving Average (default)
		#       dema    = Double Exponential Moving Average
		#       hma     = Hull Moving Average
		#       tema    = Triple Exponential Moving Average
		#       trima   = Triangular Moving Average
		#       vwma    = Volume Weighted Moving Average
		#       wma     = Weighted Moving Average
		#       zlema   = Zero-Lag Exponential Moving Average
		'stochstackedma_bbands_kchannel_standard_sma':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=4 --stacked_ma_type_primary=sma \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_ema':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=ema \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_kama':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=kama \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_dema':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=dema \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_hma':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=hma \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_tema':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=tema \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_trima':'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=trima \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_wma':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=wma \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_vwma':	'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=4 --stacked_ma_type_primary=vwma \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',
		'stochstackedma_bbands_kchannel_standard_zlema':'--primary_stoch_indicator="stacked_ma" --with_bbands_kchannel --bbands_kchannel_offset=0.15 \
								 --stacked_ma_periods_primary=3,5,8 --bbands_kchan_squeeze_count=1 --stacked_ma_type_primary=zlema \
								 --min_intra_natr=0.65 --min_daily_natr=6 ',




#		# Daily test, called from automation. Comment to disable the automation.
#		'stochrsi_standard_daily_test':		'--rsi_high_limit=85 --rsi_low_limit=15 --stochrsi_offset=6 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#							 --daily_atr_period=3 --min_intra_natr=0.15 --min_daily_natr=3 --with_supertrend --supertrend_min_natr=2 --decr_threshold=2 ',
#
#		# This is the algo that had 70% win rate with 94 trades over 3-months
#		'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx_standard_natr6_2':	'--rsi_high_limit=85 --rsi_low_limit=15 --stochrsi_offset=3 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#											 --daily_atr_period=3 --min_intra_natr=0.15 --min_daily_natr=6 --decr_threshold=2 ',
#
#		'stochrsi_standard_daily_test_rsi8020_decr1.6':		'--rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_offset=6 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#                                                       		--daily_atr_period=3 --min_intra_natr=0.15 --min_daily_natr=3 --with_supertrend --supertrend_min_natr=2 --decr_threshold=1.6 ',
#
#		'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx_standard_natr6_rsi8020_decr1.6':     '--rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_offset=3 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#                                                                                     --daily_atr_period=3 --min_intra_natr=0.15 --min_daily_natr=6 --decr_threshold=1.6 ',
#
#
#		'stochrsi_standard_daily_test_rsi7525_decr1.6':		'--rsi_high_limit=75 --rsi_low_limit=25 --stochrsi_offset=6 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#                                                        		--daily_atr_period=3 --min_intra_natr=0.15 --min_daily_natr=3 --with_supertrend --supertrend_min_natr=2 --decr_threshold=1.6 ',
#
#		'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx_standard_natr6_rsi7525_decr1.6':     '--rsi_high_limit=75 --rsi_low_limit=25 --stochrsi_offset=3 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#                                                                                     --daily_atr_period=3 --min_intra_natr=0.15 --min_daily_natr=6 --decr_threshold=1.6 ',


#		# Mid-60s percentile:
#		'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx_off6_minnatr2': '--rsi_high_limit=85 --rsi_low_limit=15 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#                                                                                  --daily_atr_period=3 --stochrsi_offset=6 --use_natr_resistance --min_intra_natr=0.15 --min_daily_natr=2 --decr_threshold=2 ',



##################################################################################################
		#### testing --dmi_with_adx ####
#		'stochrsi5m_stochmfi5m_simple_dmi_supertrend_chopsimple':	' --primary_stoch_indicator="stochrsi" --rsi_high_limit=75 --rsi_low_limit=25 --with_stoch_5m --with_stochmfi_5m \
#										  --stochrsi_5m_period=6 --stochmfi_5m_period=14 --rsi_k_period=3 --stochrsi_offset=1 --with_dmi_simple --dmi_with_adx \
#										  --daily_atr_period=3 --di_period=3 --with_supertrend --supertrend_min_natr=2 --with_chop_index ',
#
#		'stochrsi5m_stochmfi5m_simple_dmi_chopsimple':			' --primary_stoch_indicator="stochrsi" --rsi_high_limit=75 --rsi_low_limit=25 --with_stoch_5m --with_stochmfi_5m \
#										  --stochrsi_5m_period=6 --stochmfi_5m_period=14 --rsi_k_period=3 --stochrsi_offset=1 --with_dmi_simple --dmi_with_adx \
#										  --daily_atr_period=3 --di_period=3 --with_chop_index ',


		# "Portfolio" algorithms
#		'stochrsi_stochmfi_chop_simple':				'--primary_stoch_indicator="stochrsi" --rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_period=128 --stochrsi_offset=1.5 --with_stochmfi --stochmfi_period=128 \
#										 --daily_atr_period=7 --use_natr_resistance --min_intra_natr=0.15 --with_adx --adx_threshold=7 --with_chop_simple --max_intra_natr=0.4 --max_daily_natr=3.5 ',
#
#		'stochrsi_stochmfi_chop_index':					'--primary_stoch_indicator="stochrsi" --rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_period=128 --stochrsi_offset=1.5 --with_stochmfi --stochmfi_period=128 \
#										 --daily_atr_period=7 --use_natr_resistance --min_intra_natr=0.15 --with_adx --adx_threshold=7 --with_chop_index --max_intra_natr=0.4 --max_daily_natr=3.5 ',
#
#		'stochrsi_stochmfi_chop_simple_mfi':				'--primary_stoch_indicator="stochrsi" --rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_period=128 --stochrsi_offset=1.5 --with_stochmfi --stochmfi_period=128 \
#										 --daily_atr_period=7 --use_natr_resistance --min_intra_natr=0.15 --with_adx --adx_threshold=7 --with_chop_simple --max_intra_natr=0.4 --max_daily_natr=3.5 --with_mfi ',
#
#		'stochrsi_stochmfi_chop_index_mfi':				'--primary_stoch_indicator="stochrsi" --rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_period=128 --stochrsi_offset=1.5 --with_stochmfi --stochmfi_period=128 \
#										 --daily_atr_period=7 --use_natr_resistance --min_intra_natr=0.15 --with_adx --adx_threshold=7 --with_chop_index --max_intra_natr=0.4 --max_daily_natr=3.5 --with_mfi ',
#
#		'stochrsi_stochmfi_macd':					'--primary_stoch_indicator="stochrsi" --rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_period=128 --stochrsi_offset=1.5 --with_stochmfi --stochmfi_period=128 \
#										 --daily_atr_period=7 --use_natr_resistance --min_intra_natr=0.15 --with_adx --adx_threshold=7 --max_intra_natr=0.4 --max_daily_natr=3.5 \
#										 --with_macd --macd_short_period=42 --macd_long_period=52 --macd_signal_period=5 --macd_offset=0.00475 ',
#
#		'stochrsi_stochmfi_macd_chop_simple':				'--primary_stoch_indicator="stochrsi" --rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_period=128 --stochrsi_offset=1.5 --with_stochmfi --stochmfi_period=128 \
#										 --daily_atr_period=7 --use_natr_resistance --min_intra_natr=0.15 --with_adx --adx_threshold=7 --with_chop_simple --max_intra_natr=0.4 --max_daily_natr=3.5 \
#										 --with_macd --macd_short_period=42 --macd_long_period=52 --macd_signal_period=5 --macd_offset=0.00475 --with_chop_simple ',
#
#		'stochrsi_stochmfi_macd_mfi':					'--primary_stoch_indicator="stochrsi" --rsi_high_limit=80 --rsi_low_limit=20 --stochrsi_period=128 --stochrsi_offset=1.5 --with_stochmfi --stochmfi_period=128 \
#										 --daily_atr_period=7 --use_natr_resistance --min_intra_natr=0.15 --with_adx --adx_threshold=7 --max_intra_natr=0.4 --max_daily_natr=3.5 \
#										 --with_macd --macd_short_period=42 --macd_long_period=52 --macd_signal_period=5 --macd_offset=0.00475 --with_mfi ',



		# Loud, not used but good baseline
		#'stochrsi_aroonosc_simple_dmi_simple_with_macd_adx':		'--rsi_high_limit=85 --rsi_low_limit=15 --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 ',

		# Good results but fewer trades
#		'stochrsi_mfi_aroonosc_simple_dmi_simple_with_macd_adx':	'--rsi_high_limit=85 --rsi_low_limit=15 --stochrsi_offset=3 --with_mfi --with_dmi_simple --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=6 \
#										 --daily_atr_period=7 --min_intra_natr=0.15 --min_daily_natr=1.5 ',

		# Very good results but very few trades
#		'stochrsi_mfi_aroonosc_simple_adx_lowperiod':			'--rsi_high_limit=85 --rsi_low_limit=15 --stochrsi_offset=3 --with_mfi --mfi_high_limit=95 --mfi_low_limit=5 --with_aroonosc_simple --aroonosc_with_macd_simple \
#										 --with_adx --adx_threshold=20 --adx_period=48 --daily_atr_period=7 --min_intra_natr=0.15 --min_daily_natr=1.5 ',

		# Similar to above without mfi, decent results (60 percentile daily win rate) but more trades
		# Currently not used, needs more testing
		# 'stochrsi_aroonosc_simple_adx_lowperiod':			'--rsi_high_limit=85 --rsi_low_limit=15 --with_aroonosc_simple --aroonosc_with_macd_simple --with_adx --adx_threshold=20 --adx_period=48 ',

		# Decent results (60 percentile)
#		'stochrsi_mfi_rsi_adx':						'--rsi_high_limit=85 --rsi_low_limit=15 --stochrsi_offset=3 --with_mfi --mfi_high_limit=95 --mfi_low_limit=5 --with_rsi --with_adx --adx_threshold=20 \
#										 --daily_atr_period=7 --min_intra_natr=0.15 --min_daily_natr=1.5 ',

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
