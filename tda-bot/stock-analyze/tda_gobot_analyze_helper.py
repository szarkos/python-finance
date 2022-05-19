#!/usr/bin/python3 -u

import os, sys, time, re
from collections import OrderedDict

from datetime import datetime, timedelta
from pytz import timezone

import numpy as np

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

		nonlocal exit_percent_signal_long	; exit_percent_signal_long	= False
		nonlocal exit_percent_signal_short	; exit_percent_signal_short	= False

		nonlocal stacked_ma_signal		; stacked_ma_signal		= False
		nonlocal mama_fama_signal		; mama_fama_signal		= False
		nonlocal mesa_sine_signal		; mesa_sine_signal		= False

		nonlocal rs_signal			; rs_signal			= False

		nonlocal momentum_signal		; momentum_signal		= False

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
			nonlocal bbands_roc_counter			; bbands_roc_counter			= 0
			nonlocal bbands_kchan_init_signal		; bbands_kchan_init_signal		= False
			nonlocal bbands_kchan_crossover_signal		; bbands_kchan_crossover_signal		= False
			nonlocal bbands_kchan_signal			; bbands_kchan_signal			= False
			nonlocal bbands_roc_threshold_signal		; bbands_roc_threshold_signal		= False

		nonlocal plus_di_crossover		; plus_di_crossover		= False
		nonlocal minus_di_crossover		; minus_di_crossover		= False
		nonlocal macd_crossover			; macd_crossover		= False
		nonlocal macd_avg_crossover		; macd_avg_crossover		= False

		nonlocal trin_init_signal		; trin_init_signal		= False
		nonlocal trin_signal			; trin_signal			= False
		nonlocal trin_counter			; trin_counter			= 0

		nonlocal tick_signal			; tick_signal			= False
		nonlocal roc_signal			; roc_signal			= False
		nonlocal sp_monitor_init_signal		; sp_monitor_init_signal	= False
		nonlocal sp_monitor_signal		; sp_monitor_signal		= False
		nonlocal vix_signal			; vix_signal			= False
		nonlocal ts_monitor_signal		; ts_monitor_signal		= False

		nonlocal experimental_signal		; experimental_signal		= False

		return True

	# END reset_signals

	# Set test parameters based on params{}
	# Syntax is as follows:
	#
	#  Parameter			Default Value	Otherwise, use what was passed in params['var']
	#  var			=	default_value	if ( 'var' not in params ) else params['var']

	# Test range and input options
	stock_usd			= 1000		if ('stock_usd' not in params) else params['stock_usd']

	start_date 			= None		if ('start_date' not in params) else params['start_date']
	stop_date			= None		if ('stop_date' not in params) else params['stop_date']
	ph_only				= False		if ('ph_only' not in params) else params['ph_only']
	safe_open			= True		if ('safe_open' not in params) else params['safe_open']
	safe_open			= False		if (ph_only == True) else safe_open

	weekly_ph			= None		if ('weekly_ph' not in params) else params['weekly_ph']
	daily_ph			= None		if ('daily_ph' not in params) else params['daily_ph']

	debug				= False		if ('debug' not in params) else params['debug']
	debug_all			= False		if ('debug_all' not in params) else params['debug_all']

	# Trade exit parameters
	incr_threshold			= 1		if ('incr_threshold' not in params) else params['incr_threshold']
	decr_threshold			= 1.5		if ('decr_threshold' not in params) else params['decr_threshold']
	stoploss			= False		if ('stoploss' not in params) else params['stoploss']
	exit_percent_long		= None		if ('exit_percent' not in params) else params['exit_percent']
	exit_percent_short		= None		if ('exit_percent' not in params) else params['exit_percent']
	cost_basis_exit			= None		if ('cost_basis_exit' not in params) else params['cost_basis_exit']
	orig_exit_percent		= None		if ('exit_percent' not in params) else params['exit_percent']
	strict_exit_percent		= False		if ('strict_exit_percent' not in params) else params['strict_exit_percent']
	variable_exit			= False		if ('variable_exit' not in params) else params['variable_exit']

	use_ha_exit			= False		if ('use_ha_exit' not in params) else params['use_ha_exit']
	use_ha_candles			= False		if ('use_ha_candles' not in params) else params['use_ha_candles']
	use_trend_exit			= False		if ('use_trend_exit' not in params) else params['use_trend_exit']
	use_rsi_exit			= False		if ('use_rsi_exit' not in params) else params['use_rsi_exit']
	use_mesa_sine_exit		= False		if ('use_mesa_sine_exit' not in params) else params['use_mesa_sine_exit']
	use_trend			= False		if ('use_trend' not in params) else params['use_trend']
	trend_type			= 'hl2'		if ('trend_type' not in params) else params['trend_type']
	trend_period			= 5		if ('trend_period' not in params) else params['trend_period']
	use_combined_exit		= False		if ('use_combined_exit' not in params) else params['use_combined_exit']
	hold_overnight			= False		if ('hold_overnight' not in params) else params['hold_overnight']

	quick_exit			= False		if ('quick_exit' not in params) else params['quick_exit']
	quick_exit_percent		= None		if ('quick_exit_percent' not in params) else params['quick_exit_percent']
	quick_exit_percent		= params['exit_percent'] if (quick_exit_percent == None and params['exit_percent'] != None) else quick_exit_percent
	trend_quick_exit		= False		if ('trend_quick_exit' not in params) else params['trend_quick_exit']
	qe_stacked_ma_periods		= '34,55,89'	if ('qe_stacked_ma_periods' not in params) else params['qe_stacked_ma_periods']
	qe_stacked_ma_type		= 'hma'		if ('qe_stacked_ma_type' not in params) else params['qe_stacked_ma_type']
	default_quick_exit		= quick_exit

	# Stock shorting options
	noshort				= False		if ('noshort' not in params) else params['noshort']
	shortonly			= False		if ('shortonly' not in params) else params['shortonly']

	# Other stock behavior options
	blacklist_earnings		= False		if ('blacklist_earnings' not in params) else params['blacklist_earnings']
	check_volume			= False		if ('check_volume' not in params) else params['check_volume']
	avg_volume			= 2000000	if ('avg_volume' not in params) else params['avg_volume']
	min_volume			= 1500000	if ('min_volume' not in params) else params['min_volume']
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
	stacked_ma_type			= 'kama'	if ('stacked_ma_type' not in params) else params['stacked_ma_type']
	stacked_ma_periods		= '5,8,13'	if ('stacked_ma_periods' not in params) else params['stacked_ma_periods']
	with_stacked_ma_secondary	= False		if ('with_stacked_ma_secondary' not in params) else params['with_stacked_ma_secondary']
	stacked_ma_type_secondary	= 'kama'	if ('stacked_ma_type_secondary' not in params) else params['stacked_ma_type_secondary']
	stacked_ma_periods_secondary	= '5,8,13'	if ('stacked_ma_periods_secondary' not in params) else params['stacked_ma_periods_secondary']
	stacked_ma_type_primary		= 'kama'	if ('stacked_ma_type_primary' not in params) else params['stacked_ma_type_primary']
	stacked_ma_periods_primary	= '5,8,13'	if ('stacked_ma_periods_primary' not in params) else params['stacked_ma_periods_primary']

	with_momentum			= False		if ('with_momentum' not in params) else params['with_momentum']
	momentum_period			= 12		if ('momentum_period' not in params) else params['momentum_period']
	momentum_type			= 'hl2'		if ('momentum_type' not in params) else params['momentum_type']
	momentum_use_trix		= False		if ('momentum_use_trix' not in params) else params['momentum_use_trix']

	daily_ma_type			= 'wma'		if ('daily_ma_type' not in params) else params['daily_ma_type']
	confirm_daily_ma		= False		if ('confirm_daily_ma' not in params) else params['confirm_daily_ma']

	with_mama_fama			= False		if ('with_mama_fama' not in params) else params['with_mama_fama']
	mama_require_xover		= False		if ('mama_require_xover' not in params) else params['mama_require_xover']

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
	bbands_matype			= 0		if ('bbands_matype' not in params) else params['bbands_matype']
	use_bbands_kchannel_5m		= False		if ('use_bbands_kchannel_5m' not in params) else params['use_bbands_kchannel_5m']
	bbands_kchan_crossover_only	= False		if ('bbands_kchan_crossover_only' not in params) else params['bbands_kchan_crossover_only']
	use_bbands_kchannel_xover_exit	= False		if ('use_bbands_kchannel_xover_exit' not in params) else params['use_bbands_kchannel_xover_exit']
	bbands_kchannel_straddle	= False		if ('bbands_kchannel_straddle' not in params) else params['bbands_kchannel_straddle']
	bbands_kchannel_xover_exit_count= 10		if ('bbands_kchannel_xover_exit_count' not in params) else params['bbands_kchannel_xover_exit_count']
	bbands_kchannel_offset		= 0.15		if ('bbands_kchannel_offset' not in params) else params['bbands_kchannel_offset']
	bbands_kchan_squeeze_count	= 8		if ('bbands_kchan_squeeze_count' not in params) else params['bbands_kchan_squeeze_count']
	bbands_kchan_x1_xover		= False		if ('bbands_kchan_x1_xover' not in params) else params['bbands_kchan_x1_xover']
	bbands_kchan_ma_check		= False		if ('bbands_kchan_ma_check' not in params) else params['bbands_kchan_ma_check']
	bbands_kchan_ma_type		= 'ema'		if ('bbands_kchan_ma_type' not in params) else params['bbands_kchan_ma_type']
	bbands_kchan_ma_ptype		= 'close'	if ('bbands_kchan_ma_ptype' not in params) else params['bbands_kchan_ma_ptype']
	bbands_kchan_ma_period		= 21		if ('bbands_kchan_ma_period' not in params) else params['bbands_kchan_ma_period']
	max_squeeze_natr		= None		if ('max_squeeze_natr' not in params) else params['max_squeeze_natr']
	max_bbands_natr			= None		if ('max_bbands_natr' not in params) else params['max_bbands_natr']
	min_bbands_natr			= None		if ('min_bbands_natr' not in params) else params['min_bbands_natr']
	bbands_roc_threshold		= 90		if ('bbands_roc_threshold' not in params) else params['bbands_roc_threshold']
	bbands_roc_strict		= False		if ('bbands_roc_strict' not in params) else params['bbands_roc_strict']
	bbands_roc_count		= 2		if ('bbands_roc_count' not in params) else params['bbands_roc_count']
	bbands_period			= 20		if ('bbands_period' not in params) else params['bbands_period']
	kchannel_period			= 20		if ('kchannel_period' not in params) else params['kchannel_period']
	kchannel_atr_period		= 20		if ('kchannel_atr_period' not in params) else params['kchannel_atr_period']
	kchannel_multiplier		= 1.5		if ('kchannel_multiplier' not in params) else params['kchannel_multiplier']
	kchan_matype			= 'ema'		if ('kchan_matype' not in params) else params['kchan_matype']

	with_mesa_sine			= False		if ('with_mesa_sine' not in params) else params['with_mesa_sine']
	mesa_sine_strict		= False		if ('mesa_sine_strict' not in params) else params['mesa_sine_strict']
	mesa_sine_period		= 25		if ('mesa_sine_period' not in params) else params['mesa_sine_period']
	mesa_sine_type			= 'hl2'		if ('mesa_sine_type' not in params) else params['mesa_sine_type']

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

	stochrsi_signal_cancel_low_limit  = 60		if ('stochrsi_signal_cancel_low_limit' not in params) else params['stochrsi_signal_cancel_low_limit']
	stochrsi_signal_cancel_high_limit = 40		if ('stochrsi_signal_cancel_high_limit' not in params) else params['stochrsi_signal_cancel_high_limit']
	rsi_signal_cancel_low_limit	= 40		if ('rsi_signal_cancel_low_limit' not in params) else params['rsi_signal_cancel_low_limit']
	rsi_signal_cancel_high_limit	= 60		if ('rsi_signal_cancel_high_limit' not in params) else params['rsi_signal_cancel_high_limit']
	mfi_signal_cancel_low_limit	= 30		if ('mfi_signal_cancel_low_limit' not in params) else params['mfi_signal_cancel_low_limit']
	mfi_signal_cancel_high_limit	= 70		if ('mfi_signal_cancel_high_limit' not in params) else params['mfi_signal_cancel_high_limit']

	# Resistance indicators
	no_use_resistance		= False		if ('no_use_resistance' not in params) else params['no_use_resistance']
	price_resistance_pct		= 1		if ('price_resistance_pct' not in params) else params['price_resistance_pct']
	price_support_pct		= 1		if ('price_support_pct' not in params) else params['price_support_pct']
	resist_pct_dynamic		= False		if ('resist_pct_dynamic' not in params) else params['resist_pct_dynamic']
	use_pdc				= False		if ('use_pdc' not in params) else params['use_pdc']
	use_vwap			= False		if ('use_vwap' not in params) else params['use_vwap']
	use_natr_resistance		= False		if ('use_natr_resistance' not in params) else params['use_natr_resistance']
	use_pivot_resistance		= False		if ('use_pivot_resistance' not in params) else params['use_pivot_resistance']
	lod_hod_check			= False		if ('lod_hod_check' not in params) else params['lod_hod_check']
	use_keylevel			= False		if ('use_keylevel' not in params) else params['use_keylevel']
	keylevel_strict			= False		if ('keylevel_strict' not in params) else params['keylevel_strict']
	keylevel_use_daily		= False		if ('keylevel_use_daily' not in params) else params['keylevel_use_daily']
	va_check			= False		if ('va_check' not in params) else params['va_check']

	# Enable some default resistance indicators
	use_pdc				= True		if ( no_use_resistance == False ) else use_pdc
	use_vwap			= True		if ( no_use_resistance == False ) else use_vwap
	use_keylevel			= True		if ( no_use_resistance == False ) else use_keylevel

	check_etf_indicators		= False		if ('check_etf_indicators' not in params) else params['check_etf_indicators']
	check_etf_indicators_strict	= False		if ('check_etf_indicators_strict' not in params) else params ['check_etf_indicators_strict']
	etf_tickers			= ['SPY']	if ('etf_tickers' not in params) else params['etf_tickers']
	etf_indicators			= {}		if ('etf_indicators' not in params) else params['etf_indicators']
	etf_roc_period			= 50		if ('etf_roc_period' not in params) else params['etf_roc_period']
	etf_roc_type			= 'hlc3'	if ('etf_roc_type' not in params) else params['etf_roc_type']
	etf_min_rs			= None		if ('etf_min_rs' not in params) else params['etf_min_rs']
	etf_min_roc			= None		if ('etf_min_roc' not in params) else params['etf_min_roc']
	etf_min_natr			= None		if ('etf_min_natr' not in params) else params['etf_min_natr']

	etf_use_emd			= False		if ('etf_use_emd' not in params) else params['etf_use_emd']
	etf_emd_fraction		= 0.1		if ('mesa_emd_fraction' not in params) else params['mesa_emd_fraction']
	etf_emd_period			= 20		if ('mesa_emd_period' not in params) else params['mesa_emd_period']
	etf_emd_type			= 'hl2'		if ('mesa_emd_type' not in params) else params['mesa_emd_type']

	emd_affinity_long		= False		if ('emd_affinity_long' not in params) else params['emd_affinity_long']
	emd_affinity_short		= False		if ('emd_affinity_short' not in params) else params['emd_affinity_short']
	mesa_emd_fraction		= 0.1		if ('mesa_emd_fraction' not in params) else params['mesa_emd_fraction']
	mesa_emd_period			= 20		if ('mesa_emd_period' not in params) else params['mesa_emd_period']
	mesa_emd_type			= 'hl2'		if ('mesa_emd_type' not in params) else params['mesa_emd_type']

	trin_tick			= {}		if ('trin_tick' not in params) else params['trin_tick']
	with_trin			= False		if ('with_trin' not in params) else params['with_trin']
	trin_roc_type			= 'hlc3'	if ('trin_roc_type' not in params) else params['trin_roc_type']
	trin_roc_period			= 1		if ('trin_roc_period' not in params) else params['trin_roc_period']
	trin_ma_type			= 'ema'		if ('trin_ma_type' not in params) else params['trin_ma_type']
	trin_ma_period			= 5		if ('trin_ma_period' not in params) else params['trin_ma_period']
	trin_oversold			= 3		if ('trin_oversold' not in params) else params['trin_oversold']
	trin_overbought			= -1		if ('trin_overbought' not in params) else params['trin_overbought']

	with_tick			= False		if ('with_tick' not in params) else params['with_tick']
	tick_threshold			= 50		if ('tick_threshold' not in params) else params['tick_threshold']
	tick_ma_type			= 'ema'		if ('tick_ma_type' not in params) else params['tick_ma_type']
	tick_ma_period			= 5		if ('tick_ma_period' not in params) else params['tick_ma_period']

	with_roc			= False		if ('with_roc' not in params) else params['with_roc']
	roc_exit			= False		if ('roc_exit' not in params) else params['roc_exit']
	roc_type			= 'hlc3'	if ('roc_type' not in params) else params['roc_type']
	roc_period			= 25		if ('roc_period' not in params) else params['roc_period']
	roc_ma_type			= 'ema'		if ('roc_ma_type' not in params) else params['roc_ma_type']
	roc_ma_period			= 5		if ('roc_ma_period' not in params) else params['roc_ma_period']
	roc_threshold			= 0.15		if ('roc_threshold' not in params) else params['roc_threshold']
	default_roc_exit		= roc_exit

	with_sp_monitor			= False		if ('with_sp_monitor' not in params) else params['with_sp_monitor']
	sp_monitor_threshold		= 2		if ('sp_monitor_threshold' not in params) else params['sp_monitor_threshold']
	sp_monitor_tickers		= None		if ('sp_monitor_tickers' not in params) else params['sp_monitor_tickers']
	sp_roc_type			= 'hlc3'	if ('sp_roc_type' not in params) else params['sp_roc_type']
	sp_roc_period			= 1		if ('sp_roc_period' not in params) else params['sp_roc_period']
	sp_ma_period			= 5		if ('sp_ma_period' not in params) else params['sp_ma_period']
	sp_monitor_stacked_ma_type	= 'vidya'	if ('sp_monitor_stacked_ma_type' not in params) else params['sp_monitor_stacked_ma_type']
	sp_monitor_stacked_ma_periods	= '13,21'	if ('sp_monitor_stacked_ma_periods' not in params) else params['sp_monitor_stacked_ma_periods']
	sp_monitor_use_trix		= False		if ('sp_monitor_use_trix' not in params) else params['sp_monitor_use_trix']
	sp_monitor_trix_ma_type		= 'hma'		if ('sp_monitor_trix_ma_type' not in params) else params['sp_monitor_trix_ma_type']
	sp_monitor_trix_ma_period	= '5'		if ('sp_monitor_trix_ma_period' not in params) else params['sp_monitor_trix_ma_period']
	sp_monitor_strict		= False		if ('sp_monitor_strict' not in params) else params['sp_monitor_strict']
	sp_monitor			= {}		if ('sp_monitor' not in params) else params['sp_monitor']

	with_vix			= False		if ('with_vix' not in params) else params['with_vix']
	vix_stacked_ma_periods		= '5,8,13'	if ('vix_stacked_ma_periods' not in params) else params['vix_stacked_ma_periods']
	vix_stacked_ma_type		= 'ema'		if ('vix_stacked_ma_type' not in params) else params['vix_stacked_ma_type']
	vix_use_ha_candles		= False		if ('vix_use_ha_candles' not in params) else params['vix_use_ha_candles']
	vix				= {}		if ('vix' not in params) else params['vix']

	time_sales_algo			= False		if ('time_sales_algo' not in params) else params['time_sales_algo']
	time_sales_use_keylevel		= False		if ('time_sales_use_keylevel' not in params) else params['time_sales_use_keylevel']
	time_sales_size_threshold	= 3000		if ('time_sales_size_threshold' not in params) else params['time_sales_size_threshold']
	time_sales_size_max		= 8000		if ('time_sales_size_max' not in params) else params['time_sales_size_max']
	time_sales_kl_size_threshold	= 7500		if ('time_sales_kl_size_threshold' not in params) else params['time_sales_kl_size_threshold']
	time_sales_ma_period		= 8		if ('time_sales_ma_period' not in params) else params['time_sales_ma_period']
	time_sales_ma_type		= 'wma'		if ('time_sales_ma_type' not in params) else params['time_sales_ma_type']
	ts_data				= {}		if ('ts_data' not in params) else params['ts_data']

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
	pricehistory_5m = tda_gobot_helper.translate_1m(pricehistory=pricehistory, candle_type=5)

	# Daily candles
	if ( daily_ph == None ):

		# get_pricehistory() variables
		p_type	= 'year'
		period	= '2'
		freq	= '1'
		f_type	= 'daily'

		tries	= 0
		while ( tries < 3 ):
			daily_ph, ep = tda_gobot_helper.get_pricehistory(ticker, p_type, f_type, freq, period, needExtendedHoursData=True)
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
			try:
				daily_natr[day] = { 'atr': atr_d[idx], 'natr': natr_d[idx] }
			except:
				pass

	# End ATR

	##################################################################################################################
	# Experimental
	#if ( experimental == True ):
	#	sys.path.append(parent_path + '/../candle_patterns/')
	#	import pattern_helper
	#
	#	diff_signals = pattern_helper.pattern_differential(pricehistory)
	#	anti_diff_signals = pattern_helper.pattern_anti_differential(pricehistory)
	#	fib_signals = pattern_helper.pattern_fibonacci_timing(pricehistory)
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

	if ( with_stochmfi == True ):
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

	# RSI
	if ( with_rsi == True or with_rsi_simple == True ):
		rsi = []
		try:
			rsi = tda_algo_helper.get_rsi(pricehistory, rsi_period, rsi_type, debug=False)

		except Exception as e:
			print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_rsi(): ' + str(e))
			return False

	# MFI
	if ( with_mfi == True or with_mfi_simple == True ):
		mfi = []
		try:
			mfi = tda_algo_helper.get_mfi(pricehistory, period=mfi_period)

		except Exception as e:
			print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_mfi(): ' + str(e))
			return False

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

	if ( with_aroonosc == True or with_aroonosc_simple == True ):
		aroonosc	= []
		aroonosc_alt	= []
		try:
			aroonosc	= tda_algo_helper.get_aroon_osc(pricehistory, period=aroonosc_period)
			aroonosc_alt	= tda_algo_helper.get_aroon_osc(pricehistory, period=aroonosc_alt_period)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_aroon_osc(): ' + str(e))
			return False

	# MACD - 48, 104, 36
	if ( with_macd == True and with_macd_simple == True ):
		with_macd_simple = False

	if ( with_macd == True or with_macd_simple == True or aroonosc_with_macd_simple == True ):
		macd		= []
		macd_signal	= []
		macd_histogram	= []
		try:
			macd, macd_avg, macd_histogram = tda_algo_helper.get_macd(pricehistory, short_period=macd_short_period, long_period=macd_long_period, signal_period=macd_signal_period)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_macd(): ' + str(e))
			return False

	# Choppiness Index
	if ( with_chop_index == True or with_chop_simple == True ):
		chop = []
		try:
			chop = tda_algo_helper.get_chop_index(pricehistory, period=chop_period)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_chop_index(): ' + str(e))
			return False

	# VPT - Volume Price Trend
	if ( with_vpt == True or aroonosc_with_vpt == True ):
		vpt	= []
		vpt_sma	= []
		try:
			vpt, vpt_sma = tda_algo_helper.get_vpt(pricehistory, period=vpt_sma_period)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_vpt(): ' + str(e))
			return False

	# Supertrend indicator
	if ( with_supertrend == True ):
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
				bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory_5m, period=bbands_period, type='hlc3', matype=bbands_matype)
			else:
				bbands_lower, bbands_mid, bbands_upper = tda_algo_helper.get_bbands(pricehistory, period=bbands_period, type='hlc3', matype=bbands_matype)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_bbands(): ' + str(e))
			return False

		# Calculate bbands the rate-of-change
		bbands_ph	= { 'candles': [], 'symbol': ticker }
		bbands_roc	= []
		for i in range( len(bbands_upper) ):
			bbands_ph['candles'].append( {	'upper':	bbands_upper[i],
							'middle':	bbands_mid[i],
							'lower':	bbands_lower[i],
							'close':	bbands_upper[i],
							'open':		bbands_lower[i] } )

		bbands_roc = tda_algo_helper.get_roc( bbands_ph, period=bbands_kchan_squeeze_count, type='close' )

		# Keltner Channel
		kchannel_lower		= []
		kchannel_mid		= []
		kchannel_upper		= []
		kchannel_lower_x1	= []
		kchannel_mid_x1		= []
		kchannel_upper_x1	= []
		try:
			if ( use_bbands_kchannel_5m == True ):
				kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory_5m, period=kchannel_period, atr_period=kchannel_atr_period, atr_multiplier=kchannel_multiplier, matype=kchan_matype)
				kchannel_lower_x1, kchannel_mid_x1, kchannel_upper_x1 = tda_algo_helper.get_kchannels(pricehistory_5m, period=kchannel_period, atr_period=kchannel_atr_period, atr_multiplier=1, matype=kchan_matype)
			else:
				kchannel_lower, kchannel_mid, kchannel_upper = tda_algo_helper.get_kchannels(pricehistory, period=kchannel_period, atr_period=kchannel_atr_period, atr_multiplier=kchannel_multiplier, matype=kchan_matype)
				kchannel_lower_x1, kchannel_mid_x1, kchannel_upper_x1 = tda_algo_helper.get_kchannels(pricehistory, period=kchannel_period, atr_period=kchannel_atr_period, atr_multiplier=1, matype=kchan_matype)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_kchannel(): ' + str(e))
			return False

		# 21 EMA to use with bbands_kchan algo
		if ( bbands_kchan_ma_check == True ):
			bbands_kchan_ma = []
			try:
				bbands_kchan_ma = tda_algo_helper.get_alt_ma( pricehistory, ma_type=bbands_kchan_ma_type, type=bbands_kchan_ma_ptype, period=bbands_kchan_ma_period )

			except Exception as e:
				print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_alt_ma(ema,21): ' + str(e))
				return False

	# MESA sine wave
	if ( with_mesa_sine == True or primary_stoch_indicator == 'mesa_sine' or use_mesa_sine_exit == True ):
		sine = []
		lead = []
		try:
			sine, lead = tda_algo_helper.get_mesa_sine(pricehistory=pricehistory, type=mesa_sine_type, period=mesa_sine_period)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_mesa_sine(): ' + str(e))
			return False

	# Empirical Mode Decomposition (EMD)
	if ( emd_affinity_long != None or emd_affinity_short != None ):
		emd_trend	= []
		emd_peak	= []
		emd_valley	= []
		try:
			emd_trend, emd_peak, emd_valley = tda_algo_helper.get_mesa_emd(pricehistory=pricehistory, type=mesa_emd_type, period=mesa_emd_period, fraction=mesa_emd_fraction)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_mesa_emd(): ' + str(e))
			return False

	# Momentum indicator
	if ( with_momentum == True ):
		mom		= []
		trix		= []
		trix_signal	= []
		try:
			mom, trix, trix_signal = tda_algo_helper.get_momentum(pricehistory=pricehistory, period=momentum_period, type=momentum_type)

