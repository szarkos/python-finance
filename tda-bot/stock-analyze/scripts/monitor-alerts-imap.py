#!/usr/bin/python3

# Example:
#
#  ./monitor-alerts-imap.py --tda_alert_name='Gobot Stock Scanner - NATR' --ticker_group=HIGH_NATR

import os, sys
import re
import argparse
import array
import imaplib
import email

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../../')

parser = argparse.ArgumentParser()
parser.add_argument("--watchlist", help='Name of the watchlist', default=None)
parser.add_argument("--imap_user", help='Username of the email account to check', default='stonks', type=str)
parser.add_argument("--tda_alert_name", help='Name of the alert that should be on the subject line of the alert email', default=None, required=True, type=str)
parser.add_argument("--tickers_file", help='File that contains the list of tickers', default=parent_path + '/../tickers.conf', type=str)
parser.add_argument("--ticker_group", help='Name of the ticker group is the name of the variable to update in tickers.conf', default=None, type=str)
parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
args = parser.parse_args()

from dotenv import load_dotenv
if ( load_dotenv(dotenv_path=parent_path+'/../../.env') != True ):
	print('Error: unable to load .env file')
	sys.exit(1)

password = os.environ["stonks_password"]
try:
	mail = imaplib.IMAP4_SSL( host='mail.sentry.net', port=993 )
	mail.login( args.imap_user, str(password) )

except Exception as e:
	print( 'IMAP login failure (' + str(args.imap_user) + ': ' + str(e) )
	sys.exit(1)

mail.list()
mail.select( "Inbox" )
result, data = mail.search( None, 'UnSeen', '(FROM "alerts@thinkorswim.com" SUBJECT "' + str(args.tda_alert_name) + '")' )

add = remove = ''
if ( len(data[0]) != 0 ):

	for num in data[0].decode().split():
		result, data = mail.fetch(num, '(RFC822)')
		message = email.message_from_bytes(data[0][1])
		subject = message.get("Subject")

		if ( args.watchlist != None and re.search(args.watchlist, subject) == None ):
			continue

		raw_email = data[0][1]
		if ( args.debug == 1 ):
			print(str(raw_email) + "\n\n")

		# Mark email as read
		mail.store( num, '+FLAGS', '\Seen' )

		# Example subject line for alert:
		#    Alert: SAZ - Gobot Stock Scanner - NATR updated. Following list of
		#      symbols were added to SAZ - Gobot Stock Scanner - NATR: AOS, APPS, CHWY,
		#      TWLO, WOLF. Following list of symbols were removed from SAZ - Gobot Stock
		#      Scanner - NATR: ALKS, BYND, CCJ, FNGU, HUDI, NFE, PAGS, PDD, PTON, SDIG,
		#      TMHC, ZIM.
		changes	= []
		subject = re.sub( '[\r\n]', '', subject )
		changes = re.split( ' Following ', subject )
		for idx in range(1, len(changes)):
			if ( re.search('added', changes[idx]) ):
				add = changes[idx]
				add = re.sub( 'list of symbols were added .*: ', '', add )
				add = re.sub( '\..*', '', add )
			elif ( re.search('removed', changes[idx]) ):
				remove = changes[idx]
				remove = re.sub( 'list of symbols were removed .*: ', '', remove )
				remove = re.sub( '\..*', '', remove )

mail.close()
mail.logout()

if ( add == '' and remove == '' ):
	sys.exit(0)


# Just print the added and removed lines of a ticker group wasn't specified
if ( args.ticker_group == None ):
	print(add)
	print(remove)
	sys.exit(0)

# Read in the contents of the tickers.conf file
try:
	with open(args.tickers_file, 'rt') as fh:
		data = fh.read()

except Exception as e:
	print('Error opening file ' + str(args.tickers_file) + 'for reading: ' + str(e))
	sys.exit(1)


# Find the line that matches the ticker_group, and add or remove any tickers
newdata = []
add	= re.split( '\s*,\s*', add )
remove	= re.split( '\s*,\s*', remove )
for line in data.splitlines():

	if ( re.search(args.ticker_group + '=', line) != None ):
		line = line.rstrip('\n')
		line = re.sub('[\'"\s\t]', '', line)
		( varname, tickers ) = re.split('=', line, 2)

		tickers = re.split(',', tickers)
		for i in add:
			tickers.append(i)

		for idx,i in enumerate(tickers):
			if ( i in remove ):
				tickers[idx] = ''

		# Remove empty elements in tickers
		tickers = [var for var in tickers if var]

		# Remove any duplicate elements in tickers and turn tickers into
		#  a comma-delimited string
		tickers = list( dict.fromkeys(tickers) )
		tickers = sorted(tickers)
		tickers = ','.join(tickers)

		line = str(varname) + '="' + str(tickers) + '"'

	newdata.append(line)

# Write back out the file
try:
	with open(args.tickers_file, 'wt') as fh:
		for line in newdata:
			fh.write( line + "\n" )

except Exception as e:
	print('Error opening file ' + str(args.tickers_file) + ' for writing: ' + str(e))
	sys.exit(1)


sys.exit(0)
