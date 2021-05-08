#!/usr/bin/python3

from pandas_datareader import data as web
import pandas as pd
import numpy as np
from datetime import datetime

import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
plt.style.use('fivethirtyeight')

debug = 1
plot_graphs = 0
trade_days = 252
portfolio_value = 15000

# Get the stock symbols
assets = ['FB', 'AMZN', 'AAPL', 'NFLX', 'GOOG']
weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])

stockStartDate = '2013-01-01'
today = datetime.today().strftime('%Y-%m-%d')

df = pd.DataFrame()
for stock in assets:
	df[stock] = web.DataReader(stock, data_source='yahoo', start = stockStartDate, end = today)['Adj Close']

if debug == 1:
	print("Stock Price Data")
	print(df)

# Create and plot a graph of stock prices
if plot_graphs == 1:
	title = 'Portfolio Adj. Close Price History'
	my_stocks = df
	for col in df.columns.values:
		plt.plot(my_stocks[col], label = col)

	plt.title(title)
	plt.xlabel('Date', fontsize = 18)
	plt.ylabel('Adj. Price USD ($)', fontsize = 18)
	plt.legend(df.columns.values, loc = 'upper left')
	plt.show()

# Show the daily simple return
# ( new_price / old_price ) - 1
returns = df.pct_change()
if debug == 1:
	print("Daily simple return")
	print(returns)

# Create and show the annualized covariance matrix
# Directional relationship between two assets prices
# (Determines how much two random variables move together)
cov_matrix_annual = returns.cov() * trade_days
if debug == 1:
	print("Annualized Covariance Matrix")
	print(cov_matrix_annual)

# Portfolio variance
port_variance = np.dot( weights.T, np.dot(cov_matrix_annual, weights))

# Portfolio volatility (standard deviation)
port_volatility = np.sqrt(port_variance)

# Calculate the annual portfolio return
portfolio_simple_annual_return = np.sum(returns.mean() * weights) * trade_days

# Debug
if debug == 1:
	print()
	print('DEBUG: Portfolio variance: ' + str(port_variance))
	print('DEBUG: Portfolio volatility: ' + str(port_volatility))
	print('DEBUG: Portfolio simple annual return: ' + str(portfolio_simple_annual_return) + "\n")

# Expected annual return, volatility (risk), variance
percent_variance = str( round(port_variance, 2) * 100 ) + '%'
percent_volatility = str( round(port_volatility, 2) * 100 ) + '%'
percent_return = str( round(portfolio_simple_annual_return, 2) * 100 ) + '%'

print('Expected annual return: ' + percent_return)
print('Annual volatility / risk: ' + percent_volatility)
print('Annual variance: ' + percent_variance)


###########################################################
print("\n\n*** Optimize Portfolio ***")

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

#rm = risk_models.sample_cov(df)
rm = risk_models.CovarianceShrinkage(df).ledoit_wolf()


# Efficient Frontier Optimisation
print("\n\nEFOPT SHARPE")
portfolio_optimizer_helpers.efopt(mu, rm, model='sharpe', print_alloc=True, plot=False, debug=1)

print("\n\nEFOPT NONCONVEX")
portfolio_optimizer_helpers.efopt(mu, rm, model='nonconvex', print_alloc=True, plot=False, debug=1)

print("\n\nEFOPT MIN_VOLATILITY")
portfolio_optimizer_helpers.efopt(mu, rm, model='min_volitility', print_alloc=True, plot=False, debug=1)

# Hierarchical Risk Parity
print("\n\nHRPOPT")
portfolio_optimizer_helpers.hrpopt(returns, print_alloc=True, plot=False, debug=1)

# Critical Line Algorithm
print("\n\nCLAOPT SHARPE")
portfolio_optimizer_helpers.claopt(mu, rm, model='sharpe', print_alloc=True, plot=True, debug=1)
print("\n\nCLAOPT MIN_VOLATILITY")
portfolio_optimizer_helpers.claopt(mu, rm, model='min_volitility', print_alloc=True, plot=True, debug=1)

