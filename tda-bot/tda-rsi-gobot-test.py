#!/usr/bin/python3 -u

# Monitor a stock's RSI value and make purchase decisions based off that value.
#  - If the RSI drops below 30, then we monitor the RSI every minute until it
#      starts to increase again.
#  - When the RSI begins to rise again we run tda-gobot.py to purchase and
#      monitor the stock performance.

import os, subprocess
import time, datetime, pytz
import argparse

import robin_stocks.tda as tda
import tulipy as ti
import numpy as np
import tda_gobot_helper

# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("stock_usd", help='Amount of money (USD) to invest', nargs='?', default=1000, type=float)
parser.add_argument("-n", "--num_purchases", help="Number of purchases allowed per day", nargs='?', default=1, type=int)
parser.add_argument("-d", "--debug", help="Enable debug output", action="store_true")
args = parser.parse_args()

stock = args.stock
stock_usd = args.stock_usd
num_purchases = args.num_purchases

gobot_bin = '/home/steve/python-finance/tda-bot/tda-gobot.py'
debug = 0
loopt = 60

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


# tda.get_price_history() variables
eastern = pytz.timezone("US/Eastern")
pacific = pytz.timezone("US/Pacific")
p_type = 'day'
period = 10
f_type = 'minute'
freq = '1'

# RSI variables
rsiPeriod = 14
cur_rsi = 0
prev_rsi = 0


# TODO: Test during pre-market and trading day.
#       Monitor any delay in market data and quality of the data

# Helpful datetime conversion hints: convert epoch milisecond to string:
#   start = int( datetime.datetime.strptime('2021-03-26 09:30:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=eastern).timestamp() * 1000 )
#   datetime.datetime.fromtimestamp(<epoch>/1000).strftime('%Y-%m-%d %H:%M:%S.%f')
#   datetime.datetime.fromtimestamp(float(key['datetime'])/1000, tz=eastern).strftime('%Y-%m-%d %H:%M:%S.%f')
time_now = datetime.datetime.strptime('2021-03-26 09:30:00', '%Y-%m-%d %H:%M:%S').replace(tzinfo=eastern)
#	time_now = datetime.datetime.now(eastern)
time_prev = time_now - datetime.timedelta( minutes=int(freq)*(rsiPeriod * 10) ) # Subtract enough time to ensure we get an RSI for the current period
time_now_epoch = int( time_now.timestamp() * 1000 )
time_prev_epoch = int( time_prev.timestamp() * 1000 )

# Debug stuff
#print(time_now.strftime('%Y-%m-%d %H:%M:%S'))
#print(time_prev.strftime('%Y-%m-%d %H:%M:%S'))
#print(time_now_epoch)
#print(time_prev_epoch)

# {'open': 236.25, 'high': 236.25, 'low': 236.25, 'close': 236.25, 'volume': 500, 'datetime': 1616796960000}
#data,err = tda.get_price_history(stock, p_type, f_type, freq, period, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, jsonify=True)
data,err = tda.get_price_history(stock, p_type, f_type, freq, period, needExtendedHoursData=False, jsonify=True)
if ( err != None ):
	print('Error: get_price_history(' + str(stock) + ', ' + str(p_type) + ', ' + str(f_type) + ', ' + str(freq) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) +'): ' + str(err))
	time.sleep(5)
	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure')
		exit()


dates = []
close = []
keydates = []
for key in data['candles']:
	dates.append(float(key['datetime']))
	close.append(float(key['close']))

numdates = len(dates)

#dates = []
#for x in range(0,50):
#	dates.append(float(data['candles'][x]['datetime']))
#print(str(dates))
#exit()

