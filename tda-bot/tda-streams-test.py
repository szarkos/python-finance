#!/usr/bin/python3 -u

import tda as tda_api
from tda.client import Client
from tda.streaming import StreamClient

import os, sys, time
import asyncio
import json


# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv() != True ):
        print('Error: unable to load .env file')
        exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]
tda_api_key = os.environ['tda_consumer_key']
tda_pickle = os.environ['HOME'] + '/.tokens/tda2.pickle'
tda_redirect_uri = 'https://127.0.0.1:8080'

#tda_gobot_helper.tda = tda
#tda_gobot_helper.tda_account_number = tda_account_number
#tda_gobot_helper.passcode = passcode

#if ( tda_gobot_helper.tdalogin(passcode) != True ):
#	print('Error: Login failure')
#	exit(1)


try:
	tda_client = tda_api.auth.client_from_token_file(tda_pickle, tda_api_key)

except Exception as e:
	print(e)

############################
# Streaming client

tickers = [ 'EEENF',
'FRSX',
'NAOV',
'MARA',
'CLSK',
'ACY',
'FBRX',
'TME',
'MVIS',
'EDIT',
'OCGN',
'GOEV',
'MGNI',
'ASO',
'CSCW',
'NAPA',
'AMRS',
'EXPI',
'ENTX',
'CPNG',
'UNFI',
'UTZ',
'SRNGU',
'DKNG',
'PENN',
'AYRO',
'CWGYF',
'LGHL',
'VRTX',
'LYSCF',
'NXPI',
'MU',
'HOL',
'BRQS',
'ASLE',
'PULM',
'CLNE',
'FCEL',
'CTXR',
'EXPC',
'ACIC',
'ESGC',
'CIG',
'SGRP',
'REPH',
'SECO',
'PAYS',
'GLOP',
'SRAC',
'ETWO',
'DRRX' ]

tickers = ['MSFT']

def do_stuff(msg=None):
	print(json.dumps(msg, indent=4))
	print('start')
	time.sleep(60)
	print('stop')


stream_client = StreamClient(tda_client, account_id=tda_account_number)
async def read_stream():
	await stream_client.login()
	await stream_client.quality_of_service(StreamClient.QOSLevel.SLOW)

	stream_client.add_chart_equity_handler(
		lambda msg: print(json.dumps(msg, indent=4)))
#		lambda msg: do_stuff(msg) )

	await stream_client.chart_equity_subs( tickers )

	while True:
		await stream_client.handle_message()


asyncio.run(read_stream())


