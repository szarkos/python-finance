#!/usr/bin/python3

import os
import imaplib
import subprocess
import time

debug = 0
stonkbot = '/home/steve/python-finance/stonk-mailparse/stonk-mailparse.pl'

from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file')
        exit(1)

password = os.environ["stonks_password"]


while ( True ):
	try:
		mail = imaplib.IMAP4_SSL( host='mail.sentry.net', port=993 )
		mail.login( 'stonks', str(password) )
	except Exception as e:
		print('Login failure: '+ str(e))
		time.sleep(30)
		continue

	mail.list()
	mail.select( "Inbox" )

	#result, data = mail.search( None, '(SUBJECT "Deadnsyde")' )
	result, data = mail.search( None, 'UnSeen', '(SUBJECT "Deadnsyde")' )
	if ( len(data[0]) != 0 ):

		for num in data[0].split():
			result, data = mail.fetch(num, '(RFC822)')
			mail.store( num, '+FLAGS', '\\Seen' )

			raw_email = data[0][1]
			if ( debug == 1 ):
				print(str(raw_email) + "\n\n")

			p = subprocess.Popen( [stonkbot], stdin=subprocess.PIPE, text=False )
			stdout_data = p.communicate( input=raw_email )[0]

	mail.close()
	mail.logout()

	time.sleep(15)


exit(0)
