#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-gobot.py <ticker> <investment-in-usd> [--short] [--multiday]

# The goal of this bot is to purchase or short some shares and ride it until the price
# drops below (or above, for shorting) some % threshold, then sell the shares immediately.

import robin_stocks.tda as tda
import os, sys, time, random
import argparse
import tda_gobot_helper

process_id = random.randint(1000, 9999) # Used to identify this process (i.e. for log_monitor)
loopt = 3				# Period between stock get_lastprice() checks

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=-1, type=float)
parser.add_argument("--account_number", help='Account number to use (default: None)', default=None, type=int)

parser.add_argument("--checkticker", help="Check if ticker is valid", action="store_true")
parser.add_argument("--force", help='Force bot to purchase the stock even if it is listed in the stock blacklist', action="store_true")
parser.add_argument("--fake", help='Paper trade only - disables buy/sell functions', action="store_true")
parser.add_argument("--tx_log_dir", help='Transaction log directory (default: TX_LOGS-GOBOTv1', default='TX_LOGS-GOBOTv1', type=str)

parser.add_argument("--incr_threshold", help="Reset base_price if stock increases by this percent", default=1, type=float)
parser.add_argument("--decr_threshold", help="Max allowed drop percentage of the stock price", default=1, type=float)
parser.add_argument("--entry_price", help="The price to enter a trade", default=0, type=float)
parser.add_argument("--exit_price", help="The price to exit a trade", default=0, type=float)

parser.add_argument("--multiday", help="Watch stock until decr_threshold is reached. Do not sell and exit when market closes", action="store_true")
parser.add_argument("--notmarketclosed", help="Cancel order and exit if US stock market is closed", action="store_true")
parser.add_argument("--short", help='Enable short selling of stock', action="store_true")
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

debug = 1			# Should default to 0 eventually, testing for now
if args.debug:
	debug = 1
if args.decr_threshold:
	decr_percent_threshold = args.decr_threshold	# Max allowed drop percentage of the stock price
if args.incr_threshold:
	incr_percent_threshold = args.incr_threshold	# Reset base_price if stock increases by this percent
if ( args.stock_usd == -1 and args.checkticker == False ):
	print('Error: please enter stock amount (USD) to invest')
	sys.exit(1)

stock		= args.stock
stock_usd	= args.stock_usd
tx_log_dir	= args.tx_log_dir

if ( args.notmarketclosed == True and tda_gobot_helper.ismarketopen_US() == False ):
	print('Canceled order to purchase $' + str(stock_usd) + ' of stock ' + str(stock) + ', because market is closed and --notmarketclosed was set')
	sys.exit(1)


# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file')
	sys.exit(1)

tda_account_number			= int( os.environ["tda_account_number"] )
passcode				= os.environ["tda_encryption_passcode"]
tda_gobot_helper.tda			= tda
tda_gobot_helper.tda_account_number	= tda_account_number
tda_gobot_helper.passcode 		= passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure')
	sys.exit(1)

# Fix up and sanity check the stock symbol before proceeding
stock = tda_gobot_helper.fix_stock_symbol(stock)
ret = tda_gobot_helper.check_stock_symbol(stock)
if ( isinstance(ret, bool) and ret == False ):
	print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
	sys.exit(1)

if ( args.checkticker == True ): # --checkticker means we only wanted to validate the stock ticker
	sys.exit(0)

if ( tda_gobot_helper.check_blacklist(stock) == True ):
	if ( args.force == False ):
		print('(' + str(stock) + ') Error: stock ' + str(stock) + ' found in blacklist file, exiting.')
		sys.exit(1)
	else:
		print('(' + str(stock) + ') Warning: stock ' + str(stock) + ' found in blacklist file.')


# Loop until the entry price is acheived.
if ( args.entry_price != 0 ):

	while True:
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
		print('(' + str(stock) + '): entry_price=' + str(args.entry_price) + ', last_price=' + str(last_price))

		if ( args.short == True ):
			if ( last_price >= args.entry_price): # Need to be careful with this one
				break

		else:
			if ( last_price <= args.entry_price ):
				break

		time.sleep(loopt)

else:
	last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)


# Calculate stock quantity from investment amount
stock_qty = int( float(stock_usd) / float(last_price) )

# Purchase stock, set orig_base_price to the price that we purchases the stock
if ( tda_gobot_helper.ismarketopen_US() == True ):
	if ( args.short == True ):
		print('SHORTING ' + str(stock_qty) + ' shares of ' + str(stock))

		if ( args.fake == False ):
			data = tda_gobot_helper.short_stock_marketprice(stock, stock_qty, fillwait=True, account_number=args.account_number, debug=True)
			if ( data == False ):
				print('Error: Unable to short "' + str(stock) + '"', file=sys.stderr)
				sys.exit(1)

	else:
		print('PURCHASING ' + str(stock_qty) + ' shares of ' + str(stock))
		if ( args.fake == False ):
			data = tda_gobot_helper.buy_stock_marketprice(stock, stock_qty, fillwait=True, account_number=args.account_number, debug=True)
			if ( data == False ):
				print('Error: Unable to buy stock "' + str(ticker) + '"', file=sys.stderr)
				sys.exit(1)

