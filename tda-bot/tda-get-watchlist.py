#!/usr/bin/python3 -u

import os, sys
import json
import argparse

import tda as tda_api
from tda.client import Client
import json

import tda_api_helper

parser = argparse.ArgumentParser()
parser.add_argument("watchlist_name", help='Watchlist name', nargs='?', default=None, type=str)
args = parser.parse_args()

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        sys.exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]
tda_api_key = os.environ['tda_consumer_key']
tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'

try:
        tda_client = tda_api.auth.client_from_token_file(tda_pickle, tda_api_key)

except Exception as e:
        print('Exception caught: client_from_token_file(): unable to log in using tda-client: ' + str(e))
        sys.exit(0)

data = []
watchlist_id = ''
try:
	if ( args.watchlist_name == None ):
		data = tda_client.get_watchlists_for_single_account(tda_account_number)
	else:
		watchlist_id = tda_api_helper.get_watchlist_id(tda_client=tda_client, tda_account=tda_account_number, watchlist_name=args.watchlist_name)
		data = tda_client.get_watchlist(tda_account_number, watchlist_id)

	if ( data.status_code != 201 ):
		print('Error: tda_client.get_watchlist(' + str(args.watchlist_name) + '): returned status code ' + str(data.status_code))

except Exception as e:
	print('Caught exception: tda_client.get_watchlist(' + str(args.watchlist_name) + '): ' + str(e))
	sys.exit(1)

data = data.json()
print(json.dumps(data, indent=4))
sys.exit(0)

