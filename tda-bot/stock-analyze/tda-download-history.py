#!/usr/bin/python3 -u

import os, sys, time
import argparse
import json, pickle

import robin_stocks.tda as tda

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper

parser = argparse.ArgumentParser()
parser.add_argument("--stocks", help='Stock ticker data to download (comma-delimited)', required=True)
parser.add_argument("--chart_freq", help='Frequency of chart data (daily, weekly, monthly)', default=None, required=True, type=str)
parser.add_argument("--period_type", help='Period type (typicaly "year")', default='year', type=str)
parser.add_argument("--periods", help='Number of periods (Default: 2)', default='2', type=str)
parser.add_argument("--extended_hours", help='Obtain extended trading hour data if available', action="store_true")
parser.add_argument("--odir", help='Directory to store output files', default=None, type=str)
args = parser.parse_args()

# Log into TDA
from dotenv import load_dotenv
if ( load_dotenv(dotenv_path=parent_path+'/../.env') != True ):
	print('Error: unable to load .env file', file=sys.stderr)
	sys.exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda = tda
tda_gobot_helper.tda_account_number = tda_account_number
tda_gobot_helper.passcode = passcode

if ( tda_gobot_helper.tdalogin(passcode) != True ):
	print('Error: Login failure', file=sys.stderr)
	sys.exit(1)


# get_pricehistory() variables
p_type	= args.period_type
period	= args.periods
freq	= '1'

if ( args.chart_freq == 'weekly' ):
	f_type = 'weekly'
elif ( args.chart_freq == 'daily' ):
	f_type = 'daily'
else:
	print('Error: unknown chart frequency "' + str(args.chart_freq) + '"', file=sys.stderr)
	sys.exit(1)


# Iterate over tickers and download data from TDA
for ticker in args.stocks.split(','):
	print('Downloading ' + str(args.chart_freq) + ' data for ticker ' + str(ticker))
	time.sleep(1) # Try to avoid throttling

	data_ph	= []
	ep	= []

	tries	= 0
	while ( tries < 3 ):
		data_ph, ep = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, needExtendedHoursData=args.extended_hours)
		if ( (isinstance(data_ph, bool) and data_ph == False) or str(data_ph['empty']).lower() == 'true' ):
			print('Error: get_pricehistory(' + str(ticker) + '): attempt ' + str(tries) + ' returned False, retrying...', file=sys.stderr)
			tda_gobot_helper.tdalogin(passcode)
			time.sleep(5)
		else:
			break

		tries += 1

	if ( isinstance(data_ph, bool) and data_ph == False ):
		print('Error: get_pricehistory(' + str(ticker) + '): unable to retrieve weekly data, exiting...', file=sys.stderr)
		sys.exit(1)

	if ( str(data_ph['empty']).lower() == 'true' ):
		print('Error: get_pricehistory(' + str(ticker) + '): pricehistory data is empty', file=sys.stderr)


	# Dump pickle data if requested
	if ( args.odir != None ):
		outfile = args.odir + '/' + str(ticker) + '-' + str(f_type) + '-2019-2021'
		try:
			file = open(str(outfile) + '.pickle', "wb")
			pickle.dump(data_ph, file)
			file.close()

		except Exception as e:
			print('Error: Unable to write to file ' + str(outfile) + '.pickle: ' + str(e))
			sys.exit(1)

		try:
			file = open(str(outfile) + '.json', 'wt')
			data_ph = json.dumps(data_ph, indent=4)
			print(data_ph, file=file, flush=True)
			file.close()

		except Exception as e:
			print('Error: Unable to write to file ' + str(outfile) + '.json: ' + str(e))
			sys.exit(1)

	else:
		# If no odir then dump the data to the screen I guess
		data_ph = json.dumps(data_ph, indent=4)
		print(data_ph)


sys.exit(0)
