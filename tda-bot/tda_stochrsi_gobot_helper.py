#!/usr/bin/python3 -u

import os, sys, signal
import time, datetime, pytz, random
import pickle
import tda_gobot_helper


# Runs from stream_client.handle_message() - calls stochrsi_gobot() with each
#  set of specified algorithms
def stochrsi_gobot_run(stream=None, algos=None, debug=False):

	if not isinstance(stream, dict):
		print('Error:')
		return False

	if not isinstance(algos, list):
		print('Error:')
		return False

	# Example stream:
	#
	# { 'service': 'CHART_EQUITY',
	#   'timestamp': 1619813320675,
	#   'command': 'SUBS',
	#   'content': [{
	#		'seq': 2712,
	#		'key': 'FB',
	#		'OPEN_PRICE': 325.05,
	#		'HIGH_PRICE': 325.05,
	#		'LOW_PRICE': 325.0,
	#		'CLOSE_PRICE': 325.02,
	#		'VOLUME': 898.0,
	#		'SEQUENCE': 547,
	#		'CHART_TIME': 1619813220000,
	#		'CHART_DAY': 18747 }]
	# }

	# Try to avoid reprocessing duplicate streams
	# This can happen if the websocket is closed by TDA for any reason (happens frequently)
	for idx in stream['content']:
		ticker = idx['key']

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Try to avoid reprocessing duplicate streams
		# This can happen if the websocket is closed by TDA for any reason (happens frequently)
#		if ( int(stream['timestamp']) == stocks[ticker]['prev_timestamp'] ):
#			continue
		stocks[ticker]['prev_timestamp'] = int( stream['timestamp'] )

		# Documentation suggests that equity streams should have unique sequence numbers, but
		#  other comments are unclear. Adding this log here so we can check with live data, but
		#  we are not acting on this yet.
		if ( int(idx['seq']) == stocks[ticker]['prev_seq'] ):
			print( '(' + str(ticker) + '): WARNING: duplicate sequence number detected - seq/timestamp: ' + str(idx['seq']) + ' / ' + str(stream['timestamp']) )
		stocks[ticker]['prev_seq'] = int( idx['seq'] )

		candle_data = {	'open':		idx['OPEN_PRICE'],
				'high':		idx['HIGH_PRICE'],
				'low':		idx['LOW_PRICE'],
				'close':	idx['CLOSE_PRICE'],
				'volume':	idx['VOLUME'],
				'datetime':	stream['timestamp'] }

		stocks[ticker]['pricehistory']['candles'].append( candle_data )
		stocks[ticker]['period_log'].append( stream['timestamp'] )

		# Look back through period_log to determine average number of candles received
		#  and set period_multiplier accordingly.
		# But don't muck with this if user explicitely changed the default of 0 via --period_multiplier
		#
		# SAZ - 2021-08-19 - disable period multiplier. Nice idea but does not function as expected,
		#  needs more research.
#		if ( args.period_multiplier == 0 ):
		stocks[ticker]['period_multiplier'] = 1
		if ( args.period_multiplier == -999 ):

			num_candles = 0
			cur_time = float( stream['timestamp'] )
			cur_time = datetime.datetime.fromtimestamp(cur_time/1000, tz=mytimezone)
			lookback_time = cur_time - datetime.timedelta( minutes=60 )
			lookback_time = lookback_time.timestamp() * 1000

			for idx,t_stamp in enumerate( stocks[ticker]['period_log'] ):
				if ( int(t_stamp) >= lookback_time ):
					num_candles = len(stocks[ticker]['period_log']) - idx
					break

			# num_candles should be the number of candles from 1-hour ago to the current time
			stocks[ticker]['period_multiplier'] = round( num_candles / 60 )
			if ( stocks[ticker]['period_multiplier'] < 1 ):
				stocks[ticker]['period_multiplier'] = 1


	# Call stochrsi_gobot() for each set of specific algorithms
	for algo_list in algos:
		ret = stochrsi_gobot( algos=algo_list, debug=debug )
		if ( ret == False ):
			print('Error: stochrsi_gobot_start(): stochrsi_gobot(' + str(algo) + '): returned False')

	return True


# Reset all the buy/sell/short/buy-to-cover and indicator signals
def reset_signals(ticker=None):

	if ( ticker == None ):
		return False

	stocks[ticker]['buy_signal']			= False
	stocks[ticker]['sell_signal']			= False
	stocks[ticker]['short_signal']			= False
	stocks[ticker]['buy_to_cover_signal']		= False

	stocks[ticker]['final_buy_signal']		= False
	stocks[ticker]['final_sell_signal']		= False		# Currently unused
	stocks[ticker]['final_short_signal']		= False
	stocks[ticker]['final_buy_to_cover_signal']	= False		# Currently unused

	stocks[ticker]['exit_signal']			= False

	stocks[ticker]['rsi_signal']			= False
	stocks[ticker]['adx_signal']			= False
	stocks[ticker]['dmi_signal']			= False
	stocks[ticker]['macd_signal']			= False
	stocks[ticker]['aroonosc_signal']		= False
	stocks[ticker]['vwap_signal']			= False
	stocks[ticker]['vpt_signal']			= False
	stocks[ticker]['resistance_signal']		= False

	stocks[ticker]['plus_di_crossover']		= False
	stocks[ticker]['minus_di_crossover']		= False
	stocks[ticker]['macd_crossover']		= False
	stocks[ticker]['macd_avg_crossover']		= False

	return True


# Save the pricehistory data for later analysis. This is typically called on exit.
def export_pricehistory():

	print("Writing stock pricehistory to ./" + args.tx_log_dir + "/\n")
	try:
		if ( os.path.isdir('./' + str(args.tx_log_dir)) == False ):
			os.mkdir('./' + str(args.tx_log_dir), mode=0o755)

	except OSError as e:
		print('Error: export_pricehistory(): Unable to make directory ./' + str(args.tx_log_dir) + ': ' + e, file=sys.stderr)
		return False

	for ticker in stocks.keys():
		if ( len(stocks[ticker]['pricehistory']) == 0 ):
			continue

		try:
			fname = './' + str(args.tx_log_dir) + '/' + str(ticker) + '.data'
			with open(fname, 'wb') as handle:
				pickle.dump(stocks[ticker]['pricehistory'], handle)

		except Exception as e:
			print('Error: Unable to write to file ' + str(fname) + ': ' + str(e))
			pass

	return True


