#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-gobot.py <ticker> <investment-in-usd>

# The goal of this bot is to purchase some shares and ideally ride it upward,
# or if the price drops below some % threshold, then sell the shares immediately.

# Notes/Ideas:
#  - Have a way to scan and choose stocks automatically
#  - Use pypfopt to allocate number of shares to buy among a set of shares vs. just purchase
#    the same number of each.

import robin_stocks.tda as tda
import os, sys, time, random
import argparse
import tda_gobot_helper

process_id = random.randint(1000, 9999) # Used to identify this process (i.e. for log_monitor)

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=-1, type=float)
parser.add_argument("-c", "--checkticker", help="Check if ticker is valid", action="store_true")
parser.add_argument("-i", "--incr_threshold", help="Reset base_price if stock increases by this percent", type=float)
parser.add_argument("-u", "--decr_threshold", help="Max allowed drop percentage of the stock price", type=float)
parser.add_argument("-m", "--multiday", help="Watch stock until decr_threshold is reached. Do not sell and exit when market closes", action="store_true")
parser.add_argument("-o", "--notmarketclosed", help="Cancel order and exit if US stock market is closed", action="store_true")
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

debug = 1			# Should default to 0 eventually, testing for now
loopt = 10			# Period between stock get_lastprice() checks
incr_percent_threshold = 1.5	# Reset base_price if stock increases by this percent
decr_percent_threshold = 1.5	# Max allowed drop percentag of the stock price
if args.debug:
	debug = 1
if args.decr_threshold:
	decr_percent_threshold = args.decr_threshold
if args.incr_threshold:
	incr_percent_threshold = args.incr_threshold
if ( args.stock_usd == -1 and args.checkticker == False ):
	print('Error: please enter stock amount (USD) to invest')
	exit(1)

stock = args.stock
stock_usd = args.stock_usd

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

if ( args.checkticker == True ): # --checkticker means we only wanted to validate the stock ticker
	exit(0)


# Calculate stock quantity from investment amount
time.sleep(0.2) # avoid hammering the API
last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
stock_qty = int( float(stock_usd) / float(last_price) )


# Purchase stock, set orig_base_price to the price that we purchases the stock
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
base_price = orig_base_price


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
		tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id)
		time.sleep(loopt * 6)
		continue

	# Sell the security if we're getting close to market close
	if ( tda_gobot_helper.isendofday() == True and args.multiday == False ):
		print('Market close, selling stock ' + str(stock))
		data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, sold=True)
		print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
		exit(0)

	# If price decreases
	elif ( float(last_price) < float(base_price) ):
		percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100
		print('Stock "' +  str(stock) + '" -' + str(round(percent_change, 2)) + '% (' + str(last_price) + ')')

		# Log format - stock:%change:last_price:net_change:base_price:orig_base_price
		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id)

		if ( percent_change >= decr_percent_threshold):
			# Sell the security
			print('Stock ' + str(stock) + '" dropped below the decr_percent_threshold (' + str(decr_percent_threshold) + '%), selling the security...')
			data = tda_gobot_helper.sell_stock_marketprice(stock, stock_qty, fillwait=True, debug=True)

			tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id, sold=True)
			print('Net change (' + str(stock) + '): ' + str(net_change) + ' USD')
			exit(0)

	# If price increases
	elif ( float(last_price) > float(base_price) ):
		percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100
		print('Stock "' +  str(stock) + '" +' + str(round(percent_change,2)) + '% (' + str(last_price) + ')')

		# Re-set the base_price to the last_price if we increase by 5% or more
		# This way we can continue to ride a price increase until it starts dropping.
		if ( percent_change >= incr_percent_threshold ):
			base_price = last_price
			print('Stock "' + str(stock) + '" increased above the incr_percent_threshold (' + str(incr_percent_threshold) + '%), resetting base price to ' + str(base_price))

		# Log format - stock:%change:last_price:net_change:base_price:orig_base_price
		tda_gobot_helper.log_monitor(stock, percent_change, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id)

	# No price change
	else:
		if ( debug == 1 ):
			print('Stock "' +  str(stock) + '" no change (' + str(last_price) + ')')

		# Log format - stock:%change:last_price:net_change:base_price:orig_base_price
		tda_gobot_helper.log_monitor(stock, 0, last_price, net_change, base_price, orig_base_price, stock_qty, proc_id=process_id)

	time.sleep(loopt)


exit(0)
