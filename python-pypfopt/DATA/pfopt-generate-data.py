#!/usr/bin/python3

import sys, re
import pandas as pd
import pandas_datareader as web
from datetime import datetime

## This script takes a list of tickers in a CSV file and collects
## price history.
##   Usage: pfopt-generate-data.py <tickers.csv> <stockStartDate>

debug = 0

stockStartDate = str( sys.argv[2] )
today = datetime.today().strftime('%Y-%m-%d')

infile = str( sys.argv[1] )

outfile = re.sub( 'nasdaq_screener_', '', infile )
outfile = re.sub( '\.csv', '', outfile )
outfile = str(outfile) + '-AdjClose-' + str(today) + '.csv'

ticker = pd.read_csv( infile, squeeze=True )['Symbol']
ticker = ticker.values.tolist()
if debug == 1:
	print(ticker)

df = pd.DataFrame()
for symbol in ticker:
	symbol = symbol.strip()
	print(symbol)
	df[symbol] = web.DataReader(symbol, data_source='yahoo', start=stockStartDate, end=today)['Adj Close']

if debug == 1:
	print(df)

df.to_csv(outfile)

