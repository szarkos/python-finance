#!/usr/bin/python3 -u

# Monitor a stock's RSI or Stochastic RSI values and make purchase decisions based off those values.
# Examples:
#  ./tda-rsi-gobot.py --algo=rsi --short --stoploss  MSFT 1000
#  ./tda-rsi-gobot.py --algo=stochrsi --short --multiday --stoploss --decr_threshold=1.5 \
#			--num_purchases=20 --max_failed_txs=2 --max_failed_usd=300 \
#			--rsi_high_limit=80 --rsi_low_limit=20 --rsi_period=128 --rsi_k_period=128 --rsi_d_period=3 --rsi_slow=6 \
#			MSFT  1000

import os, sys
import time, datetime, pytz, random
import argparse

import robin_stocks.tda as tda
import tulipy as ti
import tda_gobot_helper


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=1000, type=float)
parser.add_argument("-a", "--algo", help='Algorithm to use (rsi|stochrsi)', default='rsi', type=str)
parser.add_argument("-f", "--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("-w", "--fake", help='Paper trade only - disables buy/sell functions', action="store_true")

parser.add_argument("-m", "--multiday", help='Watch stock until decr_threshold is reached. Do not sell and exit when market closes', action="store_true")
parser.add_argument("-o", "--notmarketclosed", help='Cancel order and exit if US stock market is closed', action="store_true")
parser.add_argument("-i", "--incr_threshold", help='Reset base_price if stock increases by this percent', type=float)
parser.add_argument("-u", "--decr_threshold", help='Max allowed drop percentage of the stock price', type=float)
parser.add_argument("-n", "--num_purchases", help='Number of purchases allowed per day', nargs='?', default=4, type=int)
parser.add_argument("-s", "--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("-t", "--max_failed_txs", help='Maximum number of failed transactions allowed for a given stock before stock is blacklisted', default=2, type=int)
parser.add_argument("-x", "--max_failed_usd", help='Maximum allowed USD for a failed transaction before the stock is blacklisted', default=100, type=int)

parser.add_argument("-q", "--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("-k", "--rsi_k_period", help='k period to use in StochRSI algorithm', default=14, type=int)
parser.add_argument("-j", "--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("-c", "--stochrsi_period", help='RSI period to use for stochastic RSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("-p", "--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("-r", "--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='ohlc4', type=str)
parser.add_argument("-g", "--rsi_high_limit", help='RSI high limit', default=70, type=int)
parser.add_argument("-l", "--rsi_low_limit", help='RSI low limit', default=30, type=int)
parser.add_argument("-b", "--nocrossover", help='Modifies the algorithm so that k and d crossovers will not generate a signal (default=False)', action="store_true")

parser.add_argument("-y", "--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("-z", "--shortonly", help='Only short sell the stock', action="store_true")
parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
args = parser.parse_args()

debug = 1			# Should default to 0 eventually, testing for now
incr_percent_threshold = 1	# Reset base_price if stock increases by this percent
decr_percent_threshold = 2	# Max allowed drop percentage of the stock price

if args.debug:
	debug = 1
if args.decr_threshold:
        decr_percent_threshold = args.decr_threshold
if args.incr_threshold:
        incr_percent_threshold = args.incr_threshold

stock = args.stock
stock_usd = args.stock_usd
num_purchases = args.num_purchases
failed_txs = args.max_failed_txs
algo = str(args.algo).lower()
nocrossover = args.nocrossover


# Early exit criteria goes here
if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
	print('Canceled order to purchase $' + str(stock_usd) + ' of stock ' + str(stock) + ', because market is closed and --notmarketclosed was set')
	exit(1)

if ( tda_gobot_helper.check_blacklist(stock) == True and args.force == False ):
	print('(' + str(stock) + ') Error: stock ' + str(stock) + ' found in blacklist file, exiting.')
	exit(1)

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda = tda
tda_gobot_helper.tda_account_number = tda_account_number
tda_gobot_helper.passcode = passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure', file=sys.stderr)
	exit(1)

# Fix up and sanity check the stock symbol before proceeding
stock = tda_gobot_helper.fix_stock_symbol(stock)
if ( tda_gobot_helper.check_stock_symbol(stock) != True ):
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
	exit(1)

# Confirm that we can short this stock
if ( args.short == True or args.shortonly == True ):
	data,err = tda.stocks.get_quote(stock, True)
	if ( err != None ):
		print('Error: get_quote(' + str(stock) + '): ' + str(err), file=sys.stderr)

	if ( str(data[stock]['shortable']) == str(False) or str(data[stock]['marginable']) == str(False) ):
		if ( args.shortonly == True ):
			print('Error: stock(' + str(stock) + '): does not appear to be shortable, exiting.')
			exit(1)
		elif ( args.short == True ):
			args.short = False
			print('Warning: stock(' + str(stock) + '): does not appear to be shortable, disabling --short')


# tda.get_pricehistory() variables
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone
p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

# RSI variables
rsi_low_limit = args.rsi_low_limit
rsi_high_limit = args.rsi_high_limit
rsi_period = args.rsi_period
stochrsi_period = args.stochrsi_period
rsi_slow = args.rsi_slow
rsi_k_period = args.rsi_k_period
rsi_d_period = args.rsi_d_period
rsi_type = args.rsi_type

cur_rsi = prev_rsi = -1
cur_rsi_k = prev_rsi_k = -1
cur_rsi_d = prev_rsi_d = -1

rsi = stochrsi = []
rsi_k = rsi_d = []


# Main Loop
#
# This bot has four modes of operation -
#   Start in the 'buy' mode where we are waiting for the right signal to purchase stock.
#   Then after purchasing stock we switch to the 'sell' mode where we begin searching
#   the signal to sell the stock.
#
# Ideal signal mode workflow looks like this:
#   buy -> sell -> short -> buy_to_cover -> buy -> ...
#
#  RSI passes from below rsi_low_limit to above = BUY
#  RSI passes from above rsi_high_limit to below = SELL and SHORT
#  RSI passes from below rsi_low_limit to above = BUY_TO_COVER and BUY

tx_id = random.randint(1000, 9999) # Used to identify each buy/sell transaction
percent_change = 0
loopt = 60

buy_signal = False
sell_signal = False
short_signal = False
buy_to_cover_signal = False

# Start in 'buy' mode unless we're only shorting
signal_mode = 'buy'
if ( args.shortonly == True ):
	signal_mode = 'short'

while ( algo == 'rsi' ):

	# Loop continuously while after hours if --multiday was set
	# Trying to call the API or do anything below beyond post-market hours will result in an error
	if ( tda_gobot_helper.ismarketopen_US() == False ):
		if ( args.multiday == True ):
			prev_rsi = cur_rsi = 0
			time.sleep(loopt*5)
			continue

		else:
			print('(' + str(stock) + ') Market closed, exiting.')
			exit(0)

	# Check to see if we are near the beginning of a new trading day.
	# The intent of this variable is to tune the algorithm to be more sensitive
	#   to the typical volitility during the opening minutes of the trading day.
	newday = tda_gobot_helper.isnewday()

	# Helpful datetime conversion hints:
	#   start = int( datetime.datetime.strptime('2021-03-26 09:30:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=mytimezone).timestamp() * 1000 )
	#   datetime.datetime.fromtimestamp(<epoch>/1000).strftime('%Y-%m-%d %H:%M:%S.%f')
	#   datetime.datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')
	#   time_now = datetime.datetime.strptime('2021-03-29 15:59:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=mytimezone)
	time_now = datetime.datetime.now( mytimezone )
	time_prev = time_now - datetime.timedelta( minutes=int(freq)*(rsi_period * 20) ) # Subtract enough time to ensure we get an RSI for the current period
	time_now_epoch = int( time_now.timestamp() * 1000 )
	time_prev_epoch = int( time_prev.timestamp() * 1000 )

	# Log in - avoids failing later and we can call this as often as we want
	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure')
		time.sleep(5)
		continue

	# Pull the stock history that we'll use to calculate the RSI
	data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=True, debug=False)
	if ( data == False ):
		time.sleep(5)
		if ( tda_gobot_helper.tdalogin(passcode) != True ):
			print('Error: Login failure')
		continue

	# Get the RSI values
	rsi = tda_gobot_helper.get_rsi(data, rsi_period, rsi_type, debug=False)
	if ( isinstance(rsi, bool) and rsi == False ):
		time.sleep(loopt)
		continue

	cur_rsi = rsi[-1]
	if ( prev_rsi == -1 ):
		prev_rsi = cur_rsi
	if ( debug == 1 ):
		print('(' + str(stock) + ') RSI period: ' + str(rsi_period) + ' / RSI type: ' + str(rsi_type))
		print('(' + str(stock) + ') Current RSI: ' + str(round(cur_rsi, 2)) + ' / Previous RSI: ' + str(round(prev_rsi, 2)))
		print('(' + str(stock) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
			', timestamp received from API ' +
			datetime.datetime.fromtimestamp(float(epochs[-1])/1000).strftime('%Y-%m-%d %H:%M:%S.%f') +
			' (' + str(int(epochs[-1])) + ')' )

	# BUY MODE - looking for a signal to purchase the stock
	if ( signal_mode == 'buy' ):

		# Exit if we've exhausted our maximum number of failed transactions for this stock
		if ( failed_txs <= 0 ):
			print('(' + str(stock) + ') Max number of failed transactions reached (' + str(args.max_failed_txs) + '), exiting.')
			exit(0)

		# Exit if we've exhausted our maximum number of purchases for the day
		if ( num_purchases < 1 ):
			print('(' + str(stock) + ') Max number of purchases exhuasted, exiting.')
			exit(0)

		# Exit if end of trading day
		# If --multiday isn't set then we do not want to start trading if the market is closed.
		# Also if --multiday isn't set we should avoid buying any securities if it's within
		#  1-hour from market close. Otherwise we may be forced to sell too early.
		if ( (tda_gobot_helper.isendofday(60) == True or tda_gobot_helper.ismarketopen_US() == False) and args.multiday == False ):
			print('(' + str(stock) + ') Market closed, exiting.')
			exit(0)

		# Switch to short mode if RSI is already above rsi_high_limit
		# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
		#  does a full loop again before acting on it.
		if ( cur_rsi > rsi_high_limit and args.short == True ):
			print('(' + str(stock) + ') RSI is already above ' + str(rsi_high_limit) + ', switching to short mode.')
			signal_mode = 'short'
			continue

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
					if ( args.fake == False ):
						data = tda_gobot_helper.buy_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)
						if ( data == False ):
							print('Error: Unable to buy stock "' + str(stock) + '"', file=sys.stderr)
							exit(1)
					try:
						orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						orig_base_price = last_price

				else:
					print('Stock ' + str(stock) + ' not purchased because market is closed, exiting.')
					exit(1)

				base_price = orig_base_price
				net_change = 0

				tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)

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

		# End of trading day - dump the stock and exit unless --multiday was set
		if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
			print('Market closing, selling stock ' + str(stock))
			if ( args.fake == False ):
				data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, sold=True)
			print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

			# Add to blacklist if sold at a loss greater than max_failed_usd
			if ( net_change < 0 and abs(net_change) > args.max_failed_usd ):
				tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

			exit(0)


		# STOPLOSS MONITOR
		# If price decreases
		if ( float(last_price) < float(base_price) ):
			percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100
			if ( debug == 1 ):
				print('Stock "' +  str(stock) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)

			# SELL the security if we are using a trailing stoploss
			if ( percent_change >= decr_percent_threshold and args.stoploss == True ):

				print('Stock ' + str(stock) + '" dropped below the decr_percent_threshold (' + str(decr_percent_threshold) + '%), selling the security...')
				if ( args.fake == False ):
					data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, sold=True)
				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

				# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
				if ( net_change < 0 ):
					failed_txs -= 1
					if ( abs(net_change) > args.max_failed_usd or failed_txs == 0 ):
						tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

				# Change signal to 'buy' and generate new tx_id for next iteration
				tx_id = random.randint(1000, 9999)
				prev_rsi = cur_rsi = -1
				signal_mode = 'buy'
				continue

		# If price increases
		elif ( float(last_price) > float(base_price) ):
			percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100
			if ( debug == 1 ):
				print('Stock "' +  str(stock) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

			# Re-set the base_price to the last_price if we increase by incr_percent_threshold or more
			# This way we can continue to ride a price increase until it starts dropping
			if ( percent_change >= incr_percent_threshold ):
				base_price = last_price
				print('Stock "' + str(stock) + '" increased above the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to '  + str(base_price))

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)

		# No price change
		else:
			tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)


		# RSI MONITOR
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

			# Check if RSI crossed below the rsi_high_limit threshold - this is the SELL signal
			#
			# At this point we know the RSI is dropping from a high above rsi_high_limit (i.e. 70).
			#   We will always sell if the RSI drops below the rsi_high_limit, but if newday=True then
			#   we take a more conservative approach and sell as soon as it start dropping.
			if ( cur_rsi <= rsi_high_limit or newday == True ):
				print('(' + str(stock) + ') SELL SIGNAL: RSI passed below the high_limit threshold (' +
					str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ' / newday=' + str(newday) +
					') - selling the security')

				if ( args.fake == False ):
					data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, sold=True)
				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

				# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
				if ( net_change < 0 ):
					failed_txs -= 1
					if ( abs(net_change) > args.max_failed_usd or failed_txs == 0 ):
						tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

				# Change signal to 'buy' or 'short' and generate new tx_id for next iteration
				tx_id = random.randint(1000, 9999)
				if ( args.short == True ):
					signal_mode = 'short'
					time.sleep(1)
					continue
				else:
					signal_mode = 'buy'


	# SHORT SELL the stock
	# In this mode we will monitor the RSI and initiate a short sale if the RSI is very high
	elif ( signal_mode == 'short' ):

		# Exit if end of trading day
		# If --multiday isn't set then we do not want to start trading if the market is closed.
		# Also if --multiday isn't set we should avoid buying any securities if it's within
		#  1-hour from market close.
		if ( (tda_gobot_helper.isendofday(60) == True or tda_gobot_helper.ismarketopen_US() == False) and args.multiday == False ):
			signal_mode = 'buy'
			continue

		if ( prev_rsi > rsi_high_limit and cur_rsi < prev_rsi ):
			if ( cur_rsi <= rsi_high_limit ):
				print('(' + str(stock) + ') SHORT SIGNAL: RSI passed below the high_limit threshold (' +
					str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ' / newday=' + str(newday) +
					') - shorting the security')

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
				if ( args.fake == False ):
					data = tda_gobot_helper.short_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)
					if ( data == False ):
						if ( args.shortonly == True ):
							print('Error: Unable to short "' + str(stock) + '" - exiting.', file=sys.stderr)
							exit(1)
						elif ( args.short == True ):
							print('Error: Unable to short "' + str(stock) + '" - disabling shorting', file=sys.stderr)
							args.short = False
							signal_mode = 'buy'
							time.sleep(1)
							continue
					try:
						orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
					except:
						orig_base_price = last_price

				else:
					orig_base_price = last_price

				net_change = 0
				base_price = orig_base_price
				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=False)

				signal_mode = 'buy_to_cover'


	# BUY_TO_COVER a previous short sale
	# This mode must always follow a previous "short" signal. We will monitor the RSI and initiate
	#   a buy-to-cover transaction to cover a previous short sale if the RSI if very low. We also
	#   need to monitor stoploss in case the stock rises above a threshold.
	elif ( signal_mode == 'buy_to_cover' ):

		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
		if ( last_price == False ):
			print('Error: get_lastprice() returned False')

			# Try logging in and looping around again
			time.sleep(5)
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
				print('Error: Login failure')

			continue

		net_change = round( (last_price - orig_base_price) * stock_qty, 3 )

		# End of trading day - cover the shorted stock unless --multiday was set
		if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
			print('Market closing, covering shorted stock ' + str(stock))
			if ( args.fake == False ):
				data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=True)
			signal_mode = 'buy'


		# STOPLOSS MONITOR
		# If price decreases
		if ( float(last_price) < float(base_price) ):
			percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, short=True, proc_id=tx_id)

			# Re-set the base_price to the last_price if we increase by incr_percent_threshold or more
			# This way we can continue to ride a price increase until it starts dropping
			if ( percent_change >= incr_percent_threshold ):
				base_price = last_price

				print('SHORTED Stock "' + str(stock) + '" decreased below the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to '  + str(base_price))
				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

		# If price increases
		elif ( float(last_price) > float(base_price) ):
			percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

			# BUY-TO-COVER the security if we are using a trailing stoploss
			if ( percent_change >= decr_percent_threshold and args.stoploss == True ):

				print('SHORTED Stock "' + str(stock) + '" increased above the decr_percent_threshold (' + str(decr_percent_threshold) + '%), covering shorted stock...')
				if ( args.fake == False ):
					data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=True)

				# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
				if ( net_change > 0 ):
					failed_txs -= 1
					if ( abs(net_change) > args.max_failed_usd or failed_txs == 0 ):
						tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

				# Change signal to 'buy' and generate new tx_id for next iteration
				tx_id = random.randint(1000, 9999)
				if ( args.shortonly == True ):
					signal_mode = 'short'
				else:
					signal_mode = 'buy'
					time.sleep(1)
					continue

		# No price change
		else:
			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True)


		# RSI MONITOR
		# RSI is rising toward the rsi_low_limit
		if ( prev_rsi < rsi_low_limit and cur_rsi > prev_rsi ):

			# RSI crossed the rsi_low_limit threshold - this is the BUY_TO_COVER signal
			if ( cur_rsi >= rsi_low_limit ):
				print('(' + str(stock) + ') BUY_TO_COVER SIGNAL: RSI passed the low_limit threshold (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

				if ( args.fake == False ):
					data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=True)

				# Change signal to 'buy' and generate new tx_id for next iteration
				tx_id = random.randint(1000, 9999)
				if ( args.shortonly == True ):
					signal_mode = 'short'
				else:
					signal_mode = 'buy'
					time.sleep(1)
					continue


	# Undefined mode - this shouldn't happen
	else:
		print('Error: undefined signal_mode: ' + str(signal_mode))


	print() # Make debug log easier to read
	prev_rsi = cur_rsi

	time.sleep(loopt)

