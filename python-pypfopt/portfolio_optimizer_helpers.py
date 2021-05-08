#!/usr/bin/python3

from pypfopt.discrete_allocation import DiscreteAllocation,get_latest_prices
from pypfopt import plotting

import warnings
def fxn():
    warnings.warn("deprecated", DeprecationWarning)

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    fxn()

##############################################
# Nonconvex objective from Kolm et al (2014)
def deviation_risk_parity(w, cov_matrix):
	diff = w * np.dot(cov_matrix, w) - (w * np.dot(cov_matrix, w)).reshape(-1, 1)
	return (diff ** 2).sum().sum()


##############################################
# Efficient Frontier Optimisation
# (Mean-variance optimisation)
# Based on Harry Markowitz’s 1952 paper
#  https://pyportfolioopt.readthedocs.io/en/latest/UserGuide.html#id3
def efopt(mu, rm, model='sharpe', print_alloc=False, plot=False, debug=0):

	from pypfopt.efficient_frontier import EfficientFrontier

	# Initialize EfficientFrontier
	# Note that if mu==None then a UserWarning is thrown, ignore it.
	# Note to allow for shorting, initialize with negative bounds: weight_bounds=(-1,1)
	import warnings
	with warnings.catch_warnings():
		warnings.simplefilter("ignore")
#		ef = EfficientFrontier(mu, rm, weight_bounds=(None, None))
		ef = EfficientFrontier(mu, rm)

	if mu is None:
		model = 'min_volitility'

	if model == 'sharpe':
		weights = ef.max_sharpe()
	elif model == 'nonconvex':
		weights = ef.nonconvex_objective(deviation_risk_parity, ef.cov_matrix)
	elif model == 'min_volitility':
		weights = ef.min_volatility()
	else:
		return False

	if debug == 1:
		cleaned_weights = ef.clean_weights()
		print(cleaned_weights)
		if plot == True:
			pd.Series(cleaned_weights).plot.barh();

	ef.portfolio_performance(verbose=True)

	# Calculate discrete allocation
	latest_prices = get_latest_prices(df)
	da = DiscreteAllocation(weights, latest_prices, total_portfolio_value = portfolio_value)
	if print_alloc == True:
		allocation, leftover = da.lp_portfolio()

		print()
		print('Discrete allocation: ', allocation)
		print('Funds remaining: ${:.2f}'.format(leftover))

	if plot == True:
		plotting.plot_weights(ef.clean_weights())

	return ef, da, weights


##############################################
# Hierarchical Risk Parity
#  Building Diversified Portfolios that Outperform Out of Sample.
#  The Journal of Portfolio Management, 42(4), 59–69. López de Prado, M. (2016).
#  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678
def hrpopt(returns, print_alloc=False, plot=False, debug=0):

	from pypfopt.hierarchical_portfolio import HRPOpt

	hrp = HRPOpt(returns)
	weights = hrp.optimize()

	if debug == 1:
		cleaned_weights = hrp.clean_weights()
		print(cleaned_weights)

	hrp.portfolio_performance(verbose=True)

	latest_prices = get_latest_prices(df)
	da = DiscreteAllocation(weights, latest_prices, total_portfolio_value = portfolio_value)
	if print_alloc == True:
		allocation, leftover = da.lp_portfolio()

		print()
		print('Discrete allocation: ', allocation)
		print('Funds remaining: ${:.2f}'.format(leftover))


	if plot == True:
		plotting.plot_weights(hrp.clean_weights())
		plotting.plot_dendrogram(hrp)

	return hrp, da, weights


##############################################
# Critical Line Algorithm
#  An Open-Source Implementation of the Critical-Line Algorithm for Portfolio Optimization
#  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2197616
def claopt(mu, rm, model='sharpe', print_alloc=False, plot=False, debug=0):

	from pypfopt.cla import CLA

	cla = CLA(mu, rm)

	if mu is None:
		model = 'min_volitility'

	if model == 'sharpe':
		weights = cla.max_sharpe()
	elif model == 'min_volitility':
		weights = cla.min_volatility()
	else:
		return False

	if debug == 1:
		cleaned_weights = cla.clean_weights()
		print(cleaned_weights)

	cla.portfolio_performance(verbose=True)

	latest_prices = get_latest_prices(df)
	da = DiscreteAllocation(weights, latest_prices, total_portfolio_value = portfolio_value)
	if print_alloc == True:
		allocation, leftover = da.lp_portfolio()
		print('Discrete allocation: ', allocation)
		print('Funds remaining: ${:.2f}'.format(leftover))

	if plot == True:
		plotting.plot_efficient_frontier(cla)

	return cla, da, weights

