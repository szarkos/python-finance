#!/usr/bin/python3 -u

import os, sys, signal
import time, datetime, pytz, random
import pickle
import tda_gobot_helper


# Runs from stream_client.handle_message() - calls stochrsi_gobot() with each
#  set of specified algorithms
def stochrsi_gobot_run(stream=None, algos=None, debug=False):

	if not isinstance(stream, dict):
		print('Error: stochrsi_gobot_run() called without valid stream{} data.', file=sys.stderr)
		return False

	if not isinstance(algos, list):
		print('Error: stochrsi_gobot_run() called without valid algos[] list', file=sys.stderr)
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
	for idx in stream['content']:
		ticker = idx['key']

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Try to avoid reprocessing duplicate streams, if there are any
		#
		# Documentation suggests that equity streams should have unique sequence numbers, but
		#   other comments are unclear.
		#
		# 'seq' - appears to be an integer that increments by one for each stream update, so it
		#    is based on when the stream started, it's not a unique identifier for a candle.
		#    This value increements up to some three-digit number (which varies between stocks)
		#    and then restarts back at 1.
		# 'sequence' - appears to be more accurate to identify a particular candle.
		#
		# Adding this log here so we can check with live data.
		if ( int(idx['SEQUENCE']) == stocks[ticker]['prev_seq'] ):
			print( '(' + str(ticker) + '): WARNING: duplicate sequence number detected - seq/timestamp: ' + str(idx['SEQUENCE']) + ' / ' + str(stream['timestamp']) )
			continue

		stocks[ticker]['prev_seq'] = int( idx['SEQUENCE'] )

		candle_data = {	'open':		float( idx['OPEN_PRICE'] ),
				'high':		float( idx['HIGH_PRICE'] ),
				'low':		float( idx['LOW_PRICE'] ),
				'close':	float( idx['CLOSE_PRICE'] ),
				'volume':	int( idx['VOLUME'] ),
				'datetime':	stream['timestamp'] }

		stocks[ticker]['pricehistory']['candles'].append( candle_data )
		stocks[ticker]['period_log'].append( stream['timestamp'] )

		# Add 5min candle
		if ( len(stocks[ticker]['pricehistory']['candles']) % 5 == 0 ):
			open_p	= stocks[ticker]['pricehistory']['candles'][-5]['open']
			close	= stocks[ticker]['pricehistory']['candles'][-1]['close']
			high	= 0
			low	= 9999
			volume	= 0

			for i in range(5, 0, -1):
				volume += stocks[ticker]['pricehistory']['candles'][-i]['volume']

				if ( high < stocks[ticker]['pricehistory']['candles'][-i]['high'] ):
					high = stocks[ticker]['pricehistory']['candles'][-i]['high']

				if ( low > stocks[ticker]['pricehistory']['candles'][-i]['low'] ):
					low = stocks[ticker]['pricehistory']['candles'][-i]['low']

			newcandle = {	'open':		open_p,
					'high':		high,
					'low':		low,
					'close':	close,
					'volume':	volume,
					'datetime':	stocks[ticker]['pricehistory']['candles'][-i]['datetime'] }

			stocks[ticker]['pricehistory_5m']['candles'].append(newcandle)

		# Look back through period_log to determine average number of candles received
		#   and set period_multiplier accordingly.
		# But don't muck with this if user explicitely changed the default of 0 via --period_multiplier
		#
		# SAZ - 2021-08-19 - disable period multiplier. Nice idea but does not function as expected,
		#  needs more research.
		stocks[ticker]['period_multiplier'] = 1
		#if ( args.period_multiplier == 0 ):
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
		ret = stochrsi_gobot( cur_algo=algo_list, debug=debug )
		if ( ret == False ):
			print('Error: stochrsi_gobot_start(): stochrsi_gobot(' + str(algo) + '): returned False', file=sys.stderr)

	return True


