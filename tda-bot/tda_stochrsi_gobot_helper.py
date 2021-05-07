#!/usr/bin/python3 -u

import os, sys
import time, datetime, pytz, random
import tda_gobot_helper


# Reset all the buy/sell/short/buy-to-cover and indicator signals
def reset_signals(ticker=None):

	if ( ticker == None ):
		return False

	stocks[ticker]['buy_signal']			= False
	stocks[ticker]['sell_signal']			= False
	stocks[ticker]['short_signal']			= False
	stocks[ticker]['buy_to_cover_signal']		= False

	stocks[ticker]['final_buy_signal']		= False
	stocks[ticker]['final_sell_signal']		= False
	stocks[ticker]['final_short_signal']		= False
	stocks[ticker]['final_buy_to_cover_signal']	= False

	stocks[ticker]['adx_signal']			= False
	stocks[ticker]['dmi_signal']			= False
	stocks[ticker]['macd_signal']			= False
	stocks[ticker]['aroonosc_signal']		= False

	stocks[ticker]['plus_di_crossover']		= False
	stocks[ticker]['minus_di_crossover']		= False
	stocks[ticker]['macd_crossover']		= False
	stocks[ticker]['macd_avg_crossover']		= False

	return True


# Main helper function for tda-stochrsi-gobot-v2 that implements the primary stochrsi
#  algorithm along with any secondary algorithms specified.
def stochrsi_gobot( stream=None, debug=False ):

	if not isinstance(stream, dict):
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
		sys.exit(0)

	# Exit if we are not set up to monitor across multiple days
	if ( tda_gobot_helper.ismarketopen_US() == False and args.multiday == False ):
		print('Market closed, exiting.')
		sys.exit(0)


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

		candle_data = {	'open':		idx['OPEN_PRICE'],
				'high':		idx['HIGH_PRICE'],
				'low':		idx['LOW_PRICE'],
				'close':	idx['CLOSE_PRICE'],
				'volume':	idx['VOLUME'],
#				'datetime':	idx['CHART_TIME'] }
				'datetime':	stream['timestamp'] }

		stocks[ticker]['pricehistory']['candles'].append(candle_data)


	# Iterate through the stock tickers, calculate the stochRSI, and make buy/sell decisions
	for ticker in stocks.keys():

		if ( stocks[ticker]['isvalid'] == False ):
			continue

		# Initialize some local variables
		percent_change = 0
		net_change = 0


		# Get stochastic RSI
		try:
			stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(stocks[ticker]['pricehistory'], rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

		except Exception as e:
			print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + '): ' + str(e))

		if ( isinstance(stochrsi, bool) and stochrsi == False ):
			print('Error: stochrsi_gobot(): get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
			continue

		# If using the same 1-minute data, the len of stochrsi will be stochrsi_period * (stochrsi_period * 2) - 1
#		if ( len(stochrsi) != len(stocks[ticker]['pricehistory']['candles']) - (stochrsi_period * 2 - 1) ):
#			print('Warning, unexpected length of stochrsi (pricehistory[candles]=' + str(len(stocks[ticker]['pricehistory']['candles'])) + ', len(stochrsi)=' + str(len(stochrsi)) + ')')

		stocks[ticker]['cur_rsi_k'] = rsi_k[-1]
		stocks[ticker]['cur_rsi_d'] = rsi_d[-1]
		if ( stocks[ticker]['prev_rsi_k'] == -1 or stocks[ticker]['prev_rsi_d'] == -1 ):
			stocks[ticker]['prev_rsi_k'] = stocks[ticker]['cur_rsi_k']
			stocks[ticker]['prev_rsi_d'] = stocks[ticker]['cur_rsi_d']

		# ADX, +DI, -DI
		if ( args.with_adx == True or args.with_dmi == True ):
			adx = []
			plus_di = []
			minus_di = []
			adx_period = 64
			try:
				adx, plus_di, minus_di = tda_gobot_helper.get_adx(stocks[ticker]['pricehistory'], period=adx_period)

			except Exception as e:
				print('Error: stochrsi_gobot(' + str(ticker) + '): get_adx(): ' + str(e))
				continue

			stocks[ticker]['cur_adx'] = adx[-1]
			stocks[ticker]['cur_plus_di'] = plus_di[-1]
			stocks[ticker]['cur_minus_di'] = minus_di[-1]

			if ( stocks[ticker]['prev_plus_di'] == -1 or stocks[ticker]['prev_minus_di'] == -1 ):
				stocks[ticker]['prev_plus_di'] = stocks[ticker]['cur_plus_di']
				stocks[ticker]['prev_minus_di'] = stocks[ticker]['cur_minus_di']

		# MACD - 48, 104, 36
		if ( args.with_macd == True ):
			macd = []
			macd_signal = []
			macd_histogram = []
			try:
				macd, macd_avg, macd_histogram = tda_gobot_helper.get_macd(stocks[ticker]['pricehistory'], short_period=macd_short_period, long_period=macd_long_period, signal_period=macd_signal_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_macd(' + str(ticker) + '): ' + str(e))
				continue

			stocks[ticker]['cur_macd'] = macd[-1]
			stocks[ticker]['cur_macd_avg'] = macd_avg[-1]

			if ( stocks[ticker]['prev_macd'] == -1 or stocks[ticker]['prev_macd_avg'] == -1 ):
				stocks[ticker]['prev_macd'] = stocks[ticker]['cur_macd']
				stocks[ticker]['prev_macd_avg'] = stocks[ticker]['cur_macd_avg']

		# Aroon Oscillator
		if ( args.with_aroonosc == True ):
			aroonosc = []
			try:
				aroonosc = tda_gobot_helper.get_aroon_osc(stocks[ticker]['pricehistory'], period=aroonosc_period)

			except Exception as e:
				print('Error: stochrsi_gobot(): get_aroon_osc(' + str(ticker) + '): ' + str(e))
				continue

			stocks[ticker]['cur_aroonosc'] = aroonosc[-1]

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

			# ADX
			if ( args.with_adx == True ):
				print('(' + str(ticker) + ') Current ADX: ' + str(round(stocks[ticker]['cur_adx'], 2)))

			# PLUS/MINUS DI
			if ( args.with_dmi == True ):
				print('(' + str(ticker) + ') Current PLUS_DI: ' + str(round(stocks[ticker]['cur_plus_di'], 2)) +
							' / Previous PLUS_DI: ' + str(round(stocks[ticker]['prev_plus_di'], 2)))
				print('(' + str(ticker) + ') Current MINUS_DI: ' + str(round(stocks[ticker]['cur_minus_di'], 2)) +
							' / Previous MINUS_DI: ' + str(round(stocks[ticker]['prev_minus_di'], 2)))

			# MACD
			if ( args.with_macd == True ):
				print('(' + str(ticker) + ') Current MACD: ' + str(round(stocks[ticker]['cur_macd'], 2)) +
							' / Previous MACD: ' + str(round(stocks[ticker]['prev_macd'], 2)))
				print('(' + str(ticker) + ') Current MACD_AVG: ' + str(round(stocks[ticker]['cur_macd_avg'], 2)) +
							' / Previous MACD_AVG: ' + str(round(stocks[ticker]['prev_macd_avg'], 2)))

			# AroonOsc
			if (args.with_aroonosc == True ):
				print('(' + str(ticker) + ') Current AroonOsc: ' + str(round(stocks[ticker]['cur_aroonosc'], 2)))

			# Timestamp check
			print('(' + str(ticker) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
				', timestamp received from API ' +
				datetime.datetime.fromtimestamp(float(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f') +
				' (' + str(int(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])) + ')' )

			print()

		# Loop continuously while after hours if --multiday was set
		if ( tda_gobot_helper.ismarketopen_US() == False and args.multiday == True ):
			continue

		# Set some short variables to improve readability :)
		signal_mode	= stocks[ticker]['signal_mode']
		cur_rsi_k	= stocks[ticker]['cur_rsi_k']
		prev_rsi_k	= stocks[ticker]['prev_rsi_k']
		cur_rsi_d	= stocks[ticker]['cur_rsi_d']
		prev_rsi_d	= stocks[ticker]['prev_rsi_d']

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
			if ( (tda_gobot_helper.isendofday(60) == True or tda_gobot_helper.ismarketopen_US() == False) and args.multiday == False ):
				print('(' + str(ticker) + ') Market is closed or near closing.')

				reset_signals(ticker)
				stocks[ticker]['prev_rsi_k'] = cur_rsi_k
				stocks[ticker]['prev_rsi_d'] = cur_rsi_d

				stocks[ticker]['prev_plus_di'] = cur_plus_di
				stocks[ticker]['prev_minus_di'] = cur_minus_di

				stocks[ticker]['prev_macd'] = cur_macd
				stocks[ticker]['prev_macd_avg'] = cur_macd_avg
				continue

			# If args.hold_overnight=False and args.multiday==True, we won't enter any new trades 1-hour before market close
			if ( args.multiday == True and args.hold_overnight == False and tda_gobot_helper.isendofday(60) ):
				reset_signals(ticker)
				stocks[ticker]['prev_rsi_k'] = cur_rsi_k
				stocks[ticker]['prev_rsi_d'] = cur_rsi_d

				stocks[ticker]['prev_plus_di'] = cur_plus_di
				stocks[ticker]['prev_minus_di'] = cur_minus_di

				stocks[ticker]['prev_macd'] = cur_macd
				stocks[ticker]['prev_macd_avg'] = cur_macd_avg
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

			elif ( cur_rsi_k > rsi_low_limit and cur_rsi_d > rsi_low_limit ):
				# Reset the buy signal if rsi has wandered back above rsi_low_limit
				if ( stocks[ticker]['buy_signal'] == True ):
					print( '(' + str(ticker) + ') BUY SIGNAL CANCELED: RSI moved back above rsi_low_limit' )

				reset_signals(ticker)

			# Process any secondary indicators
			# ADX signal
			if ( args.with_adx == True ):
				stocks[ticker]['adx_signal'] = False
				if ( cur_adx > 25 ):
					stocks[ticker]['adx_signal'] = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( args.with_dmi == True ):
				if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = True
					stocks[ticker]['minus_di_crossover'] = False

				elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = False
					stocks[ticker]['minus_di_crossover'] = True

				stocks[ticker]['dmi_signal'] = False
				if ( stocks[ticker]['plus_di_crossover'] == True and cur_plus_di > cur_minus_di ):
					stocks[ticker]['dmi_signal'] = True

			# Aroon oscillator signals
			# Values closer to 100 indicate an uptrend
			if ( args.with_aroonosc == True ):
				stocks[ticker]['aroonosc_signal'] = False
				if ( cur_aroonosc > 60 ):
					stocks[ticker]['aroonosc_signal'] = True

			# MACD crossover signals
			if ( args.with_macd == True ):
				if ( prev_macd < prev_macd_avg and cur_macd >= cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = True
					stocks[ticker]['macd_avg_crossover'] = False

				elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = True
					stocks[ticker]['macd_avg_crossover'] = True

				stocks[ticker]['macd_signal'] = False
				if ( stocks[ticker]['macd_crossover'] == True and cur_macd > cur_macd_avg ):
					stocks[ticker]['macd_signal'] = True

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( stocks[ticker]['buy_signal'] == True ):

				stocks[ticker]['final_buy_signal'] = True
				if ( args.with_adx == True and stocks[ticker]['adx_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( args.with_dmi == True and stocks[ticker]['dmi_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( args.with_aroonosc == True and stocks[ticker]['aroonosc_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False

				if ( args.with_macd == True and stocks[ticker]['macd_signal'] != True ):
					stocks[ticker]['final_buy_signal'] = False


			# BUY THE STOCK
			if ( stocks[ticker]['buy_signal'] == True and stocks[ticker]['final_buy_signal'] == True ):

				# Calculate stock quantity from investment amount
				last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
				if ( last_price == False ):
					print('Error: get_lastprice(' + str(ticker)+ ') returned False')
					time.sleep(1)

					# Try logging in and looping around again
					if ( tda_gobot_helper.tdalogin(passcode) != True ):
						print('Error: tdalogin(): login failure')

					continue

				stocks[ticker]['stock_qty'] = int( float(stock_usd) / float(last_price) )

				# Final sanity checks should go here
				if ( args.no_use_resistance == False ):
					if ( float(last_price) >= float(stocks[ticker]['twenty_week_high']) ):
						# This is not a good bet
						stocks[ticker]['twenty_week_high'] = float(last_price)
						print('Stock ' + str(ticker) + ' buy signal indicated, but last price (' + str(last_price) + ') is already above the 20-week high (' + str(stocks[ticker]['twenty_week_high']) + ')')
						stocks[ticker]['buy_signal'] = False

					elif ( ( abs(float(last_price) / float(stocks[ticker]['twenty_week_high']) - 1) * 100 ) < 1 ):
						# Current high is within 1% of 20-week high, not a good bet
						print('Stock ' + str(ticker) + ' buy signal indicated, but last price (' + str(last_price) + ') is already within 1% of the 20-week high (' + str(stocks[ticker]['twenty_week_high']) + ')')
						stocks[ticker]['buy_signal'] = False

					if ( stocks[ticker]['buy_signal'] == False ):
						reset_signals(ticker)
						stocks[ticker]['stock_qty'] = 0

						stocks[ticker]['prev_rsi_k'] = cur_rsi_k
						stocks[ticker]['prev_rsi_d'] = cur_rsi_d

						stocks[ticker]['prev_plus_di'] = cur_plus_di
						stocks[ticker]['prev_minus_di'] = cur_minus_di

						stocks[ticker]['prev_macd'] = cur_macd
						stocks[ticker]['prev_macd_avg'] = cur_macd_avg
						continue

				# Purchase the stock
				if ( tda_gobot_helper.ismarketopen_US() == True ):
					print('Purchasing ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker))
					stocks[ticker]['num_purchases'] -= 1

					if ( args.fake == False ):
						data = tda_gobot_helper.buy_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)
						if ( data == False ):
							print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
							reset_signals(ticker)
							stocks[ticker]['stock_qty'] = 0
							continue

					try:
						stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						stocks[ticker]['orig_base_price'] = last_price

				else:
					print('Stock ' + str(ticker) + ' not purchased because market is closed.')

					reset_signals(ticker)
					stocks[ticker]['stock_qty'] = 0

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d

					stocks[ticker]['prev_plus_di'] = cur_plus_di
					stocks[ticker]['prev_minus_di'] = cur_minus_di

					stocks[ticker]['prev_macd'] = cur_macd
					stocks[ticker]['prev_macd_avg'] = cur_macd_avg
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
			if ( last_price == False ):
				print('Error: get_lastprice(' + str(ticker) + ') returned False')

				# Try logging in and looping around again
				time.sleep(1)
				if ( tda_gobot_helper.tdalogin(passcode) != True ):
					print('Error: tdalogin(): login failure')

				continue

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

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d

					stocks[ticker]['prev_plus_di'] = cur_plus_di
					stocks[ticker]['prev_minus_di'] = cur_minus_di

					stocks[ticker]['prev_macd'] = cur_macd
					stocks[ticker]['prev_macd_avg'] = cur_macd_avg

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					continue


			# STOPLOSS MONITOR
			# If price decreases
			if ( float(last_price) < float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(last_price) / float(stocks[ticker]['base_price']) - 1 ) * 100
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

					stocks[ticker]['cur_rsi_k'] = -1
					stocks[ticker]['cur_rsi_d'] = -1
					stocks[ticker]['prev_rsi_k'] = -1
					stocks[ticker]['prev_rsi_d']= -1

					stocks[ticker]['cur_plus_di'] = -1
					stocks[ticker]['prev_plus_di'] = -1
					stocks[ticker]['cur_minus_di'] = -1
					stocks[ticker]['prev_minus_di'] = -1

					stocks[ticker]['cur_macd'] = -1
					stocks[ticker]['prev_macd'] = -1
					stocks[ticker]['cur_macd_avg'] = -1
					stocks[ticker]['prev_macd_avg'] = -1

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					continue


			# If price increases
			elif ( float(last_price) > float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(stocks[ticker]['base_price']) / float(last_price) - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

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

			elif ( cur_rsi_k < rsi_high_limit and cur_rsi_d < rsi_high_limit ):
				# Reset the short signal if rsi has wandered back below rsi_high_limit
				if ( stocks[ticker]['short_signal'] == True ):
					print( '(' + str(ticker) + ') SHORT SIGNAL CANCELED: RSI moved back below rsi_high_limit' )

				reset_signals(ticker)

			# Secondary Indicators
			# ADX signal
			if ( args.with_adx == True ):
				stocks[ticker]['adx_signal'] = False
				if ( cur_adx > 25 ):
					stocks[ticker]['adx_signal'] = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( args.with_dmi == True ):
				if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = True
					stocks[ticker]['minus_di_crossover'] = False

				elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
					stocks[ticker]['plus_di_crossover'] = False
					stocks[ticker]['minus_di_crossover'] = True

				stocks[ticker]['dmi_signal'] = False
				if ( stocks[ticker]['minus_di_crossover'] == True and cur_plus_di < cur_minus_di ):
					stocks[ticker]['dmi_signal'] = True

			# Aroon oscillator signals
			# Values closer to -100 indicate a downtrend
			if ( args.with_aroonosc == True ):
				stocks[ticker]['aroonosc_signal'] = False
				if ( cur_aroonosc < -60 ):
					stocks[ticker]['aroonosc_signal'] = True

			# MACD crossover signals
			if ( args.with_macd == True ):
				if ( prev_macd < prev_macd_avg and cur_macd >= cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = True
					stocks[ticker]['macd_avg_crossover'] = False

				elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
					stocks[ticker]['macd_crossover'] = True
					stocks[ticker]['macd_avg_crossover'] = True

				stocks[ticker]['macd_signal'] = False
				if ( stocks[ticker]['macd_avg_crossover'] == True and cur_macd < cur_macd_avg ):
					stocks[ticker]['macd_signal'] = True

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( stocks[ticker]['short_signal'] == True ):

				stocks[ticker]['final_short_signal'] = True
				if ( args.with_adx == True and stocks[ticker]['adx_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( args.with_dmi == True and stocks[ticker]['dmi_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( args.with_aroonosc == True and stocks[ticker]['aroonosc_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False

				if ( args.with_macd == True and stocks[ticker]['macd_signal'] != True ):
					stocks[ticker]['final_short_signal'] = False


			# SHORT THE STOCK
			if ( stocks[ticker]['short_signal'] == True and stocks[ticker]['final_short_signal'] == True ):

				# Calculate stock quantity from investment amount
				last_price = tda_gobot_helper.get_lastprice(ticker, WarnDelayed=False)
				if ( last_price == False ):
					print('Error: get_lastprice(' + str(ticker) + ') returned False')
					time.sleep(1)

					# Try logging in and looping around again
					if ( tda_gobot_helper.tdalogin(passcode) != True ):
						print('Error: tdalogin(): login failure')

					continue

				stocks[ticker]['stock_qty'] = int( float(stock_usd) / float(last_price) )

				# Final sanity checks should go here
				if ( args.no_use_resistance == False ):
					if ( float(last_price) <= float(stocks[ticker]['twenty_week_low']) ):
						# This is not a good bet
						stocks[ticker]['twenty_week_low'] = float(last_price)
						print('Stock ' + str(ticker) + ' short signal indicated, but last price (' + str(last_price) + ') is already below the 20-week low (' + str(stocks[ticker]['twenty_week_low']) + ')')
						stocks[ticker]['short_signal'] = False

					elif ( ( abs(float(stocks[ticker]['twenty_week_low']) / float(last_price) - 1) * 100 ) < 1 ):
						# Current low is within 1% of 20-week low, not a good bet
						print('Stock ' + str(ticker) + ' short signal indicated, but last price (' + str(last_price) + ') is already within 1% of the 20-week low (' + str(stocks[ticker]['twenty_week_low']) + ')')
						stocks[ticker]['short_signal'] = False

					if ( stocks[ticker]['short_signal'] == False ):
						reset_signals(ticker)
						stocks[ticker]['stock_qty'] = 0

						stocks[ticker]['prev_rsi_k'] = cur_rsi_k
						stocks[ticker]['prev_rsi_d'] = cur_rsi_d

						stocks[ticker]['prev_plus_di'] = cur_plus_di
						stocks[ticker]['prev_minus_di'] = cur_minus_di

						stocks[ticker]['prev_macd'] = cur_macd
						stocks[ticker]['prev_macd_avg'] = cur_macd_avg
						continue

				# Short the stock
				if ( tda_gobot_helper.ismarketopen_US() == True ):
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

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d

					stocks[ticker]['prev_plus_di'] = cur_plus_di
					stocks[ticker]['prev_minus_di'] = cur_minus_di

					stocks[ticker]['prev_macd'] = cur_macd
					stocks[ticker]['prev_macd_avg'] = cur_macd_avg

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
			if ( last_price == False ):
				print('Error: get_lastprice(' + str(ticker) + ') returned False')

				# Try logging in and looping around again
				time.sleep(1)
				if ( tda_gobot_helper.tdalogin(passcode) != True ):
					print('Error: tdalogin(): login failure')

				continue

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

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d

					stocks[ticker]['prev_plus_di'] = cur_plus_di
					stocks[ticker]['prev_minus_di'] = cur_minus_di

					stocks[ticker]['prev_macd'] = cur_macd
					stocks[ticker]['prev_macd_avg'] = cur_macd_avg

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					if ( args.shortonly == True ):
						stocks[ticker]['signal_mode'] = 'short'

					continue


			# STOPLOSS MONITOR
			# If price decreases
			if ( float(last_price) < float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(last_price) / float(stocks[ticker]['base_price']) - 1 ) * 100

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], short=True, proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir)

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

			# If price increases
			elif ( float(last_price) > float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(stocks[ticker]['base_price']) / float(last_price) - 1 ) * 100

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

					stocks[ticker]['cur_rsi_k'] = -1
					stocks[ticker]['cur_rsi_d'] = -1
					stocks[ticker]['prev_rsi_k'] = -1
					stocks[ticker]['prev_rsi_d']= -1

					stocks[ticker]['cur_plus_di'] = -1
					stocks[ticker]['prev_plus_di'] = -1
					stocks[ticker]['cur_minus_di'] = -1
					stocks[ticker]['prev_minus_di'] = -1

					stocks[ticker]['cur_macd'] = -1
					stocks[ticker]['prev_macd'] = -1
					stocks[ticker]['cur_macd_avg'] = -1
					stocks[ticker]['prev_macd_avg'] = -1

					reset_signals(ticker)
					stocks[ticker]['signal_mode'] = 'buy'
					if ( args.shortonly == True ):
						stocks[ticker]['signal_mode'] = 'short'

					continue

			# No price change
			else:
				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], tx_log_dir=tx_log_dir, short=True)


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
		stocks[ticker]['prev_rsi_k'] = cur_rsi_k
		stocks[ticker]['prev_rsi_d'] = cur_rsi_d

		stocks[ticker]['prev_plus_di'] = cur_plus_di
		stocks[ticker]['prev_minus_di'] = cur_minus_di

		stocks[ticker]['prev_macd'] = cur_macd
		stocks[ticker]['prev_macd_avg'] = cur_macd_avg

	# END stocks.keys() loop

	# Make the debug messages easier to read
	if ( debug == True ):
		print("\n------------------------------------------------------------------------\n")

	time.sleep(loopt)

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


