#!/usr/bin/python3 -u

import os, sys
import time, datetime, pytz, random
import tda_gobot_helper

## TODO:
#	Add all the other indicators

def stochrsi_gobot( stream=None, debug=False ):

	if not isinstance(stream, dict):
		print('Error:')
		return False

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

		if ( isinstance(stocks[ticker]['isvalid'], bool) and stocks[ticker]['isvalid'] == False ):
			continue

		# Get stochastic RSI
		stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(stocks[ticker]['pricehistory'], rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)
		if ( isinstance(stochrsi, bool) and stochrsi == False ):
			print('Error: get_stochrsi(' + str(ticker) + ') returned false - no data', file=sys.stderr)
			return False


		# If using the same 1-minute data, the len of stochrsi will be stochrsi_period * (stochrsi_period * 2) - 1
		if ( len(stochrsi) != len(stocks[ticker]['pricehistory']['candles']) - (stochrsi_period * 2 - 1) ):
			print('Warning, unexpected length of stochrsi (pricehistory[candles]=' + str(len(stocks[ticker]['pricehistory']['candles'])) + ', len(stochrsi)=' + str(len(stochrsi)) + ')')

		stocks[ticker]['cur_rsi_k'] = rsi_k[-1]
		stocks[ticker]['cur_rsi_d'] = rsi_d[-1]
		if ( stocks[ticker]['prev_rsi_k'] == -1 or stocks[ticker]['prev_rsi_d'] == -1):
			stocks[ticker]['prev_rsi_k'] = stocks[ticker]['cur_rsi_k']
			stocks[ticker]['prev_rsi_d'] = stocks[ticker]['cur_rsi_d']

		if ( debug == True ):
			time_now = datetime.datetime.now( mytimezone )
			print(  '(' + str(ticker) + ') StochRSI period: ' + str(rsi_period) + ' / StochRSI type: ' + str(rsi_type) +
				' / StochRSI K period: ' + str(rsi_k_period) + ' / StochRSI D period: ' + str(rsi_d_period) + ' / StochRSI slow period: ' + str(rsi_slow) )
			print('(' + str(ticker) + ') Current StochRSI K: ' + str(round(stocks[ticker]['cur_rsi_k'], 2)) +
						' / Previous StochRSI K: ' + str(round(stocks[ticker]['prev_rsi_k'], 2)))
			print('(' + str(ticker) + ') Current StochRSI D: ' + str(round(stocks[ticker]['cur_rsi_d'], 2)) +
						' / Previous StochRSI D: ' + str(round(stocks[ticker]['prev_rsi_d'], 2)))
			print('(' + str(ticker) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
				', timestamp received from API ' +
				datetime.datetime.fromtimestamp(float(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f') +
				' (' + str(int(stocks[ticker]['pricehistory']['candles'][-1]['datetime'])) + ')' )

		# Loop continuously while after hours if --multiday was set
		if ( tda_gobot_helper.ismarketopen_US() == False and args.multiday == True ):
			continue

		# Set some short variables to improve readability :)
		signal_mode = stocks[ticker]['signal_mode']
		cur_rsi_k = stocks[ticker]['cur_rsi_k']
		prev_rsi_k = stocks[ticker]['prev_rsi_k']
		cur_rsi_d = stocks[ticker]['cur_rsi_d']
		prev_rsi_d = stocks[ticker]['prev_rsi_d']

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

				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

				stocks[ticker]['prev_rsi_k'] = cur_rsi_k
				stocks[ticker]['prev_rsi_d'] = cur_rsi_d

				continue

			# If args.hold_overnight=False and args.multiday==True, we won't enter any new trades 1-hour before market close
			if ( args.multiday == True and args.hold_overnight == False and tda_gobot_helper.isendofday(60) ):
				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

				stocks[ticker]['prev_rsi_k'] = cur_rsi_k
				stocks[ticker]['prev_rsi_d'] = cur_rsi_d

				continue


		# BUY MODE - looking for a signal to purchase the stock
		if ( signal_mode == 'buy' ):

			# Jump to short mode if StochRSI K and D are already above rsi_high_limit
			# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit and stocks[ticker]['shortable'] == True ):
				print('(' + str(ticker) + ') StochRSI K and D values already above ' + str(rsi_high_limit) + ', switching to short mode.')

				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

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


			# BUY THE STOCK
			if ( stocks[ticker]['buy_signal'] == True ):

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
				if ( stocks[ticker]['buy_signal'] == True and args.no_use_resistance == False ):
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
						stocks[ticker]['stock_qty'] = 0
						stocks[ticker]['prev_rsi_k'] = cur_rsi_k
						stocks[ticker]['prev_rsi_d'] = cur_rsi_d
						continue

				# Purchase the stock
				if ( tda_gobot_helper.ismarketopen_US() == True ):
					print('Purchasing ' + str(stocks[ticker]['stock_qty']) + ' shares of ' + str(ticker))
					stocks[ticker]['num_purchases'] -= 1

					if ( args.fake == False ):
						data = tda_gobot_helper.buy_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)
						if ( data == False ):
							print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
							stocks[ticker]['stock_qty'] = 0
							stocks[ticker]['buy_signal'] = False
							continue

					try:
						stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						stocks[ticker]['orig_base_price'] = last_price

				else:
					print('Stock ' + str(ticker) + ' not purchased because market is closed.')
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['buy_signal'] = False

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d
					continue


				net_change = 0
				stocks[ticker]['base_price'] = stocks[ticker]['orig_base_price']

				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'])

				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

				stocks[ticker]['signal_mode'] = 'sell' # Switch to 'sell' mode for the next loop


		# SELL MODE - looking for a signal to sell the stock
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

					tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist if sold at a loss greater than max_failed_usd
					if ( net_change < 0 and abs(net_change) > float(args.max_failed_usd) ):
						tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, 0)
						stocks[ticker]['isvalid'] = False

					stocks[ticker]['tx_id'] = random.randint(1000, 9999)
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['base_price'] = 0
					stocks[ticker]['orig_base_price'] = 0

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d

					stocks[ticker]['buy_signal'] = False
					stocks[ticker]['sell_signal'] = False
					stocks[ticker]['short_signal'] = False
					stocks[ticker]['buy_to_cover_signal'] = False

					stocks[ticker]['signal_mode'] = 'buy'
					continue


			# STOPLOSS MONITOR
			# If price decreases
			if ( float(last_price) < float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(last_price) / float(stocks[ticker]['base_price']) - 1 ) * 100
				if ( debug == True ):
					print('Stock "' +  str(ticker) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'])

				# SELL the security if we are using a trailing stoploss
				if ( percent_change >= stocks[ticker]['decr_threshold'] and args.stoploss == True ):

					print('Stock "' + str(ticker) + '" dropped below the decr_threshold (' + str(stocks[ticker]['decr_threshold']) + '%), selling the security...')
					if ( args.fake == False ):
						data = tda_gobot_helper.sell_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
					if ( net_change < 0 ):
						stocks[ticker]['failed_txs'] -= 1
						if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
							tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)
							stocks[ticker]['isvalid'] = False

					# Change signal to 'buy' and generate new tx_id for next iteration
					stocks[ticker]['tx_id'] = random.randint(1000, 9999)
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['base_price'] = 0
					stocks[ticker]['orig_base_price'] = 0

					stocks[ticker]['cur_rsi_k'] = -1
					stocks[ticker]['cur_rsi_d'] = -1
					stocks[ticker]['prev_rsi_k'] = -1
					stocks[ticker]['prev_rsi_d']= -1

					stocks[ticker]['buy_signal'] = False
					stocks[ticker]['sell_signal'] = False
					stocks[ticker]['short_signal'] = False
					stocks[ticker]['buy_to_cover_signal'] = False

					stocks[ticker]['signal_mode'] = 'buy'
					continue


			# If price increases
			elif ( float(last_price) > float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(stocks[ticker]['base_price']) / float(last_price) - 1 ) * 100
				if ( debug == 1 ):
					print('Stock "' +  str(ticker) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

				# Re-set the base_price to the last_price if we increase by incr_threshold or more
				# This way we can continue to ride a price increase until it starts dropping
				if ( percent_change >= incr_threshold ):
					stocks[ticker]['base_price'] = last_price
					print('Stock "' + str(ticker) + '" increased above the incr_threshold (' + str(incr_threshold) + '%), resetting base price to '  + str(last_price))
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					stocks[ticker]['decr_threshold'] = incr_threshold / 2

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'])

			# No price change
			else:
				tda_gobot_helper.log_monitor(ticker, 0, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'])


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

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], sold=True)
				print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

				# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
				if ( net_change < 0 ):
					stocks[ticker]['failed_txs'] -= 1
					if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
						tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)


				# Change signal to 'buy' or 'short' and generate new tx_id for next iteration
				stocks[ticker]['tx_id'] = random.randint(1000, 9999)
				stocks[ticker]['stock_qty'] = 0
				stocks[ticker]['base_price'] = 0
				stocks[ticker]['orig_base_price'] = 0

				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

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

				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

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


			# SHORT THE STOCK
			if ( stocks[ticker]['short_signal'] == True ):

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
				if ( stocks[ticker]['short_signal'] == True and args.no_use_resistance == False ):
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
						stocks[ticker]['stock_qty'] = 0
						stocks[ticker]['prev_rsi_k'] = cur_rsi_k
						stocks[ticker]['prev_rsi_d'] = cur_rsi_d
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
								stocks[ticker]['short_signal'] = False

								stocks[ticker]['shortable'] = False
								stocks[ticker]['isvalid'] = False
								continue

							else:
								print('Error: Unable to short "' + str(ticker) + '" - disabling shorting', file=sys.stderr)

								stocks[ticker]['shortable'] = False
								stocks[ticker]['stock_qty'] = 0
								stocks[ticker]['short_signal'] = False
								stocks[ticker]['signal_mode'] = 'buy'
								continue

					try:
						stocks[ticker]['orig_base_price'] = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						stocks[ticker]['orig_base_price'] = last_price

				else:
					print('Stock ' + str(ticker) + ' not shorted because market is closed.')
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['short_signal'] = False

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d

					if ( args.shortonly == False ):
						signal_mode = 'buy'

					continue


				net_change = 0
				stocks[ticker]['base_price'] = stocks[ticker]['orig_base_price']

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], short=True, sold=False)

				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

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

					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], short=True, sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist if sold at a loss greater than max_failed_usd
					if ( net_change > 0 and abs(net_change) > args.max_failed_usd ):
						tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)
						stocks[ticker]['isvalid'] = False

					stocks[ticker]['tx_id'] = random.randint(1000, 9999)
					stocks[ticker]['stock_qty'] = 0
					stocks[ticker]['base_price'] = 0
					stocks[ticker]['orig_base_price'] = 0

					stocks[ticker]['prev_rsi_k'] = cur_rsi_k
					stocks[ticker]['prev_rsi_d'] = cur_rsi_d

					stocks[ticker]['buy_signal'] = False
					stocks[ticker]['sell_signal'] = False
					stocks[ticker]['short_signal'] = False
					stocks[ticker]['buy_to_cover_signal'] = False

					stocks[ticker]['signal_mode'] = 'buy'
					if ( args.shortonly == True ):
						stocks[ticker]['signal_mode'] = 'short'

					continue


			# STOPLOSS MONITOR
			# If price decreases
			if ( float(last_price) < float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(last_price) / float(stocks[ticker]['base_price']) - 1 ) * 100

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], short=True, proc_id=stocks[ticker]['tx_id'])

				# Re-set the base_price to the last_price if we increase by incr_threshold or more
				# This way we can continue to ride a price increase until it starts dropping
				if ( percent_change >= incr_threshold ):
					stocks[ticker]['base_price'] = last_price
					print('SHORTED Stock "' + str(ticker) + '" decreased below the incr_threshold (' + str(incr_threshold) + '%), resetting base price to '  + str(last_price))
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					stocks[ticker]['decr_threshold'] = incr_threshold / 2

			# If price increases
			elif ( float(last_price) > float(stocks[ticker]['base_price']) ):
				percent_change = abs( float(stocks[ticker]['base_price']) / float(last_price) - 1 ) * 100

				# BUY-TO-COVER the security if we are using a trailing stoploss
				if ( percent_change >= stocks[ticker]['decr_threshold'] and args.stoploss == True ):

					print('SHORTED Stock "' + str(ticker) + '" increased above the decr_threshold (' + str(stocks[ticker]['decr_threshold']) + '%), covering shorted stock...')
					if ( args.fake == False ):
						data = tda_gobot_helper.buytocover_stock_marketprice(ticker, stocks[ticker]['stock_qty'], fillwait=True, debug=True)

					tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], short=True, sold=True)
					print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

					# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
					if ( net_change > 0 ):
						stocks[ticker]['failed_txs'] -= 1
						if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
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

					stocks[ticker]['buy_signal'] = False
					stocks[ticker]['sell_signal'] = False
					stocks[ticker]['short_signal'] = False
					stocks[ticker]['buy_to_cover_signal'] = False

					stocks[ticker]['signal_mode'] = 'buy'
					if ( args.shortonly == True ):
						stocks[ticker]['signal_mode'] = 'short'

					continue

			# No price change
			else:
				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], short=True)


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

				tda_gobot_helper.log_monitor(ticker, percent_change, last_price, net_change, stocks[ticker]['base_price'], stocks[ticker]['orig_base_price'], stocks[ticker]['stock_qty'], proc_id=stocks[ticker]['tx_id'], short=True, sold=True)
				print('Net change (' + str(ticker) + '): ' + str(net_change) + ' USD')

				# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
				if ( net_change > 0 ):
					stocks[ticker]['failed_txs'] -= 1
					if ( abs(net_change) > args.max_failed_usd or stocks[ticker]['failed_txs'] == 0 ):
						tda_gobot_helper.write_blacklist(ticker, stocks[ticker]['stock_qty'], stocks[ticker]['orig_base_price'], last_price, net_change, percent_change)

				# Change signal to 'buy' and generate new tx_id for next iteration
				stocks[ticker]['tx_id'] = random.randint(1000, 9999)
				stocks[ticker]['stock_qty'] = 0
				stocks[ticker]['base_price'] = 0
				stocks[ticker]['orig_base_price'] = 0

				stocks[ticker]['buy_signal'] = False
				stocks[ticker]['sell_signal'] = False
				stocks[ticker]['short_signal'] = False
				stocks[ticker]['buy_to_cover_signal'] = False

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

	# END stocks.keys() loop


	time.sleep(loopt)
	print('DEBUG: END LOOP')

	return True