else:
	print('Error: stock ' + str(stock) + ' not purchased because market is closed, exiting.')
	sys.exit(1)

try:
	orig_base_price = float(data['orderActivityCollection'][0]['executionLegs'][0]['price'])
except:
	orig_base_price = last_price

base_price = orig_base_price
percent_change = 0


# Main loop
while True:
	last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=True)
	if ( last_price == False ):
		print('Error: get_lastprice() returned False')
		time.sleep(5)

		# Try logging in again
		if ( tda_gobot_helper.tdalogin(passcode) != True ):
			print('Error: Login failure')

		continue

	# Using last_price for now to approximate gain/loss, however selling
	#  the stock at market price may mean we get a slightly higher or lower return
	net_change = round( (last_price - orig_base_price) * stock_qty, 3 )

	# Log the post/pre market pricing, but skip the rest of the loop if the market is closed.
	# This should only happen if args.multiday == True
	if ( tda_gobot_helper.ismarketopen_US() == False ):
		tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir)
		time.sleep(loopt * 6)
		continue

	# If exit_price was set
	if ( args.exit_price != 0 ):
		percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

		if ( args.short == True ):
			if ( last_price <= args.exit_price ):
				print('BUY_TO_COVER stock ' + str(stock) + '" - the last_price (' + str(last_price) + ') crossed the exit_price(' + str(args.exit_price) + ')')

				if ( args.fake == False ):
					data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, account_number=args.account_number, debug=True)

				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short, sold=True)

				sys.exit(0)

		else:
			if ( last_price >= args.exit_price ):
				print('SELLING stock ' + str(stock) + '" - the last_price (' + str(last_price) + ') crossed the exit_price(' + str(args.exit_price) + ')')

				if ( args.fake == False ):
					data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, account_number=args.account_number, debug=True)

				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, sold=True)

				sys.exit(0)

	# Sell the security if we're getting close to market close
	if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
		print('Market closing, selling stock ' + str(stock))

		if ( args.fake == False ):
			data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, account_number=args.account_number, debug=True)

		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short, sold=True)
		print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
		sys.exit(0)

	# If price decreases
	elif ( float(last_price) < float(base_price) ):
		percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100
		print('Stock "' +  str(stock) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

		# Log format - stock:%change:last_price:net_change:base_price:orig_base_price:stock_qty:proc_id:short
		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short)

		if ( args.short == True ):
			if ( percent_change >= incr_percent_threshold ):
				base_price = last_price
				print('SHORTED Stock "' + str(stock) + '" decreased below the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to ' + str(base_price))

				if ( decr_percent_threshold == args.decr_threshold ):
					decr_percent_threshold = incr_percent_threshold / 2

		elif ( percent_change >= decr_percent_threshold ):

			# Sell the security
			print('SELLING stock ' + str(stock) + '" - the security moved below the decr_percent_threshold (' + str(decr_percent_threshold) + '%)')

			if ( args.fake == False ):
				data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, account_number=args.account_number, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, sold=True)
			print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
			sys.exit(0)

	# If price increases
	elif ( float(last_price) > float(base_price) ):
		percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100
		print('Stock "' +  str(stock) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

		# Log format - stock:%change:last_price:net_change:base_price:orig_base_price
		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short)

		if ( args.short == True ):
			if (percent_change >= decr_percent_threshold):
				# Buy-to-cover the security
				print('BUY_TO_COVER stock ' + str(stock) + '" - the security moved above the decr_percent_threshold (' + str(decr_percent_threshold) + '%)')

				if ( args.fake == False ):
					data = tda_gobot_helper.buytocover_stock_marketprice(stock, stock_qty, fillwait=True, account_number=args.account_number, debug=True)

				tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short, sold=True)
				print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
				sys.exit(0)

		elif ( percent_change >= incr_percent_threshold ):

			# Re-set the base_price to the last_price if we increase by incr_percent_threshold or more
			# This way we can continue to ride a price increase until it starts dropping
			base_price = last_price
			print('Stock "' + str(stock) + '" increased above the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to ' + str(base_price))

			if ( decr_percent_threshold == args.decr_threshold ):
				decr_percent_threshold = incr_percent_threshold / 2

	# No price change
	else:
		if ( debug == 1 ):
			print('Stock "' +  str(stock) + '" no change (' + str(last_price) + ')')

		# Log format - stock:%change:last_price:net_change:base_price:orig_base_price
		tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, tx_log_dir=tx_log_dir, short=args.short)

	time.sleep(loopt)


sys.exit(0)