# End algo=rsi loop


##############################################################################################################


# StochRSI Algorithm
while ( algo == 'stochrsi' ):

	# Loop continuously while after hours if --multiday was set
	# Trying to call the API or do anything below beyond post-market hours will result in an error
	if ( tda_gobot_helper.ismarketopen_US() == False ):
		if ( args.multiday == True ):
			prev_rsi_k = cur_rsi_k = -1
			prev_rsi_d = cur_rsi_d = -1
			time.sleep(loopt*5)
			continue

		else:
			print('(' + str(stock) + ') Market closed, exiting.')
			exit(0)

	# Check to see if we are near the beginning of a new trading day.
	# The intent of this variable is to tune the algorithm to be more sensitive
	#   to the typical volitility during the opening minutes of the trading day.
	newday = tda_gobot_helper.isnewday()
	time_now = datetime.datetime.now( mytimezone )
	time_prev = time_now - datetime.timedelta( minutes=int(freq)*(rsi_period * 10) ) # Subtract enough time to ensure we get an RSI for the current period
	time_now_epoch = int( time_now.timestamp() * 1000 )
	time_prev_epoch = int( time_prev.timestamp() * 1000 )

	# Log in - avoids failing later and we can call this as often as we want
	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure')
		time.sleep(5)
		continue

	# Pull the stock history that we'll use to calculate the Stochastic RSI
	data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=True, debug=False)
	if ( data == False ):
		time.sleep(5)
		if ( tda_gobot_helper.tdalogin(passcode) != True ):
			print('Error: Login failure')

		continue

	# Get stochactic RSI
	stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(data, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)
	if ( isinstance(stochrsi, bool) and stochrsi == False ):
		print('Error: get_stochrsi(' + str(stock) + ') returned false - no data', file=sys.stderr)
		time.sleep(loopt)
		continue

	# If using the same 1-minute data, the len of stochrsi will be stochrsi_period * (stochrsi_period * 2) - 1
	if ( len(stochrsi) != len(data['candles']) - (stochrsi_period * 2 - 1) ):
		print('Warning, unexpected length of stochrsi (data[candles]=' + str(len(data['candles'])) + ', len(stochrsi)=' + str(len(stochrsi)) + ')')

	cur_rsi_k = rsi_k[-1]
	cur_rsi_d = rsi_d[-1]
	if ( prev_rsi_k == -1 or prev_rsi_d == -1):
		prev_rsi_k = cur_rsi_k
		prev_rsi_d = cur_rsi_d

	if ( debug == 1 ):
		print(  '(' + str(stock) + ') StochRSI period: ' + str(rsi_period) + ' / StochRSI type: ' + str(rsi_type) +
			' / StochRSI K period: ' + str(rsi_k_period) + ' / StochRSI D period: ' + str(rsi_d_period) + ' / StochRSI slow period: ' + str(rsi_slow) )
		print('(' + str(stock) + ') Current StochRSI K: ' + str(round(cur_rsi_k, 2)) + ' / Previous StochRSI K: ' + str(round(prev_rsi_k, 2)))
		print('(' + str(stock) + ') Current StochRSI D: ' + str(round(cur_rsi_d, 2)) + ' / Previous StochRSI D: ' + str(round(prev_rsi_d, 2)))
		print('(' + str(stock) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
			', timestamp received from API ' +
			datetime.datetime.fromtimestamp(float(epochs[-1])/1000).strftime('%Y-%m-%d %H:%M:%S.%f') +
			' (' + str(int(epochs[-1])) + ')' )

	# BUY MODE - looking for a signal to purchase the stock
	if ( signal_mode == 'buy' ):

		# Exit if we've exhausted our maximum number of failed transactions for this stock
		if ( failed_txs <= 0 ):
			print('(' + str(stock) + ') Max number of failed transactions reached (' + str(args.max_failed_txs) + '), exiting.')
			exit(0)

		# Exit if we've exhausted our maximum number of purchases for the day
		if ( num_purchases < 1 ):
			print('(' + str(stock) + ') Max number of purchases exhuasted, exiting.')
			exit(0)

		# Exit if end of trading day
		# If --multiday isn't set then we do not want to start trading if the market is closed.
		# Also if --multiday isn't set we should avoid buying any securities if it's within
		#  1-hour from market close. Otherwise we may be forced to sell too early.
		if ( (tda_gobot_helper.isendofday(60) == True or tda_gobot_helper.ismarketopen_US() == False) and args.multiday == False ):
			print('(' + str(stock) + ') Market closed, exiting.')
			exit(0)

		# Jump to short mode if StochRSI K and D are already above rsi_high_limit
		# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
		#  does a full loop again before acting on it.
		if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit and args.short == True ):
			print('(' + str(stock) + ') StochRSI K and D values already above ' + str(rsi_high_limit) + ', switching to short mode.')

			buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
			signal_mode = 'short'
			continue

		# Monitor K and D
		# A buy signal occurs when an increasing %K line crosses above the %D line in the oversold region,
		#  or if the %K line crosses above the rsi limit
		if ( (cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit) and nocrossover == False ):
			if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
				print(  '(' + str(stock) + ') BUY SIGNAL: StochRSI K value passed above the D value in the low_limit region (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				buy_signal = True

		elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
			if ( cur_rsi_k >= rsi_low_limit ):
				print(  '(' + str(stock) + ') BUY SIGNAL: StochRSI K value passed above the low_limit threshold (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				buy_signal = True

		# BUY
		if ( buy_signal == True ):

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
				if ( args.fake == False ):
					data = tda_gobot_helper.buy_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)
					if ( data == False ):
						print('Error: Unable to buy stock "' + str(stock) + '"', file=sys.stderr)
						exit(1)
				try:
					orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
				except:
					orig_base_price = last_price

			else:
				print('Stock ' + str(stock) + ' not purchased because market is closed, exiting.')
				exit(1)

			num_purchases -= 1

			base_price = orig_base_price
			net_change = 0

			tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)

			nocrossover = args.nocrossover # Reset in case we stoplossed earlier

			buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
			signal_mode = 'sell' # Switch to 'sell' mode for the next loop


	# SELL MODE - looking for a signal to sell the stock
	elif ( signal_mode == 'sell' ):

		# In 'sell' mode we want to monitor the stock price along with RSI
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
		if ( last_price == False ):
			print('Error: get_lastprice() returned False')

			# Try logging in and looping around again
			time.sleep(5)
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
				print('Error: Login failure')

			continue

		net_change = round( (last_price - orig_base_price) * stock_qty, 3 )

		# End of trading day - dump the stock and exit unless --multiday was set
		if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
			print('Market closing, selling stock ' + str(stock))
			if ( args.fake == False ):
				data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, sold=True)
			print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

			# Add to blacklist if sold at a loss greater than max_failed_usd
			if ( net_change < 0 and abs(net_change) > args.max_failed_usd ):
				tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

			exit(0)


		# STOPLOSS MONITOR
		# If price decreases
		if ( float(last_price) < float(base_price) ):
			percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100
			if ( debug == 1 ):
				print('Stock "' +  str(stock) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)

			# SELL the security if we are using a trailing stoploss
			if ( percent_change >= decr_percent_threshold and args.stoploss == True ):

				print('Stock ' + str(stock) + '" dropped below the decr_percent_threshold (' + str(decr_percent_threshold) + '%), selling the security...')
				if ( args.fake == False ):
					data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, sold=True)
				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

				# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
				if ( net_change < 0 ):
					failed_txs -= 1
					if ( abs(net_change) > args.max_failed_usd or failed_txs == 0 ):
						tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

				# Change signal to 'buy' and generate new tx_id for next iteration
				tx_id = random.randint(1000, 9999)
				prev_rsi_k = cur_rsi_k = -1
				prev_rsi_d = cur_rsi_d = -1

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
				signal_mode = 'buy'

				nocrossover = True # Stock is dipping, disable crossover for this next cycle

				continue

		# If price increases
		elif ( float(last_price) > float(base_price) ):
			percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100
			if ( debug == 1 ):
				print('Stock "' +  str(stock) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

			# Re-set the base_price to the last_price if we increase by incr_percent_threshold or more
			# This way we can continue to ride a price increase until it starts dropping
			if ( percent_change >= incr_percent_threshold ):
				base_price = last_price
				print('Stock "' + str(stock) + '" increased above the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to '  + str(base_price))

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)

		# No price change
		else:
			tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id)


		# StochRSI MONITOR
		# Monitor K and D
		# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region,
		#  or if the %K line crosses below the RSI limit
		if ( (cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit) and nocrossover == False ):
			if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
				print(  '(' + str(stock) + ') SELL SIGNAL: StochRSI K value passed below the D value in the high_limit region (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				sell_signal = True

		elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
			if ( cur_rsi_k <= rsi_high_limit ):
				print(  '(' + str(stock) + ') SELL SIGNAL: StochRSI K value passed below the high_limit threshold (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				sell_signal = True

		# SELL
		if ( sell_signal == True ):

			if ( args.fake == False ):
				data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, sold=True)
			print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

			# Add to blacklist if sold at a loss greater than max_failed_usd, or if we've exceeded failed_txs
			if ( net_change < 0 ):
				failed_txs -= 1
				if ( abs(net_change) > args.max_failed_usd or failed_txs == 0 ):
					tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

			# Change signal to 'buy' or 'short' and generate new tx_id for next iteration
			tx_id = random.randint(1000, 9999)
			buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
			if ( args.short == True ):
				short_signal = True
				signal_mode = 'short'
				time.sleep(1)
				continue
			else:
				signal_mode = 'buy'


	# SHORT SELL the stock
	# In this mode we will monitor the RSI and initiate a short sale if the RSI is very high
	elif ( signal_mode == 'short' ):

		# Exit if end of trading day
		# If --multiday isn't set then we do not want to start trading if the market is closed.
		# Also if --multiday isn't set we should avoid buying any securities if it's within
		#  1-hour from market close.
		if ( (tda_gobot_helper.isendofday(60) == True or tda_gobot_helper.ismarketopen_US() == False) and args.multiday == False ):
			buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
			signal_mode = 'buy'
			continue

		# Monitor K and D
		if ( (cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit) and nocrossover == False ):
			if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
				print(  '(' + str(stock) + ') SHORT SIGNAL: StochRSI K value passed below the D value in the high_limit region (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				short_signal = True

		elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
			if ( cur_rsi_k <= rsi_high_limit ):
				print(  '(' + str(stock) + ') SHORT SIGNAL: StochRSI K value passed below the high_limit threshold (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				short_signal = True

		# SHORT
		if ( short_signal == True ):

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
			if ( args.fake == False ):
				data = tda_gobot_helper.short_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

				if ( data == False ):
					if ( args.shortonly == True ):
						print('Error: Unable to short "' + str(stock) + '" - exiting.', file=sys.stderr)
						exit(1)

					elif ( args.short == True ):
						print('Error: Unable to short "' + str(stock) + '" - disabling shorting', file=sys.stderr)
						args.short = False
						signal_mode = 'buy'
						time.sleep(1)
						continue

				try:
					orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
				except:
					orig_base_price = last_price

			else:
				orig_base_price = last_price

			num_purchases -= 1

			net_change = 0
			base_price = orig_base_price

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=False)

			nocrossover = args.nocrossover # Reset in case we stoplossed earlier

			buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
			signal_mode = 'buy_to_cover'


	# BUY_TO_COVER a previous short sale
	# This mode must always follow a previous "short" signal. We will monitor the RSI and initiate
	#   a buy-to-cover transaction to cover a previous short sale if the RSI if very low. We also
	#   need to monitor stoploss in case the stock rises above a threshold.
	elif ( signal_mode == 'buy_to_cover' ):

		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
		if ( last_price == False ):
			print('Error: get_lastprice() returned False')

			# Try logging in and looping around again
			time.sleep(5)
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
				print('Error: Login failure')

			continue

		net_change = round( (last_price - orig_base_price) * stock_qty, 3 )

		# End of trading day - cover the shorted stock unless --multiday was set
		if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
			print('Market closing, covering shorted stock ' + str(stock))
			if ( args.fake == False ):
				data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=True)

			# Add to blacklist if sold at a loss greater than max_failed_usd
			if ( net_change > 0 and abs(net_change) > args.max_failed_usd ):
				tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

			exit(0)


		# STOPLOSS MONITOR
		# If price decreases
		if ( float(last_price) < float(base_price) ):
			percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, short=True, proc_id=tx_id)

			# Re-set the base_price to the last_price if we increase by incr_percent_threshold or more
			# This way we can continue to ride a price increase until it starts dropping
			if ( percent_change >= incr_percent_threshold ):
				base_price = last_price

				print('SHORTED Stock "' + str(stock) + '" decreased below the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to '  + str(base_price))
				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')

		# If price increases
		elif ( float(last_price) > float(base_price) ):
			percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

			# BUY-TO-COVER the security if we are using a trailing stoploss
			if ( percent_change >= decr_percent_threshold and args.stoploss == True ):

				print('SHORTED Stock "' + str(stock) + '" increased above the decr_percent_threshold (' + str(decr_percent_threshold) + '%), covering shorted stock...')
				if ( args.fake == False ):
					data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=True)

				# Add to blacklist when sold at a loss greater than max_failed_usd, or if we've exceeded failed_tx
				if ( net_change > 0 ):
					failed_txs -= 1
					if ( abs(net_change) > args.max_failed_usd or failed_txs == 0 ):
						tda_gobot_helper.write_blacklist(stock, stock_qty, orig_base_price, last_price, net_change, percent_change)

				# Change signal to 'buy' and generate new tx_id for next iteration
				tx_id = random.randint(1000, 9999)
				prev_rsi_k = cur_rsi_k = -1
				prev_rsi_d = cur_rsi_d = -1

				buy_signal = sell_signal = short_signal = buy_to_cover_signal = False

				nocrossover = True # Stock is rising, disable crossover for this next cycle

				if ( args.shortonly == True ):
					signal_mode = 'short'
				else:
					signal_mode = 'buy'
					time.sleep(1)
					continue

		# No price change
		else:
			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True)


		# RSI MONITOR
		# Monitor K and D
		if ( (cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit) and nocrossover == False ):
			if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
				print(  '(' + str(stock) + ') BUY_TO_COVER SIGNAL: StochRSI K value passed above the D value in the low_limit region (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				buy_to_cover_signal = True

		elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
			if ( cur_rsi_k >= rsi_low_limit ):
				print(  '(' + str(stock) + ') BUY_TO_COVER SIGNAL: StochRSI K value passed above the low_limit threshold (' +
					str(round(prev_rsi_k, 2)) + ' / ' + str(round(cur_rsi_k, 2)) + ' / ' + str(round(prev_rsi_d, 2)) + ' / ' + str(round(cur_rsi_d, 2)) + ')' )

				buy_to_cover_signal = True

		# BUY-TO-COVER
		if ( buy_to_cover_signal == True ):
			if ( args.fake == False ):
				data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=tx_id, short=True, sold=True)

			# Change signal to 'buy' and generate new tx_id for next iteration
			buy_signal = sell_signal = short_signal = buy_to_cover_signal = False
			tx_id = random.randint(1000, 9999)
			if ( args.shortonly == True ):
				signal_mode = 'short'

			else:
				buy_signal = True
				signal_mode = 'buy'
				time.sleep(1)
				continue


	# Undefined mode - this shouldn't happen
	else:
		print('Error: undefined signal_mode: ' + str(signal_mode))


	print() # Make debug log easier to read
	prev_rsi_k = cur_rsi_k
	prev_rsi_d = cur_rsi_d

	time.sleep(loopt)


# End algo=stochrsi loop


exit(0)
