#!/usr/bin/python3 -u

# Backtest a variety of algorithms and print a report

import os, sys
import time, datetime, pytz, random
import argparse
import pickle

import robin_stocks.tda as tda
import tulipy as ti

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper
import tda_gobot_analyze_helper


# Parse and check variables
parser = argparse.ArgumentParser()
parser.add_argument("stock", help='Stock ticker to purchase')
parser.add_argument("--stock_usd", help='Amount of money (USD) to invest', default=1000, type=float)
parser.add_argument("--algo", help='Analyze the most recent 5-day and 10-day history for a stock ticker using this bot\'s algorithim(s) - (Default: stochrsi)', default='stochrsi-new', type=str)
parser.add_argument("--ofile", help='Dump the pricehistory data to pickle file', default=None, type=str)
parser.add_argument("--ifile", help='Use pickle file for pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--augment_ifile", help='Pull additional history data and append it to candles imported from ifile', action="store_true")
parser.add_argument("--weekly_ifile", help='Use pickle file for weekly pricehistory data rather than accessing the API', default=None, type=str)
parser.add_argument("--daily_ifile", help='Use pickle file for daily pricehistory data rather than accessing the API', default=None, type=str)

parser.add_argument("--start_date", help='The day to start trading (i.e. 2021-05-12). Typically useful for verifying history logs.', default=None, type=str)
parser.add_argument("--stop_date", help='The day to stop trading (i.e. 2021-05-12)', default=None, type=str)
parser.add_argument("--skip_blacklist", help='Do not process blacklisted tickers.', action="store_true")
parser.add_argument("--skip_check", help="Skip fixup and check of stock ticker", action="store_true")
parser.add_argument("--unsafe", help='Allow trading between 9:30-10:15AM where volatility is high', action="store_true")
parser.add_argument("--hold_overnight", help='Allow algorithm to hold stocks across multiple days', action="store_true")

parser.add_argument("--no_use_resistance", help='Do no use the high/low resistance to avoid possibly bad trades (Default: False)', action="store_true")
parser.add_argument("--keylevel_strict", help='Use strict key level checks to enter trades (Default: False)', action="store_true")
parser.add_argument("--keylevel_use_daily", help='Use daily candles to determine key levels instead of weekly (Default: False)', action="store_true")
parser.add_argument("--price_resistance_pct", help='Resistance indicators will come into effect if price is within this percentage of a known support/resistance line', default=1, type=float)
parser.add_argument("--price_support_pct", help='Support indicators will come into effect if price is within this percentage of a known support/resistance line', default=1, type=float)
parser.add_argument("--use_natr_resistance", help='Enable the daily NATR resistance check', action="store_true")
parser.add_argument("--lod_hod_check", help='Enable low of the day (LOD) / high of the day (HOD) resistance checks', action="store_true")
parser.add_argument("--stoch_divergence", help='Monitor Stoch(RSI/MFI) divergence when encountering a new HOD or LOD', action="store_true")
parser.add_argument("--stoch_divergence_strict", help='Require Stoch(RSI/MFI) divergence when entering a new trade', action="store_true")

# Experimental
parser.add_argument("--check_ma", help='Tailor the stochastic indicator high/low levels based on the 5-minute SMA/EMA behavior', action="store_true")
parser.add_argument("--check_ma_strict", help='Check SMA and EMA to enable/disable the longing or shorting of stock', action="store_true")
parser.add_argument("--check_etf_indicators", help='Tailor the stochastic indicator high/low levels based on the 5-minute SMA/EMA behavior of key ETFs (SPY, QQQ, DIA)', action="store_true")
parser.add_argument("--check_etf_indicators_strict", help='Do not allow trade unless the 5-minute SMA/EMA behavior of key ETFs (SPY, QQQ, DIA) agree with direction', action="store_true")
parser.add_argument("--etf_tickers", help='List of tickers to use with -check_etf_indicators (Default: SPY,QQQ,DIA)', default='SPY,QQQ,DIA', type=str)
parser.add_argument("--experimental", help='Enable experimental features (Default: False)', action="store_true")
parser.add_argument("--experimental2", help='Enable experimental features (Default: False)', action="store_true")
# Experimental

parser.add_argument("--primary_stoch_indicator", help='Use this indicator as the primary stochastic indicator (Default: stochrsi)', default='stochrsi', type=str)
parser.add_argument("--with_stoch_5m", help='Use 5-minute candles with the --primary_stoch_indicator', action="store_true")
parser.add_argument("--with_stochrsi_5m", help='Use StochRSI with 5-min candles as an additional stochastic indicator (Default: False)', action="store_true")
parser.add_argument("--with_stochmfi", help='Use StochMFI as an additional stochastic indicator (Default: False)', action="store_true")
parser.add_argument("--with_stochmfi_5m", help='Use StochMFI with 5-min candles as an additional stochastic indicator (Default: False)', action="store_true")
parser.add_argument("--with_stacked_ma", help='Use stacked MA as a secondary indicator for trade entries (Default: False)', action="store_true")

parser.add_argument("--stacked_ma_type", help='Moving average type to use (Default: vwma)', default='sma', type=str)
parser.add_argument("--stacked_ma_periods", help='List of MA periods to use, comma-delimited (Default: 3,5,8)', default='3,5,8', type=str)
parser.add_argument("--stacked_ma_type_primary", help='Moving average type to use when stacked_ma is used as primary indicator (Default: sma)', default='sma', type=str)
parser.add_argument("--stacked_ma_periods_primary", help='List of MA periods to use when stacked_ma is used as primary indicator, comma-delimited (Default: 3,5,8)', default='3,5,8,13', type=str)

parser.add_argument("--with_rsi", help='Use standard RSI as a secondary indicator', action="store_true")
parser.add_argument("--with_rsi_simple", help='Use just the current RSI value as a secondary indicator', action="store_true")
parser.add_argument("--with_mfi", help='Use MFI (Money Flow Index) as a secondary indicator', action="store_true")
parser.add_argument("--with_adx", help='Use ADX as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_dmi", help='Use DMI as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_dmi_simple", help='Use DMI as secondary indicator to advise trade entries/exits, but do not wait for crossover (Default: False)', action="store_true")
parser.add_argument("--with_aroonosc", help='Use Aroon Oscillator as secondary indicator to advise trade entries (Default: False)', action="store_true")
parser.add_argument("--with_aroonosc_simple", help='Use Aroon Oscillator as secondary indicator to advise trade entries, but only evaluate AroonOsc value, not zero-line crossover (Default: False)', action="store_true")
parser.add_argument("--with_macd", help='Use MACD as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_macd_simple", help='Use MACD as secondary indicator to advise trade entries/exits, but do not wait for crossover (default=False)', action="store_true")
parser.add_argument("--with_vwap", help='Use VWAP as secondary indicator to advise trade entries/exits (Default: False)', action="store_true")
parser.add_argument("--with_vpt", help='Use VPT as secondary indicator to advise trade entries (Default: False)', action="store_true")
parser.add_argument("--with_chop_index", help='Use the Choppiness Index as secondary indicator to advise trade entries (Default: False)', action="store_true")
parser.add_argument("--with_chop_simple", help='Use a simple version Choppiness Index as secondary indicator to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--with_supertrend", help='Use the Supertrend indicator as secondary indicator to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--supertrend_atr_period", help='ATR period to use for the supertrend indicator (Default: 128)', default=128, type=int)
parser.add_argument("--supertrend_min_natr", help='Minimum daily NATR a stock must have to enable supertrend indicator (Default: 5)', default=5, type=float)
parser.add_argument("--with_bbands_kchannel", help='Use the Bollinger bands and Keltner channel indicators as secondary to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--with_bbands_kchannel_simple", help='Use a simple version of the Bollinger bands and Keltner channel indicators as secondary to advise on trade entries (Default: False)', action="store_true")
parser.add_argument("--bbands_kchannel_offset", help='Percentage offset between the Bollinger bands and Keltner channel indicators to trigger an initial trade entry (Default: 0.15)', default=0.15, type=float)
parser.add_argument("--bbands_kchan_squeeze_count", help='Number of squeeze periods needed before triggering bbands_kchannel signal (Default: 4)', default=4, type=int)
parser.add_argument("--bbands_period", help='Period to use when calculating the Bollinger Bands (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_period", help='Period to use when calculating the Keltner channels (Default: 20)', default=20, type=int)
parser.add_argument("--kchannel_atr_period", help='Period to use when calculating the ATR for use with the Keltner channels (Default: 20)', default=20, type=int)

parser.add_argument("--aroonosc_with_macd_simple", help='When using Aroon Oscillator, use macd_simple as tertiary indicator if AroonOsc is less than +/- 70 (Default: False)', action="store_true")
parser.add_argument("--aroonosc_with_vpt", help='When using Aroon Oscillator, use vpt as tertiary indicator if AroonOsc is less than +/- 70 (Default: False)', action="store_true")
parser.add_argument("--aroonosc_secondary_threshold", help='AroonOsc threshold for when to enable macd_simple when --aroonosc_with_macd_simple is enabled (Default: 70)', default=72, type=float)
parser.add_argument("--adx_threshold", help='ADX threshold for when to trigger the ADX signal (Default: 25)', default=25, type=float)
parser.add_argument("--dmi_with_adx", help='Use ADX when confirming DI signal (Default: False)', action="store_true")

parser.add_argument("--days", help='Number of days to test. Separate with a comma to test multiple days.', default='10', type=str)
parser.add_argument("--incr_threshold", help='Reset base_price if stock increases by this percent', default=1, type=float)
parser.add_argument("--decr_threshold", help='Max allowed drop percentage of the stock price', default=1.5, type=float)
parser.add_argument("--stoploss", help='Sell security if price drops below --decr_threshold (Default: False)', action="store_true")
parser.add_argument("--exit_percent", help='Sell security if price improves by this percentile', default=None, type=float)
parser.add_argument("--strict_exit_percent", help='Only exit when exit_percent signals an exit, ignore stochrsi', action="store_true")
parser.add_argument("--quick_exit", help='Exit immediately if an exit_percent strategy was set, do not wait for the next candle', action="store_true")
parser.add_argument("--variable_exit", help='Adjust incr_threshold, decr_threshold and exit_percent based on the price action of the stock over the previous hour', action="store_true")
parser.add_argument("--use_ha_exit", help='Use Heikin Ashi candles with exit_percent-based exit strategy', action="store_true")
parser.add_argument("--use_trend_exit", help='Use ttm_trend algorithm with exit_percent-based exit strategy', action="store_true")
parser.add_argument("--trend_exit_type", help='Type to use with ttm_trend algorithm (Default: hl2', default='hl2', type=str)

parser.add_argument("--blacklist_earnings", help='Blacklist trading one week before and after quarterly earnings dates (Default: False)', action="store_true")
parser.add_argument("--check_volume", help='Check the last several days (up to 6-days, depending on how much history is available) to ensure stock is not trading at a low volume threshold (Default: False)', action="store_true")
parser.add_argument("--avg_volume", help='Skip trading for the day unless the average volume over the last few days equals this value', default=2000000, type=int)
parser.add_argument("--min_volume", help='Skip trading for the day unless the daily volume over the last few days equals at least this value', default=1500000, type=int)
parser.add_argument("--min_ticker_age", help='Do not process tickers younger than this number of days (Default: None)', default=None, type=int)
parser.add_argument("--min_daily_natr", help='Do not process tickers with less than this daily NATR value (Default: None)', default=None, type=float)
parser.add_argument("--max_daily_natr", help='Do not process tickers with more than this daily NATR value (Default: None)', default=None, type=float)
parser.add_argument("--min_intra_natr", help='Minimum intraday NATR value to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--max_intra_natr", help='Maximum intraday NATR value to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--min_price", help='Minimum stock price to allow trade entry (Default: None)', default=None, type=float)
parser.add_argument("--max_price", help='Maximum stock price to allow trade entry (Default: None)', default=None, type=float)

parser.add_argument("--rsi_period", help='RSI period to use for calculation (Default: 14)', default=14, type=int)
parser.add_argument("--stochrsi_period", help='RSI period to use for StochRSI calculation (Default: 128)', default=128, type=int)
parser.add_argument("--stochrsi_5m_period", help='RSI period to use for StochRSI calculation (Default: 28)', default=28, type=int)
parser.add_argument("--rsi_slow", help='Slowing period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_k_period", help='k period to use in StochRSI algorithm', default=128, type=int)
parser.add_argument("--rsi_d_period", help='D period to use in StochRSI algorithm', default=3, type=int)
parser.add_argument("--rsi_type", help='Price to use for RSI calculation (high/low/open/close/volume/hl2/hlc3/ohlc4)', default='hlc3', type=str)
parser.add_argument("--rsi_high_limit", help='RSI high limit', default=80, type=int)
parser.add_argument("--rsi_low_limit", help='RSI low limit', default=20, type=int)
parser.add_argument("--stochrsi_offset", help='Offset between K and D to determine strength of trend', default=8, type=float)
parser.add_argument("--nocrossover", help='Modifies the algorithm so that k and d crossovers will not generate a signal (Default: False)', action="store_true")
parser.add_argument("--crossover_only", help='Modifies the algorithm so that only k and d crossovers will generate a signal (Default: False)', action="store_true")

parser.add_argument("--stochmfi_period", help='Money Flow Index (MFI) period to use for StochMFI calculation (Default: 14)', default=14, type=int)
parser.add_argument("--stochmfi_5m_period", help='Money Flow Index (MFI) period to use for StochMFI calculation using 5-minute candles (Default: 14)', default=14, type=int)
parser.add_argument("--mfi_period", help='Money Flow Index (MFI) period', default=14, type=int)
parser.add_argument("--mfi_high_limit", help='MFI high limit', default=80, type=int)
parser.add_argument("--mfi_low_limit", help='MFI low limit', default=20, type=int)

parser.add_argument("--atr_period", help='Average True Range period for intraday calculations', default=14, type=int)
parser.add_argument("--daily_atr_period", help='Average True Range period for daily calculations', default=14, type=int)
parser.add_argument("--vpt_sma_period", help='SMA period for VPT signal line', default=72, type=int)
parser.add_argument("--adx_period", help='ADX period', default=92, type=int)
parser.add_argument("--di_period", help='Plus/Minus DI period', default=48, type=int)
parser.add_argument("--aroonosc_period", help='Aroon Oscillator period', default=24, type=int)
parser.add_argument("--aroonosc_alt_period", help='Alternate Aroon Oscillator period for higher volatility stocks', default=48, type=int)
parser.add_argument("--aroonosc_alt_threshold", help='Threshold for enabling the alternate Aroon Oscillator period for higher volatility stocks', default=0.24, type=float)

parser.add_argument("--chop_period", help='Choppiness Index period', default=14, type=int)
parser.add_argument("--chop_low_limit", help='Choppiness Index low limit', default=38.2, type=float)
parser.add_argument("--chop_high_limit", help='Choppiness Index high limit', default=61.8, type=float)

parser.add_argument("--macd_short_period", help='MACD short (fast) period', default=48, type=int)
parser.add_argument("--macd_long_period", help='MACD long (slow) period', default=104, type=int)
parser.add_argument("--macd_signal_period", help='MACD signal (length) period', default=36, type=int)
parser.add_argument("--macd_offset", help='MACD offset for signal lines', default=0.006, type=float)

parser.add_argument("--stochrsi_signal_cancel_low_limit", help='Limit used to cancel StochRSI short signals', default=60, type=int)
parser.add_argument("--stochrsi_signal_cancel_high_limit", help='Limit used to cancel StochRSI long signals', default=40, type=int)
parser.add_argument("--rsi_signal_cancel_low_limit", help='Limit used to cancel RSI short signals', default=60, type=int)
parser.add_argument("--rsi_signal_cancel_high_limit", help='Limit used to cancel RSI long signals', default=40, type=int)
parser.add_argument("--mfi_signal_cancel_low_limit", help='Limit used to cancel MFI short signals', default=60, type=int)
parser.add_argument("--mfi_signal_cancel_high_limit", help='Limit used to cancel MFI long signals', default=40, type=int)

parser.add_argument("--noshort", help='Disable short selling of stock', action="store_true")
parser.add_argument("--shortonly", help='Only short sell the stock', action="store_true")

parser.add_argument("--verbose", help='Print additional information about each transaction (Default: False)', action="store_true")
parser.add_argument("-d", "--debug", help='Enable debug output', action="store_true")
parser.add_argument("--debug_all", help='Enable extra debugging output', action="store_true")

# Obsolete, but it would have been cool if it worked...
#parser.add_argument("--use_candle_monitor", help='Enable the trivial candle monitor (Default: False)', action="store_true")

args = parser.parse_args()

args.debug = True	# Should default to False eventually, testing for now

decr_threshold = args.decr_threshold
incr_threshold = args.incr_threshold

stock = args.stock
stock_usd = args.stock_usd

# Initialize and log into TD Ameritrade
from dotenv import load_dotenv
if ( load_dotenv(dotenv_path=parent_path+'/../.env') != True ):
        print('Error: unable to load .env file', file=sys.stderr)
        exit(1)

tda_account_number = os.environ["tda_account_number"]
passcode = os.environ["tda_encryption_passcode"]

tda_gobot_helper.tda = tda
tda_gobot_analyze_helper.tda = tda

tda_gobot_helper.passcode = passcode
tda_gobot_analyze_helper.passcode = passcode

tda_gobot_helper.tda_account_number = tda_account_number

if ( args.skip_check == False ):
	if ( tda_gobot_helper.tdalogin(passcode) != True ):
		print('Error: Login failure', file=sys.stderr)
		sys.exit(1)

# Fix up and sanity check the stock symbol before proceeding
if ( args.skip_check == False ):
	stock = tda_gobot_helper.fix_stock_symbol(stock)
	ret = tda_gobot_helper.check_stock_symbol(stock)
	if ( isinstance(ret, bool) and ret == False ):
		print('Error: check_stock_symbol(' + str(stock) + ') returned False, exiting.')
		exit(1)

# Check if stock is in the blacklist
if ( tda_gobot_helper.check_blacklist(stock) == True ):
	if ( args.skip_blacklist == True ):
		print('(' + str(stock) + ') WARNING: skipping ' + str(stock) + ' because it is currently blacklisted and --skip_blacklist is set.', file=sys.stderr)
		exit(1)
	else:
		print('(' + str(stock) + ') WARNING: stock ' + str(stock) + ' is currently blacklisted')

# Confirm that we can short this stock
if ( args.ifile == None ):
	if ( args.noshort == False or args.shortonly == True ):
		data,err = tda.stocks.get_quote(stock, True)
		if ( err != None ):
			print('Error: get_quote(' + str(stock) + '): ' + str(err), file=sys.stderr)

		if ( str(data[stock]['shortable']) == str(False) or str(data[stock]['marginable']) == str(False) ):
			if ( args.shortonly == True ):
				print('Error: stock(' + str(stock) + '): does not appear to be shortable, exiting.')
				exit(1)

			if ( args.noshort == False ):
				print('Warning: stock(' + str(stock) + '): does not appear to be shortable, disabling sell-short')
				args.noshort = True


# tda.get_price_history() variables
mytimezone = pytz.timezone("US/Eastern")
tda_gobot_helper.mytimezone = mytimezone
tda_gobot_analyze_helper.mytimezone = mytimezone

safe_open = True
if ( args.unsafe == True ):
	safe_open = False

p_type = 'day'
period = None
f_type = 'minute'
freq = '1'

# RSI variables
rsi_type = args.rsi_type
rsi_period = args.rsi_period
rsi_slow = args.rsi_slow
cur_rsi = 0
prev_rsi = 0
rsi_low_limit = args.rsi_low_limit
rsi_high_limit = args.rsi_high_limit

# Report colors
red = '\033[0;31m'
green = '\033[0;32m'
reset_color = '\033[0m'
text_color = ''

# Get general info about the stock
marginable = None
shortable = None
delayed = True
volatility = 0
lastprice = 0
high = low = 0

if ( args.ifile == None ):

	try:
		data,err = tda.stocks.get_quote(stock, True)
		if ( err == None and data != {} ):
			if ( str(data[stock]['marginable']) == 'True' ):
				marginable = True
			if ( str(data[stock]['shortable']) == 'True' ):
				shortable = True
			if ( str(data[stock]['delayed']) == 'False' ):
				delayed = False

			volatility = data[stock]['volatility'] # FIXME: I don't know what this means yet
			lastprice = data[stock]['lastPrice']
			high = data[stock]['52WkHigh']
			low = data[stock]['52WkLow']

	except Exception as e:
		print('Caught exception in tda.stocks.get_quote(' + str(stock) + '): ' + str(e))
		pass

print()
print( 'Stock summary for "' + str(stock) + "\"\n" )
print( 'Last Price: $' + str(lastprice) )
print( 'Amount Per Trade: $' + str(stock_usd) )
print( '52WkHigh: $' + str(high) )
print( '52WkLow: $' + str(low) )

text_color = green
if ( shortable == False ):
	text_color = red
print( 'Shortable: ' + text_color + str(shortable) + reset_color )

text_color = green
if ( marginable == False ):
	text_color = red
print( 'Marginable: ' + text_color + str(marginable) + reset_color )

text_color = green
if ( delayed == True ):
	text_color = red
print( 'Delayed: ' + text_color + str(delayed) + reset_color )
print( 'Volatility: ' + str(volatility) )
print()


# --algo=rsi, --algo=stochrsi
for algo in args.algo.split(','):

	algo = algo.lower()
	if ( algo != 'rsi' and algo != 'stochrsi' and algo != 'stochrsi-new'):
		print('Unsupported algorithm "' + str(algo) + '"')
		continue

	if ( args.ifile != None ):
		try:
			with open(args.ifile, 'rb') as handle:
				data = handle.read()
				data = pickle.loads(data)

		except Exception as e:
			print('Error opening file ' + str(args.ifile) + ': ' + str(e))
			exit(1)

		args.days = -1

		# Add data to ifile to ensure we have enough history to perform calculations
		if ( args.augment_ifile == True ):

			days = 3
			time_now = datetime.datetime.now( mytimezone )
			time_prev = time_now - datetime.timedelta( days=days )

			# Make sure start and end dates don't land on a weekend
			#  or outside market hours
			time_now = tda_gobot_helper.fix_timestamp(time_now)
			time_prev = tda_gobot_helper.fix_timestamp(time_prev)

			time_now_epoch = int( time_now.timestamp() * 1000 )
			time_prev_epoch = int( time_prev.timestamp() * 1000 )

			try:
				ph_data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(ticker) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
				continue

			if ( ph_data == False ):
				continue

			# Populate new_data up until the last date
			new_data = { 'candles': [],
				     'symbol': ph_data['symbol'] }

			last_date = float( data['candles'][0]['datetime'] )
			for idx,key in enumerate(ph_data['candles']):
				if ( float(key['datetime']) < last_date ):
					new_data['candles'].append( ph_data['candles'][idx] )
				else:
					break

			for idx,key in enumerate(data['candles']):
				new_data['candles'].append( data['candles'][idx] )

			data = new_data
			del(new_data, ph_data)

	# Weekly Candles
	data_weekly = None
	if ( args.weekly_ifile != None ):
		try:
			with open(args.weekly_ifile, 'rb') as handle:
				data_weekly = handle.read()
				data_weekly = pickle.loads(data_weekly)

		except Exception as e:
			print('Error opening file ' + str(args.weekly_ifile) + ': ' + str(e))
			exit(1)

	# Daily Candles
	data_daily = None
	if ( args.daily_ifile != None ):
		try:
			with open(args.daily_ifile, 'rb') as handle:
				data_daily = handle.read()
				data_daily = pickle.loads(data_daily)

		except Exception as e:
			print('Error opening file ' + str(args.daily_ifile) + ': ' + str(e))
			exit(1)

	# ETF Indicators
	etf_tickers = args.etf_tickers.split(',')
	etf_indicators = {}
	for t in etf_tickers:
		etf_indicators[t] = { 'sma': {}, 'ema': {}, 'pricehistory': {} }

	if ( args.check_etf_indicators == True or args.check_etf_indicators_strict == True ):
		for t in etf_tickers:
			etf_data = None
			try:
				with open('monthly-5min-csv/' + str(t) + '.pickle', 'rb') as handle:
					etf_data = handle.read()
					etf_data = pickle.loads(etf_data)

			except Exception as e:
				print('Error opening file monthly-5min-csv/' + str(t) + '.pickle: ' + str(e))
				exit(1)

			etf_indicators[t]['pricehistory'] = etf_data


	# Print results for the most recent 10 and 5 days of data
	for days in str(args.days).split(','):

		# Pull the 1-minute stock history
		# Note: Not asking for extended hours for now since our bot doesn't even trade after hours
		if ( args.ifile != None ):
			# Use ifile for data
			start_day = data['candles'][0]['datetime']
			end_day = data['candles'][-1]['datetime']

			start_day = datetime.datetime.fromtimestamp(float(start_day)/1000, tz=mytimezone)
			end_day = datetime.datetime.fromtimestamp(float(end_day)/1000, tz=mytimezone)

			delta = start_day - end_day
			days = str(abs(int(delta.days)))

		elif ( days != '-1' ):
			try:
				int(days)
			except:
				print('Error, days (' + str(days) + ') is not an integer - exiting.')
				exit(1)

			if ( int(days) > 10 ):
				days = 10 # TDA API only allows 10-days of 1-minute daily data
			elif ( int(days) < 3 ):
				days += 2

			try:
				data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, days, needExtendedHoursData=True, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(ticker) + '): ' + str(e))
				continue

		# Specifying days=-1 will get you the most recent info we can from the API
		# But we still need to ask for a few days in order to force it to give us at least two days of data
		else:
			days = 5
			time_now = datetime.datetime.now( mytimezone )
			time_prev = time_now - datetime.timedelta( days=days )

			# Make sure start and end dates don't land on a weekend
			#  or outside market hours
			time_now = tda_gobot_helper.fix_timestamp(time_now)
			time_prev = tda_gobot_helper.fix_timestamp(time_prev)

			time_now_epoch = int( time_now.timestamp() * 1000 )
			time_prev_epoch = int( time_prev.timestamp() * 1000 )

			try:
				data, epochs = tda_gobot_helper.get_pricehistory(stock, p_type, f_type, freq, period=None, start_date=time_prev_epoch, end_date=time_now_epoch, needExtendedHoursData=True, debug=False)

			except Exception as e:
				print('Caught Exception: get_pricehistory(' + str(ticker) + ', ' + str(time_prev_epoch) + ', ' + str(time_now_epoch) + '): ' + str(e))
				continue

		if ( data == False ):
			continue

		if ( int(len(data['candles'])) <= rsi_period ):
			print('Not enough data - returned candles=' + str(len(data['candles'])) + ', rsi_period=' + str(rsi_period))
			continue

		# Translate and add Heiken Ashi candles to pricehistory (will add new array called data['hacandles'])
		data = tda_gobot_helper.translate_heikin_ashi(pricehistory=data)

		# Dump pickle data if requested
		if ( args.ofile != None ):
			try:
				file = open(args.ofile, "wb")
				pickle.dump(data, file)
				file.close()
			except Exception as e:
				print('Unable to write to file ' + str(args.ofile) + ': ' + str(e))

		# Subtract 1 because stochrsi_analyze_new() skips the first day of data
		days = int(days) - 1

		# Run the analyze function
		print('Analyzing ' + str(days) + '-day history for stock ' + str(stock) + ' using the ' + str(algo) + " algorithm:")
		print()
		print('### Debug Logs ###')

		if ( algo == 'rsi' ):
			print('Deprecated: see branch 1.0 for this algorithm')
			sys.exit(1)

		elif ( algo == 'stochrsi' or algo == 'stochrsi-new' ):

			test_params = {
					# Test range and input options
					'start_date':				args.start_date,
					'stop_date':				args.stop_date,
					'safe_open':				safe_open,
					'weekly_ph':				data_weekly,
					'daily_ph':				data_daily,

					'debug':				args.debug,
					'debug_all':				args.debug_all,

					# Trade exit parameters
					'incr_threshold':			args.incr_threshold,
					'decr_threshold':			args.decr_threshold,
					'stoploss':				args.stoploss,
					'exit_percent':				args.exit_percent,
					'quick_exit':				args.quick_exit,
					'strict_exit_percent':			args.strict_exit_percent,
					'variable_exit':			args.variable_exit,
					'use_ha_exit':				args.use_ha_exit,
					'use_trend_exit':			args.use_trend_exit,
					'trend_exit_type':			args.trend_exit_type,
					'hold_overnight':			args.hold_overnight,

					# Stock shorting options
					'noshort':				args.noshort,
					'shortonly':				args.shortonly,

					# Other stock behavior options
					'blacklist_earnings':			args.blacklist_earnings,
					'check_volume':				args.check_volume,
					'avg_volume':				args.avg_volume,
					'min_volume':				args.min_volume,
					'min_ticker_age':			args.min_ticker_age,
					'min_daily_natr':			args.min_daily_natr,
					'max_daily_natr':			args.max_daily_natr,
					'min_intra_natr':			args.min_intra_natr,
					'max_intra_natr':			args.max_intra_natr,
					'min_price':				args.min_price,
					'max_price':				args.max_price,

					# Indicators
					'primary_stoch_indicator':		args.primary_stoch_indicator,
					'with_stoch_5m':			args.with_stoch_5m,
					'with_stochrsi_5m':			args.with_stochrsi_5m,
					'with_stochmfi':			args.with_stochmfi,
					'with_stochmfi_5m':			args.with_stochmfi_5m,

					'with_stacked_ma':			args.with_stacked_ma,
					'stacked_ma_type':			args.stacked_ma_type,
					'stacked_ma_periods':			args.stacked_ma_periods,
					'stacked_ma_type_primary':		args.stacked_ma_type_primary,
					'stacked_ma_periods_primary':		args.stacked_ma_periods_primary,

					'with_rsi':				args.with_rsi,
					'with_rsi_simple':			args.with_rsi_simple,

					'with_dmi':				args.with_dmi,
					'with_dmi_simple':			args.with_dmi_simple,
					'with_adx':				args.with_adx,

					'with_macd':				args.with_macd,
					'with_macd_simple':			args.with_macd_simple,

					'with_aroonosc':			args.with_aroonosc,
					'with_aroonosc_simple':			args.with_aroonosc_simple,

					'with_mfi':				args.with_mfi,

					'with_vpt':				args.with_vpt,
					'with_vwap':				args.with_vwap,
					'with_chop_index':			args.with_chop_index,
					'with_chop_simple':			args.with_chop_simple,

					'with_supertrend':			args.with_supertrend,
					'supertrend_atr_period':		args.supertrend_atr_period,
					'supertrend_min_natr':			args.supertrend_min_natr,

					'with_bbands_kchannel':			args.with_bbands_kchannel,
					'with_bbands_kchannel_simple':		args.with_bbands_kchannel_simple,
					'bbands_kchannel_offset':		args.bbands_kchannel_offset,
					'bbands_kchan_squeeze_count':		args.bbands_kchan_squeeze_count,
					'bbands_period':			args.bbands_period,
					'kchannel_period':			args.kchannel_period,
					'kchannel_atr_period':			args.kchannel_atr_period,

 					# Indicator parameters and modifiers
					'stochrsi_period':			args.stochrsi_period,
					'stochrsi_5m_period':			args.stochrsi_5m_period,
					'rsi_period':				args.rsi_period,
					'rsi_type':				args.rsi_type,
					'rsi_slow':				args.rsi_slow,
					'rsi_k_period':				args.rsi_k_period,
					'rsi_d_period':				args.rsi_d_period,
					'rsi_low_limit':			args.rsi_low_limit,
					'rsi_high_limit':			args.rsi_high_limit,
					'stochrsi_offset':			args.stochrsi_offset,
					'nocrossover':				args.nocrossover,
					'crossover_only':			args.crossover_only,

					'di_period':				args.di_period,
					'adx_period':				args.adx_period,
					'adx_threshold':			args.adx_threshold,
					'dmi_with_adx':				args.dmi_with_adx,

					'macd_short_period':			args.macd_short_period,
					'macd_long_period':			args.macd_long_period,
					'macd_signal_period':			args.macd_signal_period,
					'macd_offset':				args.macd_offset,

					'aroonosc_period':			args.aroonosc_period,
					'aroonosc_alt_period':			args.aroonosc_alt_period,
					'aroonosc_alt_threshold':		args.aroonosc_alt_threshold,
					'aroonosc_secondary_threshold':		args.aroonosc_secondary_threshold,
					'aroonosc_with_macd_simple':		args.aroonosc_with_macd_simple,
					'aroonosc_with_vpt':			args.aroonosc_with_vpt,

					'stochmfi_period':			args.stochmfi_period,
					'stochmfi_5m_period':			args.stochmfi_5m_period,
					'mfi_period':				args.mfi_period,
					'mfi_high_limit':			args.mfi_high_limit,
					'mfi_low_limit':			args.mfi_low_limit,

					'atr_period':				args.atr_period,
					'daily_atr_period':			args.daily_atr_period,
					'vpt_sma_period':			args.vpt_sma_period,

					'chop_period':				args.chop_period,
					'chop_low_limit':			args.chop_low_limit,
					'chop_high_limit':			args.chop_high_limit,

					'stochrsi_signal_cancel_low_limit':	args.stochrsi_signal_cancel_low_limit,
					'stochrsi_signal_cancel_high_limit':	args.stochrsi_signal_cancel_high_limit,
					'rsi_signal_cancel_low_limit':		args.rsi_signal_cancel_low_limit,
					'rsi_signal_cancel_high_limit':		args.rsi_signal_cancel_high_limit,
					'mfi_signal_cancel_low_limit':		args.mfi_signal_cancel_low_limit,
					'mfi_signal_cancel_high_limit':		args.mfi_signal_cancel_high_limit,

					# Resistance indicators
					'no_use_resistance':			args.no_use_resistance,
					'price_resistance_pct':			args.price_resistance_pct,
					'price_support_pct':			args.price_support_pct,
					'lod_hod_check':			args.lod_hod_check,
					'keylevel_strict':			args.keylevel_strict,
					'keylevel_use_daily':			args.keylevel_use_daily,
					'use_natr_resistance':			args.use_natr_resistance,
					'stoch_divergence':			args.stoch_divergence,
					'stoch_divergence_strict':		args.stoch_divergence_strict,
					'check_ma':				args.check_ma,
					'check_ma_strict':			args.check_ma_strict,

					'check_etf_indicators':			args.check_etf_indicators,
					'check_etf_indicators_strict':		args.check_etf_indicators_strict,
					'etf_tickers':				etf_tickers,
					'etf_indicators':			etf_indicators,

					'experimental':				args.experimental,
					'experimental2':			args.experimental2,
			}

			# Call stochrsi_analyze_new() with test_params{} to run the backtest
			results = tda_gobot_analyze_helper.stochrsi_analyze_new( pricehistory=data, ticker=stock, params=test_params )


		# Check and print the results from stochrsi_analyze_new()
		if ( isinstance(results, bool) and results == False ):
			print('Error: rsi_analyze(' + str(stock) + ') returned false', file=sys.stderr)
			continue
		if ( int(len(results)) == 0 ):
			print('There were no possible trades for requested time period, exiting.')
			continue

		# Print the returned results
		elif ( (algo == 'stochrsi' or algo == 'stochrsi-new') and args.verbose ):
			print()
			print('### Trade Ledger ###')
			print('{0:18} {1:15} {2:15} {3:10} {4:10} {5:10} {6:10}'.format('Buy/Sell Price', 'Net Change', 'RSI_K/RSI_D', 'NATR', 'Daily_NATR', 'ADX', 'Time'))

		rating = 0
		success = fail = 0
		net_gain = float(0)
		net_loss = float(0)
		total_return = float(0)
		counter = 0
		while ( counter < len(results) - 1 ):

			price_tx, short, rsi_tx, natr_tx, dnatr_tx, adx_tx, time_tx = results[counter].split( ',', 7 )
			price_rx, short, rsi_rx, natr_rx, dnatr_rx, adx_rx, time_rx = results[counter+1].split( ',', 7 )

			vwap_tx = vwap_rx = 0
			stochrsi_tx = stochrsi_rx = 0

			# Returned RSI format is "prev_rsi/cur_rsi"
			rsi_prev_tx,rsi_cur_tx = rsi_tx.split( '/', 2 )
			rsi_prev_rx,rsi_cur_rx = rsi_rx.split( '/', 2 )

			net_change = float(price_rx) - float(price_tx)
			if ( short == str(False) ):
				if ( float(net_change) <= 0 ):
					fail += 1
					net_loss += float(net_change)
				else:
					success += 1
					net_gain += float(net_change)
			else:
				if ( float(net_change) < 0 ):
					success += 1
					net_gain += abs(float(net_change))
				else:
					fail += 1
					net_loss -= float(net_change)

			price_tx = round( float(price_tx), 2 )
			price_rx = round( float(price_rx), 2 )

			net_change = round(net_change, 2)

			num_shares = int(stock_usd / price_tx)

			if ( short == str(False) ):
				total_return += num_shares * net_change

			else:
				if ( net_change <= 0 ):
					total_return += abs(num_shares * net_change)
				else:
					total_return += num_shares * -net_change

			vwap_tx = round( float(vwap_tx), 2 )
			vwap_rx = round( float(vwap_rx), 2 )

			rsi_prev_tx = round( float(rsi_prev_tx), 1 )
			rsi_cur_tx = round( float(rsi_cur_tx), 1 )
			rsi_prev_rx = round( float(rsi_prev_rx), 1 )
			rsi_cur_rx = round( float(rsi_cur_rx), 1 )

			stochrsi_tx = round( float(stochrsi_tx), 4 )
			stochrsi_rx = round( float(stochrsi_rx), 4 )

			is_success = False
			if ( short == 'True' ):
				if ( net_change < 0 ):
					is_success = True

				price_tx = str(price_tx) + '*'
				price_rx = str(price_rx) + '*'

			else:
				if ( net_change > 0 ):
					is_success = True

			if ( args.verbose == True ):
				text_color = red
				if ( is_success == True ):
					text_color = green

				rsi_tx = str(rsi_prev_tx) + '/' + str(rsi_cur_tx)
				rsi_rx = str(rsi_prev_rx) + '/' + str(rsi_cur_rx)

				print(text_color, end='')
				print('{0:18} {1:15} {2:15} {3:10} {4:10} {5:10} {6:10}'.format(str(price_tx), '-', str(rsi_tx), str(natr_tx), str(dnatr_tx), str(adx_tx), time_tx), end='')
				print(reset_color, end='')

				print()

				print(text_color, end='')
				print('{0:18} {1:15} {2:15} {3:10} {4:10} {5:10} {6:10}'.format(str(price_rx), str(net_change), str(rsi_rx), '-', '-', str(adx_tx), time_rx), end='')
				print(reset_color, end='')

				print()

			counter += 2


		# Rate the stock
		#   txs/day < 1				 = -1 point	# SAZ - temporarily suspended this one 2021-04-26
		#   avg_gain_per_share < 1		 = -1 points
		#   success_pct < 10% higher than fail % = -2 points
		#   success_pct <= fail_pct		 = -4 points
		#   average_gain <= average_loss	 = -8 points
		#   shortable == False			 = -4 points
		#   marginable == False			 = -2 points
		#   delayed == True			 = -2 points
		#
		# Rating:
		#   0 			 = Very Good
		#   -1			 = Good
		#   <-2 & >-4		 = Poor
		#   <-3			 = Bad
		#   Success % <= Fail %  = FAIL
		#   Avg Gain <= Avg Loss = FAIL
		print()
		print('### Statistics ###')

		txs = int(len(results) / 2) / int(days)					# Average buy or sell triggers per day
		if ( success == 0 ):
			success_pct = 0
		else:
			success_pct = (int(success) / int(len(results) / 2) ) * 100	# % Successful trades using algorithm

		if ( fail == 0 ):
			fail_pct = 0
		else:
			fail_pct = ( int(fail) / int(len(results) / 2) ) * 100		# % Failed trades using algorithm

		average_gain = 0
		average_loss = 0
		if ( success != 0 ):
			average_gain = net_gain / success				# Average improvement in price using algorithm
		if ( fail != 0 ):
			average_loss = net_loss / fail					# Average regression in price using algorithm

		print()

		# Check number of transactions/day
		text_color = green
#		if ( txs < 1 ):
#			rating -= 1
#			text_color = red

		print( 'Average txs/day: ' + text_color + str(round(txs,2)) + reset_color )

		# Compare success/fail percentage
		if ( success_pct <= fail_pct ):
			rating -= 4
			text_color = red
		elif ( success_pct - fail_pct < 10 ):
			rating -= 2
			text_color = red
		else:
			text_color = green

		print( 'Success rate: ' + text_color + str(round(success_pct, 2)) + reset_color )
		print( 'Fail rate: ' + text_color + str(round(fail_pct, 2)) + reset_color )

		# Compare average gain vs average loss
		if ( average_gain <= abs(average_loss) ):
			rating -= 8
			text_color = red
		else:
			text_color = green

		print( 'Average gain: ' + text_color + str(round(average_gain, 2)) + ' / share' + reset_color )
		print( 'Average loss: ' + text_color + str(round(average_loss, 2)) + ' / share' + reset_color )

		# Compare net gain vs net loss
		if ( net_gain <= abs(net_loss) ):
			rating -= 8
			text_color = red
		else:
			text_color = green

		print( 'Net gain: ' + text_color + str(round(net_gain, 2)) + ' / share' + reset_color )
		print( 'Net loss: ' + text_color + str(round(net_loss, 2)) + ' / share' + reset_color )

		# Calculate the average gain per share price
		if ( args.ifile != None ):
			last_price = data['candles'][-1]['close']
		else:
			last_price = tda_gobot_helper.get_lastprice(stock, WarnDelayed=False)

		if ( last_price != False ):
			avg_gain_per_share = float(average_gain) / float(last_price) * 100
			if ( avg_gain_per_share < 1 ):
				rating -= 1
				text_color = red
			else:
				text_color = green

			print( 'Average gain per share: ' + text_color + str(round(avg_gain_per_share, 3)) + '%' + reset_color )

		# Total return
		text_color = green
		if ( total_return < 0 ):
			text_color = red

		print( 'Total return: ' + text_color + str(round(total_return, 2)) + reset_color )

		# Shortable / marginable / delayed / etc.
		if ( shortable == False ):
			rating -= 4
		if ( marginable == False ):
			rating -= 2
		if ( delayed == True ):
			rating -= 2

		# Print stock rating (see comments above)
		if ( success_pct <= fail_pct or average_gain <= average_loss ):
			rating = red + 'FAIL' + reset_color
		elif ( rating == 0 ):
			rating = green + 'Very Good' + reset_color
		elif ( rating == -1 ):
			rating = green + 'Good' + reset_color
		elif ( rating <= -4 ):
			rating = red + 'Bad' + reset_color
		elif ( rating <= -2 ):
			rating = red + 'Poor' + reset_color

		print( 'Stock rating: ' + str(rating) )
		print()

exit(0)
