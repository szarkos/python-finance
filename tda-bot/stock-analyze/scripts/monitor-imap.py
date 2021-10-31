#!/usr/bin/python3

import os, sys
import re
import argparse
import imaplib
import email

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../../')

parser = argparse.ArgumentParser()
parser.add_argument("--watchlist", help='Name of the watchlist', default=None)
parser.add_argument("--imap_user", help='Username of the email account to check', default='stonks')
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

#result, data = mail.search( None, 'UnSeen', '(SUBJECT "Alert")' )
result, data = mail.search( None, 'UnSeen', '(FROM "alerts@thinkorswim.com")' )
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
		add	= ''
		remove	= ''

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

		print(add)
		print(remove)

mail.close()
mail.logout()

sys.exit(0)