####### TESTING #######################
			trix, trix_signal = tda_algo_helper.get_trix_altma(pricehistory=pricehistory, ma_type='kama', type='hl2', period=24, signal_ma='ema', signal_period=3, debug=False)
#######################################

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_momentum(): ' + str(e))
			return False

		mom_ph	= { 'candles': [], 'symbol': ticker }
		mom_roc	= []
		for i in range( len(mom) ):
			mom_ph['candles'].append( { 'close': mom[i] } )

		try:
			mom_roc = tda_algo_helper.get_roc( pricehistory=mom_ph, period=3, type='close' )

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_roc(momentum): ' + str(e))
			return False

		del(mom_ph)

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
	if ( with_vwap == True or use_vwap == True or no_use_resistance == False ):
		vwap_vals = OrderedDict()
		days = OrderedDict()

		# Create a dict containing all the days and timestamps for which we need vwap data
		prev_day = ''
		prev_timestamp = ''
		for key in pricehistory['candles']:

			# I have seen single candles delivered from API that fall outside regular market hours for
			#  some reason. Use this to filter them out.
			day = datetime.fromtimestamp(key['datetime']/1000, tz=mytimezone)
			if ( tda_gobot_helper.ismarketopen_US(date=day, check_day_only=True) == False ):
				continue

			day = day.strftime('%Y-%m-%d')
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
	if ( no_use_resistance == False or use_pdc == True or use_natr_resistance == True or lod_hod_check == True ):

		# Find the first day from the 1-min pricehistory. We might need this to warn if the PDC
		#  is not available within the test timeframe.
		first_day = datetime.fromtimestamp(int(pricehistory['candles'][0]['datetime'])/1000, tz=mytimezone)

		day_stats = OrderedDict()
		for key in daily_ph['candles']:

			today_dt	= datetime.fromtimestamp(int(key['datetime'])/1000, tz=mytimezone)
			yesterday_dt	= today_dt - timedelta(days=1)
			yesterday_dt	= tda_gobot_helper.fix_timestamp(yesterday_dt, check_day_only=True)

			twoday_dt	= today_dt - timedelta(days=2)
			twoday_dt	= tda_gobot_helper.fix_timestamp(twoday_dt, check_day_only=True)

			twoday		= twoday_dt.strftime('%Y-%m-%d')
			today		= today_dt.strftime('%Y-%m-%d')
			yesterday	= yesterday_dt.strftime('%Y-%m-%d')

			day_stats[today] = { 'open':		float( key['open'] ),
					     'high':		float( key['high'] ),
					     'low':		float( key['low'] ),
					     'close':		float( key['close'] ),
					     'volume':		int( key['volume'] ),
					     'open_idx':	None,
					     'high_idx':	None,
					     'low_idx':		None,
					     'pdh':		-1,		# Previous day high
					     'pdh_idx':		None,		# Index of PDH on 1-minute candles (pricehistory['candles'])
					     'pdh2':		-1,		# Two-day previous day high
					     'pdl':		999999,		# Previous day low
					     'pdl_idx':		None,		# Index of PD: on 1-minute candles (pricehistory['candles'])
					     'pdl2':		999999,		# Two-day previous day low
					     'pdc':		-1,		# Previous day close
					     'pivot':		-1,
					     'pivot_s1':	-1,
					     'pivot_s2':	-1,
					     'pivot_r1':	-1,
					     'pivot_r2':	-1
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
					print('Warning: PDC for ' + str(yesterday) + ' not found!')

			if ( twoday in day_stats ):
				day_stats[today]['pdh2'] = float( day_stats[twoday]['high'] )
				day_stats[today]['pdl2'] = float( day_stats[twoday]['low'] )

			# Calculate the Pivot Points
			#
			# P = (PDH + PDL + PDC) / 3
			#  or
			# P = (Cur_Open + PDH + PDL + PDC) / 4
			# R1 = (P * 2) - PDL
			# R2 = P + (PDH - PDL) = P + (R1 - S1)
			# S1 = (P * 2) - PDH
			# S2 = P - (PDH - PDL) = P - (R1 - S1)
			day_stats[today]['pivot']       = ( day_stats[today]['open'] + day_stats[today]['pdh'] + day_stats[today]['pdl'] + day_stats[today]['pdc'] ) / 4
			day_stats[today]['pivot_r1']    = ( day_stats[today]['pivot'] * 2 ) - day_stats[today]['pdl']
			day_stats[today]['pivot_r2']    = day_stats[today]['pivot'] + ( day_stats[today]['pdh'] - day_stats[today]['pdl'] )
			day_stats[today]['pivot_s1']    = ( day_stats[today]['pivot'] * 2 ) - day_stats[today]['pdh']
			day_stats[today]['pivot_s2']    = day_stats[today]['pivot'] - ( day_stats[today]['pdh'] - day_stats[today]['pdl'] )

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
					if ( float(key['high']) >= day_stats[today]['high'] ):
						day_stats[today]['high_idx'] = idx
					elif ( float(key['low']) <= day_stats[today]['low'] ):
						day_stats[today]['low_idx'] = idx

				# Sometimes using the open price from the current day's daily candle
				#  as retrieved from TDA isn't very accurate, so instead just store
				#  the index of the first 1min candle so we can use the open price
				#  from that instead.
				if ( today_dt.strftime('%-H:%-M') == '9:30' ):
					day_stats[today]['open_idx'] = idx

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
								'open_idx':	None,
								'high_idx':	None,
								'low_idx':	None,
								'pdh':		-1,
								'pdh2':		-1,
								'pdh_idx':	None,
								'pdl':		-1,
								'pdl2':		-1,
								'pdl_idx':	None,
								'pdc':		-1 }

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

	# Key levels
	if ( use_keylevel == True ):

		# Pull the main keylevels, filtered to reduce redundant keylevels
		long_support, long_resistance = tda_algo_helper.get_keylevels( weekly_ph, filter=True )

		# Also pull the full keylevels, and include those that have been hit more than once
		long_support_full, long_resistance_full = tda_algo_helper.get_keylevels( weekly_ph, filter=False )

		kl = dt = count = 0
		for kl,dt,count in long_support_full:
			if ( count > 1 and (kl, dt, count) not in long_support ):
				long_support.append( (kl, dt, count) )

		for kl,dt,count in long_resistance_full:
			if ( count > 1 and (kl, dt, count) not in long_resistance ):
				long_resistance.append( (kl, dt, count) )

		# If keylevel_use_daily is True then use those daily values as well, but only those that
		#  have been hit more than once
		if ( keylevel_use_daily == True ):
			daily_threshold = 8
			long_support_full, long_resistance_full = tda_algo_helper.get_keylevels( daily_ph, filter=False )

			kl = dt = count = 0
			for kl,dt,count in long_support_full:
				if ( count >= daily_threshold and (kl, dt, count) not in long_support ):
					long_support.append( (kl, dt, count) )

			for kl,dt,count in long_resistance_full:
				if ( count >= daily_threshold and (kl, dt, count) not in long_resistance ):
					long_resistance.append( (kl, dt, count) )

	# VAH/VAL levels
	mprofile = {}
	if ( va_check == True ):
		try:
			mprofile = tda_algo_helper.get_market_profile(pricehistory=pricehistory, close_type='hl2', mp_mode='vol', tick_size=0.01)

		except Exception as e:
			print('Caught Exception: get_market_profile(' + str(ticker) + '): ' + str(e), file=sys.stderr)
			sys.exit(1)

		for day in mprofile:
			cur_day		= datetime.strptime(day, '%Y-%m-%d')
			cur_day		= mytimezone.localize(cur_day)

			prev_day	= cur_day - timedelta( days=1 )
			prev_day	= tda_gobot_helper.fix_timestamp( prev_day )

			prev_prev_day	= prev_day - timedelta( days=1 )
			prev_prev_day	= tda_gobot_helper.fix_timestamp( prev_prev_day )

			cur_day		= cur_day.strftime('%Y-%m-%d')
			prev_day	= prev_day.strftime('%Y-%m-%d')
			prev_prev_day	= prev_prev_day.strftime('%Y-%m-%d')

			mprofile[day]['prev_day']	= prev_day
			mprofile[day]['prev_prev_day']	= prev_prev_day

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

			# MAMA will return a mama/frama tuple - just return mama
			if ( stacked_ma_type == 'mama' ):
				ma = ma[0]

			ma_array.append(ma)

		s_ma = []
		for i in range(0, len(ma)):
			ma_tmp = []
			for p in range(0, len(stacked_ma_periods)):
				ma_tmp.append(ma_array[p][i])

			s_ma.append( tuple(ma_tmp) )

		return s_ma

	# Intraday moving averages
	if ( with_stacked_ma == True ):
		s_ma	= get_stackedma(pricehistory, stacked_ma_periods, stacked_ma_type)
		s_ma_ha	= get_stackedma(pricehistory, stacked_ma_periods, stacked_ma_type, use_ha_candles=True)

		if ( with_stacked_ma_secondary == True ):
			s_ma_secondary		= get_stackedma(pricehistory, stacked_ma_periods_secondary, stacked_ma_type_secondary)
			s_ma_ha_secondary	= get_stackedma(pricehistory, stacked_ma_periods_secondary, stacked_ma_type_secondary, use_ha_candles=True)

	if ( primary_stoch_indicator == 'stacked_ma' ):
		s_ma_primary	= get_stackedma(pricehistory, stacked_ma_periods_primary, stacked_ma_type_primary)
		s_ma_ha_primary	= get_stackedma(pricehistory, stacked_ma_periods_primary, stacked_ma_type_primary, use_ha_candles=True)

	# MAMA/FAMA algorithm
	if ( primary_stoch_indicator == 'mama_fama' or with_mama_fama == True ):
		mama = []
		fama = []
		try:
			mama, fama = tda_algo_helper.get_alt_ma(pricehistory=pricehistory, ma_type='mama', type='hlc3', mama_fastlimit=0.5, mama_slowlimit=0.05)

		except Exception as e:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_alt_ma(mama): ' + str(e))
			return False

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

	# $TRIN and $TICK
	if ( primary_stoch_indicator == 'trin' or with_trin == True or with_tick == True ):

		# Calculate the MA for the rate-of-change, for both $TRIN and $TICK
		# ROC values need to be squared up with the timestamp so they can be matched properly with
		#  the datetime value from the current stock's candle.
		trin_roc	= []
		trinq_roc	= []
		trina_roc	= []
		try:
			trin_roc	= tda_algo_helper.get_roc( trin_tick['trin']['pricehistory'], period=trin_roc_period, type=trin_roc_type, calc_percentage=True )
			#trinq_roc	= tda_algo_helper.get_roc( trin_tick['trinq']['pricehistory'], period=trin_roc_period, type=trin_roc_type, calc_percentage=True )
			trina_roc	= tda_algo_helper.get_roc( trin_tick['trina']['pricehistory'], period=trin_roc_period, type=trin_roc_type, calc_percentage=True )

		except Exception as e:
			print('Error, unable to calculate rate-of-change for trin_tick: ' + str(e))
			sys.exit(1)

		# It's important to cap the min/max for $TRIN and $TICK because occasionally TDA returns
		#  some very high values, which can mess with the moving average calculation (particularly EMA)
		trin_roc	= tda_algo_helper.normalize_vals( arr_data=trin_roc, min_val=-1000, max_val=1000, min_default=-1000, max_default=1000 )
		#trinq_roc	= tda_algo_helper.normalize_vals( arr_data=trinq_roc, min_val=-1000, max_val=1000, min_default=-1000, max_default=1000 )
		trina_roc	= tda_algo_helper.normalize_vals( arr_data=trina_roc, min_val=-1000, max_val=1000, min_default=-1000, max_default=1000 )

		# TRIN* data sorted by timestamps
		for i in range( len(trin_tick['trin']['pricehistory']['candles']) ):
			dt = trin_tick['trin']['pricehistory']['candles'][i]['datetime']
			trin_tick['trin']['roc'].update( { dt: trin_roc[i] } )

		#for i in range( len(trin_tick['trinq']['pricehistory']['candles']) ):
		#	dt = trin_tick['trinq']['pricehistory']['candles'][i]['datetime']
		#	trin_tick['trinq']['roc'].update( { dt: trinq_roc[i] } )

		for i in range( len(trin_tick['trina']['pricehistory']['candles']) ):
			dt = trin_tick['trina']['pricehistory']['candles'][i]['datetime']
			trin_tick['trina']['roc'].update( { dt: trina_roc[i] } )

		# Calculate the MA for the rate-of-change, for both $TRIN and $TICK
		#
		# When using $TRIN + $TRIN/Q we will average the ROC from each when generating the moving average
		# However, $TRIN and $TRIN/Q might have some different datetimes, so we need to account for that
		temp_ph = { 'candles': [] }
		#all_dts = list( trin_tick['trin']['roc'].keys() ) + list( trin_tick['trinq']['roc'].keys() ) + list( trin_tick['trina']['roc'].keys() )
		all_dts = list( trin_tick['trin']['roc'].keys() ) + list( trin_tick['trina']['roc'].keys() )
		all_dts = sorted( list(dict.fromkeys(all_dts)) )
		for dt in all_dts:
			trin	= trin_tick['trin']['roc'][dt] if ( dt in trin_tick['trin']['roc'] ) else 0
			#trinq	= trin_tick['trinq']['roc'][dt] if ( dt in trin_tick['trinq']['roc'] ) else 0
			trina	= trin_tick['trina']['roc'][dt] if ( dt in trin_tick['trina']['roc'] ) else 0

			# SAZ - 2022-04-18 - deprecate $TRINQ, unreliable
			#temp_ph['candles'].append( { 'close': (trin + trinq + trina) / 3 } )
			temp_ph['candles'].append( { 'close': (trin + trina) / 2 } )

		tmp_trin_ma = tda_algo_helper.get_alt_ma(pricehistory=temp_ph, ma_type=trin_ma_type, type='close', period=trin_ma_period)
		for idx,dt in enumerate( all_dts ):
			trin_tick['trin']['roc_ma'].update( { dt: tmp_trin_ma[idx] } )

		# TICK
		all_dts = []
		for i in range(len(trin_tick['tick']['pricehistory']['candles'])):
			all_dts.append( trin_tick['tick']['pricehistory']['candles'][i]['datetime'] )
		for i in range(len(trin_tick['ticka']['pricehistory']['candles'])):
			all_dts.append( trin_tick['ticka']['pricehistory']['candles'][i]['datetime'] )

		all_dts = sorted( list(dict.fromkeys(all_dts)) )

		# It's important to cap the min/max for $TRIN and $TICK because occasionally TDA returns
		#  some very high values, which can mess with the moving average calculation (particularly EMA)
		#
		# Since we're not using ROC, then we need to do this manually here *before* we calculate the
		#   moving averages. This is a pain.

		# $TICK
		# TDA API does not provide perfectly accurate $TICK data, but hl2 is the only possibly usable variant of this data
		temp_arr = []
		for i in range( len(trin_tick['tick']['pricehistory']['candles']) ):
			tick_hl2 = (	trin_tick['tick']['pricehistory']['candles'][i]['high'] +
					trin_tick['tick']['pricehistory']['candles'][i]['low'] ) / 2
			temp_arr.append( tick_hl2 )

		temp_arr = tda_algo_helper.normalize_vals( arr_data=temp_arr, min_val=-2000, max_val=2000, min_default=0, max_default=0 )

		temp_ph = { 'candles': [] }
		for i in range( len(temp_arr) ):
			temp_ph['candles'].append( { 'close': temp_arr[i] } )

		tmp_tick_ma = tda_algo_helper.get_alt_ma(pricehistory=temp_ph, ma_type=tick_ma_type, type='close', period=tick_ma_period)

		# $TICKA
		# TDA API does not provide perfectly accurate $TICKA data, but hl2 is the only possibly usable variant of this data
		temp_arr = []
		for i in range( len(trin_tick['ticka']['pricehistory']['candles']) ):
			tick_hl2 = (	trin_tick['ticka']['pricehistory']['candles'][i]['high'] +
					trin_tick['ticka']['pricehistory']['candles'][i]['low'] ) / 2
			temp_arr.append( tick_hl2 )

		temp_arr = tda_algo_helper.normalize_vals( arr_data=temp_arr, min_val=-2000, max_val=2000, min_default=0, max_default=0 )

		temp_ph = { 'candles': [] }
		for i in range( len(temp_arr) ):
			temp_ph['candles'].append( { 'close': temp_arr[i] } )

		tmp_ticka_ma = tda_algo_helper.get_alt_ma(pricehistory=temp_ph, ma_type=tick_ma_type, type='close', period=tick_ma_period)

		# Put this all together now in an array with dt:val
		tick_ma_dict = {}
		for i in range(len(trin_tick['tick']['pricehistory']['candles'])):
			dt			= trin_tick['tick']['pricehistory']['candles'][i]['datetime']
			tick_ma_dict[dt]	= tmp_tick_ma[i]

		ticka_ma_dict = {}
		for i in range(len(trin_tick['ticka']['pricehistory']['candles'])):
			dt			= trin_tick['ticka']['pricehistory']['candles'][i]['datetime']
			ticka_ma_dict[dt]	= tmp_ticka_ma[i]

		for dt in all_dts:
			tick	= tick_ma_dict[dt] if ( dt in tick_ma_dict ) else 0
			ticka	= ticka_ma_dict[dt] if ( dt in ticka_ma_dict ) else 0

			trin_tick['tick']['roc_ma'].update( { dt: (tick + ticka) / 2 } )


	# ROC indicator
	roc = []
	if ( with_roc == True or roc_exit == True ):
		try:
			roc = tda_algo_helper.get_roc( pricehistory, period=roc_period, type=roc_type, calc_percentage=True )

		except Exception as e:
			print('Error, unable to calculate rate-of-change for roc indicator: ' + str(e))
			sys.exit(1)

		temp_ph = { 'candles': [] }
		for i in range( len(roc) ):
			temp_ph['candles'].append({ 'close': roc[i] })

		try:
			roc_ma = tda_algo_helper.get_alt_ma( pricehistory=temp_ph, period=roc_ma_period, ma_type=roc_ma_type, type='close' )

		except Exception as e:
			print('Error, unable to calculate the moving average from the rate-of-change for the roc indicator: ' + str(e))
			sys.exit(1)

	# SP monitor
	if ( with_sp_monitor == True or primary_stoch_indicator == 'sp_monitor' ):

		# This is a little convoluted, but really all we want to do is take the *weighted* average of the *weighted*
		#  rate-of-change for each ticker in sp_monitor_tickers, and then calculate the EMA for the final
		#  rate-of-change values.
		#
		# Formula is as follows:
		#  - Calculate the 1-period rate-of-change for each candle of each stock ticker in sp_monitor_tickers[],
		#    but weight each RoC value based on the % representation in the target ETF:
		#
		#	roc_stock1 = ((stock1_cur_cndl - stock1_prev_cndl) / stock1_prev_cndl) * stock1_pct
		#
		# - For each candle, add all the RoCs together for each stock ticker, and then divide that by the sum of
		#   the previous candle for each ticker, divided by the % representation in the target ETF:
		#
		#	 total_roc[i] = (roc_stock1[i] + roc_stock2[i] .... ) \
		#		( (stock1_prev_cndl[i-1] * stock1_pct) + (stock1_prev_cndl[i-1] * stock2_pct) + ... )
		#
		# - Next, take the EMA ofr the total_roc
		#	ema(total_roc, 5)
		#
		# The difficulty with all this like all this, just like other backtesting algos in this file, is that each
		#  ticker in sp_monitor_tickers will have a different number of candles. Just like the ETF indicator, each
		#  ROC value will need to be identified based on the datetime value for each candle.
		roc_total = OrderedDict()
		for t in sp_monitor_tickers:
			try:
				sp_t	= str( t.split(':')[0] )
				sp_pct	= float( t.split(':')[1] ) / 100

			except Exception as e:
				print('Warning, invalid sp_monitor ticker format: ' + str(t) + ', ' + str(e))
				continue

			# Get the ROC for each ticker pricehistory
			sp_roc = []
			try:
				sp_roc = tda_algo_helper.get_roc( sp_monitor[sp_t]['pricehistory'], period=sp_roc_period, type=sp_roc_type, calc_percentage=False )

			except Exception as e:
				print('Error, unable to calculate rate-of-change for sp_monitor: ' + str(e))
				sys.exit(1)

			# Separate out each element of sp_roc[] based on the datetime of the original stock's pricehistory data
			for i in range( len(sp_monitor[sp_t]['pricehistory']['candles']) ):
				dt = sp_monitor[sp_t]['pricehistory']['candles'][i]['datetime']

				# In a later section we will need the HLC3 value for the previous candle, so we can calculate this
				#  now and put it in sp_monitor[sp_t][dt]['prev_cndl']
				if ( i == 0 ):
					prev_cndl_hlc3 = 0
				else:
					prev_cndl_hlc3 = ( sp_monitor[sp_t]['pricehistory']['candles'][i-1]['high'] +
							   sp_monitor[sp_t]['pricehistory']['candles'][i-1]['low'] +
							   sp_monitor[sp_t]['pricehistory']['candles'][i-1]['close'] ) / 3

				sp_monitor[sp_t][dt] = {	'roc':		sp_roc[i] * sp_pct,
								'prev_cndl':	prev_cndl_hlc3 * sp_pct }

				# roc_total will contain ALL the various timestamps from all the tickers, and the total rate-of-change
				#  values for each timestamp for all tickers.
				if ( dt not in roc_total ):
					roc_total.update( { dt: sp_monitor[sp_t][dt]['roc'] } )
				else:
					roc_total[dt] += sp_monitor[sp_t][dt]['roc']

		# At this point datetime keys have been added by various tickers, but since different tickers will have varying
		#  number of candles, we'll need to sort and re-create roc_total{}.
		roc_t = OrderedDict()
		for i in sorted( roc_total ):
			roc_t[i] = roc_total[i]
		roc_total = roc_t

		# roc_total{} contains the rate of change values for each candle for each ticker. However, for the next step we need
		#  to look at each candle (each timestamp) and divide the total rate-of-change with the sum of each stock's previous
		#  candle multiplied by the weighted percent.
		#
		# Iterate over all the timestamps in roc_total, and add up the prev_cndle_total from each ticker for each timestamp
		for dt in roc_total:
			prev_cndl_total = 0
			for t in sp_monitor_tickers:
				sp_t = str( t.split(':')[0] )

				if ( dt in sp_monitor[sp_t] ):
					prev_cndl_total += sp_monitor[sp_t][dt]['prev_cndl']

			# Once we have prev_cndl_total, we can divide roc_total[dt] by this value to find the final roc_total
			if ( prev_cndl_total == 0 ):
				roc_total[dt] = 0
			else:
				# These values are incredibly small - so multiply by 10000000 to make them useful
				roc_total[dt] = ( roc_total[dt] / prev_cndl_total ) * 10000000

		# Populate a temporary pricehistory from roc_total and calculate the EMA and Impulse
		# The EMA will just help smooth the ROC, the Impulse will help determine the change
		#  in the rate of change over time.
		temp_ph = { 'candles': [] }
		sp_monitor_roc_ma = []
		for dt in roc_total:
			temp_ph['candles'].append( { 'high': roc_total[dt], 'low': roc_total[dt], 'close': roc_total[dt] } )

		sp_monitor_roc_roc	= tda_algo_helper.get_roc(pricehistory=temp_ph, period=1, type='close', calc_percentage=True )
		sp_monitor_roc_ma	= tda_algo_helper.get_alt_ma(pricehistory=temp_ph, ma_type='ema', period=sp_ma_period, type='close')

		# Use TRIX or stacked_ma as indicator to ensure sp_monitor is moving in the right direction and
		#  not just chopping up and down
		if ( sp_monitor_use_trix == True ):
			sp_monitor_trix, sp_monitor_trix_signal	= tda_algo_helper.get_trix_altma( pricehistory=temp_ph, ma_type=sp_monitor_trix_ma_type, period=sp_monitor_trix_ma_period,
													type='close', signal_ma='ema', signal_period=3, skip_log=True )
		else:
			sp_monitor_stacked_ma			= get_stackedma( temp_ph, sp_monitor_stacked_ma_periods, sp_monitor_stacked_ma_type )

		# Finally, each element in roc_ma needs to be separated by timestamp. roc_ma[] will have the same length
		#  as the source data, so we can just iterate over roc_total.keys() and separate each moving average value
		#  based on its timestamp.
		for idx,dt in enumerate( roc_total ):
			sp_monitor['roc_ma'][dt]		= sp_monitor_roc_ma[idx]
			sp_monitor['roc_roc'][dt]		= sp_monitor_roc_roc[idx]

			if ( sp_monitor_use_trix == True ):
				sp_monitor['trix'][dt]		= sp_monitor_trix[idx]
				sp_monitor['trix_signal'][dt]	= sp_monitor_trix_signal[idx]

			else:
				sp_monitor['stacked_ma'][dt]	= sp_monitor_stacked_ma[idx]

		del(roc_total, roc_t)

	# VIX volatility index
	if ( with_vix == True ):
		vix_ma = []
		vix_ma = get_stackedma( vix['pricehistory'], vix_stacked_ma_periods, vix_stacked_ma_type, use_ha_candles=vix_use_ha_candles )

		for i in range( len(vix['pricehistory']['candles']) ):
			dt = vix['pricehistory']['candles'][i]['datetime']
			vix['ma'][dt] = vix_ma[i]

	# Time and sales algo monitor
	if ( time_sales_algo == True ):

		# If use_keylevel is disabled and time_sales_use_keylevel is enabled, then enable use_keylevel,
		#  but it will be populated with only the keylevels found via time/sales data
		if ( time_sales_use_keylevel == True and use_keylevel == False ):
			use_keylevel	= True
			long_support	= []
			long_resistance = []

		ts_days		= []
		ts_tx_data	= {}
		#ts_cum_delta	= 0
		ts_cum_delta	= []
		prev_day	= ''
		for dt in ts_data.keys():
			dt_obj	= datetime.fromtimestamp(dt/1000, tz=mytimezone)
			day	= dt_obj.strftime('%Y-%m-%d')
			t_stamp	= dt_obj.strftime('%Y-%m-%d %H:%M')

			# New day
			# Cumulative delta should get reset at the start of each day
			if ( prev_day == '' ):
				prev_day = day
			elif ( prev_day != day ):
				prev_day = day
				#ts_cum_delta = 0
				ts_cum_delta = []

			# We need to know for which days we actually have time/sales data
			if ( day not in ts_days ):
				ts_days.append( day )

			# Populate ts_tx_data with the transaction information, organized in 1-minute increments,
			#  but each 1-minute timestamp key contains an array to each of the transactions.
			if ( ts_data[dt]['size'] >= time_sales_size_threshold and ts_data[dt]['size'] <= time_sales_size_max ):
				if ( ts_data[dt]['at_ask'] <= 1 and ts_data[dt]['at_bid'] <= 1 ):
					tmp_hl2 = ( ts_data[dt]['high_price'] + ts_data[dt]['low_price'] ) / 2

					if ( t_stamp not in ts_tx_data ):
						ts_tx_data[t_stamp] = { 'txs': [], 'ts_cum_delta': 0 }

					ts_tx_data[t_stamp]['txs'].append( {	'size':		ts_data[dt]['size'],
										'price':	tmp_hl2,
										'at_bid':	ts_data[dt]['at_bid'],
										'at_ask':	ts_data[dt]['at_ask'] } )

					if ( re.search('.*00$', str(int(ts_data[dt]['size']))) != None ):

						# Large neutral trades typically happen at absorption areas
						# Add these to long_resistance as we find them.
						if ( time_sales_use_keylevel == True and ts_data[dt]['at_bid'] == 0 and ts_data[dt]['at_ask'] == 0 and
								ts_data[dt]['size'] >= time_sales_kl_size_threshold ):
							long_resistance.append( (tmp_hl2, dt, 999) )

						# Persistent aggressive bearish action
						elif ( ts_data[dt]['at_bid'] == 1 and ts_data[dt]['at_ask'] == 0 ):
							#ts_cum_delta += -ts_data[dt]['size']
							ts_cum_delta.append( -ts_data[dt]['size'] )

						# Persistent aggressive bullish action
						elif ( ts_data[dt]['at_bid'] == 0 and ts_data[dt]['at_ask'] == 1 ):
							#ts_cum_delta += ts_data[dt]['size']
							ts_cum_delta.append( ts_data[dt]['size'] )

						if ( len(ts_cum_delta) > time_sales_ma_period ):
							cur_ts_cum_delta = tda_algo_helper.get_alt_ma( ts_cum_delta, ma_type=time_sales_ma_type, period=time_sales_ma_period )
							cur_ts_cum_delta = sum(cur_ts_cum_delta)
						else:
							cur_ts_cum_delta = sum(ts_cum_delta)

						ts_tx_data[t_stamp]['ts_cum_delta'] = cur_ts_cum_delta
						#ts_tx_data[t_stamp]['ts_cum_delta'] = ts_cum_delta

		del(ts_cum_delta)

	# Quick exit when entering counter-trend moves
	if ( trend_quick_exit == True ):
		qe_s_ma = get_stackedma(pricehistory, qe_stacked_ma_periods, qe_stacked_ma_type)

	# Populate rate-of-change for etf indicators
	etf_roc		= []
	stock_roc	= []
	if ( check_etf_indicators == True ):
		if ( len(etf_indicators) == 0 ):
			print('Error: etf_indicators{} is empty, exiting.')
			sys.exit(1)

		for t in etf_tickers:
			stock_roc	= []
			etf_roc		= []
			try:
				stock_roc	= tda_algo_helper.get_roc( pricehistory, period=etf_roc_period, type=etf_roc_type )
				etf_roc		= tda_algo_helper.get_roc( etf_indicators[t]['pricehistory'], period=etf_roc_period, type=etf_roc_type )

			except Exception as e:
				print('Error, unable to calculate rate-of-change for ticker ' + str(t) + ': ' + str(e))
				sys.exit(1)

			for i in range( len(etf_indicators[t]['pricehistory']['candles']) ):
				dt = etf_indicators[t]['pricehistory']['candles'][i]['datetime']
				etf_indicators[t]['roc'].update( { dt: etf_roc[i] } )
				etf_indicators[t]['roc_close'].update( { dt: etf_indicators[t]['pricehistory']['candles'][i]['close'] } )

			# Calculate the MA for the rate-of-change for the ETF tickers
			temp_ph			= { 'candles': [] }
			tmp_roc_stacked_ma	= []
			tmp_stacked_ma		= []
			tmp_mama		= []
			tmp_fama		= []
			tmp_atr			= []
			tmp_natr		= []
			tmp_trend		= []
			tmp_peak		= []
			tmp_valley		= []
			try:
				for i in range(len(etf_roc)):
					etf_roc[i] = etf_roc[i] * 10000
					temp_ph['candles'].append({ 'open': etf_roc[i], 'high': etf_roc[i], 'low': etf_roc[i], 'close': etf_roc[i] })

				tmp_roc_stacked_ma		= get_stackedma(pricehistory=temp_ph, stacked_ma_periods=stacked_ma_periods_primary, stacked_ma_type='ema')
				tmp_stacked_ma			= get_stackedma(pricehistory=etf_indicators[t]['pricehistory'], stacked_ma_periods=stacked_ma_periods_primary, stacked_ma_type=stacked_ma_type_primary)

				tmp_atr, tmp_natr		= tda_algo_helper.get_atr(pricehistory=etf_indicators[t]['pricehistory_5m'], period=atr_period)
				tmp_trend, tmp_peak, tmp_valley	= tda_algo_helper.get_mesa_emd(pricehistory=etf_indicators[t]['pricehistory'], type=etf_emd_type, period=etf_emd_period, fraction=etf_emd_fraction)
				#tmp_mama,tmp_fama		= tda_algo_helper.get_alt_ma(pricehistory=etf_indicators[t]['pricehistory'], ma_type='mama', type='close', mama_fastlimit=0.5, mama_slowlimit=0.05)

				# Need to normalize the length of tmp_natr to match etf_indicators[t]['pricehistory']['candles']
				tmp = []
				for i in range(0, atr_period - 1):
					tmp.append(0)
				tmp_natr = tmp + list(tmp_natr)

				for i in range( len(etf_indicators[t]['pricehistory']['candles']) ):
					dt = etf_indicators[t]['pricehistory']['candles'][i]['datetime']

					etf_indicators[t]['roc_stacked_ma'].update( { dt: tmp_roc_stacked_ma[i] } )
					etf_indicators[t]['stacked_ma'].update( { dt: tmp_stacked_ma[i] } )
					etf_indicators[t]['mesa_emd'].update( { dt: (tmp_trend[i],tmp_peak[i],tmp_valley[i]) } )
					#etf_indicators[t]['mama_fama'].update( { dt: (tmp_mama[i],tmp_fama[i]) } )

					if ( int(i/5) <= len(tmp_natr) - 1 ):
						etf_indicators[t]['natr'].update( { dt: tmp_natr[int(i/5)] } )

				del(temp_ph,tmp_roc_stacked_ma,tmp_stacked_ma,tmp_atr,tmp_natr,tmp_mama,tmp_fama,tmp_trend,tmp_peak,tmp_valley)

			except Exception as e:
				print('Error, unable to calculate EMA of rate-of-change for ticker ' + str(t) + ': ' + str(e))
				sys.exit(1)

	# Run through the RSI values and log the results
	results				= []
	straddle_results		= []
	stopout_exits			= 0
	end_of_day_exits		= 0
	exit_percent_exits		= 0

	stochrsi_idx			= len(pricehistory['candles']) - len(rsi_k)
	if ( with_stoch_5m == True ):
		stochrsi_5m_idx = len(pricehistory['candles']) - len(rsi_k) * 5

	if ( with_stochrsi_5m == True ):
		stochrsi_5m_idx = len(pricehistory['candles']) - len(rsi_k_5m) * 5

	if ( with_stochmfi == True ):
		stochmfi_idx = len(pricehistory['candles']) - len(mfi_k)

	if ( with_stochmfi_5m == True ):
		stochmfi_5m_idx = len(pricehistory['candles']) - len(mfi_k_5m) * 5

	if ( with_rsi == True or with_rsi_simple == True ):
		rsi_idx = len(pricehistory['candles']) - len(rsi)

	if ( with_mfi == True or with_mfi_simple == True ):
		mfi_idx = len(pricehistory['candles']) - len(mfi)

	if ( with_aroonosc == True or with_aroonosc_simple == True ):
		aroonosc_idx		= len(pricehistory['candles']) - len(aroonosc)
		aroonosc_alt_idx	= len(pricehistory['candles']) - len(aroonosc_alt)

	if ( with_macd == True or with_macd_simple == True or aroonosc_with_macd_simple == True ):
		macd_idx = len(pricehistory['candles']) - len(macd)

	if ( with_chop_index == True or with_chop_simple == True ):
		chop_idx = len(pricehistory['candles']) - len(chop)

	if ( use_bbands_kchannel_5m == True ):
		bbands_idx	= len(pricehistory['candles']) - len(bbands_mid) * 5
		kchannel_idx	= len(pricehistory['candles']) - len(kchannel_mid) * 5

	adx_idx				= len(pricehistory['candles']) - len(adx)
	di_adx_idx			= len(pricehistory['candles']) - len(di_adx)
	di_idx				= len(pricehistory['candles']) - len(plus_di)

	buy_signal			= False
	sell_signal			= False
	short_signal			= False
	buy_to_cover_signal		= False

	final_buy_signal		= False
	final_sell_signal		= False
	final_short_signal		= False
	final_buy_to_cover_signal	= False

	exit_percent_signal_long	= False
	exit_percent_signal_short	= False

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

	trin_init_signal		= False
	trin_signal			= False
	trin_counter			= 0

	tick_signal			= False
	roc_signal			= False

	sp_monitor_init_signal		= False
	sp_monitor_signal		= False

	vix_signal			= False

	ts_monitor_signal		= False

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
	bbands_roc_counter		= 0
	bbands_kchan_init_signal	= False
	bbands_kchan_crossover_signal	= False
	bbands_kchan_signal		= False
	bbands_roc_threshold_signal	= False

	stacked_ma_signal		= False
	mama_fama_signal		= False
	mesa_sine_signal		= False

	bbands_natr			= { 'bbands': [], 'natr': 0, 'squeeze_natr': 0 }

	rs_signal			= False

	momentum_signal			= False

	plus_di_crossover		= False
	minus_di_crossover		= False
	macd_crossover			= False
	macd_avg_crossover		= False

	near_keylevel			= False
	experimental_signal		= False

	default_incr_threshold		= incr_threshold
	default_decr_threshold		= decr_threshold
	incr_threshold_long		= incr_threshold
	incr_threshold_short		= incr_threshold
	decr_threshold_long		= decr_threshold
	decr_threshold_short		= decr_threshold

	orig_stock_usd			= stock_usd
	orig_incr_threshold_long	= incr_threshold
	orig_incr_threshold_short	= incr_threshold
	orig_decr_threshold_long	= decr_threshold
	orig_decr_threshold_short	= decr_threshold

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

	# Signal mode dictionary contains information about the mode the bot is in
	signal_mode = {
			'primary':	'long',
			'secondary':	None,
			'straddle':	False
	}
	if ( shortonly == True ):
		signal_mode['primary'] = 'short'


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


	# Check orientation of stacked moving averages
	def check_stacked_ma(s_ma=[], affinity=None):

		if ( affinity == None or len(s_ma) == 0 ):
			return False

		# Round the moving average values to three decimal places
		s_ma = list(s_ma)
		for i in range(0, len(s_ma)):
			s_ma[i] = round( s_ma[i], 3 )

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
	def bbands_kchannels(pricehistory=None, simple=False, cur_bbands=(0,0,0), prev_bbands=(0,0,0), cur_kchannel=(0,0,0), prev_kchannel=(0,0,0), bbands_roc=None,
				bbands_kchan_init_signal=False, bbands_roc_threshold_signal=False, bbands_kchan_crossover_signal=False, bbands_kchan_signal=False, debug=False ):

		nonlocal bbands_kchannel_offset
		nonlocal bbands_kchannel_offset_debug
		nonlocal bbands_kchan_signal_counter
		nonlocal bbands_kchan_xover_counter
		nonlocal bbands_kchan_crossover_only
		nonlocal bbands_kchan_x1_xover

		nonlocal bbands_roc_threshold
		nonlocal bbands_roc_strict
		nonlocal bbands_roc_count
		nonlocal bbands_roc_counter
		nonlocal signal_mode
		nonlocal cur_rsi_k

		nonlocal idx
		nonlocal max_squeeze_natr
		nonlocal bbands_natr
		nonlocal max_bbands_natr
		nonlocal min_bbands_natr

		nonlocal bbands_kchan_ma

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

			return bbands_kchan_init_signal, bbands_roc_threshold_signal, bbands_kchan_crossover_signal, bbands_kchan_signal

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
			bbands_roc_threshold_signal	= False
			bbands_kchan_signal_counter	= 0
			bbands_kchan_xover_counter	= 0
			bbands_roc_counter		= 0

			return bbands_kchan_init_signal, bbands_roc_threshold_signal, bbands_kchan_crossover_signal, bbands_kchan_signal

		# Check if the Bollinger Bands have moved inside the Keltner Channel
		# Signal when they begin to converge
		if ( cur_kchannel_lower < cur_bbands_lower or cur_kchannel_upper > cur_bbands_upper ):

			# bbands_natr['bbands'] contains the difference between the upper and lower bands
			if ( bbands_kchan_signal_counter == 0 ):
				bbands_natr['natr']		= 0
				bbands_natr['squeeze_natr']	= 0
				bbands_natr['bbands']		= [cur_bbands_upper - cur_bbands_lower]
			else:
				bbands_natr['bbands'].append(cur_bbands_upper - cur_bbands_lower)

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
			if ( bbands_kchan_signal_counter >= bbands_kchan_squeeze_count and cur_offset >= bbands_kchannel_offset ):

				if ( bbands_kchan_x1_xover == True ):
					# Require bbands crossover into the kchannel with ATR multiplier == 1
					nonlocal kchannel_lower_x1
					nonlocal kchannel_mid_x1
					nonlocal kchannel_upper_x1

					cur_kchannel_lower_x1	= round( kchannel_lower_x1[idx], 3 )
					cur_kchannel_mid_x1	= round( kchannel_mid_x1[idx], 3 )
					cur_kchannel_upper_x1	= round( kchannel_upper_x1[idx], 3 )

					if ( cur_kchannel_lower_x1 < cur_bbands_lower or cur_kchannel_upper_x1 > cur_bbands_upper ):
						bbands_kchan_init_signal = True

				else:
					bbands_kchan_init_signal = True

				if ( debug == True ):
					bbands_kchannel_offset_debug['cur_squeeze'].append(cur_offset)

		# Toggle the bbands_kchan_signal when the bollinger bands pop back outside the keltner channel
		if ( bbands_kchan_init_signal == True ):

			# An aggressive strategy is to try to get in early when the Bollinger bands begin to widen
			#  and before they pop out of the Keltner channel
			prev_offset	= abs((prev_kchannel_lower / prev_bbands_lower) - 1) * 100
			cur_offset	= abs((cur_kchannel_lower / cur_bbands_lower) - 1) * 100

			# Monitor the rate-of-change of the bbands to detect a breakout before the crossover happens
			if ( bbands_kchan_crossover_only == False and bbands_kchan_crossover_signal == False and cur_offset < prev_offset ):
				if ( bbands_roc != None and cur_bbands_upper > prev_bbands_upper and bbands_roc[idx] > bbands_roc[idx-1] ):
					roc_pct = abs(((bbands_roc[idx] - bbands_roc[idx-1]) / bbands_roc[idx-1]) * 100)

					# Counter for use with bbands_roc_strict
					if ( roc_pct >= 15 ):
						bbands_roc_counter += 1

					# Check bbands_roc_threshold and set bbands_roc_threshold_signal
					# Backtesting shows a greater success rate if used with a modest stochrsi check
					if ( bbands_roc_threshold > 0 and roc_pct >= bbands_roc_threshold ):
						bbands_roc_threshold_signal = True

				if ( bbands_roc_threshold_signal == True and
						((signal_mode['primary'] == 'long' and cur_rsi_k < 40) or
						 (signal_mode['primary'] == 'short' and cur_rsi_k > 60)) ):

					bbands_kchan_signal = True

			# Reset bbands_roc_counter and bbands_roc_threshold_signal if crossover has not yet happened and
			#  the bbands start to move back away from the Keltner channel
			if ( bbands_kchan_signal == False and cur_offset > prev_offset ):
				bbands_roc_threshold_signal	= False
				bbands_roc_counter		= 0

			# Trigger bbands_kchan_signal is the bbands/kchannel offset is narrowing to a point where crossover is emminent.
			# Unless bbands_roc_strict is True, in which case a stronger change in the bbands rate-of-change is needed to
			#  allow the bbands_kchan_signal to trigger.
			if ( bbands_kchan_crossover_only == False and cur_offset < prev_offset and cur_offset <= bbands_kchannel_offset / 4 ):
				if ( bbands_roc_strict == False or (bbands_roc_strict == True and bbands_roc_counter >= bbands_roc_count) ):
					bbands_kchan_signal = True
					bbands_kchan_crossover_signal = True

			# Check for crossover
			if ( (prev_kchannel_lower <= prev_bbands_lower and cur_kchannel_lower > cur_bbands_lower) or
					(prev_kchannel_upper >= prev_bbands_upper and cur_kchannel_upper < cur_bbands_upper) ):
				bbands_kchan_crossover_signal = True

				if ( bbands_roc_strict == False or (bbands_roc_strict == True and bbands_roc_counter >= bbands_roc_count) ):
					bbands_kchan_signal = True

			if ( bbands_kchan_crossover_signal == True ):
				bbands_kchan_xover_counter += 1

			if ( debug == True ):
				if ( len(bbands_kchannel_offset_debug['cur_squeeze']) > 0 ):
					bbands_kchannel_offset_debug['squeeze'].append( max(bbands_kchannel_offset_debug['cur_squeeze']) )
					bbands_kchannel_offset_debug['cur_squeeze'] = []

			# The NATR of the bbands_natr['bbands'] will help tell us how much volatility there
			#  has been between the upper and lower Bollinger Bands during the squeeze.
			if ( bbands_kchan_signal == True ):
				cndl_slice = { 'candles': [] }
				for i in range(len(bbands_natr['bbands']), 0, -1):
					cndl_slice['candles'].append( {'open': bbands_natr['bbands'][-i], 'high': bbands_natr['bbands'][-i], 'low': bbands_natr['bbands'][-i], 'close': bbands_natr['bbands'][-i] } )

				try:
					atr_t, natr_t = tda_algo_helper.get_atr( cndl_slice, period=len(bbands_natr['bbands']) )

				except Exception as e:
					print('Caught exception: bbands_kchannels(): get_atr(): error calculating NATR: ' + str(e))
					bbands_kchan_signal = False

				else:
					bbands_natr['natr'] = natr_t[-1]

				if ( max_bbands_natr != None and bbands_natr['natr'] > max_bbands_natr ):
					bbands_kchan_signal = False
				elif ( min_bbands_natr != None and bbands_natr['natr'] < min_bbands_natr ):
					bbands_kchan_signal = False

			# If max_squeeze_natr is set, make sure the recent NATR is not too high to disqualify
			#  this stock movement as a good consolidation.
			if ( bbands_kchan_signal == True and pricehistory != None ):

				cndl_slice = { 'candles': [] }
				for i in range(bbands_kchan_signal_counter+2, 0, -1):
					cndl_slice['candles'].append( pricehistory['candles'][idx-i] )

				try:
					atr_t, natr_t = tda_algo_helper.get_atr( pricehistory=cndl_slice, period=bbands_kchan_signal_counter )

				except Exception as e:
					print('Caught exception: bbands_kchannels(): get_atr(): error calculating NATR: ' + str(e))
					bbands_kchan_signal = False

				else:
					bbands_natr['squeeze_natr'] = natr_t[-1]

				if ( max_squeeze_natr != None and natr_t[-1] > max_squeeze_natr ):
					bbands_kchan_signal = False


			# Check the closing candles in relation to the EMA 21
			# On a long signal, count the number of times the closing price has dipped below
			#  the EMA 21 value. On a short signal, count the number of times the closing price has gone above
			#  the EMA 21 value. If this happens multiple times over the course of a squeeze it indicates
			#  that this is less likely to succeed, so we cancel the bbands_kchan_signal.
			if ( bbands_kchan_signal == True and bbands_kchan_ma_check == True ):
				ema_count = 0
				for i in range(bbands_kchan_signal_counter):
					if ( signal_mode['primary'] == 'long' and pricehistory['candles'][idx-i]['close'] < bbands_kchan_ma[idx-i] ):
						ema_count += 1

					elif ( signal_mode['primary'] == 'short' and pricehistory['candles'][idx-i]['close'] > bbands_kchan_ma[idx-i] ):
						ema_count += 1

					if ( ema_count > 2 ):
						bbands_kchan_init_signal	= False
						bbands_kchan_signal		= False
						break

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
				bbands_roc_threshold_signal	= False
				bbands_kchan_signal_counter	= 0
				bbands_kchan_xover_counter	= 0
				bbands_roc_counter		= 0

		return bbands_kchan_init_signal, bbands_roc_threshold_signal, bbands_kchan_crossover_signal, bbands_kchan_signal


	# MESA Sine Wave
	def mesa_sine(sine=[], lead=[], direction=None, mesa_exit=False, strict=False, mesa_sine_signal=False):

		nonlocal idx

		cur_sine	= sine[idx]
		prev_sine	= sine[idx-1]
		cur_lead	= lead[idx]
		prev_lead	= lead[idx-1]

		midline		= 0
		min_high_limit	= 0.9
		min_low_limit	= -0.9

		# Long signal
		if ( direction == 'long' and cur_sine < midline ):
			return False

		elif ( direction == 'long' and (prev_sine <= prev_lead and cur_sine > cur_lead) ):
			if ( mesa_exit == True ):
				mesa_sine_signal = True
			else:
				if ( cur_sine > min_high_limit ):
					mesa_sine_signal = True

		# Short signal
		elif ( direction == 'short' and cur_sine > midline ):
			return False

		elif ( direction == 'short' and (prev_sine >= prev_lead and cur_sine < cur_lead) ):
			if ( mesa_exit == True ):
				mesa_sine_signal = True

			else:
				if ( cur_sine < min_low_limit ):
					mesa_sine_signal = True

		# No need to check history if signal is already False
		if ( mesa_sine_signal == False or strict == False ):
			return mesa_sine_signal

		# Analyze trendiness
		# Check for crossovers
		xover_count	= 0
		xover		= []
		for i in range( idx-1, -1, -1 ):

			# Find the last few idx points that crossed over the midline
			if ( (sine[i+1] > midline and sine[i] < midline) or
					(sine[i+1] < midline and sine[i] > midline) ):
				xover.append(i)

			if ( len(xover) >= 4 ):
				break

		if ( len(xover) >= 2 ):

			# Check the last two entries in xover[] and see if there was a crossover
			#  between sine and lead. If not then the stock is probably trending.
			for i in range( xover[-1]-1, xover[-2]+2, 1 ):
				cur_sine	= sine[i]
				prev_sine	= sine[i-1]
				cur_lead	= lead[i]
				prev_lead	= lead[i-1]

				if ( (prev_sine < prev_lead and cur_sine > cur_lead) or
					(prev_sine > prev_lead and cur_sine < cur_lead) ):
					xover_count += 1

			if ( xover_count == 0 ):
				mesa_sine_signal = False

		# Find the rate of change for the last few candles
		# Flatter sine/lead waves indicate trending
		sine_ph = { 'candles': [] }
		for i in range( 10 ):
			sine_ph['candles'].append( { 'close': sine[idx-i] } )
		sine_roc = tda_algo_helper.get_roc( sine_ph, period=9, type='close' )

		if ( abs(sine_roc[-1]) * 100 < 170 ):
			mesa_sine_signal = False

		return mesa_sine_signal


	# Return trend/cycle affinity based on EMD values
	#  cur_emd = ( cur_trend, cur_peak, cur_valley)
	def get_mesa_emd(cur_emd=(0,0,0), prev_emd=(0,0,0)):

		cur_trend	= cur_emd[0]
		prev_trend	= prev_emd[0]

		cur_peak	= cur_emd[1]
		prev_peak	= prev_emd[1]

		cur_valley	= cur_emd[2]
		prev_valley	= prev_emd[2]

		# If the trend is above the upper threshold the market is in an uptrend.
		# If the trend is below the lower threshold the market is in a downtrend.
		# When the trend falls between the two threshold levels the market is in a cycle mode.
		if ( cur_trend > cur_peak ):
			return 1
		elif ( cur_trend < cur_valley ):
			return -1
		elif ( cur_trend < cur_peak and cur_trend > cur_valley ):
			return 0
		else:
			print('Warning: get_mesa_emd(): Bad trendline: ' + str(cur_trend) + ' / ' + str(cur_peak) + ' / ' + str(cur_valley) )
			return -99


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

			assert idx - adx_idx >= 0
			assert idx - di_idx >= 1

			if ( with_macd == True or with_macd_simple == True):
				assert idx - macd_idx >= 1
				assert idx - aroonosc_idx >= 0

		except:
			continue

		# Helper variables from the current pricehistory data
		cur_open			= pricehistory['candles'][idx]['open']
		cur_high			= pricehistory['candles'][idx]['high']
		cur_low				= pricehistory['candles'][idx]['low']
		cur_close			= pricehistory['candles'][idx]['close']
		cur_volume			= pricehistory['candles'][idx]['volume']

		cur_dt				= pricehistory['candles'][idx]['datetime']
		prev_dt				= pricehistory['candles'][idx-1]['datetime']

		cur_ha_open			= pricehistory['hacandles'][idx]['open']
		cur_ha_high			= pricehistory['hacandles'][idx]['high']
		cur_ha_low			= pricehistory['hacandles'][idx]['low']
		cur_ha_close			= pricehistory['hacandles'][idx]['close']

		date				= datetime.fromtimestamp(int(cur_dt)/1000, tz=mytimezone)

		# Indicators current values
		cur_rsi_k			= rsi_k[idx - stochrsi_idx]
		prev_rsi_k			= rsi_k[idx - stochrsi_idx - 1]
		cur_rsi_d			= rsi_d[idx - stochrsi_idx]
		prev_rsi_d			= rsi_d[idx - stochrsi_idx - 1]

		if ( with_stoch_5m == True ):
			cur_rsi_k		= rsi_k[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_k		= rsi_k[int((idx - stochrsi_5m_idx) / 5) - 1]
			cur_rsi_d		= rsi_d[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_d		= rsi_d[int((idx - stochrsi_5m_idx) / 5) - 1]

		if ( with_stochrsi_5m == True ):
			cur_rsi_k_5m		= rsi_k_5m[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_k_5m		= rsi_k_5m[int((idx - stochrsi_5m_idx) / 5) - 1]
			cur_rsi_d_5m		= rsi_d_5m[int((idx - stochrsi_5m_idx) / 5)]
			prev_rsi_d_5m		= rsi_d_5m[int((idx - stochrsi_5m_idx) / 5) - 1]

		cur_mfi_k = cur_mfi_d = 0 # Needed for the ledger
		if ( with_stochmfi == True ):
			cur_mfi_k		= mfi_k[idx - stochmfi_idx]
			prev_mfi_k		= mfi_k[idx - stochmfi_idx - 1]
			cur_mfi_d		= mfi_d[idx - stochmfi_idx]
			prev_mfi_d		= mfi_d[idx - stochmfi_idx - 1]

		if ( with_stochmfi_5m == True ):
			cur_mfi_k_5m		= mfi_k_5m[int((idx - stochmfi_5m_idx) / 5)]
			prev_mfi_k_5m		= mfi_k_5m[int((idx - stochmfi_5m_idx) / 5) - 1]
			cur_mfi_d_5m		= mfi_d_5m[int((idx - stochmfi_5m_idx) / 5)]
			prev_mfi_d_5m		= mfi_d_5m[int((idx - stochmfi_5m_idx) / 5) -1]

		if ( with_stacked_ma == True ):
			cur_s_ma		= s_ma[idx]
			prev_s_ma		= s_ma[idx-1]
			cur_s_ma_ha		= s_ma_ha[idx]
			prev_s_ma_ha		= s_ma_ha[idx-1]

			if ( use_ha_candles == True ):
				cur_s_ma		= cur_s_ma_ha
				prev_s_ma		= prev_s_ma_ha

			if ( with_stacked_ma_secondary == True ):
				cur_s_ma_secondary	= s_ma_secondary[idx]
				prev_s_ma_secondary	= s_ma_secondary[idx-1]
				cur_s_ma_ha_secondary	= s_ma_ha_secondary[idx]
				prev_s_ma_ha_secondary	= s_ma_ha_secondary[idx-1]

				if ( use_ha_candles == True ):
					cur_s_ma_secondary	= cur_s_ma_ha_secondary
					prev_s_ma_secondary	= prev_s_ma_ha_secondary

		if ( primary_stoch_indicator == 'stacked_ma' ):
			cur_s_ma_primary	= s_ma_primary[idx]
			prev_s_ma_primary	= s_ma_primary[idx-1]
			cur_s_ma_ha_primary	= s_ma_ha_primary[idx]
			prev_s_ma_ha_primary	= s_ma_ha_primary[idx-1]

		if ( primary_stoch_indicator == 'mama_fama' or with_mama_fama == True ):
			cur_mama		= mama[idx]
			cur_fama		= fama[idx]
			prev_mama		= mama[idx-1]
			prev_fama		= fama[idx-1]

		if ( primary_stoch_indicator == 'trin' or with_trin == True ):
			try:
				cur_trin	= trin_tick['trin']['roc_ma'][cur_dt]
				prev_trin	= trin_tick['trin']['roc_ma'][prev_dt]

			except:
				cur_trin	= 0
				prev_trin	= 0

		if ( with_tick == True ):
			try:
				cur_tick	= trin_tick['tick']['roc_ma'][cur_dt]
				prev_tick	= trin_tick['tick']['roc_ma'][prev_dt]

			except:
				cur_tick	= 0
				prev_tick	= 0

		if ( with_roc == True or default_roc_exit == True ):
			cur_roc		= roc[idx]
			prev_roc	= roc[idx-1]
			cur_roc_ma	= roc_ma[idx]
			prev_roc_ma	= roc_ma[idx-1]

		cur_sp_monitor_impulse = 0
		if ( with_sp_monitor == True or primary_stoch_indicator == 'sp_monitor' ):
			try:
				cur_sp_monitor			= sp_monitor['roc_ma'][cur_dt]
				prev_sp_monitor			= sp_monitor['roc_ma'][prev_dt]

				cur_sp_monitor_impulse		= sp_monitor['roc_roc'][cur_dt]
				prev_sp_monitor_impulse		= sp_monitor['roc_roc'][prev_dt]

				if ( sp_monitor_use_trix == True ):
					cur_sp_monitor_trix		= sp_monitor['trix'][cur_dt]
					prev_sp_monitor_trix		= sp_monitor['trix'][prev_dt]

					cur_sp_monitor_trix_signal	= sp_monitor['trix_signal'][cur_dt]
					prev_sp_monitor_trix_signal	= sp_monitor['trix_signal'][prev_dt]

				else:
					cur_sp_monitor_stacked_ma	= sp_monitor['stacked_ma'][cur_dt]

			except:
				cur_sp_monitor			= 0
				prev_sp_monitor			= 0

				cur_sp_monitor_impulse		= 0
				prev_sp_monitor_impulse		= 0

				cur_sp_monitor_trix		= 0
				prev_sp_monitor_trix		= 0

				cur_sp_monitor_trix_signal	= 0
				prev_sp_monitor_trix_signal	= 0

				cur_sp_monitor_stacked_ma	= (0,0,0)

		if ( with_vix == True ):
			try:
				cur_vix_ma	= vix['ma'][cur_dt]
				prev_vix_ma	= vix['ma'][prev_dt]
			except:
				cur_vix_ma	= (0,0,0)
				prev_vix_ma	= (0,0,0)

		if ( trend_quick_exit == True ):
			cur_qe_s_ma		= qe_s_ma[idx]
			prev_qe_s_ma		= qe_s_ma[idx-1]

		if ( with_momentum == True ):
			cur_mom			= mom[idx]
			prev_mom		= mom[idx-1]
			cur_mom_roc		= mom_roc[idx]

			cur_trix		= trix[idx]
			prev_trix		= trix[idx-1]
			cur_trix_signal		= trix_signal[idx]

		if ( with_rsi == True or with_rsi_simple == True ):
			cur_rsi			= rsi[idx - rsi_idx]
			prev_rsi		= rsi[idx - rsi_idx - 1]

		if ( with_mfi == True or with_mfi_simple == True ):
			cur_mfi			= mfi[idx - mfi_idx]
			prev_mfi		= mfi[idx - mfi_idx - 1]

		if ( with_macd == True or with_macd_simple == True or aroonosc_with_macd_simple == True ):
			cur_macd		= macd[idx - macd_idx]
			prev_macd		= macd[idx - macd_idx - 1]
			cur_macd_avg		= macd_avg[idx - macd_idx]
			prev_macd_avg		= macd_avg[idx - macd_idx - 1]

		if ( with_aroonosc == True or with_aroonosc_simple == True ):
			cur_aroonosc		= aroonosc[idx - aroonosc_idx]
			prev_aroonosc		= aroonosc[idx - aroonosc_idx - 1]
			cur_aroonosc_alt	= aroonosc_alt[idx - aroonosc_alt_idx]
			prev_aroonosc_alt	= aroonosc_alt[idx - aroonosc_alt_idx - 1]

		if ( with_vpt == True ):
			cur_vpt			= vpt[idx]
			prev_vpt		= vpt[idx-1]
			cur_vpt_sma		= vpt_sma[idx - vpt_sma_period]
			prev_vpt_sma		= vpt_sma[idx - vpt_sma_period]

		if ( with_chop_index == True or with_chop_simple == True ):
			cur_chop		= chop[idx - chop_idx]
			prev_chop		= chop[idx - chop_idx - 1]

		cur_adx				= adx[idx - adx_idx]
		prev_adx			= adx[idx - adx_idx - 1]

		cur_di_adx			= di_adx[idx - di_adx_idx]
		prev_di_adx			= di_adx[idx - di_adx_idx - 1]
		cur_plus_di			= plus_di[idx - di_idx]
		prev_plus_di			= plus_di[idx - di_idx - 1]
		cur_minus_di			= minus_di[idx - di_idx]
		prev_minus_di			= minus_di[idx - di_idx - 1]

		cur_atr				= atr[int(idx / 5) - atr_period]
		cur_natr			= natr[int(idx / 5) - atr_period]

		cur_rs				= -1 # RelStrength

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

		# Set price_resistance_pct/price_support_pct dynamically
		if ( resist_pct_dynamic == True ):
			price_resistance_pct = (1 / cur_close) * 100
			if ( price_resistance_pct < 0.25 ):
				price_resistance_pct = 0.25
			elif ( price_resistance_pct > 1 ):
				price_resistance_pct = 1

			price_support_pct = price_resistance_pct

		# Skip all candles until start_date, if it is set
		if ( start_date != None and date < start_date ):
			continue
		elif ( stop_date != None and date >= stop_date ):
			return results

		# If time and sales algo monitor is enabled, then only
		#  process days for which we have ts data available
		if ( time_sales_algo == True ):
			if ( date.strftime('%Y-%m-%d') not in ts_days ):
				continue

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

		# If ph_only is set then only trade during high-volume periods
		#  9:30AM - 11:00AM
		#  3:30PM - 4:00PM
		if ( ph_only == True and (signal_mode['primary'] == 'long' or signal_mode['primary'] == 'short') ):
			cur_hour	= int( date.strftime('%-H') )
			cur_min		= int( date.strftime('%-M') )

			if ( cur_hour >= 11 and cur_hour < 14 ):
				continue
			elif ( cur_hour == 10 and cur_min > 30 ):
				continue
			elif ( cur_hour == 14 and cur_min < 30 ):
				continue

		# Ignore days where cur_daily_natr is below min_daily_natr or above max_daily_natr, if configured
		if ( min_daily_natr != None and cur_natr_daily < min_daily_natr ):
			continue
		if ( max_daily_natr != None and cur_natr_daily > max_daily_natr ):
			continue


		# BUY mode
		if ( signal_mode['primary'] == 'long' ):

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and ph_only == False and safe_open == True and
					tda_gobot_helper.isendofday(75, date) == True ):
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
				  bbands_roc_threshold_signal,
				  bbands_kchan_crossover_signal,
				  bbands_kchan_signal ) = bbands_kchannels( pricehistory=pricehistory, simple=with_bbands_kchannel_simple,
										cur_bbands=cur_bbands, prev_bbands=prev_bbands,
										cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
										bbands_kchan_init_signal=bbands_kchan_init_signal,
										bbands_roc_threshold_signal=bbands_roc_threshold_signal,
										bbands_kchan_crossover_signal=bbands_kchan_crossover_signal,
										bbands_kchan_signal=bbands_kchan_signal,
										bbands_roc=bbands_roc, debug=False )


			# StochRSI / StochMFI Primary
			if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
				# Jump to short mode if StochRSI K and D are already above rsi_high_limit
				# The intent here is if the bot starts up while the RSI is high we don't want to wait until the stock
				#  does a full loop again before acting on it.
				if ( cur_rsi_k >= stochrsi_default_high_limit and cur_rsi_d >= stochrsi_default_high_limit and noshort == False ):
					reset_signals()
					if ( noshort == False ):
						signal_mode['primary'] = 'short'
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

					# Note (period, -1, -1) makes sense here because we want idx-0 (the most recent candle) to be
					#  counted as well. This is different from the live bot which reads range(period+1, 0, -1),
					#  because live we will reference ph['candles'][-i] (where -1 is the latest candle).
					for i in range(period, -1, -1):
						cndl_slice.append( pricehistory['candles'][idx-i] )

					price_trend_bear_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bear')
					price_trend_bull_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bull')

				# Jump to short mode if the stacked moving averages are showing a bearish movement
				if ( (use_ha_candles == True and (stacked_ma_bear_ha_affinity == True or stacked_ma_bear_affinity == True)) or
					(use_trend == True and price_trend_bear_affinity == True) or
					(use_ha_candles == False and use_trend == False and stacked_ma_bear_affinity == True) ):

					reset_signals( exclude_bbands_kchan=True )
					if ( noshort == False ):
						signal_mode['primary'] = 'short'
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
						signal_mode['primary'] = 'short'
					continue

				if ( cur_aroonosc > 60 ):
					buy_signal = True
				else:
					reset_signals()
					continue

			# MESA Adaptive Moving Average primary
			elif ( primary_stoch_indicator == 'mama_fama' ):
				if ( mama_require_xover == True ):
					prev_prev_mama = mama[-2]
					prev_prev_fama = fama[-2]

					# Check if a crossover happened recently, which would have
					#  switched us from short->long mode
					if ( prev_prev_mama <= prev_prev_fama and cur_mama > cur_fama ):
						buy_signal = True

					# Price crossed over from bullish to bearish
					elif ( cur_mama <= cur_fama ):
						reset_signals( exclude_bbands_kchan=True )
						if ( noshort == False ):
							signal_mode['primary'] = 'short'
						continue

				else:
					# If crossover is not required then just check the orientation of
					#  mama and fama
					buy_signal = False

					# Bullish trending
					if ( cur_mama > cur_fama ):
						buy_signal = True

					# Price crossed over from bullish to bearish
					elif ( cur_mama <= cur_fama or (prev_mama > prev_fama and cur_mama <= cur_fama) ):
						reset_signals( exclude_bbands_kchan=True )
						if ( noshort == False ):
							signal_mode['primary'] = 'short'
						continue

					else:
						# This shouldn't happen, but just in case...
						buy_signal = False

			# MESA Sine Wave
			elif ( primary_stoch_indicator == 'mesa_sine' ):
				cur_sine = sine[idx]
				midline	 = 0

				if ( cur_sine < midline ):
					reset_signals( exclude_bbands_kchan=True )
					if ( noshort == False ):
						signal_mode['primary'] = 'short'
					continue

				buy_signal = mesa_sine( sine=sine, lead=lead, direction='long', strict=mesa_sine_strict, mesa_sine_signal=buy_signal )

			# $TRIN primary indicator
			#  - Higher values (>= 3) indicate bearish trend
			#  - Lower values (<= -1) indicate bullish trend
			#  - A simple algorithm here watches for higher values above 3, which
			#    indicate that a bearish trend is ongoing but may be approaching oversold
			#    levels. We then watche for a green candle to form, which will trigger the
			#    final signal.
			#  - Alone this is pretty simplistic, but supplimental indicators (roc, tick, etc.)
			#    can help confirm that a reversal is happening.
			elif ( primary_stoch_indicator == 'trin' ):

				# Jump to short mode if cur_trin is less than 0
				if ( cur_trin <= trin_overbought and noshort == False ):
					reset_signals()
					trin_init_signal	= True
					signal_mode['primary']	= 'short'
					continue

				# Trigger trin_init_signal if cur_trin moves above trin_oversold
				if ( cur_trin >= trin_oversold ):
					trin_counter		= 0
					trin_init_signal	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first green candle
				if ( trin_init_signal == True ):
					if ( cur_ha_close > cur_ha_open ):
						trin_signal	= True
					else:
						trin_signal	= False
						buy_signal	= False

					trin_counter += 1
					if ( trin_counter >= 10 ):
						trin_counter		= 0
						trin_init_signal	= False

				# Trigger the buy_signal if all the trin signals have tiggered
				if ( trin_init_signal == True and trin_signal == True ):
					buy_signal = True

			# ETF SP primary indicator
			elif ( primary_stoch_indicator == 'sp_monitor' ):

				# Use either stacked_ma or trix to help verify sp_monitor direction
				sp_monitor_bull = sp_monitor_bear = False
				if ( sp_monitor_use_trix == True ):
					if ( cur_sp_monitor_trix > prev_sp_monitor_trix and cur_sp_monitor_trix > 0 and
							cur_sp_monitor_trix > cur_sp_monitor_trix_signal ):
						sp_monitor_bull = True
						sp_monitor_bear = False

					elif ( cur_sp_monitor_trix < prev_sp_monitor_trix and cur_sp_monitor_trix < 0 and
							cur_sp_monitor_trix < cur_sp_monitor_trix_signal ):
						sp_monitor_bull = False
						sp_monitor_bear = True

				else:
					sp_monitor_bear	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bear')
					sp_monitor_bull	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bull')

				# Jump to short mode if sp_monitor is negative
				if ( cur_sp_monitor < 0 ):
					reset_signals()
					signal_mode['primary'] = 'short'

					if ( cur_sp_monitor <= -1.5 ):
						sp_monitor_init_signal = True

					elif ( cur_sp_monitor <= -sp_monitor_threshold ):
						if ( (sp_monitor_strict == True and sp_monitor_bear == True) or sp_monitor_strict == False ):
							short_signal = True

					continue

				elif ( cur_sp_monitor > 1.5 and cur_sp_monitor < sp_monitor_threshold ):
					sp_monitor_init_signal = True

#				elif ( cur_sp_monitor >= sp_monitor_threshold and sp_monitor_init_signal == True ):
				elif ( cur_sp_monitor >= sp_monitor_threshold ):
					if ( (sp_monitor_strict == True and sp_monitor_bull == True) or sp_monitor_strict == False ):
						sp_monitor_init_signal	= False
						buy_signal		= True

				# Reset signals if sp_monitor starts to fade
				if ( cur_sp_monitor < sp_monitor_threshold or (sp_monitor_strict == True and sp_monitor_bull == False) ):
					buy_signal = False
				if ( cur_sp_monitor < 1.5 ):
					sp_monitor_init_signal = False

			# Unknown primary indicator
			else:
				print('Error: primary_stoch_indicator "' + str(primary_stoch_indicator) + '" unknown, exiting.')
				return False

			##
			# Secondary Indicators
			##

			# $TRIN indicator
			if ( with_trin == True ):
				if ( cur_trin <= trin_overbought ):
					trin_init_signal = False

				# Trigger trin_init_signal if cur_trin moves above trin_oversold
				elif ( cur_trin >= trin_oversold ):
					trin_counter		= 0
					trin_init_signal	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first green candle
				if ( trin_init_signal == True ):
					if ( cur_ha_close > cur_ha_open ):
						trin_signal = True
					else:
						trin_signal = False

					trin_counter += 1
					if ( trin_counter >= 10 ):
						trin_counter		= 0
						trin_init_signal	= False

			# $TICK indicator
			# Bearish action when indicator is below zero and heading downward
			# Bullish action when indicator is above zero and heading upward
			if ( with_tick == True ):
				tick_signal = False
				if ( cur_tick > prev_tick and cur_tick > tick_threshold ):
					tick_signal = True

			# Rate-of-Change (ROC) indicator
			if ( with_roc == True ):
				#roc_signal = False
				if ( cur_roc_ma > 0 and cur_roc_ma > prev_roc_ma ):
					roc_signal = True
				if ( cur_roc_ma <= roc_threshold ):
					roc_signal = False

			# ETF SP indicator
			if ( with_sp_monitor == True ):

				# Use either stacked_ma or trix to help verify sp_monitor direction
				sp_monitor_bull = sp_monitor_bear = False
				if ( sp_monitor_use_trix == True ):
					if ( cur_sp_monitor_trix > prev_sp_monitor_trix and cur_sp_monitor_trix > 0 and
							cur_sp_monitor_trix > cur_sp_monitor_trix_signal ):
						sp_monitor_bull = True
						sp_monitor_bear = False

					elif ( cur_sp_monitor_trix < prev_sp_monitor_trix and cur_sp_monitor_trix < 0 and
							cur_sp_monitor_trix < cur_sp_monitor_trix_signal ):
						sp_monitor_bull = False
						sp_monitor_bear = True

				else:
					sp_monitor_bear	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bear')
					sp_monitor_bull	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bull')

				if ( cur_sp_monitor < 0 ):
					sp_monitor_init_signal	= False
					sp_monitor_signal	= False

				elif ( cur_sp_monitor > 1.5 and cur_sp_monitor < sp_monitor_threshold ):
					sp_monitor_init_signal = True

				elif ( cur_sp_monitor >= sp_monitor_threshold ):
					if ( (sp_monitor_strict == True and sp_monitor_bull == True) or sp_monitor_strict == False ):
						sp_monitor_init_signal	= False
						sp_monitor_signal	= True

				# Reset signals if sp_monitor starts to fade
				if ( cur_sp_monitor < sp_monitor_threshold or (sp_monitor_strict == True and sp_monitor_bull == False) ):
					sp_monitor_signal = False
				if ( cur_sp_monitor < 1.5 ):
					sp_monitor_init_signal = False

			# VIX stacked MA
			# The SP 500 and the VIX often show inverse price action - when the S&P falls sharply, the VIX rises—and vice-versa
			if ( with_vix == True ):
				vix_stacked_ma_bull_affinity = check_stacked_ma(cur_vix_ma, 'bull')
				vix_stacked_ma_bear_affinity = check_stacked_ma(cur_vix_ma, 'bear')

				# Decrease in VIX typically means bullish for SP500
				vix_signal = False
				if ( vix_stacked_ma_bear_affinity == True ):
					vix_signal = True

				elif ( (vix_stacked_ma_bull_affinity == False and vix_stacked_ma_bear_affinity == False) or
						vix_stacked_ma_bull_affinity == True ):
					vix_signal = False

			# Time and sales algo monitor
			if ( time_sales_algo == True ):
				cur_tstamp = date.strftime('%Y-%m-%d %H:%M')
				if ( cur_tstamp in ts_tx_data ):
					for key in ts_tx_data[cur_tstamp]['txs']:

						# ts_tx_data[t_stamp]['txs'].append( {	'size':		ts_data[dt]['size'],
						#					'price':	tmp_hl2,
						#					'at_bid':	ts_data[dt]['at_bid'],
						#					'at_ask':	ts_data[dt]['at_ask'] } )
						#
						# Large size values are larger institutions buying/selling.
						# Large size values with neat round numbers are typically persistent algos
						#  buying/selling at key absorption areas, which they will continue to do
						#  until they are done with their buy/sell actions.
						if ( re.search('.*00$', str(int(key['size']))) != None ):

							# Large neutral trades typically happen at absorption areas
							# Add these to long_resistance as we find them.
#							if ( time_sales_use_keylevel == True and key['at_bid'] == 0 and key['at_ask'] == 0 and
#									key['size'] >= time_sales_kl_size_threshold ):
#								long_resistance.append( (key['price'], cur_dt, 999) )
#								print( cur_tstamp + ' ' + str(key['price']) )

							# Persistent aggressive bearish action
							if ( key['at_bid'] == 1 and key['at_ask'] == 0 ):
								ts_monitor_signal = False

							# Persistent aggressive bullish action
							elif ( key['at_bid'] == 0 and key['at_ask'] == 1 ):
								ts_monitor_signal = True

					if ( ts_tx_data[cur_tstamp]['ts_cum_delta'] < 0 ):
						ts_monitor_signal = False

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

			# Stacked moving averages
			if ( with_stacked_ma == True ):
				stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma, 'bull')
				stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha, 'bull')

				if ( stacked_ma_bull_affinity == True ):
					stacked_ma_signal = True
				else:
					stacked_ma_signal = False

				# Secondary stacked MA doesn't have its own signal, but can turn off the stacked_ma_signal
				# The idea is to allow a secondary set of periods or MA types to confirm the signal
				if ( with_stacked_ma_secondary == True ):
					stacked_ma_secondary_bull_affinity	= check_stacked_ma(cur_s_ma_secondary, 'bull')
					stacked_ma_secondary_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_secondary, 'bull')

					if ( stacked_ma_secondary_bull_affinity == False ):
						stacked_ma_signal = False

			# MESA Adaptive Moving Average
			if ( with_mama_fama == True ):
				if ( mama_require_xover == True ):
					if ( prev_mama <= prev_fama and cur_mama > cur_fama ):
						mama_fama_signal = True

					elif ( cur_mama <= cur_fama ):
						mama_fama_signal = False

				else:
					mama_fama_signal = False

					# Bullish trending
					if ( cur_mama > cur_fama ):
						mama_fama_signal = True

					# Price crossed over from bullish to bearish
					elif ( cur_mama <= cur_fama ):
						mama_fama_signal = False

			# MESA Sine Wave
			if ( with_mesa_sine == True ):
				mesa_sine_signal = mesa_sine( sine=sine, lead=lead, direction='long', strict=mesa_sine_strict, mesa_sine_signal=mesa_sine_signal )

			# Momentum Indicator
			if ( with_momentum == True ):
				momentum_signal = False
				if ( momentum_use_trix == True ):
					if ( cur_trix > prev_trix and cur_trix > cur_trix_signal ):
						momentum_signal = True
				else:
					if ( cur_mom > prev_mom ):
						if ( cur_mom_roc > 0 ):
							momentum_signal = True

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
			if ( with_aroonosc_simple == True and cur_natr > aroonosc_alt_threshold ):
				cur_aroonosc = cur_aroonosc_alt
				prev_aroonosc = prev_aroonosc_alt

			if ( with_aroonosc == True or with_aroonosc_simple == True ):

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
			if ( with_macd == True or with_macd_simple == True or aroonosc_with_macd_simple == True ):
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
			if ( with_vpt == True ):
				if ( prev_vpt < prev_vpt_sma and cur_vpt > cur_vpt_sma ):
					vpt_signal = True

				# Cancel signal if VPT crosses back over
				elif ( cur_vpt < cur_vpt_sma ):
					vpt_signal = False

			# Choppiness Index
			if ( with_chop_index == True or with_chop_simple == True ):
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


			# SUPPORT / RESISTANCE LEVELS
			resistance_signal = True
			today = date.strftime('%Y-%m-%d')

			# PDC
			if ( use_pdc == True and buy_signal == True and resistance_signal == True ):
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
			if ( use_natr_resistance == True and buy_signal == True and resistance_signal == True ):
				prev_day_close = -1
				if ( today in day_stats ):
					prev_day_close = day_stats[today]['pdc']

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
			if ( use_vwap == True and buy_signal == True and resistance_signal == True ):
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
			# Skip this check for the first few hours of the day. The reason for this is
			#  the first hours of trading can create small hod/lods, but they often won't
			#  persist. Also, we are more concerned about the slow, low volume creeps toward
			#  HOD/LOD that are often permanent for the day.
			if ( lod_hod_check == True and buy_signal == True and resistance_signal == True ):

				# Check for current-day HOD after 1PM Eastern
				cur_hour = int( date.strftime('%-H') )
				if ( cur_hour >= 13 ):

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

				# If stock opened below PDH, then those can become additional resistance lines for long entry,
				# typically later in the day when volume decreases
				if ( today in day_stats ):
					if ( cur_hour >= 12 and day_stats[today]['open_idx'] != None ):
						if ( pricehistory['candles'][day_stats[today]['open_idx']]['open'] < day_stats[today]['pdh'] ):

							# Check PDH/PDL resistance
							avg = 0
							for i in range(15, 0, -1):
								avg += float( pricehistory['candles'][idx-i]['close'] )
								avg = avg / 15

							if ( avg < day_stats[today]['pdh'] and abs((cur_close / day_stats[today]['pdh'] - 1) * 100) <= price_resistance_pct ):
								resistance_signal = False

					# If stock has been sinking for a couple days, then oftentimes the 2-day previous day high will be long resistance,
					#  but also check pdh2_touch and pdh2_xover. If price has touched PDH2 multiple times and not crossed over more than
					#  1% then it's stronger resistance.
					if ( day_stats[today]['pdh'] < day_stats[today]['pdh2'] and day_stats[today]['pdc'] < day_stats[today]['pdh2'] and
						(day_stats[today]['open_idx'] != None and pricehistory['candles'][day_stats[today]['open_idx']]['open'] < day_stats[today]['pdh2']) ):

						if ( resistance_signal == True and
							abs((cur_high / day_stats[today]['pdh2'] - 1) * 100) <= price_resistance_pct ):

							# Count the number of times over the last two days where the price has touched
							#  PDH/PDL and failed to break through
							#
							# Walk through the 1-min candles for the previous two-days, but be sure to take
							#  into account after-hours trading two-days prior as PDH2/PDL2 is only calculate
							#  using the daily candles (which use standard open hours only)
							twoday_dt		= date - timedelta(days=2)
							twoday_dt		= tda_gobot_helper.fix_timestamp(twoday_dt, check_day_only=True)
							twoday			= twoday_dt.strftime('%Y-%m-%d')

							yesterday_timestamp	= datetime.strptime(twoday + ' 16:00:00', '%Y-%m-%d %H:%M:%S')
							yesterday_timestamp	= mytimezone.localize(yesterday_timestamp).timestamp() * 1000

							pdh2_touch		= 0
							pdh2_xover		= 0
							for m_key in pricehistory['candles']:
								if ( m_key['datetime'] < yesterday_timestamp ):
									continue
								elif ( m_key['datetime'] > pricehistory['candles'][idx]['datetime'] ):
									break

								if ( m_key['high'] >= day_stats[today]['pdh2'] ):
									pdh2_touch += 1

									# Price crossed over PDH2, check if it exceeded that level by > 1%
									if ( m_key['high'] > day_stats[today]['pdh2'] ):
										if ( abs(day_stats[today]['pdh2'] / m_key['high'] - 1) * 100 > 1 ):
											pdh2_xover += 1

							if ( pdh2_touch > 0 and pdh2_xover < 1 ):
								resistance_signal = False

			# END HOD/LOD/PDH/PDL Check

			# Key Levels
			# Check if price is near historic key level
			if ( use_keylevel == True and buy_signal == True and resistance_signal == True ):
				near_keylevel	 = False
				lvl = dt = count = 0
				for lvl,dt,count in long_support + long_resistance:
					if ( abs((lvl / cur_close - 1) * 100) <= price_support_pct ):

						# Since we are parsing historical data on key levels,
						#  we should check that we are not just hitting a previous
						#  or newer KL when iterating through the backtest data.
						dt_obj = datetime.fromtimestamp(int(dt)/1000, tz=mytimezone)
						if ( time_sales_use_keylevel == True and count == 999 ):
							if ( dt > cur_dt ):
								continue

						elif ( date < dt_obj + timedelta(days=6) or (date >= dt_obj and date <= dt_obj + timedelta(days=6)) ):
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

			# VAH/VAL Check
			if ( va_check == True and buy_signal == True and resistance_signal == True ):
				try:
					prev_day	= mprofile[today]['prev_day']
					prev_prev_day	= mprofile[today]['prev_prev_day']

				except Exception as e:
					print('Caught Exception: "prev_day" value does not exist in mprofile[' + str(cur_day) + ']')
					sys.exit(1)

				# Enable current VAH/VAL checks later in the day
				cur_vah = cur_val = 0
				if ( int(date.strftime('%-H')) > 11 ):
					cur_vah = mprofile[today]['vah']
					cur_val = mprofile[today]['val']

				prev_vah = prev_val = 0
				if ( prev_day in mprofile ):
					prev_vah = mprofile[prev_day]['vah']
					prev_val = mprofile[prev_day]['val']
				else:
					print('Warning: market_profile(): ' + str(mprofile[today]['prev_day']) + ' not in mprofile, skipping check')

				prev_prev_vah = prev_prev_val = 0
				if ( prev_prev_day in mprofile ):
					prev_prev_vah = mprofile[prev_prev_day]['vah']
					prev_prev_val = mprofile[prev_prev_day]['val']
				else:
					print('Warning: market_profile(): ' + str(mprofile[today]['prev_prev_day']) + ' not in mprofile, skipping check')

				for lvl in [cur_vah, cur_val, prev_vah, prev_val, prev_prev_vah, prev_prev_val]:
					if ( abs((lvl / cur_close - 1) * 100) <= price_support_pct ):

						# Current price is very close to a vah/val
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

			# End VAH/VAL Check