for x in range(51, numdates):

	closePrices = []
	epochs = []
	for y in range(0, x):
		closePrices.append(float(data['candles'][y]['close']))
		epochs.append(float(data['candles'][y]['datetime']))

	if ( len(closePrices) < rsiPeriod ):
		# Something is wrong with the data we got back from tda.get_price_history()
		print('Error: closePrices is less than rsiPeriod')
		time.sleep(loopt)
		continue

	# Calculate the RSI for the entire numpy array
	pricehistory = np.array( closePrices )
	rsi = ti.rsi( pricehistory, period=rsiPeriod )

	cur_rsi = rsi[-1]
	if ( prev_rsi == 0 ):
		prev_rsi = cur_rsi
	if ( debug == 1 ):
		print('(' + str(stock) + ') Current RSI: ' + str(round(cur_rsi, 2)) + ', Previous RSI: ' + str(round(prev_rsi, 2)))
		print('(' + str(stock) + ') Time now: ' + time_now.strftime('%Y-%m-%d %H:%M:%S') +
			', timestamp received from API ' +
			datetime.datetime.fromtimestamp(float(epochs[-1])/1000).strftime('%Y-%m-%d %H:%M:%S.%f') +
			' (' + str(int(epochs[-1])) + ')' )

	# End of trading day - exit
#	if ( tda_gobot_helper.isendofday() == True or tda_gobot_helper.ismarketopen_US() == False ):
#		print('(' + str(stock) + ') Market closed, exiting.')
#		exit(0)

	# Nothing to do if RSI hasn't dropped below 30
	if ( cur_rsi > 30 and prev_rsi > 30 ):
		if ( debug == 1 ):
			print('(' + str(stock) + ') RSI is above 30 (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

	# RSI is dropping and has hit 30
	elif ( prev_rsi > 30 and cur_rsi <= 30 ):
		print('(' + str(stock) + ') RSI has dropped below 30 (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

	# Dropping RSI below 30
	elif ( prev_rsi <= 30 and cur_rsi < prev_rsi ):
		if ( debug == 1 ):
			print('(' + str(stock) + ') RSI below 30 and still dropping (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')

	# RSI was below 30 and is now rising
	# This is where we will run tda_gobot to purchase and monitor the stock
	elif ( prev_rsi < 30 and cur_rsi > prev_rsi ):
		print('(' + str(stock) + ') RSI below 30 and is now rising (' + str(round(prev_rsi, 2)) + ' / ' + str(round(cur_rsi, 2)) + ')')
		print('A purchase would have been made at this point ( ' + str(int(epochs[-1])) + ' / ' +
			datetime.datetime.fromtimestamp(float(epochs[-1])/1000, tz=pacific).strftime('%Y-%m-%d %H:%M:%S.%f') + ' )')
		print()

		prev_rsi = 0
		cur_rsi = 0

		keydates.append(float(epochs[-1]))
#		print('(' + str(stock) + ') Running tda-gobot to purchase stock ($' + str(stock_usd) + ' USD)')

#		subprocess.call( 'nohup ' + gobot_bin + ' ' + str(stock) + ' ' + str(stock_usd) + ' --incr_threshold 1.5 --decr_threshold 2 --notmarketclosed 1>>rsilog-' + str(stock) + '.txt 2>&1 &', shell=True )
#		num_purchases -= 1

	# Exit if we've exhausted our maximum number of purchases for the day
#	if ( num_purchases < 1 ):
#		print('(' + str(stock) + ') Max number of purchases exhuasted, exiting.')
#		exit(0)

	prev_rsi = cur_rsi


for x in range(0, numdates):
	if dates[x] in keydates:
		print(str(datetime.datetime.fromtimestamp(float(dates[x])/1000, tz=pacific).strftime('%Y-%m-%d %H:%M:%S.%f')) +
			'|' + str(close[x]) + '|' + str(close[x]))
	else:
		print(str(datetime.datetime.fromtimestamp(float(dates[x])/1000, tz=pacific).strftime('%Y-%m-%d %H:%M:%S.%f')) +
			'|' + str(close[x]))

print("\n")

for x in range(0, numdates):
	if dates[x] in keydates:
		print(str(datetime.datetime.fromtimestamp(float(dates[x])/1000, tz=pacific).strftime('%Y-%m-%d %H:%M:%S.%f')) +
			'|' + str(close[x]))


print()
print(keydates)




exit(0)
