#!/usr/bin/python3

## Usage: pfopt-real.py <Stock Price History CSV>

import sys
import pandas as pd
import numpy as np
import requests
import time

debug = 0
plot_graphs = 0
portfolio_value = 15000

# Get the stock data
infile = str(sys.argv[1])
df = pd.DataFrame()
df = pd.read_csv(infile)

df = df.set_index(pd.DatetimeIndex(df['Date'].values))
df.drop(columns=['Date'], axis=1, inplace=True)

if debug == 1:
	print("Stock Price Data")
	print(df)

assets = df.columns

# Helper function to get the company name from a stock symbol
def get_company_name(symbol):
	url = 'http://d.yimg.com/autoc.finance.yahoo.com/autoc?query=' + str(symbol) + '&region=1&lang=en'
	result = requests.get(url).json()
	for r in result['ResultSet']['Result']:
		if r['symbol'] == symbol:
			return r['name']


# PyPortfolioOpt
from pypfopt.discrete_allocation import DiscreteAllocation,get_latest_prices
from pypfopt import risk_models
from pypfopt import expected_returns

import portfolio_optimizer_helpers
portfolio_optimizer_helpers.portfolio_value = portfolio_value
portfolio_optimizer_helpers.df = df
portfolio_optimizer_helpers.np = np
portfolio_optimizer_helpers.pd = pd

# Expected returns - anualized sample covariance matrix of asset returns
# NOTE: From what I've read, calculating returns based on past mean returns
#   is mostly useless. Better to use min_volatility() or HRP model.
#
#   Mean historical
#   mu = expected_returns.mean_historical_return(df, span=500)
#
#   Exponentially-weighted mean of (daily) historical returns, giving higher
#     weight to more recent data.
#   mu = expected_returns.ema_historical_return(df)
#
#   Capital Asset Pricing Model
#   mu = expected_returns.capm_return(df)
#
#mu = expected_returns.mean_historical_return(df)
#mu = expected_returns.ema_historical_return(df, span=500)
mu = expected_returns.capm_return(df)

# Annualized sample covariance matrix of the daily asset returns
#rm = risk_models.sample_cov(df)
rm = risk_models.CovarianceShrinkage(df).ledoit_wolf()

# Efficient Frontier Optimisation
#ef, da, weights = portfolio_optimizer_helpers.efopt(mu, rm, model='sharpe', print_alloc=False, plot=False, debug=0)
#ef, da, weights = portfolio_optimizer_helpers.efopt(mu, rm, model='nonconvex', print_alloc=False, plot=False, debug=0)
#ef, da, weights = portfolio_optimizer_helpers.efopt(mu, rm, model='min_volitility', print_alloc=False, plot=False, debug=0)
#for alg in ['nonconvex', 'sharpe', 'min_volitility']:
#for alg in ['nonconvex']:
for alg in ['min_volitility']:

	print('**** Efficient Frontier (' + str(alg) + ') ****')
	ef, da, weights = portfolio_optimizer_helpers.efopt(mu, rm, model=alg, print_alloc=False, plot=False, debug=0)

	if debug == 1:
		cleaned_weights = ef.clean_weights()
		print('## Cleaned Weights ##')
		print(cleaned_weights)

	allocation, leftover = da.lp_portfolio()

	print("\nPortfolio Value: $" + str(portfolio_value) + " USD\n")
#	print('Discrete Allocation: ', allocation)

	# Print the result
	company_name = []
	discrete_allocation_list = []
	for symbol in allocation:
		company_name.append( get_company_name(symbol) )
		discrete_allocation_list.append( allocation.get(symbol) )

	portfolio_df = pd.DataFrame( columns = ['Company_Name', 'Company_Ticker', 'Discrete_Val_' + str(portfolio_value)] )
	portfolio_df['Company_Name'] = company_name
	portfolio_df['Company_Ticker'] = allocation
	portfolio_df['Discrete_Val_' + str(portfolio_value)] = discrete_allocation_list

	pd.set_option('display.max_rows', None)
	pd.set_option('display.max_columns', None)
	pd.set_option('display.width', None)
	pd.set_option('display.max_colwidth', -1)

	print(portfolio_df)
	print("\nFunds remaining: ${:.2f}".format(leftover)+"\n")


exit(0)

# Hierarchical Risk Parity
#returns = df.pct_change() # Daily simple return
#hrp, da, weights = portfolio_optimizer_helpers.hrpopt(returns, print_alloc=False, plot=False, debug=0)
print('**** Hierarchical Risk Parity ****')
returns = df.pct_change() # Daily simple return
hrp, da, weights = portfolio_optimizer_helpers.hrpopt(returns, print_alloc=False, plot=False, debug=0)

if debug == 1:
	cleaned_weights = hrp.clean_weights()
	print('## Cleaned Weights ##')
	print(cleaned_weights)

allocation, leftover = da.lp_portfolio()

print("\nPortfolio Value: $" + str(portfolio_value) + " USD\n")
#print('Discrete Allocation: ', allocation)

# Print the result
company_name = []
discrete_allocation_list = []
for symbol in allocation:
	company_name.append( get_company_name(symbol) )
	discrete_allocation_list.append( allocation.get(symbol) )

portfolio_df = pd.DataFrame( columns = ['Company_Name', 'Company_Ticker', 'Discrete_Val_' + str(portfolio_value)] )
portfolio_df['Company_Name'] = company_name
portfolio_df['Company_Ticker'] = allocation
portfolio_df['Discrete_Val_' + str(portfolio_value)] = discrete_allocation_list

print(portfolio_df)
print("\nFunds remaining: ${:.2f}".format(leftover)+"\n")


# Critical Line Algorithm
#cla, da, weights = portfolio_optimizer_helpers.claopt(mu, rm, model='sharpe', print_alloc=False, plot=False, debug=0)
#cla, da, weights = portfolio_optimizer_helpers.claopt(mu, rm, model='min_volitility', print_alloc=False, plot=False, debug=0)


