#!/usr/bin/python3 -u

# Backtest a variety of algorithms and print a report

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
parser.add_argument("-a", "--algo", help='Analyze the most recent 5-day and 10-day history for a stock ticker using this bot\'s algorithim(s) - (rsi|stochrsi)', default='rsi', type=str)
parser.add_argument("-b", "--nocrossover", help='Modifies the algorithm so that k and d crossovers will not generate a signal (default=False)', action="store_true")
parser.add_argument("-c", "--crossover_only", help='Modifies the algorithm so that only k and d crossovers will generate a signal (default=False)', action="store_true")
parser.add_argument("-e", "--days", help='Number of days to test. Separate with a comma to test multiple days.', default='10', type=str)
parser.add_argument("-v", "--verbose", help='Print additional information about each transaction (default=False)', action="store_true")
parser.add_argument("-i", "--incr_threshold", help='Reset base_price if stock increases by this percent', type=float)
parser.add_argument("-u", "--decr_threshold", help='Max allowed drop percentage of the stock price', type=float)
parser.add_argument("-s", "--stoploss", help='Sell security if price drops below --decr_threshold (default=False)', action="store_true")
parser.add_argument("-p", "--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("-w", "--stochrsi_period", help='RSI period to use for StochRSI calculation (Default: 14)', default=14, type=int)
parser.add_argument("-q", "--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("-k", "--rsi_k_period", help='k period to use in StochRSI algorithm', default=14, type=int)
parser.add_argument("-t", "--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("-r", "--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='ohlc4', type=str)
parser.add_argument("-g", "--rsi_high_limit", help='RSI high limit', default=70, type=int)
parser.add_argument("-l", "--rsi_low_limit", help='RSI low limit', default=30, type=int)
parser.add_argument("-y", "--noshort", help='Disable short selling of stock', action="store_true")
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
args.nocrossover

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

# Check if stock is in the blacklist
if ( tda_gobot_helper.check_blacklist(stock) == True ):
	print('(' + str(stock) + ') WARNING: stock ' + str(stock) + ' is currently blacklisted')

# Confirm that we can short this stock
if ( args.noshort == False or args.shortonly == True ):
	data,err = tda.stocks.get_quote(stock, True)
	if ( err != None ):
		print('Error: get_quote(' + str(stock) + '): ' + str(err), file=sys.stderr)

	if ( str(data[stock]['shortable']) == str(False) or str(data[stock]['marginable']) == str(False) ):
		if ( args.shortonly == True ):
			print('Error: stock(' + str(stock) + '): does not appear to be shortable, exiting.')
			exit(1)

		if ( args.noshort == False ):
			print('Warning: stock(' + str(stock) + '): does not appear to be shortable, disabling sell-short')
			args.noshort = True


# tda.get_price_history() variables
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone
p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

# RSI variables
rsi_type = args.rsi_type
rsi_period = args.rsi_period
stochrsi_period = args.stochrsi_period
rsi_slow = args.rsi_slow
cur_rsi = 0
prev_rsi = 0
rsi_low_limit = args.rsi_low_limit
rsi_high_limit = args.rsi_high_limit

# Report colors
red = '\033[0;31m'
green = '\033[0;32m'
reset_color = '\033[0m'
text_color = ''

# Get general info about the stock
marginable = None
shortable = None
delayed = True
volatility = 0
lastprice = 0
high = low = 0

try:
	data,err = tda.stocks.get_quote(stock, True)
	if ( err == None and data != {} ):
		if ( str(data[stock]['marginable']) == 'True' ):
			marginable = True
		if ( str(data[stock]['shortable']) == 'True' ):
			shortable = True
		if ( str(data[stock]['delayed']) == 'False' ):
			delayed = False

		volatility = data[stock]['volatility'] # FIXME: I don't know what this means yet
		lastprice = data[stock]['lastPrice']
		high = data[stock]['52WkHigh']
		low = data[stock]['52WkLow']

except Exception as e:
	print('Caught exception in tda.stocks.get_quote(' + str(stock) + '): ' + str(e))
	pass

print()
print( 'Stock summary for "' + str(stock) + "\"\n" )
print( 'Last Price: $' + str(lastprice) )
print( '52WkHigh: $' + str(high) )
print( '52WkLow: $' + str(low) )

text_color = green
if ( shortable == False ):
	text_color = red
print( 'Shortable: ' + text_color + str(shortable) + reset_color )

text_color = green
if ( marginable == False ):
	text_color = red
print( 'Marginable: ' + text_color + str(marginable) + reset_color )

text_color = green
if ( delayed == True ):
	text_color = red
print( 'Delayed: ' + text_color + str(delayed) + reset_color )
print( 'Volatility: ' + str(volatility) )
print()


# --algo=rsi, --algo=stochrsi
for algo in args.algo.split(','):

	algo = algo.lower()
	if ( algo != 'rsi' and algo != 'stochrsi'):
		print('Unsupported algorithm "' + str(algo) + '"')
		continue

	# Print results for the most recent 10 and 5 days of data
	for days in args.days.split(','):

		try:
			int(days)
		except:
			print('Error, days (' + str(days) + ') is not an integer - exiting.')
			exit(1)

		if ( int(days) > 10 ):
			days = 10 # TDA API only allows 10-days of 1-minute daily data


		# Pull the 1-minute stock history
		# Note: Not asking for extended hours for now since our bot doesn't even trade after hours
		try:
	        	data, epochs = tda_gobot_helper.get_pricehistory(stock, 'day', 'minute', '1', days, needExtendedHoursData=False, debug=False)

		except Exception as e:
			print('Caught Exception: get_pricehistory(' + str(ticker) + '): ' + str(e))
			continue

		if ( data == False ):
			continue
		if ( int(len(data['candles'])) <= rsi_period ):
			print('Not enough data - returned candles=' + str(len(data['candles'])) + ', rsi_period=' + str(rsi_period))
			exit(0)


		# Run the analyze function
		print('Analyzing ' + str(days) + '-day history for stock ' + str(stock) + ' using the ' + str(algo) + " algorithm:")

		if ( algo == 'rsi' ):
			results = tda_gobot_helper.rsi_analyze( pricehistory=data, ticker=stock, rsi_period=rsi_period, stochrsi_period=stochrsi_period, rsi_type=rsi_type,
								rsi_low_limit=rsi_low_limit, rsi_high_limit=rsi_high_limit, rsi_slow=rsi_slow, rsi_k_period=args.rsi_k_period, rsi_d_period=args.rsi_d_period,
								stoploss=args.stoploss, noshort=args.noshort, shortonly=args.shortonly, debug=True )

		elif ( algo == 'stochrsi' ):
			results = tda_gobot_helper.stochrsi_analyze( pricehistory=data, ticker=stock, stochrsi_period=stochrsi_period, rsi_period=rsi_period, rsi_type=rsi_type,
								     rsi_low_limit=20, rsi_high_limit=80, rsi_slow=rsi_slow, rsi_k_period=args.rsi_k_period, rsi_d_period=args.rsi_d_period,
								     stoploss=args.stoploss, noshort=args.noshort, shortonly=args.shortonly,
								     nocrossover=args.nocrossover, crossover_only=args.crossover_only, debug=True )

		if ( results == False ):
			print('Error: rsi_analyze() returned false', file=sys.stderr)
			exit(1)
		if ( int(len(results)) == 0 ):
			print('There were no possible trades for requested time period, exiting.')
			exit(0)


		# Print the returned results
		if ( algo == 'rsi' and args.verbose ):
			print("Buy/Sell Price    Net Change        VWAP              PREV_RSI/CUR_RSI  StochRSI          Time")
		elif ( algo == 'stochrsi' and args.verbose ):
			print("Buy/Sell Price    Net Change        VWAP              RSI_K/RSI_D       StochRSI          Time")

		rating = 0
		success = fail = 0
		net_gain = net_loss = 0
		counter = 0
		while ( counter < len(results) - 1 ):
			price_tx, short, vwap_tx, rsi_tx, stochrsi_tx, time_tx = results[counter].split( ',', 6 )
			price_rx, short, vwap_rx, rsi_rx, stochrsi_rx, time_rx = results[counter+1].split( ',', 6 )

			# Returned RSI format is "prev_rsi/cur_rsi"
			rsi_prev_tx,rsi_cur_tx = rsi_tx.split( '/', 2 )
			rsi_prev_rx,rsi_cur_rx = rsi_rx.split( '/', 2 )

			net_change = float(price_rx) - float(price_tx)
			if ( short == str(False) ):
				if ( float(net_change) <= 0 ):
					fail += 1
					net_loss += float(net_change)
				else:
					success += 1
					net_gain += float(net_change)
			else:
				if ( float(net_change) < 0 ):
					success += 1
					net_gain += abs(float(net_change))
				else:
					fail += 1
					net_loss -= float(net_change)

			price_tx = round( float(price_tx), 2 )
			price_rx = round( float(price_rx), 2 )

			net_change = round(net_change, 2)

			vwap_tx = round( float(vwap_tx), 2 )
			vwap_rx = round( float(vwap_rx), 2 )

			rsi_prev_tx = round( float(rsi_prev_tx), 1 )
			rsi_cur_tx = round( float(rsi_cur_tx), 1 )
			rsi_prev_rx = round( float(rsi_prev_rx), 1 )
			rsi_cur_rx = round( float(rsi_cur_rx), 1 )

			stochrsi_tx = round( float(stochrsi_tx), 4 )
			stochrsi_rx = round( float(stochrsi_rx), 4 )

			is_success = False
			if ( short == 'True' ):
				if ( net_change < 0 ):
					is_success = True

				price_tx = str(price_tx) + '*'
				price_rx = str(price_rx) + '*'

			else:
				if ( net_change > 0 ):
					is_success = True

			if ( args.verbose == True ):
				text_color = red
				if ( is_success == True ):
					text_color = green

				rsi_tx = str(rsi_prev_tx) + '/' + str(rsi_cur_tx)
				rsi_rx = str(rsi_prev_rx) + '/' + str(rsi_cur_rx)

				for i in [str(price_tx), ' ', str(vwap_tx), str(rsi_tx), str(stochrsi_tx), time_tx]:
					print(text_color + '{0:<18}'.format(i) + reset_color, end='')

				print()
				for i in [str(price_rx), str(net_change), str(vwap_rx), str(rsi_rx), str(stochrsi_rx), time_rx]:
					print(text_color + '{0:<18}'.format(i) + reset_color, end='')

				print()

			counter += 2


		# Rate the stock
		#   txs/day < 1				 = -1 point
		#   avg_gain_per_share < 1		 = -1 points
		#   success_pct < 10% higher than fail % = -2 points
		#   success_pct <= fail_pct		 = -4 points
		#   average_gain <= average_loss	 = -8 points
		#   shortable == False			 = -4 points
		#   marginable == False			 = -2 points
		#   delayed == True			 = -2 points
		#
		# Rating:
		#   0 			 = Very Good
		#   -1			 = Good
		#   <-2 & >-4		 = Poor
		#   <-3			 = Bad
		#   Success % <= Fail %  = FAIL
		#   Avg Gain <= Avg Loss = FAIL
		success_pct = (int(success) / int(len(results) / 2) ) * 100	# % Successful trades using algorithm
		fail_pct = ( int(fail) / int(len(results) / 2) ) * 100		# % Failed trades using algorithm
		txs = int(len(results) / 2) / int(days)				# Average buy or sell triggers per day

		average_gain = 0
		average_loss = 0
		if ( success != 0 ):
			average_gain = net_gain / success			# Average improvement in price using algorithm
		if ( fail != 0 ):
			average_loss = net_loss / fail				# Average regression in price using algorithm

		print()

		# Check number of transactions/day
		if ( txs < 1 ):
			rating -= 1
			text_color = red
		else:
			text_color = green

		print( 'Average txs/day: ' + text_color + str(round(txs,2)) + reset_color )

		# Compare success/fail percentage
		if ( success_pct <= fail_pct ):
			rating -= 4
			text_color = red
		elif ( success_pct - fail_pct < 10 ):
			rating -= 2
			text_color = red
		else:
			text_color = green

		print( 'Success rate: ' + text_color + str(round(success_pct, 2)) + reset_color )
		print( 'Fail rate: ' + text_color + str(round(fail_pct, 2)) + reset_color )

		# Compare average gain vs average loss
		if ( average_gain <= abs(average_loss) ):
			rating -= 8
			text_color = red
		else:
			text_color = green

		print( 'Average gain: ' + text_color + str(round(average_gain, 2)) + ' / share' + reset_color )
		print( 'Average loss: ' + text_color + str(round(average_loss, 2)) + ' / share' + reset_color )

		# Calculate the average gain per share price
		last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)
		if ( last_price != False ):
			avg_gain_per_share = float(average_gain) / float(last_price) * 100
			if ( avg_gain_per_share < 1 ):
				rating -= 1
				text_color = red
			else:
				text_color = green

			print( 'Average gain per share: ' + text_color + str(round(avg_gain_per_share, 3)) + '%' + reset_color )

		# Shortable / marginable / delayed / etc.
		if ( shortable == False ):
			rating -= 4
		if ( marginable == False ):
			rating -= 2
		if ( delayed == True ):
			rating -= 2

		# Print stock rating (see comments above)
		if ( success_pct <= fail_pct or average_gain <= average_loss ):
			rating = red + 'FAIL' + reset_color
		elif ( rating == 0 ):
			rating = green + 'Very Good' + reset_color
		elif ( rating == -1 ):
			rating = green + 'Good' + reset_color
		elif ( rating <= -4 ):
			rating = red + 'Bad' + reset_color
		elif ( rating <= -2 ):
			rating = red + 'Poor' + reset_color

		print( 'Stock rating: ' + str(rating) )
		print()

exit(0)