#			# Pivot points resistance
#			if ( use_pivot_resistance == True and resistance_signal == True and today in day_stats ):
#				if ( day_stats[today]['open_idx'] != None ):
#					if ( pricehistory['candles'][day_stats[today]['open_idx']]['open'] < day_stats[today]['pivot'] ):
#					if ( abs((cur_close / day_stats[today]['pivot'] - 1) * 100) <= price_resistance_pct ):
#						resistance_signal = False
#
#				# Pivot point R1/R2 are resistance
#				if ( abs((cur_close / day_stats[today]['pivot_r1'] - 1) * 100) <= price_resistance_pct or
#						abs((cur_close / day_stats[today]['pivot_r2'] - 1) * 100) <= price_resistance_pct):
#					resistance_signal = False

			# 20-week high
#			purchase_price = float(pricehistory['candles'][idx]['close'])
#			if ( purchase_price >= twenty_week_high ):
#				# This is not a good bet
#				twenty_week_high = float(purchase_price)
#				resistance_signal = False
#
#			elif ( ( abs(float(purchase_price) / float(twenty_week_high) - 1) * 100 ) < price_resistance_pct ):
#				# Current high is within price_resistance_pct of 20-week high, not a good bet
#				resistance_signal = False


			# Relative Strength vs. an ETF indicator (i.e. SPY)
			if ( check_etf_indicators == True ):
				prev_rs_signal		= rs_signal
				rs_signal		= False
				tmp_dt			= pricehistory['candles'][idx]['datetime']

				stock_usd		= orig_stock_usd
				decr_threshold_long	= default_decr_threshold
				exit_percent_long	= orig_exit_percent
				quick_exit		= False
				for t in etf_tickers:
					if ( rs_signal == True ):
						break

					cur_rs = 0
					if ( tmp_dt not in etf_indicators[t]['roc'] ):
						print('Warning: etf_indicators does not include timestamp (' + str(tmp_dt) + ')')
						tmp_dt = etf_indicators[t]['last_dt']

					if ( tmp_dt in etf_indicators[t]['roc'] ):
						etf_indicators[t]['last_dt'] = tmp_dt

						try:
							if ( etf_indicators[t]['roc'][tmp_dt] != 0 ):
								with np.errstate(divide='ignore'):
									cur_rs = stock_roc[idx] / etf_indicators[t]['roc'][tmp_dt]

						except ZeroDivisionError:
							cur_rs = 0

						# Avoid trade when ETF indicator is choppy or sideways
						etf_roc_stacked_ma_bull	= etf_roc_stacked_ma_bear	= False
						etf_stacked_ma_bull	= etf_stacked_ma_bear		= False
						if ( tmp_dt in etf_indicators[t]['roc_stacked_ma'] ):
							cur_roc_stacked_ma	= etf_indicators[t]['roc_stacked_ma'][tmp_dt]
							cur_stacked_ma		= etf_indicators[t]['stacked_ma'][tmp_dt]

							etf_roc_stacked_ma_bull = check_stacked_ma(cur_roc_stacked_ma, 'bull')
							etf_roc_stacked_ma_bear = check_stacked_ma(cur_roc_stacked_ma, 'bear')

							etf_stacked_ma_bull	= check_stacked_ma(cur_stacked_ma, 'bull')
							etf_stacked_ma_bear	= check_stacked_ma(cur_stacked_ma, 'bear')

							if ( etf_roc_stacked_ma_bull == False and etf_roc_stacked_ma_bear == False ):
								rs_signal = False
								continue

						else:
							print('Warning (' + str(t) + '): ' + str(tmp_dt) + ' not in etf_indicators')

						# Check MESA EMD to determine if ETF is cycling or trending
						if ( etf_use_emd == True ):
							etf_cur_emd = ( etf_indicators[t]['mesa_emd'][tmp_dt][0],
									etf_indicators[t]['mesa_emd'][tmp_dt][1],
									etf_indicators[t]['mesa_emd'][tmp_dt][2] )

							etf_emd_affinity = get_mesa_emd( cur_emd=etf_cur_emd )
							if ( etf_emd_affinity == 0 ):
								# ETF is in a cycle mode. This typically means the stock is transitioning,
								#  flat, or trading in a channel. This is bad when we use the ETF as an
								#  indicator because we want to ensure the ETF is moving in a particular
								#  direction and not just flopping around.
								rs_signal = False
								continue

