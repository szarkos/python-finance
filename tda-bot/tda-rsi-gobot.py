#!/usr/bin/python3 -u

# Monitor a stock's RSI value and make purchase decisions based off that value.
#  - If the RSI drops below 30, then we monitor the RSI every minute until it
#      starts to increase again.
#  - When the RSI begins to rise again we run tda-gobot.py to purchase and
#      monitor the stock performance.

import os, subprocess
import time, datetime, pytz, random
import argparse

import robin_stocks.tda as tda
import tulipy as ti
import numpy as np
import tda_gobot_helper

process_id = random.randint(1000, 9999) # Used to identify this process (i.e. for log_monitor)
loopt = 60

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=1000, type=float)
parser.add_argument("-m", "--multiday", help="Watch stock until decr_threshold is reached. Do not sell and exit when market closes", action="store_true")
parser.add_argument("-n", "--num_purchases", help="Number of purchases allowed per day", nargs='?', default=1, type=int)
parser.add_argument("-o", "--notmarketclosed", help="Cancel order and exit if US stock market is closed", action="store_true")
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()


debug = 1 # Should default to 0 eventually, testing for now
if args.debug:
	debug = 1

stock = args.stock
stock_usd = args.stock_usd
num_purchases = args.num_purchases

if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
        print('Canceled order to purchase $' + str(stock_usd) + ' of stock ' + str(stock) + ', because market is closed and --notmarketclosed was set')
        exit(1)


# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file')
        exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda = tda
tda_gobot_helper.tda_account_number = tda_account_number
tda_gobot_helper.passcode = passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure')
	exit(1)

# Fix up and sanity check the stock symbol before proceeding
stock = tda_gobot_helper.fix_stock_symbol(stock)
if ( tda_gobot_helper.check_stock_symbol(stock) != True ):
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
	exit(1)


# This bot has two modes of operation -
#   We start in the 'buy' mode where we are waiting for the right signal to purchase stock.
#   Then after purchasing stock we switch to the 'sell' mode where we begin searching
#   the signal to sell the stock.
signal_mode = 'buy'

# tda.get_price_history() variables
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone
p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

# RSI variables
rsiPeriod = 14
cur_rsi = 0
prev_rsi = 0
rsi_low_limit = 30
rsi_high_limit = 70


# Main Loop
while True:

	# TODO: Test during pre-market and trading day.
	#       Monitor any delay in market data and quality of the data

	# Helpful datetime conversion hints: convert epoch milisecond to string:
	#   start = int( datetime.datetime.strptime('2021-03-26 09:30:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=mytimezone).timestamp() * 1000 )
	#   datetime.datetime.fromtimestamp(<epoch>/1000).strftime('%Y-%m-%d %H:%M:%S.%f')
	#   datetime.datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
	time_now = datetime.datetime.strptime('2021-03-29 15:59:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=mytimezone)
#	time_now = datetime.datetime.now(mytimezone)
	time_prev = time_now - datetime.timedelta( minutes=int(freq)*(rsiPeriod * 10) ) # Subtract enough time to ensure we get an RSI for the current period
	time_now_epoch = int( time_now.timestamp() * 1000 )
	time_prev_epoch = int( time_prev.timestamp() * 1000 )

	# Debug stuff
	#print(time_now.strftime('%Y-%m-%d %H:%M:%S'))
	#print(time_prev.strftime('%Y-%m-%d %H:%M:%S'))
	#print(time_now_epoch)
	#print(time_prev_epoch)

	# Pull the data stock history to calculate the RSI
	data,closeprices,epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, debug=False)
	if ( data == False ):
		time.sleep(5)
		if ( tda_gobot_helper.tdalogin(passcode) != True ):
			print('Error: Login failure')
		continue

	# Get the RSI values
	rsi = tda_gobot_helper.get_rsi(closeprices, rsiPeriod, debug=False)
	if ( isinstance(rsi, bool) and rsi == False ):
		time.sleep(loopt)
		continue

	cur_rsi = rsi[-1]
	if ( prev_rsi == 0 ):
		prev_rsi = cur_rsi
	if ( debug == 1 ):
		print('(' + str(stock) + ') Current RSI: ' + str(round(cur_rsi, 2)) + ', Previous RSI: ' + str(round(prev_rsi, 2)))
		print('(' + str(stock) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
			', timestamp received from API ' +
			datetime.datetime.fromtimestamp(float(epochs[-1])/1000).strftime('%Y-%m-%d %H:%M:%S.%f') +
			' (' + str(int(epochs[-1])) + ')' )


	# BUY MODE - looking for a signal to purchase the stock
	if ( signal_mode == 'buy' ):

		# Exit if we've exhausted our maximum number of purchases for the day
		if ( num_purchases < 1 ):
			print('(' + str(stock) + ') Max number of purchases exhuasted, exiting.')
			exit(0)

		# End of trading day - exit
