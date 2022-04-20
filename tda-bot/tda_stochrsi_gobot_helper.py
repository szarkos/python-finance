#!/usr/bin/python3 -u

import os, sys, signal
import time, datetime, pytz, random
from collections import OrderedDict
import pickle
import numpy as np

from func_timeout import func_timeout, FunctionTimedOut

import tda_gobot_helper
import tda_algo_helper


# Runs from stream_client.handle_message() - calls stochrsi_gobot() with each
#  set of specified algorithms
def gobot_run(stream=None, algos=None, debug=False):

	if not isinstance(stream, dict):
		print('Error: gobot_run() called without valid stream{} data.', file=sys.stderr)
		return False

	if not isinstance(algos, list):
		print('Error: gobot_run() called without valid algos[] list', file=sys.stderr)
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

		# First check that the last candle is not a temporary candle added via Level 1 stream
		if ( stocks[ticker]['pricehistory']['candles'][-1]['datetime'] == 9999999999999 ):
			del stocks[ticker]['pricehistory']['candles'][-1]

		# Add new candle
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
		ret = stochrsi_gobot( cur_algo=algo_list, caller_id='chart_equity', debug=debug )
		if ( ret == False ):
			print('Error: gobot_run(): stochrsi_gobot(' + str(algo) + '): returned False', file=sys.stderr)


	# After all the algos have been processed, iterate through tickers again and set
	#  the prev_seq to the cur_seq. This provides a record of sequence numbers to ensure
	#  that we do not process the same candles twice.
	for idx in stream['content']:
		ticker = idx['key']
		if ( stocks[ticker]['isvalid'] == False ):
			continue

		stocks[ticker]['prev_seq'] = stocks[ticker]['cur_seq']

	return True


# Handle level1 stream
def gobot_level1(stream=None, algos=None, debug=False):

	if not isinstance(stream, dict):
		print('Error: gobot_level1() called without valid stream{} data.', file=sys.stderr)
		return False

	# Level1 quote data fields
	# Documentation: https://developer.tdameritrade.com/content/streaming-data#_Toc504640599
	#
	# 0	Symbol			String	Ticker symbol in upper case
	# 1	Bid Price		float	Current Best Bid Price
	# 2	Ask Price		float	Current Best Ask Price
	# 3	Last Price		float	Price at which the last trade was matched
	# 4	Bid Size		float	Number of shares for bid
	# 5	Ask Size		float	Number of shares for ask
	# 8	Total Volume		long	Aggregated shares traded throughout the day, including pre/post market hours. Volume is set to zero at 7:28am ET. 
	# 9	Last Size		float	Number of shares traded with last trade	Size in 100’s
	# 14	Bid Tick		char	Indicates Up or Downtick (NASDAQ NMS & Small Cap) - SAZ Note: this doesn't seem to be populated.
	# 48	Security Status		String	Indicates a symbols current trading status, Normal, Halted, Closed
	dt = int( stream['timestamp'] )
	for idx in stream['content']:
		ticker					= str( idx['key'] )
		idx['datetime']				= dt

		stocks[ticker]['ask_price']		= float( idx['ASK_PRICE'] )	if ('ASK_PRICE' in idx) else stocks[ticker]['ask_price']
		stocks[ticker]['ask_size']		= int( idx['ASK_SIZE'] )	if ('ASK_SIZE' in idx) else stocks[ticker]['ask_size']
		stocks[ticker]['bid_price']		= float( idx['BID_PRICE'] )	if ('BID_PRICE' in idx) else stocks[ticker]['bid_price']
		stocks[ticker]['bid_size']		= int( idx['BID_SIZE'] )	if ('BID_SIZE' in idx) else stocks[ticker]['bid_size']
		stocks[ticker]['last_price']		= float( idx['LAST_PRICE'] )	if ('LAST_PRICE' in idx) else stocks[ticker]['last_price']
		stocks[ticker]['last_size']		= int( idx['LAST_SIZE'] )	if ('LAST_SIZE' in idx) else stocks[ticker]['last_size']
		stocks[ticker]['total_volume']		= int( idx['TOTAL_VOLUME'] )	if ('TOTAL_VOLUME' in idx) else stocks[ticker]['total_volume']
		stocks[ticker]['security_status']	= str( idx['SECURITY_STATUS'] )	if ('SECURITY_STATUS' in idx) else stocks[ticker]['security_status']

		try:
			stocks[ticker]['bid_ask_pct'] = abs( stocks[ticker]['bid_price'] / stocks[ticker]['ask_price'] - 1 ) * 100
		except:
			stocks[ticker]['bid_ask_pct'] = 0

		# Keep a history of all bid/ask data
		# Level1 data can come in pieces if, i.e. only the bid or ask has changed,
		#  so lets make sure each update is a complete set of data.
		l1_history = {	'ASK_PRICE':	stocks[ticker]['ask_price'],
				'ASK_SIZE':	stocks[ticker]['ask_size'],
				'BID_PRICE':	stocks[ticker]['bid_price'],
				'BID_SIZE':	stocks[ticker]['bid_size'],
				'LAST_PRICE':	stocks[ticker]['last_price'],
				'LAST_SIZE':	stocks[ticker]['last_size'],
				'TOTAL_VOLUME':	stocks[ticker]['total_volume'],
				'datetime':	dt,
				'key':		ticker }

		stocks[ticker]['level1'][dt] = l1_history

	# Call stochrsi_gobot() for each set of specific algorithms
	for algo_list in algos:
		ret = stochrsi_gobot( cur_algo=algo_list, caller_id='level1', debug=debug )
		if ( ret == False ):
			print('Error: gobot_level1(): stochrsi_gobot(' + str(algo) + '): returned False', file=sys.stderr)

	return True


# Handle level2 stream
def gobot_level2(stream=None, debug=False):

	if not isinstance(stream, dict):
		print('Error: gobot_level2() called without valid stream{} data.', file=sys.stderr)
		return False

	# Level2 Order Books
	# Documentation:
	#  https://developer.tdameritrade.com/content/streaming-data#_Toc504640617
	#  https://developer.tdameritrade.com/content/streaming-data#_Toc504640616
	#
	# The var content['BIDS|ASKS']['BIDS|ASKS'] contains an array of bids/asks at each price,
	#   so you can consider the ASK|BID_PRICE to be the key to each array of bids/asks.
	#
	# We don't actually need to iterate through all the bids and asks because the
	#   NUM_BIDS|ASKS variable will tell us how many bids or asks there are at each price
	#   point. Also, the total volume nicely counts the volume of all the bids/asks at
	#   each price point. This is all we really care about right now.
	#
	# Note also that the ASK|BID_VOLUME and TOTAL_VOLUME is the actual amount. This
	#   is unlike the level1 or get_quote() bid/ask size which is the volume / 100.
	#
	#   'content': [ { 'ASKS': [ { 'ASKS': [{	'ASK_VOLUME': 9500,
	#						'EXCHANGE': 'EDGX',
	#						'SEQUENCE': 54441732 },
	#					{...}],
	#					'ASK_PRICE': 39.3,
	#					'NUM_ASKS': 2,
	#					'TOTAL_VOLUME': 9900},
	#
	#			 { 'ASKS': [ { ......}],
	#			],
	#
	#		   'BIDS': [ { 'BIDS': [{	'BID_VOLUME': 100,
	#						'EXCHANGE': 'NSDQ',
	#						'SEQUENCE': 54443420}
	#					{...}],
	#					'BID_PRICE': 39.22,
	#					'NUM_BIDS': 1,
	#					'TOTAL_VOLUME': 100},
	#			  { 'BIDS': [ { .... } ],
	#			],
	#		'BOOK_TIME': 1644354444545,
	#		'key': 'TICKER'}],
	#   'service': 'LISTED_BOOK',
	#   'timestamp': 1644354444643 }

	# The order book changes all the time and we don't want to keep stale
	#  info - so reset the asks/bids for each ticker contained in this stream
	#  before processing it.
	for idx in stream['content']:
		ticker = idx['key']
		stocks[ticker]['level2']['asks'] = {}
		stocks[ticker]['level2']['bids'] = {}

	# Process the stream
	dt_def = int( stream['timestamp'] )
	for idx in stream['content']:

		ticker = idx['key']
		try:
			dt = int( idx['BOOK_TIME'] )
		except:
			dt = dt_def

		# ASKS
		for ask in idx['ASKS']:
			ask_price = float( ask['ASK_PRICE'] )
			stocks[ticker]['level2']['asks'][ask_price] = {}

			stocks[ticker]['level2']['asks'][ask_price]['num_asks']		= int( ask['NUM_ASKS'] )
			stocks[ticker]['level2']['asks'][ask_price]['total_volume']	= int( ask['TOTAL_VOLUME'] )

		# The lowest ask price data should be the same as what we get from the level1 stream
		try:
			cur_ask_price = min( stocks[ticker]['level2']['asks'].keys() )
			stocks[ticker]['level2']['cur_ask']['ask_price']	= cur_ask_price
			stocks[ticker]['level2']['cur_ask']['num_asks']		= stocks[ticker]['level2']['asks'][cur_ask_price]['num_asks']
			stocks[ticker]['level2']['cur_ask']['total_volume']	= stocks[ticker]['level2']['asks'][cur_ask_price]['total_volume']

		except:
			# This means that there were no asks in the L2 data received
			pass

		# BIDS
		for bid in idx['BIDS']:
			bid_price							= float( bid['BID_PRICE'] )

			stocks[ticker]['level2']['bids'][bid_price]			= {}
			stocks[ticker]['level2']['bids'][bid_price]['num_bids']		= int( bid['NUM_BIDS'] )
			stocks[ticker]['level2']['bids'][bid_price]['total_volume']	= int( bid['TOTAL_VOLUME'] )

		# The highest bid price data should be the same as what we get from the level1 stream
		try:
			cur_bid_price = max( stocks[ticker]['level2']['bids'].keys() )
			stocks[ticker]['level2']['cur_bid']['bid_price']	= cur_bid_price
			stocks[ticker]['level2']['cur_bid']['num_bids']		= stocks[ticker]['level2']['bids'][cur_bid_price]['num_bids']
			stocks[ticker]['level2']['cur_bid']['total_volume']	= stocks[ticker]['level2']['bids'][cur_bid_price]['total_volume']

		except:
			# This means that there were no bids in the L2 data received
			pass

		# Populate stocks[ticker][ask_price/ask_size/bid_price/bid_size]
		# There are several ways to obtain the latest bid/ask price and size, so we use these additional variables
		#  to store the info in case the method changes later. We used to do obtain this data with the get_quote() API,
		#  then with the level1 stream, but now the level2 stream has this info and more, so let's use just level2 for now.
		try:
			stocks[ticker]['ask_price']	= stocks[ticker]['level2']['cur_ask']['ask_price']
			stocks[ticker]['ask_size']	= stocks[ticker]['level2']['cur_ask']['total_volume'] / 100
			stocks[ticker]['bid_price']	= stocks[ticker]['level2']['cur_bid']['bid_price']
			stocks[ticker]['bid_size']	= stocks[ticker]['level2']['cur_bid']['total_volume'] / 100

		except:
			pass

		# Set the bid/ask percent, which may be useful for gauging liquidity
		try:
			stocks[ticker]['bid_ask_pct'] = abs( stocks[ticker]['bid_price'] / stocks[ticker]['ask_price'] - 1 ) * 100
		except:
			stocks[ticker]['bid_ask_pct'] = 0

		# Archive level2 data to use later with backtesting
		stocks[ticker]['level2']['history'][dt]		= {}
		stocks[ticker]['level2']['history'][dt]['asks']	= stocks[ticker]['level2']['asks']
		stocks[ticker]['level2']['history'][dt]['bids']	= stocks[ticker]['level2']['bids']

	return True


# Equity Time and Sales
def gobot_ets(stream=None, debug=False):

	if not isinstance(stream, dict):
		print('Error: gobot_ets() called without valid stream{} data.', file=sys.stderr)
		return False

	for idx in stream['content']:
		ticker = idx['key']
		stocks[ticker]['ets'].append(idx)

		if ( debug == True ):
			print(idx)

	return True


# Find the right option contract to purchase
def search_options(ticker=None, option_type=None, near_expiration=False, debug=False):

	if ( ticker == None or option_type == None ):
		return False

	option_type = option_type.upper()
	if ( option_type != 'CALL' and option_type != 'PUT' ):
		return False

	# Option data to return to caller
	option_data = {	'ticker':	None,
			'type':		option_type,
			'range_val':	'NTM',
			'strike':	0,
			'bid':		0,
			'ask':		0,
			'delta':	0,
			'gamma':	0,
			'theta':	0,
			'vega':		0,
			'iv':		0 }

	# Search for options that expire either this week or next week
	dt		= datetime.datetime.now(mytimezone)
	start_day	= dt
	end_day		= dt + datetime.timedelta(days=7)
	if ( near_expiration == False ):
		start_day = dt + datetime.timedelta(days=1)
		if ( int(dt.strftime('%w')) >= 3 ):
			start_day	= dt + datetime.timedelta(days=6)
			end_day		= dt + datetime.timedelta(days=12)

	strike_count = 5
	try:
		option_chain = tda_gobot_helper.get_option_chains( ticker=ticker, contract_type=option_data['type'], strike_count=strike_count, range_value=option_data['range_val'],
									from_date=start_day.strftime('%Y-%m-%d'), to_date=end_day.strftime('%Y-%m-%d') )

	except Exception as e:
		print('Error: unable to look up option chain for stock ' + str(ticker) + ': ' + str(e), file=sys.stderr)
		return False

	ExpDateMap = 'callExpDateMap'
	if ( option_data['type'] == 'PUT' ):
		ExpDateMap = 'putExpDateMap'

	try:
		exp_date = list(option_chain[ExpDateMap].keys())[0]
	except Exception as e:
		print('Caught Exception: search_options(' + str(ticker) + '): ' + str(e))
		return False

	# For PUTs, reverse the list to get the optimal strike price
	iter = option_chain[ExpDateMap][exp_date].keys()
	if ( option_data['type'] == 'PUT' ):
		iter = reversed(option_chain[ExpDateMap][exp_date].keys())

	for key in iter:
		try:
			option_data['strike'] = float( key )

		except:
			if ( debug == True ):
				print('(' + str(ticker) + '): error processing option chain: ' + str(key), file=sys.stderr)
			continue

		else:
			key = option_chain[ExpDateMap][exp_date][key]

		# API returns a list for each strike price, but I've not yet seen any strike price
		#  data contain more than one entry. Possibly there are times when different brokers
		#  have different offerings for each strike price.
		key = key[0]

		# Find the first OTM option
		if ( key['inTheMoney'] == False ):

			option_data['ticker']	= str( key['symbol' ])
			option_data['bid']	= float( key['bid'] )
			option_data['ask']	= float( key['ask'] )
			option_data['delta']	= float( key['delta'] )
			option_data['gamma']	= float( key['gamma'] )
			option_data['theta']	= float( key['theta'] )
			option_data['vega']	= float( key['vega'] )
			option_data['iv']	= float( key['volatility'] )

			if ( debug == True ):
				bidask_pct = round( abs( option_data['bid'] / option_data['ask'] - 1 ) * 100, 3 )
				print( str(option_data['ticker']) + ' / Strike: ' + str(option_data['strike']) )
				print( 'Bid: ' + str(key['bid']) + ' / Ask: ' + str(key['ask']) + ' (' + str(bidask_pct) + '%)' )
				print( 'Delta: ' + str(key['delta']) )
				print( 'Gamma: ' + str(key['gamma']) )
				print( 'Theta: ' + str(key['theta']) )
				print( 'Vega: ' + str(key['vega']) )
				print( 'Volatility: ' + str(key['volatility']) )

				if ( bidask_pct > 1 ):
					print('Warning: bid/ask gap is bigger than 1% (' + str(bidask_pct) + ')')

				if ( abs(key['delta']) < 0.70 ):
					print('Warning: delta is less than 70% (' + str(abs(key['delta'])) + ')')

				if ( float(key['ask']) < 1 ):
					print('Warning: option price (' + str(key['ask']) + ') is <$1, accidental stoploss via jitter might occur')

			break

	if ( option_data['ticker'] == None ):
		if ( debug == True ):
			print('Unable to locate an available option to trade, exiting.')
		return False

	return option_data


