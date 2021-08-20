#!/usr/bin/python3 -u

#curl -u shortstock: ftp://ftp3.interactivebrokers.com/usa.txt > usa-<date>.txt

import os, sys
import datetime, pytz
import argparse
import re
import json

from subprocess import Popen, PIPE, STDOUT

parser = argparse.ArgumentParser()
parser.add_argument("--ifile", help='Short availability file to read', type=str)
parser.add_argument("--cur_ifile", help='Short availability file to read', default=None, type=str)
parser.add_argument("--download", help='Download the current short inventory', action="store_true")
parser.add_argument("--short_pct", help='Percent decline needed for notification', default=10, type=int)

args = parser.parse_args()

# Only download the current file
if ( args.download == True ):

	mytimezone = pytz.timezone('US/Eastern')
	today = datetime.datetime.now(mytimezone).strftime('%Y-%m-%d')

	command = 'curl -o ./data/usa-' + str(today) + '.txt --silent -u shortstock: ftp://ftp3.interactivebrokers.com/usa.txt'
	process = ''
	try:
		process = Popen(command, stdin=None, stdout=None, stderr=STDOUT, shell=True)

	except Exception as e:
		print('Error: unable to run curl command: ' + str(e))
		exit(1)

	process.wait()

	exit(0)


prev_data = {}
cur_data = {}

# Open and read contents of ifile
try:
	fh = open( args.ifile, "rt" )

except OSError as e:
	print('Error: Unable to open file ' + str(args.ifile) + ': ' + e, file=sys.stderr)
	exit(1)

for line in fh:
	line = line.split('|')

	try:
		line[7]
	except:
		continue

	if ( re.search('[\>0-9]+', line[7]) == None ):
		continue

	ticker = line[0]
	short = line[7]
	short = re.sub( '>', '', short )

	prev_data[ticker] = int( short )

fh.close()


# Open cur_ifile if specified, do not download the current data
if ( args.cur_ifile != None ):
	try:
		fh = open( args.cur_ifile, "rt" )

	except OSError as e:
		print('Error: Unable to open file ' + str(args.cur_ifile) + ': ' + e, file=sys.stderr)
		exit(1)

	for line in fh:
		line = line.split('|')

		try:
			line[7]
		except:
			continue

		if ( re.search('[\>0-9]+', line[7]) == None ):
			continue

		ticker = line[0]
		short = line[7]
		short = re.sub( '>', '', short )

		cur_data[ticker] = int( short )

	fh.close()

else:

	command = 'curl --silent -u shortstock: ftp://ftp3.interactivebrokers.com/usa.txt'
	err = ''
	try:
		process = Popen( command, stdin=None, stdout=PIPE, stderr=STDOUT, shell=True )
		output, err = process.communicate()

	except Exception as e:
		print('Error: unable to run curl command: ' + str(e))
		exit(1)

	if ( err != None and err != '' ):
		print('Error: ' + str(err))
		exit(1)

	process.wait()
	output = str(output).split('\\r\\n')
	for line in output:

		line = line.split('|')

		try:
			line[7]
		except:
			continue

		if ( re.search('[\>0-9]+', line[7]) == None ):
			continue

		ticker = line[0]
		short = line[7]
		short = re.sub( '>', '', short )

		cur_data[ticker] = int( short )


# Compare prev_data with cur_data
short_data = {}
tickers = []
for ticker in prev_data:

	if ticker not in cur_data:
		continue

	if ( re.search('[\s\t]', ticker) != None ):
		continue

	prev_short = int( prev_data[ticker] )
	cur_short = int( cur_data[ticker] )

	if ( prev_short < 50000 ):
		continue
	if ( cur_short >= 50000 ):
		continue

	if ( cur_short < prev_short ):
		if ( abs(cur_short / prev_short * 100 - 100) > args.short_pct ):
#			print('(' + str(ticker) + ') short availability decreased greater than ' + str(args.short_pct) + '% (' + str(cur_short) + '/' + str(prev_short) + ')')
#			print(str(ticker) + ':' + str(cur_short) + ':' + str(prev_short))
			short_data.update( { ticker: {  'cur_short': cur_short,
							'prev_short': prev_short }} )


# Obtain quote information about all these stocks
command = '../tda-bot/tda-quote-stock.py --stocks=' + str( ','.join(list(short_data.keys())) )
process = Popen( command, stdin=None, stdout=PIPE, stderr=STDOUT, shell=True )
output, err = process.communicate()

# Fixup output - needs to be json compliant
# Single quotes should be double quotes
# True|False strings need to be quoted
output = output.decode()
p = re.compile('(?<!\\\\)\'')
output = p.sub('\"', output)

output = re.sub('[a-zA-Z]"s', '\'s', output)
output = re.sub('[a-zA-Z]s" [a-zA-Z]', 's\'', output)
output = re.sub('L"Air', 'L\'Air', output)

#output = re.sub('L"[a-zA-Z] ', '', output) # Handle french names like L"Air or L"Oreal
output = re.sub('L"Air', '', output)
output = re.sub('L"Oreal ', '', output)

output = re.sub('True', '"True"',  output)
output = re.sub('False', '"False"',  output)
output = re.sub('None', '"None"',  output)

# Import as json
#print(output)
quote_data = json.loads(output)

print('Ticker,Current Avail Shorts,Previous Avail Shorts,Total Volume,Last Price,52WkHigh,52WkLow,Exchange')
for ticker in quote_data.keys():

	# Filter out BATS, Pink Sheet and other non NYSE or Nasdaq exchanges
	if ( quote_data[ticker]['exchangeName'] != 'NASD' and quote_data[ticker]['exchangeName'] != 'NYSE' ):
		continue

	if ( float(quote_data[ticker]['totalVolume']) < 1000000 ):
		continue

	out = 	str(ticker) + ',' + \
		str(short_data[ticker]['cur_short']) + ',' + \
		str(short_data[ticker]['prev_short']) + ',' + \
		str(quote_data[ticker]['totalVolume']) + ',' + \
		str(quote_data[ticker]['lastPrice']) + ',' + \
		str(quote_data[ticker]['52WkHigh']) + ',' + \
		str(quote_data[ticker]['52WkLow']) + ',' + \
		str(quote_data[ticker]['exchangeName'])

	print(out)


sys.exit(0)
