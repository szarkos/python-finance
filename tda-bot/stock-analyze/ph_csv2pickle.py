#!/usr/bin/python3 -u

# Parse the monthly data from alphavantage, format it as a
#  TDA dict, and output data as a pickle data file.
# https://www.alphavantage.co/documentation/#intraday-extended

import os, sys, time
import argparse
import datetime, pytz
import re
import pickle

# Some acrobatics to import tda_gobot_helper from the upper-level directory
parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import robin_stocks.tda as tda
import tda_gobot_helper

parser = argparse.ArgumentParser()
parser.add_argument("ifile", help='CSV file to read', type=str)
parser.add_argument("ofile", help='Pickle file to write (default is ifile with .pickle extension)', nargs='?', default=None, type=str)
parser.add_argument("--augment_today", help='Augment Alphavantage history with the most recent day of 1min candles using the TDA API', action="store_true")
parser.add_argument("--debug", help='Enable debug output (prints entire pricehistory)', action="store_true")
args = parser.parse_args()

mytimezone = pytz.timezone("US/Eastern")

ticker = re.sub('^.*\/', '', args.ifile)
ticker = re.sub('\-.*$', '', ticker)

pricehistory = {'candles':	[],
		'symbol':	str(ticker),
		'empty':	'False'
}

date_fmt = '%Y-%m-%d %H:%M:%S'
if ( re.search('(daily|weekly)', args.ifile) != None ):
	date_fmt = '%Y-%m-%d'

try:

	with open(args.ifile, 'r') as handle:
		for line in handle:
			line = re.sub('[\r\n]*', '', line)

			# Log format:
			# time,open,high,low,close,volume
			# 2021-03-12 19:51:00,31.44,31.45,31.44,31.45,350
			#
			# Note: weekly data does not include %H:%M:%S
			time_t,open,high,low,close,volume = line.split(',')

			if ( time_t == 'time' ):
				continue

			time_t = datetime.datetime.strptime(time_t, date_fmt)
			time_t = mytimezone.localize(time_t)
			time_t = time_t.timestamp() * 1000

			candle_data = { 'open':		float( open ),
					'high':		float( high ),
					'low':		float( low ),
					'close':	float( close ),
					'volume':	int( volume ),
					'datetime':	time_t }

			pricehistory['candles'].append(candle_data)

	handle.close()
	del(time_t,open,high,low,close,volume)

except Exception as e:
	print('Error opening file ' + str(args.ifile) + ': ' + str(e))
	sys.exit(1)

# Alphavantage 1min history data will typically include only up to the last
#  trading day of data. Augment Alphavantage's history with the most recent
#  day of 1min candles using TDA's API.
if ( args.augment_today == True ):

	# Initialize and log into TD Ameritrade
	from dotenv import load_dotenv

	parent_path = os.path.dirname( os.path.realpath(__file__) )
	if ( load_dotenv(dotenv_path=parent_path+'/../.env') != True ):
		print('Error: unable to load .env file', file=sys.stderr)
		sys.exit(1)

	tda_account_number			= int( os.environ["tda_account_number"] )
	passcode				= os.environ["tda_encryption_passcode"]

	tda_gobot_helper.tda			= tda
	tda_gobot_helper.tda_account_number	= tda_account_number
	tda_gobot_helper.passcode		= passcode

	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure', file=sys.stderr)
		sys.exit(1)

	# Download the latest candles from TDA's API
	time_now = datetime.datetime.now( mytimezone )

	today = time_now.strftime('%Y-%m-%d')
	time_prev = datetime.datetime.strptime(today + ' 04:00:00', '%Y-%m-%d %H:%M:%S')
	time_prev = mytimezone.localize(time_prev)

	# Make sure start and end dates don't land on a weekend
	#  or outside market hours
#	time_now = tda_gobot_helper.fix_timestamp(time_now)
#	time_prev = tda_gobot_helper.fix_timestamp(time_prev)

	time_now_epoch = int( time_now.timestamp() * 1000 )
	time_prev_epoch = int( time_prev.timestamp() * 1000 )

	ph_data = epochs = False
	p_type = 'day'
	period = None
	f_type = 'minute'
	freq = '1'

	tries = 0
	while ( tries < 3 ):
		try:
			ph_data, epochs = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=True)

		except Exception as e:
			print('Caught Exception: get_pricehistory(' + str(ticker) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e) + ', exiting.', file=sys.stderr)
			sys.exit(1)

		if ( isinstance(ph_data, bool) and ph_data == False ):
			print('Error: get_pricehistory(' + str(ticker) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): attempt ' + str(tries) + ' returned False, retrying...', file=sys.stderr)
			time.sleep(5)

		else:
			break

		tries += 1

	if ( ph_data == False ):
		print('Error: get_pricehistory(' + str(ticker) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): returned False, exiting.', file=sys.stderr)
		sys.exit(1)


	# Append the TDA pricehistory to pricehistory['candles'] obtained from Alphavantage
	if ( int(ph_data['candles'][0]['datetime']) < int(pricehistory['candles'][-1]['datetime']) ):
		print('Error: augment_today: first timestamp from TDA is less than the last timestamp from Alphavantage (' + str(ph_data['candles'][0]['datetime']) + ' / ' + str(pricehistory['candles'][-1]['datetime']) + '), exiting.', file=sys.stderr)
		sys.exit(1)

	pricehistory['candles'] = pricehistory['candles'] + ph_data['candles']


# Sanity check that candle entries are properly ordered
prev_time = 0
for key in pricehistory['candles']:
	time = int( key['datetime'] )
	if ( prev_time != 0 ):
		if ( time < prev_time ):
			print('(' + str(ticker) + '): Error: timestamps out of order! Exiting.', file=sys.stderr)
			sys.exit(1)

	prev_time = time

if ( args.debug == True ):
	import pprint

	pp = pprint.PrettyPrinter(indent=4)
	for idx,key in enumerate(pricehistory['candles']):
		data = pricehistory['candles'][idx]
		data['datetime'] = datetime.datetime.fromtimestamp(data['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S')
		pp.pprint(data)

if ( args.ofile == None ):
	args.ofile = re.sub('\.csv', '', args.ifile)
	args.ofile = str(args.ofile) + '.pickle'

try:
	file = open(args.ofile, "wb")
	pickle.dump(pricehistory, file)
	file.close()

except Exception as e:
	print('Unable to write to file ' + str(args.ofile) + ': ' + str(e))


sys.exit(0)
