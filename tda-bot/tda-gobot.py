#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-gobot.py <ticker> <investment-in-usd> [--short] [--multiday]

# The goal of this bot is to purchase or short some shares and ride it until the price
# drops below (or above, for shorting) some % threshold, then sell the shares immediately.

import robin_stocks.tda as tda
import os, sys, time, random
import argparse
import datetime, pytz
import tda_gobot_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=None, type=float)
parser.add_argument("--account_number", help='Account number to use (default: None)', default=None, type=int)

parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS-GOBOTv1', default='TX_LOGS-GOBOTv1', type=str)

parser.add_argument("--incr_threshold", help="Reset base_price if stock increases by this percent", default=1, type=float)
parser.add_argument("--decr_threshold", help="Max allowed drop percentage of the stock price", default=1, type=float)
parser.add_argument("--entry_price", help="The price to enter a trade", default=None, type=float)
parser.add_argument("--exit_price", help="The price to exit a trade", default=None, type=float)

parser.add_argument("--exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)
parser.add_argument("--quick_exit", help='Exit immediately if an exit_percent strategy was set, do not wait for the next candle', action="store_true")
parser.add_argument("--use_combined_exit", help='Use both the ttm_trend algorithm and Heikin Ashi candles with exit_percent-based exit strategy', action="store_true")

parser.add_argument("--multiday", help="Watch stock until decr_threshold is reached. Do not sell and exit when market closes", action="store_true")
parser.add_argument("--notmarketclosed", help="Cancel order and exit if US stock market is closed", action="store_true")
parser.add_argument("--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

debug = True			# Should default to 0 eventually, testing for now
if args.debug == True:
	debug = True
if args.decr_threshold:
	decr_percent_threshold = args.decr_threshold	# Max allowed drop percentage of the stock price
if args.incr_threshold:
	incr_percent_threshold = args.incr_threshold	# Reset base_price if stock increases by this percent
if ( args.stock_usd == None ):
	print('Error: please enter stock amount (USD) to invest')
	sys.exit(1)

stock				= args.stock
stock_usd			= args.stock_usd
tx_log_dir			= args.tx_log_dir

process_id			= random.randint(1000, 9999)	# Used to identify this process (i.e. for log_monitor)
loopt				= 3				# Period between stock get_lastprice() checks

exit_percent_signal		= False
exit_signal			= False

mytimezone			= pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone	= mytimezone


# Do not proceed if market is closed and args.notmarketclosed is set
# Currently this won't matter much as TDA requires limit orders for all extended hours trading
if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
	print('Canceled order to purchase $' + str(stock_usd) + ' of stock ' + str(stock) + ', because market is closed and --notmarketclosed was set')
	sys.exit(1)

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file')
	sys.exit(1)

try:
	if ( args.account_number != None ):
		tda_account_number = args.account_number
	else:
		tda_account_number = int( os.environ["tda_account_number"] )

except:
	print('Error: account number not found, exiting.')
	sys.exit(1)

passcode				= os.environ["tda_encryption_passcode"]
tda_gobot_helper.tda			= tda
tda_gobot_helper.tda_account_number	= tda_account_number
tda_gobot_helper.passcode 		= passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure')
	sys.exit(1)

# Fix up and sanity check the stock symbol before proceeding
stock	= tda_gobot_helper.fix_stock_symbol(stock)
ret	= tda_gobot_helper.check_stock_symbol(stock)
if ( isinstance(ret, bool) and ret == False ):
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
	sys.exit(1)

if ( tda_gobot_helper.check_blacklist(stock) == True ):
	if ( args.force == False ):
		print('(' + str(stock) + ') Error: stock ' + str(stock) + ' found in blacklist file, exiting.')
		sys.exit(1)
	else:
		print('(' + str(stock) + ') Warning: stock ' + str(stock) + ' found in blacklist file.')


#############################################################
# Functions we may need later
def get_ph(stock=None):

	# tda.get_pricehistory() variables
	p_type		= 'day'
	period		= None
	f_type		= 'minute'
	freq		= '1'

	# Make sure start and end dates don't land on a weekend
	#  or outside market hours
	time_now	= datetime.datetime.now( mytimezone )
	time_prev	= time_now - datetime.timedelta( days=1 )

	#time_now	= tda_gobot_helper.fix_timestamp(time_now)
	time_prev	= tda_gobot_helper.fix_timestamp(time_prev)

	time_now_epoch	= int( time_now.timestamp() * 1000 )
	time_prev_epoch	= int( time_prev.timestamp() * 1000 )

	# Pull the stock history - all we really need is the latest candle, but this is
	#  the only way I know how to get it...
	ph, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period, time_prev_epoch, time_now_epoch, needExtendedHoursData=True, debug=False)
	if ( isinstance(ph, bool) and ph == False ):
		return False

	return ph


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

## End sub functions


# Loop until the entry price is acheived.
if ( args.entry_price != None ):

	while True:
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
		print('(' + str(stock) + '): entry_price=' + str(args.entry_price) + ', last_price=' + str(last_price))

		if ( args.short == True ):
			if ( last_price >= args.entry_price ): # Need to be careful with this one
				break

		else:
			if ( last_price <= args.entry_price ):
				break

		time.sleep(loopt)

else:
	last_price = tda_gobot_helper.get_lastprice( stock, WarnDelayed=False )


# Calculate stock quantity from investment amount
stock_qty = int( stock_usd / last_price )

# Purchase stock, set orig_base_price to the price that we purchases the stock
if ( tda_gobot_helper.ismarketopen_US() == True ):
	if ( args.short == True ):
		print('SHORTING ' + str(stock_qty) + ' shares of ' + str(stock))

		if ( args.fake == False ):
			data = tda_gobot_helper.short_stock_marketprice(stock, stock_qty, fillwait=True, account_number=tda_account_number, debug=debug)
			if ( isinstance(data, bool) and data == False ):
				print('Error: Unable to short "' + str(stock) + '"', file=sys.stderr)
				sys.exit(1)

	else:
		print('PURCHASING ' + str(stock_qty) + ' shares of ' + str(stock))
		if ( args.fake == False ):
			data = tda_gobot_helper.buy_stock_marketprice(stock, stock_qty, fillwait=True, account_number=tda_account_number, debug=debug)
			if ( isinstance(data, bool) and data == False ):
				print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
				sys.exit(1)

else:
	print('Error: stock ' + str(stock) + ' not purchased because market is closed, exiting.')
	sys.exit(1)

try:
	orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
except:
	orig_base_price = last_price

base_price	= orig_base_price
percent_change	= 0


# Main loop
while True:

	last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=True)
	if ( isinstance(last_price, bool) and last_price == False ):
		print('Error: get_lastprice() returned False')
		time.sleep(5)

		# Try logging in again
		if ( tda_gobot_helper.tdalogin(passcode) != True ):
			print('Error: Login failure')

		continue

	# Using last_price for now to approximate gain/loss
	net_change		= round( (last_price - orig_base_price) * stock_qty, 3 )
	total_percent_change	= abs( last_price / orig_base_price - 1 ) * 100
	percent_change		= abs( last_price / base_price - 1 ) * 100

	if ( debug == True ):
		red		= '\033[0;31m'
		green		= '\033[0;32m'
		reset_color	= '\033[0m'

		text_color	= green
		if ( args.short == False and last_price < orig_base_price or
			args.short == True and last_price > orig_base_price ):
				text_color		= red
				total_percent_change	= -total_percent_change

		print('(' +  str(stock) + '): Total Change: ' + str(text_color) + str(round(total_percent_change, 2)) + '% (' + str(last_price) + ')' + str(reset_color))

	# Log format - stock:%change:last_price:net_change:base_price:orig_base_price:stock_qty:proc_id:short
	tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short)


	# Log the post/pre market pricing, but skip the rest of the loop if the market is closed.
	# This should only happen if args.multiday == True
	if ( tda_gobot_helper.ismarketopen_US() == False ):
		time.sleep(loopt * 6)
		continue

	# Sell the security if we're getting close to market close
	if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
		print('Market closing, selling stock ' + str(stock))
		exit_signal = True

	# If exit_price was set
	if ( args.exit_price != None and exit_signal == False ):
		percent_change = abs( last_price / base_price - 1 ) * 100

		if ( args.short == True ):
			if ( last_price <= args.exit_price ):
				print('BUY_TO_COVER stock ' + str(stock) + '" - the last_price (' + str(last_price) + ') crossed the exit_price(' + str(args.exit_price) + ')')
				exit_signal = True

		else:
			if ( last_price >= args.exit_price ):
				print('SELLING stock ' + str(stock) + '" - the last_price (' + str(last_price) + ') crossed the exit_price(' + str(args.exit_price) + ')')
				exit_signal = True

	# Stoploss Monitor
	# Monitor negative movement in price, unless exit_percent_signal has been triggered
	#
	# If price decreases
	if ( last_price < base_price and exit_percent_signal == False and exit_signal == False ):
		if ( args.short == True ):
			if ( percent_change >= incr_percent_threshold ):
				base_price = last_price
				if ( debug == True ):
					print('SHORTED Stock "' + str(stock) + '" decreased below the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to ' + str(base_price))

				if ( decr_percent_threshold == args.decr_threshold ):
					decr_percent_threshold = incr_percent_threshold / 2

		elif ( percent_change >= decr_percent_threshold ):
			# Sell the security
			print('SELLING stock ' + str(stock) + '" - the security moved below the decr_percent_threshold (' + str(decr_percent_threshold) + '%)')
			exit_signal = True

	# If price increases
	elif ( last_price > base_price and exit_percent_signal == False and exit_signal == False ):

		if ( args.short == True ):
			if ( percent_change >= decr_percent_threshold ):
				# Buy-to-cover the security
				print('BUY_TO_COVER stock ' + str(stock) + '" - the security moved above the decr_percent_threshold (' + str(decr_percent_threshold) + '%)')
				exit_signal = True

		elif ( percent_change >= incr_percent_threshold ):

			# Re-set the base_price to the last_price if we increase by incr_percent_threshold or more
			# This way we can continue to ride a price increase until it starts dropping
			base_price = last_price
			if ( debug == True ):
				print('Stock "' + str(stock) + '" increased above the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to ' + str(base_price))

			if ( decr_percent_threshold == args.decr_threshold ):
				decr_percent_threshold = incr_percent_threshold / 2


	# Additional exit strategies
	if ( args.exit_percent != None and exit_signal == False ):
		if ( exit_percent_signal == False ):

			# LONG
			if ( args.short == False and last_price > orig_base_price ):
				total_percent_change = abs( orig_base_price / last_price - 1 ) * 100
				if ( total_percent_change >= args.exit_percent ):
					if ( args.quick_exit == True ):
						exit_signal = True

					else:
						exit_percent_signal = True
						if ( debug == True ):
							print('(' + str(stock) + '): exit_percent_signal triggered')

						time.sleep(loopt)
						continue

			# SHORT
			elif ( args.short == True and last_price < orig_base_price ):
				total_percent_change = abs( last_price / orig_base_price - 1 ) * 100
				if ( total_percent_change >= args.exit_percent ):
					if ( args.quick_exit == True ):
						exit_signal = True

					else:
						exit_percent_signal = True
						if ( debug == True ):
							print('(' + str(stock) + '): exit_percent_signal triggered')

						time.sleep(loopt)
						continue

		# Once exit_percent_signal is triggered we need to move to use candles so we can analyze
		#  price movement.
		elif ( exit_percent_signal == True and exit_signal == False ):

			loopt		= 30

			pricehistory	= {}
			pricehistory	= get_ph(stock)
			if ( isinstance(pricehistory, bool) and pricehistory == False ):
				print('(' + str(stock) + '): get_ph returned False')
				time.sleep(5)
				continue

			# Integrate the very last_price from get_quote() into the latest candle
			if ( last_price >= pricehistory['candles'][-1]['high'] ):
				pricehistory['candles'][-1]['high'] = last_price

			elif ( last_price <= pricehistory['candles'][-1]['low'] ):
				pricehistory['candles'][-1]['low'] = last_price

			else:
				pricehistory['candles'][-1]['close'] = last_price

			# Translate candles to Heiken Ashi candles
			pricehistory	= tda_gobot_helper.translate_heikin_ashi(pricehistory)

			last_open	= pricehistory['candles'][-1]['open']
			last_high	= pricehistory['candles'][-1]['high']
			last_low	= pricehistory['candles'][-1]['low']
			last_close	= pricehistory['candles'][-1]['close']

			# If exit_percent has been hit, we will sell at the first RED candle
			# Combined exit uses Heikin Ashi candles and ttm_trend algorithm to determine
			#  when a trend movement has ended and it's time to exit the trade.
			if ( use_combined_exit == True ):
				trend_exit	= False
				ha_exit		= False

				# Check Trend
				period = 2
				cndl_slice = []
				for i in range(period+1, 0, -1):
					cndl_slice.append( pricehistory['candles'][-i] )

				if ( args.short == False and price_trend(cndl_slice, period=period, affinity='bull') == False ):
					trend_exit = True

				elif ( args.short == True and price_trend(cndl_slice, period=period, affinity='bear') == False ):
					trend_exit = True

				# Check Heikin Ashi candles
				last_close	= pricehistory['hacandles'][-1]['close']
				last_open	= pricehistory['hacandles'][-1]['open']
				if ( args.short == False and last_close < last_open ):
					ha_exit = True

				elif ( args.short == True and last_close > last_open ):
					ha_exit = True

				if ( debug == True ):
					print('(' + str(stock) + '): trend_exit=' + str(trend_exit) + ', ha_exit=' + str(ha_exit))

				# Exit if trend_exit and ha_exit have been triggered
				if ( trend_exit == True and ha_exit == True ):
					exit_signal = True

			else:
				# If not using trend and/or HA candles then just exit when we reach
				#  a candle where the close is moving in the undesired direction.
				if ( args.short == False and last_close < last_open ):
					exit_signal = True

				elif ( args.short == True and last_close > last_open ):
					exit_signal = True


	# Sell/buy_to_cover the security
	if ( exit_signal == True ):

		if ( args.short == False ):
			print('SELLING: net change (' + str(stock) + '): ' + str(net_change) + ' USD')
			if ( args.fake == False ):
				data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, account_number=tda_account_number, debug=debug)

		else:
			print('BUY_TO_COVER: net change (' + str(stock) + '): ' + str(net_change) + ' USD')
			if ( args.fake == False ):
				data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, account_number=tda_account_number, debug=debug)

		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short, sold=True)
		sys.exit(0)



	time.sleep(loopt)

sys.exit(0)