#							tmp_dt_prev = pricehistory['candles'][idx-1]['datetime']
#							if ( tmp_dt_prev in etf_indicators[t]['mesa_emd'] ):
#								etf_prev_emd = ( etf_indicators[t]['mesa_emd'][tmp_dt_prev][0],
#										etf_indicators[t]['mesa_emd'][tmp_dt_prev][1],
#										etf_indicators[t]['mesa_emd'][tmp_dt_prev][2] )

#								if ( etf_indicators[t]['roc'][tmp_dt] < 0 ):
									# ETF rate-of-change is below zero
									# Make sure the etf_emd_affinity is trending downward, and
									# and moving downward
#									if ( etf_emd_affinity == 1 or etf_prev_emd[0] < etf_cur_emd[0] ):
#										rs_signal = False
#										continue

								# ETF rate-of-change is above zero
								# Make sure the etf_emd_affinity is trending upward, and
								# and moving upward
#								elif ( etf_indicators[t]['roc'][tmp_dt] > 0 ):
#									if ( etf_emd_affinity == -1 or etf_prev_emd[0] > etf_cur_emd[0] ):
#										rs_signal = False
#										continue

						# Stock is rising compared to ETF
						if ( stock_roc[idx] > 0 and etf_indicators[t]['roc'][tmp_dt] < 0 ):
							cur_rs		= abs( cur_rs )
							rs_signal	= True

							if ( cur_rs < 20 ):
								quick_exit = True

							#pct1		= abs((cur_close - abs(stock_roc[idx]*50)) / cur_close - 1) * 100
							#pct2		= abs((etf_indicators[t]['roc_close'][tmp_dt] - abs(etf_indicators[t]['roc'][tmp_dt]*50)) / etf_indicators[t]['roc_close'][tmp_dt] - 1) * 100
							#print(str(pct1) + ' / ' + str(pct2) + ' / ' + str(pct1/pct2) + ' / ' + str(cur_rs))

						# Both stocks are sinking
						elif ( stock_roc[idx] < 0 and etf_indicators[t]['roc'][tmp_dt] < 0 ):
							cur_rs		= -cur_rs
							rs_signal	= False

						# Stock is sinking relative to ETF
						elif ( stock_roc[idx] < 0 and etf_indicators[t]['roc'][tmp_dt] > 0 ):
							rs_signal = False

						# Both stocks are rising
						elif ( stock_roc[idx] > 0 and etf_indicators[t]['roc'][tmp_dt] > 0 ):
							rs_signal = False

							if ( check_etf_indicators_strict == False and cur_rs > 10 ):
								rs_signal = True
								if ( decr_threshold_long > 1 ):
									decr_threshold_long = 1

								if ( cur_natr < 1 ):
									quick_exit = True
									if ( exit_percent_long != None and exit_percent_long == orig_exit_percent ):
										exit_percent_long = exit_percent_long / 2

						# Something wierd is happening
						else:
							rs_signal = False

						if ( etf_min_rs != None and abs(cur_rs) < etf_min_rs ):
							rs_signal = False
						if ( etf_min_roc != None and abs(etf_indicators[t]['roc'][tmp_dt]) < etf_min_roc ):
							rs_signal = False
						if ( etf_min_natr != None and etf_indicators[t]['natr'][tmp_dt] < etf_min_natr ):
							rs_signal = False


			# Experimental pattern matching - may be removed
			#if ( experimental == True ):
			#	if ( cur_natr_daily > 6 ):
			#		#if ( (diff_signals[idx] == 'buy' or anti_diff_signals[idx] == 'buy') and fib_signals[idx]['bull_signal'] <= -8 ):
			#		if ( fib_signals[idx]['bull_signal'] <= -8 ):
			#			experimental_signal = True
			#	else:
			#		experimental_signal = True


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

				if ( with_trin == True and trin_signal != True ):
					final_buy_signal = False

				if ( with_tick == True and tick_signal != True ):
					final_buy_signal = False

				if ( with_roc == True and roc_signal != True ):
					final_buy_signal = False

				if ( with_sp_monitor == True and sp_monitor_signal != True ):
					final_buy_signal = False

				if ( with_vix == True and vix_signal != True ):
					final_buy_signal = False

				if ( time_sales_algo == True and ts_monitor_signal != True ):
					final_buy_signal = False

				if ( (with_mfi == True or with_mfi_simple == True) and mfi_signal != True ):
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

				if ( with_mama_fama == True and mama_fama_signal != True ):
					final_buy_signal = False

				if ( with_mesa_sine == True and mesa_sine_signal != True ):
					final_buy_signal = False

				if ( with_momentum == True and momentum_signal != True ):
					final_buy_signal = False

				if ( confirm_daily_ma == True and check_stacked_ma(cur_daily_ma, 'bear') == True ):
					final_buy_signal = False

				if ( resistance_signal != True ):
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

				# Relative Strength vs. an ETF indicator (i.e. SPY)
				if ( check_etf_indicators == True and rs_signal != True ):
					final_buy_signal = False

				# Experimental indicators here
				#if ( experimental == True and experimental_signal != True ):
				#	final_buy_signal = False

				# Required EMD affinity for stock
				if ( emd_affinity_long != None ):
					cur_emd		= ( emd_trend[idx], emd_peak[idx], emd_valley[idx] )
					emd_affinity	= get_mesa_emd( cur_emd=cur_emd )
					if ( emd_affinity != emd_affinity_long ):
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
					', bbands_roc_threshold_signal: ' + str(bbands_roc_threshold_signal) +
					', bbands_kchan_crossover_signal: ' + str(bbands_kchan_crossover_signal) +
					', bbands_kchan_init_signal: '	+ str(bbands_kchan_init_signal) +
					', stacked_ma_signal: '		+ str(stacked_ma_signal) +
					', mesa_sine_signal: '		+ str(mesa_sine_signal) +
					', vwap_signal: '		+ str(vwap_signal) +
					', vpt_signal: '		+ str(vpt_signal) +
					', resistance_signal: '		+ str(resistance_signal) +
					', relative_strength_signal: '	+ str(rs_signal) )

				print('(' + str(ticker) + '): ' + str(signal_mode['primary']).upper() + ' / ' + str(time_t) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
				print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
				print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) +
								', Cur/Prev DI_ADX: ' + str(round(cur_di_adx,3)) + ' / ' + str(round(prev_di_adx,3)) + ' signal: ' + str(dmi_signal))
				print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))

				if ( with_macd == True or with_macd_simple == True or aroonosc_with_macd_simple == True ):
					print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))

				if ( with_aroonosc == True or with_aroonosc_simple == True ):
					print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))

				if ( with_bbands_kchannel == True or with_bbands_kchannel_simple == True ):
					print('(' + str(ticker) + '): BBands: ' + str(round(cur_bbands[0], 3)) + ' / ' + str(round(cur_bbands[2], 3)) +
									', KChannel: ' + str(round(cur_kchannel[0], 3)) + ' / ' + str(round(cur_kchannel[1], 3)) + ' / ' + str(round(cur_kchannel[2], 3)) +
									', ROC Count: ' + str(bbands_roc_counter) +
									', Squeeze Count: ' + str(bbands_kchan_signal_counter) )

				print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
				print('(' + str(ticker) + '): BUY signal: ' + str(buy_signal) + ', Final BUY signal: ' + str(final_buy_signal))
				print()
			# DEBUG


			# BUY SIGNAL
			if ( buy_signal == True and final_buy_signal == True ):

				purchase_price	= pricehistory['candles'][idx]['close']
				num_shares	= int( stock_usd / purchase_price )
				base_price_long	= purchase_price
				purchase_time	= datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				# Log rate-of-change for stock and ETF indicators
				tmp_roc = 0
				if ( check_etf_indicators == True ):
					tmp_roc = str(round(stock_roc[idx], 5))
					for t in etf_tickers:
						if ( pricehistory['candles'][idx]['datetime'] in etf_indicators[t]['roc'] ):
							tmp_dt	= pricehistory['candles'][idx]['datetime']
							tmp_roc	+= '/' + str(round(etf_indicators[t]['roc'][tmp_dt], 5))

				results.append( str(purchase_price) + ',' + str(num_shares) + ',' + 'False' + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(cur_mfi_k) + '/' + str(cur_mfi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily,2)) + ',' +
						str(round(bbands_natr['natr'], 3)) + ',' + str(round(bbands_natr['squeeze_natr'], 3)) + ',' +
						str(round(cur_sp_monitor_impulse, 3)) + ',' + str(round(cur_rs, 3)) + ',' +
						str(round(cur_adx,2)) + ',' + str(purchase_time) )

				reset_signals( exclude_bbands_kchan=True )
				signal_mode['primary']		= 'sell'
				bbands_kchan_xover_counter	= 0

				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( variable_exit == True ):
					if ( cur_natr < incr_threshold_long ):
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
						if ( incr_threshold_long > cur_natr * 3 ):
							incr_threshold_long = cur_natr * 2

						elif ( incr_threshold_long > cur_natr * 2 ):
							incr_threshold_long = cur_natr + (cur_natr / 2)

						else:
							incr_threshold_long = cur_natr

						if ( decr_threshold_long > cur_natr * 2 ):
							decr_threshold_long = cur_natr * 2

						if ( exit_percent_long != None ):
							if ( exit_percent_long > cur_natr * 4 ):
								exit_percent_long = cur_natr * 2

						# We may adjust incr/decr_threshold later as well, so store the original version
						#   for comparison if needed.
						orig_incr_threshold_long = incr_threshold_long
						orig_decr_threshold_long = decr_threshold_long

					elif ( cur_natr*2 < decr_threshold_long ):
						decr_threshold_long = cur_natr*2

				# Quick exit when entering counter-trend moves
				if ( trend_quick_exit == True ):
					stacked_ma_bear_affinity = check_stacked_ma(cur_qe_s_ma, 'bear')
					if ( stacked_ma_bear_affinity == True ):
						quick_exit = True

				# Disable ROC exit if we're already entering in a countertrend move
				if ( roc_exit == True ):
					if ( cur_roc_ma < prev_roc_ma ):
						roc_exit = False

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold_long) + ', Decr_Threshold: ' + str(decr_threshold_long) + ', Exit Percent: ' + str(exit_percent_long))
					print('------------------------------------------------------')
				# DEBUG


		# SELL mode
		if ( signal_mode['primary'] == 'sell' or (signal_mode['straddle'] == True and signal_mode['secondary'] == 'sell') ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(5, date) == True ):
				sell_signal		= True
				end_of_day_exits	+= 1

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif ( ph_only == False and safe_open == True and hold_overnight == False and
					tda_gobot_helper.isendofday(60, date) == True ):
				if ( cur_close > purchase_price ):
					percent_change = abs( purchase_price / cur_close - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						sell_signal		= True
						end_of_day_exits	+= 1

			# If stock is sinking over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( use_bbands_kchannel_xover_exit == True and
					(primary_stoch_indicator == 'stacked_ma' or primary_stoch_indicator == 'mama_fama') ):

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

				if ( primary_stoch_indicator == 'stacked_ma' ):
					stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
					stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

					stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
					stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				elif ( primary_stoch_indicator == 'mama_fama' ):
					if ( cur_mama > cur_fama ):
						stacked_ma_bear_affinity	= False
						stacked_ma_bear_ha_affinity	= False
						stacked_ma_bull_affinity	= True
						stacked_ma_bull_ha_affinity	= True
					else:
						stacked_ma_bear_affinity	= True
						stacked_ma_bull_affinity	= True
						stacked_ma_bear_ha_affinity	= False
						stacked_ma_bull_ha_affinity	= False

				# Handle adverse conditions before the crossover
				if ( cur_kchannel_lower < cur_bbands_lower and cur_kchannel_upper > cur_bbands_upper ):
					if ( bbands_kchan_crossover_signal == True ):

						# BBands and KChannel crossed over, but then crossed back. This usually
						#  indicates that the stock is being choppy or changing direction. Check
						#  the direction of the stock, and if it's moving in the wrong direction
						#  then just exit. If we exit early we might even have a chance to re-enter
						#  in the right direction.
						if ( primary_stoch_indicator == 'stacked_ma' ):
							if ( stacked_ma_bear_affinity == True and cur_close < purchase_price ):
								sell_signal = True

					if ( bbands_kchan_crossover_signal == False and primary_stoch_indicator == 'stacked_ma' ):
						if ( stacked_ma_bear_affinity == True or stacked_ma_bear_ha_affinity == True ):

							# Stock momentum switched directions after entry and before crossover
							# We'll give it bbands_kchannel_xover_exit_count minutes to correct itself
							#  and then lower decr_threshold to mitigate risk.
							bbands_kchan_xover_counter -= 1
							if ( bbands_kchan_xover_counter <= -bbands_kchannel_xover_exit_count and cur_close < purchase_price ):
								if ( decr_threshold_long > 0.5 ):
									decr_threshold_long = 0.5

						elif ( stacked_ma_bull_affinity == True ):
							bbands_kchan_xover_counter = 0

				# Handle adverse conditions after the crossover
				elif ( (cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper) or bbands_kchan_crossover_signal == True ):

					bbands_kchan_crossover_signal = True
					bbands_kchan_xover_counter += 1
					if ( bbands_kchan_xover_counter <= 0 ):
						bbands_kchan_xover_counter = 1

					if ( cur_close < purchase_price ):
						if ( bbands_kchan_xover_counter >= 10 ):
							# We've lingered for 10+ bars and price is below entry, let's try to cut our losses
							if ( decr_threshold_long > 1 ):
								decr_threshold_long = 1

						if ( primary_stoch_indicator == 'mama_fama' ):
							# It's likely that the bbands/kchan squeeze has failed in these cases
							if ( stacked_ma_bear_affinity == True ):
								sell_signal = True

					if ( primary_stoch_indicator == 'stacked_ma' or primary_stoch_indicator == 'mama_fama' ):
						if ( stacked_ma_bear_affinity == True or stacked_ma_bear_ha_affinity == True ):
							if ( decr_threshold_long > 1 ):
								decr_threshold_long = 1

							if ( bbands_kchannel_straddle == True and
								signal_mode['primary'] == 'sell' and signal_mode['straddle'] == False ):

								if ( bbands_kchan_xover_counter >= 1 and cur_close < purchase_price ):
									if ( decr_threshold_long > 0.5 ):
										decr_threshold_long = 0.5

									short_price		= pricehistory['candles'][idx]['close']
									base_price_short	= short_price
									short_time		= datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

									# Log rate-of-change for stock and ETF indicators
									tmp_roc = 0
									if ( check_etf_indicators == True ):
										tmp_roc = str(round(stock_roc[idx], 5))
										for t in etf_tickers:
											if ( pricehistory['candles'][idx]['datetime'] in etf_indicators[t]['roc'] ):
												tmp_dt	= pricehistory['candles'][idx]['datetime']
												tmp_roc	+= '/' + str(round(etf_indicators[t]['roc'][tmp_dt], 5))

									straddle_results.append( str(short_price) + ',' + str(num_shares) + ',' + 'True' + ',' +
												 str(-1) + '/' + str(-1) + ',' +
												 str(-1) + '/' + str(-1) + ',' +
												 str(round(cur_natr, 3)) + ',' + str(round(cur_natr_daily, 3)) + ',' +
												 str(round(bbands_natr['natr'], 3)) + ',' + str(round(bbands_natr['squeeze_natr'], 3)) + ',' +
												 str(tmp_roc) + ',' + str(round(cur_rs, 3)) + ',' +
												 str(round(cur_adx, 2)) + ',' + str(short_time) )

									signal_mode['secondary']	= 'buy_to_cover'
									signal_mode['straddle']		= True

			# STOPLOSS
			# Use a flattening or falling rate-of-change to signal an exit
			if ( default_roc_exit == True and sell_signal == False ):
				if ( roc_exit == False ):
					if ( cur_roc_ma > prev_roc_ma ):
						roc_exit = True

				elif ( cur_roc_ma < prev_roc_ma ):
					decr_threshold_long = default_decr_threshold - default_decr_threshold / 3

			# Monitor cost basis
			percent_change = 0
			if ( cur_close < base_price_long and sell_signal == False and exit_percent_signal_long == False ):

				# SELL the security if we are using a trailing stoploss
				percent_change = abs( cur_close / base_price_long - 1 ) * 100
				if ( stoploss == True and percent_change >= decr_threshold_long ):

					# Sell
					sell_price	= pricehistory['candles'][idx]['close']
					sell_time	= datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

					results_t = str(sell_price) + ',' + 'False' + ',' + \
							str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +  \
							str(cur_mfi_k) + '/' + str(cur_mfi_d) + ',' +  \
							str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily, 3)) + ',' + \
							str(round(cur_adx,2)) + ',' + str(sell_time)

					if ( signal_mode['primary'] == 'sell' ):
						results.append( results_t )

					elif ( signal_mode['straddle'] == True and signal_mode['secondary'] == 'sell' ):
						straddle_results.append( results_t )

					else:
						print('Error: buy_to_cover mode: invalid signal_mode (' + str(signal_mode) + ')')

					# DEBUG
					if ( debug_all == True ):
						print('(' + str(ticker) + '): ' + str(signal_mode['primary']).upper() + ' / ' + str(sell_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
						print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
						print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold_long) + ', Decr_Threshold: ' + str(decr_threshold_long) + ', Exit Percent: ' + str(exit_percent_long))
						print('------------------------------------------------------')
					# DEBUG

					stopout_exits		+= 1
					purchase_price		= 0
					base_price_long		= 0

					stock_usd		= orig_stock_usd
					incr_threshold_long	= orig_incr_threshold_long = default_incr_threshold
					decr_threshold_long	= orig_decr_threshold_long = default_decr_threshold
					exit_percent_long	= orig_exit_percent
					quick_exit		= default_quick_exit
					roc_exit		= default_roc_exit

					if ( signal_mode['straddle'] == True ):
						if ( signal_mode['primary'] == 'sell' ):
							signal_mode['primary'] = None
						elif ( signal_mode['secondary'] == 'sell' ):
							signal_mode['secondary'] = None

						if ( signal_mode['primary'] == None and signal_mode['secondary'] == None ):
							signal_mode['straddle'] = False

					if ( signal_mode['straddle'] == False ):
						reset_signals()
						signal_mode['primary']		= 'short'
						signal_mode['secondary']	= None
						signal_mode['straddle']		= False
						if ( noshort == True ):
							signal_mode['primary'] = 'long'

					continue


			elif ( cur_close > base_price_long and sell_signal == False ):
				percent_change = abs( base_price_long / cur_close - 1 ) * 100
				if ( percent_change >= incr_threshold_long ):
					base_price_long = cur_close

					# Adapt decr_threshold based on changes made by --variable_exit
					if ( incr_threshold_long < default_incr_threshold ):

						# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
						#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
						if ( incr_threshold_long == orig_incr_threshold_long ):
							decr_threshold_long = incr_threshold_long
							incr_threshold_long = incr_threshold_long / 2

