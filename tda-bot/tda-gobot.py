#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-gobot.py <ticker> <investment-in-usd> [--short] [--multiday]
#
# The goal of this bot is to purchase or short some shares and ride it until the price
# drops below (or above, for shorting) some % threshold, then sell the shares immediately.
#
# Example - purchase $1000 worth of SPY call options that are 2-levels out of the money and
#  expire next week. Bot will determine the best option to purchase and prompt for confirmation.
#
#   $ ./tda-gobot.py --options --decr_threshold=15 --incr_threshold=2.5 \
#                    --otm_level=2 --listen_cmd --option_type=CALL SPY 1000

import robin_stocks.tda as tda
import os, sys, signal, time, random
import threading
import re
import argparse
import datetime, pytz
import math

import tda_gobot_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=None, type=float)
parser.add_argument("--account_number", help='Account number to use (default: None)', default=None, type=int)

parser.add_argument("--options", help='Purchase CALL/PUT options instead of equities', action="store_true")
parser.add_argument("--option_type", help='Type of options to purchase (CALL|PUT)', default=None, type=str)
parser.add_argument("--near_expiration", help='Choose an option contract with the earliest expiration date', action="store_true")
parser.add_argument("--strike_price", help='The desired strike price', default=None, type=float)
parser.add_argument("--otm_level", help='Out-of-the-money strike price to choose (Default: 1)', default=1, type=int)
parser.add_argument("--start_day_offset", help='Use start_day_offset to push start day of option search +N days out (Default: 0)', default=0, type=int)

parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--noprompt", help='Do not wait for confirmation before entering trade', action="store_true")
parser.add_argument("--print_only", help='Print out action and exit', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS-GOBOTv1', default='TX_LOGS-GOBOTv1', type=str)
parser.add_argument("--listen_cmd", help='Listen for manual input during main loop', action="store_true")
parser.add_argument("--test_mode", help='Test-only mode', action="store_true")

parser.add_argument("--incr_threshold", help="Reset base_price if stock increases by this percent", default=1, type=float)
parser.add_argument("--decr_threshold", help="Max allowed drop percentage of the stock price", default=1, type=float)
parser.add_argument("--entry_price", help="The price to enter a trade", default=None, type=float)
parser.add_argument("--exit_price", help="The price to exit a trade", default=None, type=float)

parser.add_argument("--exit_percent", help='Switch to monitoring price action of the security when the price improves by this percentile', default=None, type=float)
parser.add_argument("--exit_percent_loopt", help='Amount of time to sleep between queries after exit_percent_signal is triggered', default=12, type=int)
parser.add_argument("--quick_exit", help='Exit immediately if an exit_percent strategy was set, do not wait for the next candle', action="store_true")
parser.add_argument("--quick_exit_percent", help='Exit immediately if price improves by this percentage', default=None, type=float)
parser.add_argument("--use_combined_exit", help='Use both the ttm_trend algorithm and Heikin Ashi candles with exit_percent-based exit strategy', action="store_true")
parser.add_argument("--partial_exit_strat", help='Configure an exit strategy', default=None, type=str)
parser.add_argument("--initial_partial_exit_pct", help='Set the initial trigger for the first stage of partial_exit_strat, using incr_threshold afterward', default=5, type=float)

parser.add_argument("--multiday", help="Watch stock until decr_threshold is reached. Do not sell and exit when market closes", action="store_true")
parser.add_argument("--notmarketclosed", help="Cancel order and exit if US stock market is closed", action="store_true")
parser.add_argument("--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")

global args
args = parser.parse_args()

debug = True			# Should default to 0 eventually, testing for now
if args.debug == True:
	debug = True
if args.decr_threshold:
	decr_percent_threshold = args.decr_threshold	# Max allowed drop percentage of the stock price
if args.incr_threshold:
	incr_percent_threshold = args.incr_threshold	# Reset base_price if stock increases by this percent
if ( args.stock_usd == None ):
	print('Error: please enter stock amount (USD) to invest', file=sys.stderr)
	sys.exit(1)
if ( args.test_mode == True ):
	args.fake = True

if ( args.quick_exit == True ):
	if ( args.quick_exit_percent == None and args.exit_percent == None ):
		if ( args.options == True ):
			args.exit_percent	= 5
			args.quick_exit_percent	= 5
		else:
			args.exit_percent	= 1
			args.quick_exit_percent	= 1

	elif ( args.exit_percent != None and args.quick_exit_percent == None ):
		args.quick_exit_percent = args.exit_percent

stock				= args.stock
stock_usd			= args.stock_usd
tx_log_dir			= args.tx_log_dir

process_id			= random.randint(1000, 9999)	# Used to identify this process (i.e. for log_monitor)
loopt				= 3				# Period between stock get_lastprice() checks

exit_percent_signal		= False
exit_signal			= False
stopout_signal			= False

mytimezone			= pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone	= mytimezone

# Text color options
red				= '\033[0;31m'
green				= '\033[0;32m'
reset_color			= '\033[0m'
text_color			= ''

# Do not proceed if market is closed and args.notmarketclosed is set
# Currently this won't matter much as TDA requires limit orders for all extended hours trading
if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
	print('Canceled order to purchase $' + str(stock_usd) + ' of stock ' + str(stock) + ', because market is closed and --notmarketclosed was set')
	sys.exit(1)

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file', file=sys.stderr)
	sys.exit(1)

try:
	if ( args.account_number != None ):
		tda_account_number = args.account_number
	else:
		tda_account_number = int( os.environ["tda_account_number"] )

except:
	print('Error: account number not found, exiting', file=sys.stderr)
	sys.exit(1)

passcode				= os.environ["tda_encryption_passcode"]
tda_gobot_helper.tda			= tda
tda_gobot_helper.tda_account_number	= tda_account_number
tda_gobot_helper.passcode 		= passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure', file=sys.stderr)
	sys.exit(1)

# Fix up and sanity check the stock symbol before proceeding
stock	= tda_gobot_helper.fix_stock_symbol(stock)
ret	= tda_gobot_helper.check_stock_symbol(stock)
if ( isinstance(ret, bool) and ret == False ):
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting', file=sys.stderr)
	sys.exit(1)

if ( tda_gobot_helper.check_blacklist(stock) == True ):
	if ( args.force == False ):
		print('(' + str(stock) + ') Error: stock ' + str(stock) + ' found in blacklist file, exiting', file=sys.stderr)
		sys.exit(1)
	else:
		print('(' + str(stock) + ') Warning: stock ' + str(stock) + ' found in blacklist file.')

if ( tda_gobot_helper.ismarketopen_US() != True and args.multiday == False and args.test_mode == False ):
	print(str(stock) + ' transaction cancelled because market is closed, exiting.')
	sys.exit(1)

#############################################################
# Functions we may need later

# Listener thread to allow modification of order while process is running
def check_input():
	print('Starting listener thread...')

	while True:
		exit_loop = False

		in_cmd = input()
		in_cmd = str(in_cmd).lower()
		print( "Received Command: ", end='' )

		global stock_qty
		global total_stock_qty
		global orig_base_price
		global last_price
		global decr_percent_threshold
		global exit_signal
		global stopout_signal

		# Quit loop and thread if we reduce our stock_qty to zero
		if ( total_stock_qty == 0 ):
			exit_signal	= True
			stopout_signal	= True
			exit_loop	= True

		# If only 1 stock share or option is left, just sell it and exit
		elif ( total_stock_qty == 1 and (in_cmd == 'h' or in_cmd == '1' or in_cmd == '2' or in_cmd == '3')):
			print('Selling qty: ' + str(total_stock_qty) + ', remaining: 0')
			stock_qty	= 1

			exit_signal	= True
			stopout_signal	= True
			exit_loop	= True

		# Sell all remaining stock/options
		elif ( in_cmd == 's' ):
			print('SELL ALL')
			print('Selling qty: ' + str(total_stock_qty) + ', remaining: 0')
			stock_qty = total_stock_qty

			exit_signal	= True
			stopout_signal	= True
			exit_loop	= True

		# Sell half of stock/options
		elif ( in_cmd == 'h' ):
			stock_qty = math.ceil( total_stock_qty / 2 )

			print('SELL HALF')
			print('Selling qty: ' + str(stock_qty) + ', remaining: ' + str(total_stock_qty - stock_qty))
			exit_signal = True

		# Sell 10% of stock/options
		elif ( in_cmd == '1' ):
			stock_qty = math.ceil( total_stock_qty * 0.1 )

			print('SELL 10%')
			print('Selling qty: ' + str(stock_qty) + ', remaining: ' + str(total_stock_qty - stock_qty))
			exit_signal = True

		# Sell 20% of stock/options
		elif ( in_cmd == '2' ):
			stock_qty = math.ceil( total_stock_qty * 0.2 )

			print('SELL 20%')
			print('Selling qty: ' + str(stock_qty) + ', remaining: ' + str(total_stock_qty - stock_qty))
			exit_signal = True

		# Sell 30% of stock/options
		elif ( in_cmd == '3' ):
			stock_qty = math.ceil( total_stock_qty * 0.3 )

			print('SELL 30%')
			print('Selling qty: ' + str(stock_qty) + ', remaining: ' + str(total_stock_qty - stock_qty))
			exit_signal = True

		# Set stoploss to cost basis
		elif ( in_cmd == 'cb' ):
			print('SET STOPLOSS TO COST BASIS')

			# We cannot set a stoploss if we are already below cost basis
			if ( (args.short == False and last_price < orig_base_price) or
					(args.short == True and last_price > orig_base_price)):
				print('Error: last_price ($' + str(round(last_price, 2)) + ') is already below cost basis ($' + str(round(orig_base_price, 2)) + '), ignoring stoploss command')

			else:
				decr_percent_threshold = abs( ((orig_base_price / last_price) - 1) * 100 )
				print('Setting stoploss to ' + str(round(decr_percent_threshold, 2)) + '%, orig_base_price: $' + str(round(orig_base_price, 2)) + ' / last_price: $' + str(round(last_price, 2)))

		# Enable quick_exit and set a quick_exit_percent from current last_price
		elif ( re.match('qe:', in_cmd) != None ):

			try:
				qe_pct = float( in_cmd.split(':')[1] )
			except:
				print('Error: bad format: ' + str(in_cmd) + ', ignoring')

			else:
				args.quick_exit		= True
				qe_price		= last_price + (last_price * (qe_pct / 100))
				args.quick_exit_percent	= ((qe_price / orig_base_price) - 1) * 100

				print('SET QUICK EXIT: ' + str(round(args.quick_exit_percent, 2)) + '% ($' + str(round(qe_price, 2)) + ')')

		else:
			print('Unknown command (' + str(in_cmd) + '), ignoring')

		# Unblock the main thread to interrupt sleep
		main_event.set()

		if ( exit_loop == True ):
			break

	return True


# Get the pricehistory of the stock
# This is needed for --combined_exit strategy
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


# Find the right option contract to purchase
def search_options(ticker=None, option_type=None, near_expiration=False, strike_price=None, otm_level=1, start_day_offset=0, debug=False):

	if ( ticker == None or option_type == None ):
		return False

	option_type = option_type.upper()
	if ( option_type != 'CALL' and option_type != 'PUT' ):
		return False

	# Search for options that expire either this week or next week
	# Use start_day_offset to push start day of option search +N days out
	dt		= datetime.datetime.now(mytimezone)
	start_day	= dt
	if ( start_day_offset > 0 ):
		start_day = dt + datetime.timedelta(days=start_day_offset)

	end_day = dt + datetime.timedelta(days=7)

	# If near_expiration=False, then push the search date out at least one-day.
	#  This is useful for stocks like SPY that have options expiring on Mon/Wed/Fri.
	if ( near_expiration == False ):
		start_day = dt + datetime.timedelta(days=1)
		if ( start_day_offset > 0 ):
			start_day = dt + datetime.timedelta(days=start_day_offset)

		if ( int(dt.strftime('%w')) >= 3 ):
			start_day	= dt + datetime.timedelta(days=6)
			end_day		= dt + datetime.timedelta(days=12)

	range_val	= 'NTM'
	strike_price	= None
	strike_count	= 5
	if ( strike_price != None ):
		range_val	= 'ALL'
		strike_price	= float( args.strike_price )
		strike_count	= 999
	elif ( otm_level > 1 ):
		strike_count += otm_level * 2

	try:
		option_chain = tda_gobot_helper.get_option_chains( ticker=ticker, contract_type=option_type, strike_count=strike_count, range_value=range_val, strike_price=strike_price,
									from_date=start_day.strftime('%Y-%m-%d'), to_date=end_day.strftime('%Y-%m-%d') )

	except Exception as e:
		print('Error: looking up option chain for stock ' + str(ticker) + ': ' + str(e), file=sys.stderr)
		sys.exit(1)

	stock		= None
	ExpDateMap	= 'callExpDateMap'
	if ( option_type == 'PUT' ):
		ExpDateMap = 'putExpDateMap'

	try:
		exp_date = list(option_chain[ExpDateMap].keys())[0]
	except Exception as e:
		print('Caught Exception: ' + str(e))
		return False

	# For PUTs, reverse the list to get the optimal strike price
	iter = option_chain[ExpDateMap][exp_date].keys()
	if ( option_type == 'PUT' ):
		iter = reversed(option_chain[ExpDateMap][exp_date].keys())

	otm_level_count = 1
	for key in iter:
		try:
			strike = int( float(key) )
			if ( strike_price != None and strike != strike_price ):
				continue

		except Exception as e:
			print('(' + str(ticker) + '): error processing option chain: ' + str(key) + ': ' + str(e), file=sys.stderr)
			continue

		else:
			key = option_chain[ExpDateMap][exp_date][key]

		# API returns a list for each strike price, but I've not yet seen any strike price
		#  data contain more than one entry. Possibly there are times when different brokers
		#  have different offerings for each strike price.
		key = key[0]

		# Find the first OTM (or otm_level) option or follow --strike_price
		if ( key['inTheMoney'] == False or strike_price != None ):
			if ( otm_level > 1 and strike_price == None ):
				if ( otm_level_count < otm_level ):
					otm_level_count += 1
					continue

			if ( stock_usd < key['ask'] * 100 ):
				print('(' + str(key['symbol']) + '): Available stock_usd (' + str(stock_usd) + ') is less than the ask for this option (' + str(key['ask'] * 100) + ')')
				continue

			bidask_pct	= round( abs( key['bid'] / key['ask'] - 1 ) * 100, 3 )
			stock_qty	= int( stock_usd / (key['ask'] * 100) )

			print( str(key['symbol']) + ': ' + str(stock_qty) + ' contracts (' + str(stock_qty*key['ask']*100) + ') / Strike: ' + str(strike) )
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

			stock = key['symbol']

			break

	if ( stock == None ):
		print('Unable to locate an available option to trade, exiting.')
		return False

	return stock, float(key['ask'])


# Signal handler, mostly to quit all threads
def graceful_exit(signum=None, frame=None):
	print("\nNOTICE: graceful_exit(): received signal: " + str(signum))
	if ( args.listen_cmd == True ):
		total_stock_qty = 0
		cmd_thread.join(timeout=0.1)
		os._exit(0)

	sys.exit(0)

signal.signal(signal.SIGINT, graceful_exit)
signal.signal(signal.SIGTERM, graceful_exit)

## End sub functions


# Find the right option to purchase
if ( args.options == True ):
	if ( args.option_type == None ):
		print('Error: --option_type (CALL|PUT) is required, exiting', file=sys.stderr)
		sys.exit(1)

	stock, option_price = search_options(	ticker=args.stock, option_type=args.option_type,
						near_expiration=args.near_expiration, start_day_offset=args.start_day_offset,
						strike_price=args.strike_price, otm_level=args.otm_level, debug=False )
	if ( isinstance(stock, bool) and stock == False ):
		print('Error: Unable to look up options for stock "' + str(args.stock) + '"', file=sys.stderr)
		sys.exit(1)

	# If the option is < $1, then the price action may be too jittery. If near_expiration is set to True
	#  then try to disable to find an option with a later expiration date.
	if ( option_price < 1 and args.near_expiration == True and args.force == False ):
		print('Notice: ' + str(stock) + ' price (' + str(option_price) + ') is below $1, setting near_expiration to False (you can use --force to avoid this check)')

		stock, option_price = search_options(	ticker=args.stock, option_type=args.option_type,
							near_expiration=False, start_day_offset=args.start_day_offset,
							strike_price=args.strike_price, otm_level=args.otm_level, debug=False )
		if ( isinstance(stock, bool) and stock == False ):
			print('Error: Unable to look up options for stock "' + str(args.stock) + '"', file=sys.stderr)
			sys.exit(1)

# Loop until the entry price is achieved.
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


# Purchase the option or equity
# OPTIONS
if ( args.options == True ):

	quote = tda_gobot_helper.get_quotes(stock)
	try:
		option_price	= quote[stock]['askPrice']
		stock_qty       = int( stock_usd / (option_price * 100) )

	except Exception as e:
		print(str(stock) + ': Error: Unable to lookup option price')
		sys.exit(1)

	# Only print out the chosen option information and then exit
	if ( args.print_only == True ):
		sys.exit(0)

	if ( args.noprompt == False ):
		input('PURCHASING ' + str(stock_qty) + ' contracts of ' + str(stock) + ' - Press <ENTER> to confirm')
	else:
		print('PURCHASING ' + str(stock_qty) + ' contracts of ' + str(stock))

	if ( args.fake == False ):
		order_id = tda_gobot_helper.buy_sell_option(contract=stock, quantity=stock_qty, instruction='buy_to_open', fillwait=True, account_number=tda_account_number, debug=True)
		if ( isinstance(order_id, bool) and order_id == False ):
			print('Error: Unable to purchase option "' + str(stock) + '"', file=sys.stderr)
			sys.exit(1)

		# Adjust option_price with the mean fill price if available
		data = False
		try:
			data		= tda_gobot_helper.get_order(order_id, tda_account_number, passcode)
			option_price	= float( data['orderActivityCollection'][0]['executionLegs'][0]['price'] )
		except:
			option_price = quote[stock]['askPrice']

		if ( isinstance(data, bool) and data == False ):
			option_price = quote[stock]['askPrice']
			print("\nFill price not in order data, using ask price ($" + str(option_price) + ')')
		else:
			print("\nMean fill price ($" + str(option_price) + ')')

# EQUITY stock, set orig_base_price to the price that we purchased the stock
else:
	stock_qty = int( stock_usd / last_price )
	if ( args.short == True ):
		if ( args.noprompt == False ):
			input('SHORTING ' + str(stock_qty) + ' shares of ' + str(stock) + ' - Press <ENTER> to confirm')
		else:
			print('SHORTING ' + str(stock_qty) + ' shares of ' + str(stock))

		if ( args.fake == False ):
			data = tda_gobot_helper.short_stock_marketprice(stock, stock_qty, fillwait=True, account_number=tda_account_number, debug=debug)
			if ( isinstance(data, bool) and data == False ):
				print('Error: Unable to short "' + str(stock) + '"', file=sys.stderr)
				sys.exit(1)

	else:
		if ( args.noprompt == False ):
			input('PURCHASING ' + str(stock_qty) + ' shares of ' + str(stock) + ' - Press <ENTER> to confirm')
		else:
			print('PURCHASING ' + str(stock_qty) + ' shares of ' + str(stock))

		if ( args.fake == False ):
			data = tda_gobot_helper.buy_stock_marketprice(stock, stock_qty, fillwait=True, account_number=tda_account_number, debug=debug)
			if ( isinstance(data, bool) and data == False ):
				print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
				sys.exit(1)

try:
	orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
except:
	orig_base_price = last_price

open_time		= datetime.datetime.now( mytimezone )
base_price		= orig_base_price
last_price		= orig_base_price
total_stock_qty		= stock_qty
percent_change		= 0
total_percent_change	= 0

# Start input thread if needed
main_event = threading.Event()
if ( args.listen_cmd == True ):
	cmd_thread = threading.Thread(target=check_input, args=())
	cmd_thread.start()


# Main loop
# Watch the performance of the option or equity and make decisions
#  about exit strategy
while True:

	# Clear main_event.set() if set from the cmd_thread
	main_event.clear()

	# Skip the overhead of these API calls if we're carrying an exit_signal from the cmd_thread
	if ( exit_signal == False ):

		# Use get_quote() to retrieve the latest pricing information
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=True)
		if ( isinstance(last_price, bool) and last_price == False ):
			print('Error: get_lastprice() returned False', file=sys.stderr)
			main_event.wait(loopt)

			# Try logging in again
			if ( tda_gobot_helper.tdalogin(passcode) != True ):
				print('Error: Login failure', file=sys.stderr)

			continue

		stock_last_price = 0
		if ( args.options == True ):
			stock_last_price = tda_gobot_helper.get_lastprice(args.stock, WarnDelayed=True)

		# Using last_price for now to approximate gain/loss
		net_change		= round( (last_price - orig_base_price) * stock_qty, 3 )
		total_percent_change	= abs( last_price / orig_base_price - 1 ) * 100
		percent_change		= abs( last_price / base_price - 1 ) * 100

		if ( debug == True ):
			text_color = green
			if ( args.short == False and last_price < orig_base_price or
				args.short == True and last_price > orig_base_price ):
					text_color		= red
					total_percent_change	= -total_percent_change

			# Options
			if ( args.options == True ):
				print('(' +  str(stock) + ' +' + str(total_stock_qty) + '): Total Change: ' + str(text_color) + str(round(total_percent_change, 2)) + '% (' + str(last_price) + ')' + str(reset_color) + ' / ' + str(args.stock) + ': ' + str(stock_last_price))

			# Equity
			else:
				if ( args.short == False ):
					print('(' +  str(stock) + ' +' + str(total_stock_qty) + '): Total Change: ' + str(text_color) + str(round(total_percent_change, 2)) + '% (' + str(last_price) + ')' + str(reset_color))
				else:
					print('(' +  str(stock) + ' -' + str(total_stock_qty) + '): Total Change: ' + str(text_color) + str(round(total_percent_change, 2)) + '% (' + str(last_price) + ')' + str(reset_color))

		# Log format - stock:%change:last_price:net_change:base_price:orig_base_price:stock_qty:proc_id:short
		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short)

	# Log the post/pre market pricing, but skip the rest of the loop if the market is closed.
	# This should only happen if args.multiday == True
	if ( tda_gobot_helper.ismarketopen_US() == False and args.test_mode == False ):
		main_event.wait(loopt * 6)
		continue

	# Sell the security if we're getting close to market close
	elif ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
		print('Market closing, selling stock ' + str(stock))
		exit_signal	= True
		stopout_signal	= True

	# If exit_price was set
	if ( args.exit_price != None and exit_signal == False ):
		percent_change = abs( last_price / base_price - 1 ) * 100
		if ( args.short == True ):
			if ( last_price <= args.exit_price ):
				print('BUY_TO_COVER stock ' + str(stock) + '" - the last_price (' + str(last_price) + ') crossed the exit_price(' + str(args.exit_price) + ')')
				exit_signal	= True
				stopout_signal	= True

		else:
			if ( last_price >= args.exit_price ):
				print('SELLING stock ' + str(stock) + '" - the last_price (' + str(last_price) + ') crossed the exit_price(' + str(args.exit_price) + ')')
				exit_signal	= True
				stopout_signal	= True

	# Stoploss Monitor
	# Monitor negative movement in price, unless exit_percent_signal has been triggered
	#
	# If price decreases
	if ( last_price < base_price and exit_percent_signal == False and exit_signal == False ):
		if ( args.short == True and percent_change >= incr_percent_threshold ):
			base_price = last_price
			if ( debug == True ):
				print('SHORTED Stock "' + str(stock) + '" decreased below the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to ' + str(base_price))

			if ( decr_percent_threshold == args.decr_threshold ):
				decr_percent_threshold = args.decr_threshold / 2

		elif ( percent_change >= decr_percent_threshold ):
			# Sell the security
			print('SELLING stock ' + str(stock) + '" - the security moved below the decr_percent_threshold (' + str(decr_percent_threshold) + '%)')
			exit_signal	= True
			stopout_signal	= True

	# If price increases
	elif ( last_price > base_price and exit_percent_signal == False and exit_signal == False ):

		if ( args.short == True and percent_change >= decr_percent_threshold ):
			# Buy-to-cover the security
			print('BUY_TO_COVER stock ' + str(stock) + '" - the security moved above the decr_percent_threshold (' + str(decr_percent_threshold) + '%)')
			exit_signal	= True
			stopout_signal	= True

		elif ( percent_change >= incr_percent_threshold ):

			# Re-set the base_price to the last_price if we increase by incr_percent_threshold or more
			# This way we can continue to ride a price increase until it starts dropping
			base_price = last_price
			if ( debug == True ):
				print('Stock "' + str(stock) + '" increased above the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to ' + str(base_price))

