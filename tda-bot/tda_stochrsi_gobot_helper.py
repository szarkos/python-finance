#!/usr/bin/python3 -u

import os, sys, signal
import time, datetime, pytz, random
import pickle

import tda_gobot_helper
import tda_algo_helper


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

		stocks[ticker]['cur_seq'] = int( idx['SEQUENCE'] )

		candle_data = {	'open':		float( idx['OPEN_PRICE'] ),
				'high':		float( idx['HIGH_PRICE'] ),
				'low':		float( idx['LOW_PRICE'] ),
				'close':	float( idx['CLOSE_PRICE'] ),
				'volume':	int( idx['VOLUME'] ),
				'datetime':	int( stream['timestamp'] ) }

		stocks[ticker]['pricehistory']['candles'].append( candle_data )

		# Add Heikin Ashi candle
		#  ha_open	= [ha_open(Previous Bar) + ha_close(Previous Bar)]/2
		#  ha_close	= (open+high+low+close)/4
		#  ha_low	= Min(low, ha_open, ha_close)
		#  ha_high	= Max(high, ha_open, ha_close)
		ha_open		= ( stocks[ticker]['pricehistory']['hacandles'][-1]['open'] + stocks[ticker]['pricehistory']['hacandles'][-1]['close'] ) / 2
		ha_close        = ( float(idx['OPEN_PRICE']) + float(idx['HIGH_PRICE']) + float(idx['LOW_PRICE']) + float(idx['CLOSE_PRICE']) ) / 4
		ha_low          = min( float(idx['LOW_PRICE']), ha_open, ha_close )
		ha_high         = max( float(idx['HIGH_PRICE']), ha_open, ha_close )
		candle_data = { 'open':		ha_open,
				'high':		ha_high,
				'low':		ha_low,
				'close':	ha_close,
				'volume':	int( idx['VOLUME'] ),
				'datetime':	int( stream['timestamp'] ) }

		stocks[ticker]['pricehistory']['hacandles'].append( candle_data )

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


	# Call stochrsi_gobot() for each set of specific algorithms
	for algo_list in algos:
		ret = stochrsi_gobot( cur_algo=algo_list, debug=debug )
		if ( ret == False ):
			print('Error: stochrsi_gobot_start(): stochrsi_gobot(' + str(algo) + '): returned False', file=sys.stderr)


	# After all the algos have been processed, iterate through tickers again and set
	#  the prev_seq to the cur_seq. This provides a record of sequence numbers to ensure
	#  that we do not process the same candles twice.
	for idx in stream['content']:
		ticker = idx['key']
		if ( stocks[ticker]['isvalid'] == False ):
			continue

		stocks[ticker]['prev_seq'] = stocks[ticker]['cur_seq']

	return True