#					else:
#						decr_threshold_long = incr_threshold_long / 2

			# End cost basis / stoploss monitor

			# Additional exit strategies
			# Sell if exit_percent is specified
			if ( exit_percent_long != None and cur_close > purchase_price and sell_signal == False ):

				# If exit_percent has been hit, we will sell at the first RED candle
				#  unless --quick_exit was set.
				total_percent_change	= abs( purchase_price / cur_close - 1 ) * 100
				high_percent_change	= abs( purchase_price / cur_high - 1 ) * 100
				if ( total_percent_change >= exit_percent_long ):

					# Set stoploss to break even
					decr_threshold_long		= exit_percent_long
					exit_percent_signal_long	= True

					if ( quick_exit == True and total_percent_change >= quick_exit_percent ):
						sell_signal		= True
						exit_percent_exits	+= 1

				# Set the stoploss to the entry price if the candle touches the exit_percent, but closes below it
				elif ( high_percent_change >= exit_percent_long and total_percent_change < exit_percent_long and exit_percent_signal_long == False ):
					if ( decr_threshold_long > total_percent_change ):
						decr_threshold_long = total_percent_change

				# Cost-basis exit may be a bit lower than exit_percent, but if closing prices surpass this limit
				#  then set the stoploss to the cost-basis
				elif ( cost_basis_exit != None and exit_percent_signal_long == False ):
					if ( total_percent_change >= cost_basis_exit and total_percent_change < exit_percent_long ):
						if ( decr_threshold_long > total_percent_change ):
							decr_threshold_long = total_percent_change

				# If the exit_percent has been surpased, then this section will handle the stock exit
				if ( exit_percent_signal_long == True and sell_signal == False ):
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
						period		= 2
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( pricehistory['candles'][idx-i] )
						if ( price_trend(cndl_slice, type=trend_type, period=period, affinity='bull') == False ):
							trend_exit = True

						# Check Heikin Ashi
						last_open	= pricehistory['hacandles'][idx]['open']
						last_close	= pricehistory['hacandles'][idx]['close']
						if ( last_close < last_open ):
							ha_exit	= True

						if ( trend_exit == True and ha_exit == True ):
							sell_signal		= True
							exit_percent_exits	+= 1

					elif ( cur_close < cur_open ):
						sell_signal		= True
						exit_percent_exits	+= 1

			# If we've reached this point we probably need to stop out
			if ( exit_percent_signal_long == True and cur_close < purchase_price ):
				exit_percent_signal_long = False
				decr_threshold_long	 = 0.5

			# Handle quick_exit_percent if quick_exit is configured
			if ( quick_exit == True and sell_signal == False and cur_close > purchase_price ):
				total_percent_change = abs( purchase_price / cur_close - 1 ) * 100
				if ( total_percent_change >= quick_exit_percent ):
					sell_signal = True

			# Monitor RSI for SELL signal
			#  Note that this RSI implementation is more conservative than the one for buy/sell to ensure we don't
			#  miss a valid sell signal.
			#
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( use_rsi_exit == True and strict_exit_percent == False and exit_percent_signal_long == False ):
				if ( cur_rsi_k > stochrsi_default_high_limit and cur_rsi_d > stochrsi_default_high_limit ):
					stochrsi_signal = True

					# Monitor if K and D intersect
					# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region
					if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
						sell_signal = True

				if ( stochrsi_signal == True ):
					if ( prev_rsi_k > stochrsi_default_high_limit and cur_rsi_k <= stochrsi_default_high_limit ):
						sell_signal = True

			# Check the mesa sign indicator for exit signal
			if ( use_mesa_sine_exit == True and strict_exit_percent == False and exit_percent_signal_long == False ):
				mesa_sine_signal = mesa_sine( sine=sine, lead=lead, direction='short', strict=mesa_sine_strict, mesa_exit=True )
				if ( mesa_sine_signal == True ):
					 sell_signal = True


			# SELL
			if ( sell_signal == True ):

				sell_price = pricehistory['candles'][idx]['close']
				sell_time = datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results_t = str(sell_price) + ',' + 'False' + ',' + \
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +  \
						str(cur_mfi_k) + '/' + str(cur_mfi_d) + ',' +  \
						str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily, 3)) + ',' + \
						str(round(cur_adx,2)) + ',' + str(sell_time)

				if ( signal_mode['primary'] == 'sell' ):
					results.append( results_t )

				elif ( signal_mode['straddle'] == True and signal_mode['secondary'] == 'sell' ):
					straddle_results.append( results_t )

				else:
					print('Error: buy_to_cover mode: invalid signal_mode (' + str(signal_mode) + ')')

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode['primary']).upper() + ' / ' + str(sell_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold_long) + ', Decr_Threshold: ' + str(decr_threshold_long) + ', Exit Percent: ' + str(exit_percent_long))
					print('------------------------------------------------------')
				# DEBUG

				purchase_price		= 0
				base_price_long		= 0

				stock_usd		= orig_stock_usd
				incr_threshold_long	= orig_incr_threshold_long = default_incr_threshold
				decr_threshold_long	= orig_decr_threshold_long = default_decr_threshold
				exit_percent_long	= orig_exit_percent
				quick_exit		= default_quick_exit
				roc_exit		= default_roc_exit

				if ( signal_mode['straddle'] == True ):
					if ( signal_mode['primary'] == 'sell' ):
						signal_mode['primary'] = None
					elif ( signal_mode['secondary'] == 'sell' ):
						signal_mode['secondary'] = None

					if ( signal_mode['primary'] == None and signal_mode['secondary'] == None ):
						signal_mode['straddle'] = False

				if ( signal_mode['straddle'] == False ):
					reset_signals()
					signal_mode['primary']		= 'short'
					signal_mode['secondary']	= None
					signal_mode['straddle']		= False
					if ( noshort == True ):
						signal_mode['primary'] = 'long'

				continue


		# SELL SHORT mode
		if ( signal_mode['primary'] == 'short' ):

			# hold_overnight=False - Don't enter any new trades 1-hour before Market close
			if ( hold_overnight == False and ph_only == False and safe_open == True and
					tda_gobot_helper.isendofday(75, date) == True ):
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
				  bbands_roc_threshold_signal,
				  bbands_kchan_crossover_signal,
				  bbands_kchan_signal ) = bbands_kchannels( pricehistory=pricehistory, simple=with_bbands_kchannel_simple,
										cur_bbands=cur_bbands, prev_bbands=prev_bbands,
										cur_kchannel=cur_kchannel, prev_kchannel=prev_kchannel,
										bbands_kchan_init_signal=bbands_kchan_init_signal,
										bbands_roc_threshold_signal=bbands_roc_threshold_signal,
										bbands_kchan_crossover_signal=bbands_kchan_crossover_signal,
										bbands_kchan_signal=bbands_kchan_signal,
										bbands_roc=bbands_roc, debug=False )


			# StochRSI / StochMFI Primary
			if ( primary_stoch_indicator == 'stochrsi' or primary_stoch_indicator == 'stochmfi' ):
				# Jump to buy mode if StochRSI K and D are already below rsi_low_limit
				if ( cur_rsi_k <= stochrsi_default_low_limit and cur_rsi_d <= stochrsi_default_low_limit ):
					reset_signals()
					if ( shortonly == False ):
						signal_mode['primary'] = 'long'
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
					for i in range(period, -1, -1):
						cndl_slice.append( pricehistory['candles'][idx-i] )

					price_trend_bear_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bear')
					price_trend_bull_affinity = price_trend(cndl_slice, type=trend_type, period=period, affinity='bull')

				# Jump to buy mode if the stacked moving averages are showing a bearish movement
				if ( (use_ha_candles == True and (stacked_ma_bull_ha_affinity == True or stacked_ma_bull_affinity == True)) or
					(use_trend == True and price_trend_bull_affinity == True) or
					(use_ha_candles == False and stacked_ma_bull_affinity == True) ):

					reset_signals( exclude_bbands_kchan=True )
					if ( shortonly == False ):
						signal_mode['primary'] = 'long'
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
						signal_mode['primary'] = 'long'
					continue

				if ( cur_aroonosc < -60 ):
					short_signal = True
				else:
					reset_signals()
					continue

			# MESA Adaptive Moving Average primary
			elif ( primary_stoch_indicator == 'mama_fama' ):
				if ( mama_require_xover == True ):
					prev_prev_mama = mama[-2]
					prev_prev_fama = fama[-2]

					# Check if a crossover happened recently, which would have
					#  switched us from short->long mode
					if ( prev_prev_mama >= prev_prev_fama and cur_mama < cur_fama ):
						short_signal = True

					# Price crossed over from bullish to bearish
					elif ( cur_mama >= cur_fama ):
						reset_signals( exclude_bbands_kchan=True )
						if ( shortonly == False ):
							signal_mode['primary'] = 'long'
						continue

				else:
					# If crossover is not required then just check the orientation of
					#  mama and fama
					short_signal = False

					# Bearish trending
					if ( cur_mama < cur_fama ):
						short_signal = True

					# Price crossed over from bearish to bullish
					elif ( cur_mama >= cur_fama or (prev_mama < prev_fama and cur_mama >= cur_fama) ):
						reset_signals( exclude_bbands_kchan=True )
						if ( shortonly == False ):
							signal_mode['primary'] = 'long'
						continue

					else:
						# This shouldn't happen, but just in case...
						short_signal = False

			# MESA Sine Wave
			elif ( primary_stoch_indicator == 'mesa_sine' ):
				cur_sine = sine[idx]
				midline	 = 0

				if ( cur_sine > midline ):
					reset_signals( exclude_bbands_kchan=True )
					if ( shortonly == False ):
						signal_mode['primary'] = 'long'
					continue

				short_signal = mesa_sine( sine=sine, lead=lead, direction='short', strict=mesa_sine_strict, mesa_sine_signal=short_signal )

			# $TRIN primary indicator
			elif ( primary_stoch_indicator == 'trin' ):

				# Jump to long mode if cur_trin is greater than trin_overbought
				if ( cur_trin >= trin_oversold and shortonly == False ):
					reset_signals()
					trin_init_signal	= True
					signal_mode['primary']	= 'long'
					continue

				# Trigger trin_init_signal if cur_trin moves below trin_overbought
				if ( cur_trin <= trin_overbought ):
					trin_counter		= 0
					trin_init_signal	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first red candle
				if ( trin_init_signal == True ):
					if ( cur_ha_close < cur_ha_open ):
						trin_signal	= True
					else:
						trin_signal	= False
						short_signal	= False

					trin_counter += 1
					if ( trin_counter >= 10 ):
						trin_counter		= 0
						trin_init_signal	= False

				# Trigger the short_signal if all the trin signals have tiggered
				if ( trin_init_signal == True and trin_signal == True ):
					short_signal = True

			# ETF SP primary indicator
			elif ( primary_stoch_indicator == 'sp_monitor' ):

				# Use either stacked_ma or trix to help verify sp_monitor direction
				sp_monitor_bull = sp_monitor_bear = False
				if ( sp_monitor_use_trix == True ):
					if ( cur_sp_monitor_trix > prev_sp_monitor_trix and cur_sp_monitor_trix > 0 and
							cur_sp_monitor_trix > cur_sp_monitor_trix_signal ):
						sp_monitor_bull = True
						sp_monitor_bear = False

					elif ( cur_sp_monitor_trix < prev_sp_monitor_trix and cur_sp_monitor_trix < 0 and
							cur_sp_monitor_trix < cur_sp_monitor_trix_signal ):
						sp_monitor_bull = False
						sp_monitor_bear = True

				else:
					sp_monitor_bear	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bear')
					sp_monitor_bull	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bull')

				# Jump to long mode if sp_monitor is positive
				if ( cur_sp_monitor > 0 ):
					reset_signals()
					signal_mode['primary'] = 'long'

					if ( cur_sp_monitor >= 1.5 ):
						sp_monitor_init_signal = True

					if ( cur_sp_monitor >= sp_monitor_threshold ):
						if ( (sp_monitor_strict == True and sp_monitor_bull == True) or sp_monitor_strict == False ):
							buy_signal = True

					continue

				if ( cur_sp_monitor < -1.5 and cur_sp_monitor > -sp_monitor_threshold ):
					sp_monitor_init_signal = True

				#elif ( cur_sp_monitor <= -sp_monitor_threshold and sp_monitor_init_signal == True ):
				elif ( cur_sp_monitor <= -sp_monitor_threshold ):
					if ( (sp_monitor_strict == True and sp_monitor_bear == True) or sp_monitor_strict == False ):
						sp_monitor_init_signal	= False
						short_signal		= True

				# Reset signals if sp_monitor starts to fade
				if ( cur_sp_monitor > -sp_monitor_threshold or (sp_monitor_strict == True and sp_monitor_bear == False) ):
					short_signal = False
				if ( cur_sp_monitor > -1.5 ):
					sp_monitor_init_signal = False

			# Unknown primary indicator
			else:
				print('Error: primary_stoch_indicator "' + str(primary_stoch_indicator) + '" unknown, exiting.')
				return False

			##
			# Secondary Indicators
			##

			# $TRIN indicator
			if ( with_trin == True ):
				if ( cur_trin >= trin_oversold ):
					trin_init_signal = False

				# Trigger trin_init_signal if cur_trin moves below trin_overbought
				if ( cur_trin <= trin_overbought ):
					trin_counter		= 0
					trin_init_signal	= True

				# Once trin_init_signal is triggered, we can trigger the final trin_signal
				#  after the first red candle
				if ( trin_init_signal == True ):
					if ( cur_ha_close < cur_ha_open ):
						trin_signal = True
					else:
						trin_signal = False

					trin_counter += 1
					if ( trin_counter >= 10 ):
						trin_counter		= 0
						trin_init_signal	= False

			# $TICK indicator
			# Bearish action when indicator is below zero and heading downward
			# Bullish action when indicator is above zero and heading upward
			if ( with_tick == True ):
				tick_signal = False
				if ( cur_tick < prev_tick and cur_tick < -tick_threshold ):
					tick_signal = True

			# Rate-of-Change (ROC) indicator
			if ( with_roc == True ):
				#roc_signal = False
				if ( cur_roc_ma < 0 and cur_roc_ma < prev_roc_ma ):
					roc_signal = True
				if ( cur_roc_ma >= -roc_threshold ):
					roc_signal = False

			# ETF SP indicator
			if ( with_sp_monitor == True ):

				# Use either stacked_ma or trix to help verify sp_monitor direction
				sp_monitor_bull = sp_monitor_bear = False
				if ( sp_monitor_use_trix == True ):
					if ( cur_sp_monitor_trix > prev_sp_monitor_trix and cur_sp_monitor_trix > 0 and
							cur_sp_monitor_trix > cur_sp_monitor_trix_signal ):
						sp_monitor_bull = True
						sp_monitor_bear = False

					elif ( cur_sp_monitor_trix < prev_sp_monitor_trix and cur_sp_monitor_trix < 0 and
							cur_sp_monitor_trix < cur_sp_monitor_trix_signal ):
						sp_monitor_bull = False
						sp_monitor_bear = True

				else:
					sp_monitor_bear	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bear')
					sp_monitor_bull	= check_stacked_ma(cur_sp_monitor_stacked_ma, 'bull')

				if ( cur_sp_monitor > 0 ):
					sp_monitor_init_signal	= False
					sp_monitor_signal	= False

				if ( cur_sp_monitor < -1.5 and cur_sp_monitor > -sp_monitor_threshold ):
					sp_monitor_init_signal = True

				elif ( cur_sp_monitor <= -sp_monitor_threshold ):
					if ( (sp_monitor_strict == True and sp_monitor_bear == True) or sp_monitor_strict == False ):
						sp_monitor_init_signal	= False
						sp_monitor_signal	= True

				# Reset signals if sp_monitor starts to fade
				if ( cur_sp_monitor > -sp_monitor_threshold or (sp_monitor_strict == True and sp_monitor_bear == False) ):
					sp_monitor_signal = False
				if ( cur_sp_monitor > -1.5 ):
					sp_monitor_init_signal = False

			# VIX stacked MA
			# The SP 500 and the VIX often show inverse price action - when the S&P falls sharply, the VIX rises—and vice-versa
			if ( with_vix == True ):
				vix_stacked_ma_bull_affinity = check_stacked_ma(cur_vix_ma, 'bull')
				vix_stacked_ma_bear_affinity = check_stacked_ma(cur_vix_ma, 'bear')

				# Increase in VIX typically means bearish for SP500
				vix_signal = False
				if ( vix_stacked_ma_bull_affinity == True ):
					vix_signal = True

				elif ( (vix_stacked_ma_bull_affinity == False and vix_stacked_ma_bear_affinity == False) or
						vix_stacked_ma_bear_affinity == True ):
					vix_signal = False

			# Time and sales algo monitor
			if ( time_sales_algo == True ):
				cur_tstamp = date.strftime('%Y-%m-%d %H:%M')
				if ( cur_tstamp in ts_tx_data ):
					for key in ts_tx_data[cur_tstamp]['txs']:

						# ts_tx_data[t_stamp]['txs'].append( {	'size':		ts_data[dt]['size'],
						#					'price':	tmp_hl2,
						#					'at_bid':	ts_data[dt]['at_bid'],
						#					'at_ask':	ts_data[dt]['at_ask'] } )
						#
						# Large size values are larger institutions buying/selling.
						# Large size values with neat round numbers are typically persistent algos
						#  buying/selling at key absorption areas, which they will continue to do
						#  until they are done with their buy/sell actions.
						if ( re.search('.*00$', str(int(key['size']))) != None ):

							# Large neutral trades typically happen at absorption areas
							# Add these to long_resistance as we find them.