# Reset all the buy/sell/short/buy-to-cover and indicator signals
def reset_signals(ticker=None, id=None, signal_mode=None):

	if ( ticker == None ):
		return False

	stocks[ticker]['final_buy_signal']		= False
	stocks[ticker]['final_sell_signal']		= False		# Currently unused
	stocks[ticker]['final_short_signal']		= False
	stocks[ticker]['final_buy_to_cover_signal']	= False		# Currently unused
	stocks[ticker]['exit_percent_signal']		= False

	for algo in algos:
		if ( id != None and algo['algo_id'] != id ):
			continue

		algo_id = algo['algo_id']

		if ( signal_mode != None ):
			stocks[ticker]['algo_signals'][algo_id]['signal_mode']		= signal_mode

		stocks[ticker]['algo_signals'][algo_id]['buy_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['sell_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['short_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal']		= False

		stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['stochrsi_crossover_signal']	= False
		stocks[ticker]['algo_signals'][algo_id]['stochrsi_threshold_signal']	= False

		stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_crossover_signal']	= False
		stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_threshold_signal']	= False

		stocks[ticker]['algo_signals'][algo_id]['stochmfi_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['stochmfi_crossover_signal']	= False
		stocks[ticker]['algo_signals'][algo_id]['stochmfi_threshold_signal']	= False

		stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_crossover_signal']	= False
		stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_threshold_signal']	= False

		stocks[ticker]['algo_signals'][algo_id]['rsi_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['mfi_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['adx_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['dmi_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['macd_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['chop_init_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['chop_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['supertrend_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['vwap_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['vpt_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['resistance_signal']		= False

		stocks[ticker]['algo_signals'][algo_id]['plus_di_crossover']		= False
		stocks[ticker]['algo_signals'][algo_id]['minus_di_crossover']		= False
		stocks[ticker]['algo_signals'][algo_id]['macd_crossover']		= False
		stocks[ticker]['algo_signals'][algo_id]['macd_avg_crossover']		= False

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

		# Export pricehistory
		try:
			fname = './' + str(args.tx_log_dir) + '/' + str(ticker) + '.pickle'
			with open(fname, 'wb') as handle:
				pickle.dump(stocks[ticker]['pricehistory'], handle)
				handle.flush()

		except Exception as e:
			print('Warning: Unable to write to file ' + str(fname) + ': ' + str(e), file=sys.stderr)
			pass

		# Export 5-minute pricehistory
		try:
			fname = './' + str(args.tx_log_dir) + '/' + str(ticker) + '_5m.pickle'
			with open(fname, 'wb') as handle:
				pickle.dump(stocks[ticker]['pricehistory_5m'], handle)
				handle.flush()

		except Exception as e:
			print('Warning: Unable to write to file ' + str(fname) + ': ' + str(e), file=sys.stderr)
			pass

	return True


# Main helper function for tda-stochrsi-gobot-v2 that implements the primary stochrsi
#  algorithm along with any secondary algorithms specified.
def stochrsi_gobot( cur_algo=None, debug=False ):

	if not isinstance(cur_algo, dict):
		print('Error: stochrsi_gobot() called without valid cur_algo parameter, stochrsi_gobot() cannot continue.', file=sys.stderr)
		return False

	else:
		# Make sure cur_algo contains an algo_id, which is needed foe the indicator
		#  signals and used everywhere.
		try:
			algo_id	= cur_algo['algo_id']

		except Exception as e:
			print('Error: algo_id not found in cur_algo dictionary, stochrsi_gobot() cannot continue.', file=sys.stderr)
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
		sys.exit(0)

	# Exit if we are not set up to monitor across multiple days
	if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False ):
		if ( args.singleday == False and args.multiday == False ):
			print('Market closed, exiting.')
			signal.raise_signal(signal.SIGTERM)
			sys.exit(0)


	# StochRSI/StochMFI long algorithm
	def get_stoch_signal_long(algo_name=None, ticker=None, cur_k=0, cur_d=0, prev_k=0, prev_d=0, stoch_offset=0, stoch_signal=False, crossover_signal=False, threshold_signal=False, final_signal=False):

		nonlocal stoch_low_limit
		nonlocal stoch_high_limit

		# Monitor K and D
		# A buy signal occurs when an increasing %K line crosses above the %D line in the oversold region,
		#  or if the %K line crosses above the low limit
		if ( cur_k < stoch_low_limit and cur_d < stoch_low_limit ):
			stoch_signal = True

			# Monitor if K and D intersect - this must happen below the rsi_low_limit
			if ( prev_k < prev_d and cur_k >= cur_d ):
				print(  '(' + str(ticker) + ') ' + str(algo_name) + ' CROSSOVER SIGNAL: K value passed above the D value in the low_limit region (' +
					str(round(prev_k, 2)) + ' / ' + str(round(cur_k, 2)) + ' / ' + str(round(prev_d, 2)) + ' / ' + str(round(cur_d, 2)) + ')' )
				crossover_signal = True

		# Cancel the crossover signal if K wanders back below D
		if ( crossover_signal == True ):
			if ( prev_k > prev_d and cur_k <= cur_d ):
				print( '(' + str(ticker) + ') ' + str(algo_name) + ' CROSSOVER SIGNAL CANCELED: K moved back below D' )
				crossover_signal = False

		if ( stoch_signal == True ):

			# If stochrsi signal was triggered, monitor K to see if it breaks up above stoch_default_low_limit
			if ( prev_k < stoch_default_low_limit and cur_k > prev_k ):
				if ( cur_k >= stoch_default_low_limit ):
					print(  '(' + str(ticker) + ') ' + str(algo_name) + ' THRESHOLD SIGNAL: K value passed above the low_limit threshold (' +
						str(round(prev_k, 2)) + ' / ' + str(round(cur_k, 2)) + ' / ' + str(round(prev_d, 2)) + ' / ' + str(round(cur_d, 2)) + ')' )
					threshold_signal = True

			if ( crossover_signal == True or threshold_signal == True ):
				if ( cur_k - cur_d >= stoch_offset ):
					print(  '(' + str(ticker) + ') BUY SIGNAL: ' + str(algo_name) + ': crossover_signal: ' + str(crossover_signal) +
						' / threshold_signal: ' + str(threshold_signal) )
					final_signal = True

		return stoch_signal, crossover_signal, threshold_signal, final_signal


	# StochRSI/StochMFI short algorithm
	def get_stoch_signal_short(algo_name=None, ticker=None, cur_k=0, cur_d=0, prev_k=0, prev_d=0, stoch_offset=0, stoch_signal=False, crossover_signal=False, threshold_signal=False, final_signal=False):

		nonlocal stoch_low_limit
		nonlocal stoch_high_limit

		# Monitor K and D
		# A short signal occurs when an decreasing %K line crosses below the %D line in the overbought region,
		#  or if the %K line crosses below the high limit
		if ( cur_k > stoch_high_limit and cur_d > stoch_high_limit ):
			stoch_signal = True

			# Monitor if K and D intersect - this must happen above the rsi_high_limit
			if ( prev_k > prev_d and cur_k <= cur_d ):
				print(  '(' + str(ticker) + ') ' + str(algo_name) + ' CROSSOVER SIGNAL: K value passed below the D value in the high_limit region (' +
					str(round(prev_k, 2)) + ' / ' + str(round(cur_k, 2)) + ' / ' + str(round(prev_d, 2)) + ' / ' + str(round(cur_d, 2)) + ')' )
				crossover_signal = True

		# Cancel the crossover signal if K wanders back below D
		if ( crossover_signal == True ):
			if ( prev_k < prev_d and cur_k >= cur_d ):
				print( '(' + str(ticker) + ') ' + str(algo_name) + ' CROSSOVER SIGNAL CANCELED: K moved back above D' )
				crossover_signal = False

		if ( stoch_signal == True ):

			# If stochrsi signal was triggered, monitor K to see if it breaks up below stoch_default_high_limit
			if ( prev_k > stoch_default_high_limit and cur_k < prev_k ):
				if ( cur_k <= stoch_default_high_limit ):
					print(  '(' + str(ticker) + ') ' + str(algo_name) + ' THRESHOLD SIGNAL: K value passed below the high_limit threshold (' +
						str(round(prev_k, 2)) + ' / ' + str(round(cur_k, 2)) + ' / ' + str(round(prev_d, 2)) + ' / ' + str(round(cur_d, 2)) + ')' )
					threshold_signal = True

			if ( crossover_signal == True or threshold_signal == True ):
				if ( cur_d - cur_k >= stoch_offset ):
					print(  '(' + str(ticker) + ') SHORT SIGNAL: ' + str(algo_name) + ': crossover_signal: ' + str(crossover_signal) +
						' / threshold_signal: ' + str(threshold_signal) )
					final_signal = True

		return stoch_signal, crossover_signal, threshold_signal, final_signal


	# Chop Index algorithm
	def get_chop_signal(simple=False, prev_chop=-1, cur_chop=-1, chop_init_signal=False, chop_signal=False):

		nonlocal cur_algo

		chop_high_limit = cur_algo['chop_high_limit']
		chop_low_limit = cur_algo['chop_low_limit']

		if ( simple == True ):
			# Chop simple algo can be used as a weak signal to help confirm trendiness,
			#  but no crossover from high->low is required
			if ( cur_chop < chop_high_limit and cur_chop > chop_low_limit ):
				chop_init_signal = True
				chop_signal = True
			elif ( cur_chop > chop_high_limit or cur_chop < chop_low_limit ):
				chop_init_signal = False
				chop_signal = False

		else:
			if ( prev_chop > chop_high_limit and cur_chop <= chop_high_limit ):
				chop_init_signal = True

			if ( chop_init_signal == True and chop_signal == False ):
				if ( cur_chop <= default_chop_high_limit ):
					chop_signal = True

			if ( chop_signal == True ):
				if ( cur_chop > default_chop_high_limit ):
					chop_init_signal = False
					chop_signal = False

				elif ( prev_chop < chop_low_limit and cur_chop < chop_low_limit ):
					if ( cur_chop > prev_chop ):
						# Trend may be reversing, cancel the signal
						chop_init_signal = False
						chop_signal = False

		return chop_init_signal, chop_signal


	# Supertrend Indicator
	def get_supertrend_signal(short=False, cur_close=-1, prev_close=-1, cur_supertrend=-1, prev_supertrend=-1, supertrend_signal=False):

		# Short signal
		if ( prev_supertrend <= prev_close and cur_supertrend > cur_close ):
			supertrend_signal = False if ( short==False ) else True

		# Long signal
		elif ( prev_supertrend >= prev_close and cur_supertrend < cur_close ):
			supertrend_signal = True if ( short==False ) else False

		return supertrend_signal


	##########################################################################################
	# Iterate through the stock tickers, calculate the stochRSI, and make buy/sell decisions
	for ticker in stocks.keys():

		# Initialize some local variables
		percent_change	= 0
		net_change	= 0

		min_intra_natr	= cur_algo['min_intra_natr']
		max_intra_natr	= cur_algo['max_intra_natr']
		min_daily_natr	= cur_algo['min_daily_natr']
		max_daily_natr	= cur_algo['max_daily_natr']

		# Skip this ticker if it has been marked as invalid
		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Skip this ticker if it is not listed in this algorithm's per-algo valid_tickers[]
		if ( len(cur_algo['valid_tickers']) != 0 ):
			if ( ticker not in cur_algo['valid_tickers'] ):
				continue

		# Skip this ticker if it conflicts with a per-algo min/max_daily_natr configuration
		if ( min_daily_natr != None and stocks[ticker]['natr_daily'] < min_daily_natr ):
			continue
		if ( max_daily_natr != None and stocks[ticker]['natr_daily'] > max_daily_natr ):
			continue


		# Get stochastic RSI
		t_rsi_period		= cur_algo['rsi_period'] * stocks[ticker]['period_multiplier']
		t_stochrsi_period	= cur_algo['stochrsi_period'] * stocks[ticker]['period_multiplier']
		t_rsi_k_period		= cur_algo['rsi_k_period'] * stocks[ticker]['period_multiplier']

		t_stochmfi_period	= cur_algo['stochmfi_period'] * stocks[ticker]['period_multiplier']
		t_mfi_k_period		= cur_algo['mfi_k_period'] * stocks[ticker]['period_multiplier']

		try:
			if ( cur_algo['primary_stochrsi'] == True ):
				stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi( stocks[ticker]['pricehistory'], rsi_period=t_rsi_period, stochrsi_period=t_stochrsi_period, type=rsi_type,
											slow_period=cur_algo['rsi_slow'], rsi_k_period=t_rsi_k_period, rsi_d_period=cur_algo['rsi_d_period'], debug=False )

			elif ( cur_algo['primary_stochmfi'] == True ):
				rsi_k, rsi_d = tda_gobot_helper.get_stochmfi(   stocks[ticker]['pricehistory'], mfi_period=t_stochmfi_period, mfi_k_period=t_mfi_k_period,
										slow_period=cur_algo['mfi_slow'], mfi_d_period=cur_algo['mfi_d_period'], debug=False )
				stochrsi = rsi_k

			else:
				return False

		except Exception as e:
			print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

		if ( isinstance(stochrsi, bool) and stochrsi == False ):
			print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
			continue

		stocks[ticker]['cur_rsi_k']	= float( rsi_k[-1] )
		stocks[ticker]['cur_rsi_d']	= float( rsi_d[-1] )
		stocks[ticker]['prev_rsi_k']	= float( rsi_k[-2] )
		stocks[ticker]['prev_rsi_d']	= float( rsi_d[-2] )

		# Get secondary stochastic indicators
		# StochRSI with 5-minute candles
		if ( cur_algo['stochrsi_5m'] == True ):
			stochrsi_5m	= []
			rsi_k_5m	= []
			rsi_d_5m	= []
			try:
				stochrsi_5m, rsi_k_5m, rsi_d_5m = tda_gobot_helper.get_stochrsi( stocks[ticker]['pricehistory_5m'], rsi_period=cur_algo['rsi_period'],
												 stochrsi_period=cur_algo['stochrsi_5m_period'], type=rsi_type, slow_period=cur_algo['rsi_slow'],
												 rsi_k_period=cur_algo['rsi_k_5m_period'], rsi_d_period=cur_algo['rsi_d_period'], debug=False )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(stochrsi_5m, bool) and stochrsi_5m == False ):
				print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_rsi_k_5m']	= float( rsi_k_5m[-1] )
			stocks[ticker]['cur_rsi_d_5m']	= float( rsi_d_5m[-1] )
			stocks[ticker]['prev_rsi_k_5m']	= float( rsi_k_5m[-2] )
			stocks[ticker]['prev_rsi_d_5m']	= float( rsi_d_5m[-2] )

		# StochMFI
		if ( cur_algo['stochmfi'] == True ):
			mfi_k = []
			mfi_d = []
			try:
				mfi_k, mfi_d = tda_gobot_helper.get_stochmfi( stocks[ticker]['pricehistory'], mfi_period=cur_algo['stochmfi_period'], mfi_k_period=cur_algo['mfi_k_period'],
									      slow_period=cur_algo['mfi_slow'], mfi_d_period=cur_algo['mfi_d_period'], debug=False )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(mfi_k, bool) and mfi_k == False ):
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_mfi_k']	= float( mfi_k[-1] )
			stocks[ticker]['cur_mfi_d']	= float( mfi_d[-1] )
			stocks[ticker]['prev_mfi_k']	= float( mfi_k[-2] )
			stocks[ticker]['prev_mfi_d']	= float( mfi_d[-2] )

		# StochMFI with 5-minute candles
		if ( cur_algo['stochmfi_5m'] == True ):
			mfi_k_5m = []
			mfi_d_5m = []
			try:
				mfi_k_5m, mfi_d_5m = tda_gobot_helper.get_stochmfi( stocks[ticker]['pricehistory_5m'], mfi_period=cur_algo['stochmfi_5m_period'], mfi_k_period=cur_algo['mfi_k_5m_period'],
										    slow_period=cur_algo['mfi_slow'], mfi_d_period=cur_algo['mfi_d_period'], debug=False )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(mfi_k_5m, bool) and mfi_k_5m == False ):
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_mfi_k_5m']	= float( mfi_k_5m[-1] )
			stocks[ticker]['cur_mfi_d_5m']	= float( mfi_d_5m[-1] )
			stocks[ticker]['prev_mfi_k_5m']	= float( mfi_k_5m[-2] )
			stocks[ticker]['prev_mfi_d_5m']	= float( mfi_d_5m[-2] )


		# RSI
		if ( cur_algo['rsi'] == True ):
			t_rsi_period = cur_algo['rsi_period'] * stocks[ticker]['period_multiplier']

			try:
				rsi = tda_gobot_helper.get_rsi(stocks[ticker]['pricehistory'], t_rsi_period, rsi_type, debug=False)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_rsi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(rsi, bool) and rsi == False ):
				print('Error: stochrsi_gobot(): get_rsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_rsi'] = float( rsi[-1] )
			stocks[ticker]['prev_rsi'] = float( rsi[-2] )

		# Average True Range (ATR/NATR)
		atr = []
		natr = []
		try:
			atr, natr = tda_gobot_helper.get_atr( pricehistory=stocks[ticker]['pricehistory_5m'], period=cur_algo['atr_period'] )

		except Exception as e:
			print('Error: stochrsi_gobot(' + str(ticker) + '): get_atr(): ' + str(e), file=sys.stderr)
			continue

		stocks[ticker]['cur_atr']  = float( atr[-1] )
		stocks[ticker]['cur_natr'] = float( natr[-1] )

		# MFI
		if ( cur_algo['mfi'] == True ):

			t_mfi_period = cur_algo['mfi_period'] * stocks[ticker]['period_multiplier']

			mfi = []
			try:
				mfi = tda_gobot_helper.get_mfi(stocks[ticker]['pricehistory'], period=t_mfi_period)

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_mfi(): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_mfi']  = float( mfi[-1] )
			stocks[ticker]['prev_mfi'] = float( mfi[-2] )


		# ADX, +DI, -DI
		if ( cur_algo['adx'] == True or cur_algo['dmi'] == True or cur_algo['dmi_simple'] == True ):

			t_adx_period = cur_algo['adx_period'] * stocks[ticker]['period_multiplier']
			t_di_period = cur_algo['di_period'] * stocks[ticker]['period_multiplier']

			adx = []
			plus_di = []
			minus_di = []
			try:
				adx, plus_di, minus_di = tda_gobot_helper.get_adx(stocks[ticker]['pricehistory'], period=t_di_period)
				adx, plus_di_adx, minus_di_adx = tda_gobot_helper.get_adx(stocks[ticker]['pricehistory'], period=t_adx_period)

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_adx(): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_adx']	= float( adx[-1] )
			stocks[ticker]['cur_plus_di']	= float( plus_di[-1] )
			stocks[ticker]['cur_minus_di']	= float( minus_di[-1] )
			stocks[ticker]['prev_plus_di']	= float( plus_di[-2] )
			stocks[ticker]['prev_minus_di']	= float( minus_di[-2] )

		# Aroon Oscillator
		if ( cur_algo['aroonosc'] == True ):

			# SAZ - 2021-08-29: Higher volatility stocks seem to work better with a
			#  longer Aroon Oscillator value.
			stocks[ticker]['aroonosc_period'] = cur_algo['aroonosc_period']
			if ( stocks[ticker]['cur_natr'] > args.aroonosc_alt_threshold ):
				stocks[ticker]['aroonosc_period'] = args.aroonosc_alt_period

			t_aroonosc_period = stocks[ticker]['aroonosc_period'] * stocks[ticker]['period_multiplier']

			aroonosc = []
			try:
				aroonosc = tda_gobot_helper.get_aroon_osc(stocks[ticker]['pricehistory'], period=t_aroonosc_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_aroon_osc(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_aroonosc'] = float( aroonosc[-1] )

			# Enable macd_simple if --aroonosc_with_macd_simple is True
			# We do this here just so that the MACD values will be calculated below, but the buy/short logic
			#  later on will determine if MACD is actually used to make a decision.
			if ( args.aroonosc_with_macd_simple == True ):
				cur_algo['macd_simple'] = True

		# MACD - 48, 104, 36
		if ( cur_algo['macd'] == True or cur_algo['macd_simple'] == True ):
			macd = []
			macd_signal = []
			macd_histogram = []

			t_macd_short_period = cur_algo['macd_short_period'] * stocks[ticker]['period_multiplier']
			t_macd_long_period = cur_algo['macd_long_period'] * stocks[ticker]['period_multiplier']
			t_macd_signal_period = cur_algo['macd_signal_period'] * stocks[ticker]['period_multiplier']

			try:
				macd, macd_avg, macd_histogram = tda_gobot_helper.get_macd(stocks[ticker]['pricehistory'], short_period=t_macd_short_period, long_period=t_macd_long_period, signal_period=t_macd_signal_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_macd(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_macd']	= float( macd[-1] )
			stocks[ticker]['cur_macd_avg']	= float( macd_avg[-1] )
			stocks[ticker]['prev_macd']	= float( macd[-2] )
			stocks[ticker]['prev_macd_avg']	= float( macd_avg[-2] )

		# Chop Index
		if ( cur_algo['chop_index'] == True or cur_algo['chop_simple'] == True ):
			chop = []
			try:
				chop = tda_gobot_helper.get_chop_index(stocks[ticker]['pricehistory'], period=cur_algo['chop_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_chop_index' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_chop']	= float( chop[-1] )
			stocks[ticker]['prev_chop']	= float( chop[-2] )

		# Supertrend Indicator
		if ( cur_algo['supertrend'] == True ):
			supertrend = []
			try:
				supertrend = tda_gobot_helper.get_supertrend(pricehistory=stocks[ticker]['pricehistory'], atr_period=cur_algo['supertrend_atr_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_supertrend' + str(ticker) + '): ' + str(e), file=sys.stderr)

			stocks[ticker]['cur_supertrend']	= float( supertrend[-1] )
			stocks[ticker]['prev_supertrend']	= float( supertrend[-2] )

		# VWAP
		# Calculate vwap to use as entry or exit algorithm
		if ( cur_algo['vwap'] or args.vwap_exit == True or cur_algo['support_resistance'] == True ):
			vwap = []
			vwap_up = []
			vwap_down = []
			try:
				vwap, vwap_up, vwap_down = tda_gobot_helper.get_vwap( stocks[ticker]['pricehistory'] )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_vwap(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			stocks[ticker]['cur_vwap']	= float( vwap[-1] )
			stocks[ticker]['cur_vwap_up']	= float( vwap_up[-1] )
			stocks[ticker]['cur_vwap_down']	= float( vwap_down[-1] )

		# VPT
		if ( cur_algo['vpt'] == True ):
			vpt = []
			vpt_sma = []
			t_vpt_sma_period = cur_algo['vpt_sma_period'] * stocks[ticker]['period_multiplier']

			try:
				vpt, vpt_sma = tda_gobot_helper.get_vpt(stocks[ticker]['pricehistory'], period=t_vpt_sma_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_vpt(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			stocks[ticker]['cur_vpt']	= float( vpt[-1] )
			stocks[ticker]['prev_vpt']	= float( vpt[-2] )
			stocks[ticker]['cur_vpt_sma']	= float( vpt_sma[-1] )
			stocks[ticker]['prev_vpt_sma']	= float( vpt_sma[-2] )

		# Debug
		if ( debug == True ):
			time_now = datetime.datetime.now( mytimezone )
			print(  '(' + str(ticker) + ') StochRSI Period: ' + str(cur_algo['stochrsi_period']) + ' / Type: ' + str(rsi_type) +
				' / K Period: ' + str(cur_algo['rsi_k_period']) + ' / D Period: ' + str(cur_algo['rsi_d_period']) + ' / Slow Period: ' + str(cur_algo['rsi_slow']) +
				' / High Limit|Low Limit: ' + str(cur_algo['rsi_high_limit']) + '|' + str(cur_algo['rsi_low_limit']) )

			# StochRSI
			print( '(' + str(ticker) + ') Current StochRSI K: ' + str(round(stocks[ticker]['cur_rsi_k'], 2)) +
						' / Previous StochRSI K: ' + str(round(stocks[ticker]['prev_rsi_k'], 2)))
			print( '(' + str(ticker) + ') Current StochRSI D: ' + str(round(stocks[ticker]['cur_rsi_d'], 2)) +
						' / Previous StochRSI D: ' + str(round(stocks[ticker]['prev_rsi_d'], 2)))
			print( '(' + str(ticker) + ') Primary Stochastic Signals: ' +
						str(stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal']) + ' / ' +
						str(stocks[ticker]['algo_signals'][algo_id]['stochrsi_crossover_signal']) + ' / ' +
						str(stocks[ticker]['algo_signals'][algo_id]['stochrsi_threshold_signal']) + ' / ' +
						str(stocks[ticker]['algo_signals'][algo_id]['buy_signal']) )

			# RSI
			if ( cur_algo['rsi'] == True ):
				print('(' + str(ticker) + ') Current RSI: ' + str(round(stocks[ticker]['cur_rsi'], 2)) +
						' / RSI Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['rsi_signal']) )

			# MFI
			if ( cur_algo['mfi'] == True ):
				print('(' + str(ticker) + ') Current MFI: ' + str(round(stocks[ticker]['cur_mfi'], 2)) +
							' / Previous MFI: ' + str(round(stocks[ticker]['prev_mfi'], 2)) +
							' / High Limit|Low Limit: ' + str(cur_algo['mfi_high_limit']) + '|' + str(cur_algo['mfi_low_limit']) +
							' / MFI Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['mfi_signal']) )

			# ATR/NATR
			print('(' + str(ticker) + ') Current ATR/NATR: ' + str(round(stocks[ticker]['cur_atr'], 3)) + ' / ' + str(round(stocks[ticker]['cur_natr'], 3)) +
						' | Daily ATR/NATR: ' + str(round(stocks[ticker]['atr_daily'], 3)) + ' / ' + str(round(stocks[ticker]['natr_daily'], 3)) )

			# ADX
			if ( cur_algo['adx'] == True ):
				print('(' + str(ticker) + ') Current ADX: ' + str(round(stocks[ticker]['cur_adx'], 2)) +
							' / ADX Period: ' + str(cur_algo['adx_period']) +
							' / ADX Threshold: ' + str(cur_algo['adx_threshold']) +
							' / ADX Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['adx_signal']) )

			# PLUS/MINUS DI
			if ( cur_algo['dmi'] == True or cur_algo['dmi_simple'] == True ):
				print('(' + str(ticker) + ') Current PLUS_DI: ' + str(round(stocks[ticker]['cur_plus_di'], 2)) +
							' / Previous PLUS_DI: ' + str(round(stocks[ticker]['prev_plus_di'], 2)))
				print('(' + str(ticker) + ') Current MINUS_DI: ' + str(round(stocks[ticker]['cur_minus_di'], 2)) +
							' / Previous MINUS_DI: ' + str(round(stocks[ticker]['prev_minus_di'], 2)) +
							' / DMI Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['dmi_signal']) )

			# MACD
			if ( cur_algo['macd'] == True or cur_algo['macd_simple'] ):
				print('(' + str(ticker) + ') Current MACD: ' + str(round(stocks[ticker]['cur_macd'], 2)) +
							' / Previous MACD: ' + str(round(stocks[ticker]['prev_macd'], 2)))
				print('(' + str(ticker) + ') Current MACD_AVG: ' + str(round(stocks[ticker]['cur_macd_avg'], 2)) +
							' / Previous MACD_AVG: ' + str(round(stocks[ticker]['prev_macd_avg'], 2)) +
							' / MACD Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['macd_signal']) )

			# AroonOsc
			if ( cur_algo['aroonosc'] == True ):
				print('(' + str(ticker) + ') Current AroonOsc: ' + str(round(stocks[ticker]['cur_aroonosc'], 2)) +
							' / AroonOsc Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal']) )

			# Chop Index
			if ( cur_algo['chop_index'] == True or cur_algo['chop_simple'] ):
				print('(' + str(ticker) + ') Current Chop Index: ' + str(round(stocks[ticker]['cur_chop'], 2)) +
							' / Previous Chop Index: ' + str(round(stocks[ticker]['prev_chop'], 2)) +
							' / Chop Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['chop_signal']) )

			# Supertrend
			if ( cur_algo['supertrend'] == True ):
				print('(' + str(ticker) + ') Current Supertrend: ' + str(round(stocks[ticker]['cur_supertrend'], 2)) +
							' / Previous Supertrend: ' + str(round(stocks[ticker]['prev_supertrend'], 2)) +
							' / Supertrend Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['supertrend_signal']) )

			# VWAP
			if ( cur_algo['vwap'] == True or cur_algo['support_resistance'] == True ):
				print('(' + str(ticker) + ') Current VWAP: ' + str(round(stocks[ticker]['cur_vwap'], 2)) +
							' / Current VWAP_UP: ' + str(round(stocks[ticker]['cur_vwap_up'], 2)) +
							' / Current VWAP_DOWN: ' + str(round(stocks[ticker]['cur_vwap_down'], 2)) +
							' / VWAP Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['vwap_signal']) )

			# VPT
			if ( cur_algo['vpt'] == True ):
				print('(' + str(ticker) + ') Current VPT: ' + str(round(stocks[ticker]['cur_vpt'], 2)) +
							' / Previous VPT: ' + str(round(stocks[ticker]['prev_vpt'], 2)))
				print('(' + str(ticker) + ') Current VPT_SMA: ' + str(round(stocks[ticker]['cur_vpt_sma'], 2)) +
							' / Previous VPT_SMA: ' + str(round(stocks[ticker]['prev_vpt_sma'], 2)) +
							' / VPT Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['vpt_signal']) )

			# Signal mode and multiplier
			print( '(' + str(ticker) + ') Signal Mode: ' + str(stocks[ticker]['algo_signals'][algo_id]['signal_mode']) +
							' / Period Multiplier: ' + str(stocks[ticker]['period_multiplier']) )

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
		signal_mode		= stocks[ticker]['algo_signals'][algo_id]['signal_mode']

		# StochRSI
		cur_rsi_k		= stocks[ticker]['cur_rsi_k']
		prev_rsi_k		= stocks[ticker]['prev_rsi_k']
		cur_rsi_d		= stocks[ticker]['cur_rsi_d']
		prev_rsi_d		= stocks[ticker]['prev_rsi_d']

		cur_rsi_k_5m		= stocks[ticker]['cur_rsi_k_5m']
		prev_rsi_k_5m		= stocks[ticker]['prev_rsi_k_5m']
		cur_rsi_d_5m		= stocks[ticker]['cur_rsi_d_5m']
		prev_rsi_d_5m		= stocks[ticker]['prev_rsi_d_5m']

		# StochMFI
		cur_mfi_k		= stocks[ticker]['cur_mfi_k']
		prev_mfi_k		= stocks[ticker]['prev_mfi_k']
		cur_mfi_d		= stocks[ticker]['cur_mfi_d']
		prev_mfi_d		= stocks[ticker]['prev_mfi_d']

		cur_mfi_k_5m		= stocks[ticker]['cur_mfi_k_5m']
		prev_mfi_k_5m		= stocks[ticker]['prev_mfi_k_5m']
		cur_mfi_d_5m		= stocks[ticker]['cur_mfi_d_5m']
		prev_mfi_d_5m		= stocks[ticker]['prev_mfi_d_5m']

		# Additional Indicators
		cur_rsi			= stocks[ticker]['cur_rsi']
		prev_rsi		= stocks[ticker]['prev_rsi']

		cur_atr			= stocks[ticker]['cur_atr']
		cur_natr		= stocks[ticker]['cur_natr']

		cur_mfi			= stocks[ticker]['cur_mfi']
		prev_mfi		= stocks[ticker]['prev_mfi']

		cur_adx			= stocks[ticker]['cur_adx']

		cur_plus_di		= stocks[ticker]['cur_plus_di']
		prev_plus_di		= stocks[ticker]['prev_plus_di']
		cur_minus_di		= stocks[ticker]['cur_minus_di']
		prev_minus_di		= stocks[ticker]['prev_minus_di']

		cur_macd		= stocks[ticker]['cur_macd']
		prev_macd		= stocks[ticker]['prev_macd']
		cur_macd_avg		= stocks[ticker]['cur_macd_avg']
		prev_macd_avg		= stocks[ticker]['prev_macd_avg']

		cur_aroonosc		= stocks[ticker]['cur_aroonosc']

		cur_chop		= stocks[ticker]['cur_chop']
		prev_chop		= stocks[ticker]['prev_chop']

		cur_supertrend		= stocks[ticker]['cur_supertrend']
		prev_supertrend		= stocks[ticker]['prev_supertrend']

		cur_vwap		= stocks[ticker]['cur_vwap']
		cur_vwap_up		= stocks[ticker]['cur_vwap_up']
		cur_vwap_down		= stocks[ticker]['cur_vwap_down']

		cur_vpt			= stocks[ticker]['cur_vpt']
		prev_vpt		= stocks[ticker]['prev_vpt']
		cur_vpt_sma		= stocks[ticker]['cur_vpt_sma']
		prev_vpt_sma		= stocks[ticker]['prev_vpt_sma']

		# Algo modifiers
		stoch_high_limit	= cur_algo['rsi_high_limit']
		stoch_low_limit		= cur_algo['rsi_low_limit']
		mfi_high_limit		= cur_algo['mfi_high_limit']
		mfi_low_limit		= cur_algo['mfi_low_limit']
		adx_threshold		= cur_algo['adx_threshold']


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
			if ( (tda_gobot_helper.isendofday(75) == True or tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False) and args.multiday == False ):
				print('(' + str(ticker) + ') Market is closed or near closing.')
				reset_signals(ticker)
				continue

			# If args.hold_overnight=False and args.multiday==True, we won't enter any new trades 1-hour before market close
			if ( args.multiday == True and args.hold_overnight == False and tda_gobot_helper.isendofday(75) ):
				reset_signals(ticker)
				continue

			# Extra check to make sure the signals are in the right position based on global short-sell args
			if ( args.shortonly == True ):
				stocks[ticker]['algo_signals'][algo_id]['signal_mode'] = 'short'
				signal_mode = 'short'

			elif ( args.shortonly == False and args.short == False ):
				stocks[ticker]['algo_signals'][algo_id]['signal_mode'] = 'buy'
				signal_mode = 'buy'


		# BUY MODE - looking for a signal to purchase the stock
		if ( signal_mode == 'buy' ):

			# Jump to short mode if StochRSI K and D are already above stoch_high_limit
			# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( (cur_rsi_k >= stoch_default_high_limit and cur_rsi_d >= stoch_default_high_limit) and args.short == True and stocks[ticker]['shortable'] == True ):
				print('(' + str(ticker) + ') StochRSI K and D values already above ' + str(stoch_default_high_limit) + ', switching to short mode.')

				reset_signals(ticker, id=algo_id, signal_mode='short')
				continue

			# PRIMARY STOCHRSI MONITOR
			( stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'],
			  stocks[ticker]['algo_signals'][algo_id]['stochrsi_crossover_signal'],
			  stocks[ticker]['algo_signals'][algo_id]['stochrsi_threshold_signal'],
			  stocks[ticker]['algo_signals'][algo_id]['buy_signal'] ) = get_stoch_signal_long( 'StochRSI', ticker,
													    cur_rsi_k, cur_rsi_d, prev_rsi_k, prev_rsi_d,
													    cur_algo['stochrsi_offset'],
													    stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'],
													    stocks[ticker]['algo_signals'][algo_id]['stochrsi_crossover_signal'],
													    stocks[ticker]['algo_signals'][algo_id]['stochrsi_threshold_signal'],
													    stocks[ticker]['algo_signals'][algo_id]['buy_signal'] )

			# Reset the buy signal if rsi has wandered back above stoch_high_limit
			if ( cur_rsi_k > stoch_signal_cancel_high_limit ):
				if ( stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
					print( '(' + str(ticker) + ') BUY SIGNAL CANCELED: RSI moved back above stoch_high_limit' )

				reset_signals(ticker, algo_id)

			# STOCHRSI with 5-minute candles
			if ( cur_algo['stochrsi_5m'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal'] ) = get_stoch_signal_long( 'StochRSI_5m', ticker,
														cur_rsi_k_5m, cur_rsi_d_5m, prev_rsi_k_5m, prev_rsi_d_5m,
														cur_algo['stochrsi_5m_offset'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_crossover_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_threshold_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal'] )

				if ( cur_rsi_k_5m > stoch_signal_cancel_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_signal']		= False
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_crossover_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_threshold_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal']	= False

			# STOCHMFI MONITOR
			if ( cur_algo['stochmfi'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['stochmfi_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal'] ) = get_stoch_signal_long( 'StochMFI', ticker,
														cur_mfi_k, cur_mfi_d, prev_mfi_k, prev_mfi_d,
														cur_algo['stochmfi_offset'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_crossover_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_threshold_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal'] )

				if ( cur_mfi_k > stoch_signal_cancel_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_signal']		= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_crossover_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_threshold_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal']	= False

			# STOCHMFI with 5-minute candles
			if ( cur_algo['stochmfi_5m'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal'] ) = get_stoch_signal_long( 'StochMFI_5m', ticker,
														cur_mfi_k_5m, cur_mfi_d_5m, prev_mfi_k_5m, prev_mfi_d_5m,
														cur_algo['stochmfi_offset'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_crossover_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_threshold_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal'] )

				if ( cur_mfi_k_5m > stoch_signal_cancel_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_signal']		= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_crossover_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_threshold_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal']	= False


			# Process any secondary indicators
			# RSI
			if ( cur_algo['rsi'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = True
				if ( cur_rsi >= rsi_signal_cancel_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = False
				elif ( prev_rsi > 25 and cur_rsi < 25 ):
					stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = False
				elif ( prev_rsi < 25 and cur_rsi >= 25 ):
					stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = True

			# MFI signal
			if ( cur_algo['mfi'] == True ):
				if ( cur_mfi >= mfi_signal_cancel_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['mfi_signal'] = False
				elif ( prev_mfi > mfi_low_limit and cur_mfi < mfi_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['mfi_signal'] = False
				elif ( prev_mfi < mfi_low_limit and cur_mfi >= mfi_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['mfi_signal'] = True

			# ADX signal
			if ( cur_algo['adx'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['adx_signal'] = False
				if ( cur_adx > adx_threshold ):
					stocks[ticker]['algo_signals'][algo_id]['adx_signal'] = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( cur_algo['dmi'] == True or cur_algo['dmi_simple'] == True ):
				if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
					stocks[ticker]['algo_signals'][algo_id]['plus_di_crossover'] = True
					stocks[ticker]['algo_signals'][algo_id]['minus_di_crossover'] = False

				elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
					stocks[ticker]['algo_signals'][algo_id]['plus_di_crossover'] = False
					stocks[ticker]['algo_signals'][algo_id]['minus_di_crossover'] = True

				stocks[ticker]['algo_signals'][algo_id]['dmi_signal'] = False
				if ( cur_plus_di > cur_minus_di ):
					if ( cur_algo['dmi_simple'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['dmi_signal'] = True
					elif ( stocks[ticker]['algo_signals'][algo_id]['plus_di_crossover'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['dmi_signal'] = True

			# Aroon oscillator signals
			# Values closer to 100 indicate an uptrend
			if ( cur_algo['aroonosc'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal'] = False
				if ( cur_aroonosc > aroonosc_threshold ):
					stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal'] = True

					# Enable macd_simple if the aroon oscillator is less than aroonosc_secondary_threshold
					if ( args.aroonosc_with_macd_simple == True ):
						cur_algo['macd_simple'] = False
						if ( cur_aroonosc <= aroonosc_secondary_threshold ):
							cur_algo['macd_simple'] = True

			# MACD crossover signals
			if ( cur_algo['macd'] == True or cur_algo['macd_simple'] == True ):
				if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
					stocks[ticker]['algo_signals'][algo_id]['macd_crossover'] = True
					stocks[ticker]['algo_signals'][algo_id]['macd_avg_crossover'] = False

				elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
					stocks[ticker]['algo_signals'][algo_id]['macd_crossover'] = False
					stocks[ticker]['algo_signals'][algo_id]['macd_avg_crossover'] = True

				stocks[ticker]['algo_signals'][algo_id]['macd_signal'] = False
				if ( cur_macd > cur_macd_avg and cur_macd - cur_macd_avg > cur_algo['macd_offset'] ):
					if ( cur_algo['macd_simple'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['macd_signal'] = True
					elif ( stocks[ticker]['algo_signals'][algo_id]['macd_crossover'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['macd_signal'] = True

			# Chop Index
			if ( cur_algo['chop_index'] == True or cur_algo['chop_simple'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['chop_init_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['chop_signal'] ) = get_chop_signal(	simple=cur_algo['chop_simple'],
														prev_chop=prev_chop, cur_chop=cur_chop,
														chop_init_signal=stocks[ticker]['algo_signals'][algo_id]['chop_init_signal'],
														chop_signal=stocks[ticker]['algo_signals'][algo_id]['chop_signal'] )

			# Supertrend Indicator
			if ( cur_algo['supertrend'] == True ):

				# Skip supertrend signal if the stock's daily NATR is too low
				if ( stocks[ticker]['natr_daily'] < cur_algo['supertrend_min_natr'] ):
					stocks[ticker]['algo_signals'][algo_id]['supertrend_signal'] = True

				else:
					cur_close	= float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
					prev_close	= float( stocks[ticker]['pricehistory']['candles'][-2]['close'] )
					stocks[ticker]['algo_signals'][algo_id]['supertrend_signal'] = get_supertrend_signal(	short=False, cur_close=cur_close, prev_close=prev_close,
																cur_supertrend=cur_supertrend, prev_supertrend=prev_supertrend,
																supertrend_signal=stocks[ticker]['algo_signals'][algo_id]['supertrend_signal'] )

			# VWAP signal
			# This is the most simple/pessimistic approach right now
			if ( cur_algo['vwap'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['vwap_signal'] = False
				cur_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
				if ( cur_price < cur_vwap ):
					stocks[ticker]['algo_signals'][algo_id]['vwap_signal'] = True

			# VPT
			if ( cur_algo['vpt'] == True ):
				# Buy signal - VPT crosses above vpt_sma
				if ( prev_vpt < prev_vpt_sma and cur_vpt > cur_vpt_sma ):
					stocks[ticker]['algo_signals'][algo_id]['vpt_signal'] = True

				# Cancel signal if VPT crosses back over
				elif ( cur_vpt < cur_vpt_sma ):
					stocks[ticker]['algo_signals'][algo_id]['vpt_signal'] = False

			# Support / Resistance
			if ( cur_algo['support_resistance'] == True and args.no_use_resistance == False ):
				stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = True
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
							if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
								print( '(' + str(ticker) + ') BUY SIGNAL stalled due to PDC resistance - PDC: ' + str(round(stocks[ticker]['previous_day_close'], 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# NATR resistance
				if ( args.use_natr_resistance == True and stocks[ticker]['natr_daily'] != None ):
					if ( cur_price > stocks[ticker]['previous_day_close'] ):
						natr_mod = 1
						if ( stocks[ticker]['natr_daily'] >= 8 ):
							natr_mod = 2

						natr_resistance = ((stocks[ticker]['natr_daily'] / natr_mod) / 100 + 1) * stocks[ticker]['previous_day_close']
						if ( cur_price > natr_resistance ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 12 and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

						if ( abs((cur_price / natr_resistance - 1) * 100) <= price_resistance_pct ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 10 and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# VWAP
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
						abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

					# Current price is very close to VWAP
					# Next check average of last 15 (minute) candles
					avg = 0
					for i in range(15, 0, -1):
						avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
					avg = avg / 15

					# If average was below VWAP then VWAP is resistance
					# If average was above VWAP then VWAP is support
					if ( avg < cur_vwap ):
						if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
							print( '(' + str(ticker) + ') BUY SIGNAL stalled due to VWAP resistance - Current VWAP: ' + str(round(cur_vwap, 5)) + ' / 15-min Avg: ' + str(round(avg, 5)) )

						stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# High of the day (HOD)
				# Skip this check for the first 2.5 hours of the day. The reason for this is
				#  the first 2 hours or so of trading can create small hod/lods, but they
				#  often won't persist. Also, we are more concerned about the slow, low volume
				#  creeps toward HOD/LOD that are often permanent for the day.
				cur_time	= datetime.datetime.fromtimestamp(float(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone)
				cur_day		= cur_time.strftime('%Y-%m-%d')
				cur_hour	= int( cur_time.strftime('%-H') )
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and args.lod_hod_check == True and cur_hour >= 13 ):
					cur_day_start = datetime.datetime.strptime(cur_day + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start = mytimezone.localize(cur_day_start)

					delta = cur_time - cur_day_start
					delta = int( delta.total_seconds() / 60 )

					# Find HOD
					hod = 0
					for i in range (delta, 0, -1):
						if ( float(stocks[ticker]['pricehistory']['candles'][-i]['close']) > hod ):
							hod = float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )

					# If the stock has already hit a high of the day, the next rise will likely be
					#  below HOD. If we are below HOD and less than price_resistance_pct from it
					#  then we should not enter the trade.
					if ( cur_price < hod ):
						if ( abs((cur_price / hod - 1) * 100) <= price_resistance_pct ):
							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# END HOD Check

				# Key Levels
				# Check if price is near historic key level
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True ):
					near_keylevel = False
					for lvl,dt in stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']:
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
							if ( avg < lvl or abs((avg / lvl - 1) * 100) <= price_resistance_pct / 3 ):
								if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
									print( '(' + str(ticker) + ') BUY SIGNAL stalled due to Key Level resistance - KL: ' + str(round(lvl, 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )

								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
								break

					# If keylevel_strict is True then only buy the stock if price is near a key level
					# Otherwise reject this buy to avoid getting chopped around between levels
					if ( args.keylevel_strict == True and near_keylevel == False ):
						if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
							print( '(' + str(ticker) + ') BUY SIGNAL stalled due to keylevel_strict - Current price: ' + str(round(cur_price, 2)) )

						stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# End Key Levels

#				# 20-week high
#				if ( cur_price >= float(stocks[ticker]['twenty_week_high']) ):
#					# This is not a good bet
#					stocks[ticker]['twenty_week_high'] = cur_price
#					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
#
#				elif ( ( abs(cur_price / float(stocks[ticker]['twenty_week_high']) - 1) * 100 ) < 1 ):
#					# Current high is within 1% of 20-week high, not a good bet
#					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):

				stochrsi_5m_signal	= stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal']
				stochmfi_signal		= stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal']
				stochmfi_5m_signal	= stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal']
				rsi_signal		= stocks[ticker]['algo_signals'][algo_id]['rsi_signal']
				mfi_signal		= stocks[ticker]['algo_signals'][algo_id]['mfi_signal']
				adx_signal		= stocks[ticker]['algo_signals'][algo_id]['adx_signal']
				dmi_signal		= stocks[ticker]['algo_signals'][algo_id]['dmi_signal']
				aroonosc_signal		= stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal']
				macd_signal		= stocks[ticker]['algo_signals'][algo_id]['macd_signal']
				chop_signal		= stocks[ticker]['algo_signals'][algo_id]['chop_signal']
				supertrend_signal	= stocks[ticker]['algo_signals'][algo_id]['supertrend_signal']
				vwap_signal		= stocks[ticker]['algo_signals'][algo_id]['vwap_signal']
				vpt_signal		= stocks[ticker]['algo_signals'][algo_id]['vpt_signal']
				resistance_signal	= stocks[ticker]['algo_signals'][algo_id]['resistance_signal']

				stocks[ticker]['final_buy_signal'] = True

				if ( cur_algo['stochrsi_5m'] == True and stochrsi_5m_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['stochmfi'] == True and stochmfi_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['stochmfi_5m'] == True and stochmfi_5m_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['rsi'] == True and rsi_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['mfi'] == True and mfi_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['adx'] == True and adx_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( (cur_algo['dmi'] == True or cur_algo['dmi_simple'] == True) and dmi_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['aroonosc'] == True and aroonosc_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( (cur_algo['macd'] == True or cur_algo['macd_simple'] == True) and macd_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( (cur_algo['chop_index'] == True or cur_algo['chop_simple'] == True) and chop_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['supertrend'] == True and supertrend_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['vwap'] == True and vwap_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['vpt'] == True and vpt_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( (cur_algo['support_resistance'] == True and args.no_use_resistance == False) and resistance_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( min_intra_natr != None and stocks[ticker]['cur_natr'] < min_intra_natr ):
					stocks[ticker]['final_buy_signal'] = False
				if ( max_intra_natr != None and stocks[ticker]['cur_natr'] > max_intra_natr ):
					stocks[ticker]['final_buy_signal'] = False


			# BUY THE STOCK
			if ( stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True and stocks[ticker]['final_buy_signal'] == True ):

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

				# Reset and switch all algos to 'sell' mode for the next loop
				reset_signals(ticker, signal_mode='sell')

				# VARIABLE EXIT
				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( args.variable_exit == True ):
					if ( stocks[ticker]['cur_natr'] < stocks[ticker]['incr_threshold'] ):

						# The normalized ATR is below incr_threshold. This means the stock is less
						#  likely to get to incr_threshold from our purchase price, and is probably
						#  even farther away from exit_percent (if it is set). So we adjust these parameters
						#  to increase the likelihood of a successful trade.
						#
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( stocks[ticker]['incr_threshold'] > stocks[ticker]['cur_natr'] * 2 ):
							stocks[ticker]['incr_threshold'] = stocks[ticker]['cur_natr'] * 2
						else:
							stocks[ticker]['incr_threshold'] = stocks[ticker]['cur_natr']

						if ( stocks[ticker]['decr_threshold'] > stocks[ticker]['cur_natr'] * 2 ):
							stocks[ticker]['decr_threshold'] = stocks[ticker]['cur_natr'] * 2

						if ( stocks[ticker]['exit_percent'] != None ):
							if ( stocks[ticker]['exit_percent'] > stocks[ticker]['cur_natr'] * 4 ):
								stocks[ticker]['exit_percent'] = stocks[ticker]['cur_natr'] * 2

						# We may adjust incr/decr_threshold later as well, so store the original version
						#   for comparison if needed.
						stocks[ticker]['orig_incr_threshold'] = stocks[ticker]['incr_threshold']
						stocks[ticker]['orig_decr_threshold'] = stocks[ticker]['decr_threshold']

				# VARIABLE EXIT


		# SELL MODE - look for a signal to sell the stock
		elif ( signal_mode == 'sell' ):

			# Use either raw open/close data or Heikin Ashi candles
			last_close	= stocks[ticker]['pricehistory']['candles'][-1]['close']
			last_open	= stocks[ticker]['pricehistory']['candles'][-1]['open']
			if ( args.use_ha_exit == True ):
				last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
				last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']

			# First try to get the latest price from the API, and fall back to the last close only if necessary
			last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
			if ( isinstance(last_price, bool) and last_price == False ):

				# This happens often enough that it's worth just trying again before falling back
				#  to the latest candle
				tda_gobot_helper.tdalogin(passcode)
				last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
				if ( isinstance(last_price, bool) and last_price == False ):
					print('Warning: get_lastprice(' + str(ticker) + ') returned False, falling back to latest candle')
					last_price = stocks[ticker]['pricehistory']['candles'][-1]['close']

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

					reset_signals(ticker, signal_mode='buy')
					continue

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60) == True and args.hold_overnight == False ):
				if ( last_price > stocks[ticker]['orig_base_price'] ):
					percent_change = abs( stocks[ticker]['orig_base_price'] / last_price - 1 ) * 100
					if ( percent_change >= args.last_hour_threshold ):
						stocks[ticker]['exit_percent_signal'] = True
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

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
					stocks[ticker]['tx_id']			= random.randint(1000, 9999)
					stocks[ticker]['stock_qty']		= 0
					stocks[ticker]['base_price']		= 0
					stocks[ticker]['orig_base_price']	= 0
					stocks[ticker]['incr_threshold']	= args.incr_threshold
					stocks[ticker]['orig_incr_threshold']	= args.incr_threshold
					stocks[ticker]['decr_threshold']	= args.decr_threshold
					stocks[ticker]['orig_decr_threshold']	= args.decr_threshold
					stocks[ticker]['exit_percent']		= args.exit_percent

					reset_signals(ticker, signal_mode='buy')
					continue


			# If price increases
			elif ( last_price > stocks[ticker]['base_price'] ):
				percent_change = abs( stocks[ticker]['base_price'] / last_price - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

				# Re-set the base_price to the last_price if we increase by incr_threshold or more
				# This way we can continue to ride a price increase until it starts dropping
				if ( percent_change >= stocks[ticker]['incr_threshold'] ):
					stocks[ticker]['base_price'] = last_price
					print('Stock "' + str(ticker) + '" increased above the incr_threshold (' + str(stocks[ticker]['incr_threshold']) + '%), resetting base price to '  + str(last_price))
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Adapt decr_threshold based on changes made by --variable_exit
					if ( stocks[ticker]['incr_threshold'] < args.incr_threshold ):

						# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
						#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
						if ( stocks[ticker]['incr_threshold'] == stocks[ticker]['orig_incr_threshold'] ):
							stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold']
							stocks[ticker]['incr_threshold'] = stocks[ticker]['incr_threshold'] / 2

					else:
						stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold'] / 2

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

			# No price change
			else:
				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

			# END STOPLOSS MONITOR


			# ADDITIONAL EXIT STRATEGIES (exit_percent / vwap_exit)
			# Sell if --exit_percent was set and threshold met
			if ( stocks[ticker]['exit_percent'] != None and last_price > stocks[ticker]['orig_base_price'] ):
				total_percent_change = abs( stocks[ticker]['orig_base_price'] / last_price - 1 ) * 100

				# If exit_percent has been hit, we will sell at the first RED candle
				if ( stocks[ticker]['exit_percent_signal'] == True ):
					if ( last_close < last_open ):
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

				elif ( total_percent_change >= stocks[ticker]['exit_percent'] ):
					stocks[ticker]['exit_percent_signal'] = True

			# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
			if ( args.vwap_exit == True ):
				if ( cur_vwap > stocks[ticker]['orig_base_price'] ):
					if ( last_price >= ((cur_vwap - stocks[ticker]['orig_base_price']) / 2) + stocks[ticker]['orig_base_price'] ):
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

				elif ( cur_vwap < stocks[ticker]['orig_base_price'] ):
					if ( last_price >= ((cur_vwap_up - cur_vwap) / 2) + cur_vwap ):
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True


			# StochRSI MONITOR
			# Do not use stochrsi as an exit signal if exit_percent_signal is triggered. That means we've surpassed the
			# exit_percent threshold and should wait for either a red candle or for decr_threshold to be hit.
			if ( args.variable_exit == False and stocks[ticker]['exit_percent_signal'] == False ):

				# Monitor K and D
				# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region,
				#  or if the %K line crosses below the RSI limit
				if ( cur_rsi_k > stoch_default_high_limit and cur_rsi_d > stoch_default_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'] = True

					# Monitor if K and D intersect
					# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region
					if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
						print(  '(' + str(ticker) + ') SELL SIGNAL: StochRSI K value passed below the D value in the high_limit region (' +
							str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True


				if ( stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'] == True ):
					if ( prev_rsi_k > stoch_default_high_limit and cur_rsi_k <= stoch_default_high_limit ):
						print(  '(' + str(ticker) + ') SELL SIGNAL: StochRSI K value passed below the high_limit threshold (' +
							str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True


			# SELL THE STOCK
			if ( stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == True ):

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
				stocks[ticker]['tx_id']			= random.randint(1000, 9999)
				stocks[ticker]['stock_qty']		= 0
				stocks[ticker]['base_price']		= 0
				stocks[ticker]['orig_base_price']	= 0
				stocks[ticker]['incr_threshold']	= args.incr_threshold
				stocks[ticker]['orig_incr_threshold']	= args.incr_threshold
				stocks[ticker]['decr_threshold']	= args.decr_threshold
				stocks[ticker]['orig_decr_threshold']	= args.decr_threshold
				stocks[ticker]['exit_percent']		= args.exit_percent

				reset_signals(ticker)
				if ( args.short == True and stocks[ticker]['shortable'] == True ):
					reset_signals(ticker, signal_mode='short')
				else:
					reset_signals(ticker, signal_mode='buy')


		# SHORT SELL the stock
		# In this mode we will monitor the RSI and initiate a short sale if the RSI is very high
		elif ( signal_mode == 'short' ):

			# Jump to buy mode if StochRSI K and D are already below stoch_low_limit
			# The intent here is if the bot starts up while the RSI is low we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi_k < stoch_default_low_limit and cur_rsi_d < stoch_default_low_limit and args.shortonly == False ):
				print('(' + str(ticker) + ') StochRSI K and D values already below ' + str(stoch_default_low_limit) + ', switching to buy mode.')
				reset_signals(ticker, id=algo_id, signal_mode='buy')
				continue

			# StochRSI MONITOR
			# PRIMARY STOCHRSI MONITOR
			( stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'],
			  stocks[ticker]['algo_signals'][algo_id]['stochrsi_crossover_signal'],
			  stocks[ticker]['algo_signals'][algo_id]['stochrsi_threshold_signal'],
			  stocks[ticker]['algo_signals'][algo_id]['short_signal'] ) = get_stoch_signal_short( 'StochRSI', ticker,
													cur_rsi_k, cur_rsi_d, prev_rsi_k, prev_rsi_d,
													cur_algo['stochrsi_offset'],
													stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'],
													stocks[ticker]['algo_signals'][algo_id]['stochrsi_crossover_signal'],
													stocks[ticker]['algo_signals'][algo_id]['stochrsi_threshold_signal'],
													stocks[ticker]['algo_signals'][algo_id]['short_signal'] )

			# Reset the short signal if rsi has wandered back below stoch_low_limit
			if ( cur_rsi_k < stoch_signal_cancel_low_limit ):
				if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):
					print( '(' + str(ticker) + ') SHORT SIGNAL CANCELED: RSI moved back below stoch_low_limit' )

				reset_signals(ticker, algo_id)

			# STOCHRSI with 5-minute candles
			if ( cur_algo['stochrsi_5m'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal'] ) = get_stoch_signal_short( 'StochRSI_5m', ticker,
														cur_rsi_k_5m, cur_rsi_d_5m, prev_rsi_k_5m, prev_rsi_d_5m,
														cur_algo['stochrsi_5m_offset'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_crossover_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_threshold_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal'] )

				if ( cur_rsi_k_5m < stoch_signal_cancel_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_signal']		= False
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_crossover_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_threshold_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal']	= False

			# STOCHMFI MONITOR
			if ( cur_algo['stochmfi'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['stochmfi_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal'] ) = get_stoch_signal_short( 'StochMFI', ticker,
														cur_mfi_k, cur_mfi_d, prev_mfi_k, prev_mfi_d,
														cur_algo['stochmfi_offset'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_crossover_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_threshold_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal'] )

				if ( cur_mfi_k < stoch_signal_cancel_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_signal']		= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_crossover_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_threshold_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal']	= False

			# STOCHMFI with 5-minute candles
			if ( cur_algo['stochmfi_5m'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal'] ) = get_stoch_signal_short( 'StochMFI_5m', ticker,
														cur_mfi_k_5m, cur_mfi_d_5m, prev_mfi_k_5m, prev_mfi_d_5m,
														cur_algo['stochmfi_offset'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_crossover_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_threshold_signal'],
														stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal'] )

				if ( cur_mfi_k_5m < stoch_signal_cancel_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_signal']		= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_crossover_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_threshold_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal']	= False


			# Secondary Indicators
			# RSI
			if ( cur_algo['rsi'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = False
				if ( cur_rsi <= rsi_signal_cancel_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = False
				elif ( prev_rsi < 75 and cur_rsi > 75 ):
					stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = False
				elif ( prev_rsi > 75 and cur_rsi <= 75 ):
					stocks[ticker]['algo_signals'][algo_id]['rsi_signal'] = True

			# MFI signal
			if ( cur_algo['mfi'] == True ):
				if ( cur_mfi <= mfi_signal_cancel_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['mfi_signal'] = False
				elif ( prev_mfi < mfi_high_limit and cur_mfi > mfi_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['mfi_signal'] = False
				elif ( prev_mfi > mfi_high_limit and cur_mfi <= mfi_high_limit ):
					stocks[ticker]['algo_signals'][algo_id]['mfi_signal'] = True

			# ADX signal
			if ( cur_algo['adx'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['adx_signal'] = False
				if ( cur_adx > adx_threshold ):
					stocks[ticker]['algo_signals'][algo_id]['adx_signal'] = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( cur_algo['dmi'] == True or cur_algo['dmi_simple'] == True ):
				if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
					stocks[ticker]['algo_signals'][algo_id]['plus_di_crossover'] = True
					stocks[ticker]['algo_signals'][algo_id]['minus_di_crossover'] = False

				elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
					stocks[ticker]['algo_signals'][algo_id]['plus_di_crossover'] = False
					stocks[ticker]['algo_signals'][algo_id]['minus_di_crossover'] = True

				stocks[ticker]['algo_signals'][algo_id]['dmi_signal'] = False
				if ( cur_plus_di < cur_minus_di ):
					if ( cur_algo['dmi_simple'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['dmi_signal'] = True
					elif ( stocks[ticker]['algo_signals'][algo_id]['minus_di_crossover'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['dmi_signal'] = True

			# Aroon oscillator signals
			# Values closer to -100 indicate a downtrend
			if ( cur_algo['aroonosc'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal'] = False
				if ( cur_aroonosc < -aroonosc_threshold ):
					stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal'] = True

					# Enable macd_simple if the aroon oscillator is less than aroonosc_secondary_threshold
					if ( args.aroonosc_with_macd_simple == True ):
						cur_algo['macd_simple'] = False
						if ( cur_aroonosc >= -aroonosc_secondary_threshold ):
							cur_algo['macd_simple'] = True

			# MACD crossover signals
			if ( cur_algo['macd'] == True or cur_algo['macd_simple'] == True ):
				if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
					stocks[ticker]['algo_signals'][algo_id]['macd_crossover'] = True
					stocks[ticker]['algo_signals'][algo_id]['macd_avg_crossover'] = False

				elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
					stocks[ticker]['algo_signals'][algo_id]['macd_crossover'] = False
					stocks[ticker]['algo_signals'][algo_id]['macd_avg_crossover'] = True

				stocks[ticker]['algo_signals'][algo_id]['macd_signal'] = False
				if ( cur_macd < cur_macd_avg and cur_macd_avg - cur_macd > cur_algo['macd_offset'] ):
					if ( cur_algo['macd_simple'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['macd_signal'] = True
					elif ( stocks[ticker]['algo_signals'][algo_id]['macd_avg_crossover'] == True ):
						stocks[ticker]['algo_signals'][algo_id]['macd_signal'] = True

			# Chop Index
			if ( cur_algo['chop_index'] == True or cur_algo['chop_simple'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['chop_init_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['chop_signal'] ) = get_chop_signal(   simple=cur_algo['chop_simple'],
														prev_chop=prev_chop, cur_chop=cur_chop,
														chop_init_signal=stocks[ticker]['algo_signals'][algo_id]['chop_init_signal'],
														chop_signal=stocks[ticker]['algo_signals'][algo_id]['chop_signal'] )

			# Supertrend Indicator
			if ( cur_algo['supertrend'] == True ):

				# Skip supertrend signal if the stock's daily NATR is too low
				if ( stocks[ticker]['natr_daily'] < cur_algo['supertrend_min_natr'] ):
					stocks[ticker]['algo_signals'][algo_id]['supertrend_signal'] = True

				else:
					cur_close	= float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
					prev_close	= float( stocks[ticker]['pricehistory']['candles'][-2]['close'] )
					stocks[ticker]['algo_signals'][algo_id]['supertrend_signal'] = get_supertrend_signal(	short=True, cur_close=cur_close, prev_close=prev_close,
																cur_supertrend=cur_supertrend, prev_supertrend=prev_supertrend,
																supertrend_signal=stocks[ticker]['algo_signals'][algo_id]['supertrend_signal'] )

			# VWAP signal
			# This is the most simple/pessimistic approach right now
			if ( cur_algo['vwap'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['vwap_signal'] = False
				cur_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
				if ( cur_price > cur_vwap ):
					stocks[ticker]['algo_signals'][algo_id]['vwap_signal'] = True

			# VPT
			if ( cur_algo['vpt'] == True ):
				# Short signal - VPT crosses below vpt_sma
				if ( prev_vpt > prev_vpt_sma and cur_vpt < cur_vpt_sma ):
					stocks[ticker]['algo_signals'][algo_id]['vpt_signal'] = True

				# Cancel signal if VPT crosses back over
				elif ( cur_vpt > cur_vpt_sma ):
					stocks[ticker]['algo_signals'][algo_id]['vpt_signal'] = False

			# Support / Resistance
			if ( cur_algo['support_resistance'] == True and args.no_use_resistance == False ):
				stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = True
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
							if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True and debug == True ):
								print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to PDC resistance - PDC: ' + str(round(stocks[ticker]['previous_day_close'], 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# VWAP
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
						abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

					# Current price is very close to VWAP
					# Next check average of last 15 (minute) candles
					avg = 0
					for i in range(15, 0, -1):
						avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
					avg = avg / 15

					# If average was below VWAP then VWAP is resistance (good for short)
					# If average was above VWAP then VWAP is support (bad for short)
					if ( avg > cur_vwap ):
						if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True and debug == True ):
							print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to VWAP resistance - Current VWAP: ' + str(round(cur_vwap, 5)) + ' / 15-min Avg: ' + str(round(avg, 5)) )

						stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# Low of the day (LOD)
				# Skip this check for the first 1.5 hours of the day. The reason for this is
				#  the first 1-2.5 hours or so of trading can create small hod/lods, but they
				#  often won't persist. Also, we are more concerned about the slow, low volume
				#  creeps toward HOD/LOD that are often permanent for the day.
				cur_time	= datetime.datetime.fromtimestamp(float(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone)
				cur_day		= cur_time.strftime('%Y-%m-%d')
				cur_hour	= int( cur_time.strftime('%-H') )
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and args.lod_hod_check == True and cur_hour >= 13 ):

					cur_day_start = datetime.datetime.strptime(cur_day + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start = mytimezone.localize(cur_day_start)

					delta = cur_time - cur_day_start
					delta = int( delta.total_seconds() / 60 )

					# Find LOD
					lod = 9999
					for i in range (delta, 0, -1):
						if ( float(stocks[ticker]['pricehistory']['candles'][-i]['close']) < lod ):
							lod = float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )

					# If the stock has already hit a low of the day, the next decrease will likely be
					#  above LOD. If we are above LOD and less than price_resistance_pct from it
					#  then we should not enter the trade.
					if ( cur_price > lod ):
						if ( abs((lod / cur_price - 1) * 100) <= price_resistance_pct ):
							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# END HOD Check
				# Key Levels
				# Check if price is near historic key level
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True ):
					near_keylevel = False
					for lvl,dt in stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']:
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
							if ( avg > lvl or abs((avg / lvl - 1) * 100) <= price_resistance_pct / 3 ):
								if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True and debug == True ):
									print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to Key Level resistance - KL: ' + str(round(lvl, 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )

								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
								break

					# If keylevel_strict is True then only short the stock if price is near a key level
					# Otherwise reject this short altogether to avoid getting chopped around between levels
					if ( args.keylevel_strict == True and near_keylevel == False ):
						if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True and debug == True ):
							print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to keylevel_strict - Current price: ' + str(round(cur_price, 2)) )

						stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# End Key Levels

#				# 20-week low
#				if ( cur_price <= float(stocks[ticker]['twenty_week_low']) ):
#					# This is not a good bet
#					stocks[ticker]['twenty_week_low'] = cur_price
#					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
#
#				elif ( ( abs(float(stocks[ticker]['twenty_week_low']) / float(cur_price) - 1) * 100 ) < 1 ):
#					# Current low is within 1% of 20-week low, not a good bet
#					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

			# Resolve the primary stochrsi short_signal with the secondary indicators
			if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):

				stochrsi_5m_signal	= stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal']
				stochmfi_signal		= stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal']
				stochmfi_5m_signal	= stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal']
				rsi_signal		= stocks[ticker]['algo_signals'][algo_id]['rsi_signal']
				mfi_signal		= stocks[ticker]['algo_signals'][algo_id]['mfi_signal']
				adx_signal		= stocks[ticker]['algo_signals'][algo_id]['adx_signal']
				dmi_signal		= stocks[ticker]['algo_signals'][algo_id]['dmi_signal']
				aroonosc_signal		= stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal']
				macd_signal		= stocks[ticker]['algo_signals'][algo_id]['macd_signal']
				chop_signal		= stocks[ticker]['algo_signals'][algo_id]['chop_signal']
				supertrend_signal	= stocks[ticker]['algo_signals'][algo_id]['supertrend_signal']
				vwap_signal		= stocks[ticker]['algo_signals'][algo_id]['vwap_signal']
				vpt_signal		= stocks[ticker]['algo_signals'][algo_id]['vpt_signal']
				resistance_signal	= stocks[ticker]['algo_signals'][algo_id]['resistance_signal']

				stocks[ticker]['final_short_signal'] = True

				if ( cur_algo['stochrsi_5m'] == True and stochrsi_5m_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['stochmfi'] == True and stochmfi_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['stochmfi_5m'] == True and stochmfi_5m_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['rsi'] == True and rsi_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['mfi'] == True and mfi_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['adx'] == True and adx_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( (cur_algo['dmi'] == True or cur_algo['dmi_simple'] == True) and dmi_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['aroonosc'] == True and aroonosc_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( (cur_algo['macd'] == True or cur_algo['macd_simple'] == True) and macd_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( (cur_algo['chop_index'] == True or cur_algo['chop_simple'] == True) and chop_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['supertrend'] == True and supertrend_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['vwap'] == True and vwap_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['vpt'] == True and vpt_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( (cur_algo['support_resistance'] == True and args.no_use_resistance == False) and resistance_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( min_intra_natr != None and stocks[ticker]['cur_natr'] < min_intra_natr ):
					stocks[ticker]['final_short_signal'] = False
				if ( max_intra_natr != None and stocks[ticker]['cur_natr'] > max_intra_natr ):
					stocks[ticker]['final_short_signal'] = False


			# SHORT THE STOCK
			if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True and stocks[ticker]['final_short_signal'] == True ):

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

								reset_signals(ticker, signal_mode='buy')
								stocks[ticker]['shortable'] = False
								stocks[ticker]['stock_qty'] = 0
								continue

					try:
						stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						stocks[ticker]['orig_base_price'] = last_price

				else:
					print('Stock ' + str(ticker) + ' not shorted because market is closed.')

					stocks[ticker]['stock_qty'] = 0
					reset_signals(ticker)
					if ( args.shortonly == False ):
						reset_signals(ticker, signal_mode='buy')

					continue

				net_change = 0
				stocks[ticker]['base_price'] = stocks[ticker]['orig_base_price']

				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=False)

				reset_signals(ticker, signal_mode='buy_to_cover')


				# VARIABLE EXIT
				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( args.variable_exit == True ):
					if ( stocks[ticker]['cur_natr'] < stocks[ticker]['incr_threshold'] ):

						# The normalized ATR is below incr_threshold. This means the stock is less
						#  likely to get to incr_threshold from our purchase price, and is probably
						#  even farther away from exit_percent (if it is set). So we adjust these parameters
						#  to increase the likelihood of a successful trade.
						#
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( stocks[ticker]['incr_threshold'] > stocks[ticker]['cur_natr'] * 2 ):
							stocks[ticker]['incr_threshold'] = stocks[ticker]['cur_natr'] * 2
						else:
							stocks[ticker]['incr_threshold'] = stocks[ticker]['cur_natr']

						if ( stocks[ticker]['decr_threshold'] > stocks[ticker]['cur_natr'] * 2 ):
							stocks[ticker]['decr_threshold'] = stocks[ticker]['cur_natr'] * 2

						if ( stocks[ticker]['exit_percent'] != None ):
							if ( stocks[ticker]['exit_percent'] > stocks[ticker]['cur_natr'] * 4 ):
								stocks[ticker]['exit_percent'] = stocks[ticker]['cur_natr'] * 2

						# We may adjust incr/decr_threshold later as well, so store the original version
						#   for comparison if needed.
						stocks[ticker]['orig_incr_threshold'] = stocks[ticker]['incr_threshold']
						stocks[ticker]['orig_decr_threshold'] = stocks[ticker]['decr_threshold']

				# VARIABLE EXIT


		# BUY_TO_COVER a previous short sale
		# This mode must always follow a previous "short" signal. We will monitor the RSI and initiate
		#   a buy-to-cover transaction to cover a previous short sale if the RSI if very low. We also
		#   need to monitor stoploss in case the stock rises above a threshold.
		elif ( signal_mode == 'buy_to_cover' ):

			# Use either raw open/close data or Heikin Ashi candles
			last_close	= stocks[ticker]['pricehistory']['candles'][-1]['close']
			last_open	= stocks[ticker]['pricehistory']['candles'][-1]['open']
			if ( args.use_ha_exit == True ):
				last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
				last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']

			# First try to get the latest price from the API, and fall back to the last close only if necessary
			last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
			if ( isinstance(last_price, bool) and last_price == False ):

				# This happens often enough that it's worth just trying again before falling back
				#  to the latest candle
				tda_gobot_helper.tdalogin(passcode)
				last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
				if ( isinstance(last_price, bool) and last_price == False ):
					print('Warning: get_lastprice(' + str(ticker) + ') returned False, falling back to latest candle')
					last_price = float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )

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

					stocks[ticker]['tx_id']			= random.randint(1000, 9999)
					stocks[ticker]['stock_qty']		= 0
					stocks[ticker]['base_price']		= 0
					stocks[ticker]['orig_base_price']	= 0
					stocks[ticker]['incr_threshold']	= args.incr_threshold
					stocks[ticker]['orig_incr_threshold']	= args.incr_threshold
					stocks[ticker]['decr_threshold']	= args.decr_threshold
					stocks[ticker]['orig_decr_threshold']	= args.decr_threshold
					stocks[ticker]['exit_percent']		= args.exit_percent

					if ( args.shortonly == True ):
						reset_signals(ticker, signal_mode='short')
					else:
						reset_signals(ticker, signal_mode='buy')

					continue

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60) == True and args.hold_overnight == False ):
				if ( last_price < stocks[ticker]['orig_base_price'] ):
					percent_change = abs( last_price / stocks[ticker]['orig_base_price'] - 1 ) * 100
					if ( percent_change >= args.last_hour_threshold ):
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True
						stocks[ticker]['exit_percent_signal'] = True


			# STOPLOSS MONITOR
			# If price decreases
			if ( last_price < stocks[ticker]['base_price'] ):
				percent_change = abs( last_price / stocks[ticker]['base_price'] - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

				# Re-set the base_price to the last_price if we increase by incr_threshold or more
				# This way we can continue to ride a price increase until it starts dropping
				if ( percent_change >= stocks[ticker]['incr_threshold'] ):
					stocks[ticker]['base_price'] = last_price
					print('SHORTED Stock "' + str(ticker) + '" decreased below the incr_threshold (' + str(stocks[ticker]['incr_threshold']) + '%), resetting base price to '  + str(last_price))
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Adapt decr_threshold based on changes made by --variable_exit
					if ( stocks[ticker]['incr_threshold'] < args.incr_threshold ):

						# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
						#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
						if ( stocks[ticker]['incr_threshold'] == stocks[ticker]['orig_incr_threshold'] ):
							stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold']
							stocks[ticker]['incr_threshold'] = stocks[ticker]['incr_threshold'] / 2

					else:
						stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold'] / 2

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
					stocks[ticker]['tx_id']			= random.randint(1000, 9999)
					stocks[ticker]['stock_qty']		= 0
					stocks[ticker]['base_price']		= 0
					stocks[ticker]['orig_base_price']	= 0
					stocks[ticker]['incr_threshold']	= args.incr_threshold
					stocks[ticker]['orig_incr_threshold']	= args.incr_threshold
					stocks[ticker]['decr_threshold']	= args.decr_threshold
					stocks[ticker]['orig_decr_threshold']	= args.decr_threshold
					stocks[ticker]['exit_percent']		= args.exit_percent

					if ( args.shortonly == True ):
						reset_signals(ticker, signal_mode='short')
					else:
						reset_signals(ticker, signal_mode='buy')

					continue

			# No price change
			else:
				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True)

			# END STOPLOSS MONITOR


			# ADDITIONAL EXIT STRATEGIES (exit_percent / vwap_exit)
			# Sell if --exit_percent was set and threshold met
			if ( stocks[ticker]['exit_percent'] != None and last_price < stocks[ticker]['orig_base_price'] ):
				total_percent_change = abs( last_price / stocks[ticker]['orig_base_price'] - 1 ) * 100

				# If exit_percent has been hit, we will sell at the first GREEN candle
				if ( stocks[ticker]['exit_percent_signal'] == True ):
					if ( last_close > last_open ):
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

				elif ( total_percent_change >= stocks[ticker]['exit_percent'] ):
					stocks[ticker]['exit_percent_signal'] = True

			# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
			if ( args.vwap_exit == True ):
				if ( cur_vwap < stocks[ticker]['orig_base_price'] ):
					if ( last_price <= ((stocks[ticker]['orig_base_price'] - cur_vwap) / 2) + cur_vwap ):
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

				elif ( cur_vwap > stocks[ticker]['orig_base_price'] ):
					if ( last_price <= ((cur_vwap - cur_vwap_down) / 2) + cur_vwap_down ):
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True


			# RSI MONITOR
			# Do not use stochrsi as an exit signal if exit_percent_signal is triggered. That means we've surpassed the
			# exit_percent threshold and should wait for either a red candle or for decr_threshold to be hit.
			if ( args.variable_exit == False and stocks[ticker]['exit_percent_signal'] == False ):

				if ( cur_rsi_k < stoch_default_low_limit and cur_rsi_d < stoch_default_low_limit ):
					stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'] = True

					# Monitor if K and D intercect
					# A buy-to-cover signal occurs when an increasing %K line crosses above the %D line in the oversold region.
					if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
						print(  '(' + str(ticker) + ') BUY_TO_COVER SIGNAL: StochRSI K value passed above the D value in the low_limit region (' +
							str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

				if ( stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal'] == True ):
					if ( prev_rsi_k < stoch_default_low_limit and cur_rsi_k >= stoch_default_low_limit ):
						print(  '(' + str(ticker) + ') BUY_TO_COVER SIGNAL: StochRSI K value passed above the low_limit threshold (' +
							str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True


			# BUY-TO-COVER THE STOCK
			if ( stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == True ):
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

				if ( args.shortonly == True ):
					reset_signals(ticker, signal_mode='short')
				else:
					reset_signals(ticker, signal_mode='buy')


		# Undefined mode - this shouldn't happen
		else:
			print('Error: undefined signal_mode: ' + str(signal_mode), file=sys.stderr)

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
		print('Error: sell_stocks(): tdalogin(): login failure', file=sys.stderr)
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