#			if ( decr_percent_threshold == args.decr_threshold ):
#				decr_percent_threshold = args.decr_threshold / 2

			# Handle partial_exit_strat
			# Split the stock into separate partial transactions, as long as the price is going up
			if ( args.partial_exit_strat != None ):
				if ( (stock_qty == total_stock_qty and total_percent_change >= args.initial_partial_exit_pct) or
						stock_qty < total_stock_qty ):

					# Split the stock into three transactions
					if ( args.partial_exit_strat == 'one_third' or args.partial_exit_strat == 'one_third_run' ):
						if ( stock_qty > int(total_stock_qty / 3) ):
							stock_qty	= int( stock_qty - (total_stock_qty / 3) * 2 )
							exit_signal	= True

						else:
							# one_third_run means to leave the final 1/3 to a
							#  trend-based exit strategy below, otherwise just stop out
							if ( args.partial_exit_strat == 'one_third_run' ):
								exit_percent = incr_percent_threshold

							else:
								exit_signal	= True
								stopout_signal	= True

					# Split the stock into four transactions
					if ( args.partial_exit_strat == 'one_fourth' or args.partial_exit_strat == 'one_fourth_run' ):
						if ( stock_qty > int(total_stock_qty / 4) ):
							stock_qty	= int( stock_qty - (total_stock_qty / 4) * 2 )
							exit_signal	= True

						else:
							# one_fourth_run means to leave the final 1/4 to a
							#  trend-based exit strategy below, otherwise just stop out
							if ( args.partial_exit_strat == 'one_fourth_run' ):
								exit_percent = incr_percent_threshold

							else:
								exit_signal	= True
								stopout_signal	= True


	# Additional exit strategies
	if ( args.exit_percent != None and exit_signal == False ):
		if ( exit_percent_signal == False ):

			# LONG or OPTIONS
			if ( args.short == False and last_price > orig_base_price ):
				total_percent_change = abs( orig_base_price / last_price - 1 ) * 100
				if ( total_percent_change >= args.exit_percent ):
					if ( args.quick_exit == True and total_percent_change >= args.quick_exit_percent ):
						exit_signal	= True
						stopout_signal	= True

					else:
						exit_percent_signal = True
						if ( debug == True ):
							print('(' + str(stock) + '): exit_percent_signal triggered')

						main_event.wait(loopt)
						continue

			# SHORT
			elif ( args.short == True and last_price < orig_base_price ):
				total_percent_change = abs( last_price / orig_base_price - 1 ) * 100
				if ( total_percent_change >= args.exit_percent ):
					if ( args.quick_exit == True and total_percent_change >= args.quick_exit_percent ):
						exit_signal	= True
						stopout_signal	= True

					else:
						exit_percent_signal = True
						if ( debug == True ):
							print('(' + str(stock) + '): exit_percent_signal triggered')

						main_event.wait(loopt)
						continue

			# If exit_percent_signal is triggered very quickly then get_pricehistory candles
			#  may not be updated yet and could results in an early exit. Make sure we wait at
			#  least 60-seconds between opening the position and triggering exit_percent_signal.
			if ( exit_percent_signal == True ):
				cur_time	= datetime.datetime.now( mytimezone )
				delta		= cur_time - open_time
				delta		= delta.total_seconds()
				if ( delta < 60 ):
					if ( debug == True ):
						print('(' + str(stock) + '): waiting ' + str(delta+loopt) + ' seconds before triggering exit_percent_signal')

					main_event.wait( delta + loopt)

		# Once exit_percent_signal is triggered we need to move to use candles so we can analyze
		#  price movement.
		elif ( exit_percent_signal == True and exit_signal == False ):

			# First, process quick_exit_percent if configured
			if ( args.quick_exit == True and args.quick_exit_percent != None ):
				if ( total_percent_change >= args.quick_exit_percent ):
					exit_signal	= True
					stopout_signal	= True

			loopt		= args.exit_percent_loopt
			pricehistory	= {}

			if ( args.options == True ):
				pricehistory	= get_ph( args.stock ) # Follow the original stock, not the option contract
			else:
				pricehistory	= get_ph( stock )

			if ( isinstance(pricehistory, bool) and pricehistory == False ):
				print('(' + str(stock) + '): get_ph returned False')
				main_event.wait(5)
				continue

			# Integrate the latest last_price from get_quote() into the latest candle from pricehistory
			if ( args.options == False ):
				if ( last_price >= pricehistory['candles'][-1]['high'] ):
					pricehistory['candles'][-1]['high']	= last_price
					pricehistory['candles'][-1]['close']	= last_price

				elif ( last_price <= pricehistory['candles'][-1]['low'] ):
					pricehistory['candles'][-1]['low']	= last_price
					pricehistory['candles'][-1]['close']	= last_price

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
			if ( args.use_combined_exit == True ):
				trend_exit	= False
				ha_exit		= False

				# Check Trend
				period = 2
				cndl_slice = []
				for i in range(period+1, 0, -1):
					cndl_slice.append( pricehistory['candles'][-i] )

				if ( ((args.options == False and args.short == False) or (args.options == True and args.option_type == 'CALL')) and
						price_trend(cndl_slice, period=period, affinity='bull') == False ):
					trend_exit = True

				elif ( ((args.options == False and args.short == True) or (args.options == True and args.option_type == 'PUT')) and
						price_trend(cndl_slice, period=period, affinity='bear') == False ):
					trend_exit = True

				# Check Heikin Ashi candles
				last_ha_close	= pricehistory['hacandles'][-1]['close']
				last_ha_open	= pricehistory['hacandles'][-1]['open']
				if ( ((args.options == False and args.short == False) or (args.options == True and args.option_type == 'CALL')) and
						last_ha_close < last_ha_open ):
					ha_exit = True

				elif ( ((args.options == False and args.short == True) or (args.options == True and args.option_type == 'PUT')) and
						last_ha_close > last_ha_open ):
					ha_exit = True

				if ( debug == True ):
					print('(' + str(stock) + '): trend_exit=' + str(trend_exit) + ', ha_exit=' + str(ha_exit))

				# Exit if trend_exit and ha_exit have been triggered
				if ( trend_exit == True and ha_exit == True ):
					print('(' + str(args.stock) + '): last_candle: ' + str(last_open) + '/' + str(last_close) + ', last_ha_candle: ' + str(last_ha_open) + '/' + str(last_ha_close))
					exit_signal	= True
					stopout_signal	= True


			else:
				# If not using trend and/or HA candles then just exit when we reach
				#  a candle where the close is moving in the undesired direction.
				if ( ((args.options == False and args.short == False) or (args.options == True and args.option_type == 'CALL')) and
						last_close < last_open ):
					exit_signal	= True
					stopout_signal	= True

				elif ( ((args.options == False and args.short == True) or (args.options == True and args.option_type == 'PUT')) and
						last_close > last_open ):
					exit_signal	= True
					stopout_signal	= True

	# Handle quick_exit and quick_exit_percent
	if ( args.quick_exit == True and exit_signal == False ):
		if ( total_percent_change >= args.quick_exit_percent ):
			exit_signal	= True
			stopout_signal	= True

	# Sell/buy_to_cover the security
	if ( exit_signal == True ):
		text_color = green

		total_stock_qty = total_stock_qty - stock_qty
		if ( total_stock_qty == 0 ):
			stopout_signal = True
		if ( args.partial_exit_strat != None ):
			print( '(' + str(stock) + '): exiting ' + str(stock_qty) + ' shares/options, (Remaining: ' + str(total_stock_qty) + ')' )

		# OPTIONS
		if ( args.options == True ):
			if ( net_change < 0 ):
				text_color = red

			if ( args.fake == False ):

				# If only filling part, then let's submit the order and get back to the loop quicker
				fillwait = True
				if ( stopout_signal == False ):
					fillwait = False

				data = tda_gobot_helper.buy_sell_option(contract=stock, quantity=stock_qty, instruction='sell_to_close', fillwait=fillwait, account_number=tda_account_number, debug=debug)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short, sold=True)

		# EQUITY stock
		else:
			# If only filling part, then let's submit the order and get back to the loop quicker
			fillwait = True
			if ( stopout_signal == False ):
				fillwait = False

			if ( args.short == False ):
				if ( net_change < 0 ):
					text_color = red

				print('SELLING: net change (' + str(stock) + '): ' + str(text_color) + str(net_change) + ' USD' + str(reset_color))
				if ( args.fake == False ):
					data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=fillwait, account_number=tda_account_number, debug=debug)

			else:
				if ( net_change > 0 ):
					text_color = red
				else:
					# Shorts usually have a negative net_change when trades are successful,
					#  but make it a positive number for readability
					net_change = abs(net_change)

				print('BUY_TO_COVER: net change (' + str(stock) + '): ' + str(text_color) + str(net_change) + ' USD' + str(reset_color))
				if ( args.fake == False ):
					data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=fillwait, account_number=tda_account_number, debug=debug)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short, sold=True)

		exit_signal = False
		if ( stopout_signal == True ):
			break

		# Skip main_event.wait() to expedite the loop around after exiting part of our position
		continue

	main_event.wait(loopt)


# Use os._exit(0) if listener thread is blocked on input()
if ( args.listen_cmd == True ):
	total_stock_qty = 0
	cmd_thread.join(timeout=0.1)
	os._exit(0)

sys.exit(0)