#							if ( time_sales_use_keylevel == True and key['at_bid'] == 0 and key['at_ask'] == 0 and
#									key['size'] >= time_sales_kl_size_threshold ):
#								long_resistance.append( (key['price'], cur_dt, 999) )
#								print( cur_tstamp + ' ' + str(key['price']) )

							# Persistent aggressive bearish action
							if ( key['at_bid'] == 1 and key['at_ask'] == 0 ):
								ts_monitor_signal = True

							# Persistent aggressive bullish action
							elif ( key['at_bid'] == 0 and key['at_ask'] == 1 ):
								ts_monitor_signal = False

					if ( ts_tx_data[cur_tstamp]['ts_cum_delta'] > 0 ):
						ts_monitor_signal = False

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

			# Stacked moving averages
			if ( with_stacked_ma == True ):
				stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma, 'bear')
				stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha, 'bear')

				if ( stacked_ma_bear_affinity == True ):
					stacked_ma_signal = True
				else:
					stacked_ma_signal = False

				# Secondary stacked MA doesn't have its own signal, but can turn off the stacked_ma_signal
				# The idea is to allow a secondary set of periods or MA types to confirm the signal
				if ( with_stacked_ma_secondary == True ):
					stacked_ma_secondary_bear_affinity	= check_stacked_ma(cur_s_ma_secondary, 'bear')
					stacked_ma_secondary_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_secondary, 'bear')

					if ( stacked_ma_secondary_bear_affinity == False ):
						stacked_ma_signal = False

			# MESA Adaptive Moving Average
			if ( with_mama_fama == True ):
				if ( mama_require_xover == True ):
					if ( prev_mama >= prev_fama and cur_mama < cur_fama ):
						mama_fama_signal = True

					elif ( cur_mama >= cur_fama ):
						mama_fama_signal = False

				else:
					mama_fama_signal = False

					# Bearish trending
					if ( cur_mama < cur_fama ):
						mama_fama_signal = True

					# Price crossed over from bearish to bullish
					elif ( cur_mama >= cur_fama ):
						mama_fama_signal = False

			# MESA Sine Wave
			if ( with_mesa_sine == True ):
				mesa_sine_signal = mesa_sine(sine=sine, lead=lead, direction='short', strict=mesa_sine_strict, mesa_sine_signal=mesa_sine_signal)

			# Momentum Indicator
			if ( with_momentum == True ):
				momentum_signal = False
				if ( momentum_use_trix == True ):
					if ( cur_trix < prev_trix and cur_trix < cur_trix_signal ):
						momentum_signal = True

				else:
					if ( cur_mom < prev_mom ):
						if ( cur_mom_roc < 0 ):
							momentum_signal = True

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
			if ( with_aroonosc_simple == True and cur_natr > aroonosc_alt_threshold ):
				cur_aroonosc = cur_aroonosc_alt
				prev_aroonosc = prev_aroonosc_alt

			if ( with_aroonosc == True or with_aroonosc_simple == True ):
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
			if ( with_macd == True or with_macd_simple == True or aroonosc_with_macd_simple == True ):
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
			if ( with_vpt == True ):
				if ( prev_vpt > prev_vpt_sma and cur_vpt < cur_vpt_sma ):
					vpt_signal = True

				# Cancel signal if VPT cross back over
				elif ( cur_vpt > cur_vpt_sma ):
					vpt_signal = False

			# Choppiness Index
			if ( with_chop_index == True or with_chop_simple == True ):
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


			# SUPPORT / RESISTANCE LEVELS
			resistance_signal = True
			today = date.strftime('%Y-%m-%d')

			# PDC
			if ( use_pdc == True and short_signal == True and resistance_signal == True ):
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
			if ( use_natr_resistance == True and short_signal == True and resistance_signal == True ):
				prev_day_close = -1
				if ( today in day_stats ):
					prev_day_close = day_stats[today]['pdc']

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
			if ( use_vwap == True and short_signal == True and resistance_signal == True ):
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
			# Skip this check for the first few hours of the day. The reason for this is
			#  the first hours of trading can create small hod/lods, but they often won't
			#  persist. Also, we are more concerned about the slow, low volume creeps toward
			#  HOD/LOD that are often permanent for the day.
			if ( lod_hod_check == True and short_signal == True and resistance_signal == True ):

				# Check for current-day LOD after 1PM Eastern
				cur_hour = int( date.strftime('%-H') )
				if ( cur_hour >= 13 ):

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

				# If stock opened above PDL, then those can become additional resistance lines for short entry
				# typically later in the day when volume decreases
				if ( today in day_stats ):
					if ( cur_hour >= 12 and day_stats[today]['open_idx'] != None ):
						if ( pricehistory['candles'][day_stats[today]['open_idx']]['open'] > day_stats[today]['pdl'] ):

							# Check PDH/PDL resistance
							avg = 0
							for i in range(15, 0, -1):
								avg += float( pricehistory['candles'][idx-i]['close'] )
								avg = avg / 15

							if ( avg > day_stats[today]['pdl'] and abs((cur_close / day_stats[today]['pdl'] - 1) * 100) <= price_resistance_pct ):
								resistance_signal = False

					# If stock has been rising for a couple days, then oftentimes the 2-day previous day low will be short resistance,
					#  but also check pdl2_touch and pdl2_xover. If price has touched PDL2 multiple times and not crossed over more than
					#  1% then it's stronger resistance
					if ( day_stats[today]['pdl'] > day_stats[today]['pdl2'] and day_stats[today]['pdc'] > day_stats[today]['pdl2'] and
						(day_stats[today]['open_idx'] != None and pricehistory['candles'][day_stats[today]['open_idx']]['open'] > day_stats[today]['pdl2']) ):

						if ( resistance_signal == True and
							abs((cur_low / day_stats[today]['pdl2'] - 1) * 100) <= price_resistance_pct ):

							# Count the number of times over the last two days where the price has touched
							#  PDH/PDL and failed to break through
							#
							# Walk through the 1-min candles for the previous two-days, but be sure to take
							#  into account after-hours trading two-days prior as PDH2/PDL2 is only calculate
							#  using the daily candles (which use standard open hours only)
							twoday_dt		= date - timedelta(days=2)
							twoday_dt		= tda_gobot_helper.fix_timestamp(twoday_dt, check_day_only=True)
							twoday			= twoday_dt.strftime('%Y-%m-%d')

							yesterday_timestamp	= datetime.strptime(twoday + ' 16:00:00', '%Y-%m-%d %H:%M:%S')
							yesterday_timestamp	= mytimezone.localize(yesterday_timestamp).timestamp() * 1000

							pdl2_touch		= 0
							pdl2_xover		= 0
							for m_key in pricehistory['candles']:
								if ( m_key['datetime'] < yesterday_timestamp ):
									continue
								elif ( m_key['datetime'] > pricehistory['candles'][idx]['datetime'] ):
									break

								if ( m_key['low'] <= day_stats[today]['pdl2'] ):
									pdl2_touch += 1

									# Price crossed over PDL2 and exceeded that level by > 1%
									if ( m_key['low'] < day_stats[today]['pdl2'] ):
										if ( abs(m_key['low'] / day_stats[today]['pdl2'] - 1) * 100 > 1 ):
											pdl2_xover += 1

							if ( pdl2_touch > 0 and pdl2_xover < 1 ):
								resistance_signal = False

			# END HOD/LOD/PDH/PDL Check

			# Key Levels
			# Check if price is near historic key level
			if ( use_keylevel == True and short_signal == True and resistance_signal == True ):
				near_keylevel	 = False
				lvl = dt = count = 0
				for lvl,dt,count in long_support + long_resistance:
					if ( abs((lvl / cur_close - 1) * 100) <= price_resistance_pct ):

						# Since we are parsing historical data on key levels,
						#  we should check that we are not just hitting a previous
						#  KL when iterating through the backtest data.
						dt_obj = datetime.fromtimestamp(int(dt)/1000, tz=mytimezone)
						if ( time_sales_use_keylevel == True and count == 999 ):
							if ( dt > cur_dt ):
								continue

						elif ( date < dt_obj + timedelta(days=6) or (date >= dt_obj and date <= dt_obj + timedelta(days=6)) ):
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

			# VAH/VAL Check
			if ( va_check == True and short_signal == True and resistance_signal == True ):
				try:
					prev_day	= mprofile[today]['prev_day']
					prev_prev_day	= mprofile[today]['prev_prev_day']

				except Exception as e:
					print('Caught Exception: "prev_day" value does not exist in mprofile[' + str(today) + ']')
					sys.exit(1)

				# Enable current VAH/VAL checks later in the day
				cur_vah = cur_val = 0
				if ( int(date.strftime('%-H')) > 11 ):
					cur_vah = mprofile[today]['vah']
					cur_val = mprofile[today]['val']

				prev_vah = prev_val = 0
				if ( prev_day in mprofile ):
					prev_vah = mprofile[prev_day]['vah']
					prev_val = mprofile[prev_day]['val']
				else:
					print('Warning: market_profile(): ' + str(mprofile[today]['prev_prev_day']) + ' not in mprofile, skipping check')

				prev_prev_vah = prev_prev_val = 0
				if ( prev_prev_day in mprofile ):
					prev_prev_vah = mprofile[prev_prev_day]['vah']
					prev_prev_val = mprofile[prev_prev_day]['val']
				else:
					print('Warning: market_profile(): ' + str(mprofile[today]['prev_prev_day']) + ' not in mprofile, skipping check')

				for lvl in [ cur_vah, cur_val, prev_vah, prev_val, prev_prev_vah, prev_prev_val ]:
					if ( abs((lvl / cur_close - 1) * 100) <= price_support_pct ):

						# Current price is very close to a vah/val
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
						if ( avg > lvl ):
							resistance_signal = False
							break

			# End VAH/VAL Check

