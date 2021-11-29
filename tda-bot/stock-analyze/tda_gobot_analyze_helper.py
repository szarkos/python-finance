#!/usr/bin/python3 -u

import os, sys
from collections import OrderedDict

from datetime import datetime, timedelta
from pytz import timezone

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper
import tda_algo_helper


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
	def reset_signals( exclude_bbands_kchan=False ):

		nonlocal buy_signal			; buy_signal			= False
		nonlocal sell_signal			; sell_signal			= False
		nonlocal short_signal			; short_signal			= False
		nonlocal buy_to_cover_signal		; buy_to_cover_signal		= False

		nonlocal final_buy_signal		; final_buy_signal		= False
		nonlocal final_sell_signal		; final_sell_signal		= False
		nonlocal final_short_signal		; final_short_signal		= False
		nonlocal final_buy_to_cover_signal	; final_buy_to_cover_signal	= False

		nonlocal exit_percent_signal		; exit_percent_signal		= False

		nonlocal stacked_ma_signal		; stacked_ma_signal		= False

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
		nonlocal supertrend_signal		; supertrend_signal		= False

		if ( exclude_bbands_kchan == False ):
			nonlocal bbands_kchan_signal_counter		; bbands_kchan_signal_counter		= 0
			nonlocal bbands_kchan_xover_counter		; bbands_kchan_xover_counter		= 0
			nonlocal bbands_kchan_init_signal		; bbands_kchan_init_signal		= False
			nonlocal bbands_kchan_crossover_signal		; bbands_kchan_crossover_signal		= False
			nonlocal bbands_kchan_signal			; bbands_kchan_signal			= False

		nonlocal plus_di_crossover		; plus_di_crossover		= False
		nonlocal minus_di_crossover		; minus_di_crossover		= False
		nonlocal macd_crossover			; macd_crossover		= False
		nonlocal macd_avg_crossover		; macd_avg_crossover		= False

		nonlocal experimental_signal		; experimental_signal		= False

		return True

	# END reset_signals

	# Set test parameters based on params{}
	# Syntax is as follows:
	#
	#  Parameter			Default Value	Otherwise, use what was passed in params['var']
	#
	#  var			=	default_value	if ( 'var' not in params ) else params['var']

	# Test range and input options
	start_date 			= None		if ('start_date' not in params) else params['start_date']
	stop_date			= None		if ('stop_date' not in params) else params['stop_date']
	safe_open			= True		if ('safe_open' not in params) else params['safe_open']
	weekly_ph			= None		if ('weekly_ph' not in params) else params['weekly_ph']
	daily_ph			= None		if ('daily_ph' not in params) else params['daily_ph']

	debug				= False		if ('debug' not in params) else params['debug']
	debug_all			= False		if ('debug_all' not in params) else params['debug_all']

	# Trade exit parameters
	incr_threshold			= 1		if ('incr_threshold' not in params) else params['incr_threshold']
	decr_threshold			= 1.5		if ('decr_threshold' not in params) else params['decr_threshold']
	stoploss			= False		if ('stoploss' not in params) else params['stoploss']
	exit_percent			= None		if ('exit_percent' not in params) else params['exit_percent']
	quick_exit			= False		if ('quick_exit' not in params) else params['quick_exit']
	strict_exit_percent		= False		if ('strict_exit_percent' not in params) else params['strict_exit_percent']
	variable_exit			= False		if ('variable_exit' not in params) else params['variable_exit']
	use_ha_exit			= False		if ('use_ha_exit' not in params) else params['use_ha_exit']
	use_ha_candles			= False		if ('use_ha_candles' not in params) else params['use_ha_candles']
	use_trend_exit			= False		if ('use_trend_exit' not in params) else params['use_trend_exit']
	use_trend			= False		if ('use_trend' not in params) else params['use_trend']
	trend_type			= 'hl2'		if ('trend_type' not in params) else params['trend_type']
	trend_period			= 5		if ('trend_period' not in params) else params['trend_period']
	use_combined_exit		= False		if ('use_combined_exit' not in params) else params['use_combined_exit']
	hold_overnight			= False		if ('hold_overnight' not in params) else params['hold_overnight']

	# Stock shorting options
	noshort				= False		if ('noshort' not in params) else params['noshort']
	shortonly			= False		if ('shortonly' not in params) else params['shortonly']

	# Other stock behavior options
	blacklist_earnings		= False		if ('blacklist_earnings' not in params) else params['blacklist_earnings']
	check_volume			= False		if ('check_volume' not in params) else params['check_volume']
	avg_volume			= 2000000		if ('avg_volume' not in params) else params['avg_volume']
	min_volume			= 1500000		if ('min_volume' not in params) else params['min_volume']
	min_ticker_age			= None		if ('min_ticker_age' not in params) else params['min_ticker_age']
	min_daily_natr			= None		if ('min_daily_natr' not in params) else params['min_daily_natr']
	max_daily_natr			= None		if ('max_daily_natr' not in params) else params['max_daily_natr']
	min_intra_natr			= None		if ('min_intra_natr' not in params) else params['min_intra_natr']
	max_intra_natr			= None		if ('max_intra_natr' not in params) else params['max_intra_natr']
	min_price			= None		if ('min_price' not in params) else params['min_price']
	max_price			= None		if ('max_price' not in params) else params['max_price']

	# Indicators
	primary_stoch_indicator		= 'stochrsi'	if ('primary_stoch_indicator' not in params) else params['primary_stoch_indicator']
	with_stoch_5m			= False		if ('with_stoch_5m' not in params) else params['with_stoch_5m']
	with_stochrsi_5m		= False		if ('with_stochrsi_5m' not in params) else params['with_stochrsi_5m']
	with_stochmfi			= False		if ('with_stochmfi' not in params) else params['with_stochmfi']
	with_stochmfi_5m		= False		if ('with_stochmfi_5m' not in params) else params['with_stochmfi_5m']

	with_stacked_ma			= False		if ('with_stacked_ma' not in params) else params['with_stacked_ma']
	stacked_ma_type			= 'vwma'	if ('stacked_ma_type' not in params) else params['stacked_ma_type']
	stacked_ma_periods		= '3,5,8'	if ('stacked_ma_periods' not in params) else params['stacked_ma_periods']
	stacked_ma_type_primary		= 'wma'		if ('stacked_ma_type_primary' not in params) else params['stacked_ma_type_primary']
	stacked_ma_periods_primary	= '5,8,13'	if ('stacked_ma_periods_primary' not in params) else params['stacked_ma_periods_primary']
	daily_ma_type			= 'wma'		if ('daily_ma_type' not in params) else params['daily_ma_type']
	confirm_daily_ma		= False		if ('confirm_daily_ma' not in params) else params['confirm_daily_ma']

	with_rsi			= False		if ('with_rsi' not in params) else params['with_rsi']
	with_rsi_simple			= False		if ('with_rsi_simple' not in params) else params['with_rsi_simple']

	with_dmi			= False		if ('with_dmi' not in params) else params['with_dmi']
	with_dmi_simple			= False		if ('with_dmi_simple' not in params) else params['with_dmi_simple']
	with_adx			= False		if ('with_adx' not in params) else params['with_adx']

	with_macd			= False		if ('with_macd' not in params) else params['with_macd']
	with_macd_simple		= False		if ('with_macd_simple' not in params) else params['with_macd_simple']

	with_aroonosc			= False		if ('with_aroonosc' not in params) else params['with_aroonosc']
	with_aroonosc_simple		= False		if ('with_aroonosc_simple' not in params) else params['with_aroonosc_simple']

	with_mfi			= False		if ('with_mfi' not in params) else params['with_mfi']
	with_mfi_simple			= False		if ('with_mfi_simple' not in params) else params['with_mfi_simple']

	with_vpt			= False		if ('with_vpt' not in params) else params['with_vpt']
	with_vwap			= False		if ('with_vwap' not in params) else params['with_vwap']
	with_chop_index			= False		if ('with_chop_index' not in params) else params['with_chop_index']
	with_chop_simple		= False		if ('with_chop_simple' not in params) else params['with_chop_simple']

	with_supertrend			= False		if ('with_supertrend' not in params) else params['with_supertrend']
	supertrend_min_natr		= 5		if ('supertrend_min_natr' not in params) else params['supertrend_min_natr']
	supertrend_atr_period		= 128		if ('supertrend_atr_period' not in params) else params['supertrend_atr_period']

	with_bbands_kchannel_simple	= False		if ('with_bbands_kchannel_simple' not in params) else params['with_bbands_kchannel_simple']
	with_bbands_kchannel		= False		if ('with_bbands_kchannel' not in params) else params['with_bbands_kchannel']
	use_bbands_kchannel_5m		= False		if ('use_bbands_kchannel_5m' not in params) else params['use_bbands_kchannel_5m']
	bbands_kchan_crossover_only	= False		if ('bbands_kchan_crossover_only' not in params) else params['bbands_kchan_crossover_only']
	use_bbands_kchannel_xover_exit	= False		if ('use_bbands_kchannel_xover_exit' not in params) else params['use_bbands_kchannel_xover_exit']
	bbands_kchannel_xover_exit_count= 10		if ('bbands_kchannel_xover_exit_count' not in params) else params['bbands_kchannel_xover_exit_count']
	bbands_kchannel_offset		= 0.15		if ('bbands_kchannel_offset' not in params) else params['bbands_kchannel_offset']
	bbands_kchan_squeeze_count	= 4		if ('bbands_kchan_squeeze_count' not in params) else params['bbands_kchan_squeeze_count']
	bbands_period			= 20		if ('bbands_period' not in params) else params['bbands_period']
	kchannel_period			= 20		if ('kchannel_period' not in params) else params['kchannel_period']
	kchannel_atr_period		= 20		if ('kchannel_atr_period' not in params) else params['kchannel_atr_period']

	# Indicator parameters and modifiers
	stochrsi_period			= 128		if ('stochrsi_period' not in params) else params['stochrsi_period']
	stochrsi_5m_period		= 28		if ('stochrsi_5m_period' not in params) else params['stochrsi_5m_period']
	rsi_period			= 14		if ('rsi_period' not in params) else params['rsi_period']
	rsi_type			= 'hlc3'	if ('rsi_type' not in params) else params['rsi_type']
	rsi_slow			= 3		if ('rsi_slow' not in params) else params['rsi_slow']
	rsi_k_period			= 128		if ('rsi_k_period' not in params) else params['rsi_k_period']
	rsi_d_period			= 3		if ('rsi_d_period' not in params) else params['rsi_d_period']
	rsi_low_limit			= 20		if ('rsi_low_limit' not in params) else params['rsi_low_limit']
	rsi_high_limit			= 80		if ('rsi_high_limit' not in params) else params['rsi_high_limit']
	stochrsi_offset			= 8		if ('stochrsi_offset' not in params) else params['stochrsi_offset']
	nocrossover			= False		if ('nocrossover' not in params) else params['nocrossover']
	crossover_only			= False		if ('crossover_only' not in params) else params['crossover_only']

	di_period			= 48		if ('di_period' not in params) else params['di_period']
	adx_period			= 92		if ('adx_period' not in params) else params['adx_period']
	adx_threshold			= 25		if ('adx_threshold' not in params) else params['adx_threshold']
	dmi_with_adx			= False		if ('dmi_with_adx' not in params) else params['dmi_with_adx']

	macd_short_period		= 48		if ('macd_short_period' not in params) else params['macd_short_period']
	macd_long_period		= 104		if ('macd_long_period' not in params) else params['macd_long_period']
	macd_signal_period		= 36		if ('macd_signal_period' not in params) else params['macd_signal_period']
	macd_offset			= 0.006		if ('macd_offset' not in params) else params['macd_offset']

	aroonosc_period			= 24		if ('aroonosc_period' not in params) else params['aroonosc_period']
	aroonosc_alt_period		= 48		if ('aroonosc_alt_period' not in params) else params['aroonosc_alt_period']
	aroonosc_alt_threshold		= 0.24		if ('aroonosc_alt_threshold' not in params) else params['aroonosc_alt_threshold']
	aroonosc_secondary_threshold	= 70		if ('aroonosc_secondary_threshold' not in params) else params['aroonosc_secondary_threshold']
	aroonosc_with_macd_simple	= False		if ('aroonosc_with_macd_simple' not in params) else params['aroonosc_with_macd_simple']
	aroonosc_with_vpt		= False		if ('aroonosc_with_vpt' not in params) else params['aroonosc_with_vpt']

	stochmfi_5m_period		= 14		if ('stochmfi_5m_period' not in params) else params['stochmfi_5m_period']
	stochmfi_period			= 14		if ('stochmfi_period' not in params) else params['stochmfi_period']
	mfi_period			= 14		if ('mfi_period' not in params) else params['mfi_period']
	mfi_low_limit			= 20		if ('mfi_low_limit' not in params) else params['mfi_low_limit']
	mfi_high_limit			= 80		if ('mfi_high_limit' not in params) else params['mfi_high_limit']

	atr_period			= 14		if ('atr_period' not in params) else params['atr_period']
	daily_atr_period		= 3		if ('daily_atr_period' not in params) else params['daily_atr_period']
	vpt_sma_period			= 72		if ('vpt_sma_period' not in params) else params['vpt_sma_period']

	chop_period			= 14		if ('chop_period' not in params) else params['chop_period']
	chop_low_limit			= 38.2		if ('chop_low_limit' not in params) else params['chop_low_limit']
	chop_high_limit			= 61.8		if ('chop_high_limit' not in params) else params['chop_high_limit']

	stochrsi_signal_cancel_low_limit  = 60	if ('stochrsi_signal_cancel_low_limit' not in params) else params['stochrsi_signal_cancel_low_limit']
	stochrsi_signal_cancel_high_limit = 40	if ('stochrsi_signal_cancel_high_limit' not in params) else params['stochrsi_signal_cancel_high_limit']
	rsi_signal_cancel_low_limit	= 40	if ('rsi_signal_cancel_low_limit' not in params) else params['rsi_signal_cancel_low_limit']
	rsi_signal_cancel_high_limit	= 60	if ('rsi_signal_cancel_high_limit' not in params) else params['rsi_signal_cancel_high_limit']
	mfi_signal_cancel_low_limit	= 30	if ('mfi_signal_cancel_low_limit' not in params) else params['mfi_signal_cancel_low_limit']
	mfi_signal_cancel_high_limit	= 70	if ('mfi_signal_cancel_high_limit' not in params) else params['mfi_signal_cancel_high_limit']

	# Resistance indicators
	no_use_resistance		= False		if ('no_use_resistance' not in params) else params['no_use_resistance']
	price_resistance_pct		= 1		if ('price_resistance_pct' not in params) else params['price_resistance_pct']
	price_support_pct		= 1		if ('price_support_pct' not in params) else params['price_support_pct']
	use_natr_resistance		= False		if ('use_natr_resistance' not in params) else params['use_natr_resistance']
	lod_hod_check			= False		if ('lod_hod_check' not in params) else params['lod_hod_check']
	keylevel_strict			= False		if ('keylevel_strict' not in params) else params['keylevel_strict']
	keylevel_use_daily		= False		if ('keylevel_use_daily' not in params) else params['keylevel_use_daily']

	check_etf_indicators_strict	= False		if ('check_etf_indicators_strict' not in params) else params['check_etf_indicators_strict']
	check_etf_indicators		= False		if ('check_etf_indicators' not in params) else params['check_etf_indicators']
	check_etf_indicators		= True		if (check_etf_indicators_strict == True ) else check_etf_indicators ; params['check_etf_indicators'] = check_etf_indicators
	etf_tickers			= ['SPY','QQQ','DIA']	if ('etf_tickers' not in params) else params['etf_tickers']
	etf_indicators			= {}		if ('etf_indicators' not in params) else params['etf_indicators']

	experimental			= False		if ('experimental' not in params) else params['experimental']
	# End params{} configuration


	# If set, turn start_date and/or stop_date into a datetime object
	if ( start_date != None ):
		start_date = datetime.strptime(start_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
		start_date = mytimezone.localize(start_date)
	if ( stop_date != None ):
		stop_date = datetime.strptime(stop_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
		stop_date = mytimezone.localize(stop_date)

	# Ensure we have Heikin Ashi pricehistory data available if needed
	if ( use_ha_exit == True ):
		try:
			pricehistory['hacandles']
		except:
			print('Error, pricehistory does not include Heikin Ashi candle data, exiting.', file=sys.stderr)
			return False

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

	# Daily candles
	if ( daily_ph == None ):

		# get_pricehistory() variables
		p_type	= 'year'
		period	= '2'
		freq	= '1'
		f_type	= 'daily'

		tries	= 0
		while ( tries < 3 ):
			daily_ph, ep = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, needExtendedHoursData=False)
			if ( isinstance(daily_ph, bool) and daily_ph == False ):
				print('Error: daily get_pricehistory(' + str(ticker) + '): attempt ' + str(tries) + ' returned False, retrying...', file=sys.stderr)
				time.sleep(5)
			else:
				break

			tries += 1

		if ( isinstance(daily_ph, bool) and daily_ph == False ):
			print('Error: get_pricehistory(' + str(ticker) + '): unable to retrieve daily data, exiting...', file=sys.stderr)
			sys.exit(1)

	# Weekly candles
	if ( weekly_ph == None ):

		# get_pricehistory() variables
		p_type	= 'year'
		period	= '2'
		freq	= '1'
		f_type	= 'weekly'

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

		if ( isinstance(weekly_ph, bool) and weekly_ph == False ):
			print('Error: get_pricehistory(' + str(ticker) + '): unable to retrieve weekly data, exiting...', file=sys.stderr)
			sys.exit(1)


	# Average True Range (ATR)
	# Calculate this first as we might use daily or intraday NATR to modify the indicators below
	atr	= []
	natr	= []
	try:
		atr, natr = tda_algo_helper.get_atr( pricehistory=pricehistory_5m, period=atr_period )

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_atr(): ' + str(e))
		return False

	# Daily ATR/NATR
	atr_d	= []
	natr_d	= []
	try:
		atr_d, natr_d = tda_algo_helper.get_atr( pricehistory=daily_ph, period=daily_atr_period )

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

	##################################################################################################################
	# Experimental
	if ( experimental == True ):
		sys.path.append(parent_path + '/../candle_patterns/')
		import pattern_helper

		diff_signals = pattern_helper.pattern_differential(pricehistory)
		anti_diff_signals = pattern_helper.pattern_anti_differential(pricehistory)
		fib_signals = pattern_helper.pattern_fibonacci_timing(pricehistory)
	##################################################################################################################


	# Get stochastic RSI/MFI
	stochrsi	= []
	rsi_k		= []
	rsi_d		= []
	try:
		if ( primary_stoch_indicator == 'stochrsi' ):
			if ( with_stoch_5m == True ):
				stochrsi, rsi_k, rsi_d = tda_algo_helper.get_stochrsi(pricehistory_5m, rsi_period=rsi_period, stochrsi_period=stochrsi_5m_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)
			else:
				stochrsi, rsi_k, rsi_d = tda_algo_helper.get_stochrsi(pricehistory, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

			if ( isinstance(stochrsi, bool) and stochrsi == False ):
				print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi() returned false - no data', file=sys.stderr)
				return False

		elif ( primary_stoch_indicator == 'stochmfi' ):
			if ( with_stoch_5m == True ):
				rsi_k, rsi_d = tda_algo_helper.get_stochmfi(pricehistory_5m, mfi_period=mfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)
			else:
				rsi_k, rsi_d = tda_algo_helper.get_stochmfi(pricehistory, mfi_period=mfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)

			stochrsi = rsi_k
			if ( isinstance(rsi_k, bool) and rsi_k == False ):
				print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi() returned false - no data', file=sys.stderr)
				return False

		else:
			stochrsi, rsi_k, rsi_d = tda_algo_helper.get_stochrsi(pricehistory, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)
			print('Primary stochastic indicator is set to "' + str(primary_stoch_indicator) + '"')

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
			stochrsi, rsi_k_5m, rsi_d_5m = tda_algo_helper.get_stochrsi(pricehistory_5m, rsi_period=rsi_period, stochrsi_period=stochrsi_5m_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

		except Exception as e:
			print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi(): ' + str(e))
			return False
		if ( isinstance(stochrsi_5m, bool) and stochrsi_5m == False ):
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi() returned false - no data', file=sys.stderr)
			return False

	if ( with_stochmfi == True or True == True):
		mfi_k		= []
		mfi_d		= []
		try:
			mfi_k, mfi_d = tda_algo_helper.get_stochmfi(pricehistory, mfi_period=stochmfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)

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
			mfi_k_5m, mfi_d_5m = tda_algo_helper.get_stochmfi(pricehistory_5m, mfi_period=stochmfi_5m_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)

		except Exception as e:
			print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi(): ' + str(e))
			return False
		if ( isinstance(mfi_k_5m, bool) and mfi_k_5m == False ):
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochmfi() returned false - no data', file=sys.stderr)
			return False

	# Get RSI
	rsi = []
	try:
		rsi = tda_algo_helper.get_rsi(pricehistory, rsi_period, rsi_type, debug=False)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_rsi(): ' + str(e))
		return False

	# Get MFI
	mfi = []
	try:
		mfi = tda_algo_helper.get_mfi(pricehistory, period=mfi_period)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_mfi(): ' + str(e))

	# ADX, +DI, -DI
	# We now use different periods for adx and plus/minus_di
	if ( with_dmi == True and with_dmi_simple == True ):
		with_dmi_simple = False

	adx		= []
	di_adx		= []
	plus_di		= []
	minus_di	= []
	try:
		di_adx, plus_di, minus_di	= tda_algo_helper.get_adx(pricehistory, period=di_period)
		adx, plus_di_adx, minus_di_adx	= tda_algo_helper.get_adx(pricehistory, period=adx_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_adx(): ' + str(e))
		return False

	# Aroon Oscillator
	# aroonosc_with_macd_simple implies that macd_simple will be enabled or disabled based on the
	#  level of the aroon oscillator (i.e. < aroonosc_secondary_threshold then use macd_simple)
	if ( aroonosc_with_macd_simple == True ):
		with_aroonosc		= True
		with_macd		= False
		with_macd_simple	= False

	aroonosc	= []
	aroonosc_alt	= []
	try:
		aroonosc	= tda_algo_helper.get_aroon_osc(pricehistory, period=aroonosc_period)
		aroonosc_alt	= tda_algo_helper.get_aroon_osc(pricehistory, period=aroonosc_alt_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_aroon_osc(): ' + str(e))
		return False

	# MACD - 48, 104, 36
	if ( with_macd == True and with_macd_simple == True):
		with_macd_simple = False

	macd		= []
	macd_signal	= []
	macd_histogram	= []
	try:
		macd, macd_avg, macd_histogram = tda_algo_helper.get_macd(pricehistory, short_period=macd_short_period, long_period=macd_long_period, signal_period=macd_signal_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_macd(): ' + str(e))
		return False

	# Choppiness Index
	chop = []
	try:
		chop = tda_algo_helper.get_chop_index(pricehistory, period=chop_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_chop_index(): ' + str(e))
		return False

	# VPT - Volume Price Trend
	vpt	= []
	vpt_sma	= []
	try:
		vpt, vpt_sma = tda_algo_helper.get_vpt(pricehistory, period=vpt_sma_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_vpt(): ' + str(e))
		return False

	# Supertrend indicator
	supertrend = []
	try:
		supertrend = tda_algo_helper.get_supertrend(pricehistory=pricehistory, atr_period=supertrend_atr_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_supertrend(): ' + str(e))
		return False

	# Bollinger bands and Keltner channels
	if ( with_bbands_kchannel == True or with_bbands_kchannel_simple == True ):
		bbands_kchannel_offset_debug = { 'squeeze': [], 'cur_squeeze': [] }

		bbands_lower	= []
		bbands_mid	= []
		bbands_upper	= []
		try:
			if ( use_bbands_kchannel_5m == True ):
				bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory_5m, period=bbands_period)
			else:
				bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory, period=bbands_period)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_bbands(): ' + str(e))
			return False

		kchannel_lower	= []
		kchannel_mid	= []
		kchannel_upper	= []
		try:
			if ( use_bbands_kchannel_5m == True ):
				kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory_5m, period=kchannel_period, atr_period=kchannel_atr_period)
			else:
				kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory, period=kchannel_period, atr_period=kchannel_atr_period)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_kchannel(): ' + str(e))
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

	# Calculate vwap
	if ( with_vwap == True or no_use_resistance == False ):
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
				vwap, vwap_up, vwap_down = tda_algo_helper.get_vwap(pricehistory, day=key, end_timestamp=days[key]['end'], num_stddev=2)

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
		max_hodlod_counter = 30
		if ( with_stoch_5m == True ):
			max_hodlod_counter = 6

		# Find the first day from the 1-min pricehistory. We might need this to warn if the PDC
		#  is not available within the test timeframe.
		first_day = datetime.fromtimestamp(int(pricehistory['candles'][0]['datetime'])/1000, tz=mytimezone)

		day_stats = OrderedDict()
		for key in daily_ph['candles']:

			today_dt	= datetime.fromtimestamp(int(key['datetime'])/1000, tz=mytimezone)
			yesterday_dt	= today_dt - timedelta(days=1)
			yesterday_dt	= tda_gobot_helper.fix_timestamp(yesterday_dt, check_day_only=True)

			today		= today_dt.strftime('%Y-%m-%d')
			yesterday	= yesterday_dt.strftime('%Y-%m-%d')

			day_stats[today] = { 'open':		float( key['open'] ),
					     'high':		float( key['high'] ),
					     'low':		float( key['low'] ),
					     'close':		float( key['close'] ),
					     'volume':		int( key['volume'] ),
					     'high_idx':	None,
					     'low_idx':		None,
					     'pdh':		-1,
					     'pdh_idx':		None,
					     'pdl':		999999,
					     'pdl_idx':		None,
					     'pdc':		-1
			}

			if ( yesterday in day_stats ):
				day_stats[today]['pdh'] = float( day_stats[yesterday]['high'] )
				day_stats[today]['pdl'] = float( day_stats[yesterday]['low'] )
				day_stats[today]['pdc'] = float( day_stats[yesterday]['close'] )

			else:
				# This may not be abnormal as daily_ph includes 2-years worth of data, but
				#   fix_timestamp()->ismarketopen_US() only knows about this years' holidays.
				day_stats[today]['pdc'] = float( key['open'] )

				# Only warn if the missing PDC data falls within the bounds of the test data
				if ( today_dt > first_day ):
					print('Warning: PDC for ' + str(yesterday) + 'not found!')

		# We still need to iterate over the 1-minute candles to ensure we have all the info we need
		for idx,key in enumerate( pricehistory['candles'] ):
			today_dt	= datetime.fromtimestamp(int(key['datetime'])/1000, tz=mytimezone)
			yesterday_dt	= today_dt - timedelta(days=1)
			yesterday_dt	= tda_gobot_helper.fix_timestamp(yesterday_dt, check_day_only=True)

			today		= today_dt.strftime('%Y-%m-%d')
			yesterday	= yesterday_dt.strftime('%Y-%m-%d')

			# Fill in the 1-minute pricehistory index
			if ( today in day_stats ):
				if ( tda_gobot_helper.ismarketopen_US(today_dt, safe_open=False) == True ):
					if ( float(key['close']) >= day_stats[today]['high'] ):
						day_stats[today]['high_idx'] = idx
					elif ( float(key['close']) <= day_stats[today]['low'] ):
						day_stats[today]['low_idx'] = idx

				if ( yesterday in day_stats ):
					day_stats[today]['pdh_idx'] = day_stats[yesterday]['high_idx']
					day_stats[today]['pdl_idx'] = day_stats[yesterday]['low_idx']

			# Check day_stats[] in case daily history does not match up exactly with 1-min pricehistory
			else:
				try:
					day_stats[today]['pdh']		= day_stats[yesterday]['high']
					day_stats[today]['pdl']		= day_stats[yesterday]['low']
					pday_stats[today]['pdc']	= day_stats[yesterday]['close']

				except Exception as e:
					print('Warning: daily and 1-min candles mismatch on ' + str(today))
					day_stats[today] = {	'open':		-1,
								'high':		-1,
								'low':		-1,
								'close':	-1,
								'volume':	-1,
								'high_idx':	None,
								'low_idx':	None,
								'pdh':		None,
								'pdh_idx':	None,
								'pdl':		None,
								'pdl_idx':	None,
								'pdc':		-1 }

		# Key levels
		klfilter = False
		long_support, long_resistance = tda_algo_helper.get_keylevels(weekly_ph, filter=klfilter)

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

	# Intraday stacked moving averages
	def get_stackedma(pricehistory=None, stacked_ma_periods=None, stacked_ma_type=None, use_ha_candles=False):
		try:
			assert pricehistory		!= None
			if ( use_ha_candles == True ):
				assert pricehistory['hacandles']

			assert stacked_ma_periods	!= None
			assert stacked_ma_type		!= None
		except:
			return False

		ph = { 'candles': [] }
		if ( use_ha_candles == True ):
			ph['candles'] = pricehistory['hacandles']
		else:
			ph['candles'] = pricehistory['candles']

		stacked_ma_periods = stacked_ma_periods.split(',')
		ma_array = []
		for ma_period in stacked_ma_periods:
			ma = []
			try:
				ma = tda_algo_helper.get_alt_ma(ph, ma_type=stacked_ma_type, period=int(ma_period) )

			except Exception as e:
				print('Error, unable to calculate stacked MAs: ' + str(e))
				return False

			ma_array.append(ma)

		s_ma = []
		for i in range(0, len(ma)):
			ma_tmp = []
			for p in range(0, len(stacked_ma_periods)):
				ma_tmp.append(ma_array[p][i])

			s_ma.append( tuple(ma_tmp) )

		return s_ma

	# Intraday moving averages
	s_ma = get_stackedma(pricehistory, stacked_ma_periods, stacked_ma_type)
	s_ma_ha = get_stackedma(pricehistory, stacked_ma_periods, stacked_ma_type, use_ha_candles=True)
	if ( primary_stoch_indicator == 'stacked_ma' ):
		s_ma_primary = get_stackedma(pricehistory, stacked_ma_periods_primary, stacked_ma_type_primary)
		s_ma_ha_primary = get_stackedma(pricehistory, stacked_ma_periods_primary, stacked_ma_type_primary, use_ha_candles=True)

	# Daily moving averages
	ma = []
	try:
		ma = get_stackedma(daily_ph, '3,5,8', daily_ma_type)

	except Exception as e:
		print('Error, unable to calculate daily EMA: ' + str(e))
		return False

	daily_ma = OrderedDict()
	for idx in range(0, len(daily_ph['candles'])):
		day = datetime.fromtimestamp(int(daily_ph['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
		if day not in daily_ma:
			if ( idx == 0 ):
				daily_ma[day] = ma[idx]
			else:
				# Use the previous day's moving average to avoid looking at the MA that was
				#  generated from the current day's candle (which hasn't happened yet)
				daily_ma[day] = ma[idx-1]
	# End MA

	# Populate SMA/EMA for etf indicators
	if ( check_etf_indicators == True ):
		if ( len(etf_indicators) == 0 ):
			print('Error: etf_indicators{} is empty, exiting.')
			sys.exit(1)

		all_datetime = []
		for t in etf_tickers:
			etf_indicators[t]['sma'] = {}
			etf_indicators[t]['ema'] = {}

			sma_period = ema_period = 5
			etf_sma = []
			etf_ema = []
			try:
				etf_sma = tda_algo_helper.get_sma( etf_indicators[t]['pricehistory'], period=sma_period, type='hlc3' )
				etf_ema = tda_algo_helper.get_ema( etf_indicators[t]['pricehistory'], period=ema_period )

			except Exception as e:
				print('Error, unable to calculate SMA/EMA for ticker ' + str(t) + ': ' + str(e))
				sys.exit(1)

			# Note:
			#  len(sma) = len(pricehistory) - sma_period-1
			#  len(ema) = len(pricehistory)
			for i in range( 0, len(etf_sma) ):
				# Format:
				#  etf_indicators[t]['sma'] = { cur_datetime: cur_sma, ... }
				cur_datetime = int( etf_indicators[t]['pricehistory']['candles'][i+sma_period-1]['datetime'] )
				etf_indicators[t]['sma'][cur_datetime] = etf_sma[i]
				etf_indicators[t]['ema'][cur_datetime] = etf_ema[i+ema_period-1]

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
	stopout_exits			= 0
	end_of_day_exits		= 0
	exit_percent_exits		= 0

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
	di_adx_idx			= len(pricehistory['candles']) - len(di_adx)
	di_idx				= len(pricehistory['candles']) - len(plus_di)
	aroonosc_idx			= len(pricehistory['candles']) - len(aroonosc)
	aroonosc_alt_idx		= len(pricehistory['candles']) - len(aroonosc_alt)
	macd_idx			= len(pricehistory['candles']) - len(macd)
	chop_idx			= len(pricehistory['candles']) - len(chop)

	if ( use_bbands_kchannel_5m == True ):
		bbands_idx	= len(pricehistory['candles']) - len(bbands_mid) * 5
		kchannel_idx	= len(pricehistory['candles']) - len(kchannel_mid) * 5

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
	supertrend_signal		= False

	bbands_kchan_signal_counter	= 0
	bbands_kchan_xover_counter	= 0
	bbands_kchan_init_signal	= False
	bbands_kchan_crossover_signal	= False
	bbands_kchan_signal		= False
	stacked_ma_signal		= False

	plus_di_crossover		= False
	minus_di_crossover		= False
	macd_crossover			= False
	macd_avg_crossover		= False

	near_keylevel			= False
	experimental_signal		= False

	default_incr_threshold		= incr_threshold
	default_decr_threshold		= decr_threshold
	orig_incr_threshold		= incr_threshold
	orig_decr_threshold		= decr_threshold
	orig_exit_percent		= exit_percent

	ma_intraday_affinity		= None
	prev_ma_intraday_affinity	= None
	ma_daily_affinity		= None

	stochrsi_default_low_limit	= 20
	stochrsi_default_high_limit	= 80
	if ( rsi_low_limit > stochrsi_default_low_limit ):
		stochrsi_default_low_limit = rsi_low_limit
	if ( rsi_high_limit < stochrsi_default_high_limit ):
		stochrsi_default_high_limit = rsi_high_limit

	orig_rsi_low_limit		= rsi_low_limit
	orig_rsi_high_limit		= rsi_high_limit

	default_chop_low_limit		= 38.2
	default_chop_high_limit		= 61.8

	first_day			= datetime.fromtimestamp(float(pricehistory['candles'][0]['datetime'])/1000, tz=mytimezone)
	start_day			= first_day + timedelta( days=1 )
	start_day_epoch			= int( start_day.timestamp() * 1000 )

	last_hour_threshold		= 0.2 # Last hour trading threshold

	signal_mode = 'buy'
	if ( shortonly == True ):
		signal_mode = 'short'


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


	# Check orientation fo stacked moving averages
	def check_stacked_ma(s_ma=[], affinity=None):

		if ( affinity == None or len(s_ma) == 0 ):
			return False

		# Round the moving average values to two decimal places
		s_ma = list(s_ma)
		for i in range(0, len(s_ma)):
			s_ma[i] = round( s_ma[i], 2 )

		ma_affinity = False
		if ( affinity == 'bear' ):
			for i in range(0, len(s_ma)):
				if ( i == len(s_ma)-1 ):
					break

				if ( s_ma[i] < s_ma[i+1] ):
					ma_affinity = True
				else:
					ma_affinity = False
					break

		elif ( affinity == 'bull' ):
			for i in range(0, len(s_ma)):
				if ( i == len(s_ma)-1 ):
					break

				if ( s_ma[i] > s_ma[i+1] ):
					ma_affinity = True
				else:
					ma_affinity = False
					break

		return ma_affinity


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


	# Bollinger Bands and Keltner Channel crossover
	def bbands_kchannels(simple=False, cur_bbands=(0,0,0), prev_bbands=(0,0,0), cur_kchannel=(0,0,0), prev_kchannel=(0,0,0),
				bbands_kchan_init_signal=False, bbands_kchan_crossover_signal=False, bbands_kchan_signal=False, debug=False ):

		nonlocal bbands_kchannel_offset
		nonlocal bbands_kchannel_offset_debug
		nonlocal bbands_kchan_signal_counter
		nonlocal bbands_kchan_xover_counter
		nonlocal bbands_kchan_crossover_only

		# bbands/kchannel (0,0,0) = lower, middle, upper
		cur_bbands_lower	= round( cur_bbands[0], 3 )
		cur_bbands_mid		= round( cur_bbands[1], 3 )
		cur_bbands_upper	= round( cur_bbands[2], 3 )

		prev_bbands_lower	= round( prev_bbands[0], 3 )
		prev_bbands_mid		= round( prev_bbands[1], 3 )
		prev_bbands_upper	= round( prev_bbands[2], 3 )

		cur_kchannel_lower	= round( cur_kchannel[0], 3 )
		cur_kchannel_mid	= round( cur_kchannel[1], 3 )
		cur_kchannel_upper	= round( cur_kchannel[2], 3 )

		prev_kchannel_lower	= round( prev_kchannel[0], 3 )
		prev_kchannel_mid	= round( prev_kchannel[1], 3 )
		prev_kchannel_upper	= round( prev_kchannel[2], 3 )

		if ( debug == True and bbands_kchan_init_signal == False and bbands_kchan_signal == False ):
			bbands_kchannel_offset_debug['cur_squeeze'] = []

		# Simple algo
		if ( simple == True ):
			bbands_kchan_init_signal = True
			if ( cur_kchannel_lower < cur_bbands_lower and prev_kchannel_lower < prev_bbands_lower ):
				prev_offset	= ((prev_kchannel_lower / prev_bbands_lower) - 1) * 100
				cur_offset	= ((cur_kchannel_lower / cur_bbands_lower) - 1) * 100
				if ( cur_offset < prev_offset ):
					bbands_kchan_signal = True

			elif ( cur_kchannel_lower > cur_bbands_lower and cur_kchannel_upper < cur_bbands_upper ):
				bbands_kchan_signal = False

			return bbands_kchan_init_signal, bbands_kchan_crossover_signal, bbands_kchan_signal

		# If the Bollinger Bands are outside the Keltner channel and the init signal hasn't been triggered,
		#  then we can just make sure everything is reset and return False. We need to make sure that at least
		#  bbands_kchan_signal_counter is reset and is not left set to >0 after a half-triggered squeeze.
		#
		# If the init signal has been triggered then we can move on and the signal may be canceled later
		#  either via the buy/short signal or using bbands_kchan_xover_counter below
		if ( (cur_bbands_lower <= cur_kchannel_lower or cur_bbands_upper >= cur_kchannel_upper) and bbands_kchan_init_signal == False ):
			bbands_kchan_init_signal	= False
			bbands_kchan_signal		= False
			bbands_kchan_crossover_signal	= False
			bbands_kchan_signal_counter	= 0
			bbands_kchan_xover_counter	= 0

			return bbands_kchan_init_signal, bbands_kchan_crossover_signal, bbands_kchan_signal

		# Check if the Bollinger Bands have moved inside the Keltner Channel
		# Signal when they begin to converge
		if ( cur_kchannel_lower < cur_bbands_lower or cur_kchannel_upper > cur_bbands_upper ):
			# Squeeze counter
			bbands_kchan_signal_counter += 1

			# Enforce a minimum offset to ensure the squeeze has some energy before triggering
			#  the bbands_kchan_init_signal signal
			#
			# Note: I debated checking the bbands_kchan_squeeze_count in this section vs. just setting
			#  bbands_kchan_init_signal=True sooner, and checking bbands_kchan_squeeze_count in the next
			#  section. Having it here results in a bit fewer trades, but slightly better trade percentage.
			#  So this appears to produce just slighly better trades.
			prev_offset	= abs((prev_kchannel_lower / prev_bbands_lower) - 1) * 100
			cur_offset	= abs((cur_kchannel_lower / cur_bbands_lower) - 1) * 100
			if ( cur_offset >= bbands_kchannel_offset and bbands_kchan_signal_counter >= bbands_kchan_squeeze_count ):
				bbands_kchan_init_signal = True

				if ( debug == True ):
					bbands_kchannel_offset_debug['cur_squeeze'].append(cur_offset)

		# Toggle the bbands_kchan_signal when the bollinger bands pop back outside the keltner channel
		if ( bbands_kchan_init_signal == True ):

			# An aggressive strategy is to try to get in early when the Bollinger bands begin to widen
			#  and before they pop out of the Keltner channel
			prev_offset	= abs((prev_kchannel_lower / prev_bbands_lower) - 1) * 100
			cur_offset	= abs((cur_kchannel_lower / cur_bbands_lower) - 1) * 100
			if ( bbands_kchan_crossover_only == False and cur_offset < prev_offset and cur_offset <= bbands_kchannel_offset / 2 ):
				bbands_kchan_signal = True

			# Check for crossover
			if ( (prev_kchannel_lower <= prev_bbands_lower and cur_kchannel_lower > cur_bbands_lower) or
					(prev_kchannel_upper >= prev_bbands_upper and cur_kchannel_upper < cur_bbands_upper) ):
				bbands_kchan_crossover_signal	= True
				bbands_kchan_signal		= True

			if ( bbands_kchan_crossover_signal == True ):
				bbands_kchan_xover_counter += 1

			if ( debug == True ):
				if ( len(bbands_kchannel_offset_debug['cur_squeeze']) > 0 ):
					bbands_kchannel_offset_debug['squeeze'].append( max(bbands_kchannel_offset_debug['cur_squeeze']) )
					bbands_kchannel_offset_debug['cur_squeeze'] = []

			# Cancel the bbands_kchan_signal if the bollinger bands popped back inside the keltner channel,
			#  or if the bbands_kchan_signal_counter has lingered for too long
			#
			# Note: The criteria for the crossover signal is when *either* the upper or lower bands cross over,
			#  since they don't always cross at the same time. So when checking if the bands crossed back over,
			#  it is important that we don't just check the current position but check both the previous and
			#  current positions. Otherwise a lingering upper or lower band could cause the signal to be cancelled
			#  just because it hasn't yet crossed over, but probably will.
			if ( bbands_kchan_crossover_signal == True and
				((prev_kchannel_lower > prev_bbands_lower and cur_kchannel_lower <= cur_bbands_lower) or
				(prev_kchannel_upper < prev_bbands_upper and cur_kchannel_upper >= cur_bbands_upper)) or
				bbands_kchan_xover_counter >= 2 ):

				bbands_kchan_init_signal	= False
				bbands_kchan_signal		= False
				bbands_kchan_crossover_signal	= False
				bbands_kchan_signal_counter	= 0
				bbands_kchan_xover_counter	= 0

		return bbands_kchan_init_signal, bbands_kchan_crossover_signal, bbands_kchan_signal


	# Return a bull/bear signal based on the ttm_trend algorithm
	# Look back 6 candles and take the high and the low of them then divide by 2
	#  and if the close of the next candle is above that number the trend is bullish,
	#  and if its below the trend is bearish.
	def price_trend(candles=None, type='hl2', period=5, affinity=None):

		if ( candles == None or affinity == None ):
			return False

		cur_close	= candles[-1]['close']
		price		= 0
		for idx in range(-(period+1), -1, 1):
			if ( type == 'close' ):
				price += candles[idx]['close']

			elif ( type == 'hl2' ):
				price += (candles[idx]['high'] + candles[idx]['low']) / 2

			elif ( type == 'hlc3' ):
				price += (candles[idx]['high'] + candles[idx]['low'] + candles[idx]['close']) / 3

			elif ( type == 'ohlc4' ):
				price += (candles[idx]['open'] + candles[idx]['high'] + candles[idx]['low'] + candles[idx]['close']) / 4

			else:
				return False

		price = price / period
		#print(str(cur_close) + ' / ' + str(price))

		if ( affinity == 'bull' and cur_close > price ):
			return True
		elif ( affinity == 'bear' and cur_close <= price ):
			return True

		return False


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

		# Helper variables from the current pricehistory data
		date		= datetime.fromtimestamp(int(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone)
		cur_close	= float( pricehistory['candles'][idx]['close'] )
		cur_high	= float( pricehistory['candles'][idx]['high'] )
		cur_low		= float( pricehistory['candles'][idx]['low'] )

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
		prev_adx		= adx[idx - adx_idx - 1]

		cur_di_adx		= di_adx[idx - di_adx_idx]
		prev_di_adx		= di_adx[idx - di_adx_idx - 1]
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

		# Stacked moving average (1min candles)
		cur_s_ma	= s_ma[idx]
		prev_s_ma	= s_ma[idx-1]
		cur_s_ma_ha	= s_ma_ha[idx]
		prev_s_ma_ha	= s_ma_ha[idx-1]
		if ( primary_stoch_indicator == 'stacked_ma' ):
			cur_s_ma_primary	= s_ma_primary[idx]
			prev_s_ma_primary	= s_ma_primary[idx-1]
			cur_s_ma_ha_primary	= s_ma_ha_primary[idx]
			prev_s_ma_ha_primary	= s_ma_ha_primary[idx-1]

		cur_natr_daily = 0
		try:
			cur_natr_daily = daily_natr[date.strftime('%Y-%m-%d')]['natr']
		except:
			pass

		cur_daily_ma = (0,0,0)
		try:
			cur_daily_ma = daily_ma[date.strftime('%Y-%m-%d')]
		except:
			pass

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

		# Check the moving average of the main ETF tickers
		if ( check_etf_indicators == True ):
			etf_affinity = None

			# Floor the current datetime to the lower 5-min
			# This produces and even 5-minute timestamp, with seconds/microseconds=0,
			#  which happens to be what I get from the API.
			cur_dt = date - timedelta(minutes=date.minute % 5, seconds=date.second, microseconds=date.microsecond)
			cur_dt = int( cur_dt.timestamp() * 1000 )

			cur_etf_sma = etf_indicators['sma_avg'][cur_dt]
			cur_etf_ema = etf_indicators['ema_avg'][cur_dt]

			if ( cur_etf_ema > cur_etf_sma ):
				etf_affinity	= 'bull'
				rsi_low_limit	= 15
				rsi_high_limit	= 95

			elif ( cur_etf_ema < cur_etf_sma ):
				etf_affinity	= 'bear'
				rsi_low_limit	= 5
				rsi_high_limit	= 85


		# BUY mode
		if ( signal_mode == 'buy' ):
			short = False

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(75, date) ):
				reset_signals()
				continue

			# Bollinger Bands and Keltner Channel crossover
			# We put this above the primary indicator since we want to keep track of what the
			#  Bollinger bands and Keltner channel are doing across buy/short transitions.
			if ( with_bbands_kchannel == True or with_bbands_kchannel_simple == True ):

				if ( use_bbands_kchannel_5m == True ):
					cur_bbands	= (bbands_lower[int((idx - bbands_idx) / 5)], bbands_mid[int((idx - bbands_idx) / 5)], bbands_upper[int((idx - bbands_idx) / 5)])
					prev_bbands	= (bbands_lower[(int((idx - bbands_idx) / 5))-1], bbands_mid[(int((idx - bbands_idx) / 5))-1], bbands_upper[(int((idx - bbands_idx) / 5))-1])
					cur_kchannel	= (kchannel_lower[int((idx - kchannel_idx) / 5)], kchannel_mid[int((idx - kchannel_idx) / 5)], kchannel_upper[int((idx - kchannel_idx) / 5)])
					prev_kchannel	= (kchannel_lower[(int((idx - kchannel_idx) / 5))-1], kchannel_mid[(int((idx - kchannel_idx) / 5))-1], kchannel_upper[(int((idx - kchannel_idx) / 5))-1])

				else:
					cur_bbands	= (bbands_lower[idx], bbands_mid[idx], bbands_upper[idx])
					prev_bbands	= (bbands_lower[idx-1], bbands_mid[idx-1], bbands_upper[idx-1])
					cur_kchannel	= (kchannel_lower[idx], kchannel_mid[idx], kchannel_upper[idx])
					prev_kchannel	= (kchannel_lower[idx-1], kchannel_mid[idx-1], kchannel_upper[idx-1])

				( bbands_kchan_init_signal,
				  bbands_kchan_crossover_signal,
				  bbands_kchan_signal ) = bbands_kchannels( simple=with_bbands_kchannel_simple, cur_bbands=cur_bbands, prev_bbands=prev_bbands,
										cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
										bbands_kchan_init_signal=bbands_kchan_init_signal,
										bbands_kchan_crossover_signal=bbands_kchan_crossover_signal,
										bbands_kchan_signal=bbands_kchan_signal,
										debug=False )

			# StochRSI / StochMFI Primary
			if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
				# Jump to short mode if StochRSI K and D are already above rsi_high_limit
				# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
				#  does a full loop again before acting on it.
				if ( cur_rsi_k >= stochrsi_default_high_limit and cur_rsi_d >= stochrsi_default_high_limit and noshort == False ):
					reset_signals()
					if ( noshort == False ):
						signal_mode = 'short'
					continue

				# Check StochRSI
				( stochrsi_signal,
				  stochrsi_crossover_signal,
				  stochrsi_threshold_signal,
				  buy_signal ) = get_stoch_signal_long(	cur_rsi_k, cur_rsi_d, prev_rsi_k, prev_rsi_d,
									stochrsi_signal, stochrsi_crossover_signal, stochrsi_threshold_signal, buy_signal )

				if ( cur_rsi_k > stochrsi_signal_cancel_high_limit ):
					# Reset all signals if the primary stochastic
					#  indicator wanders into higher territory
					reset_signals()
					continue

			# Stacked moving average primary
			elif ( primary_stoch_indicator == 'stacked_ma' ):

				# Standard candles
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

				# Heikin Ashi candles
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				# TTM Trend
				if ( use_trend == True ):
					period		= trend_period
					cndl_slice	= []
					for i in range(period+1, 0, -1):
						cndl_slice.append( pricehistory['candles'][idx-i] )

					price_trend_bear_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bear')
					price_trend_bull_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bull')

				# Jump to short mode if the stacked moving averages are showing a bearish movement
				if ( (use_ha_candles == True and (stacked_ma_bear_ha_affinity == True or stacked_ma_bear_affinity == True)) or
					(use_trend == True and price_trend_bear_affinity == True) or
					(use_ha_candles == False and use_trend == False and stacked_ma_bear_affinity == True) ):

					reset_signals( exclude_bbands_kchan=True )
					if ( noshort == False ):
						signal_mode = 'short'
					continue

				elif ( use_ha_candles == True and stacked_ma_bull_ha_affinity == True or stacked_ma_bull_affinity == True ):
					buy_signal = True
				elif ( use_trend == True and price_trend_bull_affinity == True ):
					buy_signal = True
				elif ( use_ha_candles == False and use_trend == False and stacked_ma_bull_affinity == True ):
					buy_signal = True
				else:
					buy_signal = False

			# AroonOsc (simple) primary
			elif ( primary_stoch_indicator == 'aroonosc' ):
				# Jump to short mode if AroonOsc is pointing in that direction
				if ( cur_aroonosc < -15 ):
					reset_signals()
					if ( noshort == False ):
						signal_mode = 'short'
					continue

				if ( cur_aroonosc > 60 ):
					buy_signal = True
				else:
					reset_signals()
					continue


			# StochRSI with 5-minute candles
			if ( with_stochrsi_5m == True ):
				( stochrsi_5m_signal,
				  stochrsi_5m_crossover_signal,
				  stochrsi_5m_threshold_signal,
				  stochrsi_5m_final_signal ) = get_stoch_signal_long( cur_rsi_k_5m, cur_rsi_d_5m, prev_rsi_k_5m, prev_rsi_d_5m,
										      stochrsi_5m_signal, stochrsi_5m_crossover_signal, stochrsi_5m_threshold_signal, stochrsi_5m_final_signal )

				if ( cur_rsi_k_5m > stochrsi_signal_cancel_high_limit ):
					stochrsi_5m_signal		= False
					stochrsi_5m_crossover_signal	= False
					stochrsi_5m_threshold_signal	= False
					stochrsi_5m_final_signal	= False

			# StochMFI
			if ( with_stochmfi == True ):
				( stochmfi_signal,
				  stochmfi_crossover_signal,
				  stochmfi_threshold_signal,
				  stochmfi_final_signal ) = get_stoch_signal_long( cur_mfi_k, cur_mfi_d, prev_mfi_k, prev_mfi_d,
										   stochmfi_signal, stochmfi_crossover_signal, stochmfi_threshold_signal, stochmfi_final_signal )

				if ( cur_mfi_k > stochrsi_signal_cancel_high_limit ):
					stochmfi_signal			= False
					stochmfi_crossover_signal	= False
					stochmfi_threshold_signal	= False
					stochmfi_final_signal		= False

			# StochMFI with 5-minute candles
			if ( with_stochmfi_5m == True ):
				( stochmfi_5m_signal,
				  stochmfi_5m_crossover_signal,
				  stochmfi_5m_threshold_signal,
				  stochmfi_5m_final_signal ) = get_stoch_signal_long( cur_mfi_k_5m, cur_mfi_d_5m, prev_mfi_k_5m, prev_mfi_d_5m,
										      stochmfi_5m_signal, stochmfi_5m_crossover_signal, stochmfi_5m_threshold_signal, stochmfi_5m_final_signal )

				if ( cur_mfi_k_5m > stochrsi_signal_cancel_high_limit ):
					stochmfi_5m_signal		= False
					stochmfi_5m_crossover_signal	= False
					stochmfi_5m_threshold_signal	= False
					stochmfi_5m_final_signal	= False


			# Secondary Indicators
			# Stacked moving averages
			if ( with_stacked_ma == True ):
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma, 'bull')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				if ( stacked_ma_bull_affinity == True ):
					stacked_ma_signal = True
				else:
					stacked_ma_signal = False

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
			if ( cur_plus_di > cur_minus_di ): # Bullish signal
				if ( dmi_with_adx == True ):

					# Require that ADX is above cur_minus_di to confirm bullish momentum
					# If ADX is above both plus/minus DI, then set the DMI signal
					# IF ADX is only above minus DI, then ADX must be rising
					if ( cur_di_adx > cur_minus_di and cur_di_adx > cur_plus_di ):

						# Make sure there is some gap between cur_di_adx and cur_plus_di, and
						#  if not at least make sure di_adx is rising
						if ( cur_di_adx - cur_plus_di > 6 ):
							dmi_signal = True
						elif ( cur_di_adx > prev_di_adx ):
							dmi_signal = True

					elif ( cur_di_adx > cur_minus_di and cur_di_adx < cur_plus_di ):
						if ( cur_di_adx > prev_di_adx ):
							dmi_signal = True

				else:
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
			if ( with_mfi == True ):
				if ( cur_mfi >= mfi_signal_cancel_high_limit ):
					mfi_signal = False
				elif ( prev_mfi > mfi_low_limit and cur_mfi < mfi_low_limit ):
					mfi_signal = False
				elif ( prev_mfi < mfi_low_limit and cur_mfi >= mfi_low_limit ):
					mfi_signal = True

			elif ( with_mfi_simple == True ):
				if ( cur_mfi < mfi_low_limit ):
					mfi_signal = True
				elif ( cur_mfi >= mfi_low_limit ):
					mfi_signal = False

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
				vwap_signal = False
				if ( cur_close < cur_vwap ):
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

			# Supertrend Indicator
			if ( with_supertrend == True ):

				# Supertrend falls over with stocks that are flat/not moving or trending
				if ( cur_natr_daily < supertrend_min_natr ):
					supertrend_signal = True
				else:

					# Short signal
					if ( supertrend[idx-1] <= float(pricehistory['candles'][idx-1]['close']) and \
						supertrend[idx] > float(pricehistory['candles'][idx]['close']) ):
						supertrend_signal = False

					# Long signal
					elif ( supertrend[idx-1] >= float(pricehistory['candles'][idx-1]['close']) and \
						supertrend[idx] < float(pricehistory['candles'][idx]['close']) ):
						supertrend_signal = True

			# Resistance Levels
			if ( no_use_resistance == False and buy_signal == True ):
				today			= date.strftime('%Y-%m-%d')
				resistance_signal	= True

				# PDC
				prev_day_close = -1
				if ( today in day_stats ):
					prev_day_close = day_stats[today]['pdc']

				if ( prev_day_close != 0 ):

					if ( abs((prev_day_close / cur_close - 1) * 100) <= price_resistance_pct ):

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
					if ( cur_close > prev_day_close ):
						natr_mod = 1
						if ( cur_natr_daily >= 8 ):
							natr_mod = 2

						natr_resistance = ((cur_natr_daily / natr_mod) / 100 + 1) * prev_day_close
						if ( cur_close > natr_resistance and buy_signal == True ):
							if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
								if ( cur_rsi_k > cur_rsi_d and cur_rsi_k - cur_rsi_d < 12 ):
									resistance_signal = False
							else:
								resistance_signal = False

						if ( abs((cur_close / natr_resistance - 1) * 100) <= price_resistance_pct and buy_signal == True ):
							if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
								if ( cur_rsi_k > cur_rsi_d and cur_rsi_k - cur_rsi_d < 10 ):
									resistance_signal = False
							else:
								resistance_signal = False

				# VWAP
				if ( resistance_signal == True ):
					cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
					if ( abs((cur_vwap / cur_close - 1) * 100) <= price_resistance_pct ):

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
				cur_hour = int( date.strftime('%-H') )
				if ( resistance_signal == True and lod_hod_check == True and cur_hour >= 13 ):
					cur_day_start	= datetime.strptime(today + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start	= mytimezone.localize(cur_day_start)

					delta = date - cur_day_start
					delta = int( delta.total_seconds() / 60 )

					# Find HOD
					hod = 0
					for i in range (delta, 0, -1):
						if ( float(pricehistory['candles'][idx-i]['close']) > hod ):
							hod = float( pricehistory['candles'][idx-i]['close'] )

					# If the stock has already hit a high of the day, the next rise will likely be
					#  below HOD. If we are below HOD and less than price_resistance_pct from it
					#  then we should not enter the trade.
					if ( cur_close < hod ):
						if ( abs((cur_close / hod - 1) * 100) <= price_resistance_pct ):
							resistance_signal = False

					# END HOD Check

				# Key Levels
				# Check if price is near historic key level
				near_keylevel = False
				if ( resistance_signal == True ):
					for lvl,dt in long_support + long_resistance:
						if ( abs((lvl / cur_close - 1) * 100) <= price_support_pct ):

							# Since we are parsing historical data on key levels,
							#  we should check that we are not just hitting a previous
							#  or newer KL when iterating through the backtest data.
							dt = datetime.fromtimestamp(int(dt)/1000, tz=mytimezone)
							if ( date < dt + timedelta(days=6) or (date >= dt and date <= dt + timedelta(days=6)) ):
								continue

							# Current price is very close to a key level
							# Next check average of last 15 (1-minute) candles
							#
							# If last 15 candles average above key level, then key level is support
							# otherwise it is resistance
							near_keylevel = True

							avg = 0
							for i in range(15, 0, -1):
								avg += float( pricehistory['candles'][idx-i]['close'] )
							avg = avg / 15

							# If average was below key level then key level is resistance
							# Therefore this is not a great buy
							if ( avg < lvl or abs((avg / lvl - 1) * 100) <= price_resistance_pct / 3 ):
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

			# Experimental pattern matching - may be removed
			if ( experimental == True ):
				if ( cur_natr_daily > 6 ):
					#if ( (diff_signals[idx] == 'buy' or anti_diff_signals[idx] == 'buy') and fib_signals[idx]['bull_signal'] <= -8 ):
					if ( fib_signals[idx]['bull_signal'] <= -8 ):
						experimental_signal = True
				else:
					experimental_signal = True


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

				if ( with_supertrend == True and supertrend_signal != True ):
					final_buy_signal = False

				if ( (with_bbands_kchannel == True or with_bbands_kchannel_simple == True) and bbands_kchan_signal != True ):
					final_buy_signal = False

				if ( with_stacked_ma == True and stacked_ma_signal != True ):
					final_buy_signal = False

				if ( confirm_daily_ma == True and check_stacked_ma(cur_daily_ma, 'bear') == True ):
					final_buy_signal = False

				if ( no_use_resistance == False and resistance_signal != True ):
					final_buy_signal = False

				# Min/max stock behavior options
				if ( min_intra_natr != None and cur_natr < min_intra_natr ):
					final_buy_signal = False
				if ( max_intra_natr != None and cur_natr > max_intra_natr ):
					final_buy_signal = False
				if ( min_price != None and cur_close < min_price ):
					final_buy_signal = False
				if ( max_price != None and cur_close > max_price ):
					final_buy_signal = False

				# Experimental indicators here
				if ( check_etf_indicators_strict == True and etf_affinity == 'bear' ):
					final_buy_signal = False
				if ( experimental == True and experimental_signal != True ):
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
					', bbands_kchan_signal: '	+ str(bbands_kchan_signal) +
					', bbands_kchan_crossover_signal: ' + str(bbands_kchan_crossover_signal) +
					', bbands_kchan_init_signal: '	+ str(bbands_kchan_init_signal) +
					', stacked_ma_signal: '		+ str(stacked_ma_signal) +
					', vwap_signal: '		+ str(vwap_signal) +
					', vpt_signal: '		+ str(vpt_signal) +
					', resistance_signal: '		+ str(resistance_signal) )

				print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(time_t) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
				print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
				print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
				print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) +
								', Cur/Prev DI_ADX: ' + str(round(cur_di_adx,3)) + ' / ' + str(round(prev_di_adx,3)) + ' signal: ' + str(dmi_signal))
				print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
				print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
				print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))

				if ( with_bbands_kchannel == True or with_bbands_kchannel_simple == True ):
					print('(' + str(ticker) + '): BBands: ' + str(round(cur_bbands[0], 4)) + ' / ' + str(round(cur_bbands[2], 4)) +
									', KChannel: ' + str(round(cur_kchannel[0], 4)) + ' / ' + str(round(cur_kchannel[2], 4)) +
									', Squeeze Count: ' + str(bbands_kchan_signal_counter) )

				print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
				print('(' + str(ticker) + '): BUY signal: ' + str(buy_signal) + ', Final BUY signal: ' + str(final_buy_signal))
				print()
			# DEBUG


			# BUY SIGNAL
			if ( buy_signal == True and final_buy_signal == True ):
				purchase_price	= pricehistory['candles'][idx]['close']
				base_price	= purchase_price
				purchase_time	= datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

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

					elif ( cur_natr*2 < decr_threshold ):
						decr_threshold = cur_natr*2

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG


		# SELL mode
		if ( signal_mode == 'sell' ):

			# Set last_close and last_open using either raw candles from API or Heiken Ashi candles
			last_open	= pricehistory['candles'][idx]['open']
			last_close	= pricehistory['candles'][idx]['close']

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(5, date) ):
				sell_signal		= True
				end_of_day_exits	+= 1

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60, date) == True and hold_overnight == False ):
				if ( last_close > purchase_price ):
					percent_change = abs( purchase_price / last_close - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						sell_signal		= True
						end_of_day_exits	+= 1

			# If stock is sinking over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( use_bbands_kchannel_xover_exit == True ):
				if ( use_bbands_kchannel_5m == True ):
					cur_bbands_lower	= round( bbands_lower[int((idx - bbands_idx) / 5)], 3 )
					cur_bbands_upper	= round( bbands_upper[int((idx - bbands_idx) / 5)], 3 )
					cur_kchannel_lower	= round( kchannel_lower[int((idx - kchannel_idx) / 5)], 3 )
					cur_kchannel_upper	= round( kchannel_upper[int((idx - kchannel_idx) / 5)], 3 )
				else:
					cur_bbands_lower	= round( bbands_lower[idx], 3 )
					cur_bbands_upper	= round( bbands_upper[idx], 3 )
					cur_kchannel_lower	= round( kchannel_lower[idx], 3 )
					cur_kchannel_upper	= round( kchannel_upper[idx], 3 )

				# Handle adverse conditions before the crossover
				if ( cur_kchannel_lower < cur_bbands_lower and cur_kchannel_upper > cur_bbands_upper ):
					if ( bbands_kchan_crossover_signal == True ):

						# BBands and KChannel crossed over, but then crossed back. This usually
						#  indicates that the stock is being choppy or changing direction. Check
						#  the direction of the stock, and if it's moving in the wrong direction
						#  then just exit. If we exit early we might even have a chance to re-enter
						#  in the right direction.
						if ( primary_stoch_indicator == 'stacked_ma' ):
							if ( check_stacked_ma(cur_s_ma_primary, 'bear') == True and last_close < purchase_price ):
								sell_signal = True

					if ( primary_stoch_indicator == 'stacked_ma' ):
						if ( check_stacked_ma(cur_s_ma_primary, 'bear') == True ):

							# Stock momentum switched directions after entry and before crossover
							# We'll give it bbands_kchannel_xover_exit_count minutes to correct itself
							#  and then lower decr_threshold to mitigate risk.
							bbands_kchan_xover_counter += 1
							if ( bbands_kchan_xover_counter >= bbands_kchannel_xover_exit_count and last_close < purchase_price ):
								if ( decr_threshold > 0.5 ):
									decr_threshold = 0.5

						elif ( check_stacked_ma(cur_s_ma_primary, 'bull') == True ):
							if ( bbands_kchan_xover_counter > 0 ):
								bbands_kchan_xover_counter = 0

				# Handle adverse conditions after the crossover
				elif ( cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper ):
					bbands_kchan_crossover_signal = True

					if ( last_close < purchase_price and decr_threshold > 0.5 ):
						decr_threshold = 0.5

					if ( primary_stoch_indicator == 'stacked_ma' ):
						if ( check_stacked_ma(cur_s_ma_primary, 'bear') == True and last_close < purchase_price ):
							# If we are not trending in the right direction after crossover then this
							#  strategy is not likely to succeed.
							sell_signal = True

			# STOPLOSS
			# Monitor cost basis
			percent_change = 0
			if ( last_close < base_price and sell_signal == False and exit_percent_signal == False ):

				# SELL the security if we are using a trailing stoploss
				percent_change = abs( last_close / base_price - 1 ) * 100
				if ( stoploss == True and percent_change >= decr_threshold ):

					# Sell
					sell_price	= pricehistory['candles'][idx]['close']
					sell_time	= datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

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

					stopout_exits	+= 1
					purchase_price	= 0
					base_price	= 0
					incr_threshold	= orig_incr_threshold = default_incr_threshold
					decr_threshold	= orig_decr_threshold = default_decr_threshold
					exit_percent	= orig_exit_percent

					signal_mode	= 'short'
					continue

			elif ( last_close > base_price and sell_signal == False ):
				percent_change = abs( base_price / last_close - 1 ) * 100
				if ( percent_change >= incr_threshold ):
					base_price = last_close

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
			if ( exit_percent != None and last_close > purchase_price and sell_signal == False ):

				# If exit_percent has been hit, we will sell at the first RED candle
				#  unless --quick_exit was set.
				total_percent_change = abs( purchase_price / last_close - 1 ) * 100
				if ( total_percent_change >= exit_percent ):
					exit_percent_signal = True
					if ( quick_exit == True ):
						sell_signal		= True
						exit_percent_exits	+= 1

				if ( exit_percent_signal == True and sell_signal == False ):
					if ( use_trend_exit == True ):
						if ( use_ha_exit == True ):
							cndls = pricehistory['hacandles']
						else:
							cndls = pricehistory['candles']

						# We need to pull the latest n-period candles from pricehistory and send it
						#  to our function.
						period		= trend_period
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( cndls[idx-i] )

						if ( price_trend(cndl_slice, type=trend_type, period=period, affinity='bull') == False ):
							sell_signal		= True
							exit_percent_exits	+= 1

					elif ( use_ha_exit == True ):
						last_open	= pricehistory['hacandles'][idx]['open']
						last_close	= pricehistory['hacandles'][idx]['close']
						if ( last_close < last_open ):
							sell_signal		= True
							exit_percent_exits	+= 1

					elif ( use_combined_exit == True ):
						trend_exit	= False
						ha_exit		= False

						# Check trend
						period		= trend_period
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( pricehistory['candles'][idx-i] )
						if ( price_trend(cndl_slice, type=trend_type, period=period, affinity='bull') == False ):
							trend_exit = True

						# Check Heikin Ashi
						ha_open		= pricehistory['hacandles'][idx]['open']
						ha_close	= pricehistory['hacandles'][idx]['close']
						if ( ha_close < ha_open ):
							ha_exit	= True

						if ( trend_exit == True or ha_exit == True ):
							sell_signal		= True
							exit_percent_exits	+= 1

					elif ( last_close < last_open ):
						sell_signal		= True
						exit_percent_exits	+= 1

			# If we've reached this point we probably need to stop out
			elif ( exit_percent_signal == True and last_close < purchase_price ):
				exit_percent_signal = False
				decr_threshold = 0.5

			# Monitor RSI for SELL signal
			#  Note that this RSI implementation is more conservative than the one for buy/sell to ensure we don't
			#  miss a valid sell signal.
			#
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( variable_exit == False and strict_exit_percent == False and exit_percent_signal == False ):
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
				sell_price = pricehistory['candles'][idx]['close']
				sell_time = datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

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

			# Bollinger Bands and Keltner Channel crossover
			# We put this above the primary indicator since we want to keep track of what the
			#  Bollinger bands and Keltner channel are doing across buy/short transitions.
			if ( with_bbands_kchannel == True or with_bbands_kchannel_simple == True ):

				if ( use_bbands_kchannel_5m == True ):
					bbands_idx	= len(pricehistory['candles']) - len(bbands_mid) * 5
					kchannel_idx	= len(pricehistory['candles']) - len(kchannel_mid) * 5
					cur_bbands	= (bbands_lower[int((idx - bbands_idx) / 5)], bbands_mid[int((idx - bbands_idx) / 5)], bbands_upper[int((idx - bbands_idx) / 5)])
					prev_bbands	= (bbands_lower[(int((idx - bbands_idx) / 5))-1], bbands_mid[(int((idx - bbands_idx) / 5))-1], bbands_upper[(int((idx - bbands_idx) / 5))-1])
					cur_kchannel	= (kchannel_lower[int((idx - kchannel_idx) / 5)], kchannel_mid[int((idx - kchannel_idx) / 5)], kchannel_upper[int((idx - kchannel_idx) / 5)])
					prev_kchannel	= (kchannel_lower[(int((idx - kchannel_idx) / 5))-1], kchannel_mid[(int((idx - kchannel_idx) / 5))-1], kchannel_upper[(int((idx - kchannel_idx) / 5))-1])

				else:
					cur_bbands	= (bbands_lower[idx], bbands_mid[idx], bbands_upper[idx])
					prev_bbands	= (bbands_lower[idx-1], bbands_mid[idx-1], bbands_upper[idx-1])
					cur_kchannel	= (kchannel_lower[idx], kchannel_mid[idx], kchannel_upper[idx])
					prev_kchannel	= (kchannel_lower[idx-1], kchannel_mid[idx-1], kchannel_upper[idx-1])

				( bbands_kchan_init_signal,
				  bbands_kchan_crossover_signal,
				  bbands_kchan_signal ) = bbands_kchannels( simple=with_bbands_kchannel_simple, cur_bbands=cur_bbands, prev_bbands=prev_bbands,
										cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
										bbands_kchan_init_signal=bbands_kchan_init_signal,
										bbands_kchan_crossover_signal=bbands_kchan_crossover_signal,
										bbands_kchan_signal=bbands_kchan_signal,
										debug=False )

			# StochRSI / StochMFI Primary
			if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
				# Jump to buy mode if StochRSI K and D are already below rsi_low_limit
				if ( cur_rsi_k <= stochrsi_default_low_limit and cur_rsi_d <= stochrsi_default_low_limit ):
					reset_signals()
					if ( shortonly == False ):
						signal_mode = 'buy'
					continue

				# Monitor StochRSI
				( stochrsi_signal,
				  stochrsi_crossover_signal,
				  stochrsi_threshold_signal,
				  short_signal ) = get_stoch_signal_short( cur_rsi_k, cur_rsi_d, prev_rsi_k, prev_rsi_d,
									   stochrsi_signal, stochrsi_crossover_signal, stochrsi_threshold_signal, short_signal )

				if ( cur_rsi_k < stochrsi_signal_cancel_low_limit ):
					# Reset all signals if the primary stochastic
					#  indicator wanders into low territory
					reset_signals()
					continue

			# Stacked moving average primary
			elif ( primary_stoch_indicator == 'stacked_ma' ):

				# Standard candles
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

				# Heikin Ashi candles
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				# TTM Trend
				if ( use_trend == True ):
					period		= trend_period
					cndl_slice	= []
					for i in range(period+1, 0, -1):
						cndl_slice.append( pricehistory['candles'][idx-i] )

					price_trend_bear_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bear')
					price_trend_bull_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bull')

				# Jump to buy mode if the stacked moving averages are showing a bearish movement
				if ( (use_ha_candles == True and (stacked_ma_bull_ha_affinity == True or stacked_ma_bull_affinity == True)) or
					(use_trend == True and price_trend_bull_affinity == True) or
					(use_ha_candles == False and stacked_ma_bull_affinity == True) ):

					reset_signals( exclude_bbands_kchan=True )
					if ( shortonly == False ):
						signal_mode = 'buy'
					continue

				elif ( use_ha_candles == True and stacked_ma_bear_ha_affinity == True and stacked_ma_bear_affinity == True ):
					short_signal = True
				elif ( use_trend == True and price_trend_bear_affinity == True ):
					short_signal = True
				elif ( use_ha_candles == False and use_trend == False and stacked_ma_bear_affinity == True ):
					short_signal = True
				else:
					short_signal = False

			# AroonOsc (simple) primary
			elif ( primary_stoch_indicator == 'aroonosc' ):
				# Jump to short mode if AroonOsc is pointing in that direction
				if ( cur_aroonosc > 10 ):
					reset_signals()
					if ( shortonly == False ):
						signal_mode = 'buy'
					continue

				if ( cur_aroonosc < -60 ):
					short_signal = True
				else:
					reset_signals()
					continue


			# StochRSI with 5-minute candles
			if ( with_stochrsi_5m == True ):
				( stochrsi_5m_signal,
				  stochrsi_5m_crossover_signal,
				  stochrsi_5m_threshold_signal,
				  stochrsi_5m_final_signal ) = get_stoch_signal_short(	cur_rsi_k_5m, cur_rsi_d_5m, prev_rsi_k_5m, prev_rsi_d_5m,
											stochrsi_5m_signal, stochrsi_5m_crossover_signal, stochrsi_5m_threshold_signal, stochrsi_5m_final_signal )

				if ( cur_rsi_k_5m < stochrsi_signal_cancel_low_limit ):
					stochrsi_5m_signal		= False
					stochrsi_5m_crossover_signal	= False
					stochrsi_5m_threshold_signal	= False
					stochrsi_5m_final_signal	= False

			# StochMFI
			if ( with_stochmfi == True ):
				( stochmfi_signal,
				  stochmfi_crossover_signal,
				  stochmfi_threshold_signal,
				  stochmfi_final_signal ) = get_stoch_signal_short( cur_mfi_k, cur_mfi_d, prev_mfi_k, prev_mfi_d,
										    stochmfi_signal, stochmfi_crossover_signal, stochmfi_threshold_signal, stochmfi_final_signal )

				if ( cur_mfi_k < stochrsi_signal_cancel_low_limit ):
					stochmfi_signal			= False
					stochmfi_crossover_signal	= False
					stochmfi_threshold_signal	= False
					stochmfi_final_signal		= False

			# StochMFI with 5-minute candles
			if ( with_stochmfi_5m == True ):
				( stochmfi_5m_signal,
				  stochmfi_5m_crossover_signal,
				  stochmfi_5m_threshold_signal,
				  stochmfi_5m_final_signal ) = get_stoch_signal_short(	cur_mfi_k_5m, cur_mfi_d_5m, prev_mfi_k_5m, prev_mfi_d_5m,
											stochmfi_5m_signal, stochmfi_5m_crossover_signal, stochmfi_5m_threshold_signal, stochmfi_5m_final_signal )

				if ( cur_mfi_k_5m < stochrsi_signal_cancel_low_limit ):
					stochmfi_5m_signal		= False
					stochmfi_5m_crossover_signal	= False
					stochmfi_5m_threshold_signal	= False
					stochmfi_5m_final_signal	= False


			# Secondary Indicators
			# Stacked moving averages
			if ( with_stacked_ma == True ):
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma, 'bear')
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')

				if ( stacked_ma_bear_affinity == True ):
					stacked_ma_signal = True
				else:
					stacked_ma_signal = False

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
			if ( cur_plus_di < cur_minus_di ): # Bearish signal
				if ( dmi_with_adx == True ):

					# Require that ADX is above cur_plus_di to confirm bullish momentum
					# If ADX is above both plus/minus DI, then set the DMI signal
					# IF ADX is only above plus DI, then ADX must be rising
					if ( cur_di_adx > cur_plus_di and cur_di_adx > cur_minus_di ):

						# Make sure there is some gap between cur_di_adx and cur_minus_di, and
						#  if not at least make sure di_adx is rising
						if ( cur_di_adx - cur_minus_di > 6 ):
							dmi_signal = True
						elif ( cur_di_adx > prev_di_adx ):
							dmi_signal = True

					elif ( cur_di_adx > cur_plus_di and cur_di_adx < cur_minus_di ):
						if ( cur_di_adx > prev_di_adx ):
							dmi_signal = True

				else:
					if ( with_dmi_simple == True ):
						dmi_signal = True
					elif ( plus_di_crossover == True ):
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
			if ( with_mfi == True ):
				if ( cur_mfi <= mfi_signal_cancel_low_limit ):
					mfi_signal = False
				elif ( prev_mfi < mfi_high_limit and cur_mfi > mfi_high_limit ):
					mfi_signal = False
				elif ( prev_mfi > mfi_high_limit and cur_mfi <= mfi_high_limit ):
					mfi_signal = True

			elif ( with_mfi_simple == True ):
				if ( cur_mfi > mfi_high_limit ):
					mfi_signal = True
				elif ( cur_mfi <= mfi_high_limit ):
					mfi_signal = False

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
				if ( cur_close > cur_vwap ):
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

			# Supertrend indicator
			if ( with_supertrend == True ):

				# Supertrend falls over with stocks that are flat/not moving or trending
				if ( cur_natr_daily < supertrend_min_natr ):
					supertrend_signal = True
				else:
					# Short signal
					if ( supertrend[idx-1] <= float(pricehistory['candles'][idx-1]['close']) and \
						supertrend[idx] > float(pricehistory['candles'][idx]['close']) ):
						supertrend_signal = True

					# Long signal
					elif ( supertrend[idx-1] >= float(pricehistory['candles'][idx-1]['close']) and \
						supertrend[idx] < float(pricehistory['candles'][idx]['close']) ):
						supertrend_signal = False

			# Resistance
			if ( no_use_resistance == False and short_signal == True ):
				today			= datetime.fromtimestamp(float(key['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d')
				resistance_signal	= True

				# PDC
				prev_day_close = -1
				if ( today in day_stats ):
					prev_day_close = day_stats[today]['pdc']

				if ( prev_day_close != 0 ):

					if ( abs((prev_day_close / cur_close - 1) * 100) <= price_resistance_pct ):

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
					if ( cur_close < prev_day_close ):
						natr_mod = 1
						if ( cur_natr_daily > 8 ):
							natr_mod = 2

						natr_resistance = ((cur_natr_daily / natr_mod) / 100 + 1) * prev_day_close - prev_day_close
						natr_resistance = prev_day_close - natr_resistance

						if ( cur_close < natr_resistance and short_signal == True ):
							if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
								if ( cur_rsi_k < cur_rsi_d and cur_rsi_d - cur_rsi_k < 12 ):
									resistance_signal = False
							else:
								resistance_signal = False

						if ( abs((cur_close / natr_resistance - 1) * 100) <= price_resistance_pct and short_signal == True ):
							if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
								if ( cur_rsi_k < cur_rsi_d and cur_rsi_d - cur_rsi_k < 10 ):
									resistance_signal = False
							else:
								resistance_signal = False

				# VWAP
				if ( resistance_signal == True ):
					cur_vwap = vwap_vals[pricehistory['candles'][idx]['datetime']]['vwap']
					if ( abs((cur_vwap / cur_close - 1) * 100) <= price_resistance_pct ):

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
				cur_hour = int( date.strftime('%-H') )
				if ( resistance_signal == True and lod_hod_check == True and cur_hour >= 13 ):
					cur_day_start	= datetime.strptime(today + ' 09:30:00', '%Y-%m-%d %H:%M:%S')
					cur_day_start	= mytimezone.localize(cur_day_start)

					delta = date - cur_day_start
					delta = int( delta.total_seconds() / 60 )

					# Find LOD
					lod = 9999
					for i in range (delta, 0, -1):
						if ( float(pricehistory['candles'][idx-i]['close']) < lod ):
							lod = float( pricehistory['candles'][idx-i]['close'] )

					# If the stock has already hit a low of the day, the next decrease will likely be
					#  above LOD. If we are above LOD and less than price_resistance_pct from it
					#  then we should not enter the trade.
					if ( cur_close > lod ):
						if ( abs((lod / cur_close - 1) * 100) <= price_resistance_pct ):
							resistance_signal = False

					# END LOD Check

				# Key Levels
				# Check if price is near historic key level
				if ( resistance_signal == True ):
					near_keylevel = False
					for lvl,dt in long_support + long_resistance:
						if ( abs((lvl / cur_close - 1) * 100) <= price_resistance_pct ):

							# Since we are parsing historical data on key levels,
							#  we should check that we are not just hitting a previous
							#  KL when iterating through the backtest data.
							dt = datetime.fromtimestamp(int(dt)/1000, tz=mytimezone)
							if ( dt + timedelta(days=6) > date or (date >= dt and date <= dt + timedelta(days=6)) ):
								continue

							# Current price is very close to a key level
							# Next check average of last 15 (1-minute) candles
							#
							# If last 15 candles average below key level, then key level is resistance
							# otherwise it is support
							near_keylevel = True

							avg = 0
							for i in range(15, 0, -1):
								avg += float( pricehistory['candles'][idx-i]['close'] )
							avg = avg / 15

							# If average was above key level then key level is support
							# If average is still within 1/2 of price_resistance_pct then it is also still risky
							if ( avg > lvl or abs((avg / lvl - 1) * 100) <= price_resistance_pct / 3 ):
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

			if ( experimental == True ):
				if ( cur_natr_daily > 6 ):
					#if ( (diff_signals[idx] == 'short' or anti_diff_signals[idx] == 'short') and fib_signals[idx]['bear_signal'] >= 8 ):
					if ( fib_signals[idx]['bear_signal'] >= 8 ):
						experimental_signal = True
				else:
					experimental_signal = True


			# Resolve the primary stochrsi short_signal with the secondary indicators
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

				if ( with_supertrend == True and supertrend_signal != True ):
					final_short_signal = False

				if ( (with_bbands_kchannel == True or with_bbands_kchannel_simple == True) and bbands_kchan_signal != True ):
					final_short_signal = False

				if ( with_stacked_ma == True and stacked_ma_signal != True ):
					final_short_signal = False

				if ( confirm_daily_ma == True and check_stacked_ma(cur_daily_ma, 'bull') == True ):
					final_short_signal = False

				if ( no_use_resistance == False and resistance_signal != True ):
					final_short_signal = False

				# Min/max stock behavior options
				if ( min_intra_natr != None and cur_natr < min_intra_natr ):
					final_short_signal = False
				if ( max_intra_natr != None and cur_natr > max_intra_natr ):
					final_short_signal = False
				if ( min_price != None and cur_close < min_price ):
					final_short_signal = False
				if ( max_price != None and cur_close > max_price ):
					final_short_signal = False

				# Experimental
				if ( check_etf_indicators_strict == True and etf_affinity == 'bull' ):
					final_short_signal = False
				if ( experimental == True and experimental_signal != True ):
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
					', bbands_kchan_signal: '	+ str(bbands_kchan_signal) +
					', bbands_kchan_crossover_signal: ' + str(bbands_kchan_crossover_signal) +
					', bbands_kchan_init_signal: '  + str(bbands_kchan_init_signal) +
					', stacked_ma_signal: '		+ str(stacked_ma_signal)+
					', vwap_signal: '		+ str(vwap_signal) +
					', vpt_signal: '		+ str(vpt_signal) +
					', resistance_signal: '		+ str(resistance_signal) )

				print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(time_t) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
				print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
				print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
				print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) +
								', Cur/Prev DI_ADX: ' + str(round(cur_di_adx,3)) + ' / ' + str(round(prev_di_adx,3)) + ' signal: ' + str(dmi_signal))
				print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
				print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
				print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))

				if ( with_bbands_kchannel == True or with_bbands_kchannel_simple == True ):
					print('(' + str(ticker) + '): BBands: ' + str(round(cur_bbands[0], 4)) + ' / ' + str(round(cur_bbands[2], 4)) +
								  ', KChannel: ' + str(round(cur_kchannel[0], 4)) + ' / ' + str(round(cur_kchannel[2], 4)) +
								  ', Squeeze Count: ' + str(bbands_kchan_signal_counter) )
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

				short_price	= pricehistory['candles'][idx]['close']
				base_price	= short_price
				short_time	= datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

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

					elif ( cur_natr*2 < decr_threshold ):
						decr_threshold = cur_natr*2

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold) + ', Decr_Threshold: ' + str(decr_threshold) + ', Exit Percent: ' + str(exit_percent))
					print('------------------------------------------------------')
				# DEBUG


		# BUY-TO-COVER mode
		if ( signal_mode == 'buy_to_cover' ):

			# Set last_close and last_open using either raw candles from API or Heiken Ashi candles
			last_open	= pricehistory['candles'][idx]['open']
			last_close	= pricehistory['candles'][idx]['close']

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(5, date) ):
				buy_to_cover_signal	= True
				end_of_day_exits	+= 1

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( tda_gobot_helper.isendofday(60, date) == True and hold_overnight == False ):
				if ( last_close < short_price ):
					percent_change = abs( short_price / last_close - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						buy_to_cover_signal	= True
						end_of_day_exits	+= 1

			# If stock is rising over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( use_bbands_kchannel_xover_exit == True ):
				if ( use_bbands_kchannel_5m == True ):
					cur_bbands_lower	= round( bbands_lower[int((idx - bbands_idx) / 5)], 3 )
					cur_bbands_upper	= round( bbands_upper[int((idx - bbands_idx) / 5)], 3 )
					cur_kchannel_lower	= round( kchannel_lower[int((idx - kchannel_idx) / 5)], 3 )
					cur_kchannel_upper	= round( kchannel_upper[int((idx - kchannel_idx) / 5)], 3 )
				else:
					cur_bbands_lower	= round( bbands_lower[idx], 3 )
					cur_bbands_upper	= round( bbands_upper[idx], 3 )
					cur_kchannel_lower	= round( kchannel_lower[idx], 3 )
					cur_kchannel_upper	= round( kchannel_upper[idx], 3 )

				# Handle adverse conditions before the crossover
				if ( cur_kchannel_lower < cur_bbands_lower and cur_kchannel_upper > cur_bbands_upper ):
					if ( bbands_kchan_crossover_signal == True ):

						# BBands and KChannel crossed over, but then crossed back. This usually
						#  indicates that the stock is being choppy or changing direction. Check
						#  the direction of the stock, and if it's moving in the wrong direction
						#  then just exit. If we exit early we might even have a chance to re-enter
						#  in the right direction.
						if ( primary_stoch_indicator == 'stacked_ma' ):
							if ( check_stacked_ma(cur_s_ma_primary, 'bull') == True and last_close > short_price ):
								buy_to_cover_signal = True

					if ( primary_stoch_indicator == 'stacked_ma' ):
						if ( check_stacked_ma(cur_s_ma_primary, 'bull') == True ):

							# Stock momentum switched directions after entry and before crossover.
							# We'll give it bbands_kchannel_xover_exit_count minutes to correct itself
							#  and then lower decr_threshold to mitigate risk.
							bbands_kchan_xover_counter += 1
							if ( bbands_kchan_xover_counter >= bbands_kchannel_xover_exit_count and last_close > short_price ):
								if ( decr_threshold > 0.5 ):
									decr_threshold = 0.5

						elif ( check_stacked_ma(cur_s_ma_primary, 'bear') == True ):
							if ( bbands_kchan_xover_counter > 0 ):
								bbands_kchan_xover_counter = 0

				# Handle adverse conditions after the crossover
				if ( cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper ):
					bbands_kchan_crossover_signal = True

					if ( last_close > short_price and decr_threshold > 0.5 ):
						decr_threshold = 0.5

					if ( primary_stoch_indicator == 'stacked_ma' ):
						if ( check_stacked_ma(cur_s_ma_primary, 'bull') == True and last_close > short_price ):
							# If we are not trending in the right direction after crossover then this
							#  strategy is not likely to succeed.
							buy_to_cover_signal = True

			# STOPLOSS
			# Monitor cost basis
			percent_change = 0
			if ( last_close > base_price and buy_to_cover_signal == False and exit_percent_signal == False ):

				# Buy-to-cover the security if we are using a trailing stoploss
				percent_change = abs( base_price / last_close - 1 ) * 100
				if ( stoploss == True and percent_change >= decr_threshold ):

					# Buy-to-cover
					buy_to_cover_price = pricehistory['candles'][idx]['close']
					buy_to_cover_time = datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

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

					stopout_exits	+= 1
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

			elif ( last_close < base_price and buy_to_cover_signal == False ):
				percent_change = abs( last_close / base_price - 1 ) * 100
				if ( percent_change >= incr_threshold ):
					base_price = last_close

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
			if ( last_close < short_price and exit_percent != None and buy_to_cover_signal == False ):

				# If exit_percent has been hit, we will sell at the first GREEN candle
				#  unless quick_exit was set.
				total_percent_change = abs( last_close / short_price - 1 ) * 100
				if ( total_percent_change >= float(exit_percent) ):
					exit_percent_signal = True
					if ( quick_exit == True ):
						buy_to_cover_signal	= True
						exit_percent_exits	+= 1

				if ( exit_percent_signal == True and buy_to_cover_signal == False ):
					if ( use_trend_exit == True ):
						if ( use_ha_exit == True ):
							cndls = pricehistory['hacandles']
						else:
							cndls = pricehistory['candles']

						# We need to pull the latest n-period candles from pricehistory and send it
						#  to our function.
						period = trend_period
						cndl_slice = []
						for i in range(period+1, 0, -1):
							cndl_slice.append( cndls[idx-i] )

						if ( price_trend(cndl_slice, type=trend_type, period=period, affinity='bear') == False ):
							buy_to_cover_signal	= True
							exit_percent_exits	+= 1

					elif ( use_ha_exit == True ):
						last_open	= pricehistory['hacandles'][idx]['open']
						last_close	= pricehistory['hacandles'][idx]['close']
						if ( last_close > last_open ):
							buy_to_cover_signal	= True
							exit_percent_exits	+= 1

					elif ( use_combined_exit == True ):
						trend_exit	= False
						ha_exit		= False

						# Check trend
						period = trend_period
						cndl_slice = []
						for i in range(period+1, 0, -1):
							cndl_slice.append( pricehistory['candles'][idx-i] )
						if ( price_trend(cndl_slice, type=trend_type, period=period, affinity='bear') == False ):
							trend_exit = True

						# Check Heikin Ashi
						ha_open		= pricehistory['hacandles'][idx]['open']
						ha_close	= pricehistory['hacandles'][idx]['close']
						if ( ha_close > ha_open ):
							ha_exit	= True

						if ( trend_exit == True or ha_exit == True ):
							buy_to_cover_signal	= True
							exit_percent_exits	+= 1

					elif ( last_close > last_open ):
						buy_to_cover_signal	= True
						exit_percent_exits	+= 1

			elif ( exit_percent_signal == True and last_close > short_price ):
				# If we've reached this point we probably need to stop out
				exit_percent_signal = False
				decr_threshold = 0.5

			# Monitor RSI for BUY_TO_COVER signal
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( variable_exit == False and strict_exit_percent == False and exit_percent_signal == False ):
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

				buy_to_cover_price = pricehistory['candles'][idx]['close']
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

	# End main loop

	# Debug
	if ( debug == True and len(results) > 0):
		if ( (with_bbands_kchannel == True or with_bbands_kchannel_simple == True) and len(bbands_kchannel_offset_debug['squeeze']) > 0 ):
			print( 'DEBUG: bbands_kchannel_offset_debug: ' + str(min(bbands_kchannel_offset_debug['squeeze'])) + ' / ' +
									 str(max(bbands_kchannel_offset_debug['squeeze'])) + ' / ' +
									 str(sum(bbands_kchannel_offset_debug['squeeze'])/len(bbands_kchannel_offset_debug['squeeze'])) )
			print()

	print('# Exit stats')
	print('stopouts: ' + str(stopout_exits) + ', end_of_day: ' + str(end_of_day_exits) + ', exit_percent: ' + str(exit_percent_exits) + "\n")

	return results