# Reset all the buy/sell/short/buy-to-cover and indicator signals
def reset_signals(ticker=None, id=None, signal_mode=None, exclude_bbands_kchan=False):

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

			# If switching into the 'buy' or 'short' mode, reset the
			#  primary algo to None.
			if ( signal_mode == 'buy' or signal_mode == 'short' ):
				stocks[ticker]['primary_algo'] = None

		stocks[ticker]['algo_signals'][algo_id]['buy_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['sell_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['short_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal']		= False

		stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal']		= False

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
		stocks[ticker]['algo_signals'][algo_id]['rs_signal']			= False
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

		if ( exclude_bbands_kchan == False ):
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal']		= False
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal']	= False
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal']			= False
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter']		= 0
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter']		= 0

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
		export_pricehistory()
		signal.raise_signal(signal.SIGTERM)
		sys.exit(0)

	# Exit if we are not set up to monitor across multiple days
	if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == False ):
		if ( args.singleday == False and args.multiday == False ):
			print('Market closed, exiting.')
			export_pricehistory()
			signal.raise_signal(signal.SIGTERM)
			sys.exit(0)


	# If check_etf_indicators is configured, then calculate the rate-of-change for each ETF ticker
	#  before we reach the main loop for all the tradeable tickers.
	if ( cur_algo['check_etf_indicators'] == True ):
		etf_roc = []
		for ticker in cur_algo['etf_tickers'].split(','):
			stocks[ticker]['cur_roc'] = 0
			try:
				etf_roc = tda_algo_helper.get_roc( pricehistory=stocks[ticker]['pricehistory'], period=cur_algo['etf_roc_period'], type='hlc3' )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_roc(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			if ( isinstance(etf_roc, bool) and etf_roc == False ):
				print('Error: stochrsi_gobot(): get_roc(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_roc'] = etf_roc[-1]


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


	# Bollinger Bands and Keltner Channel crossover
	def bbands_kchannels(pricehistory=None, simple=False, cur_bbands=(0,0,0), prev_bbands=(0,0,0), cur_kchannel=(0,0,0), prev_kchannel=(0,0,0),
				bbands_kchan_signal_counter=0, bbands_kchan_xover_counter=0, bbands_kchan_init_signal=False, bbands_kchan_crossover_signal=False, bbands_kchan_signal=False, debug=False ):

		nonlocal cur_algo

		bbands_kchannel_offset		= cur_algo['bbands_kchannel_offset']
		bbands_kchan_squeeze_count	= cur_algo['bbands_kchan_squeeze_count']
		max_squeeze_natr		= cur_algo['max_squeeze_natr']

		# bbands/kchannel (0,0,0) = lower, middle, upper
		cur_bbands_lower	= round( cur_bbands[0], 3 )
		cur_bbands_mid		= round( cur_bbands[1], 3 )
		cur_bbands_upper	= round( cur_bbands[2], 3 )

		prev_bbands_lower	= round( prev_bbands[0], 3 )
		prev_bbands_mid		= round( prev_bbands[1], 3 )
		prev_bbands_upper	= round( prev_bbands[2], 3 )

		cur_kchannel_lower	= round( cur_kchannel[0], 3 )
		cur_kchannel_mid	= round( cur_kchannel[1], 3 )
		cur_kchannel_upper	= round( cur_kchannel[2], 3 )

		prev_kchannel_lower	= round( prev_kchannel[0], 3 )
		prev_kchannel_mid	= round( prev_kchannel[1], 3 )
		prev_kchannel_upper	= round( prev_kchannel[2], 3 )

		if ( simple == True ):
			bbands_kchan_init_signal = True
			if ( cur_kchannel_lower < cur_bbands_lower and prev_kchannel_lower < prev_bbands_lower ):
				prev_offset	= ((prev_kchannel_lower / prev_bbands_lower) - 1) * 100
				cur_offset	= ((cur_kchannel_lower / cur_bbands_lower) - 1) * 100
				if ( cur_offset < prev_offset ):
					bbands_kchan_signal = True

			elif ( cur_kchannel_lower > cur_bbands_lower and cur_kchannel_upper < cur_bbands_upper ):
				bbands_kchan_signal = False

			return ( bbands_kchan_init_signal, bbands_kchan_crossover_signal, bbands_kchan_signal,
					bbands_kchan_signal_counter, bbands_kchan_xover_counter )

		# If the Bollinger Bands are outside the Keltner channel and the init signal hasn't been triggered,
		#  then we can just make sure everything is reset and return False. We need to make sure that at least
		#  bbands_kchan_signal_counter is reset and is not left set to >0 after a half-triggered squeeze.
		#
		# If the init signal has been triggered then we can move on and the signal may be canceled later
		#  either via the buy/short signal or using bbands_kchan_xover_counter below
		if ( (cur_bbands_lower <= cur_kchannel_lower or cur_bbands_upper >= cur_kchannel_upper) and bbands_kchan_init_signal == False ):
			bbands_kchan_init_signal        = False
			bbands_kchan_signal             = False
			bbands_kchan_crossover_signal   = False
			bbands_kchan_signal_counter     = 0
			bbands_kchan_xover_counter      = 0

			return ( bbands_kchan_init_signal, bbands_kchan_crossover_signal, bbands_kchan_signal,
					bbands_kchan_signal_counter, bbands_kchan_xover_counter )

		# Check if the Bollinger Bands have moved inside the Keltner Channel
		# Signal when they begin to converge
		if ( cur_kchannel_lower < cur_bbands_lower and cur_kchannel_upper > cur_bbands_upper ):

			# Squeeze counter
			bbands_kchan_signal_counter += 1

			# Enforce a minimum offset to ensure the squeeze has some energy before triggering
			#  the bbands_kchan_init_signal signal
			#
			# Note: I debated checking the bbands_kchan_squeeze_count in this section vs. just setting
			#  bbands_kchan_init_signal=True sooner, and checking bbands_kchan_squeeze_count in the next
			#  section. Having it here results in a bit fewer trades, but slightly better trade percentage.
			#  So this appears to produce just slighly better trades.
			prev_offset	= abs((prev_kchannel_lower / prev_bbands_lower) - 1) * 100
			cur_offset	= abs((cur_kchannel_lower / cur_bbands_lower) - 1) * 100
			if ( cur_offset >= bbands_kchannel_offset and bbands_kchan_signal_counter >= bbands_kchan_squeeze_count ):
				bbands_kchan_init_signal = True

		# Toggle the bbands_kchan_signal when the bollinger bands pop back outside the keltner channel
		if ( bbands_kchan_init_signal == True and bbands_kchan_signal_counter >= bbands_kchan_squeeze_count ):

			# An aggressive strategy is to try to get in early when the Bollinger bands begin to widen
			#  and before they pop out of the Keltner channel
			prev_offset	= abs((prev_kchannel_lower / prev_bbands_lower) - 1) * 100
			cur_offset	= abs((cur_kchannel_lower / cur_bbands_lower) - 1) * 100
			if ( cur_offset < prev_offset and cur_offset <= bbands_kchannel_offset / 4 ):
				bbands_kchan_signal = True

			# Check for crossover
			if ( (prev_kchannel_lower <= prev_bbands_lower and cur_kchannel_lower > cur_bbands_lower) or
					(prev_kchannel_upper >= prev_bbands_upper and cur_kchannel_upper < cur_bbands_upper) ):
				bbands_kchan_crossover_signal   = True
				bbands_kchan_signal             = True

			if ( bbands_kchan_crossover_signal == True ):
				bbands_kchan_xover_counter += 1

			# If max_squeeze_natr is set, make sure the recent NATR is not too high to disqualify
			#  this stock movement as a good consolidation.
			if ( max_squeeze_natr != None and bbands_kchan_signal == True and pricehistory != None ):

				cndl_slice = { 'candles': [] }
				for i in range(bbands_kchan_signal_counter+2, 0, -1):
					cndl_slice['candles'].append( pricehistory['candles'][-i] )

				try:
					atr_t, natr_t = tda_algo_helper.get_atr( pricehistory=cndl_slice, period=bbands_kchan_signal_counter )

				except Exception as e:
					print('Caught exception: bbands_kchannels(): get_atr(): error calculating NATR: ' + str(e))
					bbands_kchan_signal = False

				if ( natr_t[-1] >= max_squeeze_natr ):
					bbands_kchan_signal = False
					if ( debug == True ):
						print('NOTICE: bbands_kchan_signal canceled due to high NATR above max_squeeze_natr: ' + str(natr_t[-1]) + ' / ' + str(max_squeeze_natr) )

			# Cancel the bbands_kchan_signal if the bollinger bands popped back inside the keltner channel,
			#  or if the bbands_kchan_signal_counter has lingered for too long
			#
			# Note: The criteria for the crossover signal is when *either* the upper or lower bands cross over,
			#  since they don't always cross at the same time. So when checking if the bands crossed back over,
			#  it is important that we don't just check the current position but check both the previous and
			#  current positions. Otherwise a lingering upper or lower band could cause the signal to be cancelled
			#  just because it hasn't yet crossed over, but probably will.
			if ( bbands_kchan_crossover_signal == True and
					((prev_kchannel_lower > prev_bbands_lower and cur_kchannel_lower <= cur_bbands_lower) or
					 (prev_kchannel_upper < prev_bbands_upper and cur_kchannel_upper >= cur_bbands_upper)) or
					  bbands_kchan_xover_counter >= 2 ):

				bbands_kchan_init_signal	= False
				bbands_kchan_crossover_signal	= False
				bbands_kchan_signal		= False
				bbands_kchan_signal_counter	= 0
				bbands_kchan_xover_counter	= 0

		return ( bbands_kchan_init_signal, bbands_kchan_crossover_signal, bbands_kchan_signal,
				bbands_kchan_signal_counter, bbands_kchan_xover_counter )


	# Intraday stacked moving averages
	def get_stackedma(pricehistory=None, stacked_ma_periods=None, stacked_ma_type=None, use_ha_candles=False):
		try:
			assert pricehistory		!= None
			if ( use_ha_candles == True ):
				assert pricehistory['hacandles']

			assert stacked_ma_periods	!= None
			assert stacked_ma_type		!= None
		except:
			return False

		ph = { 'candles': [] }
		if ( use_ha_candles == True ):
			ph['candles'] = pricehistory['hacandles']
		else:
			ph['candles'] = pricehistory['candles']

		stacked_ma_periods = stacked_ma_periods.split(',')
		ma_array = []
		for ma_period in stacked_ma_periods:
			ma = []
			try:
				ma = tda_algo_helper.get_alt_ma(ph, ma_type=stacked_ma_type, period=int(ma_period) )

			except Exception as e:
				print('Error, unable to calculate stacked MAs: ' + str(e))
				return False

			ma_array.append(ma)

		s_ma = []
		for i in range(0, len(ma)):
			ma_tmp = []
			for p in range(0, len(stacked_ma_periods)):
				ma_tmp.append(ma_array[p][i])

			s_ma.append( tuple(ma_tmp) )

		return s_ma


	# Check orientation of stacked moving averages
	def check_stacked_ma(s_ma=[], affinity=None):

		if ( affinity == None or len(s_ma) == 0 ):
			return False

		# Round the moving average values to two decimal places
		s_ma = list(s_ma)
		for i in range(0, len(s_ma)):
			s_ma[i] = round( s_ma[i], 2 )

		ma_affinity = False
		if ( affinity == 'bear' ):
			for i in range(0, len(s_ma)):
				if ( i == len(s_ma)-1 ):
					break

				if ( s_ma[i] < s_ma[i+1] ):
					ma_affinity = True
				else:
					ma_affinity = False
					break

		elif ( affinity == 'bull' ):
			for i in range(0, len(s_ma)):
				if ( i == len(s_ma)-1 ):
					break

				if ( s_ma[i] > s_ma[i+1] ):
					ma_affinity = True
				else:
					ma_affinity = False
					break

		return ma_affinity


	# Return a bull/bear signal based on the ttm_trend algorithm
	# Look back 6 candles and take the high and the low of them then divide by 2
	#  and if the close of the next candle is above that number the trend is bullish,
	#  and if its below the trend is bearish.
	def price_trend(candles=None, type='hl2', period=5, affinity=None):

		if ( candles == None or affinity == None ):
			return False

		cur_close	= candles[-1]['close']
		price		= 0
		for idx in range(-(period+1), -1, 1):
			if ( type == 'close' ):
				price += candles[idx]['close']

			elif ( type == 'hl2' ):
				price += (candles[idx]['high'] + candles[idx]['low']) / 2

			elif ( type == 'hlc3' ):
				price += (candles[idx]['high'] + candles[idx]['low'] + candles[idx]['close']) / 3

			elif ( type == 'ohlc4' ):
				price += (candles[idx]['open'] + candles[idx]['high'] + candles[idx]['low'] + candles[idx]['close']) / 4

			else:
				return False

		price = price / period
		if ( affinity == 'bull' and cur_close > price ):
			return True
		elif ( affinity == 'bear' and cur_close <= price ):
			return True

		return False


	##########################################################################################
	# Iterate through the stock tickers, calculate all the indicators, and make buy/sell decisions
	for ticker in stocks.keys():

		# Initialize some local variables
		percent_change	= 0
		net_change	= 0

		min_intra_natr	= cur_algo['min_intra_natr']
		max_intra_natr	= cur_algo['max_intra_natr']
		min_daily_natr	= cur_algo['min_daily_natr']
		max_daily_natr	= cur_algo['max_daily_natr']

		# Skip this ticker if it has been marked as invalid or not tradeable
		if ( stocks[ticker]['isvalid'] == False or stocks[ticker]['tradeable'] == False ):
			continue

		# Skip this ticker if it is not listed in this algorithm's per-algo valid_tickers[],
		#  or if it is listed in exclude_tickers[]
		if ( len(cur_algo['valid_tickers']) != 0 ):
			if ( ticker not in cur_algo['valid_tickers'] ):
				continue
		if ( len(cur_algo['exclude_tickers']) != 0 ):
			if ( ticker in cur_algo['exclude_tickers'] ):
				continue

		# Skip processing this ticker again if we have already processed this sequence number.
		# Sometimes this can happen if the stream socket is reset or if the volume is very low.
		# The exception is if the stock is in sell or buy_to_cover mode, it makes sense to check
		#  the current price to allow stoploss.
		if ( stocks[ticker]['prev_seq'] == stocks[ticker]['cur_seq'] ):
			if ( stocks[ticker]['algo_signals'][algo_id]['signal_mode'] == 'buy' or
				stocks[ticker]['algo_signals'][algo_id]['signal_mode'] == 'short' ):
				continue

		# Skip this ticker if it conflicts with a per-algo min/max_daily_natr configuration
		if ( min_daily_natr != None and stocks[ticker]['natr_daily'] < min_daily_natr ):
			continue
		if ( max_daily_natr != None and stocks[ticker]['natr_daily'] > max_daily_natr ):
			continue


		# Get stochastic RSI
		if ( cur_algo['primary_stochrsi'] == True or cur_algo['primary_stochmfi'] == True ):
			rsi_k		= []
			rsi_d		= []
			stochrsi	= []
			try:
				if ( cur_algo['primary_stochrsi'] == True ):
					stochrsi, rsi_k, rsi_d = tda_algo_helper.get_stochrsi( stocks[ticker]['pricehistory'], rsi_period=cur_algo['rsi_period'], stochrsi_period=cur_algo['stochrsi_period'], type=rsi_type,
												slow_period=cur_algo['rsi_slow'], rsi_k_period=cur_algo['rsi_k_period'], rsi_d_period=cur_algo['rsi_d_period'], debug=False )

				elif ( cur_algo['primary_stochmfi'] == True ):
					rsi_k, rsi_d = tda_algo_helper.get_stochmfi( stocks[ticker]['pricehistory'], mfi_period=cur_algo['stochmfi_period'], mfi_k_period=cur_algo['mfi_k_period'],
											slow_period=cur_algo['mfi_slow'], mfi_d_period=cur_algo['mfi_d_period'], debug=False )
					stochrsi = rsi_k

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(stochrsi, bool) and stochrsi == False ):
				print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_rsi_k']	= rsi_k[-1]
			stocks[ticker]['cur_rsi_d']	= rsi_d[-1]
			stocks[ticker]['prev_rsi_k']	= rsi_k[-2]
			stocks[ticker]['prev_rsi_d']	= rsi_d[-2]

		# Get secondary stochastic indicators
		# StochRSI with 5-minute candles
		if ( cur_algo['stochrsi_5m'] == True ):
			stochrsi_5m	= []
			rsi_k_5m	= []
			rsi_d_5m	= []
			try:
				stochrsi_5m, rsi_k_5m, rsi_d_5m = tda_algo_helper.get_stochrsi( stocks[ticker]['pricehistory_5m'], rsi_period=cur_algo['rsi_period'],
												 stochrsi_period=cur_algo['stochrsi_5m_period'], type=rsi_type, slow_period=cur_algo['rsi_slow'],
												 rsi_k_period=cur_algo['rsi_k_5m_period'], rsi_d_period=cur_algo['rsi_d_period'], debug=False )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(stochrsi_5m, bool) and stochrsi_5m == False ):
				print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_rsi_k_5m']	= rsi_k_5m[-1]
			stocks[ticker]['cur_rsi_d_5m']	= rsi_d_5m[-1]
			stocks[ticker]['prev_rsi_k_5m']	= rsi_k_5m[-2]
			stocks[ticker]['prev_rsi_d_5m']	= rsi_d_5m[-2]

		# StochMFI
		if ( cur_algo['stochmfi'] == True ):
			mfi_k = []
			mfi_d = []
			try:
				mfi_k, mfi_d = tda_algo_helper.get_stochmfi( stocks[ticker]['pricehistory'], mfi_period=cur_algo['stochmfi_period'], mfi_k_period=cur_algo['mfi_k_period'],
									      slow_period=cur_algo['mfi_slow'], mfi_d_period=cur_algo['mfi_d_period'], debug=False )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(mfi_k, bool) and mfi_k == False ):
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_mfi_k']	= mfi_k[-1]
			stocks[ticker]['cur_mfi_d']	= mfi_d[-1]
			stocks[ticker]['prev_mfi_k']	= mfi_k[-2]
			stocks[ticker]['prev_mfi_d']	= mfi_d[-2]

		# StochMFI with 5-minute candles
		if ( cur_algo['stochmfi_5m'] == True ):
			mfi_k_5m = []
			mfi_d_5m = []
			try:
				mfi_k_5m, mfi_d_5m = tda_algo_helper.get_stochmfi( stocks[ticker]['pricehistory_5m'], mfi_period=cur_algo['stochmfi_5m_period'], mfi_k_period=cur_algo['mfi_k_5m_period'],
										    slow_period=cur_algo['mfi_slow'], mfi_d_period=cur_algo['mfi_d_period'], debug=False )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(mfi_k_5m, bool) and mfi_k_5m == False ):
				print('Error: stochrsi_gobot(): get_stochmfi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_mfi_k_5m']	= mfi_k_5m[-1]
			stocks[ticker]['cur_mfi_d_5m']	= mfi_d_5m[-1]
			stocks[ticker]['prev_mfi_k_5m']	= mfi_k_5m[-2]
			stocks[ticker]['prev_mfi_d_5m']	= mfi_d_5m[-2]

		# Stacked moving averages
		if ( cur_algo['primary_stacked_ma'] == True ):
			s_ma_primary	= []
			s_ma_ha_primary	= []
			try:
				s_ma_primary	= get_stackedma(stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods_primary'], cur_algo['stacked_ma_type_primary'] )
				s_ma_ha_primary	= get_stackedma(stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods_primary'], cur_algo['stacked_ma_type_primary'], use_ha_candles=True )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stackedma(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_s_ma_primary']	= s_ma_primary[-1]
			stocks[ticker]['prev_s_ma_primary']	= s_ma_primary[-2]
			stocks[ticker]['cur_s_ma_ha_primary']	= s_ma_ha_primary[-1]
			stocks[ticker]['prev_s_ma_ha_primary']	= s_ma_ha_primary[-2]

		if ( cur_algo['stacked_ma'] == True ):
			s_ma	= []
			s_ma_ha	= []
			try:
				s_ma	= get_stackedma( stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods'], cur_algo['stacked_ma_type'] )
				s_ma_ha	= get_stackedma( stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods'], cur_algo['stacked_ma_type'], use_ha_candles=True )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stackedma(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_s_ma']	= s_ma[-1]
			stocks[ticker]['prev_s_ma']	= s_ma[-2]
			stocks[ticker]['cur_s_ma_ha']	= s_ma_ha[-1]
			stocks[ticker]['prev_s_ma_ha']	= s_ma_ha[-2]

		# RSI
		if ( cur_algo['rsi'] == True ):
			rsi = []
			try:
				rsi = tda_algo_helper.get_rsi(stocks[ticker]['pricehistory'], cur_algo['rsi_period'], rsi_type, debug=False)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_rsi(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			if ( isinstance(rsi, bool) and rsi == False ):
				print('Error: stochrsi_gobot(): get_rsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
				continue

			stocks[ticker]['cur_rsi']	= rsi[-1]
			stocks[ticker]['prev_rsi']	= rsi[-2]

		# Average True Range (ATR/NATR)
		atr	= []
		natr	= []
		try:
			atr, natr = tda_algo_helper.get_atr( pricehistory=stocks[ticker]['pricehistory_5m'], period=cur_algo['atr_period'] )

		except Exception as e:
			print('Error: stochrsi_gobot(' + str(ticker) + '): get_atr(): ' + str(e), file=sys.stderr)
			continue

		stocks[ticker]['cur_atr']  = atr[-1]
		stocks[ticker]['cur_natr'] = natr[-1]

		# Rate-of-Change and Relative Strength
		stock_roc	= []
		try:
			stock_roc = tda_algo_helper.get_roc( pricehistory=stocks[ticker]['pricehistory'], period=cur_algo['etf_roc_period'], type='hlc3' )

		except Exception as e:
			print('Error: stochrsi_gobot(): get_roc(' + str(ticker) + '): ' + str(e), file=sys.stderr)
			continue

		if ( isinstance(stock_roc, bool) and stock_roc == False ):
			print('Error: stochrsi_gobot(): get_roc(' + str(ticker) + ') returned false - no data', file=sys.stderr)
			continue

		stocks[ticker]['cur_roc'] = stock_roc[-1]

		# MFI
		if ( cur_algo['mfi'] == True ):

			mfi = []
			try:
				mfi = tda_algo_helper.get_mfi(stocks[ticker]['pricehistory'], period=cur_algo['mfi_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_mfi(): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_mfi']  = mfi[-1]
			stocks[ticker]['prev_mfi'] = mfi[-2]


		# ADX, +DI, -DI
		if ( cur_algo['adx'] == True or cur_algo['dmi'] == True or cur_algo['dmi_simple'] == True ):

			adx		= []
			plus_di		= []
			minus_di	= []
			try:
				adx, plus_di, minus_di		= tda_algo_helper.get_adx(stocks[ticker]['pricehistory'], period=cur_algo['di_period'])
				adx, plus_di_adx, minus_di_adx	= tda_algo_helper.get_adx(stocks[ticker]['pricehistory'], period=cur_algo['adx_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_adx(): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_adx']	= adx[-1]
			stocks[ticker]['cur_plus_di']	= plus_di[-1]
			stocks[ticker]['cur_minus_di']	= minus_di[-1]
			stocks[ticker]['prev_plus_di']	= plus_di[-2]
			stocks[ticker]['prev_minus_di']	= minus_di[-2]

		# Aroon Oscillator
		if ( cur_algo['aroonosc'] == True ):

			# SAZ - 2021-08-29: Higher volatility stocks seem to work better with a
			#  longer Aroon Oscillator value.
			stocks[ticker]['aroonosc_period'] = cur_algo['aroonosc_period']
			if ( stocks[ticker]['cur_natr'] > args.aroonosc_alt_threshold ):
				stocks[ticker]['aroonosc_period'] = args.aroonosc_alt_period

			aroonosc = []
			try:
				aroonosc = tda_algo_helper.get_aroon_osc(stocks[ticker]['pricehistory'], period=stocks[ticker]['aroonosc_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_aroon_osc(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_aroonosc'] = aroonosc[-1]

			# Enable macd_simple if --aroonosc_with_macd_simple is True
			# We do this here just so that the MACD values will be calculated below, but the buy/short logic
			#  later on will determine if MACD is actually used to make a decision.
			if ( args.aroonosc_with_macd_simple == True ):
				cur_algo['macd_simple'] = True

		# MACD - 48, 104, 36
		if ( cur_algo['macd'] == True or cur_algo['macd_simple'] == True ):

			macd		= []
			macd_signal	= []
			macd_histogram	= []
			try:
				macd, macd_avg, macd_histogram = tda_algo_helper.get_macd(stocks[ticker]['pricehistory'], short_period=cur_algo['macd_short_period'], long_period=cur_algo['macd_long_period'], signal_period=cur_algo['macd_signal_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_macd(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_macd']	= macd[-1]
			stocks[ticker]['cur_macd_avg']	= macd_avg[-1]
			stocks[ticker]['prev_macd']	= macd[-2]
			stocks[ticker]['prev_macd_avg']	= macd_avg[-2]

		# Chop Index
		if ( cur_algo['chop_index'] == True or cur_algo['chop_simple'] == True ):
			chop = []
			try:
				chop = tda_algo_helper.get_chop_index(stocks[ticker]['pricehistory'], period=cur_algo['chop_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_chop_index' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_chop']	= chop[-1]
			stocks[ticker]['prev_chop']	= chop[-2]

		# Supertrend Indicator
		if ( cur_algo['supertrend'] == True ):
			supertrend = []
			try:
				supertrend = tda_algo_helper.get_supertrend(pricehistory=stocks[ticker]['pricehistory'], atr_period=cur_algo['supertrend_atr_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_supertrend' + str(ticker) + '): ' + str(e), file=sys.stderr)

			stocks[ticker]['cur_supertrend']	= supertrend[-1]
			stocks[ticker]['prev_supertrend']	= supertrend[-2]


		# Bollinger Bands and Keltner Channel
		if ( cur_algo['bbands_kchannel'] == True or cur_algo['bbands_kchannel_simple'] == True ):

			bbands_lower    = []
			bbands_mid      = []
			bbands_upper    = []
			try:
				if ( cur_algo['use_bbands_kchannel_5m'] == True ):
					bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory=stocks[ticker]['pricehistory_5m'], period=cur_algo['bbands_period'])
				else:
					bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory=stocks[ticker]['pricehistory'], period=cur_algo['bbands_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_bbands(): ' + str(e))
				continue

			stocks[ticker]['cur_bbands']	= ( bbands_lower[-1], bbands_mid[-1], bbands_upper[-1] )
			stocks[ticker]['prev_bbands']	= ( bbands_lower[-2], bbands_mid[-2], bbands_upper[-2] )

			kchannel_lower  = []
			kchannel_mid    = []
			kchannel_upper  = []
			try:
				if ( cur_algo['use_bbands_kchannel_5m'] == True ):
					kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory=stocks[ticker]['pricehistory_5m'], period=cur_algo['kchannel_period'], atr_period=cur_algo['kchannel_atr_period'])
				else:
					kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory=stocks[ticker]['pricehistory'], period=cur_algo['kchannel_period'], atr_period=cur_algo['kchannel_atr_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_kchannel(): ' + str(e))
				continue

			stocks[ticker]['cur_kchannel']	= ( kchannel_lower[-1], kchannel_mid[-1], kchannel_upper[-1] )
			stocks[ticker]['prev_kchannel']	= ( kchannel_lower[-2], kchannel_mid[-2], kchannel_upper[-2] )


		# VWAP
		# Calculate vwap to use as entry or exit algorithm
		if ( cur_algo['vwap'] == True or cur_algo['support_resistance'] == True ):
			vwap = []
			vwap_up = []
			vwap_down = []
			try:
				vwap, vwap_up, vwap_down = tda_algo_helper.get_vwap( stocks[ticker]['pricehistory'] )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_vwap(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			if ( isinstance(vwap, bool) and vwap == False ):
				print('Error: stochrsi_gobot(): get_vwap(' + str(ticker) + '): returned False', file=sys.stderr)
				continue

			elif ( len(vwap) == 0 ):
				print('Error: stochrsi_gobot(): get_vwap(' + str(ticker) + '): returned an empty data set', file=sys.stderr)
				continue

			stocks[ticker]['cur_vwap']	= vwap[-1]
			stocks[ticker]['cur_vwap_up']	= vwap_up[-1]
			stocks[ticker]['cur_vwap_down']	= vwap_down[-1]

		# VPT
		if ( cur_algo['vpt'] == True ):

			vpt = []
			vpt_sma = []
			try:
				vpt, vpt_sma = tda_algo_helper.get_vpt(stocks[ticker]['pricehistory'], period=cur_algo['vpt_sma_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_vpt(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			stocks[ticker]['cur_vpt']	= vpt[-1]
			stocks[ticker]['prev_vpt']	= vpt[-2]
			stocks[ticker]['cur_vpt_sma']	= vpt_sma[-1]
			stocks[ticker]['prev_vpt_sma']	= vpt_sma[-2]

		# Debug
		if ( debug == True ):
			time_now = datetime.datetime.now( mytimezone )
			print( '(' + str(ticker) + ') Algo ID: ' + str(cur_algo['algo_id']) )
			print( '(' + str(ticker) + ') OHLCV: ' + str(stocks[ticker]['pricehistory']['candles'][-1]['open']) +
							  ' / ' + str(stocks[ticker]['pricehistory']['candles'][-1]['high']) +
							  ' / ' + str(stocks[ticker]['pricehistory']['candles'][-1]['low']) +
							  ' / ' + str(stocks[ticker]['pricehistory']['candles'][-1]['close']) +
							  ' / ' + str(stocks[ticker]['pricehistory']['candles'][-1]['volume']) )

			# StochRSI
			print( '(' + str(ticker) + ') StochRSI Period: ' + str(cur_algo['stochrsi_period']) + ' / Type: ' + str(rsi_type) +
				' / K Period: ' + str(cur_algo['rsi_k_period']) + ' / D Period: ' + str(cur_algo['rsi_d_period']) + ' / Slow Period: ' + str(cur_algo['rsi_slow']) +
				' / High Limit|Low Limit: ' + str(cur_algo['rsi_high_limit']) + '|' + str(cur_algo['rsi_low_limit']) )
			print( '(' + str(ticker) + ') Current StochRSI K: ' + str(round(stocks[ticker]['cur_rsi_k'], 2)) +
						' / Previous StochRSI K: ' + str(round(stocks[ticker]['prev_rsi_k'], 2)))
			print( '(' + str(ticker) + ') Current StochRSI D: ' + str(round(stocks[ticker]['cur_rsi_d'], 2)) +
						' / Previous StochRSI D: ' + str(round(stocks[ticker]['prev_rsi_d'], 2)))
			print( '(' + str(ticker) + ') Primary Stochastic Signals: ' +
						str(stocks[ticker]['algo_signals'][algo_id]['stochrsi_signal']) + ' / ' +
						str(stocks[ticker]['algo_signals'][algo_id]['stochrsi_crossover_signal']) + ' / ' +
						str(stocks[ticker]['algo_signals'][algo_id]['stochrsi_threshold_signal']) + ' / ' +
						str(stocks[ticker]['algo_signals'][algo_id]['buy_signal']) )

			# Stacked moving averages
			if ( cur_algo['primary_stacked_ma'] == True ):
				print('(' + str(ticker) + ') Primary Stacked MA: ', end='')
				for idx in range(0, len(stocks[ticker]['cur_s_ma_primary'])):
					print( str(round(stocks[ticker]['cur_s_ma_primary'][idx], 2)) + ' ', end='' )
				print()

			if ( cur_algo['stacked_ma'] == True ):
				print('(' + str(ticker) + ') Stacked MA: ', end='')
				for idx in range(0, len(stocks[ticker]['cur_s_ma'])):
					print( str(round(stocks[ticker]['cur_s_ma'][idx], 2)) + ' ', end='' )
				print()

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

			# Bollinger Bands and Keltner Channel
			if ( cur_algo['bbands_kchannel'] == True or cur_algo['bbands_kchannel_simple'] == True ):
				print('(' + str(ticker) + ') Current BBands: ' +
								str(round(stocks[ticker]['cur_bbands'][0], 3)) + ',' +
								str(round(stocks[ticker]['cur_bbands'][1], 3)) + ',' +
								str(round(stocks[ticker]['cur_bbands'][2], 3)) +
							' / Current Kchannel: ' +
								str(round(stocks[ticker]['cur_kchannel'][0], 3)) + ',' +
								str(round(stocks[ticker]['cur_kchannel'][1], 3)) + ',' +
								str(round(stocks[ticker]['cur_kchannel'][2], 3)) +
							' / Squeeze Count: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter']) +
							' / BBands_Kchannel Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal']) +
							' / BBands_Kchannel Crossover Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal']) )

			# Rate of Change
			if ( cur_algo['check_etf_indicators'] == True ):
				print( '(' + str(ticker) + ') Current Rate-of-Change: ' + str(round(stocks[ticker]['cur_roc'], 5)), end='' )
				for t in cur_algo['etf_tickers'].split(','):
					print( ', ' + str(t) + ': ' + str(round(stocks[t]['cur_roc'], 5)), end='' )

				print( ' / RelStrength Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['rs_signal']) )

			# VWAP
			if ( cur_algo['vwap'] == True or cur_algo['support_resistance'] == True ):
				print('(' + str(ticker) + ') PDH/PDL/PDC: ' + str(round(stocks[ticker]['previous_day_high'], 2)) +
							' / ' + str(round(stocks[ticker]['previous_day_low'], 2)) +
							' / ' + str(round(stocks[ticker]['previous_day_close'], 2)) )

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

			# Signal mode
			print( '(' + str(ticker) + ') Signal Mode: ' + str(stocks[ticker]['algo_signals'][algo_id]['signal_mode']) )

			# Timestamp check
			print('(' + str(ticker) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
				', timestamp received from API ' +
				datetime.datetime.fromtimestamp(int(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f') +
				' (' + str(int(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])) + ')' +
				' (seq: ' + str(stocks[ticker]['cur_seq']) + ')' )

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

		last_open		= stocks[ticker]['pricehistory']['candles'][-1]['open']
		last_high		= stocks[ticker]['pricehistory']['candles'][-1]['high']
		last_low		= stocks[ticker]['pricehistory']['candles'][-1]['low']
		last_close		= stocks[ticker]['pricehistory']['candles'][-1]['close']

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

		# Stacked MA
		cur_s_ma_primary	= stocks[ticker]['cur_s_ma_primary']
		prev_s_ma_primary	= stocks[ticker]['prev_s_ma_primary']
		cur_s_ma		= stocks[ticker]['cur_s_ma']
		prev_s_ma		= stocks[ticker]['prev_s_ma']

		cur_s_ma_ha_primary	= stocks[ticker]['cur_s_ma_ha_primary']
		prev_s_ma_ha_primary	= stocks[ticker]['prev_s_ma_ha_primary']
		cur_s_ma_ha		= stocks[ticker]['cur_s_ma_ha']
		prev_s_ma_ha		= stocks[ticker]['prev_s_ma_ha']

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

		cur_bbands		= stocks[ticker]['cur_bbands']
		prev_bbands		= stocks[ticker]['prev_bbands']
		cur_kchannel		= stocks[ticker]['cur_kchannel']
		prev_kchannel		= stocks[ticker]['prev_kchannel']

		cur_vwap		= stocks[ticker]['cur_vwap']
		cur_vwap_up		= stocks[ticker]['cur_vwap_up']
		cur_vwap_down		= stocks[ticker]['cur_vwap_down']

		cur_vpt			= stocks[ticker]['cur_vpt']
		prev_vpt		= stocks[ticker]['prev_vpt']
		cur_vpt_sma		= stocks[ticker]['cur_vpt_sma']
		prev_vpt_sma		= stocks[ticker]['prev_vpt_sma']

		cur_roc			= stocks[ticker]['cur_roc']

		# Algo modifiers
		stoch_high_limit	= cur_algo['rsi_high_limit']
		stoch_low_limit		= cur_algo['rsi_low_limit']
		mfi_high_limit		= cur_algo['mfi_high_limit']
		mfi_low_limit		= cur_algo['mfi_low_limit']
		adx_threshold		= cur_algo['adx_threshold']


		# Global criteria for buy or sell mode
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

		# Global criteria for short or buy_to_cover mode
		elif ( signal_mode == 'sell' or signal_mode == 'buy_to_cover'):

			# primary_algo is the algorithm that entered the trade.
			# Some algos may have their own exit criteria, so we will only
			#  process the sell/buy_to_cover loop for that algo.
			if ( stocks[ticker]['primary_algo'] != cur_algo['algo_id'] ):
				continue


		# BUY MODE - looking for a signal to purchase the stock
		if ( signal_mode == 'buy' ):

			# Bollinger Bands and Keltner Channel
			# We put this above the primary indicator since we want to keep track of what the
			#  Bollinger bands and Keltner channel are doing across buy/short transitions.
			if ( cur_algo['bbands_kchannel'] == True or cur_algo['bbands_kchannel_simple'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] ) = bbands_kchannels( pricehistory=stocks[ticker]['pricehistory'], simple=cur_algo['bbands_kchannel_simple'],
																cur_bbands=cur_bbands, prev_bbands=prev_bbands,
																cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
																bbands_kchan_signal_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
																bbands_kchan_xover_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'],
																bbands_kchan_init_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
																bbands_kchan_crossover_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
																bbands_kchan_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
																debug=True )

			# PRIMARY STOCHRSI MONITOR
			if ( cur_algo['primary_stochrsi'] == True or cur_algo['primary_stochmfi'] == True ):

				# Jump to short mode if StochRSI K and D are already above stoch_high_limit
				# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
				#  does a full loop again before acting on it.
				if ( (cur_rsi_k >= stoch_default_high_limit and cur_rsi_d >= stoch_default_high_limit) and args.short == True and stocks[ticker]['shortable'] == True ):
					print('(' + str(ticker) + ') StochRSI K and D values already above ' + str(stoch_default_high_limit) + ', switching to short mode.')
					reset_signals(ticker, id=algo_id, signal_mode='short')
					continue

				# Update the StochRSI/MFI signals
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

			# PRIMARY STACKED MOVING AVERAGE
			elif ( cur_algo['primary_stacked_ma'] == True ):

				# Standard candles
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

				# Heikin Ashi candles
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				# TTM Trend
				if ( cur_algo['use_trend'] == True ):
					cndl_slice	= []
					for i in range(cur_algo['trend_period']+1, 0, -1):
						cndl_slice.append( stocks[ticker]['pricehistory']['candles'][-i] )

					price_trend_bear_affinity = price_trend(cndl_slice, type=cur_algo['trend_type'], period=cur_algo['trend_period'], affinity='bear')
					price_trend_bull_affinity = price_trend(cndl_slice, type=cur_algo['trend_type'], period=cur_algo['trend_period'], affinity='bull')

				# Jump to short mode if the stacked moving averages are showing a bearish movement
				if ( args.short == True and stocks[ticker]['shortable'] == True and
						(cur_algo['use_ha_candles'] == True and (stacked_ma_bear_ha_affinity == True or stacked_ma_bear_affinity == True)) or
						(cur_algo['use_trend'] == True and price_trend_bear_affinity == True) or
						(cur_algo['use_ha_candles'] == False and cur_algo['use_trend'] == False and stacked_ma_bear_affinity == True) ):

					print('(' + str(ticker) + ') StackedMA values indicate bearish trend ' + str(cur_s_ma_primary) + ", switching to short mode.\n" )
					reset_signals(ticker, id=algo_id, signal_mode='short', exclude_bbands_kchan=True)
					continue

				elif ( cur_algo['use_ha_candles'] == True and stacked_ma_bull_ha_affinity == True or stacked_ma_bull_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = True

				elif ( cur_algo['use_trend'] == True and price_trend_bull_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = True

				elif ( cur_algo['use_ha_candles'] == False and cur_algo['use_trend'] == False and stacked_ma_bull_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = True

				else:
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = False

			# Secondary Stacked Moving Average
			if ( cur_algo['stacked_ma'] == True ):
				if ( check_stacked_ma(cur_s_ma, 'bull') == True ):
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = True
				else:
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = False

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

			# Relative Strength
			if ( cur_algo['check_etf_indicators'] == True ):

				cur_rs = 0
				for t in cur_algo['etf_tickers'].split(','):

					if ( cur_roc > 0 and stocks[t]['cur_roc'] < 0 ):
						# Stock is rising compared to ETF
						cur_rs = abs( cur_roc / stocks[t]['cur_roc'] )
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

					elif ( cur_roc < 0 and stocks[t]['cur_roc'] < 0 ):
						# Both stocks are sinking
						cur_rs = -( cur_roc / stocks[t]['cur_roc'] )
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					elif ( cur_roc < 0 and stocks[t]['cur_roc'] > 0 ):
						# Stock is sinking relative to ETF
						cur_rs = cur_roc / stocks[t]['cur_roc']
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					else:
						# Both stocks are rising
						cur_rs = cur_roc / stocks[t]['cur_roc']
						if ( cur_algo['check_etf_indicators_strict'] == True ):
							stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False
						else:
							if ( cur_rs > 10 ):
								stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

					if ( cur_algo['etf_min_rs'] != None and abs(cur_rs) < cur_algo['etf_min_rs'] ):
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

			# VWAP signal
			# This is the most simple/pessimistic approach right now
			if ( cur_algo['vwap'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['vwap_signal'] = False
				if ( last_close < cur_vwap ):
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

				# PDC
				if ( stocks[ticker]['previous_day_close'] != 0 ):
					if ( abs((stocks[ticker]['previous_day_close'] / last_close - 1) * 100) <= price_resistance_pct ):

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
								print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# NATR resistance
				if ( cur_algo['use_natr_resistance'] == True and stocks[ticker]['natr_daily'] != None ):
					if ( last_close > stocks[ticker]['previous_day_close'] ):
						natr_mod = 1
						if ( stocks[ticker]['natr_daily'] >= 8 ):
							natr_mod = 2

						natr_resistance = ((stocks[ticker]['natr_daily'] / natr_mod) / 100 + 1) * stocks[ticker]['previous_day_close']
						if ( last_close > natr_resistance ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 12 and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

						if ( abs((last_close / natr_resistance - 1) * 100) <= price_resistance_pct ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 10 and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# VWAP
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
						abs((cur_vwap / last_close - 1) * 100) <= price_resistance_pct ):

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
							print( '(' + str(ticker) + ') BUY SIGNAL stalled due to VWAP resistance - Current VWAP: ' + str(round(cur_vwap, 3)) + ' / 15-min Avg: ' + str(round(avg, 3)) )
							print()

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
					if ( last_close < hod ):
						if ( abs((last_close / hod - 1) * 100) <= price_resistance_pct ):
							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

					# Check PDH/PDL resistance
					avg = 0
					for i in range(15, 0, -1):
						avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
					avg = avg / 15

					# If stock opened below PDH, then those can become additional resistance lines for long entry
					if ( stocks[ticker]['today_open'] < stocks[ticker]['previous_day_high'] ):
						if ( avg < stocks[ticker]['previous_day_high'] and abs((last_close / stocks[ticker]['previous_day_high'] - 1) * 100) <= price_resistance_pct ):
							print( '(' + str(ticker) + ') BUY SIGNAL stalled due to PDL resistance - Current Price: ' + str(round(last_close, 3)) + ' / 15-min Avg: ' + str(round(avg, 3)) )
							print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# END HOD/LOD/PDH/PDL Check

				# Key Levels
				# Check if price is near historic key level
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True ):
					near_keylevel = False
					for lvl,dt in stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']:
						if ( abs((lvl / last_close - 1) * 100) <= price_support_pct ):
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
									print()

								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
								break

					# If keylevel_strict is True then only buy the stock if price is near a key level
					# Otherwise reject this buy to avoid getting chopped around between levels
					if ( args.keylevel_strict == True and near_keylevel == False ):
						if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
							print( '(' + str(ticker) + ') BUY SIGNAL stalled due to keylevel_strict - Current price: ' + str(round(last_close, 2)) )
							print()

						stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# End Key Levels

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):

				stacked_ma_signal		= stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal']
				stochrsi_5m_signal		= stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal']
				stochmfi_signal			= stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal']
				stochmfi_5m_signal		= stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal']
				rsi_signal			= stocks[ticker]['algo_signals'][algo_id]['rsi_signal']
				mfi_signal			= stocks[ticker]['algo_signals'][algo_id]['mfi_signal']
				adx_signal			= stocks[ticker]['algo_signals'][algo_id]['adx_signal']
				dmi_signal			= stocks[ticker]['algo_signals'][algo_id]['dmi_signal']
				aroonosc_signal			= stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal']
				macd_signal			= stocks[ticker]['algo_signals'][algo_id]['macd_signal']
				chop_signal			= stocks[ticker]['algo_signals'][algo_id]['chop_signal']
				supertrend_signal		= stocks[ticker]['algo_signals'][algo_id]['supertrend_signal']
				bbands_kchan_init_signal	= stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal']
				bbands_kchan_signal		= stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal']
				rs_signal			= stocks[ticker]['algo_signals'][algo_id]['rs_signal']
				vwap_signal			= stocks[ticker]['algo_signals'][algo_id]['vwap_signal']
				vpt_signal			= stocks[ticker]['algo_signals'][algo_id]['vpt_signal']
				resistance_signal		= stocks[ticker]['algo_signals'][algo_id]['resistance_signal']

				stocks[ticker]['final_buy_signal'] = True

				if ( cur_algo['stacked_ma'] == True and stacked_ma_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

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

				if ( (cur_algo['bbands_kchannel'] == True or cur_algo['bbands_kchannel_simple'] == True) and bbands_kchan_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['check_etf_indicators'] == True and rs_signal != True ):
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
				stocks[ticker]['stock_qty'] = int( cur_algo['stock_usd'] / float(last_price) )

				# Purchase the stock
				if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == True ):
					print( 'Purchasing ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker) + ' (' + str(cur_algo['algo_id'])  + ')' )
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

				stocks[ticker]['base_price']	= stocks[ticker]['orig_base_price']
				stocks[ticker]['primary_algo']	= cur_algo['algo_id']
				net_change			= 0

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

					elif ( stocks[ticker]['cur_natr'] * 2 < stocks[ticker]['decr_threshold'] ):
						stocks[ticker]['decr_threshold'] = stocks[ticker]['cur_natr'] * 2

				# VARIABLE EXIT


		# SELL MODE - look for a signal to sell the stock
		elif ( signal_mode == 'sell' ):

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
					if ( net_change < 0 ):
						stocks[ticker]['failed_usd'] += net_change
						if ( stocks[ticker]['failed_usd'] <= 0 ):
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

			# If stock is sinking over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( cur_algo['use_bbands_kchannel_xover_exit'] == True ):

				cur_bbands_lower	= round( cur_bbands[0], 3 )
				cur_bbands_upper	= round( cur_bbands[2], 3 )
				cur_kchannel_lower	= round( cur_kchannel[0], 3 )
				cur_kchannel_upper	= round( cur_kchannel[2], 3 )

				# Standard candles
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

				# Heikin Ashi candles
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				# Handle adverse conditions before the crossover
				if ( cur_kchannel_lower < cur_bbands_lower and cur_kchannel_upper > cur_bbands_upper ):
					if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] == True ):

						# BBands and KChannel crossed over, but then crossed back. This usually
						#  indicates that the stock is being choppy or changing direction. Check
						#  the direction of the stock, and if it's moving in the wrong direction
						#  then just exit. If we exit early we might even have a chance to re-enter
						#  in the right direction.
						if (cur_algo['primary_stacked_ma'] == True ):
							if ( stacked_ma_bear_affinity == True and last_close < stocks[ticker]['orig_base_price'] ):
								stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

					if ( cur_algo['primary_stacked_ma'] == True ):
						if ( stacked_ma_bear_affinity == True ):

							# Stock momentum switched directions after entry and before crossover
							stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] -= 1
							if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] <= -cur_algo['bbands_kchannel_xover_exit_count'] and last_close < stocks[ticker]['orig_base_price'] ):
								if ( stocks[ticker]['decr_threshold'] > 0.5 ):
									stocks[ticker]['decr_threshold'] = 0.5

						# Reset bbands_kchan_xover_counter if momentum switched back
						elif ( stacked_ma_bull_affinity == True ):
							stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 0

				# Handle adverse conditions after the crossover
				elif ( cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper ):
					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] = True

					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] <= 0 ):
						stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 1

					if ( cur_algo['primary_stacked_ma'] == True ):
						if ( stacked_ma_bear_affinity == True or stacked_ma_bear_ha_affinity == True ):
							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['decr_threshold'] = 1

			# STOPLOSS MONITOR
			# If price decreases
			if ( last_price < stocks[ticker]['base_price'] and stocks[ticker]['exit_percent_signal'] == False ):
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
						stocks[ticker]['failed_usd'] += net_change
						if ( stocks[ticker]['failed_usd'] <= 0 or stocks[ticker]['failed_txs'] <= 0 ):
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


			# ADDITIONAL EXIT STRATEGIES
			# Sell if --exit_percent was set and threshold met
			if ( stocks[ticker]['exit_percent'] != None and last_price > stocks[ticker]['orig_base_price'] ):
				total_percent_change = abs( stocks[ticker]['orig_base_price'] / last_price - 1 ) * 100
				high_percent_change = abs( stocks[ticker]['orig_base_price'] / last_high - 1 ) * 100

				if ( total_percent_change >= stocks[ticker]['exit_percent'] ):
					stocks[ticker]['exit_percent_signal'] = True

					# Once we've hit exit_percent, move the stoploss to break even
					stocks[ticker]['decr_threshold'] = stocks[ticker]['exit_percent']

				# Set the stoploss lower if the candle touches the exit_percent, but closes below it
				elif ( high_percent_change >= stocks[ticker]['exit_percent'] and total_percent_change < stocks[ticker]['exit_percent'] and
						stocks[ticker]['exit_percent_signal'] == False ):
					if ( stocks[ticker]['decr_threshold'] > 1 ):
						stocks[ticker]['decr_threshold'] = 1

				# If exit_percent has been hit, we will sell at the first RED candle
				if ( stocks[ticker]['exit_percent_signal'] == True ):

					if ( cur_algo['use_ha_exit'] == True ):
						last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
						last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']
						if ( last_close < last_open ):
							stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

					elif ( cur_algo['use_trend_exit'] == True ):
						if ( cur_algo['use_ha_exit'] == True ):
							cndls = stocks[ticker]['pricehistory']['hacandles']
						else:
							cndls = stocks[ticker]['pricehistory']['candles']

						# We need to pull the latest n-period candles from pricehistory and send it
						#  to our function.
						period = 5
						cndl_slice = []
						for i in range(period+1, 0, -1):
							cndl_slice.append( cndls[-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bull') == False ):
							stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

					elif ( cur_algo['use_combined_exit'] ):
						trend_exit	= False
						ha_exit		= False

						# Check Trend
						period = 2
						cndl_slice = []
						for i in range(period+1, 0, -1):
							cndl_slice.append( stocks[ticker]['pricehistory']['candles'][-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bull') == False ):
							trend_exit = True

						# Check Heikin Ashi candles
						last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
						last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']
						if ( last_close < last_open ):
							ha_exit = True

						if ( trend_exit == True and ha_exit == True ):
							stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

					elif ( last_close < last_open ):
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

			elif ( stocks[ticker]['exit_percent_signal'] == True and last_close < stocks[ticker]['orig_base_price'] ):
				# If we get to this point then the exit_percent_signal was triggered, but then the stock
				#  rapidly changed direction below cost basis. But because exit_percent_signal was triggered
				#  the stoploss routine above will not catch this. So at this point we probably need to stop out.
				stocks[ticker]['exit_percent_signal'] = False
				stocks[ticker]['decr_threshold'] = 0.5


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
					stocks[ticker]['failed_usd'] += net_change
					if ( stocks[ticker]['failed_usd'] <= 0 or stocks[ticker]['failed_txs'] <= 0 ):
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

			# Bollinger Bands and Keltner Channel
			# We put this above the primary indicator since we want to keep track of what the
			#  Bollinger bands and Keltner channel are doing across buy/short transitions.
			if ( cur_algo['bbands_kchannel'] == True or cur_algo['bbands_kchannel_simple'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] ) = bbands_kchannels( pricehistory=stocks[ticker]['pricehistory'], simple=cur_algo['bbands_kchannel_simple'], cur_bbands=cur_bbands, prev_bbands=prev_bbands,
																cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
																bbands_kchan_signal_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
																bbands_kchan_xover_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'],
																bbands_kchan_init_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
																bbands_kchan_crossover_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
																bbands_kchan_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
																debug=True )

			# PRIMARY STOCHRSI MONITOR
			if ( cur_algo['primary_stochrsi'] == True or cur_algo['primary_stochmfi'] == True ):

				# Jump to buy mode if StochRSI K and D are already below stoch_low_limit
				# The intent here is if the bot starts up while the RSI is low we don't want to wait until the stock
				#  does a full loop again before acting on it.
				if ( cur_rsi_k < stoch_default_low_limit and cur_rsi_d < stoch_default_low_limit and args.shortonly == False ):
					print('(' + str(ticker) + ') StochRSI K and D values already below ' + str(stoch_default_low_limit) + ', switching to buy mode.')
					reset_signals(ticker, id=algo_id, signal_mode='buy')
					continue

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

			# PRIMARY STACKED MOVING AVERAGE
			elif ( cur_algo['primary_stacked_ma'] == True ):

				# Standard candles
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

				# Heikin Ashi candles
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				# TTM Trend
				if ( cur_algo['use_trend'] == True ):
					cndl_slice	= []
					for i in range(cur_algo['trend_period']+1, 0, -1):
						cndl_slice.append( stocks[ticker]['pricehistory']['candles'][-i] )

					price_trend_bear_affinity = price_trend(cndl_slice, type=cur_algo['trend_type'], period=cur_algo['trend_period'], affinity='bear')
					price_trend_bull_affinity = price_trend(cndl_slice, type=cur_algo['trend_type'], period=cur_algo['trend_period'], affinity='bull')

				# Jump to short mode if the stacked moving averages are showing a bearish movement
				if ( args.shortonly == False and
						(cur_algo['use_ha_candles'] == True and (stacked_ma_bull_ha_affinity == True or stacked_ma_bull_affinity == True)) or
						(cur_algo['use_trend'] == True and price_trend_bull_affinity == True) or
						(cur_algo['use_ha_candles'] == False and cur_algo['use_trend'] == False and stacked_ma_bull_affinity == True) ):

					print('(' + str(ticker) + ') StackedMA values indicate bullish trend ' + str(cur_s_ma_primary) + ", switching to long mode.\n")
					reset_signals(ticker, id=algo_id, signal_mode='buy', exclude_bbands_kchan=True)
					continue

				elif ( cur_algo['use_ha_candles'] == True and stacked_ma_bear_ha_affinity == True or stacked_ma_bear_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

				elif ( cur_algo['use_trend'] == True and price_trend_bear_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

				elif ( cur_algo['use_ha_candles'] == False and cur_algo['use_trend'] == False and stacked_ma_bear_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

				else:
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = False

			# Secondary Stacked Moving Average
			if ( cur_algo['stacked_ma'] == True ):
				if ( check_stacked_ma(cur_s_ma, 'bear') == True ):
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = True
				else:
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = False

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

			# Relative Strength
			if ( cur_algo['check_etf_indicators'] == True ):
				cur_rs = 0
				for t in cur_algo['etf_tickers'].split(','):

					if ( cur_roc > 0 and stocks[t]['cur_roc'] < 0 ):
						# Stock is rising compared to ETF
						cur_rs = abs( cur_roc / stocks[t]['cur_roc'] )
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					elif ( cur_roc < 0 and stocks[t]['cur_roc'] < 0 ):
						# Both stocks are sinking
						cur_rs = -( cur_roc / stocks[t]['cur_roc'] )
						if ( cur_algo['check_etf_indicators_strict'] == True ):
							stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False
						else:
							if ( abs(cur_rs) > 10 ):
								stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

					elif ( cur_roc < 0 and stocks[t]['cur_roc'] > 0 ):
						# Stock is sinking relative to ETF
						cur_rs = cur_roc / stocks[t]['cur_roc']
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

					else:
						# Both stocks are rising
						cur_rs = cur_roc / stocks[t]['cur_roc']
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					if ( cur_algo['etf_min_rs'] != None and abs(cur_rs) < cur_algo['etf_min_rs'] ):
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

			# VWAP signal
			# This is the most simple/pessimistic approach right now
			if ( cur_algo['vwap'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['vwap_signal'] = False
				if ( last_close > cur_vwap ):
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

				# PDC
				if ( stocks[ticker]['previous_day_close'] != 0 ):
					if ( abs((stocks[ticker]['previous_day_close'] / last_close - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to PDC
						# Next check average of last 15 (minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
						avg = avg / 15

						# If average was below PDC then PDC is resistance (good for short)
						# If average was above PDC then PDC is support (bad for short)
						if ( avg > stocks[ticker]['previous_day_close'] ):
							if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):
								print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to PDC resistance - PDC: ' + str(round(stocks[ticker]['previous_day_close'], 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )
								print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# NATR resistance
				if ( cur_algo['use_natr_resistance'] == True and stocks[ticker]['natr_daily'] != None ):
					if ( last_close < stocks[ticker]['previous_day_close'] ):
						natr_mod = 1
						if ( stocks[ticker]['natr_daily'] >= 8 ):
							natr_mod = 2

						natr_resistance = ((stocks[ticker]['natr_daily'] / natr_mod) / 100 + 1) * stocks[ticker]['previous_day_close']
						if ( last_close > natr_resistance ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 12 and stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

						if ( abs((last_close / natr_resistance - 1) * 100) <= price_resistance_pct ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 10 and stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# VWAP
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
						abs((cur_vwap / last_close - 1) * 100) <= price_resistance_pct ):

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
							print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to VWAP resistance - Current VWAP: ' + str(round(cur_vwap, 3)) + ' / 15-min Avg: ' + str(round(avg, 3)) )
							print()

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
					if ( last_close > lod ):
						if ( abs((lod / last_close - 1) * 100) <= price_resistance_pct ):
							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

					# Check PDH/PDL resistance
					avg = 0
					for i in range(15, 0, -1):
						avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
					avg = avg / 15

					# If stock opened above PDL, then those can become additional resistance lines for short entry
					if ( stocks[ticker]['today_open'] > stocks[ticker]['previous_day_low'] ):
						if ( avg > stocks[ticker]['previous_day_low'] and abs((last_close / stocks[ticker]['previous_day_low'] - 1) * 100) <= price_resistance_pct ):
							print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to PDL resistance - Current Price: ' + str(round(last_close, 3)) + ' / 15-min Avg: ' + str(round(avg, 3)) )
							print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

                                # END HOD/LOD/PDH/PDL Check

				# Key Levels
				# Check if price is near historic key level
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True ):
					near_keylevel = False
					for lvl,dt in stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']:
						if ( abs((lvl / last_close - 1) * 100) <= price_resistance_pct ):
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
									print()

								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
								break

					# If keylevel_strict is True then only short the stock if price is near a key level
					# Otherwise reject this short altogether to avoid getting chopped around between levels
					if ( args.keylevel_strict == True and near_keylevel == False ):
						if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True and debug == True ):
							print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to keylevel_strict - Current price: ' + str(round(last_close, 2)) )
							print()

						stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# End Key Levels

			# Resolve the primary stochrsi short_signal with the secondary indicators
			if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):

				stacked_ma_signal		= stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal']
				stochrsi_5m_signal		= stocks[ticker]['algo_signals'][algo_id]['stochrsi_5m_final_signal']
				stochmfi_signal			= stocks[ticker]['algo_signals'][algo_id]['stochmfi_final_signal']
				stochmfi_5m_signal		= stocks[ticker]['algo_signals'][algo_id]['stochmfi_5m_final_signal']
				rsi_signal			= stocks[ticker]['algo_signals'][algo_id]['rsi_signal']
				mfi_signal			= stocks[ticker]['algo_signals'][algo_id]['mfi_signal']
				adx_signal			= stocks[ticker]['algo_signals'][algo_id]['adx_signal']
				dmi_signal			= stocks[ticker]['algo_signals'][algo_id]['dmi_signal']
				aroonosc_signal			= stocks[ticker]['algo_signals'][algo_id]['aroonosc_signal']
				macd_signal			= stocks[ticker]['algo_signals'][algo_id]['macd_signal']
				chop_signal			= stocks[ticker]['algo_signals'][algo_id]['chop_signal']
				supertrend_signal		= stocks[ticker]['algo_signals'][algo_id]['supertrend_signal']
				bbands_kchan_init_signal	= stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal']
				bbands_kchan_signal		= stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal']
				rs_signal			= stocks[ticker]['algo_signals'][algo_id]['rs_signal']
				vwap_signal			= stocks[ticker]['algo_signals'][algo_id]['vwap_signal']
				vpt_signal			= stocks[ticker]['algo_signals'][algo_id]['vpt_signal']
				resistance_signal		= stocks[ticker]['algo_signals'][algo_id]['resistance_signal']

				stocks[ticker]['final_short_signal'] = True

				if ( cur_algo['stacked_ma'] == True and stacked_ma_signal != True ):
					stocks[ticker]['final_short_signal'] = False

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

				if ( (cur_algo['bbands_kchannel'] == True or cur_algo['bbands_kchannel_simple'] == True) and bbands_kchan_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['check_etf_indicators'] == True and rs_signal != True ):
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
				stocks[ticker]['stock_qty'] = int( cur_algo['stock_usd'] / float(last_price) )

				# Short the stock
				if ( tda_gobot_helper.ismarketopen_US(safe_open=safe_open) == True ):
					print( 'Shorting ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker) + ' (' + str(cur_algo['algo_id'])  + ')' )
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

				stocks[ticker]['base_price']	= stocks[ticker]['orig_base_price']
				stocks[ticker]['primary_algo']	= cur_algo['algo_id']
				net_change			= 0

				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=False)

				# Reset and switch all algos to 'buy_to_cover' mode for the next loop
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

					elif ( stocks[ticker]['cur_natr'] * 2 < stocks[ticker]['decr_threshold'] ):
						stocks[ticker]['decr_threshold'] = stocks[ticker]['cur_natr'] * 2

				# VARIABLE EXIT


		# BUY_TO_COVER a previous short sale
		# This mode must always follow a previous "short" signal. We will monitor the RSI and initiate
		#   a buy-to-cover transaction to cover a previous short sale if the RSI if very low. We also
		#   need to monitor stoploss in case the stock rises above a threshold.
		elif ( signal_mode == 'buy_to_cover' ):

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
					if ( net_change > 0 ):
						stocks[ticker]['failed_usd'] -= net_change
						if ( stocks[ticker]['failed_usd'] <= 0 ):
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

			# If stock is rising over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( cur_algo['use_bbands_kchannel_xover_exit'] == True ):

				cur_bbands_lower	= round( cur_bbands[0], 3 )
				cur_bbands_upper	= round( cur_bbands[2], 3 )
				cur_kchannel_lower	= round( cur_kchannel[0], 3 )
				cur_kchannel_upper	= round( cur_kchannel[2], 3 )

				# Standard candles
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

				# Heikin Ashi candles
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				# Handle adverse conditions before the crossover
				if ( cur_kchannel_lower < cur_bbands_lower and cur_kchannel_upper > cur_bbands_upper ):
					if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] == True ):

						# BBands and KChannel crossed over, but then crossed back. This usually
						#  indicates that the stock is being choppy or changing direction. Check
						#  the direction of the stock, and if it's moving in the wrong direction
						#  then just exit. If we exit early we might even have a chance to re-enter
						#  in the right direction.
						if (cur_algo['primary_stacked_ma'] == True ):
							if ( stacked_ma_bull_affinity == True and last_close > stocks[ticker]['orig_base_price'] ):
								stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

					if ( cur_algo['primary_stacked_ma'] == True ):
						if ( stacked_ma_bull_affinity == True or stacked_ma_bull_ha_affinity == True ):

							# Stock momentum switched directions after entry and before crossover
							stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] -= 1
							if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] <= -cur_algo['bbands_kchannel_xover_exit_count'] and last_close > stocks[ticker]['orig_base_price'] ):
								if ( stocks[ticker]['decr_threshold'] > 0.5 ):
									stocks[ticker]['decr_threshold'] = 0.5

						# Reset bbands_kchan_xover_counter if momentum switched back
						elif ( stacked_ma_bear_affinity == True ):
							stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 0

				# Handle adverse conditions after the crossover
				elif ( cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper ):
					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] = True

					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] <= 0 ):
						stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 1

					if ( cur_algo['primary_stacked_ma'] == True ):
						if ( stacked_ma_bull_affinity == True or stacked_ma_bull_ha_affinity == True ):
							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['decr_threshold'] = 1

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
			elif ( last_price > stocks[ticker]['base_price'] and stocks[ticker]['exit_percent_signal'] == False ):
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
						stocks[ticker]['failed_usd'] -= net_change
						if ( stocks[ticker]['failed_usd'] <= 0 or stocks[ticker]['failed_txs'] <= 0 ):
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


			# ADDITIONAL EXIT STRATEGIES
			# Sell if --exit_percent was set and threshold met
			if ( stocks[ticker]['exit_percent'] != None and last_price < stocks[ticker]['orig_base_price'] ):
				total_percent_change = abs( last_price / stocks[ticker]['orig_base_price'] - 1 ) * 100
				low_percent_change = abs( last_low / stocks[ticker]['orig_base_price'] - 1 ) * 100

				if ( total_percent_change >= stocks[ticker]['exit_percent'] ):
					stocks[ticker]['exit_percent_signal'] = True

					# Once we've hit exit_percent, move the stoploss to break even
					stocks[ticker]['decr_threshold'] = stocks[ticker]['exit_percent']

				# Set the stoploss lower if the candle touches the exit_percent, but closes above it
				elif ( low_percent_change >= stocks[ticker]['exit_percent'] and total_percent_change < stocks[ticker]['exit_percent'] and
						stocks[ticker]['exit_percent_signal'] == False ):
					if ( stocks[ticker]['decr_threshold'] > 1 ):
						stocks[ticker]['decr_threshold'] = 1

				# If exit_percent has been hit, we will sell at the first GREEN candle
				if ( stocks[ticker]['exit_percent_signal'] == True ):

					if ( cur_algo['use_ha_exit'] == True ):
						last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
						last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']
						if ( last_close > last_open ):
							stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

					elif ( cur_algo['use_trend_exit'] == True ):
						if ( cur_algo['use_ha_exit'] == True ):
							cndls = stocks[ticker]['pricehistory']['hacandles']
						else:
							cndls = stocks[ticker]['pricehistory']['candles']

						# We need to pull the latest n-period candles from pricehistory and send it
						#  to our function.
						period = 5
						cndl_slice = []
						for i in range(period+1, 0, -1):
							cndl_slice.append( cndls[-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bear') == False ):
							stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

					elif ( cur_algo['use_combined_exit'] ):
						trend_exit	= False
						ha_exit		= False

						# Check Trend
						period = 2
						cndl_slice = []
						for i in range(period+1, 0, -1):
							cndl_slice.append( stocks[ticker]['pricehistory']['candles'][-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bear') == False ):
							trend_exit = True

						# Check Heikin Ashi candles
						last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
						last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']
						if ( last_close > last_open ):
							ha_exit = True

						if ( trend_exit == True and ha_exit == True ):
							stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

					elif ( last_close > last_open ):
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

			elif ( stocks[ticker]['exit_percent_signal'] == True and last_close > stocks[ticker]['orig_base_price'] ):
				# If we get to this point then the exit_percent_signal was triggered, but then the stock
				#  rapidly changed direction above cost basis. But because exit_percent_signal was triggered
				#  the stoploss routine above will not catch this. So at this point we probably need to stop out.
				stocks[ticker]['exit_percent_signal'] = False
				stocks[ticker]['decr_threshold'] = 0.5

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
					stocks[ticker]['failed_usd'] -= net_change
					if ( stocks[ticker]['failed_usd'] <= 0 or stocks[ticker]['failed_txs'] <= 0 ):
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