#			# Pivot points resistance
#			if ( use_pivot_resistance == True and resistance_signal == True and today in day_stats):
#					if ( pricehistory['candles'][day_stats[today]['open_idx']]['open'] > day_stats[today]['pivot'] ):
#						if ( abs((cur_close / day_stats[today]['pivot'] - 1) * 100) <= price_resistance_pct ):
#							resistance_signal = False
#
#				# Pivot points S1 and S2 are short resistance
#				if ( abs((cur_close / day_stats[today]['pivot_s1'] - 1) * 100) <= price_resistance_pct or
#						abs((cur_close / day_stats[today]['pivot_s2'] - 1) * 100) <= price_resistance_pct):
#					resistance_signal = False


			# High / low resistance
#			short_price = float(pricehistory['candles'][idx]['close'])
#			if ( float(short_price) <= float(twenty_week_low) ):
#				# This is not a good bet
#				twenty_week_low = float(short_price)
#				resistance_signal = False
#
#			elif ( ( abs(float(twenty_week_low) / float(short_price) - 1) * 100 ) < price_support_pct ):
#				# Current low is within price_support_pct of 20-week low, not a good bet
#				resistance_signal = False


			# Relative Strength vs. an ETF indicator (i.e. SPY)
			if ( check_etf_indicators == True ):
				prev_rs_signal		= rs_signal
				rs_signal		= False
				tmp_dt			= pricehistory['candles'][idx]['datetime']

				stock_usd		= orig_stock_usd
				decr_threshold_short	= default_decr_threshold
				exit_percent_short	= orig_exit_percent
				quick_exit		= False
				for t in etf_tickers:
					if ( rs_signal == True ):
						break

					cur_rs = 0
					if ( tmp_dt not in etf_indicators[t]['roc'] ):
						print('Warning: etf_indicators does not include timestamp (' + str(tmp_dt) + ')')
						tmp_dt = etf_indicators[t]['last_dt']

					if ( tmp_dt in etf_indicators[t]['roc'] ):
						etf_indicators[t]['last_dt'] = tmp_dt

						try:
							if ( etf_indicators[t]['roc'][tmp_dt] != 0 ):
								with np.errstate(divide='ignore'):
									cur_rs = stock_roc[idx] / etf_indicators[t]['roc'][tmp_dt]

						except ZeroDivisionError:
							cur_rs = 0

						# Avoid trade when ETF indicator is choppy or sideways
						etf_roc_stacked_ma_bull	= etf_roc_stacked_ma_bear	= False
						etf_stacked_ma_bull	= etf_stacked_ma_bear		= False
						if ( tmp_dt in etf_indicators[t]['roc_stacked_ma'] ):
							cur_roc_stacked_ma	= etf_indicators[t]['roc_stacked_ma'][tmp_dt]
							cur_stacked_ma		= etf_indicators[t]['stacked_ma'][tmp_dt]

							etf_roc_stacked_ma_bull = check_stacked_ma(cur_roc_stacked_ma, 'bull')
							etf_roc_stacked_ma_bear = check_stacked_ma(cur_roc_stacked_ma, 'bear')

							etf_stacked_ma_bull	= check_stacked_ma(cur_stacked_ma, 'bull')
							etf_stacked_ma_bear	= check_stacked_ma(cur_stacked_ma, 'bear')

							if ( etf_roc_stacked_ma_bull == False and etf_roc_stacked_ma_bear == False ):
								rs_signal = False
								continue

						else:
							print('Warning (' + str(t) + '): ' + str(tmp_dt) + ' not in etf_indicators')

						# Check MESA EMD to determine if ETF is cycling or trending
						if ( etf_use_emd == True ):
							etf_cur_emd = ( etf_indicators[t]['mesa_emd'][tmp_dt][0],
									etf_indicators[t]['mesa_emd'][tmp_dt][1],
									etf_indicators[t]['mesa_emd'][tmp_dt][2] )

							etf_emd_affinity = get_mesa_emd( cur_emd=etf_cur_emd )
							if ( etf_emd_affinity == 0 ):
								# ETF is in a cycle mode. This typically means the stock is transitioning,
								#  flat, or trading in a channel. This is bad when we use the ETF as an
								#  indicator because we want to ensure the ETF is moving in a particular
								#  direction and not just flopping around.
								rs_signal = False
								continue

#							tmp_dt_prev = pricehistory['candles'][idx-1]['datetime']
#							if ( tmp_dt_prev in etf_indicators[t]['mesa_emd'] ):
#								etf_prev_emd = ( etf_indicators[t]['mesa_emd'][tmp_dt_prev][0],
#										etf_indicators[t]['mesa_emd'][tmp_dt_prev][1],
#										etf_indicators[t]['mesa_emd'][tmp_dt_prev][2] )

#								if ( etf_indicators[t]['roc'][tmp_dt] < 0 ):
									# ETF rate-of-change is below zero
									# Make sure the etf_emd_affinity is trending downward, and
									# and moving downward
#									if ( etf_emd_affinity == 1 or etf_prev_emd[0] < etf_cur_emd[0] ):
#										rs_signal = False
#										continue

								# ETF rate-of-change is above zero
								# Make sure the etf_emd_affinity is trending upward, and
								# and moving upward