# Reset all the long/sell/short/buy-to-cover and indicator signals
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

			# If switching into the 'long' or 'short' mode, reset the
			#  primary algo to None.
			if ( signal_mode == 'long' or signal_mode == 'short' ):
				stocks[ticker]['primary_algo']				= None

		stocks[ticker]['algo_signals'][algo_id]['buy_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['sell_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['short_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal']		= False

		stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['mesa_sine_signal']		= False

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
			stocks[ticker]['algo_signals'][algo_id]['bbands_roc_threshold_signal']		= False
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal']	= False
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal']			= False
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter']		= 0
			stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter']		= 0
			stocks[ticker]['algo_signals'][algo_id]['bbands_roc_counter']			= 0

		stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']		= False
		stocks[ticker]['algo_signals'][algo_id]['trin_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['trin_counter']			= 0

		stocks[ticker]['algo_signals'][algo_id]['tick_signal']			= False
		stocks[ticker]['algo_signals'][algo_id]['roc_signal']			= False

		stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal']	= False
		stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal']		= False

		stocks[ticker]['algo_signals'][algo_id]['plus_di_crossover']		= False
		stocks[ticker]['algo_signals'][algo_id]['minus_di_crossover']		= False
		stocks[ticker]['algo_signals'][algo_id]['macd_crossover']		= False
		stocks[ticker]['algo_signals'][algo_id]['macd_avg_crossover']		= False

	return True


# Save the pricehistory data for later analysis. This is typically called on exit.
def export_pricehistory():

	import lzma

	# Append today's date to files for archiving
	dt_today = datetime.datetime.now(mytimezone).strftime('%Y-%m-%d')

	print("Writing stock pricehistory to ./" + args.tx_log_dir + '/' + str(dt_today) + "/\n")
	try:
		if ( os.path.isdir('./' + str(args.tx_log_dir)) == False ):
			os.mkdir('./' + str(args.tx_log_dir), mode=0o755)
		if ( os.path.isdir('./' + str(args.tx_log_dir) + '/' + str(dt_today)) == False ):
			os.mkdir('./' + str(args.tx_log_dir) + '/' + str(dt_today), mode=0o755)

	except OSError as e:
		print('Error: export_pricehistory(): Unable to make TX_LOG_DIR: ' + str(e), file=sys.stderr)
		return False


	base_dir = './' + str(args.tx_log_dir) + '/' + str(dt_today) + '/'
	for ticker in stocks.keys():
		if ( len(stocks[ticker]['pricehistory']) == 0 ):
			continue

		# Export pricehistory
		try:
			fname = base_dir + str(ticker) + '-' + str(dt_today) + '.pickle.xz'
			with lzma.open(fname, 'wb') as handle:
				pickle.dump(stocks[ticker]['pricehistory'], handle)
				handle.flush()

		except Exception as e:
			print('Warning: Unable to write pricehistory data to file ' + str(fname) + ': ' + str(e), file=sys.stderr)
			pass

		# Export 5-minute pricehistory
		# SAZ 2022-02-08 - This is no longer needed
		#try:
		#	fname = base_dir + str(ticker) + '_5m-' + str(dt_today) + '.pickle.xz'
		#	with lzma.open(fname, 'wb') as handle:
		#		pickle.dump(stocks[ticker]['pricehistory_5m'], handle)
		#		handle.flush()
		#except Exception as e:
		#	print('Warning: Unable to write to pricehistory_5m data file ' + str(fname) + ': ' + str(e), file=sys.stderr)
		#	pass

		# Export level 1 data
		try:
			fname = base_dir + str(ticker) + '_level1-' + str(dt_today) + '.pickle.xz'
			with lzma.open(fname, 'wb') as handle:
				pickle.dump(stocks[ticker]['level1'], handle)
				handle.flush()
		except Exception as e:
			print('Warning: Unable to write level1 data to file ' + str(fname) + ': ' + str(e), file=sys.stderr)
			pass

		# Export level 2 data
		try:
			fname = base_dir + str(ticker) + '_level2-' + str(dt_today) + '.pickle.xz'
			with lzma.open(fname, 'wb') as handle:
				pickle.dump(stocks[ticker]['level2']['history'], handle)
				handle.flush()

		except Exception as e:
			print('Warning: Unable to write level2 data to file ' + str(fname) + ': ' + str(e), file=sys.stderr)
			pass

		# Export equity time and sale data
		try:
			fname = base_dir + str(ticker) + '_ets-' + str(dt_today) + '.pickle.xz'
			with lzma.open(fname, 'wb') as handle:
				pickle.dump(stocks[ticker]['ets'], handle)
				handle.flush()

		except Exception as e:
			print('Warning: Unable to write ets data to file ' + str(fname) + ': ' + str(e), file=sys.stderr)
			pass

	return True


# Main helper function for tda-stochrsi-gobot-v2 that implements the primary stochrsi
#  algorithm along with any secondary algorithms specified.
def stochrsi_gobot( cur_algo=None, caller_id=None, debug=False ):

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
	if ( tda_gobot_helper.ismarketopen_US(safe_open=cur_algo['safe_open']) == False ):
		if ( args.singleday == False and args.multiday == False ):
			print('Market closed, exiting.')
			export_pricehistory()
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


	# Bollinger Bands and Keltner Channel crossover
	def bbands_kchannels(pricehistory=None, cur_bbands=(0,0,0), prev_bbands=(0,0,0), cur_kchannel=(0,0,0), prev_kchannel=(0,0,0), bbands_roc=None,
				bbands_kchan_signal_counter=0, bbands_kchan_xover_counter=0, bbands_roc_counter=0, bbands_kchan_ma=[],
				bbands_kchan_init_signal=False, bbands_roc_threshold_signal=False, bbands_kchan_crossover_signal=False, bbands_kchan_signal=False, debug=False ):

		nonlocal cur_algo
		nonlocal signal_mode
		nonlocal cur_rsi_k

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

		cur_bbands_roc		= 0
		prev_bbands_roc		= 0
		if ( bbands_roc != None ):
			try:
				cur_bbands_roc		= bbands_roc[-1]
				prev_bbands_roc		= bbands_roc[-2]
			except:
				cur_bbands_roc = prev_bbands_roc = 0

		# If the Bollinger Bands are outside the Keltner channel and the init signal hasn't been triggered,
		#  then we can just make sure everything is reset and return False. We need to make sure that at least
		#  bbands_kchan_signal_counter is reset and is not left set to >0 after a half-triggered squeeze.
		#
		# If the init signal has been triggered then we can move on and the signal may be canceled later
		#  either via the long/short signal or using bbands_kchan_xover_counter below
		if ( (cur_bbands_lower <= cur_kchannel_lower or cur_bbands_upper >= cur_kchannel_upper) and bbands_kchan_init_signal == False ):
			bbands_kchan_init_signal        = False
			bbands_kchan_signal             = False
			bbands_kchan_crossover_signal   = False
			bbands_roc_threshold_signal	= False
			bbands_kchan_signal_counter     = 0
			bbands_kchan_xover_counter      = 0
			bbands_roc_counter		= 0

			return ( bbands_kchan_init_signal, bbands_roc_threshold_signal, bbands_kchan_crossover_signal, bbands_kchan_signal,
					bbands_kchan_signal_counter, bbands_kchan_xover_counter, bbands_roc_counter )

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

			# Aggressive strategy #2 is to detect any sudden change in the Bollinger Bands' toward
			#  the Keltner channel. This often indicates a sudden rise in volatility and likely breakout.
			if ( bbands_kchan_crossover_signal == False and cur_offset < prev_offset ):
				if ( cur_bbands_upper > prev_bbands_upper and cur_bbands_roc > prev_bbands_roc ):
					roc_pct = abs(((cur_bbands_roc - prev_bbands_roc) / prev_bbands_roc) * 100)

					# Counter for use with bbands_roc_strict
					if ( roc_pct >= 15 ):
						bbands_roc_counter += 1

					if ( cur_algo['bbands_roc_threshold'] > 0 and roc_pct >= cur_algo['bbands_roc_threshold'] ):
						bbands_roc_threshold_signal = True

				if ( bbands_roc_threshold_signal == True and
						((signal_mode == 'long' and cur_rsi_k <= 40) or
						 (signal_mode == 'short' and cur_rsi_k >= 60)) ):

					bbands_kchan_signal = True

			# Reset bbands_roc_counter and bbands_roc_threshold_signal if crossover has not yet happened and
			#  the bbands start to move back away from the Keltner channel
			if ( bbands_kchan_signal == False and cur_offset > prev_offset ):
				bbands_roc_threshold_signal	= False
				bbands_roc_counter		= 0

			# Trigger bbands_kchan_signal is the bbands/kchannel offset is narrowing to a point where crossover is emminent.
			# Unless bbands_roc_strict is True, in which case a stronger change in the bbands rate-of-change is needed to
			#  allow the bbands_kchan_signal to trigger.
			if ( cur_offset < prev_offset and cur_offset <= bbands_kchannel_offset / 4 ):
				if ( cur_algo['bbands_roc_strict'] == False or (cur_algo['bbands_roc_strict'] == True and bbands_roc_counter >= cur_algo['bbands_roc_count']) ):
					bbands_kchan_signal = True
					bbands_kchan_crossover_signal = True

			# Check for crossover
			if ( (prev_kchannel_lower <= prev_bbands_lower and cur_kchannel_lower > cur_bbands_lower) or
					(prev_kchannel_upper >= prev_bbands_upper and cur_kchannel_upper < cur_bbands_upper) ):
				bbands_kchan_crossover_signal = True

				if ( cur_algo['bbands_roc_strict'] == False or (cur_algo['bbands_roc_strict'] == True and bbands_roc_counter >= cur_algo['bbands_roc_count']) ):
					bbands_kchan_signal = True

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


			# Check the closing candles in relation to the EMA 21
			# On a long signal, count the number of times the closing price has dipped below
			#  the EMA 21 value. On a short signal, count the number of times the closing price has gone above
			#  the EMA 21 value. If this happens multiple times over the course of a squeeze it indicates
			#  that this is less likely to succeed, so we cancel the bbands_kchan_signal.
			if ( bbands_kchan_signal == True and cur_algo['bbands_kchan_ma_check'] == True and pricehistory != None ):

				ema_count = 0
				try:
					for i in range(bbands_kchan_signal_counter, 0, -1):
						if ( signal_mode == 'long' and pricehistory['candles'][-i]['close'] < bbands_kchan_ma[-i] ):
							ema_count += 1

						elif ( signal_mode == 'short' and pricehistory['candles'][-i]['close'] > bbands_kchan_ma[-i] ):
							ema_count += 1

						if ( ema_count > 2 ):
							bbands_kchan_init_signal        = False
							bbands_kchan_signal             = False
							if ( debug == True ):
								print('NOTICE: bbands_kchan_signal canceled due to too many closing candles traversing the EMA21 level.')

							break

				except Exception as e:
					print('Caught exception: bbands_kchannels(): ' + str(e))
					pass

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
				bbands_roc_threshold_signal	= False
				bbands_kchan_signal_counter	= 0
				bbands_kchan_xover_counter	= 0
				bbands_roc_counter		= 0

		return ( bbands_kchan_init_signal, bbands_roc_threshold_signal, bbands_kchan_crossover_signal, bbands_kchan_signal,
				bbands_kchan_signal_counter, bbands_kchan_xover_counter, bbands_roc_counter )


	# MESA Sine Wave
	def mesa_sine(sine=[], lead=[], direction=None, mesa_exit=False, strict=False, mesa_sine_signal=False):

		cur_sine        = sine[-1]
		prev_sine       = sine[-2]
		cur_lead        = lead[-1]
		prev_lead       = lead[-2]

		midline         = 0
		min_high_limit  = 0.9
		min_low_limit   = -0.9

		# Long signal
		if ( direction == 'long' and cur_sine < midline ):
			return False

		elif ( direction == 'long' and (prev_sine <= prev_lead and cur_sine > cur_lead) ):
			if ( mesa_exit == True ):
				mesa_sine_signal = True
			else:
				if ( cur_sine > min_high_limit ):
					mesa_sine_signal = True

		# Short signal
		elif ( direction == 'short' and cur_sine > midline ):
			return False

		elif ( direction == 'short' and (prev_sine >= prev_lead and cur_sine < cur_lead) ):
			if ( mesa_exit == True ):
				mesa_sine_signal = True

			else:
				if ( cur_sine < min_low_limit ):
					mesa_sine_signal = True

		# No need to check history if signal is already False
		if ( mesa_sine_signal == False or strict == False ):
			return mesa_sine_signal

		# Analyze trendiness
		# Check for crossovers
		xover_count     = 0
		xover           = []
		for i in range( len(sine)-1, -1, -1 ):

			# Find the last few sine points that crossed over the midline
			if ( (sine[i+1] > midline and sine[i] < midline) or
					(sine[i+1] < midline and sine[i] > midline) ):
				xover.append(i)

			if ( len(xover) >= 4 ):
				break

		if ( len(xover) >= 2 ):

			# Check the last two entries in xover[] and see if there was a crossover
			#  between sine and lead. If not then the stock is probably trending.
			for i in range( xover[-1]-1, xover[-2]+2, 1 ):
				cur_sine	= sine[i]
				prev_sine	= sine[i-1]
				cur_lead	= lead[i]
				prev_lead	= lead[i-1]

				if ( (prev_sine < prev_lead and cur_sine > cur_lead) or
						(prev_sine > prev_lead and cur_sine < cur_lead) ):
					xover_count += 1

			if ( xover_count == 0 ):
				mesa_sine_signal = False

		# Find the rate of change for the last few candles
		# Flatter sine/lead waves indicate trending
		sine_ph = { 'candles': [] }
		for i in range( 10, 0, -1 ):
			sine_ph['candles'].append( { 'close': sine[-i] } )
		sine_roc = tda_algo_helper.get_roc( sine_ph, period=9, type='close' )

		if ( abs(sine_roc[-1]) * 100 < 170 ):
			mesa_sine_signal = False

		return mesa_sine_signal


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

		# Round the moving average values to three decimal places
		s_ma = list(s_ma)
		for i in range(0, len(s_ma)):
			s_ma[i] = round( s_ma[i], 3 )

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

			# ETF ATR/NATR
			etf_atr		= []
			etf_natr	= []
			try:
				etf_atr, etf_natr = tda_algo_helper.get_atr( pricehistory=stocks[ticker]['pricehistory_5m'], period=cur_algo['atr_period'] )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_atr(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_atr']	= etf_atr[-1]
			stocks[ticker]['cur_natr']	= etf_natr[-1]

			# Calculate the EMA for the rate-of-change for the ETF tickers
			temp_ph         = { 'candles': [] }
			roc_stacked_ma  = []
			try:
				for i in range(len(etf_roc)):
					if ( np.isnan(etf_roc[i] * 10000) == True ):
						etf_roc[i] = 1
					else:
						etf_roc[i] = etf_roc[i] * 10000

					temp_ph['candles'].append({ 'open': etf_roc[i], 'high': etf_roc[i], 'low': etf_roc[i], 'close': etf_roc[i] })

				roc_stacked_ma = get_stackedma( pricehistory=temp_ph, stacked_ma_periods=cur_algo['stacked_ma_periods_primary'], stacked_ma_type='ema' )
				del(temp_ph)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stackedma(' + str(ticker) + '): ' + str(e), file=sys.stderr)

			stocks[ticker]['cur_s_ma_primary']	= roc_stacked_ma[-1]
			stocks[ticker]['prev_s_ma_primary']	= roc_stacked_ma[-2]

	# $TRIN
	if ( cur_algo['primary_trin'] == True or cur_algo['trin'] == True ):

		try:
			stocks['$TRIN']['isvalid']	= True
			stocks['$TRIN']['tradeable']	= False

			stocks['$TRINA']['isvalid']	= True
			stocks['$TRINA']['tradeable']	= False

			stocks['$TRINQ']['isvalid']	= True
			stocks['$TRINQ']['tradeable']	= False

		except:
			pass

		# First, calculate the rate-of-change for $TRIN
		trin_roc	= []
		trinq_roc	= []
		trina_roc	= []
		try:
			trin_roc	= tda_algo_helper.get_roc( stocks['$TRIN']['pricehistory'], period=cur_algo['trin_roc_period'], type=cur_algo['trin_roc_type'], calc_percentage=True )
			trinq_roc	= tda_algo_helper.get_roc( stocks['$TRINQ']['pricehistory'], period=cur_algo['trin_roc_period'], type=cur_algo['trin_roc_type'], calc_percentage=True )
			trina_roc	= tda_algo_helper.get_roc( stocks['$TRINA']['pricehistory'], period=cur_algo['trin_roc_period'], type=cur_algo['trin_roc_type'], calc_percentage=True )

		except Exception as e:
			print('Error: stochrsi_gobot(): get_roc($TRIN/$TRINQ/$TRINA): ' + str(e))
			trin_roc_ma = [0 ,0]

		if ( (isinstance(trin_roc, bool) and trin_roc == False) or (isinstance(trinq_roc, bool) and trinq_roc == False) or (isinstance(trina_roc, bool) and trina_roc == False)):
			print('Error: stochrsi_gobot(): get_roc($TRIN/$TRINQ/$TRINA) returned False')
			trin_roc_ma = [0, 0]

		# It's important to cap the min/max for $TRIN and $TICK because occasionally TDA returns
		#  some very high values, which can mess with the moving average calculation (particularly EMA)
		trin_roc	= tda_algo_helper.normalize_vals( arr_data=trin_roc, min_val=-1000, max_val=1000, min_default=-1000, max_default=1000 )
		trinq_roc	= tda_algo_helper.normalize_vals( arr_data=trinq_roc, min_val=-1000, max_val=1000, min_default=-1000, max_default=1000 )
		trina_roc	= tda_algo_helper.normalize_vals( arr_data=trina_roc, min_val=-1000, max_val=1000, min_default=-1000, max_default=1000 )

		# TRIN* data sorted by timestamps
		trin_roc_dt	= {}
		trinq_roc_dt	= {}
		trina_roc_dt	= {}
		for i in range( len(stocks['$TRIN']['pricehistory']['candles']) ):
			dt = stocks['$TRIN']['pricehistory']['candles'][i]['datetime']
			trin_roc_dt.update( { dt: trin_roc[i] } )

		for i in range( len(stocks['$TRINQ']['pricehistory']['candles']) ):
			dt = stocks['$TRINQ']['pricehistory']['candles'][i]['datetime']
			trinq_roc_dt.update( { dt: trinq_roc[i] } )

		for i in range( len(stocks['$TRINA']['pricehistory']['candles']) ):
			dt = stocks['$TRINA']['pricehistory']['candles'][i]['datetime']
			trina_roc_dt.update( { dt: trina_roc[i] } )

		# Next, calculate a moving average of trin_roc_ma to smooth trin_roc
		temp_ph = { 'candles': [] }
		all_dts = list( trin_roc_dt.keys() ) + list( trinq_roc_dt.keys() ) + list( trina_roc_dt.keys() )
		all_dts = sorted( list(dict.fromkeys(all_dts)) )
		for dt in all_dts:
			trin	= trin_roc_dt[dt] if ( dt in trin_roc_dt ) else 0
			trinq	= trinq_roc_dt[dt] if ( dt in trinq_roc_dt ) else 0
			trina	= trina_roc_dt[dt] if ( dt in trina_roc_dt ) else 0

			temp_ph['candles'].append( { 'close': (trin + trinq + trina) / 3 } )

		trin_roc_ma = []
		try:
			trin_roc_ma = tda_algo_helper.get_alt_ma( pricehistory=temp_ph, ma_type=cur_algo['trin_ma_type'], type='close', period=cur_algo['trin_ma_period'] )

		except Exception as e:
			print('Error: stochrsi_gobot(): get_alt_ma(trin_roc): ' + str(e))
			trin_roc_ma = [0 ,0]

		if ( isinstance(trin_roc_ma, bool) and trin_roc_ma == False ):
			print('Error: stochrsi_gobot(): get_alt_ma($TRIN) returned False')
			trin_roc_ma = [0, 0]

		for ticker in stocks.keys():
			stocks[ticker]['cur_trin']	= trin_roc_ma[-1]
			stocks[ticker]['prev_trin']	= trin_roc_ma[-2]

	# $TICK
	if ( cur_algo['tick'] == True ):
		stocks['$TICK']['isvalid']	= True
		stocks['$TICK']['tradeable']	= False

		# Normalize $TICK and $TICKA values
		# It's important to cap the min/max for $TRIN and $TICK because occasionally TDA returns
		#  some very high values, which can mess with the moving average calculation (particularly EMA)

		# $TICK
		tick_vals = []
		for i in range( len(stocks['$TICK']['pricehistory']['candles']) ):
			tick_vals.append(  ( stocks['$TICK']['pricehistory']['candles'][i]['high'] +
					     stocks['$TICK']['pricehistory']['candles'][i]['low'] +
					     stocks['$TICK']['pricehistory']['candles'][i]['close'] ) / 3 )

		tick_vals = tda_algo_helper.normalize_vals( arr_data=tick_vals, min_val=-5000, max_val=5000, min_default=-5000, max_default=5000 )

		tick_dict = {}
		for i in range( len(tick_vals) ):
			dt = stocks['$TICK']['pricehistory']['candles'][i]['datetime']
			tick_dict[dt] = tick_vals[i]

		# $TICKA
		ticka_vals = []
		for i in range( len(stocks['$TICKA']['pricehistory']['candles']) ):
			ticka_vals.append(  ( stocks['$TICKA']['pricehistory']['candles'][i]['high'] +
					      stocks['$TICKA']['pricehistory']['candles'][i]['low'] +
					      stocks['$TICKA']['pricehistory']['candles'][i]['close'] ) / 3 )

		ticka_vals = tda_algo_helper.normalize_vals( arr_data=ticka_vals, min_val=-5000, max_val=5000, min_default=-5000, max_default=5000 )

		ticka_dict = {}
		for i in range( len(ticka_vals) ):
			dt = stocks['$TICKA']['pricehistory']['candles'][i]['datetime']
			ticka_dict[dt] = ticka_vals[i]

		# Collect and sort all the datetime values to ensure the final data are aligned
		all_dts = []
		for i in range( len(stocks['$TICK']['pricehistory']['candles']) ):
			all_dts.append( stocks['$TICK']['pricehistory']['candles'][i]['datetime'] )
		for i in range( len(stocks['$TICKA']['pricehistory']['candles']) ):
			all_dts.append( stocks['$TICKA']['pricehistory']['candles'][i]['datetime'] )

		all_dts = sorted( list(dict.fromkeys(all_dts)) )

		temp_ph = { 'candles': [] }
		for i in range( len(all_dts) ):
			tick	= tick_dict[dt] if ( dt in tick_dict ) else 0
			ticka	= ticka_dict[dt] if ( dt in ticka_dict ) else 0

			temp_ph['candles'].append( { 'close': (tick + ticka) / 2 } )

		tick_ma = []
		try:
			tick_ma = tda_algo_helper.get_alt_ma( pricehistory=temp_ph, ma_type=cur_algo['tick_ma_type'], type='close', period=cur_algo['tick_ma_period'] )

		except Exception as e:
			print('Error: stochrsi_gobot(): get_alt_ma(tick_ma): ' + str(e))
			tick_ma = [0, 0]

		if ( isinstance(tick_ma, bool) and tick_ma == False ):
			print('Error: stochrsi_gobot(): get_alt_ma($TICK) returned False')
			tick_ma = [0, 0]

		for ticker in stocks.keys():
			stocks[ticker]['cur_tick']      = tick_ma[-1]
			stocks[ticker]['prev_tick']     = tick_ma[-2]

	# SP_Monitor
	# This algorithm measures the price action of the more highly represented stocks in an ETF to help gauge strength and trend.
	# It uses the *weighted* average of the *weighted* rate-of-change for each ticker in sp_monitor_tickers, and then calculates
	#  the EMA for the final rate-of-change values.
	#
	# Formula is as follows:
	#  - Calculate the 1-period rate-of-change for each candle of each stock ticker in sp_monitor_tickers,
	#    but weight each RoC value based on the % representation in the target ETF:
	#
	#	roc_stock1 = ((stock1_cur_cndl - stock1_prev_cndl) / stock1_prev_cndl) * stock1_pct
	#
	# - Add all the RoCs together for each stock ticker, and then divide that by the sum of
	#   the previous candle for each ticker, divided by the % representation in the target ETF:
	#
	#	total_roc = (roc_stock1 + roc_stock2 .... ) \
	#			( (stock1_prev_cndl * stock1_pct) + (stock1_prev_cndl * stock2_pct) + ... )
	#
	# - Next, take the EMA ofr the total_roc
	#
	#	ema(total_roc, N)
	#
	if ( cur_algo['primary_sp_monitor'] == True or cur_algo['sp_monitor'] == True ):

		# First collect all the datetime values for all candles in sp_monitor tickers
		sp_mon_dt = OrderedDict()
		for idx in range( len(cur_algo['sp_monitor_tickers']) ):
			try:
				sp_t	= cur_algo['sp_monitor_tickers'][idx]['sp_t']
				sp_pct	= cur_algo['sp_monitor_tickers'][idx]['sp_pct']

			except Exception as e:
				print('Warning, invalid sp_monitor ticker format: ' + str(cur_algo['sp_monitor_tickers'][idx]) + ', ' + str(e))
				continue

			stocks[sp_t]['isvalid'] = True

			# Integrate last_price into a new candle to ensure we can make use of the latest Level 1 data
			#  when calculate the ROC and MA
			if ( caller_id != None and caller_id == 'level1' and stocks[sp_t]['last_price'] != 0 ):
				if ( stocks[sp_t]['pricehistory']['candles'][-1]['datetime'] != 9999999999999 ):

					stocks[sp_t]['pricehistory']['candles'].append( {
						'open':		stocks[sp_t]['pricehistory']['candles'][-1]['open'],
						'high':		stocks[sp_t]['pricehistory']['candles'][-1]['high'],
						'low':		stocks[sp_t]['pricehistory']['candles'][-1]['low'],
						'close':	stocks[sp_t]['pricehistory']['candles'][-1]['close'],
						'datetime':	9999999999999 } )

				if ( stocks[sp_t]['last_price'] >= stocks[sp_t]['pricehistory']['candles'][-1]['high'] ):
					stocks[sp_t]['pricehistory']['candles'][-1]['high']	= stocks[sp_t]['last_price']
					stocks[sp_t]['pricehistory']['candles'][-1]['close']	= stocks[sp_t]['last_price']

				elif ( stocks[sp_t]['last_price'] <= stocks[sp_t]['pricehistory']['candles'][-1]['low'] ):
					stocks[sp_t]['pricehistory']['candles'][-1]['low']	= stocks[sp_t]['last_price']
					stocks[sp_t]['pricehistory']['candles'][-1]['close']	= stocks[sp_t]['last_price']

				else:
					stocks[sp_t]['pricehistory']['candles'][-1]['close']	= stocks[sp_t]['last_price']

			# Initialize sp_mon_dt{}
			for i in range( len(stocks[sp_t]['pricehistory']['candles']) ):
				dt = stocks[sp_t]['pricehistory']['candles'][i]['datetime']
				sp_mon_dt[dt] = { 'total_roc_prelim': 0, 'prev_cndl_sum': 0, 'total_roc': 0 }

		# Calculate ROC and ROC_MA
		for idx in range( len(cur_algo['sp_monitor_tickers']) ):
			try:
				sp_t	= cur_algo['sp_monitor_tickers'][idx]['sp_t']
				sp_pct	= cur_algo['sp_monitor_tickers'][idx]['sp_pct']

			except Exception as e:
				print('Warning, invalid sp_monitor ticker format: ' + str(cur_algo['sp_monitor_tickers'][idx]) + ', ' + str(e))
				continue

			# Get the ROC for each ticker pricehistory, then multiply the latest value by sp_pct and add
			#  it to total_roc_prelim
			sp_roc = []
			try:
				sp_roc = tda_algo_helper.get_roc( stocks[sp_t]['pricehistory'], period=cur_algo['sp_roc_period'], type=cur_algo['sp_roc_type'], calc_percentage=False )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_roc(' + str(sp_t) + '): ' + str(e))
				continue

			for i in range( len(stocks[sp_t]['pricehistory']['candles']) ):
				dt = stocks[sp_t]['pricehistory']['candles'][i]['datetime']

				# Next, calculate the denominator which is the previous_candle's HLC3 value, multiply
				#  it by sp_pct and add it to prev_cndl_sum
				if ( i == 0 ):
					prev_cndl_hlc3 = 0
				else:
					prev_cndl_hlc3 = ( stocks[sp_t]['pricehistory']['candles'][i-1]['high'] +
								stocks[sp_t]['pricehistory']['candles'][i-1]['low'] +
								stocks[sp_t]['pricehistory']['candles'][i-1]['close'] ) / 3

				sp_mon_dt[dt]['total_roc_prelim']	+= ( sp_roc[i] * sp_pct )
				sp_mon_dt[dt]['prev_cndl_sum']		+= ( prev_cndl_hlc3 * sp_pct )


		# At this point datetime keys have been added by various tickers, but since different tickers will have varying
		#  number of candles, we'll need to sort and re-create roc_total{}.
		roc_t = OrderedDict()
		for i in sorted(sp_mon_dt):
			roc_t[i] = sp_mon_dt[i]
		sp_mon_dt = roc_t

		total_roc = []
		for dt in sp_mon_dt.keys():
			if ( sp_mon_dt[dt]['total_roc_prelim'] == 0 or sp_mon_dt[dt]['prev_cndl_sum'] == 0 ):
				total_roc.append(0)

			else:
				# These values are incredibly small - so multiply by 10000000 to make them more readable
				total_roc.append( (sp_mon_dt[dt]['total_roc_prelim'] / sp_mon_dt[dt]['prev_cndl_sum']) * 10000000 )

		# Now calculate the MA for total_roc
		temp_ph			= { 'candles': [] }
		sp_monitor_roc_ma	= []
		for i in range( len(total_roc) ):
			temp_ph['candles'].append({ 'close': total_roc[i] })
			try:
				sp_monitor_roc_ma = tda_algo_helper.get_alt_ma(pricehistory=temp_ph, ma_type='ema', period=cur_algo['sp_ma_period'], type='close')

			except Exception as e:
				print('Error: stochrsi_gobot(): sp_monitor: get_alt_ma(total_roc): ' + str(e))
				sp_monitor_roc_ma = [0, 0]

		# Update cur_sp_monitor and prev_sp_monitor for all tickers
		for ticker in stocks.keys():
			stocks[ticker]['cur_sp_monitor']	= sp_monitor_roc_ma[-1]
			stocks[ticker]['prev_sp_monitor']	= sp_monitor_roc_ma[-2]

		del(total_roc,roc_t,sp_mon_dt,sp_monitor_roc_ma,temp_ph)


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
			if ( stocks[ticker]['algo_signals'][algo_id]['signal_mode'] == 'long' or
				stocks[ticker]['algo_signals'][algo_id]['signal_mode'] == 'short' ):
				continue

		# If called from gobot_level1() and the stock is in sell or buy_to_cover mode, then we
		#  will use this opportunity to check last_price and determine exit_criteria.
		#
		# SAZ - Make an exception when using primary_sp_monitor
		if ( caller_id != None and caller_id == 'level1' ):
			if ( (stocks[ticker]['algo_signals'][algo_id]['signal_mode'] == 'long' or
					stocks[ticker]['algo_signals'][algo_id]['signal_mode'] == 'short') and
					cur_algo['primary_sp_monitor'] == False ):
				continue

		# Skip this ticker if it conflicts with a per-algo min/max_daily_natr configuration
		if ( min_daily_natr != None and stocks[ticker]['natr_daily'] < min_daily_natr ):
			print( '(' + str(ticker) + ') |' + str(algo_id) + '| Skipped - Daily NATR: ' + str(stocks[ticker]['natr_daily']) + ', min_daily_natr: ' + str(min_daily_natr) )
			print()
			continue
		if ( max_daily_natr != None and stocks[ticker]['natr_daily'] > max_daily_natr ):
			print( '(' + str(ticker) + ') |' + str(algo_id) + '| Skipped - Daily NATR: ' + str(stocks[ticker]['natr_daily']) + ', max_daily_natr: ' + str(max_daily_natr) )
			print()
			continue

		# Get stochastic RSI
		if ( cur_algo['primary_stochrsi'] == True or cur_algo['primary_stochmfi'] == True or cur_algo['bbands_kchannel'] == True ):
			rsi_k		= []
			rsi_d		= []
			stochrsi	= []
			try:
				if ( cur_algo['primary_stochrsi'] == True or cur_algo['bbands_kchannel'] == True ):
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

		# MESA Adaptive Moving Average
		if ( cur_algo['primary_mama_fama'] == True or cur_algo['mama_fama'] == True ):
			mama = []
			fama = []
			try:
				mama, fama = tda_algo_helper.get_alt_ma(pricehistory=stocks[ticker]['pricehistory'], ma_type='mama', type='hlc3', mama_fastlimit=0.5, mama_slowlimit=0.05)

			except Exception as e:
				print('Error: stochrsi_gobot(): mama_fama(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_mama']	= mama[-1]
			stocks[ticker]['prev_mama']	= mama[-2]
			stocks[ticker]['cur_fama']	= fama[-1]
			stocks[ticker]['prev_fama']	= fama[-2]

		# MESA Sine Wave
		if ( cur_algo['primary_mesa_sine'] == True ):
			m_sine = []
			m_lead = []
			try:
				m_sine, m_lead = tda_algo_helper.get_mesa_sine(pricehistory=stocks[ticker]['pricehistory'], type=cur_algo['mesa_sine_type'], period=cur_algo['mesa_sine_period'])

			except Exception as e:
				print('Error: stochrsi_gobot(): get_mesa_sine(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_sine']	= m_sine[-1]
			stocks[ticker]['prev_sine']	= m_sine[-2]
			stocks[ticker]['cur_lead']	= m_lead[-1]
			stocks[ticker]['prev_lead']	= m_lead[-2]

		# Stacked Moving Averages (non-primary)
		if ( cur_algo['stacked_ma'] == True ):
			s_ma			= []
			s_ma_ha			= []
			s_ma_secondary		= []
			s_ma_ha_secondary	= []
			try:
				s_ma	= get_stackedma( stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods'], cur_algo['stacked_ma_type'] )
				s_ma_ha	= get_stackedma( stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods'], cur_algo['stacked_ma_type'], use_ha_candles=True )

				if ( cur_algo['stacked_ma_secondary'] == True ):
					s_ma_secondary		= get_stackedma( stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods_secondary'], cur_algo['stacked_ma_type_secondary'] )
					s_ma_ha_secondary	= get_stackedma( stocks[ticker]['pricehistory'], cur_algo['stacked_ma_periods_secondary'], cur_algo['stacked_ma_type_secondary'], use_ha_candles=True )

			except Exception as e:
				print('Error: stochrsi_gobot(): get_stackedma(' + str(ticker) + '): ' + str(e), file=sys.stderr)
				continue

			stocks[ticker]['cur_s_ma']	= s_ma[-1]
			stocks[ticker]['prev_s_ma']	= s_ma[-2]
			stocks[ticker]['cur_s_ma_ha']	= s_ma_ha[-1]
			stocks[ticker]['prev_s_ma_ha']	= s_ma_ha[-2]

			if ( cur_algo['stacked_ma_secondary'] == True ):
				stocks[ticker]['cur_s_ma_secondary']		= s_ma_secondary[-1]
				stocks[ticker]['prev_s_ma_secondary']		= s_ma_secondary[-2]
				stocks[ticker]['cur_s_ma_ha_secondary']		= s_ma_ha_secondary[-1]
				stocks[ticker]['prev_s_ma_ha_secondary']	= s_ma_ha_secondary[-2]

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
			# We do this here just so that the MACD values will be calculated below, but the long/short logic
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
		if ( cur_algo['bbands_kchannel'] == True ):

			bbands_lower    = []
			bbands_mid      = []
			bbands_upper    = []
			try:
				if ( cur_algo['use_bbands_kchannel_5m'] == True ):
					bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory=stocks[ticker]['pricehistory_5m'], period=cur_algo['bbands_period'], type='hlc3', matype=cur_algo['bbands_matype'])
				else:
					bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory=stocks[ticker]['pricehistory'], period=cur_algo['bbands_period'], type='hlc3', matype=cur_algo['bbands_matype'])

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_bbands(): ' + str(e))
				continue

			stocks[ticker]['cur_bbands']	= ( bbands_lower[-1], bbands_mid[-1], bbands_upper[-1] )
			stocks[ticker]['prev_bbands']	= ( bbands_lower[-2], bbands_mid[-2], bbands_upper[-2] )

			# Calculation bbands the rate-of-change
			bbands_ph	= { 'candles': [], 'symbol': ticker }
			bbands_roc	= []
			for i in range( len(bbands_upper) ):
				bbands_ph['candles'].append( {  'upper':        bbands_upper[i],
								'middle':       bbands_mid[i],
								'lower':        bbands_lower[i],
								'close':        bbands_upper[i],
								'open':         bbands_lower[i] } )

			bbands_roc = tda_algo_helper.get_roc( bbands_ph, period=cur_algo['bbands_kchan_squeeze_count'], type='close' )

			# Keltner channel
			kchannel_lower  = []
			kchannel_mid    = []
			kchannel_upper  = []
			try:
				if ( cur_algo['use_bbands_kchannel_5m'] == True ):
					kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory=stocks[ticker]['pricehistory_5m'], period=cur_algo['kchannel_period'], atr_period=cur_algo['kchannel_atr_period'], matype=cur_algo['kchan_matype'])
				else:
					kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory=stocks[ticker]['pricehistory'], period=cur_algo['kchannel_period'], atr_period=cur_algo['kchannel_atr_period'], matype=cur_algo['kchan_matype'])

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_kchannel(): ' + str(e))
				continue

			stocks[ticker]['cur_kchannel']	= ( kchannel_lower[-1], kchannel_mid[-1], kchannel_upper[-1] )
			stocks[ticker]['prev_kchannel']	= ( kchannel_lower[-2], kchannel_mid[-2], kchannel_upper[-2] )

			# 21 EMA to use with bbands_kchan algo
			bbands_kchan_ma = []
			if ( cur_algo['bbands_kchan_ma_check'] == True ):
				try:
					bbands_kchan_ma = tda_algo_helper.get_alt_ma( pricehistory=stocks[ticker]['pricehistory'], ma_type=cur_algo['bbands_kchan_ma_type'], type=cur_algo['bbands_kchan_ma_ptype'], period=cur_algo['bbands_kchan_ma_period'] )

				except Exception as e:
					print('Error: stochrsi_gobot(' + str(ticker) + '): get_alt_ma(ema,21): ' + str(e))
					bbands_kchan_ma = []

		# Rate-of-Change (ROC)
		if ( cur_algo['roc'] == True or cur_algo['roc_exit'] == True ):
			roc = []
			try:
				roc = tda_algo_helper.get_roc( stocks[ticker]['pricehistory'], period=cur_algo['roc_period'], type=cur_algo['roc_type'], calc_percentage=True )

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_roc(): ' + str(e))
				continue

			# Calculate the moving average to smooth the rate-of-change values
			tmp_ph = { 'candles': [] }
			for i in range( len(roc) ):
				tmp_ph['candles'].append( { 'close': roc[i] } )

			try:
				roc_ma = tda_algo_helper.get_alt_ma( pricehistory=tmp_ph, period=cur_algo['roc_ma_period'], ma_type=cur_algo['roc_ma_type'], type='close' )

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_alt_ma(roc_ma): ' + str(e))
				continue

			stocks[ticker]['cur_roc_ma']	= roc_ma[-1]
			stocks[ticker]['prev_roc_ma']	= roc_ma[-2]


		# Trend quick exit
		if ( cur_algo['trend_quick_exit'] == True ):
			qe_s_ma = []
			try:
				qe_s_ma = get_stackedma(stocks[ticker]['pricehistory'], cur_algo['qe_stacked_ma_periods'], cur_algo['qe_stacked_ma_type'])

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_stackedma(): ' + str(e))
				continue

			stocks[ticker]['cur_qe_s_ma']	= qe_s_ma[-1]
			stocks[ticker]['prev_qe_s_ma']	= qe_s_ma[-2]

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

			print( '(' + str(ticker) + ') Bid/Ask: ' + str(stocks[ticker]['bid_price']) + ' (' + str(stocks[ticker]['bid_size']) + ')' +
							' / ' + str(stocks[ticker]['ask_price']) + ' (' + str(stocks[ticker]['ask_size']) + ')' +
							' / ' + str(round(stocks[ticker]['bid_ask_pct'], 2)) + '%' )

			if ( stocks[ticker]['last_price'] != 0 ):
				print( '(' + str(ticker) + ') Last Price: ' + str(stocks[ticker]['last_price']) )


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

			# $TRIN
			if ( cur_algo['primary_trin'] == True or cur_algo['trin'] == True ):
				trin_dt = datetime.datetime.fromtimestamp(stocks['$TRIN']['pricehistory']['candles'][-1]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S')
				print( '(' + str(ticker) + ') Current TRIN: ' +
							str( round(stocks['$TRIN']['pricehistory']['candles'][-1]['open'], 2) ) + '|' +
							str( round(stocks['$TRIN']['pricehistory']['candles'][-1]['high'], 2) ) + '|' +
							str( round(stocks['$TRIN']['pricehistory']['candles'][-1]['low'], 2) ) + '|' +
							str( round(stocks['$TRIN']['pricehistory']['candles'][-1]['close'], 2) ) +
							' (' + str(trin_dt) + ') / ' +
						'Current TRIN_ROC_MA: ' + str(round(stocks[ticker]['cur_trin'], 3)) + ' / ' +
						'$TRIN Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['trin_signal']) + ' / ' +
						'Counter: ' + str(stocks[ticker]['algo_signals'][algo_id]['trin_counter']) )

			# $TICK
			if ( cur_algo['tick'] == True ):
				tick_dt = datetime.datetime.fromtimestamp(stocks['$TICK']['pricehistory']['candles'][-1]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S')
				print( '(' + str(ticker) + ') Current TICK: ' +
							str( round(stocks['$TICK']['pricehistory']['candles'][-1]['open'], 2) ) + '|' +
							str( round(stocks['$TICK']['pricehistory']['candles'][-1]['high'], 2) ) + '|' +
							str( round(stocks['$TICK']['pricehistory']['candles'][-1]['low'], 2) ) + '|' +
							str( round(stocks['$TICK']['pricehistory']['candles'][-1]['close'], 2) ) +
							' (' + str(tick_dt) + ') / ' +
						'Current TICK_MA: ' + str(round(stocks[ticker]['cur_tick'], 3)) + ' / ' +
						'$TICK Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['tick_signal']) )

			# ROC
			if ( cur_algo['roc'] == True or cur_algo['roc_exit'] == True ):
				print( '(' + str(ticker) + ') Current ROC_MA: ' + str(round(stocks[ticker]['cur_roc_ma'], 4)) + ' / ' +
						'ROC Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['roc_signal']) )

			# SP_Monitor
			if ( cur_algo['primary_sp_monitor'] == True or cur_algo['sp_monitor'] == True ):
				print('(' + str(ticker) + ') Current SP_Monitor: ' + str(round(stocks[ticker]['cur_sp_monitor'], 6)) + ' / ' +
						'SP Monitor Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal']) )

			# MESA Adaptive Moving Average
			if ( cur_algo['primary_mama_fama'] == True or cur_algo['mama_fama'] == True ):
				print('(' + str(ticker) + ') Current MAMA/FAMA: ' + str(round(stocks[ticker]['cur_mama'], 4)) +
						' / ' + str(round(stocks[ticker]['cur_fama'], 4)) )

			# MESA Sine Wave
			if ( cur_algo['primary_mesa_sine'] == True ):
				print('(' + str(ticker) + ') Current MESA Sine/Lead: ' + str(round(stocks[ticker]['cur_sine'], 4)) +
						' / ' + str(round(stocks[ticker]['cur_lead'], 4)) )

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
			if ( cur_algo['bbands_kchannel'] == True ):
				print('(' + str(ticker) + ') Current BBands: ' +
								str(round(stocks[ticker]['cur_bbands'][0], 3)) + ',' +
								str(round(stocks[ticker]['cur_bbands'][1], 3)) + ',' +
								str(round(stocks[ticker]['cur_bbands'][2], 3)) +
							' / Current Kchannel: ' +
								str(round(stocks[ticker]['cur_kchannel'][0], 3)) + ',' +
								str(round(stocks[ticker]['cur_kchannel'][1], 3)) + ',' +
								str(round(stocks[ticker]['cur_kchannel'][2], 3)) +
							' / ROC Counter: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_roc_counter']) +
							' / Squeeze Count: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter']) +
							' / BBands_Kchannel_Init Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal']) +
							' / BBands_Kchannel Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal']) +
							' / BBands_Threshold Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_roc_threshold_signal']) +
							' / BBands_Kchannel Crossover Signal: ' + str(stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal']) )

			# Rate of Change
			if ( cur_algo['check_etf_indicators'] == True ):
				print( '(' + str(ticker) + ') Current Rate-of-Change: ' + str(round(stocks[ticker]['cur_roc'], 5)), end='' )
				for etf_ticker in cur_algo['etf_tickers'].split(','):
					print( ', ' + str(etf_ticker) + ': ' + str(round(stocks[etf_ticker]['cur_roc'], 5)), end='' )

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
		if ( tda_gobot_helper.ismarketopen_US(safe_open=cur_algo['safe_open']) == False ):
			if ( args.multiday == True or args.singleday == True ):
				continue
		else:
			args.singleday = False

		# Set some short variables to improve readability :)
		signal_mode		= stocks[ticker]['algo_signals'][algo_id]['signal_mode']
		order_id		= None

		last_open		= stocks[ticker]['pricehistory']['candles'][-1]['open']
		last_high		= stocks[ticker]['pricehistory']['candles'][-1]['high']
		last_low		= stocks[ticker]['pricehistory']['candles'][-1]['low']
		last_close		= stocks[ticker]['pricehistory']['candles'][-1]['close']

		last_ha_open		= stocks[ticker]['pricehistory']['hacandles'][-1]['open']
		last_ha_high		= stocks[ticker]['pricehistory']['hacandles'][-1]['high']
		last_ha_low		= stocks[ticker]['pricehistory']['hacandles'][-1]['low']
		last_ha_close		= stocks[ticker]['pricehistory']['hacandles'][-1]['close']

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
		cur_s_ma_secondary	= stocks[ticker]['cur_s_ma_secondary']
		prev_s_ma_secondary	= stocks[ticker]['prev_s_ma_secondary']

		cur_s_ma_ha_primary	= stocks[ticker]['cur_s_ma_ha_primary']
		prev_s_ma_ha_primary	= stocks[ticker]['prev_s_ma_ha_primary']
		cur_s_ma_ha		= stocks[ticker]['cur_s_ma_ha']
		prev_s_ma_ha		= stocks[ticker]['prev_s_ma_ha']
		cur_s_ma_ha_secondary	= stocks[ticker]['cur_s_ma_ha_secondary']
		prev_s_ma_ha_secondary	= stocks[ticker]['prev_s_ma_ha_secondary']

		# MESA Adaptive Moving Average
		cur_mama		= stocks[ticker]['cur_mama']
		cur_fama		= stocks[ticker]['cur_fama']
		prev_mama		= stocks[ticker]['prev_mama']
		prev_fama		= stocks[ticker]['prev_fama']

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

		cur_trin		= stocks[ticker]['cur_trin']
		prev_trin		= stocks[ticker]['prev_trin']

		cur_tick		= stocks[ticker]['cur_tick']
		prev_tick		= stocks[ticker]['prev_tick']

		cur_roc_ma		= stocks[ticker]['cur_roc_ma']
		prev_roc_ma		= stocks[ticker]['prev_roc_ma']

		cur_sp_monitor		= stocks[ticker]['cur_sp_monitor']
		prev_sp_monitor		= stocks[ticker]['prev_sp_monitor']

		cur_qe_s_ma		= stocks[ticker]['cur_qe_s_ma']
		prev_qe_s_ma		= stocks[ticker]['prev_qe_s_ma']

		# Algo modifiers
		stoch_high_limit	= cur_algo['rsi_high_limit']
		stoch_low_limit		= cur_algo['rsi_low_limit']
		mfi_high_limit		= cur_algo['mfi_high_limit']
		mfi_low_limit		= cur_algo['mfi_low_limit']
		adx_threshold		= cur_algo['adx_threshold']

		# Set price_resistance_pct/price_support_pct dynamically based on price of the stock
		if ( cur_algo['resist_pct_dynamic'] == True ):
			cur_algo['price_resistance_pct'] = ( 1 / last_close ) * 100
			if ( cur_algo['price_resistance_pct'] < 0.25 ):
				cur_algo['price_resistance_pct'] = 0.25

			elif ( cur_algo['price_resistance_pct'] > 1 ):
				cur_algo['price_resistance_pct'] = 1

			cur_algo['price_support_pct'] = cur_algo['price_resistance_pct']

		# Global criteria for long or sell mode
		if ( signal_mode == 'long' or signal_mode == 'short'):

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
			if ( (tda_gobot_helper.isendofday(75) == True or tda_gobot_helper.ismarketopen_US(safe_open=cur_algo['safe_open']) == False) and args.multiday == False ):
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
				stocks[ticker]['algo_signals'][algo_id]['signal_mode'] = 'long'
				signal_mode = 'long'

		# Global criteria for short or buy_to_cover mode
		elif ( signal_mode == 'sell' or signal_mode == 'buy_to_cover'):

			# primary_algo is the algorithm that entered the trade.
			# Some algos may have their own exit criteria, so we will only
			#  process the sell/buy_to_cover loop for that algo.
			if ( stocks[ticker]['primary_algo'] != cur_algo['algo_id'] ):
				continue

		# Check security_status from Level1 data
		# "Normal" / "Halted" / "Closed"
		try:
			str( stocks[ticker]['security_status'] )
		except:
			pass
		else:
			if ( stocks[ticker]['security_status'].lower() != 'normal' ):
				print( '(' + str(ticker) + '): WARNING, security status is not set to "Normal" (' + str(stocks[ticker]['security_status']) + '), skipping for now.')
				continue


		# BUY MODE - looking for a signal to purchase the stock
		if ( signal_mode == 'long' ):

			# Bollinger Bands and Keltner Channel
			# We put this above the primary indicator since we want to keep track of what the
			#  Bollinger bands and Keltner channel are doing across long/short transitions.
			if ( cur_algo['bbands_kchannel'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_roc_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_roc_counter'] ) = bbands_kchannels( pricehistory=stocks[ticker]['pricehistory'],
															cur_bbands=cur_bbands, prev_bbands=prev_bbands,
															cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
															bbands_kchan_signal_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
															bbands_kchan_xover_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'],
															bbands_roc_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_roc_counter'],
															bbands_kchan_init_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
															bbands_roc_threshold_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_roc_threshold_signal'],
															bbands_kchan_crossover_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
															bbands_kchan_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
															bbands_roc=bbands_roc, bbands_kchan_ma=bbands_kchan_ma, debug=True )

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

			# PRIMARY MESA Adaptive Moving Average
			elif ( cur_algo['primary_mama_fama'] == True ):

				stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = False

				# Bullish trending
				if ( cur_mama > cur_fama ):
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = True

				# Jump to short mode if the MAMA/FAMA are showing a bearish movement
				elif ( cur_mama <= cur_fama or (prev_mama > prev_fama and cur_mama <= cur_fama) ):
					if ( args.short == True and stocks[ticker]['shortable'] == True ):
						print('(' + str(ticker) + ') MAMA/FAMA values indicate bearish trend ' + str(cur_mama) + '/' + str(cur_fama) + ", switching to short mode.\n" )
						reset_signals(ticker, id=algo_id, signal_mode='short', exclude_bbands_kchan=True)
						continue

				# This shouldn't happen, but just in case...
				else:
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = False


			# PRIMARY MESA Sine Wave
			elif ( cur_algo['primary_mesa_sine'] == True ):
				midline  = 0
				if ( stocks[ticker]['cur_sine'] < midline ):
					if ( args.short == True and stocks[ticker]['shortable'] == True ):
						print('(' + str(ticker) + ') MESA SINE below midline ' + str(stocks[ticker]['cur_sine']) + '/' + str(stocks[ticker]['cur_lead']) + ", switching to short mode.\n" )
						reset_signals(ticker, id=algo_id, signal_mode='short', exclude_bbands_kchan=True)
					continue

				stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = mesa_sine( sine=m_sine, lead=m_lead, direction='long', strict=cur_algo['mesa_sine_strict'],
													mesa_sine_signal=stocks[ticker]['algo_signals'][algo_id]['buy_signal'] )


			# $TRIN primary indicator
			#  - Higher values (>= 3) indicate bearish trend
			#  - Lower values (<= -1) indicate bullish trend
			#  - A simple algorithm here watches for higher values above 3, which
			#    indicate that a bearish trend is ongoing but may be approaching oversold
			#    levels. We then watch for a green candle to form, which will trigger the
			#    final signal.
			#  - Alone this is pretty simplistic, but supplimental indicators (roc, tick, etc.)
			#    can help confirm that a reversal is happening.
			elif ( cur_algo['primary_trin'] ):

				# Jump to short mode if cur_trin is less than 0
				if ( cur_trin <= cur_algo['trin_overbought'] and args.short == True and stocks[ticker]['shortable'] == True ):
					reset_signals(ticker, id=algo_id, signal_mode='short', exclude_bbands_kchan=True)
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] = True
					continue

				# Trigger trin_init_signal if cur_trin moves above trin_oversold
				elif ( cur_trin >= cur_algo['trin_oversold'] ):
					stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first green candle
				if ( stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] == True ):
					if ( last_ha_close > last_ha_open ):
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= True
					else:
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= False
						stocks[ticker]['algo_signals'][algo_id]['buy_signal']	= False

					# Cancel the trin_init_signal if we've lingered here for too long
					stocks[ticker]['algo_signals'][algo_id]['trin_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['trin_counter'] >= 10 ):
						stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
						stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= False

				# Trigger the buy_signal if all the trin signals have tiggered
				if ( stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] == True and stocks[ticker]['algo_signals'][algo_id]['trin_signal'] == True ):
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = True

			# SP Monitor Primary Algo
			elif ( cur_algo['primary_sp_monitor'] == True ):
				if ( cur_sp_monitor < 0 and args.short == True and stocks[ticker]['shortable'] == True ):
					reset_signals(ticker, id=algo_id, signal_mode='short', exclude_bbands_kchan=True)

					if ( cur_sp_monitor <= -1.5 ):
						stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] = True

					if ( cur_sp_monitor <= -cur_algo['sp_monitor_threshold'] ):
						stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

					continue

				elif ( cur_sp_monitor > 1.5 and cur_sp_monitor < cur_algo['sp_monitor_threshold'] ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] = True

				elif ( cur_sp_monitor >= cur_algo['sp_monitor_threshold'] and
						stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] == True ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] = False
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = True

				else:
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] = False
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = False

			## END PRIMARY ALGOS


			# TRIN
			if ( cur_algo['trin'] == True ):
				if ( cur_trin <= cur_algo['trin_overbought'] ):
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] = False

				# Trigger trin_init_signal if cur_trin moves above trin_oversold
				elif ( cur_trin >= cur_algo['trin_oversold'] ):
					stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first green candle
				if ( stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] == True ):
					if ( last_ha_close > last_ha_open ):
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= True
					else:
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= False

					# Cancel the trin_init_signal if we've lingered here for too long
					stocks[ticker]['algo_signals'][algo_id]['trin_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['trin_counter'] >= 10 ):
						stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
						stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= False

			# TICK
			# Bearish action when indicator is below zero and heading downward
			# Bullish action when indicator is above zero and heading upward
			if ( cur_algo['tick'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['tick_signal'] = False
				if ( cur_tick > prev_tick and cur_tick > cur_algo['tick_threshold'] ):
					stocks[ticker]['algo_signals'][algo_id]['tick_signal'] = True

			# Rate-of-Change (ROC) indicator
			if ( cur_algo['roc'] == True ):
				#roc_signal = False
				if ( cur_roc_ma > 0 and cur_roc_ma > prev_roc_ma ):
					stocks[ticker]['algo_signals'][algo_id]['roc_signal'] = True
				if ( cur_roc_ma <= cur_algo['roc_threshold'] ):
					stocks[ticker]['algo_signals'][algo_id]['roc_signal'] = False

			# ETF SP indicator
			if ( cur_algo['sp_monitor'] == True ):
				if ( cur_sp_monitor < 0 ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal'] = False
				elif ( cur_sp_monitor > 0 and cur_sp_monitor > prev_sp_monitor ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal'] = True

			# MESA Adaptive Moving Average
			if ( cur_algo['mama_fama'] == True ):

				stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal'] = False

				# Bullish trending
				if ( cur_mama > cur_fama ):
					stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal'] = True

				# Price crossed over from bullish to bearish
				elif ( cur_mama <= cur_fama ):
					stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal'] = False

			# Secondary Stacked Moving Average(s)
			if ( cur_algo['stacked_ma'] == True ):
				if ( check_stacked_ma(cur_s_ma, 'bull') == True ):
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = True
				else:
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = False

				# Secondary (really 'tertiary') stacked MA doesn't have its own signal, but can turn off
				#  the stacked_ma_signal. The idea is to allow a secondary set of periods or MA types to
				#  confirm the signal
				if ( cur_algo['stacked_ma_secondary'] == True ):
					if ( check_stacked_ma(cur_s_ma_secondary, 'bull') == False ):
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

				stocks[ticker]['algo_signals'][algo_id]['rs_signal']	= False
				stocks[ticker]['decr_threshold']			= args.decr_threshold
				stocks[ticker]['orig_decr_threshold']			= args.decr_threshold
				stocks[ticker]['exit_percent']				= args.exit_percent
				stocks[ticker]['quick_exit']				= cur_algo['quick_exit']

				cur_rs = 0
				for etf_ticker in cur_algo['etf_tickers'].split(','):
					if ( stocks[ticker]['algo_signals'][algo_id]['rs_signal'] == True ):
						break

					# Do not allow trade if the rate-of-change of the ETF indicator has no directional affinity.
					# This is to avoid choppy or sideways movement of the ETF indicator.
					if ( check_stacked_ma(stocks[etf_ticker]['cur_s_ma_primary'], 'bull') == False and
							check_stacked_ma(stocks[etf_ticker]['cur_s_ma_primary'], 'bear') == False ):
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False
						continue

					# Stock is rising compared to ETF
					if ( cur_roc > 0 and stocks[etf_ticker]['cur_roc'] < 0 ):
						cur_rs = abs( cur_roc / stocks[etf_ticker]['cur_roc'] )
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

						if ( cur_rs < 20 ):
							stocks[ticker]['quick_exit'] = True

					# Both stocks are sinking
					elif ( cur_roc < 0 and stocks[etf_ticker]['cur_roc'] < 0 ):
						cur_rs = -( cur_roc / stocks[etf_ticker]['cur_roc'] )
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					# Stock is sinking relative to ETF
					elif ( cur_roc < 0 and stocks[etf_ticker]['cur_roc'] > 0 ):
						cur_rs = cur_roc / stocks[etf_ticker]['cur_roc']
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					# Both stocks are rising
					elif ( cur_roc > 0 and stocks[etf_ticker]['cur_roc'] > 0 ):
						cur_rs = cur_roc / stocks[etf_ticker]['cur_roc']
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

						if ( cur_algo['check_etf_indicators_strict'] == False and cur_rs > 10 ):
							stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['orig_decr_threshold']	= stocks[ticker]['decr_threshold']
								stocks[ticker]['decr_threshold']	= 1

							if ( stocks[ticker]['exit_percent'] != None ):
								stocks[ticker]['exit_percent'] = stocks[ticker]['exit_percent'] / 2
								if ( cur_natr < 1 ):
									stocks[ticker]['quick_exit'] = True

					# Weird
					else:
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					if ( cur_algo['etf_min_rs'] != None and abs(cur_rs) < cur_algo['etf_min_rs'] ):
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					if ( cur_algo['etf_min_natr'] != None and stocks[etf_ticker]['cur_natr'] < cur_algo['etf_min_natr'] ):
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
					if ( abs((stocks[ticker]['previous_day_close'] / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):

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

						if ( abs((last_close / natr_resistance - 1) * 100) <= cur_algo['price_resistance_pct'] ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 10 and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# VWAP
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
						abs((cur_vwap / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):

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
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and args.lod_hod_check == True ):
					cur_time	= datetime.datetime.fromtimestamp(float(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone)
					cur_day		= cur_time.strftime('%Y-%m-%d')
					cur_hour	= int( cur_time.strftime('%-H') )

					cur_day_start	= datetime.datetime.strptime(cur_day + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start	= mytimezone.localize(cur_day_start)

					delta		= cur_time - cur_day_start
					delta		= int( delta.total_seconds() / 60 )

					# Check for current-day HOD after 1PM Eastern
					if ( cur_hour >= 13 ):
						hod = 0
						for i in range (delta, 0, -1):
							if ( float(stocks[ticker]['pricehistory']['candles'][-i]['close']) > hod ):
								hod = float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )

						# If the stock has already hit a high of the day, the next rise will likely be
						#  below HOD. If we are below HOD and less than price_resistance_pct from it
						#  then we should not enter the trade.
						if ( last_close < hod ):
							if ( abs((last_close / hod - 1) * 100) <= cur_algo['price_resistance_pct'] ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

					# If stock opened below PDH, then those can become additional resistance lines for long entry
					if ( cur_hour >= 12 and stocks[ticker]['today_open'] < stocks[ticker]['previous_day_high'] ):

						# Check PDH/PDL resistance
						avg = 0
						for i in range(15, 0, -1):
							avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
						avg = avg / 15

						if ( avg < stocks[ticker]['previous_day_high'] and abs((last_close / stocks[ticker]['previous_day_high'] - 1) * 100) <= cur_algo['price_resistance_pct'] ):
							print( '(' + str(ticker) + ') BUY SIGNAL stalled due to PDL resistance - Current Price: ' + str(round(last_close, 3)) + ' / 15-min Avg: ' + str(round(avg, 3)) )
							print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

					# If stock has been sinking for a couple days, then oftentimes the 2-day previous day high will be long resistance,
					#  but also check touch and xover. If price has touched two-day PDH multiple times and not crossed over more than
					#  1% then it's stronger resistance.
					if ( stocks[ticker]['previous_day_high'] < stocks[ticker]['previous_twoday_high'] and
						stocks[ticker]['previous_day_close'] < stocks[ticker]['previous_twoday_high'] and
						stocks[ticker]['today_open'] < stocks[ticker]['previous_twoday_high'] ):

						if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
							abs((last_high / stocks[ticker]['previous_twoday_high'] - 1) * 100) <= cur_algo['price_resistance_pct'] ):

							# Count the number of times over the last two days where the price has touched
							#  PDH/PDL and failed to break through
							#
							# Walk through the 1-min candles for the previous two-days, but be sure to take
							#  into account after-hours trading two-days prior as PDH2/PDL2 is only calculate
							#  using the daily candles (which use standard open hours only)
							cur_time		= datetime.datetime.fromtimestamp(stocks[ticker]['pricehistory']['candles'][-1]['datetime']/1000, tz=mytimezone)
							twoday_dt		= cur_time - datetime.timedelta(days=2)
							twoday_dt		= tda_gobot_helper.fix_timestamp(twoday_dt, check_day_only=True)
							twoday			= twoday_dt.strftime('%Y-%m-%d')

							yesterday_timestamp	= datetime.datetime.strptime(twoday + ' 16:00:00', '%Y-%m-%d %H:%M:%S')
							yesterday_timestamp	= mytimezone.localize(yesterday_timestamp).timestamp() * 1000

							pdh2_touch		= 0
							pdh2_xover		= 0
							for m_key in stocks[ticker]['pricehistory']['candles']:
								if ( m_key['datetime'] < yesterday_timestamp ):
									continue

								if ( m_key['high'] >= stocks[ticker]['previous_twoday_high'] ):
									pdh2_touch += 1

									# Price crossed over PDH2, check if it exceeded that level by > 1%
									if ( m_key['high'] > stocks[ticker]['previous_twoday_high'] ):
										if ( abs(stocks[ticker]['previous_twoday_high'] / m_key['high'] - 1) * 100 > 1 ):
											pdh2_xover += 1

							if ( pdh2_touch > 0 and pdh2_xover < 1 ):
								if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
									print( '(' + str(ticker) + ') BUY SIGNAL stalled due to PDH2 resistance' )
									print()

								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# END HOD/LOD/PDH/PDL Check
			# END Support / Resistance

			# Key Levels
			# Check if price is near historic key level
			if ( cur_algo['use_keylevel'] == True and
					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):

				# Use daily keylevels as well if keylevel_use_daily was configured
				if ( cur_algo['keylevel_use_daily'] == True ):
					kl_all_support_levels = ( stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance'] +
									stocks[ticker]['kl_long_support_daily'] + stocks[ticker]['kl_long_resistance_daily'] )
				else:
					kl_all_support_levels = stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']

				near_keylevel = False
				for lvl,dt,count in kl_all_support_levels:
					if ( abs((lvl / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):
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
						if ( avg < lvl or abs((avg / lvl - 1) * 100) <= cur_algo['price_resistance_pct'] / 3 ):
							if ( debug == True ):
								print( '(' + str(ticker) + ') BUY SIGNAL stalled due to Key Level resistance - KL: ' + str(round(lvl, 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )
								print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
							break

				# If keylevel_strict is True then only buy the stock if price is near a key level
				# Otherwise reject this buy to avoid getting chopped around between levels
				if ( cur_algo['keylevel_strict'] == True and near_keylevel == False ):
					if ( debug == True ):
						print( '(' + str(ticker) + ') BUY SIGNAL stalled due to keylevel_strict - Current price: ' + str(round(last_close, 2)) )
						print()

					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
			# End Key Levels

			# Volume Profile (VAH/VAL)
			if ( cur_algo['va_check'] == True and
					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
					stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):

				levels = [ stocks[ticker]['vah'], stocks[ticker]['val'] ] # stocks[ticker]['vah_2'], stocks[ticker]['val_2']
				for lvl in levels:
					if ( abs((lvl / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):

						# Current price is very close to a VA level
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
							if ( debug == True ):
								print( '(' + str(ticker) + ') BUY SIGNAL stalled due to VAH/VAL resistance: ' + str(round(lvl, 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )
								print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
							break

			# End Volume Profile (VAH/VAL)


			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):

				stacked_ma_signal		= stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal']
				trin_signal			= stocks[ticker]['algo_signals'][algo_id]['trin_signal']
				tick_signal			= stocks[ticker]['algo_signals'][algo_id]['tick_signal']
				roc_signal			= stocks[ticker]['algo_signals'][algo_id]['roc_signal']
				sp_monitor_signal		= stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal']
				mama_fama_signal		= stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal']
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

				if ( cur_algo['trin'] == True and trin_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['tick'] == True and tick_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['roc'] == True and roc_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['sp_monitor'] == True and sp_monitor_signal != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( cur_algo['mama_fama'] == True and mama_fama_signal != True ):
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

				if ( cur_algo['bbands_kchannel'] == True and bbands_kchan_signal != True ):
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

				# Ensure we are logged in
				tda_gobot_helper.tdalogin(passcode)

				# PURCHASE OPTIONS
				if ( cur_algo['options'] == True ):

					# Lookup the option to purchase
					option_data = search_options(ticker=ticker, option_type='CALL', near_expiration=cur_algo['near_expiration'], debug=True)
					if ( isinstance(option_data, bool) and option_data == False ):
						print('Error: Unable to look up options for stock "' + str(ticker) + '"', file=sys.stderr)
						stocks[ticker]['options_usd'] = cur_algo['options_usd']
						reset_signals(ticker)
						continue

					# If the option is < $1, then the price action may be too jittery. If near_expiration is set to True
					#  then try to disable to find an option with a later expiration date.
					if ( cur_algo['near_expiration'] == True and float(option_data['ask']) < 1 ):
						print('Notice: ' + str(option_data['ticker']) + ' price (' + str(option_data['ask']) + ') is below $1, setting near_expiration to False')
						option_data = search_options(ticker=ticker, option_type='CALL', near_expiration=False, debug=True)
						if ( isinstance(option_data, bool) and option_data == False ):
							print('Error: Unable to look up options for stock "' + str(ticker) + '"', file=sys.stderr)
							stocks[ticker]['options_usd'] = cur_algo['options_usd']
							reset_signals(ticker)
							continue

					stocks[ticker]['options_ticker']	= option_data['ticker']
					stocks[ticker]['options_qty']		= int( stocks[ticker]['options_usd'] / (option_data['ask'] * 100) )

					# Buy the options
					print( 'Purchasing ' + str(stocks[ticker]['options_qty']) + ' contracts of ' + str(stocks[ticker]['options_ticker']) + ' (' + str(cur_algo['algo_id'])  + ')' )
					order_data = {}
					if ( args.fake == False ):
						order_id = tda_gobot_helper.buy_sell_option(contract=stocks[ticker]['options_ticker'], quantity=stocks[ticker]['options_qty'], instruction='buy_to_open', fillwait=True, account_number=tda_account_number, debug=debug)
						if ( isinstance(order_id, bool) and order_id == False ):
							print('Error: Unable to purchase CALL option "' + str(stocks[ticker]['options_ticker']) + '"', file=sys.stderr)
							stocks[ticker]['options_usd']	= cur_algo['options_usd']
							stocks[ticker]['isvalid']	= False
							reset_signals(ticker)
							continue

						# Check the order to find the final mean fill price, if available
						order_data = tda_gobot_helper.get_order(order_id=order_id, account_number=tda_account_number, passcode=passcode)
						if ( isinstance(order_data, bool) and order_data == False ):
							order_data					= {}
							stocks[ticker]['options_orig_base_price']	= float( option_data['ask'] )

						stocks[ticker]['order_id'] = order_id

					# Set options_last_price and options_orig_base_price to the mean fill price, if available, otherwise
					#  default to the original 'ask' price
					try:
						options_last_price				= float( order_data['orderActivityCollection'][0]['executionLegs'][0]['price'] )
						stocks[ticker]['options_orig_base_price']	= float( order_data['orderActivityCollection'][0]['executionLegs'][0]['price'] )
					except:
						options_last_price				= float( option_data['ask'] )
						stocks[ticker]['options_orig_base_price']	= float( option_data['ask'] )

					stocks[ticker]['options_base_price']	= stocks[ticker]['options_orig_base_price']
					stocks[ticker]['orig_base_price']	= float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
					options_net_change			= 0

					# When working in scalp mode, immediately place a LIMIT order that will hopefully be filled later
					if ( cur_algo['scalp_mode'] == True and args.fake == False ):
						scalp_price	= stocks[ticker]['options_orig_base_price'] * ( cur_algo['scalp_mode_pct'] / 100 + 1 )
						scalp_price	= round( scalp_price, 2 )
						order_id	= tda_gobot_helper.buy_sell_option(contract=stocks[ticker]['options_ticker'], quantity=stocks[ticker]['options_qty'], limit_price=scalp_price, instruction='sell_to_close', fillwait=False, account_number=tda_account_number, debug=debug)
						if ( isinstance(order_id, bool) and order_id == False ):
							print('Error: Unable to create limit order for "' + str(stocks[ticker]['options_ticker']) + '"', file=sys.stderr)

							# This could be bad - so in this case let's immediately jump to sell mode and set the sell_signal=True
							reset_signals(ticker, signal_mode='sell', exclude_bbands_kchan=True)
							stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True
							continue

						print( 'Successfully placed limit order for ' + str(stocks[ticker]['options_ticker']) + ' at ' + str(scalp_price) )
						stocks[ticker]['order_id'] = order_id

				# PURCHASE EQUITY
				else:

					# Calculate stock quantity from investment amount
					last_price			= float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
					stocks[ticker]['stock_qty']	= int( stocks[ticker]['stock_usd'] / float(last_price) )

					# Purchase the stock
					if ( tda_gobot_helper.ismarketopen_US(safe_open=cur_algo['safe_open']) == True ):
						print( 'Purchasing ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker) + ' (' + str(cur_algo['algo_id'])  + ')' )
						stocks[ticker]['num_purchases'] -= 1

						if ( args.fake == False ):
							data = tda_gobot_helper.buy_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)
							if ( data == False ):
								print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
								stocks[ticker]['stock_usd']	= cur_algo['stock_usd']
								stocks[ticker]['stock_qty']	= 0
								stocks[ticker]['isvalid']	= False
								reset_signals(ticker)
								continue

						try:
							stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
						except:
							stocks[ticker]['orig_base_price'] = float(last_price)

					else:
						print('Stock ' + str(ticker) + ' not purchased because market is closed.')

						reset_signals(ticker)
						stocks[ticker]['stock_usd'] = cur_algo['stock_usd']
						stocks[ticker]['stock_qty'] = 0
						continue

				stocks[ticker]['primary_algo']	= cur_algo['algo_id']
				stocks[ticker]['base_price']	= stocks[ticker]['orig_base_price']
				net_change			= 0
				exit_passthrough		= False

				if ( cur_algo['options'] == True ):
					tda_gobot_helper.log_monitor(stocks[ticker]['options_ticker'], 0, options_last_price, options_net_change, stocks[ticker]['options_base_price'], stocks[ticker]['options_orig_base_price'], stocks[ticker]['options_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, sold=False)
				else:
					tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, sold=False)

				# Reset and switch all algos to 'sell' mode for the next loop
				reset_signals(ticker, signal_mode='sell', exclude_bbands_kchan=True)
				stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 0

				# VARIABLE EXIT
				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( args.variable_exit == True and cur_algo['options'] == False ):
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

				# END VARIABLE EXIT

				# Quick exit when entering counter-trend moves
				if ( cur_algo['trend_quick_exit'] == True ):
					stacked_ma_bear_affinity = check_stacked_ma(cur_qe_s_ma, 'bear')
					if ( stacked_ma_bear_affinity == True ):
						stocks[ticker]['quick_exit'] = True

				# Disable ROC exit if we're already entering in a countertrend move
				stocks[ticker]['roc_exit'] = cur_algo['roc_exit']
				if ( cur_algo['roc_exit'] == True ):
					if ( cur_roc_ma < prev_roc_ma ):
						stocks[ticker]['roc_exit'] = False


		# SELL MODE - look for a signal to sell the stock
		elif ( signal_mode == 'sell' ):
			last_price			= 0
			net_change			= 0
			total_percent_change		= 0
			options_last_price		= 0
			options_net_change		= 0
			options_total_percent_change	= 0

			# If called from gobot_level1() then just use the last_price received from level1
			# Otherwise, try to get the last_price from the API, and fall back to the last close
			#  price only if necessary
			if ( caller_id != None and caller_id == 'level1' ):
				try:
					last_price = float( stocks[ticker]['last_price'] )
				except:
					last_price = 0

			if ( last_price == 0 ):
				last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
				if ( isinstance(last_price, bool) and last_price == False ):

					# This happens often enough that it's worth just trying again before falling back
					#  to the latest candle
					tda_gobot_helper.tdalogin(passcode)
					last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
					if ( isinstance(last_price, bool) and last_price == False ):
						print('Warning: get_lastprice(' + str(ticker) + ') returned False, falling back to latest candle')
						last_price = stocks[ticker]['pricehistory']['candles'][-1]['close']

			net_change		= round( (last_price - stocks[ticker]['orig_base_price']) * stocks[ticker]['stock_qty'], 3 )
			total_percent_change	= abs( stocks[ticker]['orig_base_price'] / last_price - 1 ) * 100

			# Along with the equity's last_price above, lookup the option price as well since we will use the
			#  options_last_price with the stoploss algorithm, but we'll use the equity candles with algos
			#  like --combined_exit
			if ( cur_algo['options'] == True ):
				options_last_price = tda_gobot_helper.get_lastprice(stocks[ticker]['options_ticker'], WarnDelayed=False)
				if ( isinstance(options_last_price, bool) and options_last_price == False ):

					# Try again
					tda_gobot_helper.tdalogin(passcode)
					options_last_price = tda_gobot_helper.get_lastprice(stocks[ticker]['options_ticker'], WarnDelayed=False)
					if ( isinstance(options_last_price, bool) and options_last_price == False ):
						print('Warning: get_lastprice(' + str(stocks[ticker]['options_ticker']) + ') returned False')
						options_last_price = stocks[ticker]['options_base_price']

				options_net_change		= round( (options_last_price - stocks[ticker]['options_orig_base_price']) * stocks[ticker]['options_qty'] * 100, 3 )
				options_total_percent_change	= abs( stocks[ticker]['options_orig_base_price'] / options_last_price - 1 ) * 100

			# Integrate last_price from get_lastprice() into the latest candle from pricehistory.
			#
			# This helps ensure we have the latest data to use with our exit strategies.
			# The downside is this may make reproducing trades via backtesting more difficult,
			#  but that is already difficult sometimes as the streaming API can provide
			#  slightly different candles than the historical data.
			if ( last_price >= stocks[ticker]['pricehistory']['candles'][-1]['high'] ):
				stocks[ticker]['pricehistory']['candles'][-1]['high']	= last_price
				stocks[ticker]['pricehistory']['candles'][-1]['close']	= last_price

			elif ( last_price <= stocks[ticker]['pricehistory']['candles'][-1]['low'] ):
				stocks[ticker]['pricehistory']['candles'][-1]['low']	= last_price
				stocks[ticker]['pricehistory']['candles'][-1]['close']	= last_price

			else:
				stocks[ticker]['pricehistory']['candles'][-1]['close'] = last_price

			# Recalculate the latest Heikin Ashi candle
			ha_open		= ( stocks[ticker]['pricehistory']['hacandles'][-2]['open'] + stocks[ticker]['pricehistory']['hacandles'][-2]['close'] ) / 2
			ha_close	= ( stocks[ticker]['pricehistory']['candles'][-1]['open'] +
						stocks[ticker]['pricehistory']['candles'][-1]['high'] +
						stocks[ticker]['pricehistory']['candles'][-1]['low'] +
						stocks[ticker]['pricehistory']['candles'][-1]['close'] ) / 4

			ha_high		= max( stocks[ticker]['pricehistory']['candles'][-1]['high'], ha_open, ha_close )
			ha_low		= min( stocks[ticker]['pricehistory']['candles'][-1]['low'], ha_open, ha_close )

			stocks[ticker]['pricehistory']['hacandles'][-1]['open']		= ha_open
			stocks[ticker]['pricehistory']['hacandles'][-1]['close']	= ha_close
			stocks[ticker]['pricehistory']['hacandles'][-1]['high']		= ha_high
			stocks[ticker]['pricehistory']['hacandles'][-1]['low']		= ha_low

			# Finally, reset last_* vars
			last_open	= stocks[ticker]['pricehistory']['candles'][-1]['open']
			last_high	= stocks[ticker]['pricehistory']['candles'][-1]['high']
			last_low	= stocks[ticker]['pricehistory']['candles'][-1]['low']
			last_close	= stocks[ticker]['pricehistory']['candles'][-1]['close']

			# End of trading day - dump the stock and exit unless --multiday was set
			#  or if args.hold_overnight=False and args.multiday=True
			if ( tda_gobot_helper.isendofday(4) == True ):
				if ( (args.multiday == True and args.hold_overnight == False) or args.multiday == False ):
					print('Market closing, selling stock ' + str(ticker))
					stocks[ticker]['exit_percent_signal'] = True
					stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60) == True and args.hold_overnight == False ):
				if ( cur_algo['options'] == True ):
					if ( options_last_price > stocks[ticker]['options_orig_base_price'] ):
						percent_change = abs( stocks[ticker]['options_orig_base_price'] / options_last_price - 1 ) * 100
				else:
					if ( last_price > stocks[ticker]['orig_base_price'] ):
						percent_change = abs( stocks[ticker]['orig_base_price'] / last_price - 1 ) * 100

				# Close position if percent_change has surpassed the last_hour_threshold
				if ( percent_change >= args.last_hour_threshold ):
					stocks[ticker]['exit_percent_signal'] = True
					stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

			# If stock is sinking over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( cur_algo['use_bbands_kchannel_xover_exit'] == True and stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == False ):

				cur_bbands_lower	= round( cur_bbands[0], 3 )
				cur_bbands_upper	= round( cur_bbands[2], 3 )
				cur_kchannel_lower	= round( cur_kchannel[0], 3 )
				cur_kchannel_upper	= round( cur_kchannel[2], 3 )

				if ( cur_algo['primary_stacked_ma'] == True ):

					# Standard candles
					stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
					stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

					# Heikin Ashi candles
					stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
					stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				elif ( cur_algo['primary_mama_fama'] == True ):
					if ( cur_mama > cur_fama ):
						stacked_ma_bear_affinity	= False
						stacked_ma_bear_ha_affinity	= False
						stacked_ma_bull_affinity	= True
						stacked_ma_bull_ha_affinity	= True

					else:
						stacked_ma_bear_affinity	= True
						stacked_ma_bear_ha_affinity	= True
						stacked_ma_bull_affinity	= False
						stacked_ma_bull_ha_affinity	= False

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
						if ( stacked_ma_bear_affinity == True or stacked_ma_bear_ha_affinity == True ):

							# Stock momentum switched directions after entry and before crossover
							stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] -= 1
							if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] <= -cur_algo['bbands_kchannel_xover_exit_count'] and last_close < stocks[ticker]['orig_base_price'] ):
								if ( stocks[ticker]['decr_threshold'] > 0.5 ):
									stocks[ticker]['decr_threshold'] = 0.5

						# Reset bbands_kchan_xover_counter if momentum switched back
						elif ( stacked_ma_bull_affinity == True ):
							stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 0

				# Handle adverse conditions after the crossover
				elif ( (cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper) or
						stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] == True ):

					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] = True
					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] <= 0 ):
						stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 1

					if ( last_price < stocks[ticker]['orig_base_price'] ):
						if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] >= 10 ):
							# We've lingered for 10+ bars and price is below entry, let's try to cut our losses
							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['decr_threshold'] = 1

						if ( cur_algo['primary_mama_fama'] == True ):
							# It's likely that the bbands/kchan squeeze has failed at this point
							if ( stacked_ma_bear_affinity == True ):
								stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

					if ( cur_algo['primary_stacked_ma'] == True or cur_algo['primary_mama_fama'] == True ):
						if ( stacked_ma_bear_affinity == True or stacked_ma_bear_ha_affinity == True ):
							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['decr_threshold'] = 1

			# STOPLOSS MONITOR
			# Use a falling rate-of-change (actually its moving average) as a warning signal and reduce the decr_threshold
			if ( cur_algo['roc_exit'] == True and stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == False ):
				if ( stocks[ticker]['roc_exit'] == False ):
					if ( cur_roc_ma > prev_roc_ma ):
						stocks[ticker]['roc_exit'] = True

				elif ( cur_roc_ma < prev_roc_ma ):
					stocks[ticker]['decr_threshold']		= args.decr_threshold - args.decr_threshold / 3
					stocks[ticker]['options_decr_threshold']	= args.options_decr_threshold / 2

			# When using options, we follow the options price when in stoploss mode.
			# If exit_percent is configured and stocks[ticker]['exit_percent_signal'] is set, then we use the original stock
			#  candles with strategies like --combined_exit.
			#
			# OPTIONS
			if ( cur_algo['options'] == True ):
				stoploss_ticker		= stocks[ticker]['options_ticker']
				stoploss_qty		= stocks[ticker]['options_qty']
				stoploss_last_price	= options_last_price
				stoploss_orig_base	= stocks[ticker]['options_orig_base_price']
				stoploss_base		= stocks[ticker]['options_base_price']
				stoploss_net_change	= options_net_change

			# EQUITY
			else:
				stoploss_ticker		= ticker
				stoploss_qty		= stocks[ticker]['stock_qty']
				stoploss_last_price	= last_price
				stoploss_orig_base	= stocks[ticker]['orig_base_price']
				stoploss_base		= stocks[ticker]['base_price']
				stoploss_net_change	= net_change

			# If price decreases
			if ( stoploss_last_price < stoploss_base and stocks[ticker]['exit_percent_signal'] == False ):
				percent_change = abs( stoploss_last_price / stoploss_base - 1 ) * 100
				if ( debug == True ):
					print(str(stoploss_ticker) + '" -' + str(round(percent_change, 2)) + '% (' + str(stoploss_last_price) + ')')

				tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

				# SELL the security if we are using a trailing stoploss
				if ( cur_algo['options'] == True ):
					if ( percent_change >= stocks[ticker]['options_decr_threshold'] and args.stoploss == True ):
						print(str(stoploss_ticker) + '" dropped below the decr_threshold (' + str(stocks[ticker]['options_decr_threshold']) + '%), selling the security...')
						stocks[ticker]['algo_signals'][algo_id]['sell_signal']	= True

				else:
					if ( percent_change >= stocks[ticker]['decr_threshold'] and args.stoploss == True ):
						print(str(stoploss_ticker) + '" dropped below the decr_threshold (' + str(stocks[ticker]['decr_threshold']) + '%), selling the security...')
						stocks[ticker]['algo_signals'][algo_id]['sell_signal']	= True

			# If price increases
			elif ( stoploss_last_price > stoploss_base and stocks[ticker]['exit_percent_signal'] == False ):
				percent_change = abs( stoploss_base / stoploss_last_price - 1 ) * 100
				if ( debug == True ):
					print(str(stoploss_ticker) + '" +' + str(round(percent_change,2)) + '% (' + str(stoploss_last_price) + ')')

				# Re-set the base_price to the last_price if we increase by incr_threshold or more
				# This way we can continue to ride a price increase until it starts dropping
				if ( percent_change >= stocks[ticker]['incr_threshold'] ):
					stocks[ticker]['base_price']		= last_price
					stocks[ticker]['options_base_price']	= options_last_price

					print('Net change (' + str(stoploss_ticker) + '): ' + str(net_change) + ' USD')

					if ( cur_algo['options'] == True ):
						print(str(stoploss_ticker) + '" increased above the incr_threshold (' + str(stocks[ticker]['options_incr_threshold']) + '%), resetting base price to '  + str(stoploss_last_price))
						#stocks[ticker]['options_decr_threshold'] = stocks[ticker]['options_incr_threshold']

					else:
						print(str(stoploss_ticker) + '" increased above the incr_threshold (' + str(stocks[ticker]['incr_threshold']) + '%), resetting base price to '  + str(stoploss_last_price))

						# Adapt decr_threshold based on changes made by --variable_exit
						if ( stocks[ticker]['incr_threshold'] < args.incr_threshold ):

							# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
							#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
							if ( stocks[ticker]['incr_threshold'] == stocks[ticker]['orig_incr_threshold'] ):
								stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold']
								stocks[ticker]['incr_threshold'] = stocks[ticker]['incr_threshold'] / 2
						else:
							stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold'] / 2

				tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

			# No price change
			else:
				tda_gobot_helper.log_monitor(stoploss_ticker, 0, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

			# END STOPLOSS MONITOR


			# ADDITIONAL EXIT STRATEGIES
			# Sell if --exit_percent was set and threshold met
			if ( stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == False and stoploss_last_price > stoploss_orig_base and
					((cur_algo['options'] == False and stocks[ticker]['exit_percent'] != None) or
					 (cur_algo['options'] == True and stocks[ticker]['options_exit_percent'] != None)) ):

				# Determine if exit_percent has been achieved
				if ( stocks[ticker]['exit_percent_signal'] == False ):

					if ( cur_algo['options'] == True ):
						if ( options_total_percent_change >= stocks[ticker]['options_exit_percent'] ):
							stocks[ticker]['exit_percent_signal'] = True

					else:
						high_percent_change = abs( stocks[ticker]['orig_base_price'] / last_high - 1 ) * 100
						if ( total_percent_change >= stocks[ticker]['exit_percent'] ):
							stocks[ticker]['exit_percent_signal'] = True

						# Set the stoploss lower if the candle touches the exit_percent, but closes below it
						elif ( high_percent_change >= stocks[ticker]['exit_percent'] and total_percent_change < stocks[ticker]['exit_percent'] and
								stocks[ticker]['exit_percent_signal'] == False ):
							if ( stocks[ticker]['decr_threshold'] > total_percent_change ):
								stocks[ticker]['decr_threshold'] = total_percent_change

					# Actions to take when we first hit exit_percent_signal
					if ( stocks[ticker]['exit_percent_signal'] == True ):

						# Set stoploss to exit_percent
						stocks[ticker]['decr_threshold']		= stocks[ticker]['exit_percent']
						stocks[ticker]['options_decr_threshold']	= stocks[ticker]['options_exit_percent']

						# Trigger the exit signal if quick_exit was configured and quick_exit_percent
						#  has been achieved
						if ( cur_algo['quick_exit'] == True or stocks[ticker]['quick_exit'] == True ):
							if ( cur_algo['options'] == True and options_total_percent_change >= cur_algo['quick_exit_percent'] ):
								print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(options_total_percent_change, 3)) + '%' )
								stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

							elif ( cur_algo['options'] == False and total_percent_change >= cur_algo['quick_exit_percent'] ):
								print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(total_percent_change, 3)) + '%' )
								stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

				# If exit_percent has been hit, watch the price action and determine when the trend has ended
				elif ( stocks[ticker]['exit_percent_signal'] == True ):

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
						period		= 5
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( cndls[-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bull') == False ):
							stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

					elif ( cur_algo['use_combined_exit'] ):
						trend_exit	= False
						ha_exit		= False

						# Check Trend
						period		= 2
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( stocks[ticker]['pricehistory']['candles'][-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bull') == False ):
							trend_exit = True

						# Check Heikin Ashi candles
						last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
						last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']
						if ( last_close < last_open ):
							ha_exit = True

						print( '(' + str(ticker) + '): trend_exit=' + str(trend_exit) + ', ha_exit=' + str(ha_exit) )
						if ( trend_exit == True and ha_exit == True ):
							stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

					# Basic exit algo, just sell on the first RED candle
					elif ( last_close < last_open ):
						stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

			# Check for price reversal below the original entry price
			if ( stocks[ticker]['exit_percent_signal'] == True and stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == False and
					 stoploss_last_price < stoploss_orig_base ):

				# If we get to this point then the exit_percent_signal was triggered, but then the stock
				#  rapidly changed direction below cost basis. But because exit_percent_signal was triggered
				#  the stoploss routine above will not catch this. So at this point we probably need to stop out.
				stocks[ticker]['exit_percent_signal']		= False
				stocks[ticker]['decr_threshold']		= 0.5
				stocks[ticker]['options_decr_threshold']	= stocks[ticker]['options_decr_threshold'] / 2

			# Handle quick_exit_percent if quick_exit is configured
			if ( (cur_algo['quick_exit'] == True or stocks[ticker]['quick_exit'] == True) and
					stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == False and stoploss_last_price > stoploss_orig_base ):

				print( str(options_total_percent_change) + ' / ' + str(cur_algo['quick_exit_percent']))

				if ( cur_algo['options'] == True and options_total_percent_change >= cur_algo['quick_exit_percent'] ):
					print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(options_total_percent_change, 3)) + '%')
					stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

				elif ( cur_algo['options'] == False and total_percent_change >= cur_algo['quick_exit_percent'] ):
					print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(total_percent_change, 3)) + '%')
					stocks[ticker]['algo_signals'][algo_id]['sell_signal'] = True

			# StochRSI MONITOR
			# Do not use stochrsi as an exit signal if exit_percent_signal is triggered. That means we've surpassed the
			#  exit_percent threshold and should wait for either a red candle or for decr_threshold to be hit.
			# Note: This exit strategy is considered legacy for now since it tends to exit too early most of the time.
			if ( (cur_algo['primary_stochrsi'] == True or cur_algo['stochrsi_5m'] == True) and
					args.variable_exit == False and stocks[ticker]['exit_percent_signal'] == False ):

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

			# When in scalp mode, check to see if previous LIMIT order has been set
			exit_passthrough = False
			if ( cur_algo['scalp_mode'] == True and stocks[ticker]['order_id'] != None and args.fake == False and
					(caller_id != None and caller_id == 'chart_equity') and
					stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == False ):

				# Look up order_id status to see if stock had already hit the stop limit
				order_data = tda_gobot_helper.get_order(order_id=stocks[ticker]['order_id'], account_number=tda_account_number, passcode=passcode)
				if ( isinstance(order_data, bool) and order_data == False ):
					print('Error: Unable to look up order data for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']), file=sys.stderr)

				# Check if the existing LIMIT order has been filled, and if not then cancel it
				try:
					quantity_remaining = float( order_data['remainingQuantity'] )
				except:
					quantity_remaining = stocks[ticker]['options_qty']

				# If LIMIT order has been filled, try to set options_last_price to the last price from get_order()
				#  and move to exit out of sell mode
				if ( quantity_remaining == 0 ):
					try:
						float( order_data['orderActivityCollection'][0]['executionLegs'][0]['price'] )
					except:
						pass
					else:
						options_last_price = order_data['orderActivityCollection'][0]['executionLegs'][0]['price']

				stocks[ticker]['algo_signals'][algo_id]['sell_signal']	= True
				exit_passthrough					= True


			# SELL THE STOCK
			if ( stocks[ticker]['algo_signals'][algo_id]['sell_signal'] == True ):
				if ( args.fake == False or (args.fake == False and exit_passthrough == False) ):

					# Ensure we are logged in
					tda_gobot_helper.tdalogin(passcode)

					# OPTIONS
					if ( cur_algo['options'] == True ):
						if ( cur_algo['scalp_mode'] == True and stocks[ticker]['order_id'] != None ):

							# Look up order_id status to see if stock had already hit the stop limit
							order_data = tda_gobot_helper.get_order(order_id=stocks[ticker]['order_id'], account_number=tda_account_number, passcode=passcode)
							if ( isinstance(order_data, bool) and order_data == False ):
								print('Error: Unable to look up order data for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']), file=sys.stderr)

							# Check if the existing LIMIT order has been filled, and if not then cancel it
							try:
								quantity_remaining = float( order_data['remainingQuantity'] )
							except:
								quantity_remaining = stocks[ticker]['options_qty']

							if ( quantity_remaining > 0 ):
								print('Canceling limit order for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']) + ', remaining options: ' + str(quantity_remaining))
								order_data = tda_gobot_helper.cancel_order(order_id=stocks[ticker]['order_id'], account_number=tda_account_number, passcode=passcode)
								if ( isinstance(order_data, bool) and order_data == False ):
									print('Error: Unable to cancel limit order for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']), file=sys.stderr)

								stocks[ticker]['options_qty'] = quantity_remaining

						# Place market order to sell option
						order_data = tda_gobot_helper.buy_sell_option(contract=stocks[ticker]['options_ticker'], quantity=stocks[ticker]['options_qty'], instruction='sell_to_close', fillwait=True, account_number=tda_account_number, debug=debug)

					# EQUITY
					else:
						data = tda_gobot_helper.sell_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

				if ( cur_algo['options'] == True ):
					percent_change = abs( stocks[ticker]['options_orig_base_price'] / options_last_price - 1 ) * 100
					print('Net change (' + str(stocks[ticker]['options_ticker']) + '): ' + str(options_net_change) + ' USD (' + str(round(percent_change, 2)) + '%)')
					tda_gobot_helper.log_monitor(stocks[ticker]['options_ticker'], percent_change, options_last_price, options_net_change, stocks[ticker]['options_base_price'], stocks[ticker]['options_orig_base_price'], stocks[ticker]['options_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, sold=True)

				else:
					percent_change = abs( stocks[ticker]['options_orig_base_price'] / options_last_price - 1 ) * 100
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD (' + str(round(percent_change, 2)) + '%)')
					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, sold=True)

				# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
				if ( net_change < 0 ):
					stocks[ticker]['failed_txs'] -= 1
					stocks[ticker]['failed_usd'] += net_change
					if ( stocks[ticker]['failed_usd'] <= 0 or stocks[ticker]['failed_txs'] <= 0 ):
						stocks[ticker]['isvalid'] = False
						if ( args.fake == False ):
							tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)

				# Change signal to 'long' or 'short' and generate new tx_id for next iteration
				stocks[ticker]['tx_id']				= random.randint(1000, 9999)
				stocks[ticker]['stock_usd']			= cur_algo['stock_usd']
				stocks[ticker]['quick_exit']			= cur_algo['quick_exit']
				stocks[ticker]['order_id']			= None
				stocks[ticker]['stock_qty']			= 0
				stocks[ticker]['base_price']			= 0
				stocks[ticker]['orig_base_price']		= 0

				stocks[ticker]['options_ticker']		= None
				stocks[ticker]['options_usd']			= cur_algo['options_usd']
				stocks[ticker]['options_qty']			= 0
				stocks[ticker]['options_orig_base_price']	= 0
				stocks[ticker]['options_base_price']		= 0

				stocks[ticker]['incr_threshold']		= args.incr_threshold
				stocks[ticker]['orig_incr_threshold']		= args.incr_threshold
				stocks[ticker]['decr_threshold']		= args.decr_threshold
				stocks[ticker]['orig_decr_threshold']		= args.decr_threshold
				stocks[ticker]['exit_percent']			= args.exit_percent

				stocks[ticker]['options_incr_threshold']	= args.options_incr_threshold
				stocks[ticker]['options_decr_threshold']	= args.options_decr_threshold
				stocks[ticker]['options_exit_percent']		= args.options_exit_percent

				exit_passthrough				= False

				reset_signals(ticker)
				if ( args.short == True and stocks[ticker]['shortable'] == True ):
					reset_signals(ticker, signal_mode='short')
				else:
					reset_signals(ticker, signal_mode='long')


		# SHORT SELL the stock
		# In this mode we will monitor the RSI and initiate a short sale if the RSI is very high
		elif ( signal_mode == 'short' ):

			# Bollinger Bands and Keltner Channel
			# We put this above the primary indicator since we want to keep track of what the
			#  Bollinger bands and Keltner channel are doing across long/short transitions.
			if ( cur_algo['bbands_kchannel'] == True ):
				( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_roc_threshold_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'],
				  stocks[ticker]['algo_signals'][algo_id]['bbands_roc_counter'] ) = bbands_kchannels( pricehistory=stocks[ticker]['pricehistory'],
															cur_bbands=cur_bbands, prev_bbands=prev_bbands,
															cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
															bbands_kchan_signal_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal_counter'],
															bbands_kchan_xover_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'],
															bbands_roc_counter=stocks[ticker]['algo_signals'][algo_id]['bbands_roc_counter'],
															bbands_kchan_init_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_init_signal'],
															bbands_roc_threshold_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_roc_threshold_signal'],
															bbands_kchan_crossover_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'],
															bbands_kchan_signal=stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_signal'],
															bbands_roc=bbands_roc, bbands_kchan_ma=bbands_kchan_ma, debug=True )

			# PRIMARY STOCHRSI MONITOR
			if ( cur_algo['primary_stochrsi'] == True or cur_algo['primary_stochmfi'] == True ):

				# Jump to long mode if StochRSI K and D are already below stoch_low_limit
				# The intent here is if the bot starts up while the RSI is low we don't want to wait until the stock
				#  does a full loop again before acting on it.
				if ( cur_rsi_k < stoch_default_low_limit and cur_rsi_d < stoch_default_low_limit and args.shortonly == False ):
					print('(' + str(ticker) + ') StochRSI K and D values already below ' + str(stoch_default_low_limit) + ', switching to long mode.')
					reset_signals(ticker, id=algo_id, signal_mode='long')
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
					reset_signals(ticker, id=algo_id, signal_mode='long', exclude_bbands_kchan=True)
					continue

				elif ( cur_algo['use_ha_candles'] == True and stacked_ma_bear_ha_affinity == True or stacked_ma_bear_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

				elif ( cur_algo['use_trend'] == True and price_trend_bear_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

				elif ( cur_algo['use_ha_candles'] == False and cur_algo['use_trend'] == False and stacked_ma_bear_affinity == True ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

				else:
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = False

			# PRIMARY MESA Adaptive Moving Average
			elif ( cur_algo['primary_mama_fama'] == True ):

				stocks[ticker]['algo_signals'][algo_id]['short_signal'] = False

				# Bearish trending
				if ( cur_mama < cur_fama ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

				# Jump to short mode if the MAMA/FAMA are showing a bearish movement
				elif ( cur_mama >= cur_fama or (prev_mama < prev_fama and cur_mama >= cur_fama) ):
					if ( args.shortonly == False ):
						print('(' + str(ticker) + ') MAMA/FAMA values indicate bullish trend ' + str(cur_mama) + '/' + str(cur_fama) + ", switching to long mode.\n" )
						reset_signals(ticker, id=algo_id, signal_mode='long', exclude_bbands_kchan=True)
						continue

				# This shouldn't happen, but just in case...
				else:
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = False

			# PRIMARY MESA Sine Wave
			elif ( cur_algo['primary_mesa_sine'] == True ):
				midline = 0
				if ( stocks[ticker]['cur_sine'] > midline ):
					if ( args.shortonly == False ):
						print('(' + str(ticker) + ') MESA SINE above midline ' + str(stocks[ticker]['cur_sine']) + '/' + str(stocks[ticker]['cur_lead']) + ", switching to long mode.\n" )
						reset_signals(ticker, id=algo_id, signal_mode='long', exclude_bbands_kchan=True)
					continue

				stocks[ticker]['algo_signals'][algo_id]['short_signal'] = mesa_sine( sine=m_sine, lead=m_lead, direction='short', strict=cur_algo['mesa_sine_strict'],
													mesa_sine_signal=stocks[ticker]['algo_signals'][algo_id]['short_signal'] )

			# $TRIN primary indicator
			#  - Higher values (>= 3) indicate bearish trend
			#  - Lower values (<= -1) indicate bullish trend
			elif ( cur_algo['primary_trin'] ):

				# Jump to long mode if cur_trin is greater than trin_overbought
				if ( cur_trin >= cur_algo['trin_oversold'] and args.shortonly == False):
					reset_signals(ticker, id=algo_id, signal_mode='long', exclude_bbands_kchan=True)
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] = True
					continue

				# Trigger trin_init_signal if cur_trin moves below trin_overbought
				elif ( cur_trin <= cur_algo['trin_overbought'] ):
					stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first red candle
				if ( stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] == True ):
					if ( last_ha_close < last_ha_open ):
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= True

					else:
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= False
						stocks[ticker]['algo_signals'][algo_id]['short_signal']	= False

					# Cancel the trin_init_signal if we've lingered here for too long
					stocks[ticker]['algo_signals'][algo_id]['trin_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['trin_counter'] >= 10 ):
						stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
						stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= False

				# Trigger the short_signal if all the trin signals have tiggered
				if ( stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] == True and stocks[ticker]['algo_signals'][algo_id]['trin_signal'] == True ):
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] = True

			# SP Monitor Primary Algo
			elif ( cur_algo['primary_sp_monitor'] == True ):
				if ( cur_sp_monitor > 0 and args.shortonly == False ):
					reset_signals(ticker, id=algo_id, signal_mode='long', exclude_bbands_kchan=True)

					if ( cur_sp_monitor >= 1.5 ):
						stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] = True

					if ( cur_sp_monitor >= cur_algo['sp_monitor_threshold'] ):
						stocks[ticker]['algo_signals'][algo_id]['buy_signal'] = True

					continue

				elif ( cur_sp_monitor < -1.5 and cur_sp_monitor > -cur_algo['sp_monitor_threshold'] ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] = True

				elif ( cur_sp_monitor <= -cur_algo['sp_monitor_threshold'] and
						stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal'] == True ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['short_signal']			= True

				else:
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_init_signal']	= False
					stocks[ticker]['algo_signals'][algo_id]['short_signal']			= False

			## END PRIMARY ALGOS


			# TRIN
			if ( cur_algo['trin'] == True ):
				if ( cur_trin >= cur_algo['trin_oversold'] ):
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] = False

				# Trigger trin_init_signal if cur_trin moves below trin_overbought
				elif ( cur_trin <= cur_algo['trin_overbought'] ):
					stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
					stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first red candle
				if ( stocks[ticker]['algo_signals'][algo_id]['trin_init_signal'] == True ):
					if ( last_ha_close < last_ha_open ):
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= True
					else:
						stocks[ticker]['algo_signals'][algo_id]['trin_signal']	= False

					# Cancel the trin_init_signal if we've lingered here for too long
					stocks[ticker]['algo_signals'][algo_id]['trin_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['trin_counter'] >= 10 ):
						stocks[ticker]['algo_signals'][algo_id]['trin_counter']		= 0
						stocks[ticker]['algo_signals'][algo_id]['trin_init_signal']	= False

			# TICK
			# Bearish action when indicator is below zero and heading downward
			# Bullish action when indicator is above zero and heading upward
			if ( cur_algo['tick'] == True ):
				stocks[ticker]['algo_signals'][algo_id]['tick_signal'] = False
				if ( cur_tick < prev_tick and cur_tick < -cur_algo['tick_threshold'] ):
					stocks[ticker]['algo_signals'][algo_id]['tick_signal'] = True

			# Rate-of-Change (ROC) indicator
			if ( cur_algo['roc'] == True ):
				if ( cur_roc_ma < 0 and cur_roc_ma < prev_roc_ma ):
					stocks[ticker]['algo_signals'][algo_id]['roc_signal'] = True
				if ( cur_roc_ma >= -cur_algo['roc_threshold'] ):
					stocks[ticker]['algo_signals'][algo_id]['roc_signal'] = False

			# ETF SP indicator
			if ( cur_algo['sp_monitor'] == True ):
				if ( cur_sp_monitor > 0 ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal'] = False
				elif ( cur_sp_monitor < 0 and cur_sp_monitor < prev_sp_monitor ):
					stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal'] = True

			# MESA Adaptive Moving Average
			if ( cur_algo['mama_fama'] == True ):

				stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal'] = False

				# Bearish trending
				if ( cur_mama < cur_fama ):
					stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal'] = True

				# Price crossed over from bearish to bullish
				elif ( cur_mama >= cur_fama ):
					stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal'] = False

			# Secondary Stacked Moving Average(s)
			if ( cur_algo['stacked_ma'] == True ):
				if ( check_stacked_ma(cur_s_ma, 'bear') == True ):
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = True
				else:
					stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal'] = False

				# Secondary (really 'tertiary') stacked MA doesn't have its own signal, but can turn off
				#  the stacked_ma_signal. The idea is to allow a secondary set of periods or MA types to
				#  confirm the signal
				if ( cur_algo['stacked_ma_secondary'] == True ):
					if ( check_stacked_ma(cur_s_ma_secondary, 'bear') == False ):
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

				stocks[ticker]['algo_signals'][algo_id]['rs_signal']	= False
				stocks[ticker]['decr_threshold']			= args.decr_threshold
				stocks[ticker]['orig_decr_threshold']			= args.decr_threshold
				stocks[ticker]['exit_percent']				= args.exit_percent
				stocks[ticker]['quick_exit']				= cur_algo['quick_exit']

				cur_rs = 0
				for etf_ticker in cur_algo['etf_tickers'].split(','):
					if ( stocks[ticker]['algo_signals'][algo_id]['rs_signal'] == True ):
						break

					# Do not allow trade if the rate-of-change of the ETF indicator has no directional affinity.
					# This is to avoid choppy or sideways movement of the ETF indicator.
					if ( check_stacked_ma(stocks[etf_ticker]['cur_s_ma_primary'], 'bull') == False and
							check_stacked_ma(stocks[etf_ticker]['cur_s_ma_primary'], 'bear') == False ):
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False
						continue

					# Stock is rising compared to ETF
					if ( cur_roc > 0 and stocks[etf_ticker]['cur_roc'] < 0 ):
						cur_rs = abs( cur_roc / stocks[etf_ticker]['cur_roc'] )
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					# Both stocks are sinking
					elif ( cur_roc < 0 and stocks[etf_ticker]['cur_roc'] < 0 ):
						cur_rs = -( cur_roc / stocks[etf_ticker]['cur_roc'] )
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

						if ( cur_algo['check_etf_indicators_strict'] == False and cur_rs > 10 ):
							stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['orig_decr_threshold']	= stocks[ticker]['decr_threshold']
								stocks[ticker]['decr_threshold']	= 1

							if ( stocks[ticker]['exit_percent'] != None ):
								stocks[ticker]['exit_percent'] = stocks[ticker]['exit_percent'] / 2
								if ( cur_natr < 1 ):
									stocks[ticker]['quick_exit'] = True

					# Stock is sinking relative to ETF
					elif ( cur_roc < 0 and stocks[etf_ticker]['cur_roc'] > 0 ):
						cur_rs = cur_roc / stocks[etf_ticker]['cur_roc']
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = True

						if ( abs(cur_rs) < 20 ):
							stocks[ticker]['quick_exit'] = True

					# Both stocks are rising
					elif ( cur_roc > 0 and stocks[etf_ticker]['cur_roc'] > 0 ):
						cur_rs = cur_roc / stocks[etf_ticker]['cur_roc']
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					# Weird
					else:
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					if ( cur_algo['etf_min_rs'] != None and abs(cur_rs) < cur_algo['etf_min_rs'] ):
						stocks[ticker]['algo_signals'][algo_id]['rs_signal'] = False

					if ( cur_algo['etf_min_natr'] != None and stocks[etf_ticker]['cur_natr'] < cur_algo['etf_min_natr'] ):
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
					if ( abs((stocks[ticker]['previous_day_close'] / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):

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

						if ( abs((last_close / natr_resistance - 1) * 100) <= cur_algo['price_resistance_pct'] ):
							if ( abs(cur_rsi_k - cur_rsi_d) < 10 and stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

				# VWAP
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
						abs((cur_vwap / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):

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
				if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and args.lod_hod_check == True ):
					cur_time	= datetime.datetime.fromtimestamp(float(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone)
					cur_day		= cur_time.strftime('%Y-%m-%d')
					cur_hour	= int( cur_time.strftime('%-H') )

					cur_day_start	= datetime.datetime.strptime(cur_day + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start	= mytimezone.localize(cur_day_start)

					delta		= cur_time - cur_day_start
					delta		= int( delta.total_seconds() / 60 )

					# Check for current-day LOD after 1PM Eastern
					if ( cur_hour >= 13 ):
						lod = 9999
						for i in range (delta, 0, -1):
							if ( float(stocks[ticker]['pricehistory']['candles'][-i]['close']) < lod ):
								lod = float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )

						# If the stock has already hit a low of the day, the next decrease will likely be
						#  above LOD. If we are above LOD and less than price_resistance_pct from it
						#  then we should not enter the trade.
						if ( last_close > lod ):
							if ( abs((lod / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):
								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

					# If stock opened above PDL, then those can become additional resistance lines for short entry
					if ( cur_hour >= 12 and stocks[ticker]['today_open'] > stocks[ticker]['previous_day_low'] ):

						# Check PDH/PDL resistance
						avg = 0
						for i in range(15, 0, -1):
							avg += float( stocks[ticker]['pricehistory']['candles'][-i]['close'] )
						avg = avg / 15

						if ( avg > stocks[ticker]['previous_day_low'] and abs((last_close / stocks[ticker]['previous_day_low'] - 1) * 100) <= cur_algo['price_resistance_pct'] ):
							print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to PDL resistance - Current Price: ' + str(round(last_close, 3)) + ' / 15-min Avg: ' + str(round(avg, 3)) )
							print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

					# If stock has been rising for a couple days, then oftentimes the 2-day previous day low will be short resistance,
					#  but also check touch and xover. If price has touched two-day PDL multiple times and not crossed over more than
					#  1% then it's stronger resistance.
					if ( stocks[ticker]['previous_day_low'] > stocks[ticker]['previous_twoday_low'] and
						stocks[ticker]['previous_day_close'] > stocks[ticker]['previous_twoday_low'] and
						stocks[ticker]['today_open'] > stocks[ticker]['previous_twoday_low'] ):

						if ( stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
							abs((last_low / stocks[ticker]['previous_twoday_low'] - 1) * 100) <= cur_algo['price_resistance_pct'] ):

							# Count the number of times over the last two days where the price has touched
							#  PDH/PDL and failed to break through
							#
							# Walk through the 1-min candles for the previous two-days, but be sure to take
							#  into account after-hours trading two-days prior as PDH2/PDL2 is only calculate
							#  using the daily candles (which use standard open hours only)
							cur_time		= datetime.datetime.fromtimestamp(stocks[ticker]['pricehistory']['candles'][-1]['datetime']/1000, tz=mytimezone)
							twoday_dt		= cur_time - datetime.timedelta(days=2)
							twoday_dt		= tda_gobot_helper.fix_timestamp(twoday_dt, check_day_only=True)
							twoday			= twoday_dt.strftime('%Y-%m-%d')

							yesterday_timestamp	= datetime.datetime.strptime(twoday + ' 16:00:00', '%Y-%m-%d %H:%M:%S')
							yesterday_timestamp	= mytimezone.localize(yesterday_timestamp).timestamp() * 1000

							pdl2_touch		= 0
							pdl2_xover		= 0
							for m_key in stocks[ticker]['pricehistory']['candles']:
								if ( m_key['datetime'] < yesterday_timestamp ):
									continue

								if ( m_key['low'] <= stocks[ticker]['previous_twoday_low'] ):
									pdl2_touch += 1

									# Price crossed over PDL2, check if it exceeded that level by > 1%
									if ( m_key['low'] < stocks[ticker]['previous_twoday_low'] ):
										if ( abs(m_key['low'] / stocks[ticker]['previous_twoday_low'] - 1) * 100 > 1 ):
											pdl2_xover += 1

							if ( pdl2_touch > 0 and pdl2_xover < 1 ):
								if ( debug == True and stocks[ticker]['algo_signals'][algo_id]['buy_signal'] == True ):
									print( '(' + str(ticker) + ') BUY SIGNAL stalled due to PDH2 resistance' )
									print()

								stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False

                                # END HOD/LOD/PDH/PDL Check
			# END Support / Resistance

			# Key Levels
			# Check if price is near historic key level
			if ( cur_algo['use_keylevel'] == True and
					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):

				# Use daily keylevels as well if keylevel_use_daily was configured
				if ( cur_algo['keylevel_use_daily'] == True ):
					kl_all_support_levels = ( stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance'] +
									stocks[ticker]['kl_long_support_daily'] + stocks[ticker]['kl_long_resistance_daily'] )
				else:
					kl_all_support_levels = stocks[ticker]['kl_long_support'] + stocks[ticker]['kl_long_resistance']

				near_keylevel = False
				for lvl,dt,count in kl_all_support_levels:
					if ( abs((lvl / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):
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
						if ( avg > lvl or abs((avg / lvl - 1) * 100) <= cur_algo['price_resistance_pct'] / 3 ):
							if ( debug == True ):
								print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to Key Level resistance - KL: ' + str(round(lvl, 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )
								print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
							break

				# If keylevel_strict is True then only short the stock if price is near a key level
				# Otherwise reject this short altogether to avoid getting chopped around between levels
				if ( cur_algo['keylevel_strict'] == True and near_keylevel == False ):
					if ( debug == True ):
						print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to keylevel_strict - Current price: ' + str(round(last_close, 2)) )
						print()

					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
			# End Key Levels

			# Volume Profile (VAH/VAL)
			if ( cur_algo['va_check'] == True and
					stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] == True and
					stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):

				levels = [ stocks[ticker]['vah'], stocks[ticker]['val'] ] # stocks[ticker]['vah_2'], stocks[ticker]['val_2']
				for lvl in levels:
					if ( abs((lvl / last_close - 1) * 100) <= cur_algo['price_resistance_pct'] ):

						# Current price is very close to a VA level
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
						if ( avg > lvl ):
							if ( debug == True ):
								print( '(' + str(ticker) + ') SHORT SIGNAL stalled due to VAH/VAL resistance: ' + str(round(lvl, 2)) + ' / 15-min Avg: ' + str(round(avg, 2)) )
								print()

							stocks[ticker]['algo_signals'][algo_id]['resistance_signal'] = False
							break

			# End Volume Profile (VAH/VAL)


			# Resolve the primary stochrsi short_signal with the secondary indicators
			if ( stocks[ticker]['algo_signals'][algo_id]['short_signal'] == True ):

				stacked_ma_signal		= stocks[ticker]['algo_signals'][algo_id]['stacked_ma_signal']
				trin_signal			= stocks[ticker]['algo_signals'][algo_id]['trin_signal']
				tick_signal			= stocks[ticker]['algo_signals'][algo_id]['tick_signal']
				roc_signal			= stocks[ticker]['algo_signals'][algo_id]['roc_signal']
				sp_monitor_signal		= stocks[ticker]['algo_signals'][algo_id]['sp_monitor_signal']
				mama_fama_signal		= stocks[ticker]['algo_signals'][algo_id]['mama_fama_signal']
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

				if ( cur_algo['trin'] == True and trin_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['tick'] == True and tick_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['roc'] == True and roc_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['sp_monitor'] == True and sp_monitor_signal != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( cur_algo['mama_fama'] == True and mama_fama_signal != True ):
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

				if ( cur_algo['bbands_kchannel'] == True and bbands_kchan_signal != True ):
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

				# Ensure we are logged in
				tda_gobot_helper.tdalogin(passcode)

				# PURCHASE OPTIONS
				if ( cur_algo['options'] == True ):

					# Lookup the option to purchase
					option_data = search_options(ticker=ticker, option_type='PUT', near_expiration=cur_algo['near_expiration'], debug=True)
					if ( isinstance(option_data, bool) and option_data == False ):
						print('Error: Unable to look up options for stock "' + str(ticker) + '"', file=sys.stderr)
						stocks[ticker]['options_usd'] = cur_algo['options_usd']
						reset_signals(ticker)
						continue

					# If the option is < $1, then the price action may be too jittery. If near_expiration is set to True
					#  then try to disable to find an option with a later expiration date.
					if ( cur_algo['near_expiration'] == True and float(option_data['ask']) < 1 ):
						print('Notice: ' + str(option_data['ticker']) + ' price (' + str(option_data['ask']) + ') is below $1, setting near_expiration to False')
						option_data = search_options(ticker=ticker, option_type='PUT', near_expiration=False, debug=True)
						if ( isinstance(option_data, bool) and option_data == False ):
							print('Error: Unable to look up options for stock "' + str(ticker) + '"', file=sys.stderr)
							stocks[ticker]['options_usd'] = cur_algo['options_usd']
							reset_signals(ticker)
							continue

					stocks[ticker]['options_ticker']	= option_data['ticker']
					stocks[ticker]['options_qty']		= int( stocks[ticker]['options_usd'] / (option_data['ask'] * 100) )

					# Buy the options
					print( 'Purchasing ' + str(stocks[ticker]['options_qty']) + ' contracts of ' + str(stocks[ticker]['options_ticker']) + ' (' + str(cur_algo['algo_id'])  + ')' )
					order_data = {}
					if ( args.fake == False ):
						order_id = tda_gobot_helper.buy_sell_option(contract=stocks[ticker]['options_ticker'], quantity=stocks[ticker]['options_qty'], instruction='buy_to_open', fillwait=True, account_number=tda_account_number, debug=debug)
						if ( isinstance(order_id, bool) and order_id == False ):
							print('Error: Unable to purchase CALL option "' + str(stocks[ticker]['options_ticker']) + '"', file=sys.stderr)
							stocks[ticker]['options_usd']	= cur_algo['options_usd']
							stocks[ticker]['isvalid']	= False
							reset_signals(ticker)
							continue

						# Check the order to find the final mean fill price, if available
						order_data = tda_gobot_helper.get_order(order_id=order_id, account_number=tda_account_number, passcode=passcode)
						if ( isinstance(order_data, bool) and order_data == False ):
							order_data					= {}
							stocks[ticker]['options_orig_base_price']	= float( option_data['ask'] )

						stocks[ticker]['order_id'] = order_id

					# Set options_last_price and options_orig_base_price to the mean fill price, if available, otherwise
					#  default to the original 'ask' price
					try:
						options_last_price				= float( order_data['orderActivityCollection'][0]['executionLegs'][0]['price'] )
						stocks[ticker]['options_orig_base_price']	= float( order_data['orderActivityCollection'][0]['executionLegs'][0]['price'] )
					except:
						options_last_price				= float( option_data['ask'] )
						stocks[ticker]['options_orig_base_price']	= float( option_data['ask'] )

					stocks[ticker]['options_base_price']	= stocks[ticker]['options_orig_base_price']
					stocks[ticker]['orig_base_price']	= float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
					options_net_change			= 0

					# When working in scalp mode, immediately place a LIMIT order that will hopefully be filled later
					if ( cur_algo['scalp_mode'] == True and args.fake == False ):
						scalp_price	= stocks[ticker]['options_orig_base_price'] * ( cur_algo['scalp_mode_pct'] / 100 + 1 )
						scalp_price	= round( scalp_price, 2 )
						order_id	= tda_gobot_helper.buy_sell_option(contract=stocks[ticker]['options_ticker'], quantity=stocks[ticker]['options_qty'], limit_price=scalp_price, instruction='sell_to_close', fillwait=False, account_number=tda_account_number, debug=debug)
						if ( isinstance(order_id, bool) and order_id == False ):
							print('Error: Unable to create limit order for "' + str(stocks[ticker]['options_ticker']) + '"', file=sys.stderr)

							# This could be bad - so in this case let's immediately jump to buy_to_cover mode and set the buy_to_cover_signal=True
							reset_signals(ticker, signal_mode='buy_to_cover', exclude_bbands_kchan=True)
							stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True
							continue

						print( 'Successfully placed limit order for ' + str(stocks[ticker]['options_ticker']) + ' at $' + str(scalp_price) )
						stocks[ticker]['order_id'] = order_id

				# PURCHASE EQUITY
				else:

					# Calculate stock quantity from investment amount
					last_price			= float( stocks[ticker]['pricehistory']['candles'][-1]['close'] )
					stocks[ticker]['stock_qty']	= int( stocks[ticker]['stock_usd'] / float(last_price) )

					# Short the stock
					if ( tda_gobot_helper.ismarketopen_US(safe_open=cur_algo['safe_open']) == True ):
						print( 'Shorting ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker) + ' (' + str(cur_algo['algo_id'])  + ')' )
						stocks[ticker]['num_purchases'] -= 1

						if ( args.fake == False ):
							data = tda_gobot_helper.short_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)
							if ( data == False ):
								if ( args.shortonly == True ):
									print('Error: Unable to short "' + str(ticker) + '"', file=sys.stderr)
									stocks[ticker]['stock_usd']	= cur_algo['stock_usd']
									stocks[ticker]['stock_qty']	= 0

									reset_signals(ticker)
									stocks[ticker]['shortable']	= False
									stocks[ticker]['isvalid']	= False
									continue

								else:
									print('Error: Unable to short "' + str(ticker) + '" - disabling shorting', file=sys.stderr)

									reset_signals(ticker, signal_mode='long')
									stocks[ticker]['shortable'] = False
									stocks[ticker]['stock_usd'] = cur_algo['stock_usd']
									stocks[ticker]['stock_qty'] = 0
									continue

						try:
							stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
						except:
							stocks[ticker]['orig_base_price'] = last_price

					else:
						print('Stock ' + str(ticker) + ' not shorted because market is closed.')

						stocks[ticker]['stock_usd'] = cur_algo['stock_usd']
						stocks[ticker]['stock_qty'] = 0
						reset_signals(ticker)
						if ( args.shortonly == False ):
							reset_signals(ticker, signal_mode='long')

						continue

				stocks[ticker]['primary_algo']	= cur_algo['algo_id']
				stocks[ticker]['base_price']	= stocks[ticker]['orig_base_price']
				net_change			= 0
				exit_passthrough		= False

				if ( cur_algo['options'] == True ):
					tda_gobot_helper.log_monitor(stocks[ticker]['options_ticker'], 0, options_last_price, options_net_change, stocks[ticker]['options_base_price'], stocks[ticker]['options_orig_base_price'], stocks[ticker]['options_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=False, sold=False)
				else:
					tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=False)

				# Reset and switch all algos to 'buy_to_cover' mode for the next loop
				reset_signals(ticker, signal_mode='buy_to_cover', exclude_bbands_kchan=True)
				stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 0

				# VARIABLE EXIT
				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( args.variable_exit == True and cur_algo['options'] == False ):
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

				# END VARIABLE EXIT

				# Quick exit when entering counter-trend moves
				if ( cur_algo['trend_quick_exit'] == True ):
					stacked_ma_bull_affinity = check_stacked_ma(cur_qe_s_ma, 'bull')
					if ( stacked_ma_bull_affinity == True ):
						stocks[ticker]['quick_exit'] = True

				# Disable ROC exit if we're already entering in a countertrend move
				stocks[ticker]['roc_exit'] = cur_algo['roc_exit']
				if ( cur_algo['roc_exit'] == True ):
					if ( cur_roc_ma > prev_roc_ma ):
						stocks[ticker]['roc_exit'] = False


		# BUY_TO_COVER a previous short sale
		# This mode must always follow a previous "short" signal. We will monitor the RSI and initiate
		#   a buy-to-cover transaction to cover a previous short sale if the RSI if very low. We also
		#   need to monitor stoploss in case the stock rises above a threshold.
		elif ( signal_mode == 'buy_to_cover' ):
			last_price			= 0
			net_change			= 0
			total_percent_change		= 0
			options_last_price		= 0
			options_net_change		= 0
			options_total_percent_change	= 0

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

			net_change		= round( (last_price - stocks[ticker]['orig_base_price']) * stocks[ticker]['stock_qty'], 3 )
			total_percent_change	= abs( last_price / stocks[ticker]['orig_base_price'] - 1 ) * 100

			# Lookup the option price as well as the equity since we will use the options_last_price
			#  with the stoploss algorithm, but we'll use the equity candles with algos like --combined_exit
			if ( cur_algo['options'] == True ):
				options_last_price = tda_gobot_helper.get_lastprice(stocks[ticker]['options_ticker'], WarnDelayed=False)
				if ( isinstance(options_last_price, bool) and options_last_price == False ):

					# Try again
					tda_gobot_helper.tdalogin(passcode)
					options_last_price = tda_gobot_helper.get_lastprice(stocks[ticker]['options_ticker'], WarnDelayed=False)
					if ( isinstance(options_last_price, bool) and options_last_price == False ):
						print('Warning: get_lastprice(' + str(stocks[ticker]['options_ticker']) + ') returned False')
						options_last_price = stocks[ticker]['options_base_price']

				options_net_change		= round( (options_last_price - stocks[ticker]['options_orig_base_price']) * stocks[ticker]['options_qty'] * 100, 3 )
				options_total_percent_change	= abs( options_last_price / stocks[ticker]['options_orig_base_price'] - 1 ) * 100

			# Integrate last_price from get_lastprice() into the latest candle from pricehistory.
			#
			# This helps ensure we have the latest data to use with our exit strategies.
			# The downside is this may make reproducing trades via backtesting more difficult,
			#  but that is already difficult sometimes as the streaming API can provide
			#  slightly different candles than the historical data.
			if ( last_price >= stocks[ticker]['pricehistory']['candles'][-1]['high'] ):
				stocks[ticker]['pricehistory']['candles'][-1]['high']	= last_price
				stocks[ticker]['pricehistory']['candles'][-1]['close']	= last_price

			elif ( last_price <= stocks[ticker]['pricehistory']['candles'][-1]['low'] ):
				stocks[ticker]['pricehistory']['candles'][-1]['low']	= last_price
				stocks[ticker]['pricehistory']['candles'][-1]['close']	= last_price

			else:
				stocks[ticker]['pricehistory']['candles'][-1]['close'] = last_price

			# Recalculate the latest Heikin Ashi candle
			ha_open		= ( stocks[ticker]['pricehistory']['hacandles'][-2]['open'] + stocks[ticker]['pricehistory']['hacandles'][-2]['close'] ) / 2
			ha_close	= ( stocks[ticker]['pricehistory']['candles'][-1]['open'] +
						stocks[ticker]['pricehistory']['candles'][-1]['high'] +
						stocks[ticker]['pricehistory']['candles'][-1]['low'] +
						stocks[ticker]['pricehistory']['candles'][-1]['close'] ) / 4

			ha_high		= max( stocks[ticker]['pricehistory']['candles'][-1]['high'], ha_open, ha_close )
			ha_low		= min( stocks[ticker]['pricehistory']['candles'][-1]['low'], ha_open, ha_close )

			stocks[ticker]['pricehistory']['hacandles'][-1]['open']		= ha_open
			stocks[ticker]['pricehistory']['hacandles'][-1]['close']	= ha_close
			stocks[ticker]['pricehistory']['hacandles'][-1]['high']		= ha_high
			stocks[ticker]['pricehistory']['hacandles'][-1]['low']		= ha_low

			# Finally, reset last_* vars
			last_open	= stocks[ticker]['pricehistory']['candles'][-1]['open']
			last_high	= stocks[ticker]['pricehistory']['candles'][-1]['high']
			last_low	= stocks[ticker]['pricehistory']['candles'][-1]['low']
			last_close	= stocks[ticker]['pricehistory']['candles'][-1]['close']

			# End of trading day - dump the stock and exit unless --multiday was set
			#  or if args.hold_overnight=False and args.multiday=True
			if ( tda_gobot_helper.isendofday(4) == True ):
				if ( (args.multiday == True and args.hold_overnight == False) or args.multiday == False ):
					print('Market closing, covering shorted stock ' + str(ticker))
					stocks[ticker]['exit_percent_signal'] = True
					stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60) == True and args.hold_overnight == False ):
				if ( cur_algo['options'] == True ):
					if ( options_last_price > stocks[ticker]['options_orig_base_price'] ):
						percent_change = abs( stocks[ticker]['options_orig_base_price'] / options_last_price - 1 ) * 100
				else:
					if ( last_price < stocks[ticker]['orig_base_price'] ):
						percent_change = abs( last_price / stocks[ticker]['orig_base_price'] - 1 ) * 100

				# Close position if percent_change has surpassed the last_hour_threshold
				if ( percent_change >= args.last_hour_threshold ):
					print('Last hour increase threshold has been reached (' + str(args.last_hour_threshold) + '), closing position')
					stocks[ticker]['exit_percent_signal']				= True
					stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal']	= True

			# If stock is rising over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( cur_algo['use_bbands_kchannel_xover_exit'] == True and stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == False ):

				cur_bbands_lower	= round( cur_bbands[0], 3 )
				cur_bbands_upper	= round( cur_bbands[2], 3 )
				cur_kchannel_lower	= round( cur_kchannel[0], 3 )
				cur_kchannel_upper	= round( cur_kchannel[2], 3 )

				if ( cur_algo['primary_stacked_ma'] == True ):

					# Standard candles
					stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
					stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

					# Heikin Ashi candles
					stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
					stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				elif ( cur_algo['primary_mama_fama'] == True ):
					if ( cur_mama < cur_fama ):
						stacked_ma_bear_affinity	= True
						stacked_ma_bear_ha_affinity	= True
						stacked_ma_bull_affinity	= False
						stacked_ma_bull_ha_affinity	= False

					else:
						stacked_ma_bear_affinity	= False
						stacked_ma_bear_ha_affinity	= False
						stacked_ma_bull_affinity	= True
						stacked_ma_bull_ha_affinity	= True

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

					if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] == False and cur_algo['primary_stacked_ma'] == True ):
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
				elif ( (cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper) or
						stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] == True ):

					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_crossover_signal'] = True
					stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] += 1
					if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] <= 0 ):
						stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] = 1

					if ( last_price > stocks[ticker]['orig_base_price'] ):
						if ( stocks[ticker]['algo_signals'][algo_id]['bbands_kchan_xover_counter'] >= 10 ):
							# We've lingered for 10+ bars and price is above entry, let's try to cut our losses
							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['decr_threshold'] = 1

						if ( cur_algo['primary_mama_fama'] == True ):
							# It's likely that the bbands/kchan squeeze has failed at this point
							if ( stacked_ma_bull_affinity == True ):
								stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

					if ( cur_algo['primary_stacked_ma'] == True or cur_algo['primary_mama_fama'] == True ):
						if ( stacked_ma_bull_affinity == True or stacked_ma_bull_ha_affinity == True ):
							if ( stocks[ticker]['decr_threshold'] > 1 ):
								stocks[ticker]['decr_threshold'] = 1

			# STOPLOSS MONITOR
			# Use a rising rate-of-change (actually its moving average) as a warning signal and reduce the decr_threshold
			if ( cur_algo['roc_exit'] == True and stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == False ):
				if ( stocks[ticker]['roc_exit'] == False ):
					if ( cur_roc_ma < prev_roc_ma ):
						stocks[ticker]['roc_exit'] = True

				elif ( cur_roc_ma > prev_roc_ma ):
					stocks[ticker]['decr_threshold']		= args.decr_threshold - args.decr_threshold / 3
					stocks[ticker]['options_decr_threshold']	= args.options_decr_threshold / 2

			# When using options, we follow the options price when in stoploss mode.
			# If exit_percent is configured and stocks[ticker]['exit_percent_signal'] is set, then we use the original stock
			#  candles with strategies like --combined_exit.
			#
			# OPTIONS
			if ( cur_algo['options'] == True ):
				stoploss_ticker		= stocks[ticker]['options_ticker']
				stoploss_qty		= stocks[ticker]['options_qty']
				stoploss_last_price	= options_last_price
				stoploss_orig_base	= stocks[ticker]['options_orig_base_price']
				stoploss_base		= stocks[ticker]['options_base_price']
				stoploss_net_change	= options_net_change

			# EQUITY
			else:
				stoploss_ticker		= ticker
				stoploss_qty		= stocks[ticker]['stock_qty']
				stoploss_last_price	= last_price
				stoploss_orig_base	= stocks[ticker]['orig_base_price']
				stoploss_base		= stocks[ticker]['base_price']
				stoploss_net_change	= net_change

			# If price decreases
			if ( stoploss_last_price < stoploss_base and stocks[ticker]['exit_percent_signal'] == False ):
				percent_change = abs( stoploss_last_price / stoploss_base - 1 ) * 100
				print('Net change (' + str(stoploss_ticker) + '): ' + str(stoploss_net_change) + ' USD')
				if ( debug == True ):
					print('Stock "' +  str(stoploss_ticker) + '" -' + str(round(percent_change, 2)) + '% (' + str(stoploss_last_price) + ')')

				# Sell the PUT option if price decreased below decr_threshold
				if ( cur_algo['options'] == True ):
					if ( percent_change >= stocks[ticker]['options_decr_threshold'] and args.stoploss == True ):
						print(str(stoploss_ticker) + ' (PUT) decreased below the decr_threshold (' + str(stocks[ticker]['options_decr_threshold']) + '%), selling option...')
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

				# When shorting, price going downward is a good thing
				else:
					# Re-set the base_price to the last_price if we increase by incr_threshold or more
					# This way we can continue to ride a price increase until it starts dropping
					if ( percent_change >= stocks[ticker]['incr_threshold'] ):
						stocks[ticker]['base_price']		= last_price
						stocks[ticker]['options_base_price']	= options_last_price

						print(str(stoploss_ticker) + ' (SHORT) decreased below the incr_threshold (' + str(stocks[ticker]['incr_threshold']) + '%), resetting base price to '  + str(stoploss_last_price))

						# Adapt decr_threshold based on changes made by --variable_exit
						if ( stocks[ticker]['incr_threshold'] < args.incr_threshold ):

							# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
							#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
							if ( stocks[ticker]['incr_threshold'] == stocks[ticker]['orig_incr_threshold'] ):
								stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold']
								stocks[ticker]['incr_threshold'] = stocks[ticker]['incr_threshold'] / 2

						else:
							stocks[ticker]['decr_threshold'] = stocks[ticker]['incr_threshold'] / 2

				if ( cur_algo['options'] == True ):
					tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=False, sold=False)
				else:
					tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=False)

			# If price increases
			elif ( stoploss_last_price > stoploss_base and stocks[ticker]['exit_percent_signal'] == False ):
				percent_change = abs( stoploss_base / stoploss_last_price - 1 ) * 100
				print('Net change (' + str(stoploss_ticker) + '): ' + str(stoploss_net_change) + ' USD')
				if ( debug == True ):
					print(str(stoploss_ticker) + '" +' + str(round(percent_change, 2)) + '% (' + str(stoploss_last_price) + ')')

				# Increasing PUT option value is a good thing
				if ( cur_algo['options'] == True ):
					if ( percent_change >= stocks[ticker]['options_incr_threshold'] ):
						stocks[ticker]['options_base_price'] = options_last_price
						print(str(stoploss_ticker) + ' (PUT) increased above the incr_threshold (' + str(stocks[ticker]['options_incr_threshold']) + '%), resetting base price to '  + str(stoploss_last_price))

				else:
					# BUY-TO-COVER the shorted equity if we are using a trailing stoploss
					if ( percent_change >= stocks[ticker]['decr_threshold'] and args.stoploss == True ):
						print(str(stoploss_ticker) + ' (SHORT) increased above the decr_threshold (' + str(stocks[ticker]['decr_threshold']) + '%), covering shorted stock...')
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

				if ( cur_algo['options'] == True ):
					tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=False, sold=False)
				else:
					tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=False)

			# No price change
			else:
				print('Net change (' + str(stoploss_ticker) + '): ' + str(stoploss_net_change) + ' USD (No Change)')
				if ( cur_algo['options'] == True ):
					tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=False)
				else:
					tda_gobot_helper.log_monitor(stoploss_ticker, percent_change, stoploss_last_price, stoploss_net_change, stoploss_base, stoploss_orig_base, stoploss_qty, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True)

			# END STOPLOSS MONITOR


			# ADDITIONAL EXIT STRATEGIES
			# Sell if --exit_percent was set and threshold met
			if ( stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == False and
					((cur_algo['options'] == False and stoploss_last_price < stoploss_orig_base) or
					 (cur_algo['options'] == True and stoploss_last_price > stoploss_orig_base))
					and
					((cur_algo['options'] == False and stocks[ticker]['exit_percent'] != None) or
					 (cur_algo['options'] == True and stocks[ticker]['options_exit_percent'] != None)) ):

				# Determine if exit_percent has been achieved
				if ( stocks[ticker]['exit_percent_signal'] == False ):

					if ( cur_algo['options'] == True ):
						if ( options_total_percent_change >= stocks[ticker]['options_exit_percent'] ):
							stocks[ticker]['exit_percent_signal'] = True

					else:
						low_percent_change = abs( last_low / stocks[ticker]['orig_base_price'] - 1 ) * 100

						if ( total_percent_change >= stocks[ticker]['exit_percent'] ):
							stocks[ticker]['exit_percent_signal'] = True

						# Set the stoploss lower if the candle touches the exit_percent, but closes above it
						elif ( low_percent_change >= stocks[ticker]['exit_percent'] and total_percent_change < stocks[ticker]['exit_percent'] and
								stocks[ticker]['exit_percent_signal'] == False ):
							if ( stocks[ticker]['decr_threshold'] > total_percent_change ):
								stocks[ticker]['decr_threshold'] = total_percent_change

					# Actions to take when we first hit exit_percent_signal
					if ( stocks[ticker]['exit_percent_signal'] == True ):

						# Set stoploss to exit_percent
						stocks[ticker]['decr_threshold']                = stocks[ticker]['exit_percent']
						stocks[ticker]['options_decr_threshold']        = stocks[ticker]['options_exit_percent']

						# Trigger the exit signal if quick_exit was configured and quick_exit_percent
						#  has been achieved
						if ( (cur_algo['quick_exit'] == True or stocks[ticker]['quick_exit'] == True) ):
							if ( cur_algo['options'] == True and options_total_percent_change >= cur_algo['quick_exit_percent'] ):
								print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(options_total_percent_change, 3)) + '%')
								stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

							elif ( cur_algo['options'] == False and total_percent_change >= cur_algo['quick_exit_percent'] ):
								print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(total_percent_change, 3)) + '%')
								stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

				# If exit_percent has been hit, watch the price action and determine when the trend has ended
				#  Typically this is when the candles start to turn GREEN
				elif ( stocks[ticker]['exit_percent_signal'] == True ):

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
						period		= 5
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( cndls[-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bear') == False ):
							stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

					elif ( cur_algo['use_combined_exit'] ):
						trend_exit	= False
						ha_exit		= False

						# Check Trend
						period		= 2
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( stocks[ticker]['pricehistory']['candles'][-i] )

						if ( price_trend(cndl_slice, period=period, affinity='bear') == False ):
							trend_exit = True

						# Check Heikin Ashi candles
						last_close	= stocks[ticker]['pricehistory']['hacandles'][-1]['close']
						last_open	= stocks[ticker]['pricehistory']['hacandles'][-1]['open']
						if ( last_close > last_open ):
							ha_exit = True

						print( '(' + str(ticker) + '): trend_exit=' + str(trend_exit) + ', ha_exit=' + str(ha_exit) )
						if ( trend_exit == True and ha_exit == True ):
							stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

					# Basic exit algo, just sell on the first RED candle
					elif ( last_close > last_open ):
						stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

			# Check for price reversal above the original entry price
			if ( stocks[ticker]['exit_percent_signal'] == True and stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == False and
					((cur_algo['options'] == True and stoploss_last_price < stoploss_orig_base) or
					 (cur_algo['options'] == False and stoploss_last_price > stoploss_orig_base)) ):

				# If we get to this point then the exit_percent_signal was triggered, but then the stock
				#  rapidly changed direction above cost basis. But because exit_percent_signal was triggered
				#  the stoploss routine above will not catch this. So at this point we probably need to stop out.
				stocks[ticker]['exit_percent_signal']		= False
				stocks[ticker]['decr_threshold']		= 0.5
				stocks[ticker]['options_decr_threshold']	= stocks[ticker]['options_decr_threshold'] / 2

			# Handle quick_exit_percent if quick_exit is configured
			if ( (cur_algo['quick_exit'] == True or stocks[ticker]['quick_exit'] == True) and
					stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == False ):

				print( str(options_total_percent_change) + ' / ' + str(cur_algo['quick_exit_percent']))
				if ( cur_algo['options'] == True and stoploss_last_price > stoploss_orig_base and
						options_total_percent_change >= cur_algo['quick_exit_percent'] ):
					print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(options_total_percent_change, 3)) + '%')
					stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

				elif ( cur_algo['options'] == False and stoploss_last_price < stoploss_orig_base and
						total_percent_change >= cur_algo['quick_exit_percent'] ):
					print( '(' + str(ticker) + '): quick_exit triggered at ' + str(round(total_percent_change, 3)) + '%')
					stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] = True

			# StochRSI MONITOR
			# Do not use stochrsi as an exit signal if exit_percent_signal is triggered. That means we've surpassed the
			# exit_percent threshold and should wait for either a red candle or for decr_threshold to be hit.
			if ( (cur_algo['primary_stochrsi'] == True or cur_algo['stochrsi_5m'] == True) and
					args.variable_exit == False and stocks[ticker]['exit_percent_signal'] == False ):

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

			# When in scalp mode, check to see if previous LIMIT order has been set
			exit_passthrough = True
			if ( cur_algo['scalp_mode'] == True and stocks[ticker]['order_id'] != None and args.fake == False and
					(caller_id != None and caller_id == 'chart_equity') and
					stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == False ):

				# Look up order_id status to see if stock had already hit the stop limit
				order_data = tda_gobot_helper.get_order(order_id=stocks[ticker]['order_id'], account_number=tda_account_number, passcode=passcode)
				if ( isinstance(order_data, bool) and order_data == False ):
					print('Error: Unable to look up order data for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']), file=sys.stderr)

				# Check if the existing LIMIT order has been filled, and if not then cancel it
				try:
					quantity_remaining = float( order_data['remainingQuantity'] )
				except:
					quantity_remaining = stocks[ticker]['options_qty']

				# If LIMIT order has been filled, try to set options_last_price to the last price from get_order()
				#  and move to exit out of sell mode
				if ( quantity_remaining == 0 ):
					try:
						float( order_data['orderActivityCollection'][0]['executionLegs'][0]['price'] )
					except:
						pass
					else:
						options_last_price = order_data['orderActivityCollection'][0]['executionLegs'][0]['price']

				stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal']	= True
				exit_passthrough						= True


			# BUY-TO-COVER THE STOCK
			if ( stocks[ticker]['algo_signals'][algo_id]['buy_to_cover_signal'] == True ):
				if ( args.fake == False or (args.fake == False and exit_passthrough == False) ):

					# Ensure we are logged in
					tda_gobot_helper.tdalogin(passcode)

					# OPTIONS
					if ( cur_algo['options'] == True ):
						if ( cur_algo['scalp_mode'] == True and stocks[ticker]['order_id'] != None ):

							# Look up order_id status to see if stock had already hit the stop limit
							order_data = tda_gobot_helper.get_order(order_id=stocks[ticker]['order_id'], account_number=tda_account_number, passcode=passcode)
							if ( isinstance(order_data, bool) and order_data == False ):
								print('Error: Unable to look up order data for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']), file=sys.stderr)

							# Check if the existing LIMIT order has been filled, and if not then cancel it
							try:
								quantity_remaining = float( order_data['remainingQuantity'] )
							except:
								quantity_remaining = stocks[ticker]['options_qty']

							if ( quantity_remaining > 0 ):
								print('Canceling limit order for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']) + ', remaining options: ' + str(quantity_remaining))
								order_data = tda_gobot_helper.cancel_order(order_id=stocks[ticker]['order_id'], account_number=tda_account_number, passcode=passcode)
								if ( isinstance(order_data, bool) and order_data == False ):
									print('Error: Unable to cancel limit order for "' + str(stocks[ticker]['options_ticker']) + '", order ID: ' + str(stocks[ticker]['order_id']), file=sys.stderr)

								stocks[ticker]['options_qty'] = quantity_remaining

						# Place market order to sell option
						order_data = tda_gobot_helper.buy_sell_option(contract=stocks[ticker]['options_ticker'], quantity=stocks[ticker]['options_qty'], instruction='sell_to_close', fillwait=True, account_number=tda_account_number, debug=debug)

					# EQUITY
					else:
						data = tda_gobot_helper.buytocover_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

				if ( cur_algo['options'] == True ):
					percent_change = abs( stocks[ticker]['options_orig_base_price'] / options_last_price - 1 ) * 100
					print('Net change (' + str(stocks[ticker]['options_ticker']) + '): ' + str(options_net_change) + ' USD (' + str(round(percent_change, 2)) + '%)')
					tda_gobot_helper.log_monitor(stocks[ticker]['options_ticker'], percent_change, options_last_price, options_net_change, stocks[ticker]['options_base_price'], stocks[ticker]['options_orig_base_price'], stocks[ticker]['options_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=False, sold=True)

				else:
					percent_change = abs( stocks[ticker]['options_orig_base_price'] / options_last_price - 1 ) * 100
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD (' + str(round(percent_change, 2)) + '%)')
					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True, sold=True)

				# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
				if ( net_change > 0 ):
					stocks[ticker]['failed_txs'] -= 1
					stocks[ticker]['failed_usd'] -= net_change
					if ( stocks[ticker]['failed_usd'] <= 0 or stocks[ticker]['failed_txs'] <= 0 ):
						stocks[ticker]['isvalid'] = False
						if ( args.fake == False ):
							tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)

				# Change signal to 'long' and generate new tx_id for next iteration
				stocks[ticker]['tx_id']				= random.randint(1000, 9999)
				stocks[ticker]['stock_usd']			= cur_algo['stock_usd']
				stocks[ticker]['quick_exit']			= cur_algo['quick_exit']
				stocks[ticker]['order_id']			= None
				stocks[ticker]['stock_qty']			= 0
				stocks[ticker]['base_price']			= 0
				stocks[ticker]['orig_base_price']		= 0

				stocks[ticker]['options_ticker']		= None
				stocks[ticker]['options_usd']			= cur_algo['options_usd']
				stocks[ticker]['options_qty']			= 0
				stocks[ticker]['options_orig_base_price']	= 0
				stocks[ticker]['options_base_price']		= 0

				stocks[ticker]['incr_threshold']		= args.incr_threshold
				stocks[ticker]['orig_incr_threshold']		= args.incr_threshold
				stocks[ticker]['decr_threshold']		= args.decr_threshold
				stocks[ticker]['orig_decr_threshold']		= args.decr_threshold
				stocks[ticker]['exit_percent']			= args.exit_percent

				stocks[ticker]['options_incr_threshold']	= args.options_incr_threshold
				stocks[ticker]['options_decr_threshold']	= args.options_decr_threshold
				stocks[ticker]['options_exit_percent']		= args.options_exit_percent

				if ( args.shortonly == True ):
					reset_signals(ticker, signal_mode='short')
				else:
					reset_signals(ticker, signal_mode='long')


		# Undefined mode - this shouldn't happen
		else:
			print('Error: undefined signal_mode: ' + str(signal_mode), file=sys.stderr)

	# END stocks.keys() loop

	# Make the debug messages easier to read
	if ( debug == True and caller_id != 'level1' ):
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

