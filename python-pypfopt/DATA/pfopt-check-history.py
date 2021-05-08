#!/usr/bin/python3

import sys
import pandas as pd
import pandas_datareader as web
from datetime import datetime

## Usage: pfopt-check-history.py ticker

debug = 0

#today = datetime.today().strftime('%Y-%m-%d')
stockStartDate = '2013-01-01'
stockEndDate = '2013-01-02'

ticker = str( sys.argv[1] )
ticker = ticker.strip()

#print(ticker)

df = pd.DataFrame()
try:
	df[ticker] = web.DataReader(ticker, data_source='yahoo', start=stockStartDate, end=stockEndDate)['Adj Close']
except:
	print(str(ticker)+": No Data")
	exit()

if debug == 1:
	print(df)