#								elif ( etf_indicators[t]['roc'][tmp_dt] > 0 ):
#									if ( etf_emd_affinity == -1 or etf_prev_emd[0] > etf_cur_emd[0] ):
#										rs_signal = False
#										continue

						# Stock is rising compared to ETF
						if ( stock_roc[idx] > 0 and etf_indicators[t]['roc'][tmp_dt] < 0 ):
							cur_rs		= abs( cur_rs )
							rs_signal	= False

						# Both stocks are sinking
						elif ( stock_roc[idx] < 0 and etf_indicators[t]['roc'][tmp_dt] < 0 ):
							cur_rs		= -cur_rs
							rs_signal	= False

							if ( check_etf_indicators_strict == False and cur_rs > 10 ):
								rs_signal = True
								if ( decr_threshold_short > 1 ):
									decr_threshold_short = 1

								if ( cur_natr < 1 ):
									quick_exit = True
									if ( exit_percent_short != None and exit_percent_short == orig_exit_percent ):
										exit_percent_short = exit_percent_short / 2

						# Stock is sinking relative to ETF
						elif ( stock_roc[idx] < 0 and etf_indicators[t]['roc'][tmp_dt] > 0 ):
							rs_signal = True
							if ( abs(cur_rs) < 20 ):
								quick_exit = True

						# Both stocks are rising
						elif ( stock_roc[idx] > 0 and etf_indicators[t]['roc'][tmp_dt] > 0 ):
							rs_signal = False

						# Something wierd is happening
						else:
							rs_signal = False

						if ( etf_min_rs != None and abs(cur_rs) < etf_min_rs ):
							rs_signal = False
						if ( etf_min_roc != None and abs(etf_indicators[t]['roc'][tmp_dt]) < etf_min_roc ):
							rs_signal = False
						if ( etf_min_natr != None and etf_indicators[t]['natr'][tmp_dt] < etf_min_natr ):
							rs_signal = False


			# Experimental indicators
			#if ( experimental == True ):
			#	if ( cur_natr_daily > 6 ):
			#		#if ( (diff_signals[idx] == 'short' or anti_diff_signals[idx] == 'short') and fib_signals[idx]['bear_signal'] >= 8 ):
			#		if ( fib_signals[idx]['bear_signal'] >= 8 ):
			#			experimental_signal = True
			#	else:
			#		experimental_signal = True


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

				if ( with_trin == True and trin_signal != True ):
					final_short_signal = False

				if ( with_tick == True and tick_signal != True ):
					final_short_signal = False

				if ( with_roc == True and roc_signal != True ):
					final_short_signal = False

				if ( with_sp_monitor == True and sp_monitor_signal != True ):
					final_short_signal = False

				if ( with_vix == True and vix_signal != True ):
					final_short_signal = False

				if ( time_sales_algo == True and ts_monitor_signal != True ):
					final_short_signal = False

				if ( (with_mfi == True or with_mfi_simple == True) and mfi_signal != True ):
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

				if ( with_mama_fama == True and mama_fama_signal != True ):
					final_short_signal = False

				if ( with_mesa_sine == True and mesa_sine_signal != True ):
					final_short_signal = False

				if ( with_momentum == True and momentum_signal != True ):
					final_short_signal = False

				if ( confirm_daily_ma == True and check_stacked_ma(cur_daily_ma, 'bull') == True ):
					final_short_signal = False

				if ( resistance_signal != True ):
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

				# Relative Strength vs. an ETF indicator (i.e. SPY)
				if ( check_etf_indicators == True and rs_signal != True ):
					final_short_signal = False

				# Experimental
				#if ( experimental == True and experimental_signal != True ):
				#	final_short_signal = False

				# Required EMD affinity for stock
				if ( emd_affinity_short != None ):
					cur_emd		= ( emd_trend[idx],emd_peak[idx], emd_valley[idx] )
					emd_affinity	= get_mesa_emd( cur_emd=cur_emd )
					if ( emd_affinity != emd_affinity_short ):
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
					', bbands_roc_threshold_signal: ' + str(bbands_roc_threshold_signal) +
					', bbands_kchan_crossover_signal: ' + str(bbands_kchan_crossover_signal) +
					', bbands_kchan_init_signal: '  + str(bbands_kchan_init_signal) +
					', stacked_ma_signal: '		+ str(stacked_ma_signal) +
					', mesa_sine_signal: '		+ str(mesa_sine_signal) +
					', vwap_signal: '		+ str(vwap_signal) +
					', vpt_signal: '		+ str(vpt_signal) +
					', resistance_signal: '		+ str(resistance_signal) +
					', relative_strength_signal: '	+ str(rs_signal) )

				print('(' + str(ticker) + '): ' + str(signal_mode['primary']).upper() + ' / ' + str(time_t) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
				print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
				print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) +
								', Cur/Prev DI_ADX: ' + str(round(cur_di_adx,3)) + ' / ' + str(round(prev_di_adx,3)) + ' signal: ' + str(dmi_signal))
				print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))

				if ( with_macd == True or with_macd_simple == True or aroonosc_with_macd_simple == True ):
					print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))

				if ( with_aroonosc == True or with_aroonosc_simple == True ):
					print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))

				if ( with_bbands_kchannel == True or with_bbands_kchannel_simple == True ):
					print('(' + str(ticker) + '): BBands: ' + str(round(cur_bbands[0], 3)) + ' / ' + str(round(cur_bbands[2], 3)) +
									', KChannel: ' + str(round(cur_kchannel[0], 3)) + ' / ' + str(round(cur_kchannel[1], 3)) + ' / ' + str(round(cur_kchannel[2], 3)) +
									', ROC Count: ' + str(bbands_roc_counter) +
									', Squeeze Count: ' + str(bbands_kchan_signal_counter) )

				print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
				print('(' + str(ticker) + '): SHORT signal: ' + str(short_signal) + ', Final SHORT signal: ' + str(final_short_signal))
				print()
			# DEBUG


			# SHORT SIGNAL
			if ( short_signal == True and final_short_signal == True ):

				short_price		= pricehistory['candles'][idx]['close']
				num_shares		= int( stock_usd / short_price )
				base_price_short	= short_price
				short_time		= datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				# Log rate-of-change for stock and ETF indicators
				tmp_roc = 0
				if ( check_etf_indicators == True ):
					tmp_roc = str(round(stock_roc[idx], 5))
					for t in etf_tickers:
						if ( pricehistory['candles'][idx]['datetime'] in etf_indicators[t]['roc'] ):
							tmp_dt	= pricehistory['candles'][idx]['datetime']
							tmp_roc	+= '/' + str(round(etf_indicators[t]['roc'][tmp_dt], 5))

				results.append( str(short_price) + ',' + str(num_shares) + ',' + 'True' + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(cur_mfi_k) + '/' + str(cur_mfi_d) + ',' +
						str(round(cur_natr, 3)) + ',' + str(round(cur_natr_daily, 3)) + ',' +
						str(round(bbands_natr['natr'], 3)) + ',' + str(round(bbands_natr['squeeze_natr'], 3)) + ',' +
						str(round(cur_sp_monitor_impulse, 3)) + ',' + str(round(cur_rs, 3)) + ',' +
						str(round(cur_adx, 2)) + ',' + str(short_time) )

				reset_signals( exclude_bbands_kchan=True )
				signal_mode['primary']		= 'buy_to_cover'
				bbands_kchan_xover_counter	= 0

				# Build a profile of the stock's price action over the 90 minutes and adjust
				#  incr_threshold, decr_threshold and exit_percent if needed.
				if ( variable_exit == True ):
					if ( cur_natr < incr_threshold_short ):

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
						if ( incr_threshold_short > cur_natr * 3 ):
							incr_threshold_short = cur_natr * 2

						elif ( incr_threshold_short > cur_natr * 2 ):
							incr_threshold_short = cur_natr + (cur_natr / 2)

						else:
							incr_threshold_short = cur_natr

						if ( decr_threshold_short > cur_natr * 2 ):
							decr_threshold_short = cur_natr * 2

						if ( exit_percent_short != None ):
							if ( exit_percent_short > cur_natr * 4 ):
								exit_percent_short = cur_natr * 2

						# We may adjust incr/decr_threshold later as well, so store the original version
						#   for comparison if needed.
						orig_incr_threshold_short = incr_threshold_short
						orig_decr_threshold_short = decr_threshold_short

					elif ( cur_natr*2 < decr_threshold_short ):
						decr_threshold_short = cur_natr*2

				# Quick exit when entering counter-trend moves
				if ( trend_quick_exit == True ):
					stacked_ma_bull_affinity = check_stacked_ma(cur_qe_s_ma, 'bull')
					if ( stacked_ma_bull_affinity == True ):
						quick_exit = True

				# Disable ROC exit if we're already entering in a countertrend move
				if ( roc_exit == True ):
					if ( cur_roc_ma > prev_roc_ma ):
						roc_exit = False

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold_short) + ', Decr_Threshold: ' + str(decr_threshold_short) + ', Exit Percent: ' + str(exit_percent_short))
					print('------------------------------------------------------')
				# DEBUG


		# BUY-TO-COVER mode
		if ( signal_mode['primary'] == 'buy_to_cover' or (signal_mode['straddle'] == True and signal_mode['secondary'] == 'buy_to_cover') ):

			# hold_overnight=False - drop the stock before market close
			if ( hold_overnight == False and tda_gobot_helper.isendofday(5, date) == True ):
				buy_to_cover_signal	= True
				end_of_day_exits	+= 1

			# The last trading hour is a bit unpredictable. If --hold_overnight is false we want
			#  to sell the stock at a more conservative exit percentage.
			elif (ph_only == False and hold_overnight == False and safe_open == True and
					tda_gobot_helper.isendofday(60, date) == True ):
				if ( cur_close < short_price ):
					percent_change = abs( short_price / cur_close - 1 ) * 100
					if ( percent_change >= last_hour_threshold ):
						buy_to_cover_signal	= True
						end_of_day_exits	+= 1

			# If stock is rising over n-periods (bbands_kchannel_xover_exit_count) after entry then just exit
			#  the position
			if ( use_bbands_kchannel_xover_exit == True and
					(primary_stoch_indicator == 'stacked_ma' or primary_stoch_indicator == 'mama_fama') ):
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

				if ( primary_stoch_indicator == 'stacked_ma' ):
					stacked_ma_bear_affinity	= check_stacked_ma(cur_s_ma_primary, 'bear')
					stacked_ma_bull_affinity	= check_stacked_ma(cur_s_ma_primary, 'bull')

					stacked_ma_bear_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bear')
					stacked_ma_bull_ha_affinity	= check_stacked_ma(cur_s_ma_ha_primary, 'bull')

				elif ( primary_stoch_indicator == 'mama_fama' ):
					if ( cur_mama < cur_fama ):
						stacked_ma_bear_affinity	= True
						stacked_ma_bear_ha_affinity	= True
						stacked_ma_bull_affinity	= False
						stacked_ma_bull_ha_affinity	= False
					else:
						stacked_ma_bear_affinity	= False
						stacked_ma_bull_affinity	= False
						stacked_ma_bear_ha_affinity	= True
						stacked_ma_bull_ha_affinity	= True

				# Handle adverse conditions before the crossover
				if ( cur_kchannel_lower < cur_bbands_lower and cur_kchannel_upper > cur_bbands_upper ):
					if ( bbands_kchan_crossover_signal == True ):

						# BBands and KChannel crossed over, but then crossed back. This usually
						#  indicates that the stock is being choppy or changing direction. Check
						#  the direction of the stock, and if it's moving in the wrong direction
						#  then just exit. If we exit early we might even have a chance to re-enter
						#  in the right direction.
						if ( primary_stoch_indicator == 'stacked_ma' ):
							if ( stacked_ma_bull_affinity == True and cur_close > short_price ):
								buy_to_cover_signal = True

					if ( bbands_kchan_crossover_signal == False and primary_stoch_indicator == 'stacked_ma' ):
						if ( stacked_ma_bull_affinity == True or stacked_ma_bull_ha_affinity == True ):

							# Stock momentum switched directions after entry and before crossover.
							# We'll give it bbands_kchannel_xover_exit_count minutes to correct itself
							#  and then lower decr_threshold to mitigate risk.
							bbands_kchan_xover_counter -= 1
							if ( bbands_kchan_xover_counter <= -bbands_kchannel_xover_exit_count and cur_close > short_price ):
								if ( decr_threshold_short > 0.5 ):
									decr_threshold_short = 0.5

						elif ( stacked_ma_bear_affinity == True ):
							bbands_kchan_xover_counter = 0

				# Handle adverse conditions after the crossover
				if ( (cur_kchannel_lower > cur_bbands_lower or cur_kchannel_upper < cur_bbands_upper) or bbands_kchan_crossover_signal == True ):

					bbands_kchan_crossover_signal = True
					bbands_kchan_xover_counter += 1
					if ( bbands_kchan_xover_counter <= 0 ):
						bbands_kchan_xover_counter = 1

					if ( cur_close > short_price ):
						if ( bbands_kchan_xover_counter >= 10 ):
							# We've lingered for 10+ bars and price is above short entry, let's try to cut out losses
							if ( decr_threshold_short > 1 ):
								decr_threshold_short = 1

						if ( primary_stoch_indicator == 'mama_fama' ):
							# It's likely that the bbands/kchan squeeze has failed in these cases
							if ( stacked_ma_bull_affinity == True ):
								buy_to_cover_signal = True

#							elif ( bbands_kchan_xover_counter >= 4 and cur_close > cur_open ):
#								buy_to_cover_signal = True

					if ( primary_stoch_indicator == 'stacked_ma' or primary_stoch_indicator == 'mama_fama' ):
						if ( stacked_ma_bull_affinity == True or stacked_ma_bull_ha_affinity == True ):
							if ( decr_threshold_short > 1 ):
								decr_threshold_short = 1

							if ( bbands_kchannel_straddle == True and
								signal_mode['primary'] == 'buy_to_cover' and signal_mode['straddle'] == False ):

								if ( bbands_kchan_xover_counter >= 1 and cur_close > short_price ):
									if ( decr_threshold_short > 0.5 ):
										decr_threshold_short = 0.5

									purchase_price		= pricehistory['candles'][idx]['close']
									base_price_long		= purchase_price
									purchase_time		= datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

									# Log rate-of-change for stock and ETF indicators
									tmp_roc = 0
									if ( check_etf_indicators == True ):
										tmp_roc = str(round(stock_roc[idx], 5))
										for t in etf_tickers:
											if ( pricehistory['candles'][idx]['datetime'] in etf_indicators[t]['roc'] ):
												tmp_dt	= pricehistory['candles'][idx]['datetime']
												tmp_roc	+= '/' + str(round(etf_indicators[t]['roc'][tmp_dt], 5))

									straddle_results.append( str(purchase_price) + ',' + str(num_shares) + ',' + 'False' + ',' +
												 str(-1) + '/' + str(-1) + ',' +
												 str(-1) + '/' + str(-1) + ',' +
												 str(round(cur_natr, 3)) + ',' + str(round(cur_natr_daily, 3)) + ',' +
												 str(round(bbands_natr['natr'], 3)) + ',' + str(round(bbands_natr['squeeze_natr'], 3)) + ',' +
												 str(tmp_roc) + ',' + str(round(cur_rs, 3)) + ',' +
												 str(round(cur_adx, 2)) + ',' + str(purchase_time) )

									signal_mode['secondary']	= 'sell'
									signal_mode['straddle']		= True

					# So far these strategies do not work
					# Keeping them commented here for reference
#					if ( bbands_kchan_xover_counter >= 2 and cur_close > short_price and abs(cur_close / short_price - 1) * 100 > 0.5 ):
#						if ( decr_threshold > 1 ):
#							decr_threshold = 1
#					if ( cur_close > short_price ):
#						if ( decr_threshold > 1 ):
#							decr_threshold = 1
#					if ( bbands_kchan_xover_counter >= 15 and cur_close > short_price ):
#						buy_to_cover_signal = True

			# STOPLOSS
			# Use a flattening or falling rate-of-change to signal an exit
			if ( default_roc_exit == True and buy_to_cover_signal == False ):
				if ( roc_exit == False ):
					if ( cur_roc_ma < prev_roc_ma ):
						roc_exit = True

				elif ( cur_roc_ma > prev_roc_ma ):
					decr_threshold_short = default_decr_threshold - default_decr_threshold / 3

			# Monitor cost basis
			percent_change = 0
			if ( cur_close > base_price_short and buy_to_cover_signal == False and exit_percent_signal_short == False ):

				# Buy-to-cover the security if we are using a trailing stoploss
				percent_change = abs( base_price_short / cur_close - 1 ) * 100
				if ( stoploss == True and percent_change >= decr_threshold_short ):

					# Buy-to-cover
					buy_to_cover_price = pricehistory['candles'][idx]['close']
					buy_to_cover_time = datetime.fromtimestamp(pricehistory['candles'][idx]['datetime']/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

					results_t = str(buy_to_cover_price) + ',' + 'True' + ',' + \
							str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +  \
							str(cur_mfi_k) + '/' + str(cur_mfi_d) + ',' +  \
							str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily, 3)) + ',' + \
							str(round(cur_adx,2)) + ',' + str(buy_to_cover_time)

					if ( signal_mode['primary'] == 'buy_to_cover' ):
						results.append( results_t )

					elif ( signal_mode['straddle'] == True and signal_mode['secondary'] == 'buy_to_cover' ):
						straddle_results.append( results_t )

					else:
						print('Error: buy_to_cover mode: invalid signal_mode (' + str(signal_mode) + ')')

					# DEBUG
					if ( debug_all == True ):
						print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(buy_to_cover_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
						print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
						print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold_short) + ', Decr_Threshold: ' + str(decr_threshold_short) + ', Exit Percent: ' + str(exit_percent_short))
						print('------------------------------------------------------')
					# DEBUG

					stopout_exits		+= 1
					short_price		= 0
					base_price_short	= 0

					stock_usd		= orig_stock_usd
					incr_threshold_short	= orig_incr_threshold_short = default_incr_threshold
					decr_threshold_short	= orig_decr_threshold_short = default_decr_threshold
					exit_percent_short	= orig_exit_percent
					quick_exit		= default_quick_exit
					roc_exit		= default_roc_exit

					if ( signal_mode['straddle'] == True ):
						if ( signal_mode['primary'] == 'buy_to_cover' ):
							signal_mode['primary'] = None
						elif ( signal_mode['secondary'] == 'buy_to_cover' ):
							signal_mode['secondary'] = None

						if ( signal_mode['primary'] == None and signal_mode['secondary'] == None ):
							signal_mode['straddle'] = False

					if ( signal_mode['straddle'] == False ):
						reset_signals()
						signal_mode['primary']		= 'long'
						signal_mode['secondary']	= None
						signal_mode['straddle']		= False
						if ( shortonly == True ):
							signal_mode['primary'] = 'short'

					continue

			elif ( cur_close < base_price_short and buy_to_cover_signal == False ):
				percent_change = abs( cur_close / base_price_short - 1 ) * 100
				if ( percent_change >= incr_threshold_short ):
					base_price_short = cur_close

					# Adapt decr_threshold based on changes made by --variable_exit
					if ( incr_threshold_short < default_incr_threshold ):

						# If this is the first adjustment, then set decr_threshold to be the same as orig_incr_threshold,
						#  and reduce incr_threshold by half just one time to enable a quick base_price update reaction.
						if ( incr_threshold_short == orig_incr_threshold_short ):
							decr_threshold_short = incr_threshold_short
							incr_threshold_short = incr_threshold_short / 2

#					else:
#						decr_threshold_short = incr_threshold_short / 2

			# End cost basis / stoploss monitor


			# Additional exit strategies
			# Sell if exit_percent is specified
			if ( cur_close < short_price and exit_percent_short != None and buy_to_cover_signal == False ):

				# If exit_percent has been hit, we will sell at the first GREEN candle
				#  unless quick_exit was set.
				total_percent_change	= abs( cur_close / short_price - 1 ) * 100
				low_percent_change	= abs( cur_low / short_price - 1 ) * 100
				if ( total_percent_change >= exit_percent_short ):

					# Set stoploss to break even
					decr_threshold_short		= exit_percent_short
					exit_percent_signal_short	= True

					if ( quick_exit == True and total_percent_change >= quick_exit_percent ):
						buy_to_cover_signal	= True
						exit_percent_exits	+= 1

				# Set the stoploss to the entry price if the candle touches the exit_percent, but closes below it
				elif ( low_percent_change >= exit_percent_short and total_percent_change < exit_percent_short and exit_percent_signal_short == False ):
					if ( decr_threshold_short > total_percent_change ):
						decr_threshold_short = total_percent_change

				# Cost-basis exit may be a bit lower than exit_percent, but if closing prices surpass this limit
				#  then set the stoploss to the cost-basis
				elif ( cost_basis_exit != None and exit_percent_signal_short == False ):
					if ( total_percent_change >= cost_basis_exit and total_percent_change < exit_percent_short ):
						if ( decr_threshold_short > total_percent_change ):
							decr_threshold_short = total_percent_change

				# If the exit_percent has been surpased, then this section will handle the stock exit
				if ( exit_percent_signal_short == True and buy_to_cover_signal == False ):
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
						period		= 2
						cndl_slice	= []
						for i in range(period+1, 0, -1):
							cndl_slice.append( pricehistory['candles'][idx-i] )
						if ( price_trend(cndl_slice, type=trend_type, period=period, affinity='bear') == False ):
							trend_exit = True

						# Check Heikin Ashi
						last_open	= pricehistory['hacandles'][idx]['open']
						last_close	= pricehistory['hacandles'][idx]['close']
						if ( last_close > last_open ):
							ha_exit	= True

						if ( trend_exit == True and ha_exit == True ):
							buy_to_cover_signal	= True
							exit_percent_exits	+= 1

					elif ( cur_close > cur_open ):
						buy_to_cover_signal	= True
						exit_percent_exits	+= 1

			# If we've reached this point we probably need to stop out
			if ( exit_percent_signal_short == True and cur_close > short_price ):
				exit_percent_signal_short	= False
				decr_threshold_short		= 0.5

			# Handle quick_exit_percent if quick_exit is configured
			if ( quick_exit == True and buy_to_cover_signal == False and cur_close < short_price ):
				total_percent_change = abs( cur_close / short_price - 1 ) * 100
				if ( total_percent_change >= quick_exit_percent ):
					buy_to_cover_signal = True

			# Monitor RSI for BUY_TO_COVER signal
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( use_rsi_exit == True and strict_exit_percent == False and exit_percent_signal_short == False ):
				if ( cur_rsi_k < stochrsi_default_low_limit and cur_rsi_d < stochrsi_default_low_limit ):
					stochrsi_signal = True

					# Monitor if K and D intercect
					# A buy-to-cover signal occurs when an increasing %K line crosses above the %D line in the oversold region.
					if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
						buy_to_cover_signal = True

				if ( stochrsi_signal == True ):
					if ( prev_rsi_k < stochrsi_default_low_limit and cur_rsi_k >= stochrsi_default_low_limit ):
						buy_to_cover_signal = True

			# Check the mesa sign indicator for exit signal
			if ( use_mesa_sine_exit == True and strict_exit_percent == False and exit_percent_signal_short == False ):
				mesa_sine_signal = mesa_sine( sine=sine, lead=lead, direction='long', strict=mesa_sine_strict, mesa_exit=True )
				if ( mesa_sine_signal == True ):
					 buy_to_cover_signal = True


			# BUY-TO-COVER
			if ( buy_to_cover_signal == True ):

				buy_to_cover_price = pricehistory['candles'][idx]['close']
				buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results_t = str(buy_to_cover_price) + ',' + 'True' + ',' + \
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' + \
						str(cur_mfi_k) + '/' + str(cur_mfi_d) + ',' + \
						str(round(cur_natr,3)) + ',' + str(round(cur_natr_daily, 3)) + ',' + \
						str(round(cur_adx,2)) + ',' + str(buy_to_cover_time)

				if ( signal_mode['primary'] == 'buy_to_cover' ):
					results.append( results_t )

				elif ( signal_mode['straddle'] == True and signal_mode['secondary'] == 'buy_to_cover' ):
					straddle_results.append( results_t )

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(buy_to_cover_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): Incr_Threshold: ' + str(incr_threshold_short) + ', Decr_Threshold: ' + str(decr_threshold_short) + ', Exit Percent: ' + str(exit_percent_short))
					print('------------------------------------------------------')
				# DEBUG

				short_price		= 0
				base_price_short	= 0

				stock_usd		= orig_stock_usd
				incr_threshold_short	= orig_incr_threshold_short = default_incr_threshold
				decr_threshold_short	= orig_decr_threshold_short = default_decr_threshold
				exit_percent_short	= orig_exit_percent
				quick_exit		= default_quick_exit
				roc_exit		= default_roc_exit

				if ( signal_mode['straddle'] == True ):
					if ( signal_mode['primary'] == 'buy_to_cover' ):
						signal_mode['primary'] = None
					elif ( signal_mode['secondary'] == 'buy_to_cover' ):
						signal_mode['secondary'] = None

					if ( signal_mode['primary'] == None and signal_mode['secondary'] == None ):
						signal_mode['straddle'] = False

				if ( signal_mode['straddle'] == False ):
					reset_signals()
					signal_mode['primary']		= 'short'
					signal_mode['secondary']	= None
					signal_mode['straddle']		= False
					if ( noshort == True ):
						signal_mode['primary'] = 'long'

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

	return results + straddle_results