#		if ( tda_gobot_helper.isendofday() == True or tda_gobot_helper.ismarketopen_US() == False ):
#			print('(' + str(stock) + ') Market closed, exiting.')
#			exit(0)

		# Nothing to do if RSI hasn't dropped below rsi_low_limit (typically 30)
		if ( cur_rsi > rsi_low_limit and prev_rsi > rsi_low_limit ):
			if ( debug == 1 ):
				print('(' + str(stock) + ') RSI is above ' + str(rsi_low_limit) + ' (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

		# RSI is dropping and has hit rsi_low_limit (30)
		elif ( prev_rsi > rsi_low_limit and cur_rsi <= rsi_low_limit ):
			print('(' + str(stock) + ') RSI has dropped below ' + str(rsi_low_limit) + ' (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

		# Dropping RSI below rsi_low_limit (30)
		elif ( prev_rsi <= rsi_low_limit and cur_rsi < prev_rsi ):
			if ( debug == 1 ):
				print('(' + str(stock) + ') RSI below ' + str(rsi_low_limit) + ' and still dropping (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

		# RSI was below rsi_low_limit (30) and is now rising
		elif ( prev_rsi < rsi_low_limit and cur_rsi > prev_rsi ):
			if ( debug == 1 ):
				print('(' + str(stock) + ') RSI below ' + str(rsi_low_limit) + ' and is now rising (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

			# RSI crossed the rsi_low_limit threshold - this is the BUY signal
			if ( cur_rsi >= rsi_low_limit ):
				print('(' + str(stock) + ') BUY SIGNAL: RSI passed the low_limit threshold (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

				# Calculate stock quantity from investment amount
				last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
				if ( last_price == False ):
					print('Error: get_lastprice() returned False')
					time.sleep(5)

					# Try logging in and looping around again
					if ( tda_gobot_helper.tdalogin(passcode) != True ):
						print('Error: Login failure')

					continue

				stock_qty = int( float(stock_usd) / float(last_price) )

				# Purchase stock
				if ( tda_gobot_helper.ismarketopen_US() == True ):
					print('Purchasing ' + str(stock_qty) + ' shares of ' + str(stock))
					data = tda_gobot_helper.buy_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)
					if ( data == False ):
						print('Error: Unable to buy stock "' + str(ticker) + '"')
						exit(1)

				else:
					print('Error: stock ' + str(stock) + ' not purchased because market is closed, exiting.')
					exit(1)

				orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
				base_price = orig_base_price # Compat for now
				net_change = 0

				tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id)

				num_purchases -= 1
				signal_mode = 'sell' # Switch to 'sell' mode for the next loop


	# SELL MODE - looking for a signal to sell the stock
	elif ( signal_mode == 'sell' ):

		# In 'sell' mode we also want to monitor the stock price along with RSI
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
		if ( last_price == False ):
			print('Error: get_lastprice() returned False')

			# Try logging in and looping around again
			time.sleep(5)
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
				print('Error: Login failure')

			continue

		net_change = round( (last_price - orig_base_price) * stock_qty, 3 )
		tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id)

		# End of trading day - dump the stock and exit
		if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
			print('Market closing, selling stock ' + str(stock))
			data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, sold=True)
			print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
			exit(0)

		# Nothing to do if RSI hasn't dropped below rsi_high_limit (typically 70)
		if ( cur_rsi > rsi_high_limit and prev_rsi > rsi_high_limit ):
			if ( debug == 1 ):
				print('(' + str(stock) + ') RSI is above ' + str(rsi_high_limit) + ' (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

		# RSI is rising and has hit rsi_high_limit (70)
		elif ( prev_rsi < rsi_high_limit and cur_rsi >= rsi_high_limit ):
			print('(' + str(stock) + ') RSI has risen above ' + str(rsi_high_limit) + ' (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

		# RSI is above rsi_high_limit (70) and is now dropping
		elif ( prev_rsi > rsi_high_limit and cur_rsi < prev_rsi ):
			if ( debug == 1 ):
				print('(' + str(stock) + ') RSI above ' + str(rsi_high_limit) + ' and is now dropping (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

			# RSI crossed below the rsi_high_limit threshold - this is the SELL signal
			if ( cur_rsi <= rsi_high_limit ):
				print('(' + str(stock) + ') SELL SIGNAL: RSI passed below the high_limit threshold (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ') - selling the security')

				data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)
				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, sold=True)
				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

				signal_mode = 'buy'


	# Undefined mode - this shouldn't happen
	else:
		print('Error: undefined signal_mode: ' + str(signal_mode))


	print() # Make debug log easier to read
	prev_rsi = cur_rsi

	time.sleep(loopt)



exit(0)