# Main helper function for tda-stochrsi-gobot-v2 that implements the primary stochrsi
#  algorithm along with any secondary algorithms specified.
def stochrsi_gobot( algos=None, debug=False ):

	if not isinstance(algos, dict):
		print('Error:')
		return False

	# Exit of there are no more tickers marked as valid
	valid = 0
	for ticker in stocks.keys():
		if ( stocks[ticker]['isvalid'] == True ):
			valid = 1
			break

	if ( valid == 0 ):
		print("\nNo more valid stock tickers, exiting.")
		signal.raise_signal(signal.SIGTERM)

	# Exit if we are not set up to monitor across multiple days
	if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False ):
		if ( args.singleday == False and args.multiday == False ):
			print('Market closed, exiting.')
			signal.raise_signal(signal.SIGTERM)

	# Iterate through the stock tickers, calculate the stochRSI, and make buy/sell decisions
	for ticker in stocks.keys():

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Initialize some local variables
		percent_change = 0
		net_change = 0

		t_rsi_period = rsi_period * stocks[ticker]['period_multiplier']
		t_stochrsi_period = stochrsi_period * stocks[ticker]['period_multiplier']
		t_rsi_k_period = rsi_k_period * stocks[ticker]['period_multiplier']

		# Get stochastic RSI
		try:
			stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(stocks[ticker]['pricehistory'], rsi_period=t_rsi_period, stochrsi_period=t_stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=t_rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

		except Exception as e:
			print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + '): ' + str(e))

		if ( isinstance(stochrsi, bool) and stochrsi == False ):
			print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
			continue

		stocks[ticker]['cur_rsi_k']	= float( rsi_k[-1] )
		stocks[ticker]['cur_rsi_d']	= float( rsi_d[-1] )
		stocks[ticker]['prev_rsi_k']	= float( rsi_k[-2] )
		stocks[ticker]['prev_rsi_d']	= float( rsi_d[-2] )

		# RSI
		if ( algos['rsi'] == True ):
			t_rsi_period = rsi_period * stocks[ticker]['period_multiplier']

			try:
				rsi = tda_gobot_helper.get_rsi(stocks[ticker]['pricehistory'], t_rsi_period, rsi_type, debug=False)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_rsi(' + str(ticker) + '): ' + str(e))

			if ( isinstance(rsi, bool) and rsi == False ):
				print('Error: stochrsi_gobot(): get_rsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_rsi'] = float( rsi[-1] )

		# ADX, +DI, -DI
		if ( algos['adx'] == True or algos['dmi'] == True or algos['dmi_simple'] == True ):
			adx = []
			plus_di = []
			minus_di = []
			t_adx_period = adx_period * stocks[ticker]['period_multiplier']

			try:
				adx, plus_di, minus_di = tda_gobot_helper.get_adx(stocks[ticker]['pricehistory'], period=t_adx_period)

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_adx(): ' + str(e))
				continue

			stocks[ticker]['cur_adx']	= float( adx[-1] )
			stocks[ticker]['cur_plus_di']	= float( plus_di[-1] )
			stocks[ticker]['cur_minus_di']	= float( minus_di[-1] )
			stocks[ticker]['prev_plus_di']	= float( plus_di[-2] )
			stocks[ticker]['prev_minus_di']	= float( minus_di[-2] )

		# MACD - 48, 104, 36
		if ( algos['macd'] == True or algos['macd_simple'] == True ):
			macd = []
			macd_signal = []
			macd_histogram = []

			t_macd_short_period = macd_short_period * stocks[ticker]['period_multiplier']
			t_macd_long_period = macd_long_period * stocks[ticker]['period_multiplier']
			t_macd_signal_period = macd_signal_period * stocks[ticker]['period_multiplier']

			try:
				macd, macd_avg, macd_histogram = tda_gobot_helper.get_macd(stocks[ticker]['pricehistory'], short_period=t_macd_short_period, long_period=t_macd_long_period, signal_period=t_macd_signal_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_macd(' + str(ticker) + '): ' + str(e))
				continue

			stocks[ticker]['cur_macd']	= float( macd[-1] )
			stocks[ticker]['cur_macd_avg']	= float( macd_avg[-1] )
			stocks[ticker]['prev_macd']	= float( macd[-2] )
			stocks[ticker]['prev_macd_avg']	= float( macd_avg[-2] )

		# Aroon Oscillator
		if ( algos['aroonosc'] == True ):
			aroonosc = []
			t_aroonosc_period = aroonosc_period * stocks[ticker]['period_multiplier']

			try:
				aroonosc = tda_gobot_helper.get_aroon_osc(stocks[ticker]['pricehistory'], period=t_aroonosc_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_aroon_osc(' + str(ticker) + '): ' + str(e))
				continue

			stocks[ticker]['cur_aroonosc'] = float( aroonosc[-1] )

		# VWAP
		# Calculate vwap to use as entry or exit algorithm
		if ( algos['vwap'] or args.vwap_exit == True or algos['support_resistance'] == True ):
			vwap = []
			vwap_up = []
			vwap_down = []
			try:
				vwap, vwap_up, vwap_down = tda_gobot_helper.get_vwap( stocks[ticker]['pricehistory'] )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_vwap(' + str(ticker) + '): ' + str(e))

			stocks[ticker]['cur_vwap']	= float( vwap[-1] )
			stocks[ticker]['cur_vwap_up']	= float( vwap_up[-1] )
			stocks[ticker]['cur_vwap_down']	= float( vwap_down[-1] )

		# VPT
		if ( algos['vpt'] == True ):
			vpt = []
			vpt_sma = []
			t_vpt_sma_period = vpt_sma_period * stocks[ticker]['period_multiplier']

			try:
				vpt, vpt_sma = tda_gobot_helper.get_vpt(stocks[ticker]['pricehistory'], period=t_vpt_sma_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_vpt(' + str(ticker) + '): ' + str(e))

			stocks[ticker]['cur_vpt']	= float( vpt[-1] )
			stocks[ticker]['prev_vpt']	= float( vpt[-2] )
			stocks[ticker]['cur_vpt_sma']	= float( vpt_sma[-1] )
			stocks[ticker]['prev_vpt_sma']	= float( vpt_sma[-2] )


		# Debug
		if ( debug == True ):
			time_now = datetime.datetime.now( mytimezone )
			print(  '(' + str(ticker) + ') StochRSI period: ' + str(rsi_period) + ' / StochRSI type: ' + str(rsi_type) +
				' / StochRSI K period: ' + str(rsi_k_period) + ' / StochRSI D period: ' + str(rsi_d_period) + ' / StochRSI slow period: ' + str(rsi_slow) )

			# StochRSI
			print('(' + str(ticker) + ') Current StochRSI K: ' + str(round(stocks[ticker]['cur_rsi_k'], 2)) +
						' / Previous StochRSI K: ' + str(round(stocks[ticker]['prev_rsi_k'], 2)))
			print('(' + str(ticker) + ') Current StochRSI D: ' + str(round(stocks[ticker]['cur_rsi_d'], 2)) +
						' / Previous StochRSI D: ' + str(round(stocks[ticker]['prev_rsi_d'], 2)))

			# RSI
			if ( algos['rsi'] == True ):
				print('(' + str(ticker) + ') Current RSI: ' + str(round(stocks[ticker]['cur_rsi'], 2)))

			# ADX
			if ( algos['adx'] == True ):
				print('(' + str(ticker) + ') Current ADX: ' + str(round(stocks[ticker]['cur_adx'], 2)))

			# PLUS/MINUS DI
			if ( algos['dmi'] == True or algos['dmi_simple'] == True ):
				print('(' + str(ticker) + ') Current PLUS_DI: ' + str(round(stocks[ticker]['cur_plus_di'], 2)) +
							' / Previous PLUS_DI: ' + str(round(stocks[ticker]['prev_plus_di'], 2)))
				print('(' + str(ticker) + ') Current MINUS_DI: ' + str(round(stocks[ticker]['cur_minus_di'], 2)) +
							' / Previous MINUS_DI: ' + str(round(stocks[ticker]['prev_minus_di'], 2)))

			# MACD
			if ( algos['macd'] == True or algos['macd_simple'] ):
				print('(' + str(ticker) + ') Current MACD: ' + str(round(stocks[ticker]['cur_macd'], 2)) +
							' / Previous MACD: ' + str(round(stocks[ticker]['prev_macd'], 2)))
				print('(' + str(ticker) + ') Current MACD_AVG: ' + str(round(stocks[ticker]['cur_macd_avg'], 2)) +
							' / Previous MACD_AVG: ' + str(round(stocks[ticker]['prev_macd_avg'], 2)))

			# AroonOsc
			if ( algos['aroonosc'] == True ):
				print('(' + str(ticker) + ') Current AroonOsc: ' + str(round(stocks[ticker]['cur_aroonosc'], 2)))

			# VWAP
			if ( algos['vwap'] == True or algos['support_resistance'] == True ):
				print('(' + str(ticker) + ') Current VWAP: ' + str(round(stocks[ticker]['cur_vwap'], 2)) +
							' / Current VWAP_UP: ' + str(round(stocks[ticker]['cur_vwap_up'], 2)) +
							' / Current VWAP_DOWN: ' + str(round(stocks[ticker]['cur_vwap_down'], 2)))

			# VPT
			if ( algos['vpt'] == True ):
				print('(' + str(ticker) + ') Current VPT: ' + str(round(stocks[ticker]['cur_vpt'], 2)) +
							' / Previous VPT: ' + str(round(stocks[ticker]['prev_vpt'], 2)))
				print('(' + str(ticker) + ') Current VPT_SMA: ' + str(round(stocks[ticker]['cur_vpt_sma'], 2)) +
							' / Previous VPT_SMA: ' + str(round(stocks[ticker]['prev_vpt_sma'], 2)))

			print('(' + str(ticker) + ') Period Multiplier: ' + str(stocks[ticker]['period_multiplier']))

			# Timestamp check
			print('(' + str(ticker) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
				', timestamp received from API ' +
				datetime.datetime.fromtimestamp(int(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f') +
				' (' + str(int(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])) + ')' +
				' (seq: ' + str(stocks[ticker]['prev_seq']) + ')' )

			print()

		# Loop continuously while after hours if --multiday or --singleday is set
		# Also re-set --singleday to False when the market opens
		if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False ):
			if ( args.multiday == True or args.singleday == True ):
				continue
		else:
			args.singleday = False

		# Set some short variables to improve readability :)
		signal_mode	= stocks[ticker]['signal_mode']
		cur_rsi_k	= stocks[ticker]['cur_rsi_k']
		prev_rsi_k	= stocks[ticker]['prev_rsi_k']
		cur_rsi_d	= stocks[ticker]['cur_rsi_d']
		prev_rsi_d	= stocks[ticker]['prev_rsi_d']

		cur_rsi		= stocks[ticker]['cur_rsi']

		cur_adx		= stocks[ticker]['cur_adx']

		cur_plus_di	= stocks[ticker]['cur_plus_di']
		prev_plus_di	= stocks[ticker]['prev_plus_di']
		cur_minus_di	= stocks[ticker]['cur_minus_di']
		prev_minus_di	= stocks[ticker]['prev_minus_di']

		cur_macd	= stocks[ticker]['cur_macd']
		prev_macd	= stocks[ticker]['prev_macd']
		cur_macd_avg	= stocks[ticker]['cur_macd_avg']
		prev_macd_avg	= stocks[ticker]['prev_macd_avg']

		cur_aroonosc	= stocks[ticker]['cur_aroonosc']

		cur_vwap	= stocks[ticker]['cur_vwap']
		cur_vwap_up	= stocks[ticker]['cur_vwap_up']
		cur_vwap_down	= stocks[ticker]['cur_vwap_down']

		cur_vpt		= stocks[ticker]['cur_vpt']
		prev_vpt	= stocks[ticker]['prev_vpt']
		cur_vpt_sma	= stocks[ticker]['cur_vpt_sma']
		prev_vpt_sma	= stocks[ticker]['prev_vpt_sma']


		# Criteria for when we will not enter new trades
		if ( signal_mode == 'buy' or signal_mode == 'short'):

			# Skip if we've exhausted our maximum number of failed transactions for this stock
			if ( stocks[ticker]['failed_txs'] <= 0 ):
				print('(' + str(ticker) + ') Max number of failed transactions reached (' + str(args.max_failed_txs) + ').')
				stocks[ticker]['isvalid'] = False
				continue

			# Skip if we've exhausted our maximum number of purchases
			if ( stocks[ticker]['num_purchases'] < 1 ):
				print('(' + str(ticker) + ') Max number of purchases exhuasted.')
				stocks[ticker]['isvalid'] = False
				continue

			# Skip if end of trading day
			# If --multiday isn't set then we do not want to start trading if the market is closed.
			# Also if --multiday isn't set we should avoid buying any securities if it's within
			#  1-hour from market close. Otherwise we may be forced to sell too early.
			if ( (tda_gobot_helper.isendofday(60) == True or tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False) and args.multiday == False ):
				print('(' + str(ticker) + ') Market is closed or near closing.')
				reset_signals(ticker)
				continue

			# If args.hold_overnight=False and args.multiday==True, we won't enter any new trades 1-hour before market close
			if ( args.multiday == True and args.hold_overnight == False and tda_gobot_helper.isendofday(60) ):
				reset_signals(ticker)
				continue


		# BUY MODE - looking for a signal to purchase the stock
		if ( signal_mode == 'buy' ):

			# Jump to short mode if StochRSI K and D are already above rsi_high_limit
			# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit and stocks[ticker]['shortable'] == True ):
				print('(' + str(ticker) + ') StochRSI K and D values already above ' + str(rsi_high_limit) + ', switching to short mode.')

				reset_signals(ticker)
				stocks[ticker]['signal_mode'] = 'short'
				continue

			# StochRSI MONITOR
			# Monitor K and D
			# A buy signal occurs when an increasing %K line crosses above the %D line in the oversold region,
			#  or if the %K line crosses above the rsi limit
			if ( (cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit) ):
				if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
					print(  '(' + str(ticker) + ') BUY SIGNAL: StochRSI K value passed above the D value in the low_limit region (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['buy_signal'] = True

			elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
				if ( cur_rsi_k >= rsi_low_limit ):
					print(  '(' + str(ticker) + ') BUY SIGNAL: StochRSI K value passed above the low_limit threshold (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['buy_signal'] = True

			elif ( cur_rsi_k > rsi_signal_cancel_low_limit and cur_rsi_d > rsi_signal_cancel_low_limit ):
				# Reset the buy signal if rsi has wandered back above rsi_low_limit
				if ( stocks[ticker]['buy_signal'] == True ):
					print( '(' + str(ticker) + ') BUY SIGNAL CANCELED: RSI moved back above rsi_low_limit' )

				reset_signals(ticker)

			# Process any secondary indicators
			# RSI
			if ( algos['rsi'] == True ):
				stocks[ticker]['rsi_signal'] = False
				if ( cur_rsi < 20 ):
					stocks[ticker]['rsi_signal'] = True

			# ADX signal
			if ( algos['adx'] == True ):
				stocks[ticker]['adx_signal'] = False
				if ( cur_adx > 25 ):
					stocks[ticker]['adx_signal'] = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( algos['dmi'] == True or algos['dmi_simple'] == True ):
				if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = True
					stocks[ticker]['minus_di_crossover'] = False

				elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = False
					stocks[ticker]['minus_di_crossover'] = True

				stocks[ticker]['dmi_signal'] = False
				if ( cur_plus_di > cur_minus_di ):
					if ( algos['dmi_simple'] == True ):
						stocks[ticker]['dmi_signal'] = True
					elif ( stocks[ticker]['plus_di_crossover'] == True ):
						stocks[ticker]['dmi_signal'] = True

			# Aroon oscillator signals
			# Values closer to 100 indicate an uptrend
			if ( algos['aroonosc'] == True ):
				stocks[ticker]['aroonosc_signal'] = False
				if ( cur_aroonosc > 60 ):
					stocks[ticker]['aroonosc_signal'] = True

			# MACD crossover signals
			if ( algos['macd'] == True or algos['macd_simple'] == True ):
				if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = True
					stocks[ticker]['macd_avg_crossover'] = False

				elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = False
					stocks[ticker]['macd_avg_crossover'] = True

				stocks[ticker]['macd_signal'] = False
				if ( cur_macd > cur_macd_avg and cur_macd - cur_macd_avg > macd_offset ):
					if ( algos['macd_simple'] == True ):
						stocks[ticker]['macd_signal'] = True
					elif ( stocks[ticker]['macd_crossover'] == True ):
						stocks[ticker]['macd_signal'] = True

			# VWAP signal
			# This is the most simple/pessimistic approach right now
			if ( algos['vwap'] == True ):
				stocks[ticker]['vwap_signal'] = False
				cur_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
				if ( cur_price < cur_vwap ):
					stocks[ticker]['vwap_signal'] = True

			# VPT
			if ( algos['vpt'] == True ):
				# Buy signal - VPT crosses above vpt_sma
				if ( prev_vpt < prev_vpt_sma and cur_vpt > cur_vpt_sma ):
					stocks[ticker]['vpt_signal'] = True

				# Cancel signal if VPT crosses back over
				elif ( cur_vpt < cur_vpt_sma ):
					stocks[ticker]['vpt_signal'] = False

			# Support / Resistance
			if ( algos['support_resistance'] == True and args.no_use_resistance == False ):
				stocks[ticker]['resistance_signal'] = True
				cur_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )

				# PDC
				if ( stocks[ticker]['previous_day_close'] != 0 ):
					if ( abs((stocks[ticker]['previous_day_close'] / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to PDC
						# Next check average of last 15 (minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
						avg = avg / 15

						# If average was below PDC then PDC is resistance
						# If average was above PDC then PDC is support
						if ( avg < stocks[ticker]['previous_day_close'] ):
							stocks[ticker]['resistance_signal'] = False

				# VWAP
				if ( abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

					# Current price is very close to VWAP
					# Next check average of last 15 (minute) candles
					avg = 0
					for i in range(15, 0, -1):
						avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
					avg = avg / 15

					# If average was below VWAP then VWAP is resistance
					# If average was above VWAP then VWAP is support
					if ( avg < cur_vwap ):
						stocks[ticker]['resistance_signal'] = False

				# Key Levels
				# Check if price is near historic key level
				near_keylevel = False
				for lvl in stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']:
					if ( abs((lvl / cur_price - 1) * 100) <= price_support_pct ):
						near_keylevel = True

						# Current price is very close to a key level
						# Next check average of last 15 (1-minute) candles
						#
						# If last 15 candles average above key level, then key level is support
						# otherwise it is resistance
						avg = 0
						for i in range(15, 0, -1):
							avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
						avg = avg / 15

						# If average was below key level then key level is resistance
						# Therefore this is not a great buy
						if ( avg < lvl ):
							stocks[ticker]['resistance_signal'] = False
							break

				# If keylevel_strict is True then only buy the stock if price is near a key level
				# Otherwise reject this buy to avoid getting chopped around between levels
				if ( args.keylevel_strict == True and near_keylevel == False ):
					stocks[ticker]['resistance_signal'] = False

				# End Key Levels

#				# 20-week high
#				if ( cur_price >= float(stocks[ticker]['twenty_week_high']) ):
#					# This is not a good bet
#					stocks[ticker]['twenty_week_high'] = cur_price
#					stocks[ticker]['resistance_signal'] = False
#
#				elif ( ( abs(cur_price / float(stocks[ticker]['twenty_week_high']) - 1) * 100 ) < 1 ):
#					# Current high is within 1% of 20-week high, not a good bet
#					stocks[ticker]['resistance_signal'] = False

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( stocks[ticker]['buy_signal'] == True ):

				stocks[ticker]['final_buy_signal'] = True
				if ( algos['rsi'] == True and stocks[ticker]['rsi_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( algos['adx'] == True and stocks[ticker]['adx_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( (algos['dmi'] == True or algos['dmi_simple'] == True) and stocks[ticker]['dmi_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( algos['aroonosc'] == True and stocks[ticker]['aroonosc_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( (algos['macd'] == True or algos['macd_simple'] == True) and stocks[ticker]['macd_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( algos['vwap'] == True and stocks[ticker]['vwap_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( algos['vpt'] == True and stocks[ticker]['vpt_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( (algos['support_resistance'] == True and args.no_use_resistance == False) and stocks[ticker]['resistance_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

			# BUY THE STOCK
			if ( stocks[ticker]['buy_signal'] == True and stocks[ticker]['final_buy_signal'] == True ):

				# Calculate stock quantity from investment amount
				last_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
				stocks[ticker]['stock_qty'] = int( float(stock_usd) / float(last_price) )

				# Purchase the stock
				if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == True ):
					print('Purchasing ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker))
					stocks[ticker]['num_purchases'] -= 1

					if ( args.fake == False ):
						data = tda_gobot_helper.buy_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)
						if ( data == False ):
							print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
							stocks[ticker]['stock_qty'] = 0
							stocks[ticker]['isvalid'] = False
							reset_signals(ticker)
							continue

					try:
						stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						stocks[ticker]['orig_base_price'] = float(last_price)

				else:
					print('Stock ' + str(ticker) + ' not purchased because market is closed.')

					reset_signals(ticker)
					stocks[ticker]['stock_qty'] = 0
					continue

				net_change = 0
				stocks[ticker]['base_price'] = stocks[ticker]['orig_base_price']

				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

				reset_signals(ticker)
				stocks[ticker]['signal_mode'] = 'sell' # Switch to 'sell' mode for the next loop


		# SELL MODE - look for a signal to sell the stock
		elif ( signal_mode == 'sell' ):

			# In 'sell' mode we want to monitor the stock price along with RSI
			last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
			if ( isinstance(last_price, bool) and last_price == False ):
				print('Error: get_lastprice(' + str(ticker) + ') returned False, falling back to latest candle')
				last_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )

				tda_gobot_helper.tdalogin(passcode)
				time.sleep(0.5)

			net_change = round( (last_price - stocks[ticker]['orig_base_price']) * stocks[ticker]['stock_qty'], 3 )

			# End of trading day - dump the stock and exit unless --multiday was set
			#  or if args.hold_overnight=False and args.multiday=True
			if ( tda_gobot_helper.isendofday(4) == True ):
				if ( (args.multiday == True and args.hold_overnight == False) or args.multiday == False ):

					print('Market closing, selling stock ' + str(ticker))
					if ( args.fake == False ):
						data = tda_gobot_helper.sell_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

					tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist if sold at a loss greater than max_failed_usd
					if ( net_change < 0 and abs(net_change) > float(args.max_failed_usd) ):
						stocks[ticker]['isvalid'] = False
						if ( args.fake == False ):
							tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, 0)

					stocks[ticker]['tx_id'] = random.randint(1000, 9999)
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['base_price'] = 0
					stocks[ticker]['orig_base_price'] = 0

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					continue

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60) == True and args.hold_overnight == False ):
				if ( last_price > stocks[ticker]['orig_base_price'] ):
					percent_change = abs( stocks[ticker]['orig_base_price'] / last_price - 1 ) * 100
					if ( percent_change >= args.last_hour_threshold ):
						stocks[ticker]['exit_signal'] = True
						stocks[ticker]['sell_signal'] = True


			# STOPLOSS MONITOR
			# If price decreases
			if ( last_price < stocks[ticker]['base_price'] ):
				percent_change = abs( last_price / stocks[ticker]['base_price'] - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

				# SELL the security if we are using a trailing stoploss
				if ( percent_change >= stocks[ticker]['decr_threshold'] and args.stoploss == True ):

					print('Stock "' + str(ticker) + '" dropped below the decr_threshold (' + str(stocks[ticker]['decr_threshold']) + '%), selling the security...')
					if ( args.fake == False ):
						data = tda_gobot_helper.sell_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
					if ( net_change < 0 ):
						stocks[ticker]['failed_txs'] -= 1
						if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
							stocks[ticker]['isvalid'] = False
							if ( args.fake == False ):
								tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)

					# Change signal to 'buy' and generate new tx_id for next iteration
					stocks[ticker]['tx_id'] = random.randint(1000, 9999)
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['base_price'] = 0
					stocks[ticker]['orig_base_price'] = 0

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					continue


			# If price increases
			elif ( last_price > stocks[ticker]['base_price'] ):
				percent_change = abs( stocks[ticker]['base_price'] / last_price - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

				# Sell if --exit_percent was set and threshold met
				if ( args.exit_percent != None ):

					# If exit_percent has been hit, we will sell at the first RED candle
					if ( stocks[ticker]['exit_signal'] == True ):

						last_close = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
						last_open = float( stocks[ticker]['pricehistory']['candles'][-1]['open'] )
						if ( last_close < last_open ):
							stocks[ticker]['sell_signal'] = True

					elif ( percent_change >= float(args.exit_percent) ):
						stocks[ticker]['exit_signal'] = True

				# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
				if ( args.vwap_exit == True ):
					if ( cur_vwap > stocks[ticker]['orig_base_price'] ):
						if ( last_price >= ((cur_vwap - stocks[ticker]['orig_base_price']) / 2) + stocks[ticker]['orig_base_price'] ):
							stocks[ticker]['sell_signal'] = True

					elif ( cur_vwap < stocks[ticker]['orig_base_price'] ):
						if ( last_price >= ((cur_vwap_up - cur_vwap) / 2) + cur_vwap ):
							stocks[ticker]['sell_signal'] = True

				# Re-set the base_price to the last_price if we increase by incr_threshold or more
				# This way we can continue to ride a price increase until it starts dropping
				if ( percent_change >= incr_threshold ):
					stocks[ticker]['base_price'] = last_price
					print('Stock "' + str(ticker) + '" increased above the incr_threshold (' + str(incr_threshold) + '%), resetting base price to '  + str(last_price))
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					if ( args.scalp_mode == True ):
						stocks[ticker]['decr_threshold'] = 0.1
					else:
						stocks[ticker]['decr_threshold'] = incr_threshold / 2

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

			# No price change
			else:
				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

			# END STOPLOSS MONITOR

			# StochRSI MONITOR
			# Monitor K and D
			# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region,
			#  or if the %K line crosses below the RSI limit
			if ( (cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit) ):
				if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
					print(  '(' + str(ticker) + ') SELL SIGNAL: StochRSI K value passed below the D value in the high_limit region (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['sell_signal'] = True

			elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
				if ( cur_rsi_k <= rsi_high_limit ):
					print(  '(' + str(ticker) + ') SELL SIGNAL: StochRSI K value passed below the high_limit threshold (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['sell_signal'] = True


			# SELL THE STOCK
			if ( stocks[ticker]['sell_signal'] == True ):

				if ( args.fake == False ):
					data = tda_gobot_helper.sell_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, sold=True)
				print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

				# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
				if ( net_change < 0 ):
					stocks[ticker]['failed_txs'] -= 1
					if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
						stocks[ticker]['isvalid'] = False
						if ( args.fake == False ):
							tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)


				# Change signal to 'buy' or 'short' and generate new tx_id for next iteration
				stocks[ticker]['tx_id'] = random.randint(1000, 9999)
				stocks[ticker]['stock_qty'] = 0
				stocks[ticker]['base_price'] = 0
				stocks[ticker]['orig_base_price'] = 0

				reset_signals(ticker)
				if ( args.short == True and stocks[ticker]['shortable'] == True ):
					stocks[ticker]['short_signal'] = True
					stocks[ticker]['signal_mode'] = 'short'
					continue
				else:
					stocks[ticker]['signal_mode'] = 'buy'


		# SHORT SELL the stock
		# In this mode we will monitor the RSI and initiate a short sale if the RSI is very high
		elif ( signal_mode == 'short' ):

			# Jump to buy mode if StochRSI K and D are already below rsi_low_limit
			# The intent here is if the bot starts up while the RSI is low we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit and args.shortonly == False ):
				print('(' + str(ticker) + ') StochRSI K and D values already below ' + str(rsi_low_limit) + ', switching to buy mode.')

				reset_signals(ticker)
				stocks[ticker]['signal_mode'] = 'buy'
				continue


			# StochRSI MONITOR
			# Monitor K and D
			if ( (cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit) ):
				if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
					print(  '(' + str(ticker) + ') SHORT SIGNAL: StochRSI K value passed below the D value in the high_limit region (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['short_signal'] = True

			elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
				if ( cur_rsi_k <= rsi_high_limit ):
					print(  '(' + str(ticker) + ') SHORT SIGNAL: StochRSI K value passed below the high_limit threshold (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['short_signal'] = True

			elif ( cur_rsi_k < rsi_signal_cancel_high_limit and cur_rsi_d < rsi_signal_cancel_high_limit ):
				# Reset the short signal if rsi has wandered back below rsi_high_limit
				if ( stocks[ticker]['short_signal'] == True ):
					print( '(' + str(ticker) + ') SHORT SIGNAL CANCELED: RSI moved back below rsi_high_limit' )

				reset_signals(ticker)

			# Secondary Indicators
			# RSI
			if ( algos['rsi'] == True ):
				stocks[ticker]['rsi_signal'] = False
				if ( cur_rsi > 75 ):
					stocks[ticker]['rsi_signal'] = True

			# ADX signal
			if ( algos['adx'] == True ):
				stocks[ticker]['adx_signal'] = False
				if ( cur_adx > 25 ):
					stocks[ticker]['adx_signal'] = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( algos['dmi'] == True or algos['dmi_simple'] == True ):
				if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = True
					stocks[ticker]['minus_di_crossover'] = False

				elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = False
					stocks[ticker]['minus_di_crossover'] = True

				stocks[ticker]['dmi_signal'] = False
				if ( cur_plus_di < cur_minus_di ):
					if ( algos['dmi_simple'] == True ):
						stocks[ticker]['dmi_signal'] = True
					elif ( stocks[ticker]['minus_di_crossover'] == True ):
						stocks[ticker]['dmi_signal'] = True

			# Aroon oscillator signals
			# Values closer to -100 indicate a downtrend
			if ( algos['aroonosc'] == True ):
				stocks[ticker]['aroonosc_signal'] = False
				if ( cur_aroonosc < -60 ):
					stocks[ticker]['aroonosc_signal'] = True

			# MACD crossover signals
			if ( algos['macd'] == True or algos['macd_simple'] == True ):
				if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = True
					stocks[ticker]['macd_avg_crossover'] = False

				elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = False
					stocks[ticker]['macd_avg_crossover'] = True

				stocks[ticker]['macd_signal'] = False
				if ( cur_macd < cur_macd_avg and cur_macd_avg - cur_macd > macd_offset ):
					if ( algos['macd_simple'] == True ):
						stocks[ticker]['macd_signal'] = True
					elif ( stocks[ticker]['macd_avg_crossover'] == True ):
						stocks[ticker]['macd_signal'] = True

			# VWAP signal
			# This is the most simple/pessimistic approach right now
			if ( algos['vwap'] == True ):
				stocks[ticker]['vwap_signal'] = False
				cur_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
				if ( cur_price > cur_vwap ):
					stocks[ticker]['vwap_signal'] = True

			# VPT
			if ( algos['vpt'] == True ):
				# Short signal - VPT crosses below vpt_sma
				if ( prev_vpt > prev_vpt_sma and cur_vpt < cur_vpt_sma ):
					stocks[ticker]['vpt_signal'] = True

				# Cancel signal if VPT crosses back over
				elif ( cur_vpt > cur_vpt_sma ):
					stocks[ticker]['vpt_signal'] = False

			# Support / Resistance
			if ( algos['support_resistance'] == True and args.no_use_resistance == False ):
				stocks[ticker]['resistance_signal'] = True
				cur_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )

				# PDC
				if ( stocks[ticker]['previous_day_close'] != 0 ):
					if ( abs((stocks[ticker]['previous_day_close'] / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to PDC
						# Next check average of last 15 (minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
						avg = avg / 15

						# If average was below PDC then PDC is resistance (good for short)
						# If average was above PDC then PDC is support (bad for short)
						if ( avg > stocks[ticker]['previous_day_close'] ):
							stocks[ticker]['resistance_signal'] = False

				# VWAP
				if ( abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

					# Current price is very close to VWAP
					# Next check average of last 15 (minute) candles
					avg = 0
					for i in range(15, 0, -1):
						avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
					avg = avg / 15

					# If average was below VWAP then VWAP is resistance (good for short)
					# If average was above VWAP then VWAP is support (bad for short)
					if ( avg > cur_vwap ):
						stocks[ticker]['resistance_signal'] = False

				# Key Levels
				# Check if price is near historic key level
				near_keylevel = False
				for lvl in stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']:
					if ( abs((lvl / cur_price - 1) * 100) <= price_resistance_pct ):
						near_keylevel = True

						# Current price is very close to a key level
						# Next check average of last 15 (1-minute) candles
						#
						# If last 15 candles average below key level, then key level is resistance
						# otherwise it is support
						avg = 0
						for i in range(15, 0, -1):
							avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
						avg = avg / 15

						# If average was above key level then key level is support
						# Therefore this is not a good short
						if ( avg > lvl ):
							stocks[ticker]['resistance_signal'] = False
							break

				# If keylevel_strict is True then only short the stock if price is near a key level
				# Otherwise reject this short altogether to avoid getting chopped around between levels
				if ( args.keylevel_strict == True and near_keylevel == False ):
					stocks[ticker]['resistance_signal'] = False

				# End Key Levels

#				# 20-week low
#				if ( cur_price <= float(stocks[ticker]['twenty_week_low']) ):
#					# This is not a good bet
#					stocks[ticker]['twenty_week_low'] = cur_price
#					stocks[ticker]['resistance_signal'] = False
#
#				elif ( ( abs(float(stocks[ticker]['twenty_week_low']) / float(cur_price) - 1) * 100 ) < 1 ):
#					# Current low is within 1% of 20-week low, not a good bet
#					stocks[ticker]['resistance_signal'] = False

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( stocks[ticker]['short_signal'] == True ):

				stocks[ticker]['final_short_signal'] = True
				if ( algos['rsi'] == True and stocks[ticker]['rsi_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( algos['adx'] == True and stocks[ticker]['adx_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( (algos['dmi'] == True or algos['dmi_simple'] == True) and stocks[ticker]['dmi_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( algos['aroonosc'] == True and stocks[ticker]['aroonosc_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( (algos['macd'] == True or algos['macd_simple'] == True) and stocks[ticker]['macd_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( algos['vwap'] == True and stocks[ticker]['vwap_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( algos['vpt'] == True and stocks[ticker]['vpt_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( (algos['support_resistance'] == True and args.no_use_resistance == False) and stocks[ticker]['resistance_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False


			# SHORT THE STOCK
			if ( stocks[ticker]['short_signal'] == True and stocks[ticker]['final_short_signal'] == True ):

				# Calculate stock quantity from investment amount
				last_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
				stocks[ticker]['stock_qty'] = int( float(stock_usd) / float(last_price) )

				# Short the stock
				if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == True ):
					print('Shorting ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker))
					stocks[ticker]['num_purchases'] -= 1

					if ( args.fake == False ):
						data = tda_gobot_helper.short_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)
						if ( data == False ):
							if ( args.shortonly == True ):
								print('Error: Unable to short "' + str(ticker) + '"', file=sys.stderr)
								stocks[ticker]['stock_qty'] = 0

								reset_signals(ticker)
								stocks[ticker]['shortable'] = False
								stocks[ticker]['isvalid'] = False
								continue

							else:
								print('Error: Unable to short "' + str(ticker) + '" - disabling shorting', file=sys.stderr)

								reset_signals(ticker)
								stocks[ticker]['shortable'] = False
								stocks[ticker]['stock_qty'] = 0
								stocks[ticker]['signal_mode'] = 'buy'
								continue

					try:
						stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						stocks[ticker]['orig_base_price'] = last_price

				else:
					print('Stock ' + str(ticker) + ' not shorted because market is closed.')

					reset_signals(ticker)
					stocks[ticker]['stock_qty'] = 0
					if ( args.shortonly == False ):
						signal_mode = 'buy'

					continue

				net_change = 0
				stocks[ticker]['base_price'] = stocks[ticker]['orig_base_price']

				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=False)

				reset_signals(ticker)
				stocks[ticker]['signal_mode'] = 'buy_to_cover'


		# BUY_TO_COVER a previous short sale
		# This mode must always follow a previous "short" signal. We will monitor the RSI and initiate
		#   a buy-to-cover transaction to cover a previous short sale if the RSI if very low. We also
		#   need to monitor stoploss in case the stock rises above a threshold.
		elif ( signal_mode == 'buy_to_cover' ):

			last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
			if ( isinstance(last_price, bool) and last_price == False ):
				print('Error: get_lastprice(' + str(ticker) + ') returned False, falling back to latest candle')
				last_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )

				tda_gobot_helper.tdalogin(passcode)
				time.sleep(0.5)

			net_change = round( (last_price - stocks[ticker]['orig_base_price']) * stocks[ticker]['stock_qty'], 3 )

			# End of trading day - dump the stock and exit unless --multiday was set
			#  or if args.hold_overnight=False and args.multiday=True
			if ( tda_gobot_helper.isendofday(4) == True ):
				if ( (args.multiday == True and args.hold_overnight == False) or args.multiday == False ):

					print('Market closing, covering shorted stock ' + str(ticker))
					if ( args.fake == False ):
						data = tda_gobot_helper.buytocover_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist if sold at a loss greater than max_failed_usd
					if ( net_change > 0 and abs(net_change) > args.max_failed_usd ):
						stocks[ticker]['isvalid'] = False
						if ( args.fake == False ):
							tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)

					stocks[ticker]['tx_id'] = random.randint(1000, 9999)
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['base_price'] = 0
					stocks[ticker]['orig_base_price'] = 0

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					if ( args.shortonly == True ):
						stocks[ticker]['signal_mode'] = 'short'

					continue

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60) == True and args.hold_overnight == False ):
				if ( last_price < stocks[ticker]['orig_base_price'] ):
					percent_change = abs( last_price / stocks[ticker]['orig_base_price'] - 1 ) * 100
					if ( percent_change >= args.last_hour_threshold ):
						stocks[ticker]['exit_signal'] = True
						stocks[ticker]['buy_to_cover_signal'] = True


			# STOPLOSS MONITOR
			# If price decreases
			if ( last_price < stocks[ticker]['base_price'] ):
				percent_change = abs( last_price / stocks[ticker]['base_price'] - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

				if ( args.exit_percent != None ):

					# If exit_percent has been hit, we will sell at the first GREEN candle
					if ( stocks[ticker]['exit_signal'] == True ):

						last_close = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
						last_open = float( stocks[ticker]['pricehistory']['candles'][-1]['open'] )
						if ( last_close > last_open ):
							stocks[ticker]['buy_to_cover_signal'] = True

					elif ( percent_change >= float(args.exit_percent) ):
						stocks[ticker]['exit_signal'] = True


				# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
				if ( args.vwap_exit == True ):
					if ( cur_vwap < stocks[ticker]['orig_base_price'] ):
						if ( last_price <= ((stocks[ticker]['orig_base_price'] - cur_vwap) / 2) + cur_vwap ):
							stocks[ticker]['buy_to_cover_signal'] = True

					elif ( cur_vwap > stocks[ticker]['orig_base_price'] ):
						if ( last_price <= ((cur_vwap - cur_vwap_down) / 2) + cur_vwap_down ):
							stocks[ticker]['buy_to_cover_signal'] = True

				# Re-set the base_price to the last_price if we increase by incr_threshold or more
				# This way we can continue to ride a price increase until it starts dropping
				if ( percent_change >= incr_threshold ):
					stocks[ticker]['base_price'] = last_price
					print('SHORTED Stock "' + str(ticker) + '" decreased below the incr_threshold (' + str(incr_threshold) + '%), resetting base price to '  + str(last_price))
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					if ( args.scalp_mode == True ):
						stocks[ticker]['decr_threshold'] = 0.1
					else:
						stocks[ticker]['decr_threshold'] = incr_threshold / 2

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], short=True, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

			# If price increases
			elif ( last_price > stocks[ticker]['base_price'] ):
				percent_change = abs( stocks[ticker]['base_price'] / last_price - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], short=True, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

				# BUY-TO-COVER the security if we are using a trailing stoploss
				if ( percent_change >= stocks[ticker]['decr_threshold'] and args.stoploss == True ):

					print('SHORTED Stock "' + str(ticker) + '" increased above the decr_threshold (' + str(stocks[ticker]['decr_threshold']) + '%), covering shorted stock...')
					if ( args.fake == False ):
						data = tda_gobot_helper.buytocover_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
					if ( net_change > 0 ):
						stocks[ticker]['failed_txs'] -= 1
						if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
							stocks[ticker]['isvalid'] = False
							if ( args.fake == False ):
								tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)

					# Change signal to 'buy' and generate new tx_id for next iteration
					stocks[ticker]['tx_id'] = random.randint(1000, 9999)
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['base_price'] = 0
					stocks[ticker]['orig_base_price'] = 0

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					if ( args.shortonly == True ):
						stocks[ticker]['signal_mode'] = 'short'

					continue

			# No price change
			else:
				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True)

			# END STOPLOSS MONITOR

			# RSI MONITOR
			# Monitor K and D
			if ( (cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit) ):
				if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
					print(  '(' + str(ticker) + ') BUY_TO_COVER SIGNAL: StochRSI K value passed above the D value in the low_limit region (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['buy_to_cover_signal'] = True

			elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
				if ( cur_rsi_k >= rsi_low_limit ):
					print(  '(' + str(ticker) + ') BUY_TO_COVER SIGNAL: StochRSI K value passed above the low_limit threshold (' +
						str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

					stocks[ticker]['buy_to_cover_signal'] = True


			# BUY-TO-COVER THE STOCK
			if ( stocks[ticker]['buy_to_cover_signal'] == True ):
				if ( args.fake == False ):
					data = tda_gobot_helper.buytocover_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=True)
				print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

				# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
				if ( net_change > 0 ):
					stocks[ticker]['failed_txs'] -= 1
					if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
						stocks[ticker]['isvalid'] = False
						if ( args.fake == False ):
							tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)

				# Change signal to 'buy' and generate new tx_id for next iteration
				stocks[ticker]['tx_id'] = random.randint(1000, 9999)
				stocks[ticker]['stock_qty'] = 0
				stocks[ticker]['base_price'] = 0
				stocks[ticker]['orig_base_price'] = 0

				reset_signals(ticker)
				if ( args.shortonly == True ):
					stocks[ticker]['signal_mode'] = 'short'

				else:
					stocks[ticker]['buy_signal'] = True
					stocks[ticker]['signal_mode'] = 'buy'
					continue


		# Undefined mode - this shouldn't happen
		else:
			print('Error: undefined signal_mode: ' + str(signal_mode))

		print() # Make debug log easier to read

	# END stocks.keys() loop

	# Make the debug messages easier to read
	if ( debug == True ):
		print("\n------------------------------------------------------------------------\n")


	return True


# Sell any open positions. This is usually called via a signal handler.
def sell_stocks():

	# Make sure we are logged into TDA
	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: sell_stocks(): tdalogin(): login failure')
		return False

	# Run through the stocks we are watching and sell/buy-to-cover any open positions
	data = tda.get_account(tda_account_number, options='positions', jsonify=True)
	for ticker in stocks.keys():

		# Look up the stock in the account and sell
		for asset in data[0]['securitiesAccount']['positions']:
			if ( str(asset['instrument']['symbol']).upper() == str(ticker).upper() ):

				if ( float(asset['shortQuantity']) > 0 ):
					print('Covering ' + str(asset['shortQuantity']) + ' shares of ' + str(ticker))
					data = tda_gobot_helper.buytocover_stock_marketprice(ticker, asset['shortQuantity'], fillwait=False, debug=False)
				else:
					print('Selling ' + str(asset['longQuantity']) + ' shares of ' + str(ticker))
					data = tda_gobot_helper.sell_stock_marketprice(ticker, asset['longQuantity'], fillwait=False, debug=False)

				break

	return True

