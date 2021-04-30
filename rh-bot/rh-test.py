#!/usr/bin/python3 -u

import robin_stocks.robinhood as rh
import os, time
import pyotp
import pprint

stock = 'TKAT'

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
	print('Error: unable to load .env file')
	exit(1)

rh_username = os.environ['rh_username']
rh_password = os.environ['rh_password']
rh_2fa_auth = os.environ['rh_2fa_auth']

totp  = pyotp.TOTP("T6M4XOJXMAIPFUBT").now()
login = rh.login(rh_username, rh_password, mfa_code=totp)


try:
	data = rh.stocks.find_instrument_data(stock)
except Exception as e:
	print('Exception: find_instrument_data(): ' + str(e))
else:
	pp = pprint.PrettyPrinter(indent=4)
	pp.pprint(data)


print()
time.sleep(1)
try:
	data = rh.stocks.get_fundamentals(stock)
except Exception as e:
	print('Exception: get_fundamentals(): ' + str(e))
else:
	pp = pprint.PrettyPrinter(indent=4)
	pp.pprint(data)


print()
time.sleep(1)
try:
	data = rh.stocks.get_instruments_by_symbols(stock)
except Exception as e:
	print('Exception: get_instruments_by_symbols(): ' + str(e))
else:
	pp = pprint.PrettyPrinter(indent=4)
	pp.pprint(data)


print()
time.sleep(1)
try:
	data = rh.stocks.get_ratings(stock)
except Exception as e:
	print('Exception: get_ratings(): ' + str(e))
else:
	pp = pprint.PrettyPrinter(indent=4)
	pp.pprint(data)


print()
time.sleep(1)
try:
	data = rh.stocks.get_stock_quote_by_symbol(stock)
except Exception as e:
	print('Exception: get_stock_quote_by_symbol(): ' + str(e))
else:
	pp = pprint.PrettyPrinter(indent=4)
	pp.pprint(data)




