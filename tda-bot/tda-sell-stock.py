#!/usr/bin/python3 -u

# Command-line options:
#  ./tda-sell-stock.py <ticker>

# Sell all owned stock of <ticker>
# If the stock is shorted, it will initiate a buy_to_cover instead of a sell
import robin_stocks.tda as tda
import os, time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase', nargs='?', default=None)
parser.add_argument("--panic", help="Sell all stocks in portfolio immediately", action="store_true")
parser.add_argument("--force", help="Used with --panic to force sell all stocks in portfolio immediately without prompt", action="store_true")
parser.add_argument("--prompt", help="Wait for prompt before selling security", action="store_true")
parser.add_argument("--decrement", help="Sell the stock in increments (implies --prompt). Default behavior sells 50% at a time in three phases (50%/%50/Remaining)", action="store_true")
parser.add_argument("--num_decrements", help="Number of decrements when --decrement is enabled (i.e. 3 means sell 50% at a time in three stages)", default=3, type=int)
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

debug = 1			# Should default to 0 eventually, testing for now
if args.debug == True:
	debug = 1

stock = args.stock

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file')
	exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]

import tda_gobot_helper
tda_gobot_helper.tda = tda
tda_gobot_helper.tda_account_number = tda_account_number
tda_gobot_helper.passcode = passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure')
	exit(1)


if ( stock != None ):

	# Fix up and sanity check the stock symbol before proceeding
	stock = tda_gobot_helper.fix_stock_symbol(stock)
	ret = tda_gobot_helper.check_stock_symbol(stock)
	if ( isinstance(ret, bool) and ret == False ):
		print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
		exit(1)

	# Look up the stock in the account and sell
	found = 0
	data = tda.get_account(tda_account_number, options='positions', jsonify=True)
	for asset in data[0]['securitiesAccount']['positions']:
		if ( str(asset['instrument']['symbol']).upper() == str(stock).upper() ):
			last_price = tda_gobot_helper.get_lastprice(stock)
			wait = tda_gobot_helper.ismarketopen_US()

			# BUY_TO_COVER
			if ( float(asset['shortQuantity']) > 0 ):
				if ( args.prompt == True ):

					# Cover the stock in multiple stages
					if ( args.decrement == True and args.num_decrements > 0 ):

						total_shares = int(asset['shortQuantity'])
						num_decrements = 1
						while ( num_decrements <= args.num_decrements ):
							shares = round( total_shares / 2 )
							if ( num_decrements == args.num_decrements ):
								shares = total_shares

							input(  'Stock ' + str(stock) + ', Total Shares: ' + str(total_shares) + ', Shares to COVER: ' + str(shares) +
								'(Stage ' + str(num_decrements) + '/' + str(args.num_decrements) + '). Press <ENTER>')

							tda_gobot_helper.tdalogin(passcode)
							data = tda_gobot_helper.buytocover_stock_marketprice(stock, shares, fillwait=False, debug=True)

							total_shares -= shares
							num_decrements += 1

					# Cover all at once
					else:
						input(str(asset['shortQuantity']) + ' shares of ' + str(stock) + ' found, press <ENTER> to cover')

						tda_gobot_helper.tdalogin(passcode)
						data = tda_gobot_helper.buytocover_stock_marketprice(stock, asset['shortQuantity'], fillwait=wait, debug=True)

				else:
					sell_value = float(last_price) * float(asset['shortQuantity'])
					print('Covering ' + str(asset['shortQuantity']) + ' shares of ' + str(stock) + ' at market price (~$' + str(sell_value) + ")\n")
					data = tda_gobot_helper.buytocover_stock_marketprice(stock, asset['shortQuantity'], fillwait=wait, debug=True)

			# SELL
			else:
				if ( args.prompt == True ):

					# Sell the stock in multiple stages
					if ( args.decrement == True and args.num_decrements > 0 ):

						total_shares = int(asset['longQuantity'])
						num_decrements = 1
						while ( num_decrements <= args.num_decrements ):
							shares = round( total_shares / 2 )
							if ( num_decrements == args.num_decrements ):
								shares = total_shares

							input(  'Stock ' + str(stock) + ', Total Shares: ' + str(total_shares) + ', Shares to SELL: ' + str(shares) +
								'(Stage ' + str(num_decrements) + '/' + str(args.num_decrements) + '). Press <ENTER>')

							tda_gobot_helper.tdalogin(passcode)
							data = tda_gobot_helper.sell_stock_marketprice(stock, asset['longQuantity'], fillwait=False, debug=True)

							total_shares -= shares
							num_decrements += 1

					# Sell all at once
					else:
						input(str(asset['longQuantity']) + ' shares of ' + str(stock) + ' found, press <ENTER> to sell')

						tda_gobot_helper.tdalogin(passcode)
						data = tda_gobot_helper.sell_stock_marketprice(stock, asset['longQuantity'], fillwait=wait, debug=True)

				else:
					sell_value = float(last_price) * float(asset['longQuantity'])
					print('Selling ' + str(asset['longQuantity']) + ' shares of ' + str(stock) + ' at market price (~$' + str(sell_value) + ")\n")
					data = tda_gobot_helper.sell_stock_marketprice(stock, asset['longQuantity'], fillwait=wait, debug=True)

			found = 1
			break


	if ( found == 0 ):
		print('Error: no ' + str(stock) + ' stock found under account number ' + str(tda_account_number))
		exit(1)

elif ( args.panic == True ): ## Panic button

	if ( args.force == False ):
		confirm = input('Confirm liquidation of entire portfolio (yes/no): ')
		if ( str(confirm).lower() != 'yes' ):
			print('Not confirmed, exiting.')
			exit(0)

	found = False
	data = tda.get_account(tda_account_number, options='positions', jsonify=True)
	for asset in data[0]['securitiesAccount']['positions']:
		if ( asset['instrument']['assetType'] != 'EQUITY' ):
			continue

		stock = str(asset['instrument']['symbol']).upper()
		last_price = tda_gobot_helper.get_lastprice(stock)

		if ( float(asset['shortQuantity']) > 0 ):
			sell_value = float(last_price) * float(asset['shortQuantity'])
			print('Covering ' + str(asset['shortQuantity']) + ' shares of ' + str(stock) + ' at market price (~$' + str(sell_value) + ")\n")
			data = tda_gobot_helper.buytocover_stock_marketprice(stock, asset['shortQuantity'], fillwait=False, debug=True)
		else:
			sell_value = float(last_price) * float(asset['longQuantity'])
			print('Selling ' + str(asset['longQuantity']) + ' shares of ' + str(stock) + ' at market price (~$' + str(sell_value) + ")\n")
			data = tda_gobot_helper.sell_stock_marketprice(stock, asset['longQuantity'], fillwait=False, debug=True)

		time.sleep(0.2) # Avoid hammering

		found = True

	if ( found == False ):
		print('Error: no stocks found under account number ' + str(tda_account_number))


else:
	# If no arguments are given just print all the account positions.
	import pprint
	pp = pprint.PrettyPrinter(indent=4)

	data = tda.get_account(tda_account_number, options='positions', jsonify=True)
	pp.pprint(data)
	exit(0)


exit(0)
