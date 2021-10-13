#!/usr/bin/python3 -u

import os, sys
from collections import OrderedDict

from datetime import datetime, timedelta
from pytz import timezone

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper


# Like stochrsi_analyze(), but sexier
def stochrsi_analyze_new( pricehistory=None, ticker=None, params={} ):

	if ( ticker == None or pricehistory == None ):
		print('Error: stochrsi_analyze(' + str(ticker) + '): Either pricehistory or ticker is empty', file=sys.stderr)
		return False

	try:
		assert mytimezone
	except:
		mytimezone = timezone("US/Eastern")


	# Reset all the buy/sell/short/buy-to-cover and indicator signals
	def reset_signals():

		nonlocal buy_signal			; buy_signal			= False
		nonlocal sell_signal			; sell_signal			= False
		nonlocal short_signal			; short_signal			= False
		nonlocal buy_to_cover_signal		; buy_to_cover_signal		= False

		nonlocal final_buy_signal		; final_buy_signal		= False
		nonlocal final_sell_signal		; final_sell_signal		= False
		nonlocal final_short_signal		; final_short_signal		= False
		nonlocal final_buy_to_cover_signal	; final_buy_to_cover_signal	= False

		nonlocal exit_percent_signal		; exit_percent_signal		= False

		nonlocal stochrsi_signal		; stochrsi_signal		= False
		nonlocal stochrsi_crossover_signal	; stochrsi_crossover_signal	= False
		nonlocal stochrsi_threshold_signal	; stochrsi_threshold_signal	= False

		nonlocal stochrsi_5m_signal		; stochrsi_5m_signal		= False
		nonlocal stochrsi_5m_crossover_signal	; stochrsi_5m_crossover_signal	= False
		nonlocal stochrsi_5m_threshold_signal	; stochrsi_5m_threshold_signal	= False
		nonlocal stochrsi_5m_final_signal	; stochrsi_5m_final_signal	= False

		nonlocal stochmfi_signal		; stochmfi_signal		= False
		nonlocal stochmfi_crossover_signal	; stochmfi_crossover_signal	= False
		nonlocal stochmfi_threshold_signal	; stochmfi_threshold_signal	= False
		nonlocal stochmfi_final_signal		; stochmfi_final_signal		= False

		nonlocal stochmfi_5m_signal		; stochmfi_5m_signal		= False
		nonlocal stochmfi_5m_crossover_signal	; stochmfi_5m_crossover_signal	= False
		nonlocal stochmfi_5m_threshold_signal	; stochmfi_5m_threshold_signal	= False
		nonlocal stochmfi_5m_final_signal	; stochmfi_5m_final_signal	= False

		nonlocal rsi_signal			; rsi_signal			= False
		nonlocal mfi_signal			; mfi_signal			= False
		nonlocal adx_signal			; adx_signal			= False
		nonlocal dmi_signal			; dmi_signal			= False
		nonlocal macd_signal			; macd_signal			= False
		nonlocal aroonosc_signal		; aroonosc_signal		= False
		nonlocal vwap_signal			; vwap_signal			= False
		nonlocal vpt_signal			; vpt_signal			= False
		nonlocal resistance_signal		; resistance_signal		= False

		nonlocal chop_init_signal		; chop_init_signal		= False
		nonlocal chop_signal			; chop_signal			= False

		nonlocal plus_di_crossover		; plus_di_crossover		= False
		nonlocal minus_di_crossover		; minus_di_crossover		= False
		nonlocal macd_crossover			; macd_crossover		= False
		nonlocal macd_avg_crossover		; macd_avg_crossover		= False

		return True

	# END reset_signals

	# Set test parameters based on params{}
	# Syntax is as follows:
	#
	#  Parameter			Default Value	Otherwise, use what was passed in params['var']
	#
	#  var			=	default_value	if ( 'var' not in params ) else params['var']

	# Test range and input options
	start_date 		=	None		if ('start_date' not in params) else params['start_date']
	stop_date		=	None		if ('stop_date' not in params) else params['stop_date']
	safe_open		=	True		if ('safe_open' not in params) else params['safe_open']
	weekly_ph		=	None		if ('weekly_ph' not in params) else params['weekly_ph']
	daily_ph		=	None		if ('daily_ph' not in params) else params['daily_ph']

	debug			=	False		if ('debug' not in params) else params['debug']
	debug_all		=	False		if ('debug_all' not in params) else params['debug_all']

	# Trade exit parameters
	incr_threshold		=	1		if ('incr_threshold' not in params) else params['incr_threshold']
	decr_threshold		=	1.5		if ('decr_threshold' not in params) else params['decr_threshold']
	stoploss		=	False		if ('stoploss' not in params) else params['stoploss']
	exit_percent		=	None		if ('exit_percent' not in params) else params['exit_percent']
	quick_exit		=	False		if ('quick_exit' not in params) else params['quick_exit']
	strict_exit_percent	=	False		if ('strict_exit_percent' not in params) else params['strict_exit_percent']
	vwap_exit		=	False		if ('vwap_exit' not in params) else params['vwap_exit']
	variable_exit		=	False		if ('variable_exit' not in params) else params['variable_exit']
	hold_overnight		=	False		if ('hold_overnight' not in params) else params['hold_overnight']

	# Stock shorting options
	noshort			=	False		if ('noshort' not in params) else params['noshort']
	shortonly		=	False		if ('shortonly' not in params) else params['shortonly']

	# Other stock behavior options
	blacklist_earnings	=	False		if ('blacklist_earnings' not in params) else params['blacklist_earnings']
	check_volume		=	False		if ('check_volume' not in params) else params['check_volume']
	avg_volume		=	2000000		if ('avg_volume' not in params) else params['avg_volume']
	min_volume		=	1500000		if ('min_volume' not in params) else params['min_volume']
	min_ticker_age		=	None		if ('min_ticker_age' not in params) else params['min_ticker_age']
	min_daily_natr		=	None		if ('min_daily_natr' not in params) else params['min_daily_natr']
	max_daily_natr		=	None		if ('max_daily_natr' not in params) else params['max_daily_natr']
	min_intra_natr		=	None		if ('min_intra_natr' not in params) else params['min_intra_natr']
	max_intra_natr		=	None		if ('max_intra_natr' not in params) else params['max_intra_natr']

	# Indicators
	primary_stoch_indicator	=	'stochrsi'	if ('primary_stoch_indicator' not in params) else params['primary_stoch_indicator']
	with_stoch_5m		=	False		if ('with_stoch_5m' not in params) else params['with_stoch_5m']
	with_stochrsi_5m	=	False		if ('with_stochrsi_5m' not in params) else params['with_stochrsi_5m']
	with_stochmfi		=	False		if ('with_stochmfi' not in params) else params['with_stochmfi']
	with_stochmfi_5m	=	False		if ('with_stochmfi_5m' not in params) else params['with_stochmfi_5m']

	with_rsi		=	False		if ('with_rsi' not in params) else params['with_rsi']
	with_rsi_simple		=	False		if ('with_rsi_simple' not in params) else params['with_rsi_simple']

	with_dmi		=	False		if ('with_dmi' not in params) else params['with_dmi']
	with_dmi_simple		=	False		if ('with_dmi_simple' not in params) else params['with_dmi_simple']
	with_adx		=	False		if ('with_adx' not in params) else params['with_adx']

	with_macd		=	False		if ('with_macd' not in params) else params['with_macd']
	with_macd_simple	=	False		if ('with_macd_simple' not in params) else params['with_macd_simple']

	with_aroonosc		=	False		if ('with_aroonosc' not in params) else params['with_aroonosc']
	with_aroonosc_simple	=	False		if ('with_aroonosc_simple' not in params) else params['with_aroonosc_simple']

	with_mfi		=	False		if ('with_mfi' not in params) else params['with_mfi']

	with_vpt		=	False		if ('with_vpt' not in params) else params['with_vpt']
	with_vwap		=	False		if ('with_vwap' not in params) else params['with_vwap']
	with_chop_index		=	False		if ('with_chop_index' not in params) else params['with_chop_index']
	with_chop_simple	=	False		if ('with_chop_simple' not in params) else params['with_chop_simple']

	# Indicator parameters and modifiers
	stochrsi_period		=	128		if ('stochrsi_period' not in params) else params['stochrsi_period']
	stochrsi_5m_period	=	28		if ('stochrsi_5m_period' not in params) else params['stochrsi_5m_period']
	rsi_period		=	14		if ('rsi_period' not in params) else params['rsi_period']
	rsi_type		=	'hlc3'		if ('rsi_type' not in params) else params['rsi_type']
	rsi_slow		=	3		if ('rsi_slow' not in params) else params['rsi_slow']
	rsi_k_period		=	128		if ('rsi_k_period' not in params) else params['rsi_k_period']
	rsi_d_period		=	3		if ('rsi_d_period' not in params) else params['rsi_d_period']
	rsi_low_limit		=	20		if ('rsi_low_limit' not in params) else params['rsi_low_limit']
	rsi_high_limit		=	80		if ('rsi_high_limit' not in params) else params['rsi_high_limit']
	stochrsi_offset		=	8		if ('stochrsi_offset' not in params) else params['stochrsi_offset']
	nocrossover		=	False		if ('nocrossover' not in params) else params['nocrossover']
	crossover_only		=	False		if ('crossover_only' not in params) else params['crossover_only']

	di_period		=	48		if ('di_period' not in params) else params['di_period']
	adx_period		=	92		if ('adx_period' not in params) else params['adx_period']
	adx_threshold		=	25		if ('adx_threshold' not in params) else params['adx_threshold']

	macd_short_period	=	48		if ('macd_short_period' not in params) else params['macd_short_period']
	macd_long_period	=	104		if ('macd_long_period' not in params) else params['macd_long_period']
	macd_signal_period	=	36		if ('macd_signal_period' not in params) else params['macd_signal_period']
	macd_offset		=	0.006		if ('macd_offset' not in params) else params['macd_offset']

	aroonosc_period		=	24		if ('aroonosc_period' not in params) else params['aroonosc_period']
	aroonosc_alt_period	=	48		if ('aroonosc_alt_period' not in params) else params['aroonosc_alt_period']
	aroonosc_alt_threshold	=	0.24		if ('aroonosc_alt_threshold' not in params) else params['aroonosc_alt_threshold']
	aroonosc_secondary_threshold	= 70		if ('aroonosc_secondary_threshold' not in params) else params['aroonosc_secondary_threshold']
	aroonosc_with_macd_simple	= False		if ('aroonosc_with_macd_simple' not in params) else params['aroonosc_with_macd_simple']
	aroonosc_with_vpt		= False		if ('aroonosc_with_vpt' not in params) else params['aroonosc_with_vpt']

	stochmfi_5m_period	=	14		if ('stochmfi_5m_period' not in params) else params['stochmfi_5m_period']
	stochmfi_period		=	14		if ('stochmfi_period' not in params) else params['stochmfi_period']
	mfi_period		=	14		if ('mfi_period' not in params) else params['mfi_period']
	mfi_low_limit		=	20		if ('mfi_low_limit' not in params) else params['mfi_low_limit']
	mfi_high_limit		=	80		if ('mfi_high_limit' not in params) else params['mfi_high_limit']

	atr_period		=	14		if ('atr_period' not in params) else params['atr_period']
	daily_atr_period	=	14		if ('daily_atr_period' not in params) else params['daily_atr_period']
	vpt_sma_period		=	72		if ('vpt_sma_period' not in params) else params['vpt_sma_period']

	chop_period		=	14		if ('chop_period' not in params) else params['chop_period']
	chop_low_limit		=	38.2		if ('chop_low_limit' not in params) else params['chop_low_limit']
	chop_high_limit		=	61.8		if ('chop_high_limit' not in params) else params['chop_high_limit']

	stochrsi_signal_cancel_low_limit	= 60	if ('stochrsi_signal_cancel_low_limit' not in params) else params['stochrsi_signal_cancel_low_limit']
	stochrsi_signal_cancel_high_limit	= 40	if ('stochrsi_signal_cancel_high_limit' not in params) else params['stochrsi_signal_cancel_high_limit']
	rsi_signal_cancel_low_limit		= 40	if ('rsi_signal_cancel_low_limit' not in params) else params['rsi_signal_cancel_low_limit']
	rsi_signal_cancel_high_limit		= 60	if ('rsi_signal_cancel_high_limit' not in params) else params['rsi_signal_cancel_high_limit']
	mfi_signal_cancel_low_limit		= 30	if ('mfi_signal_cancel_low_limit' not in params) else params['mfi_signal_cancel_low_limit']
	mfi_signal_cancel_high_limit		= 70	if ('mfi_signal_cancel_high_limit' not in params) else params['mfi_signal_cancel_high_limit']

	# Resistance indicators
	no_use_resistance	=	False		if ('no_use_resistance' not in params) else params['no_use_resistance']
	price_resistance_pct	=	1		if ('price_resistance_pct' not in params) else params['price_resistance_pct']
	price_support_pct	=	1		if ('price_support_pct' not in params) else params['price_support_pct']
	use_natr_resistance	=	False		if ('use_natr_resistance' not in params) else params['use_natr_resistance']
	lod_hod_check		=	False		if ('lod_hod_check' not in params) else params['lod_hod_check']
	keylevel_strict		=	False		if ('keylevel_strict' not in params) else params['keylevel_strict']
	keylevel_use_daily	=	False		if ('keylevel_use_daily' not in params) else params['keylevel_use_daily']
	check_daily_natr	=	False		if ('check_daily_natr' not in params) else params['check_daily_natr']
	check_ma_strict		=	False		if ('check_ma_strict' not in params) else params['check_ma_strict']
	check_ma		=	False		if ('check_ma' not in params) else params['check_ma']
	check_ma		=	True		if (check_ma_strict == True ) else check_ma ; params['check_ma'] = check_ma
	sma_period		=	5		if ('sma_period' not in params) else params['sma_period']
	ema_period		=	5		if ('ema_period' not in params) else params['ema_period']

	check_etf_indicators	=	False		if ('check_etf_indicators' not in params) else params['check_etf_indicators']
	etf_tickers		=  ['SPY','QQQ','DIA']	if ('etf_tickers' not in params) else params['etf_tickers']
	etf_indicators		=	{}		if ('etf_indicators' not in params) else params['etf_indicators']
	# End params{} configuration


	# If set, turn start_date and/or stop_date into a datetime object
	if ( start_date != None ):
		start_date = datetime.strptime(start_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
		start_date = mytimezone.localize(start_date)
	if ( stop_date != None ):
		stop_date = datetime.strptime(stop_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
		stop_date = mytimezone.localize(stop_date)

	# 5-minute candles
	pricehistory_5m = { 'candles': [], 'ticker': ticker }
	for idx,key in enumerate(pricehistory['candles']):
		if ( idx == 0 ):
			continue

		cndl_num = idx + 1
		if ( cndl_num % 5 == 0 ):
			open_p	= float( pricehistory['candles'][idx - 4]['open'] )
			close	= float( pricehistory['candles'][idx]['close'] )
			high	= 0
			low	= 9999
			volume	= 0

			for i in range(4,0,-1):
				volume += int( pricehistory['candles'][idx-i]['volume'] )

				if ( high < float(pricehistory['candles'][idx-i]['high']) ):
					high = float( pricehistory['candles'][idx-i]['high'] )

				if ( low > float(pricehistory['candles'][idx-i]['low']) ):
					low = float( pricehistory['candles'][idx-i]['low'] )

			newcandle = {	'open':		open_p,
					'high':		high,
					'low':		low,
					'close':	close,
					'volume':	volume,
					'datetime':	pricehistory['candles'][idx]['datetime'] }

			pricehistory_5m['candles'].append(newcandle)

	del(open_p, high, low, close, volume, newcandle)

	# Get stochastic RSI/MFI
	stochrsi	= []
	rsi_k		= []
	rsi_d		= []
	try:
		if ( primary_stoch_indicator == 'stochrsi' ):
			if ( with_stoch_5m == True ):
				stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(pricehistory_5m, rsi_period=rsi_period, stochrsi_period=stochrsi_5m_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)
			else:
				stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(pricehistory, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

			if ( isinstance(stochrsi, bool) and stochrsi == False ):
				print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi() returned false - no data', file=sys.stderr)
				return False

		elif ( primary_stoch_indicator == 'stochmfi' ):
			if ( with_stoch_5m == True ):
				rsi_k, rsi_d = tda_gobot_helper.get_stochmfi(pricehistory_5m, mfi_period=mfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)
			else:
				rsi_k, rsi_d = tda_gobot_helper.get_stochmfi(pricehistory, mfi_period=mfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)

			stochrsi = rsi_k
			if ( isinstance(rsi_k, bool) and rsi_k == False ):
				print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi() returned false - no data', file=sys.stderr)
				return False

		else:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): unknown primary_stoch_indicator "' + str(primary_stoch_indicator) + '"')
			sys.exit(1)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi(): ' + str(e))
		return False

	# If using the same 1-minute data, the len of stochrsi will be (stochrsi_period * 2 - 1)
	# len(rsi_k) should be (stochrsi_period * 2 - rsi_d_period)
	if ( primary_stoch_indicator == 'stochrsi' and with_stoch_5m == False ):
		if ( len(stochrsi) != len(pricehistory['candles']) - (rsi_period * 2 - 1) ):
			print( 'Warning, unexpected length of stochrsi (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(stochrsi)=' + str(len(stochrsi)) + ')' )

		if ( len(rsi_k) != len(pricehistory['candles']) - (stochrsi_period + rsi_k_period + rsi_d_period) ):
			print( 'Warning, unexpected length of rsi_k (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(rsi_k)=' + str(len(rsi_k)) + ')' )
		if ( len(rsi_k) != len(rsi_d) ):
			print( 'Warning, unexpected length of rsi_k (pricehistory[candles]=' + str(len(pricehistory['candles'])) +
				', len(rsi_k)=' + str(len(stochrsi)) + '), len(rsi_d)=' + str(len(rsi_d)) + ')' )

	# Get secondary stochastic indicators
	if ( with_stochrsi_5m == True ):
		stochrsi_5m	= []
		rsi_k_5m	= []
		rsi_d_5m	= []
		try:
			stochrsi, rsi_k_5m, rsi_d_5m = tda_gobot_helper.get_stochrsi(pricehistory_5m, rsi_period=rsi_period, stochrsi_period=stochrsi_5m_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

		except Exception as e:
			print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi(): ' + str(e))
			return False
		if ( isinstance(stochrsi_5m, bool) and stochrsi_5m == False ):
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi() returned false - no data', file=sys.stderr)
			return False

	if ( with_stochmfi == True ):
		mfi_k		= []
		mfi_d		= []
		try:
			mfi_k, mfi_d = tda_gobot_helper.get_stochmfi(pricehistory, mfi_period=stochmfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)

		except Exception as e:
			print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi(): ' + str(e))
			return False
		if ( isinstance(mfi_k, bool) and mfi_k == False ):
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi() returned false - no data', file=sys.stderr)
			return False

	if ( with_stochmfi_5m == True ):
		mfi_k_5m	= []
		mfi_d_5m	= []
		try:
			mfi_k_5m, mfi_d_5m = tda_gobot_helper.get_stochmfi(pricehistory_5m, mfi_period=stochmfi_5m_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)

		except Exception as e:
			print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi(): ' + str(e))
			return False
		if ( isinstance(mfi_k_5m, bool) and mfi_k_5m == False ):
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi() returned false - no data', file=sys.stderr)
			return False

	# Get RSI
	try:
		rsi = tda_gobot_helper.get_rsi(pricehistory, rsi_period, rsi_type, debug=False)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_rsi(): ' + str(e))
		return False

	# Get MFI
	try:
		mfi = tda_gobot_helper.get_mfi(pricehistory, period=mfi_period)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_mfi(): ' + str(e))

	# Average True Range (ATR)
	atr	= []
	natr	= []
	try:
		atr, natr = tda_gobot_helper.get_atr( pricehistory=pricehistory_5m, period=atr_period )

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_atr(): ' + str(e))
		return False

	# Daily ATR/NATR
	if ( daily_ph == None ):

		# get_pricehistory() variables
		p_type	= 'year'
		period	= '2'
		freq	= '1'
		f_type	= 'daily'

		tries	= 0
		while ( tries < 3 ):
			daily_ph, ep = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, needExtendedHoursData=False)
			if ( isinstance(daily_ph, bool) and daly_ph == False ):
				print('Error: get_pricehistory(' + str(ticker) + '): attempt ' + str(tries) + ' returned False, retrying...', file=sys.stderr)
				time.sleep(5)
			else:
				break

			tries += 1

	atr_d	= []
	natr_d	= []
	try:
		atr_d, natr_d = tda_gobot_helper.get_atr( pricehistory=daily_ph, period=daily_atr_period )

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_atr(): ' + str(e))
		return False

	if ( min_ticker_age != None ):
		if ( len(atr_d) + daily_atr_period < min_ticker_age ):
			print('Error: ' + str(ticker) + ' appears to be younger than min_ticker_age (' + str(len(atr_d)+daily_atr_period) + '), exiting.')
			sys.exit(1)

	daily_natr = OrderedDict()
	for idx in range(-1, -len(atr_d), -1):
		day = datetime.fromtimestamp(int(daily_ph['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
		if day not in daily_natr:
			daily_natr[day] = { 'atr': atr_d[idx], 'natr': natr_d[idx] }

	# End ATR

	# ADX, +DI, -DI
	# We now use different periods for adx and plus/minus_di
	if ( with_dmi == True and with_dmi_simple == True ):
		with_dmi_simple = False

	adx = []
	plus_di = []
	minus_di = []
	try:
		adx, plus_di, minus_di = tda_gobot_helper.get_adx(pricehistory, period=di_period)
		adx, plus_di_adx, minus_di_adx = tda_gobot_helper.get_adx(pricehistory, period=adx_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_adx(): ' + str(e))
		return False

	# Aroon Oscillator
	# aroonosc_with_macd_simple implies that macd_simple will be enabled or disabled based on the
	#  level of the aroon oscillator (i.e. < aroonosc_secondary_threshold then use macd_simple)
	if ( aroonosc_with_macd_simple == True ):
		with_aroonosc = True
		with_macd = False
		with_macd_simple = False

	aroonosc = []
	aroonosc_alt = []
	try:
		aroonosc = tda_gobot_helper.get_aroon_osc(pricehistory, period=aroonosc_period)
		aroonosc_alt = tda_gobot_helper.get_aroon_osc(pricehistory, period=aroonosc_alt_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_aroon_osc(): ' + str(e))
		return False

	# MACD - 48, 104, 36
	if ( with_macd == True and with_macd_simple == True):
		with_macd_simple = False

	macd = []
	macd_signal = []
	macd_histogram = []
	try:
		macd, macd_avg, macd_histogram = tda_gobot_helper.get_macd(pricehistory, short_period=macd_short_period, long_period=macd_long_period, signal_period=macd_signal_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_macd(): ' + str(e))
		return False

	# Choppiness Index
	chop = []
	try:
		chop = tda_gobot_helper.get_chop_index(pricehistory, period=chop_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_chop_index(): ' + str(e))
		return False

	# VPT - Volume Price Trend
	vpt = []
	vpt_sma = []
	try:
		vpt, vpt_sma = tda_gobot_helper.get_vpt(pricehistory, period=vpt_sma_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_vpt(): ' + str(e))
		return False

	# Calculate daily volume from the 1-minute candles that we have
	if ( check_volume == True ):
		daily_volume = OrderedDict()
		for key in pricehistory['candles']:
			day = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
			if day not in daily_volume:
				daily_volume[day] = { 'volume': int(key['volume']), 'trade': True }
			else:
				daily_volume[day]['volume'] += int(key['volume'])

		for idx,day in enumerate(daily_volume):
			avg_vol = 0
			if ( idx == 0 ):
				if ( daily_volume[day]['volume'] < min_volume ):
					daily_volume[day]['trade'] = False

			elif ( idx < 5 ):
				# Add up the previous days of volume (but not the current day)
				for i in range(0, idx, 1):
					avg_vol += list(daily_volume.values())[i]['volume']
					if ( list(daily_volume.values())[i]['volume'] < min_volume ):
						daily_volume[day]['trade'] = False
						break

				avg_vol = avg_vol / idx
				if ( avg_vol < avg_volume ):
					daily_volume[day]['trade'] = False

			else:
				# Add up the previous SIX days of volume (but not the current day)
				for i in range(idx-6, idx, 1):
					avg_vol += list(daily_volume.values())[i]['volume']
					if ( list(daily_volume.values())[i]['volume'] < min_volume ):
						daily_volume[day]['trade'] = False
						break

				avg_vol = avg_vol / 6
				if ( avg_vol < avg_volume ):
					daily_volume[day]['trade'] = False

	# End daily volume check

	# Blacklist the week before and after earnings reporting
	if ( blacklist_earnings == True ):

		import av_gobot_helper
		earnings = av_gobot_helper.av_get_earnings( ticker=ticker, type='reported' )
		if ( earnings == False ):
			print('Error: (' + str(ticker) + '): --blacklist_earnings was set but av_gobot_helper.av_get_earnings() returned False')
			return False

		earnings_blacklist = {}
		for day in earnings:
			date = datetime.strptime(day, '%Y-%m-%d')
			date = mytimezone.localize(date)
			start_blacklist	= date
			end_blacklist	= date + timedelta( days=2 )

			entry = { day: { 'start_blacklist': start_blacklist, 'end_blacklist': end_blacklist } }
			earnings_blacklist.update( entry )

	# End earnings blacklist

	# Calculate vwap and/or vwap_exit
	if ( with_vwap == True or vwap_exit == True or no_use_resistance == False ):
		vwap_vals = OrderedDict()
		days = OrderedDict()

		# Create a dict containing all the days and timestamps for which we need vwap data
		prev_day = ''
		prev_timestamp = ''
		for key in pricehistory['candles']:

			day = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
			if day not in days:
				days[day] = { 'start': key['datetime'], 'end': '', 'timestamps': [] }
				if ( prev_day != '' ):
					days[prev_day]['end'] = prev_timestamp

			prev_day = day
			prev_timestamp = key['datetime']
			days[day]['timestamps'].append(key['datetime'])

		days[day]['end'] = prev_timestamp

		# Calculate the VWAP data for each day in days{}
		for key in days:
			try:
				vwap, vwap_up, vwap_down = tda_gobot_helper.get_vwap(pricehistory, day=key, end_timestamp=days[key]['end'], num_stddev=2)

			except Exception as e:
				print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_vwap(): ' + str(e), file=sys.stderr)
				return False

			if ( len(vwap) != len(days[key]['timestamps']) ):
				print('WARNING: len(vwap) != len(days[key][timestamps]): ' + str(len(vwap)) + ', ' + str(len(days[key]['timestamps'])))

			for idx,val in enumerate(vwap):
				vwap_vals.update( { days[key]['timestamps'][idx]: {
							'vwap': float(val),
							'vwap_up': float(vwap_up[idx]),
							'vwap_down': float(vwap_down[idx]) }
						} )

	# Resistance / Support
	if ( no_use_resistance == False ):

		# Day stats
		pdc = OrderedDict()
		for key in pricehistory['candles']:

			today = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone)
			time = today.strftime('%H:%M')

			yesterday = today - timedelta(days=1)
			yesterday = tda_gobot_helper.fix_timestamp(yesterday)

			today = today.strftime('%Y-%m-%d')
			yesterday = yesterday.strftime('%Y-%m-%d')

			if ( today not in pdc ):
				pdc[today] = {  'open':		0,
						'high':		0,
						'low':		100000,
						'close':	0,
						'pdc':		0 }

			if ( yesterday in pdc ):
				pdc[today]['pdc'] = float(pdc[yesterday]['close'])

			if ( float(key['close']) > pdc[today]['high'] ):
				pdc[today]['high'] = float(key['close'])

			if ( float(key['close']) < pdc[today]['low'] ):
				pdc[today]['low'] = float(key['close'])

			if ( time == '09:30'):
				pdc[today]['open'] = float(key['open'])

			elif ( time == '16:00'):
				pdc[today]['close'] = float(key['close'])

		# Key levels
		klfilter = False
		if ( weekly_ph == None ):

			# get_pricehistory() variables
			p_type = 'year'
			period = '2'
			freq = '1'
			f_type = 'weekly'

			if ( keylevel_use_daily == True ):
				f_type = 'daily'

				klfilter = True
				if ( keylevel_strict == True ):
					klfilter = False

			tries = 0
			while ( tries < 3 ):
				weekly_ph, ep = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, needExtendedHoursData=False)
				if ( isinstance(weekly_ph, bool) and weekly_ph == False ):
					print('Error: get_pricehistory(' + str(ticker) + '): attempt ' + str(tries) + ' returned False, retrying...', file=sys.stderr)
					time.sleep(5)
				else:
					break

				tries += 1

		long_support, long_resistance = tda_gobot_helper.get_keylevels(weekly_ph, filter=klfilter)

		# Three/Twenty week high/low
#		three_week_high = three_week_low = three_week_avg = -1
		twenty_week_high = twenty_week_low = twenty_week_avg = -1

#		try:
#			# 3-week high / low / average
#			three_week_high, three_week_low, three_week_avg = tda_gobot_helper.get_price_stats(ticker, days=15)
#
#		except Exception as e:
#			print('Warning: stochrsi_analyze_new(' + str(ticker) + '): get_price_stats(): ' + str(e))
#
#		try:
#			# 20-week high / low / average
#			twenty_week_high, twenty_week_low, twenty_week_avg = tda_gobot_helper.get_price_stats(ticker, days=100)
#
#		except Exception as e:
#			print('Warning: stochrsi_analyze_new(' + str(ticker) + '): get_price_stats(): ' + str(e))


	# Intraday SMA/EMA
	# We can use this to tailor the stochastic indicator high/low levels based on the 5-minute SMA/EMA behavior
	sma = []
	ema = []
	try:
		sma = tda_gobot_helper.get_sma( pricehistory_5m, period=sma_period, type='hlc3' )
		ema = tda_gobot_helper.get_ema( pricehistory_5m, period=ema_period )

	except Exception as e:
		print('Error, unable to calculate SMA/EMA: ' + str(e))
		sma[0] = 0
		ema[0] = 0

	# Daily SMA/EMA
	daily_sma = []
	daily_ema = []
	try:
		daily_sma = tda_gobot_helper.get_sma( pricehistory=daily_ph, period=10, type='hlc3' )
		daily_ema = tda_gobot_helper.get_ema( pricehistory=daily_ph, period=5 )

	except Exception as e:
		print('Error, unable to calculate SMA/EMA: ' + str(e))
		daily_sma[0] = 0
		daily_ema[0] = 0

	daily_ma = OrderedDict()
	for idx in range(-1, -len(daily_sma), -1):
		day = datetime.fromtimestamp(int(daily_ph['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
		if day not in daily_ma:
			daily_ma[day] = { 'sma': daily_sma[idx], 'ema': daily_ema[idx] }

	# End SMA/EMA

	# Populate SMA/EMA for etf indicators
	if ( check_etf_indicators == True ):
		if ( len(etf_indicators) == 0 ):
			print('Error: etf_indicators{} is empty, exiting.')
			sys.exit(1)

		all_datetime = []
		for t in etf_tickers:
			etf_indicators[t]['sma'] = {}
			etf_indicators[t]['ema'] = {}

			sma = []
			ema = []
			try:
				sma = tda_gobot_helper.get_sma( etf_indicators[t]['pricehistory'], period=sma_period, type='hlc3' )
				ema = tda_gobot_helper.get_ema( etf_indicators[t]['pricehistory'], period=ema_period )

			except Exception as e:
				print('Error, unable to calculate SMA/EMA for ticker ' + str(t) + ': ' + str(e))
				sys.exit(1)

			# Note:
			#  len(sma) = len(pricehistory) - sma_period-1
			#  len(ema) = len(pricehistory)
			for i in range( 0, len(sma) ):
				# Format:
				#  etf_indicators[t]['sma'] = { cur_datetime: cur_sma, ... }
				cur_datetime = int( etf_indicators[t]['pricehistory']['candles'][i+sma_period-1]['datetime'] )
				etf_indicators[t]['sma'][cur_datetime] = sma[i]
				etf_indicators[t]['ema'][cur_datetime] = ema[i+sma_period-1]

			all_datetime = all_datetime + list( etf_indicators[t]['sma'].keys() )

		all_datetime = list(dict.fromkeys(all_datetime))
		etf_indicators['sma_avg'] = {}
		etf_indicators['ema_avg'] = {}
		for i in all_datetime:
			found = 0
			etf_indicators['sma_avg'][i] = 0
			etf_indicators['ema_avg'][i] = 0
			for t in etf_tickers:
				if ( i not in etf_indicators[t]['sma'] ):
					continue

				found += 1
				etf_indicators['sma_avg'][i] += etf_indicators[t]['sma'][i]
				etf_indicators['ema_avg'][i] += etf_indicators[t]['ema'][i]

			etf_indicators['sma_avg'][i] = etf_indicators['sma_avg'][i] / found
			etf_indicators['ema_avg'][i] = etf_indicators['ema_avg'][i] / found


	# Run through the RSI values and log the results
	results				= []

	stochrsi_idx			= len(pricehistory['candles']) - len(rsi_k)
	if ( with_stoch_5m == True ):
		stochrsi_5m_idx		= len(pricehistory['candles']) - len(rsi_k) * 5
	if ( with_stochrsi_5m == True ):
		stochrsi_5m_idx		= len(pricehistory['candles']) - len(rsi_k_5m) * 5
	if ( with_stochmfi == True ):
		stochmfi_idx		= len(pricehistory['candles']) - len(mfi_k)
	if ( with_stochmfi_5m == True ):
		stochmfi_5m_idx		= len(pricehistory['candles']) - len(mfi_k_5m) * 5

	rsi_idx				= len(pricehistory['candles']) - len(rsi)
	mfi_idx				= len(pricehistory['candles']) - len(mfi)
	adx_idx				= len(pricehistory['candles']) - len(adx)
	di_idx				= len(pricehistory['candles']) - len(plus_di)
	aroonosc_idx			= len(pricehistory['candles']) - len(aroonosc)
	aroonosc_alt_idx		= len(pricehistory['candles']) - len(aroonosc_alt)
	macd_idx			= len(pricehistory['candles']) - len(macd)
	chop_idx			= len(pricehistory['candles']) - len(chop)

	buy_signal			= False
	sell_signal			= False
	short_signal			= False
	buy_to_cover_signal		= False

	final_buy_signal		= False
	final_sell_signal		= False
	final_short_signal		= False
	final_buy_to_cover_signal	= False

	exit_percent_signal		= False

	stochrsi_signal			= False
	stochrsi_crossover_signal	= False
	stochrsi_threshold_signal	= False

	stochrsi_5m_signal		= False
	stochrsi_5m_crossover_signal	= False
	stochrsi_5m_threshold_signal	= False
	stochrsi_5m_final_signal	= False

	stochmfi_signal			= False
	stochmfi_crossover_signal	= False
	stochmfi_threshold_signal	= False
	stochmfi_final_signal		= False

	stochmfi_5m_signal		= False
	stochmfi_5m_crossover_signal	= False
	stochmfi_5m_threshold_signal	= False
	stochmfi_5m_final_signal	= False

	rsi_signal			= False
	mfi_signal			= False
	adx_signal			= False
	dmi_signal			= False
	macd_signal			= False
	aroonosc_signal			= False
	vwap_signal			= False
	vpt_signal			= False
	resistance_signal		= False

	chop_init_signal		= False
	chop_signal			= False

	plus_di_crossover		= False
	minus_di_crossover		= False
	macd_crossover			= False
	macd_avg_crossover		= False

	default_incr_threshold		= incr_threshold
	default_decr_threshold		= decr_threshold
	orig_incr_threshold		= incr_threshold
	orig_decr_threshold		= decr_threshold
	orig_exit_percent		= exit_percent

	ma_intraday_affinity		= None
	ma_daily_affinity		= None

	stochrsi_default_low_limit	= 20
	stochrsi_default_high_limit	= 80

	orig_rsi_low_limit		= rsi_low_limit
	orig_rsi_high_limit		= rsi_high_limit

	rsi_signal_cancel_low_limit	= 40
	rsi_signal_cancel_high_limit	= 60

	default_chop_low_limit		= 38.2
	default_chop_high_limit		= 61.8

	stochrsi_signal_cancel_low_limit  = 60	# Cancel stochrsi short signal at this level
	stochrsi_signal_cancel_high_limit = 40	# Cancel stochrsi buy signal at this level

	first_day			= datetime.fromtimestamp(float(pricehistory['candles'][0]['datetime'])/1000, tz=mytimezone)
	start_day			= first_day + timedelta( days=1 )
	start_day_epoch			= int( start_day.timestamp() * 1000 )

	last_hour_threshold		= 0.2 # Last hour trading threshold

	signal_mode = 'buy'
	if ( shortonly == True ):
		signal_mode = 'short'


	# Choppiness Index
	def get_chop_signal(simple=False, prev_chop=-1, cur_chop=-1, chop_init_signal=False, chop_signal=False):

		nonlocal chop_high_limit
		nonlocal chop_low_limit
		nonlocal default_chop_high_limit

		if ( simple == True ):
			# Chop simple algo can be used as a weak signal to help confirm trendiness,
			#  but no crossover from high->low is required
			if ( cur_chop < chop_high_limit and cur_chop > chop_low_limit ):
				chop_init_signal = True
				chop_signal = True
			elif ( cur_chop > chop_high_limit or cur_chop < chop_low_limit ):
				chop_init_signal = False
				chop_signal = False

		else:
			if ( prev_chop > chop_high_limit and cur_chop <= chop_high_limit ):
				chop_init_signal = True

			if ( chop_init_signal == True and chop_signal == False ):
				if ( cur_chop <= default_chop_high_limit ):
					chop_signal = True

			if ( chop_signal == True ):
				if ( cur_chop > default_chop_high_limit ):
					chop_init_signal = False
					chop_signal = False

				elif ( prev_chop < chop_low_limit and cur_chop < chop_low_limit ):
					if ( cur_chop > prev_chop ):
						# Trend may be reversing, cancel the signal
						chop_init_signal = False
						chop_signal = False

		return chop_init_signal, chop_signal


	# StochRSI/StochMFI long algorithm
	def get_stoch_signal_long(cur_k=0, cur_d=0, prev_k=0, prev_d=0, stoch_signal=False, crossover_signal=False, threshold_signal=False, final_signal=False):

		nonlocal rsi_low_limit				; stoch_low_limit		= rsi_low_limit
		nonlocal rsi_high_limit				; stoch_high_limit		= rsi_high_limit
		nonlocal stochrsi_offset			; stoch_offset			= stochrsi_offset
		nonlocal stochrsi_default_low_limit		; stoch_default_low_limit	= stochrsi_default_low_limit
		nonlocal stochrsi_default_high_limit		; stoch_default_high_limit	= stochrsi_default_high_limit
		nonlocal nocrossover
		nonlocal crossover_only

		# Signal the primary stoch signal if K and D cross the low limit threshold
		if ( cur_k < stoch_low_limit and cur_d < stoch_low_limit ):
			stoch_signal = True

			# Monitor if K and D intersect - this must happen below the stoch_low_limit
			# A buy signal occurs when an increasing %K line crosses above the %D line in the oversold region.
			#  or if the %K line crosses below the low limit
			if ( prev_k < prev_d and cur_k >= cur_d ):
				crossover_signal = True

		# Cancel the crossover signal if K wanders back below D
		if ( crossover_signal == True ):
			if ( prev_k > prev_d and cur_k <= cur_d ):
				crossover_signal = False

		if ( stoch_signal == True ):

			# If stoch signal was triggered, monitor K to see if it breaks up above default_low_limit
			if ( prev_k < stoch_default_low_limit and cur_k > prev_k ):
				if ( cur_k >= stoch_default_low_limit ):
					threshold_signal = True

			# If the crossover or threshold signals have been triggered, then next test the gap
			#  between K and D to confirm there is strength to this movement.
			if ( (crossover_signal == True and nocrossover == False) or
			     (threshold_signal == True and crossover_only == False) ):

				if ( cur_k - cur_d >= stoch_offset ):
					final_signal = True

		return stoch_signal, crossover_signal, threshold_signal, final_signal


	# StochRSI/StochMFI short algorithm
	def get_stoch_signal_short(cur_k=0, cur_d=0, prev_k=0, prev_d=0, stoch_signal=False, crossover_signal=False, threshold_signal=False, final_signal=False):

		nonlocal rsi_low_limit				; stoch_low_limit		= rsi_low_limit
		nonlocal rsi_high_limit				; stoch_high_limit		= rsi_high_limit
		nonlocal stochrsi_offset			; stoch_offset			= stochrsi_offset
		nonlocal stochrsi_default_low_limit		; stoch_default_low_limit	= stochrsi_default_low_limit
		nonlocal stochrsi_default_high_limit		; stoch_default_high_limit	= stochrsi_default_high_limit
		nonlocal nocrossover
		nonlocal crossover_only

		# Signal the primary stoch signal if K and D cross the high limit threshold
		if ( cur_k > stoch_high_limit and cur_d > stoch_high_limit ):
			stoch_signal = True

			# Monitor if K and D intercect - this must happen above the stoch_high_limit
			# A sell-short signal occurs when a decreasing %K line crosses below the %D line in the overbought region
			if ( prev_k > prev_d and cur_k <= cur_d ):
				crossover_signal = True

		# Cancel the crossover signal if K wanders back above D
		if ( crossover_signal == True ):
			if ( prev_k < prev_d and cur_k >= cur_d ):
				crossover_signal = False

		if ( stoch_signal == True ):

			# If stoch signal was triggered, monitor K to see if it breaks down below stoch_default_high_limit
			if ( prev_k > stoch_default_high_limit and cur_k < prev_k ):
				if ( cur_k <= stoch_default_high_limit ):
					threshold_signal = True

			# If the crossover or threshold signals have been triggered, then next test the gap
			#  between K and D to confirm there is strength to this movement.
			if ( (crossover_signal == True and nocrossover == False) or
			     (threshold_signal == True and crossover_only == False) ):

				if ( cur_d - cur_k >= stoch_offset ):
					final_signal = True

		return stoch_signal, crossover_signal, threshold_signal, final_signal


	##################################################################################################################
	# Main loop
	for idx,key in enumerate(pricehistory['candles']):

		# Skip the first day of data
		if ( float(pricehistory['candles'][idx]['datetime']) < start_day_epoch ):
			continue

		try:
			assert idx - stochrsi_idx >= 1
			assert int((idx - stochrsi_idx) / 5) - 1 >= 1

			assert idx - mfi_idx >= 1
			assert idx - adx_idx >= 0
			assert idx - di_idx >= 1
			assert idx - macd_idx >= 1
			assert idx - aroonosc_idx >= 0

		except:
			continue

		# Datetime object from the current timestamp
		date = datetime.fromtimestamp(int(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone)

		# Indicators current values
		cur_rsi_k	= rsi_k[idx - stochrsi_idx]
		prev_rsi_k	= rsi_k[idx - stochrsi_idx - 1]
		cur_rsi_d	= rsi_d[idx - stochrsi_idx]
		prev_rsi_d	= rsi_d[idx - stochrsi_idx - 1]

		if ( with_stoch_5m == True ):
			cur_rsi_k	= rsi_k[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_k	= rsi_k[int((idx - stochrsi_5m_idx) / 5) - 1]
			cur_rsi_d	= rsi_d[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_d	= rsi_d[int((idx - stochrsi_5m_idx) / 5) - 1]

		if ( with_stochrsi_5m == True ):
			cur_rsi_k_5m	= rsi_k_5m[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_k_5m	= rsi_k_5m[int((idx - stochrsi_5m_idx) / 5) - 1]
			cur_rsi_d_5m	= rsi_d_5m[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_d_5m	= rsi_d_5m[int((idx - stochrsi_5m_idx) / 5) - 1]

		if ( with_stochmfi == True ):
			cur_mfi_k	= mfi_k[idx - stochmfi_idx]
			prev_mfi_k	= mfi_k[idx - stochmfi_idx - 1]
			cur_mfi_d	= mfi_d[idx - stochmfi_idx]
			prev_mfi_d	= mfi_d[idx - stochmfi_idx - 1]

		if ( with_stochmfi_5m == True ):
			cur_mfi_k_5m	= mfi_k_5m[int((idx - stochmfi_5m_idx) / 5)]
			prev_mfi_k_5m	= mfi_k_5m[int((idx - stochmfi_5m_idx) / 5) - 1]
			cur_mfi_d_5m	= mfi_d_5m[int((idx - stochmfi_5m_idx) / 5)]
			prev_mfi_d_5m	= mfi_d_5m[int((idx - stochmfi_5m_idx) / 5) -1]

		cur_rsi			= rsi[idx - rsi_idx]
		prev_rsi		= rsi[idx - rsi_idx - 1]

		cur_mfi			= mfi[idx - mfi_idx]
		prev_mfi		= mfi[idx - mfi_idx - 1]

		cur_adx			= adx[idx - adx_idx]
		cur_plus_di		= plus_di[idx - di_idx]
		prev_plus_di		= plus_di[idx - di_idx - 1]
		cur_minus_di		= minus_di[idx - di_idx]
		prev_minus_di		= minus_di[idx - di_idx - 1]

		cur_macd		= macd[idx - macd_idx]
		prev_macd		= macd[idx - macd_idx - 1]

		cur_macd_avg		= macd_avg[idx - macd_idx]
		prev_macd_avg		= macd_avg[idx - macd_idx - 1]

		cur_aroonosc		= aroonosc[idx - aroonosc_idx]
		prev_aroonosc		= aroonosc[idx - aroonosc_idx - 1]
		cur_aroonosc_alt	= aroonosc_alt[idx - aroonosc_alt_idx]
		prev_aroonosc_alt	= aroonosc_alt[idx - aroonosc_alt_idx - 1]

		cur_vpt			= vpt[idx]
		prev_vpt		= vpt[idx-1]

		cur_vpt_sma		= vpt_sma[idx - vpt_sma_period]
		prev_vpt_sma		= vpt_sma[idx - vpt_sma_period]

		cur_atr			= atr[int(idx / 5) - atr_period]
		cur_natr		= natr[int(idx / 5) - atr_period]

		cur_chop		= chop[idx - chop_idx]
		prev_chop		= chop[idx - chop_idx - 1]

		cur_natr_daily = 0
		try:
			cur_natr_daily = daily_natr[date.strftime('%Y-%m-%d')]['natr']
		except:
			pass

		cur_daily_sma = 0
		cur_daily_ema = 0
		try:
			cur_daily_sma = daily_ma[date.strftime('%Y-%m-%d')]['sma']
			cur_daily_ema = daily_ma[date.strftime('%Y-%m-%d')]['ema']
		except:
			pass

		# EMA/SMA
		# 5min candles
		cur_sma		= round( sma[int(idx / 5) - sma_period], 3 )
		cur_ema		= round( ema[int(idx / 5) - 1], 3 )

		# 1min candles
		#cur_sma			= sma[idx - sma_period]
		#cur_ema			= ema[idx - 1]

		# Skip all candles until start_date, if it is set
		if ( start_date != None and date < start_date ):
			continue
		elif ( stop_date != None and date >= stop_date ):
			return results

		# Skip the week before/after earnings if --blacklist_earnings was set
		if ( blacklist_earnings == True ):
			blackout = False
			for day in earnings_blacklist:
				if ( date > earnings_blacklist[day]['start_blacklist'] and date < earnings_blacklist[day]['end_blacklist'] ):
					blackout = True
					break

			if ( blackout == True ):
				continue

		# Skip any days if check_volume marked it as low volume
		if ( check_volume == True ):
			day = date.strftime('%Y-%m-%d')
			if ( isinstance(daily_volume[day]['trade'], bool) and daily_volume[day]['trade'] == False ):
				continue

		# Ignore pre-post market since we cannot trade during those hours
		if ( tda_gobot_helper.ismarketopen_US(date, safe_open=safe_open) != True ):
			continue

		# Ignore days where cur_daily_natr is below min_daily_natr or above max_daily_natr, if configured
		if ( min_daily_natr != None and cur_natr_daily < min_daily_natr ):
			continue
		if ( max_daily_natr != None and cur_natr_daily > max_daily_natr ):
			continue

		# Tailor the rsi_low_limit and rsi_high_limit based on the SMA/EMA orientation
		#  to make the indicator more biased toward bullish or bearish trades
		if ( check_ma == True ):
			rsi_low_limit		= orig_rsi_low_limit
			rsi_high_limit		= orig_rsi_high_limit

			ma_intraday_affinity	= None
			ma_daily_affinity	= None

			check_ma_strict	 	= params['check_ma_strict']
			with_mfi	 	= params['with_mfi']

			# Price action is bullish
			if ( cur_ema > cur_sma ):
				ma_intraday_affinity	= 'bull'
				rsi_low_limit		= 15
				rsi_high_limit		= 95

			# Price action is bearish
			elif ( cur_ema < cur_sma ):
				ma_intraday_affinity	= 'bear'
				rsi_low_limit		= 10
				rsi_high_limit		= 90

			# Check daily affinity
			if ( cur_daily_ema > cur_daily_sma ):
				ma_daily_affinity = 'bull'
			elif ( cur_daily_ema < cur_daily_sma ):
				ma_daily_affinity = 'bear'

			if ( signal_mode == 'buy' ):
				if ( ma_daily_affinity == 'bear' and ma_intraday_affinity == 'bear' ):
					if ( cur_rsi_k > cur_rsi_d and cur_rsi_k - cur_rsi_d < 8 ):
						with_mfi = True

			elif ( signal_mode == 'short' ):
				if ( ma_daily_affinity == 'bull' and ma_intraday_affinity == 'bull' ):
					if ( cur_rsi_k < cur_rsi_d and cur_rsi_d - cur_rsi_k < 8 ):
						with_mfi = True

		# Check the moving average of the main ETF tickers
		if ( check_etf_indicators == True ):
			etf_affinity = None

			# floor the current datetime to the lower 5-min
			cur_dt = date - timedelta(minutes=date.minute % 5, seconds=date.second, microseconds=date.microsecond)
			cur_dt = int( cur_dt.timestamp() * 1000 )

			cur_etf_sma = etf_indicators['sma_avg'][cur_dt]
			cur_etf_ema = etf_indicators['ema_avg'][cur_dt]

			if ( cur_etf_ema > cur_etf_sma ):
				etf_affinity = 'bull'
			elif ( cur_etf_ema < cur_etf_sma ):
				etf_affinity = 'bear'


		# Check the daily and intraday NATR values
		# Tune the algorithms based on the daily volatility of the stock
		if ( check_daily_natr == True ):
			with_mfi	 	= params['with_mfi']
			with_rsi	 	= params['with_rsi']
			stochrsi_offset	 	= params['stochrsi_offset']

			if ( cur_natr_daily > 3 ):
				stochrsi_offset		+= 1

			if ( cur_natr_daily > 5 ):
				with_mfi		= True
				with_rsi		= True

			if ( cur_natr_daily > 6 ):
				stochrsi_offset		+= 1


		# BUY mode
		if ( signal_mode == 'buy' ):
			short = False

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(75, date) ):
				reset_signals()
				continue

			# Jump to short mode if StochRSI K and D are already above rsi_high_limit
			# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
			#  does a full loop again before acting on it.
			if ( cur_rsi_k >= stochrsi_default_high_limit and cur_rsi_d >= stochrsi_default_high_limit and noshort == False ):
				reset_signals()
				signal_mode = 'short'
				continue

			# Check StochRSI
			stochrsi_signal, stochrsi_crossover_signal, stochrsi_threshold_signal, buy_signal = \
					get_stoch_signal_long(	cur_rsi_k, cur_rsi_d, prev_rsi_k, prev_rsi_d,
								stochrsi_signal, stochrsi_crossover_signal, stochrsi_threshold_signal, buy_signal )

			if ( cur_rsi_k > stochrsi_signal_cancel_high_limit ):
				# Reset all signals if the primary stochastic
				#  indicator wanders into higher territory
				reset_signals()


			# StochRSI with 5-minute candles
			if ( with_stochrsi_5m == True ):
				stochrsi_5m_signal, stochrsi_5m_crossover_signal, stochrsi_5m_threshold_signal, stochrsi_5m_final_signal = \
						get_stoch_signal_long(	cur_rsi_k_5m, cur_rsi_d_5m, prev_rsi_k_5m, prev_rsi_d_5m,
									stochrsi_5m_signal, stochrsi_5m_crossover_signal, stochrsi_5m_threshold_signal, stochrsi_5m_final_signal )

				if ( cur_rsi_k_5m > stochrsi_signal_cancel_high_limit ):
					stochrsi_5m_signal		= False
					stochrsi_5m_crossover_signal	= False
					stochrsi_5m_threshold_signal	= False
					stochrsi_5m_final_signal	= False

			# StochMFI
			if ( with_stochmfi == True ):
				stochmfi_signal, stochmfi_crossover_signal, stochmfi_threshold_signal, stochmfi_final_signal = \
						get_stoch_signal_long(	cur_mfi_k, cur_mfi_d, prev_mfi_k, prev_mfi_d,
									stochmfi_signal, stochmfi_crossover_signal, stochmfi_threshold_signal, stochmfi_final_signal )

				if ( cur_mfi_k > stochrsi_signal_cancel_high_limit ):
					stochmfi_signal			= False
					stochmfi_crossover_signal	= False
					stochmfi_threshold_signal	= False
					stochmfi_final_signal		= False

			# StochMFI with 5-minute candles
			if ( with_stochmfi_5m == True ):
				stochmfi_5m_signal, stochmfi_5m_crossover_signal, stochmfi_5m_threshold_signal, stochmfi_5m_final_signal = \
						get_stoch_signal_long(	cur_mfi_k_5m, cur_mfi_d_5m, prev_mfi_k_5m, prev_mfi_d_5m,
									stochmfi_5m_signal, stochmfi_5m_crossover_signal, stochmfi_5m_threshold_signal, stochmfi_5m_final_signal )

				if ( cur_mfi_k_5m > stochrsi_signal_cancel_high_limit ):
					stochmfi_5m_signal		= False
					stochmfi_5m_crossover_signal	= False
					stochmfi_5m_threshold_signal	= False
					stochmfi_5m_final_signal	= False


			# Secondary Indicators
			# RSI signal
			if ( with_rsi == True ):
				if ( cur_rsi >= rsi_signal_cancel_high_limit ):
					rsi_signal = False
				elif ( prev_rsi > 25 and cur_rsi < 25 ):
					rsi_signal = False
				elif ( prev_rsi < 25 and cur_rsi >= 25 ):
					rsi_signal = True

			elif ( with_rsi_simple == True ):
				rsi_signal = False
				if ( cur_rsi < 25 ):
					rsi_signal = True

			# ADX signal
			adx_signal = False
			if ( cur_adx >= adx_threshold ):
				adx_signal = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
				plus_di_crossover = True
				minus_di_crossover = False
			elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
				plus_di_crossover = False
				minus_di_crossover = True

			dmi_signal = False
			if ( cur_plus_di > cur_minus_di ):
				if ( with_dmi_simple == True ):
					dmi_signal = True
				elif ( plus_di_crossover == True ):
					dmi_signal = True

			# Aroon oscillator signals
			# Values closer to 100 indicate an uptrend
			#
			# SAZ - 2021-08-29: Higher volatility stocks seem to work better with a longer
			# Aroon Oscillator period value.
			if ( cur_natr > aroonosc_alt_threshold and with_aroonosc_simple == True ):
				cur_aroonosc = cur_aroonosc_alt
				prev_aroonosc = prev_aroonosc_alt

			if ( cur_aroonosc < 60 ):
				aroonosc_signal = False

			if ( cur_aroonosc > 60 ):
				if ( with_aroonosc_simple == True ):
					aroonosc_signal = True

				else:
					if ( prev_aroonosc < 0 ):
						# Crossover has occurred
						aroonosc_signal = True

				if ( aroonosc_with_vpt == True ):
					if ( cur_aroonosc <= aroonosc_secondary_threshold ):
						with_vpt = True
					else:
						with_vpt = False

				# Enable macd_simple if the aroon oscillator is less than aroonosc_secondary_threshold
				if ( aroonosc_with_macd_simple == True ):
					with_macd_simple = False
					if ( cur_aroonosc <= aroonosc_secondary_threshold ):
						with_macd_simple = True

			# MFI signal
			if ( cur_mfi >= mfi_signal_cancel_high_limit ):
				mfi_signal = False
			elif ( prev_mfi > mfi_low_limit and cur_mfi < mfi_low_limit ):
				mfi_signal = False
			elif ( prev_mfi < mfi_low_limit and cur_mfi >= mfi_low_limit ):
				mfi_signal = True

			# MACD crossover signals
			if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
				macd_crossover = True
				macd_avg_crossover = False
			elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
				macd_crossover = False
				macd_avg_crossover = True

			macd_signal = False
			if ( cur_macd > cur_macd_avg and cur_macd - cur_macd_avg > macd_offset ):
				if ( with_macd_simple == True ):
					macd_signal = True
				elif ( macd_crossover == True ):
					macd_signal = True

			# VWAP
			# This is the most simple/pessimistic approach right now
			if ( with_vwap == True ):
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_price = float(pricehistory['candles'][idx]['close'])

				vwap_signal = False
				if ( cur_price < cur_vwap ):
					vwap_signal = True

			# VPT
			# Buy signal - VPT crosses above vpt_sma
			if ( prev_vpt < prev_vpt_sma and cur_vpt > cur_vpt_sma ):
				vpt_signal = True

			# Cancel signal if VPT crosses back over
			elif ( cur_vpt < cur_vpt_sma ):
				vpt_signal = False

			# Choppiness Index
			chop_init_signal, chop_signal = get_chop_signal( simple=with_chop_simple,
									 prev_chop=prev_chop, cur_chop=cur_chop,
									 chop_init_signal=chop_init_signal, chop_signal=chop_signal )

			# Resistance
			if ( no_use_resistance == False and buy_signal == True ):

				today			= datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
				cur_price		= float( pricehistory['candles'][idx]['close'] )
				resistance_signal	= True

				# PDC
				prev_day_close = 0
				if ( today in pdc ):
					prev_day_close = pdc[today]['pdc']

				if ( prev_day_close != 0 ):

					if ( abs((prev_day_close / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to PDC
						# Next check average of last 15 (minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was below PDC then PDC is resistance
						# If average was above PDC then PDC is support
						if ( avg < prev_day_close ):
							resistance_signal = False

				# NATR resistance
				if ( use_natr_resistance == True ):
					if ( cur_price > prev_day_close ):
						natr_mod = 1
						if ( cur_natr_daily >= 8 ):
							natr_mod = 2

						natr_resistance = ((cur_natr_daily / natr_mod) / 100 + 1) * prev_day_close
						if ( cur_price > natr_resistance and buy_signal == True ):
							if ( cur_rsi_k > cur_rsi_d and cur_rsi_k - cur_rsi_d < 12 ):
								resistance_signal = False

						if ( abs((cur_price / natr_resistance - 1) * 100) <= price_resistance_pct and buy_signal == True ):
							if ( cur_rsi_k > cur_rsi_d and cur_rsi_k - cur_rsi_d < 10 ):
								resistance_signal = False


				# VWAP
				if ( resistance_signal == True ):
					cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
					if ( abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to VWAP
						# Next check average of last 15 (1-minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was below VWAP then VWAP is resistance
						# If average was above VWAP then VWAP is support
						if ( avg < cur_vwap ):
							resistance_signal = False

				# High of the day (HOD)
				# Skip this check for the first 1.5 hours of the day. The reason for this is
				#  the first 2 hours or so of trading can create small hod/lods, but they
				#  often won't persist. Also, we are more concerned about the slow, low volume
				#  creeps toward HOD/LOD that are often permanent for the day.
				cur_time = datetime.fromtimestamp( float(key['datetime'])/1000, tz=mytimezone )
				cur_hour = int( cur_time.strftime('%-H') )
				if ( resistance_signal == True and lod_hod_check == True and cur_hour >= 13 ):
					cur_day_start	= datetime.strptime(today + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start	= mytimezone.localize(cur_day_start)

					delta = cur_time - cur_day_start
					delta = int( delta.total_seconds() / 60 )

					# Find HOD
					hod = 0
					for i in range (delta, 0, -1):
						if ( float(pricehistory['candles'][idx-i]['close']) > hod ):
							hod = float( pricehistory['candles'][idx-i]['close'] )

					# If the stock has already hit a high of the day, the next rise will likely be
					#  below HOD. If we are below HOD and less than price_resistance_pct from it
					#  then we should not enter the trade.
					if ( cur_price < hod ):
						if ( abs((cur_price / hod - 1) * 100) <= price_resistance_pct ):
							resistance_signal = False

					# END HOD Check

				# Key Levels
				# Check if price is near historic key level
				if ( resistance_signal == True ):
					near_keylevel = False
					for lvl in long_support + long_resistance:
						if ( abs((lvl / cur_price - 1) * 100) <= price_support_pct ):
							near_keylevel = True

							# Current price is very close to a key level
							# Next check average of last 15 (1-minute) candles
							#
							# If last 15 candles average above key level, then key level is support
							# otherwise it is resistance
							avg = 0
							for i in range(15, 0, -1):
								avg += float( pricehistory['candles'][idx-i]['close'] )
							avg = avg / 15

							# If average was below key level then key level is resistance
							# Therefore this is not a great buy
							if ( avg < lvl ):
								resistance_signal = False
								break

					# If keylevel_strict is True then only buy the stock if price is near a key level
					# Otherwise reject this buy to avoid getting chopped around between levels
					if ( keylevel_strict == True and near_keylevel == False ):
						resistance_signal = False

					# End Key Levels


				# 20-week high
#				purchase_price = float(pricehistory['candles'][idx]['close'])
#				if ( purchase_price >= twenty_week_high ):
#					# This is not a good bet
#					twenty_week_high = float(purchase_price)
#					resistance_signal = False
#
#				elif ( ( abs(float(purchase_price) / float(twenty_week_high) - 1) * 100 ) < price_resistance_pct ):
#					# Current high is within price_resistance_pct of 20-week high, not a good bet
#					resistance_signal = False

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( buy_signal == True ):
				final_buy_signal = True

				if ( with_stochrsi_5m == True and stochrsi_5m_final_signal != True ):
					final_buy_signal = False

				if ( with_stochmfi == True and stochmfi_final_signal != True ):
					final_buy_signal = False

				if ( with_stochmfi_5m == True and stochmfi_5m_final_signal != True ):
					final_buy_signal = False

				if ( with_rsi == True and rsi_signal != True ):
					final_buy_signal = False

				if ( with_mfi == True and mfi_signal != True ):
					final_buy_signal = False

				if ( with_adx == True and adx_signal != True ):
					final_buy_signal = False

				if ( (with_dmi == True or with_dmi_simple == True) and dmi_signal != True ):
					final_buy_signal = False

				if ( with_aroonosc == True and aroonosc_signal != True ):
					final_buy_signal = False

				if ( (with_macd == True or with_macd_simple == True) and macd_signal != True ):
					final_buy_signal = False

				if ( with_vwap == True and vwap_signal != True ):
					final_buy_signal = False

				if ( with_vpt == True and vpt_signal != True ):
					final_buy_signal = False

				if ( with_chop_index == True and chop_signal != True ):
					final_buy_signal = False

				if ( no_use_resistance == False and resistance_signal != True ):
					final_buy_signal = False

				if ( check_ma_strict == True and ma_intraday_affinity != 'bull' ):
					final_buy_signal = False

				if ( min_intra_natr != None and cur_natr < min_intra_natr ):
					final_buy_signal = False
				if ( max_intra_natr != None and cur_natr > max_intra_natr ):
					final_buy_signal = False

				if ( check_etf_indicators == True and etf_affinity == 'bear' ):
					final_buy_signal = False

			# DEBUG
			if ( debug_all == True ):
				time_t = datetime.fromtimestamp(int(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S')
				print(	'(' + str(time_t) + ') '	+
					'buy_signal:'			+ str(buy_signal) +
					', final_buy_signal: '		+ str(final_buy_signal) +
					', rsi_signal: '		+ str(rsi_signal) +
					', mfi_signal: '		+ str(mfi_signal) +
					', adx_signal: '		+ str(adx_signal) +
					', dmi_signal: '		+ str(dmi_signal) +
					', aroonosc_signal: '		+ str(aroonosc_signal) +
					', macd_signal: '		+ str(macd_signal) +
					', vwap_signal: '		+ str(vwap_signal) +
					', vpt_signal: '		+ str(vpt_signal) +
					', resistance_signal: '		+ str(resistance_signal) )

				print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(time_t) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
				print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
				print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
				print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) + ' signal: ' + str(dmi_signal))
				print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
				print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
				print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))
				print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
				print('(' + str(ticker) + '): BUY signal: ' + str(buy_signal) + ', Final BUY signal: ' + str(final_buy_signal))
				print()
			# DEBUG


			# BUY SIGNAL
			if ( buy_signal == True and final_buy_signal == True ):
				purchase_price = float(pricehistory['candles'][idx]['close'])
				base_price = purchase_price
				purchase_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(purchase_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily,2)) + ',' +
						str(round(cur_adx,2)) + ',' + str(purchase_time) )

				reset_signals()
				signal_mode = 'sell'

				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( variable_exit == True ):
					if ( cur_natr < incr_threshold ):

						# The normalized ATR is below incr_threshold. This means the stock is less
						#  likely to get to incr_threshold from our purchase price, and is probably
						#  even farther away from exit_percent (if it is set). So we adjust these parameters
						#  to increase the likelihood of a successful trade.
						#
						# This typically means the price action is not very good, but setting
						#  incr_threshold too low risks losing the ability to handle even slight
						#  variations in price. So we try to tailor incr_threshold to make the best
						#  of this entry.
						#
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( incr_threshold > cur_natr * 3 ):
							incr_threshold = cur_natr * 2

						elif ( incr_threshold > cur_natr * 2 ):
							incr_threshold = cur_natr + (cur_natr / 2)

						else:
							incr_threshold = cur_natr

						if ( decr_threshold > cur_natr * 2 ):
							decr_threshold = cur_natr * 2

						if ( exit_percent != None ):
							if ( exit_percent > cur_natr * 4 ):
								exit_percent = cur_natr * 2

						# We may adjust incr/decr_threshold later as well, so store the original version
						#   for comparison if needed.
						orig_incr_threshold = incr_threshold
						orig_decr_threshold = decr_threshold

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG


		# SELL mode
		if ( signal_mode == 'sell' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(5, date) ):
				sell_signal = True

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60, date) == True and hold_overnight == False ):
				last_price = float( pricehistory['candles'][idx]['close'] )
				if ( last_price > purchase_price ):
					percent_change = abs( purchase_price / last_price - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						sell_signal = True

			# Monitor cost basis
			last_price = float(pricehistory['candles'][idx]['close'])
			percent_change = 0
			if ( float(last_price) < float(base_price) ):
				percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100

				# SELL the security if we are using a trailing stoploss
				if ( percent_change >= decr_threshold and stoploss == True ):

					# Sell
					sell_price = float(pricehistory['candles'][idx]['close'])
					sell_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

					# sell_price,bool(short),rsi,stochrsi,sell_time
					results.append( str(sell_price) + ',' + str(short) + ',' +
							str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
							str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily,2)) + ',' +
							str(round(cur_adx,2)) + ',' + str(sell_time) )

					# DEBUG
					if ( debug_all == True ):
						print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(sell_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
						print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
						print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
						print('------------------------------------------------------')
					# DEBUG

					reset_signals()

					purchase_price	= 0
					base_price	= 0
					incr_threshold	= orig_incr_threshold = default_incr_threshold
					decr_threshold	= orig_decr_threshold = default_decr_threshold
					exit_percent	= orig_exit_percent

					signal_mode = 'short'
					continue

			elif ( float(last_price) > float(base_price) ):
				percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100
				if ( percent_change >= incr_threshold ):
					base_price = last_price

					# Adapt decr_threshold based on changes made by --variable_exit
					if ( incr_threshold < default_incr_threshold ):

						# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
						#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
						if ( incr_threshold == orig_incr_threshold ):
							decr_threshold = incr_threshold
							incr_threshold = incr_threshold / 2

					else:
						decr_threshold = incr_threshold / 2

			# End cost basis / stoploss monitor

			# Additional exit strategies
			# Sell if exit_percent is specified
			if ( exit_percent != None and float(last_price) > float(purchase_price) ):
				total_percent_change = abs( float(purchase_price) / float(last_price) - 1 ) * 100

				# If exit_percent has been hit, we will sell at the first RED candle
				#  unless --quick_exit was set.
				if ( exit_percent_signal == True ):
					if ( float(pricehistory['candles'][idx]['close']) < float(pricehistory['candles'][idx]['open']) ):
						sell_signal = True

				elif ( total_percent_change >= exit_percent ):
					exit_percent_signal = True
					if ( quick_exit == True ):
						sell_signal = True

			# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
			if ( vwap_exit == True ):
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_vwap_up = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap_up']
				if ( cur_vwap > purchase_price ):
					if ( last_price >= ((cur_vwap - purchase_price) / 2) + purchase_price ):
						sell_signal = True

				elif ( cur_vwap < purchase_price ):
					if ( last_price >= ((cur_vwap_up - cur_vwap) / 2) + cur_vwap ):
						sell_signal = True


			# Monitor RSI for SELL signal
			#  Note that this RSI implementation is more conservative than the one for buy/sell to ensure we don't
			#  miss a valid sell signal.
			#
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( strict_exit_percent == False and exit_percent_signal == False ):
				if ( cur_rsi_k > stochrsi_default_high_limit and cur_rsi_d > stochrsi_default_high_limit ):
					stochrsi_signal = True

					# Monitor if K and D intersect
					# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region
					if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
						sell_signal = True

				if ( stochrsi_signal == True ):
					if ( prev_rsi_k > stochrsi_default_high_limit and cur_rsi_k <= stochrsi_default_high_limit ):
						sell_signal = True


			if ( sell_signal == True ):

				# Sell
				sell_price = float(pricehistory['candles'][idx]['close'])
				sell_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				# sell_price,bool(short),rsi,stochrsi,sell_time
				results.append( str(sell_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily,2)) + ',' +
						str(round(cur_adx,2)) + ',' + str(sell_time) )

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(sell_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG

				reset_signals()

				purchase_price	= 0
				base_price	= 0
				incr_threshold	= orig_incr_threshold = default_incr_threshold
				decr_threshold	= orig_decr_threshold = default_decr_threshold
				exit_percent	= orig_exit_percent

				if ( noshort == False ):
					short_signal = True
					signal_mode = 'short'
					continue
				else:
					signal_mode = 'buy'


		# SELL SHORT mode
		if ( signal_mode == 'short' ):
			short = True

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(75, date) ):
				reset_signals()
				continue

			# Jump to buy mode if StochRSI K and D are already below rsi_low_limit
			if ( cur_rsi_k <= stochrsi_default_low_limit and cur_rsi_d <= stochrsi_default_low_limit ):
				reset_signals()
				signal_mode = 'buy'
				continue

			# Monitor StochRSI
			stochrsi_signal, stochrsi_crossover_signal, stochrsi_threshold_signal, short_signal = \
					get_stoch_signal_short(	cur_rsi_k, cur_rsi_d, prev_rsi_k, prev_rsi_d,
								stochrsi_signal, stochrsi_crossover_signal, stochrsi_threshold_signal, short_signal )

			if ( cur_rsi_k < stochrsi_signal_cancel_low_limit ):
				# Reset all signals if the primary stochastic
				#  indicator wanders into low territory
				reset_signals()

			# StochRSI with 5-minute candles
			if ( with_stochrsi_5m == True ):
				stochrsi_5m_signal, stochrsi_5m_crossover_signal, stochrsi_5m_threshold_signal, stochrsi_5m_final_signal = \
						get_stoch_signal_short(	cur_rsi_k_5m, cur_rsi_d_5m, prev_rsi_k_5m, prev_rsi_d_5m,
									stochrsi_5m_signal, stochrsi_5m_crossover_signal, stochrsi_5m_threshold_signal, stochrsi_5m_final_signal )

				if ( cur_rsi_k_5m < stochrsi_signal_cancel_low_limit ):
					stochrsi_5m_signal		= False
					stochrsi_5m_crossover_signal	= False
					stochrsi_5m_threshold_signal	= False
					stochrsi_5m_final_signal	= False

			# StochMFI
			if ( with_stochmfi == True ):
				stochmfi_signal, stochmfi_crossover_signal, stochmfi_threshold_signal, stochmfi_final_signal = \
						get_stoch_signal_short(	cur_mfi_k, cur_mfi_d, prev_mfi_k, prev_mfi_d,
									stochmfi_signal, stochmfi_crossover_signal, stochmfi_threshold_signal, stochmfi_final_signal )

				if ( cur_mfi_k < stochrsi_signal_cancel_low_limit ):
					stochmfi_signal			= False
					stochmfi_crossover_signal	= False
					stochmfi_threshold_signal	= False
					stochmfi_final_signal		= False

			# StochMFI with 5-minute candles
			if ( with_stochmfi_5m == True ):
				stochmfi_5m_signal, stochmfi_5m_crossover_signal, stochmfi_5m_threshold_signal, stochmfi_5m_final_signal = \
						get_stoch_signal_short(	cur_mfi_k_5m, cur_mfi_d_5m, prev_mfi_k_5m, prev_mfi_d_5m,
									stochmfi_5m_signal, stochmfi_5m_crossover_signal, stochmfi_5m_threshold_signal, stochmfi_5m_final_signal )

				if ( cur_mfi_k_5m < stochrsi_signal_cancel_low_limit ):
					stochmfi_5m_signal		= False
					stochmfi_5m_crossover_signal	= False
					stochmfi_5m_threshold_signal	= False
					stochmfi_5m_final_signal	= False


			# Secondary Indicators
			# RSI signal
			if ( with_rsi == True ):
				if ( cur_rsi <= rsi_signal_cancel_low_limit ):
					rsi_signal = False
				elif ( prev_rsi < 75 and cur_rsi > 75 ):
					rsi_signal = False
				elif ( prev_rsi > 75 and cur_rsi <= 75 ):
					rsi_signal = True

			elif ( with_rsi_simple == True ):
				rsi_signal = False
				if ( cur_rsi >= 80 ):
					rsi_signal = True

			# ADX signal
			adx_signal = False
			if ( cur_adx > adx_threshold ):
				adx_signal = True

			# DMI signals
			# DI+ cross above DI- indicates uptrend
			if ( prev_plus_di < prev_minus_di and cur_plus_di > cur_minus_di ):
				plus_di_crossover = True
				minus_di_crossover = False
			elif ( prev_plus_di > prev_minus_di and cur_plus_di < cur_minus_di ):
				plus_di_crossover = False
				minus_di_crossover = True

			dmi_signal = False
			if ( cur_plus_di < cur_minus_di ):
				if ( with_dmi_simple == True ):
					dmi_signal = True
				elif ( minus_di_crossover == True ):
					dmi_signal = True

			# Aroon oscillator signals
			# Values closer to -100 indicate a downtrend
			if ( cur_natr > aroonosc_alt_threshold and with_aroonosc_simple == True ):
				cur_aroonosc = cur_aroonosc_alt
				prev_aroonosc = prev_aroonosc_alt

			if ( cur_aroonosc > -60 ):
				aroonosc_signal = False

			elif ( cur_aroonosc < -60 ):
				if ( with_aroonosc_simple == True ):
					aroonosc_signal = True

				else:
					if ( prev_aroonosc > 0 ):
						# Crossover has occurred
						aroonosc_signal = True

				# Enable macd_simple if the aroon oscillitor is greater than -aroonosc_secondary_threshold
				if ( aroonosc_with_macd_simple == True ):
					with_macd_simple = False
					if ( cur_aroonosc >= -aroonosc_secondary_threshold ):
						with_macd_simple = True

			# MFI signal
			if ( cur_mfi <= mfi_signal_cancel_low_limit ):
				mfi_signal = False
			elif ( prev_mfi < mfi_high_limit and cur_mfi > mfi_high_limit ):
				mfi_signal = False
			elif ( prev_mfi > mfi_high_limit and cur_mfi <= mfi_high_limit ):
				mfi_signal = True

			# MACD crossover signals
			if ( prev_macd < prev_macd_avg and cur_macd > cur_macd_avg ):
				macd_crossover = True
				macd_avg_crossover = False
			elif ( prev_macd > prev_macd_avg and cur_macd < cur_macd_avg ):
				macd_crossover = False
				macd_avg_crossover = True

			macd_signal = False
			if ( cur_macd < cur_macd_avg and cur_macd_avg - cur_macd > macd_offset ):
				if ( with_macd_simple == True ):
					macd_signal = True
				elif ( macd_avg_crossover == True ):
					macd_signal = True

			# VWAP
			# This is the most simple/pessimistic approach right now
			if ( with_vwap == True ):
				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_price = float(pricehistory['candles'][idx]['close'])
				if ( cur_price > cur_vwap ):
					vwap_signal = True

			# VPT
			# Short signal - VPT crosses below vpt_sma
			if ( prev_vpt > prev_vpt_sma and cur_vpt < cur_vpt_sma ):
				vpt_signal = True

			# Cancel signal if VPT cross back over
			elif ( cur_vpt > cur_vpt_sma ):
				vpt_signal = False

			# Choppiness Index
			chop_init_signal, chop_signal = get_chop_signal( simple=with_chop_simple,
									 prev_chop=prev_chop, cur_chop=cur_chop,
									 chop_init_signal=chop_init_signal, chop_signal=chop_signal )

			# Resistance
			if ( no_use_resistance == False and short_signal == True ):

				today			= datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
				cur_price		= float( pricehistory['candles'][idx]['close'] )
				resistance_signal	= True

				# PDC
				prev_day_close = 0
				if ( today in pdc ):
					prev_day_close = pdc[today]['pdc']

				if ( prev_day_close != 0 ):

					if ( abs((prev_day_close / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to PDC
						# Next check average of last 15 (minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was below PDC then PDC is resistance (good for short)
						# If average was above PDC then PDC is support (bad for short)
						if ( avg > prev_day_close ):
							resistance_signal = False

				# NATR resistance
				if ( use_natr_resistance == True ):
					if ( cur_price < prev_day_close ):
						natr_mod = 1
						if ( cur_natr_daily > 8 ):
							natr_mod = 2

						natr_resistance = ((cur_natr_daily / natr_mod) / 100 + 1) * prev_day_close - prev_day_close
						natr_resistance = prev_day_close - natr_resistance
						if ( cur_price < natr_resistance and short_signal == True ):
							if ( cur_rsi_k < cur_rsi_d and cur_rsi_d - cur_rsi_k < 12 ):
								resistance_signal = False

						if ( abs((cur_price / natr_resistance - 1) * 100) <= price_resistance_pct and short_signal == True ):
							if ( cur_rsi_k < cur_rsi_d and cur_rsi_d - cur_rsi_k < 10 ):
								resistance_signal = False


				# VWAP
				if ( resistance_signal == True ):
					cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
					if ( abs((cur_vwap / cur_price - 1) * 100) <= price_resistance_pct ):

						# Current price is very close to VWAP
						# Next check average of last 15 (1-minute) candles
						avg = 0
						for i in range(15, 0, -1):
							avg += float( pricehistory['candles'][idx-i]['close'] )
						avg = avg / 15

						# If average was below VWAP then VWAP is resistance (good for short)
						# If average was above VWAP then VWAP is support (bad for short)
						if ( avg > cur_vwap ):
							resistance_signal = False

				# Low of the day (LOD)
				# Skip this check for the first 1.5 hours of the day. The reason for this is
				#  the first 1-1.5 hours or so of trading can create small hod/lods, but they
				#  often won't persist. Also, we are more concerned about the slow, low volume
				#  creeps toward HOD/LOD that are often permanent for the day.
				cur_time = datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone)
				cur_hour = int( cur_time.strftime('%-H') )
				if ( resistance_signal == True and lod_hod_check == True and cur_hour >= 13 ):
					cur_day_start	= datetime.strptime(today + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start	= mytimezone.localize(cur_day_start)

					delta = cur_time - cur_day_start
					delta = int( delta.total_seconds() / 60 )

					# Find LOD
					lod = 9999
					for i in range (delta, 0, -1):
						if ( float(pricehistory['candles'][idx-i]['close']) < lod ):
							lod = float( pricehistory['candles'][idx-i]['close'] )

					# If the stock has already hit a low of the day, the next decrease will likely be
					#  above LOD. If we are above LOD and less than price_resistance_pct from it
					#  then we should not enter the trade.
					if ( cur_price > lod ):
						if ( abs((lod / cur_price - 1) * 100) <= price_resistance_pct ):
							resistance_signal = False

					# END LOD Check

				# Key Levels
				# Check if price is near historic key level
				if ( resistance_signal == True ):
					near_keylevel = False
					for lvl in long_support + long_resistance:
						if ( abs((lvl / cur_price - 1) * 100) <= price_resistance_pct ):
							near_keylevel = True

							# Current price is very close to a key level
							# Next check average of last 15 (1-minute) candles
							#
							# If last 15 candles average below key level, then key level is resistance
							# otherwise it is support
							avg = 0
							for i in range(15, 0, -1):
								avg += float( pricehistory['candles'][idx-i]['close'] )
							avg = avg / 15

							# If average was above key level then key level is support
							# Therefore this is not a good short
							if ( avg > lvl ):
								resistance_signal = False
								break

					# If keylevel_strict is True then only short the stock if price is near a key level
					# Otherwise reject this short altogether to avoid getting chopped around between levels
					if ( keylevel_strict == True and near_keylevel == False ):
						resistance_signal = False

					# End Key Levels

				# High / low resistance
#				short_price = float(pricehistory['candles'][idx]['close'])
#				if ( float(short_price) <= float(twenty_week_low) ):
#					# This is not a good bet
#					twenty_week_low = float(short_price)
#					resistance_signal = False
#
#				elif ( ( abs(float(twenty_week_low) / float(short_price) - 1) * 100 ) < price_support_pct ):
#					# Current low is within price_support_pct of 20-week low, not a good bet
#					resistance_signal = False

			# Resolve the primary stochrsi buy_signal with the secondary indicators
			if ( short_signal == True ):
				final_short_signal = True

				if ( with_stochrsi_5m == True and stochrsi_5m_final_signal != True ):
					final_short_signal = False

				if ( with_stochmfi == True and stochmfi_final_signal != True ):
					final_short_signal = False

				if ( with_stochmfi_5m == True and stochmfi_5m_final_signal != True ):
					final_short_signal = False

				if ( with_rsi == True and rsi_signal != True ):
					final_short_signal = False

				if ( with_mfi == True and mfi_signal != True ):
					final_short_signal = False

				if ( with_adx == True and adx_signal != True ):
					final_short_signal = False

				if ( (with_dmi == True or with_dmi_simple == True) and dmi_signal != True ):
					final_short_signal = False

				if ( with_aroonosc == True and aroonosc_signal != True ):
					final_short_signal = False

				if ( (with_macd == True or with_macd_simple == True) and macd_signal != True ):
					final_short_signal = False

				if ( with_vwap == True and vwap_signal != True ):
					final_short_signal = False

				if ( with_vpt == True and vpt_signal != True ):
					final_short_signal = False

				if ( with_chop_index == True and chop_signal != True ):
					final_short_signal = False

				if ( no_use_resistance == False and resistance_signal != True ):
					final_short_signal = False

				if ( check_ma_strict == True and ma_intraday_affinity != 'bear' ):
					final_short_signal = False

				if ( min_intra_natr != None and cur_natr < min_intra_natr ):
					final_short_signal = False
				if ( max_intra_natr != None and cur_natr > max_intra_natr ):
					final_short_signal = False

				if ( check_etf_indicators == True and etf_affinity == 'bull' ):
					final_short_signal = False

			# DEBUG
			if ( debug_all == True ):
				time_t = datetime.fromtimestamp(int(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S')
				print(	'(' + str(time_t) + ') '	+
					'short_signal:'			+ str(short_signal) +
					', final_short_signal: '	+ str(final_short_signal) +
					', rsi_signal: '		+ str(rsi_signal) +
					', mfi_signal: '		+ str(mfi_signal) +
					', adx_signal: '		+ str(adx_signal) +
					', dmi_signal: '		+ str(dmi_signal) +
					', aroonosc_signal: '		+ str(aroonosc_signal) +
					', macd_signal: '		+ str(macd_signal) +
					', vwap_signal: '		+ str(vwap_signal) +
					', vpt_signal: '		+ str(vpt_signal) +
					', resistance_signal: '		+ str(resistance_signal) )

				print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(time_t) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
				print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
				print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
				print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) + ' signal: ' + str(dmi_signal))
				print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
				print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
				print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))
				print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
				print('(' + str(ticker) + '): SHORT signal: ' + str(short_signal) + ', Final SHORT signal: ' + str(final_short_signal))
				print()
			# DEBUG


			# SHORT SIGNAL
			if ( short_signal == True and final_short_signal == True ):

				cur_natr_daily = 0
				try:
					cur_natr_daily = daily_natr[date.strftime('%Y-%m-%d')]['natr']
				except:
					pass

				short_price = float(pricehistory['candles'][idx]['close'])
				base_price = short_price
				short_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(short_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr, 3)) + ',' + str(round(cur_natr_daily, 3)) + ',' +
						str(round(cur_adx, 2)) + ',' + str(short_time) )

				reset_signals()

				signal_mode = 'buy_to_cover'

				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( variable_exit == True ):
					if ( cur_natr < incr_threshold ):

						# The normalized ATR is below incr_threshold. This means the stock is less
						#  likely to get to incr_threshold from our purchase price, and is probably
						#  even farther away from exit_percent (if it is set). So we adjust these parameters
						#  to increase the likelihood of a successful trade.
						#
						# This typically means the price action is not very good, but setting
						#  incr_threshold too low risks losing the ability to handle even slight
						#  variations in price. So we try to tailor incr_threshold to make the best
						#  of this entry.
						#
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( incr_threshold > cur_natr * 3 ):
							incr_threshold = cur_natr * 2

						elif ( incr_threshold > cur_natr * 2 ):
							incr_threshold = cur_natr + (cur_natr / 2)

						else:
							incr_threshold = cur_natr

						if ( decr_threshold > cur_natr * 2 ):
							decr_threshold = cur_natr * 2

						if ( exit_percent != None ):
							if ( exit_percent > cur_natr * 4 ):
								exit_percent = cur_natr * 2

						# We may adjust incr/decr_threshold later as well, so store the original version
						#   for comparison if needed.
						orig_incr_threshold = incr_threshold
						orig_decr_threshold = decr_threshold

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG


		# BUY-TO-COVER mode
		if ( signal_mode == 'buy_to_cover' ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(5, date) ):
				buy_to_cover_signal = True

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60, date) == True and hold_overnight == False ):
				last_price = float( pricehistory['candles'][idx]['close'] )
				if ( last_price < short_price ):
					percent_change = abs( short_price / last_price - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						sell_signal = True

			# Monitor cost basis
			last_price = float(pricehistory['candles'][idx]['close'])
			percent_change = 0
			if ( float(last_price) > float(base_price) ):
				percent_change = abs( float(base_price) / float(last_price) - 1 ) * 100

				# Buy-to-cover the security if we are using a trailing stoploss
				if ( percent_change >= decr_threshold and stoploss == True ):

					# Buy-to-cover
					buy_to_cover_price = float(pricehistory['candles'][idx]['close'])
					buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

					results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
							str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
							str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily, 3)) + ',' +
							str(round(cur_adx,2)) + ',' + str(buy_to_cover_time) )

					# DEBUG
					if ( debug_all == True ):
						print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(buy_to_cover_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
						print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
						print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
						print('------------------------------------------------------')
					# DEBUG

					reset_signals()

					short_price	= 0
					base_price	= 0
					incr_threshold	= orig_incr_threshold = default_incr_threshold
					decr_threshold	= orig_decr_threshold = default_decr_threshold
					exit_percent	= orig_exit_percent

					if ( shortonly == True ):
						signal_mode = 'short'
					else:
						signal_mode = 'buy'
						continue

			elif ( float(last_price) < float(base_price) ):
				percent_change = abs( float(last_price) / float(base_price) - 1 ) * 100
				if ( percent_change >= incr_threshold ):
					base_price = last_price

					# Adapt decr_threshold based on changes made by --variable_exit
					if ( incr_threshold < default_incr_threshold ):

						# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
						#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
						if ( incr_threshold == orig_incr_threshold ):
							decr_threshold = incr_threshold
							incr_threshold = incr_threshold / 2

					else:
						decr_threshold = incr_threshold / 2

			# End cost basis / stoploss monitor


			# Additional exit strategies
			# Sell if exit_percent is specified
			if ( exit_percent != None and float(last_price) < float(short_price) ):

				total_percent_change = abs( float(last_price) / float(short_price) - 1 ) * 100

				# If exit_percent has been hit, we will sell at the first GREEN candle
				#  unless quick_exit was set.
				if ( exit_percent_signal == True ):
					if ( float(pricehistory['candles'][idx]['close']) > float(pricehistory['candles'][idx]['open']) ):
						buy_to_cover_signal = True

				elif ( total_percent_change >= float(exit_percent) ):
					exit_percent_signal = True
					if ( quick_exit == True ):
						buy_to_cover_signal = True

			# Sell if --vwap_exit was set and last_price is half way between the orig_base_price and cur_vwap
			if ( vwap_exit == True ):

				cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
				cur_vwap_down = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap_down']
				if ( cur_vwap < short_price ):
					if ( last_price <= ((short_price - cur_vwap) / 2) + cur_vwap ):
						buy_to_cover_signal = True

				elif ( cur_vwap > short_price ):
					if ( last_price <= ((cur_vwap - cur_vwap_down) / 2) + cur_vwap_down ):
						buy_to_cover_signal = True


			# Monitor RSI for BUY_TO_COVER signal
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( strict_exit_percent == False and exit_percent_signal == False ):
				if ( cur_rsi_k < stochrsi_default_low_limit and cur_rsi_d < stochrsi_default_low_limit ):
					stochrsi_signal = True

					# Monitor if K and D intercect
					# A buy-to-cover signal occurs when an increasing %K line crosses above the %D line in the oversold region.
					if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
						buy_to_cover_signal = True

				if ( stochrsi_signal == True ):
					if ( prev_rsi_k < stochrsi_default_low_limit and cur_rsi_k >= stochrsi_default_low_limit ):
						buy_to_cover_signal = True


			# BUY-TO-COVER
			if ( buy_to_cover_signal == True ):

				buy_to_cover_price = float(pricehistory['candles'][idx]['close'])
				buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily, 3)) + ',' +
						str(round(cur_adx,2)) + ',' + str(buy_to_cover_time) )

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(buy_to_cover_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG

				reset_signals()

				short_price	= 0
				base_price	= 0
				incr_threshold	= orig_incr_threshold = default_incr_threshold
				decr_threshold	= orig_decr_threshold = default_decr_threshold
				exit_percent	= orig_exit_percent

				if ( shortonly == True ):
					signal_mode = 'short'
				else:
					buy_signal = True
					signal_mode = 'buy'
					continue

	# End main loop

	return results

