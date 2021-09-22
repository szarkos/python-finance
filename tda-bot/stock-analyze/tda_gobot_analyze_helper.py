#!/usr/bin/python3 -u

import os, sys
from collections import OrderedDict

from datetime import datetime, timedelta
from pytz import timezone

parent_path = os.path.dirname( os.path.realpath(__file__) )
sys.path.append(parent_path + '/../')
import tda_gobot_helper


# Like stochrsi_analyze(), but sexier
def stochrsi_analyze_new( pricehistory=None, ticker=None, primary_stoch_indicator='stochrsi', rsi_period=14, stochrsi_period=128, rsi_type='hlc3', rsi_slow=3, rsi_low_limit=20, rsi_high_limit=80, rsi_k_period=128, rsi_d_period=3, stochrsi_5m=False,
			  stoploss=False, incr_threshold=1, decr_threshold=1.5, hold_overnight=False, exit_percent=None, strict_exit_percent=False, vwap_exit=False, quick_exit=False,
			  variable_exit=False, no_use_resistance=False, price_resistance_pct=1, price_support_pct=1,
			  with_rsi=False, with_rsi_simple=False, with_adx=False, with_dmi=False, with_aroonosc=False, with_aroonosc_simple=False, with_macd=False, with_vwap=False, with_vpt=False, with_mfi=False,
			  with_dmi_simple=False, with_macd_simple=False, aroonosc_with_macd_simple=False, aroonosc_with_vpt=False, aroonosc_secondary_threshold=70,
			  vpt_sma_period=72, adx_period=92, di_period=48, atr_period=14, adx_threshold=25, mfi_period=14, aroonosc_period=48, mfi_low_limit=20, mfi_high_limit=80,
			  lod_hod_check=False, check_volume=False, avg_volume=2000000, min_volume=1500000,
			  check_ma=False, noshort=False, shortonly=False, safe_open=True, start_date=None, stop_date=None, weekly_ph=None, keylevel_strict=False, keylevel_use_daily=False, blacklist_earnings=False,
			  debug=False, debug_all=False ):

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

		nonlocal rsi_signal			; rsi_signal			= False
		nonlocal mfi_signal			; mfi_signal			= False
		nonlocal adx_signal			; adx_signal			= False
		nonlocal dmi_signal			; dmi_signal			= False
		nonlocal macd_signal			; macd_signal			= False
		nonlocal aroonosc_signal		; aroonosc_signal		= False
		nonlocal vwap_signal			; vwap_signal			= False
		nonlocal vpt_signal			; vpt_signal			= False
		nonlocal resistance_signal		; resistance_signal		= False

		nonlocal plus_di_crossover		; plus_di_crossover		= False
		nonlocal minus_di_crossover		; minus_di_crossover		= False
		nonlocal macd_crossover			; macd_crossover		= False
		nonlocal macd_avg_crossover		; macd_avg_crossover		= False

		return True

	# END reset_signals

	# If set, turn start_date and/or stop_date into a datetime object
	if ( start_date != None ):
		start_date = datetime.strptime(start_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
		start_date = mytimezone.localize(start_date)
	if ( stop_date != None ):
		stop_date = datetime.strptime(stop_date + ' 00:00:00', '%Y-%m-%d %H:%M:%S')
		stop_date = mytimezone.localize(stop_date)

	# We use 5-minute candles to calculate the ATR
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
	stochrsi_signal_cancel_low_limit = 20
	stochrsi_signal_cancel_high_limit = 80

	try:
		if ( primary_stoch_indicator == 'stochrsi' ):
			if ( stochrsi_5m == True ):
				stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(pricehistory_5m, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)
			else:
				stochrsi, rsi_k, rsi_d = tda_gobot_helper.get_stochrsi(pricehistory, rsi_period=rsi_period, stochrsi_period=stochrsi_period, type=rsi_type, slow_period=rsi_slow, rsi_k_period=rsi_k_period, rsi_d_period=rsi_d_period, debug=False)

		elif ( primary_stoch_indicator == 'stochmfi' ):
			if ( stochrsi_5m == True ):
				rsi_k, rsi_d = tda_gobot_helper.get_stochmfi(pricehistory_5m, mfi_period=mfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)
			else:
				rsi_k, rsi_d = tda_gobot_helper.get_stochmfi(pricehistory, mfi_period=mfi_period, mfi_k_period=rsi_k_period, slow_period=rsi_slow, mfi_d_period=rsi_d_period, debug=False)

			stochrsi = rsi_k

		else:
			print('Error: stochrsi_analyze_new(' + str(ticker) + '): unknown primary_stoch_indicator "' + str(primary_stoch_indicator) + '"')
			sys.exit(1)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi(): ' + str(e))
		return False

	if ( isinstance(stochrsi, bool) and stochrsi == False ):
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_stochrsi() returned false - no data', file=sys.stderr)
		return False

	# If using the same 1-minute data, the len of stochrsi will be (stochrsi_period * 2 - 1)
	# len(rsi_k) should be (stochrsi_period * 2 - rsi_d_period)
	if ( primary_stoch_indicator == 'stochrsi' and stochrsi_5m == False ):
		if ( len(stochrsi) != len(pricehistory['candles']) - (rsi_period * 2 - 1) ):
			print( 'Warning, unexpected length of stochrsi (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(stochrsi)=' + str(len(stochrsi)) + ')' )

		if ( len(rsi_k) != len(pricehistory['candles']) - stochrsi_period * 2 - rsi_d_period ):
			print( 'Warning, unexpected length of rsi_k (pricehistory[candles]=' + str(len(pricehistory['candles'])) + ', len(rsi_k)=' + str(len(rsi_k)) + ')' )
		if ( len(rsi_k) != len(rsi_d) ):
			print( 'Warning, unexpected length of rsi_k (pricehistory[candles]=' + str(len(pricehistory['candles'])) +
				', len(rsi_k)=' + str(len(stochrsi)) + '), len(rsi_d)=' + str(len(rsi_d)) + ')' )

	# Get RSI
	rsi_signal_cancel_low_limit = 30
	rsi_signal_cancel_high_limit = 70

	try:
		rsi = tda_gobot_helper.get_rsi(pricehistory, rsi_period, rsi_type, debug=False)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_rsi(): ' + str(e))
		return False

	# Get MFI
	mfi_signal_cancel_low_limit = 30
	mfi_signal_cancel_high_limit = 70

	try:
		mfi = tda_gobot_helper.get_mfi(pricehistory, period=mfi_period)

	except Exception as e:
		print('Caught Exception: stochrsi_analyze_new(' + str(ticker) + '): get_mfi(): ' + str(e))

	# Average True Range (ATR)
	atr = []
	natr = []
	try:
		atr, natr = tda_gobot_helper.get_atr( pricehistory=pricehistory_5m, period=atr_period )

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_atr(): ' + str(e))
		return False


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
	aroonosc_92 = []
	try:
		aroonosc = tda_gobot_helper.get_aroon_osc(pricehistory, period=aroonosc_period)
		aroonosc_92 = tda_gobot_helper.get_aroon_osc(pricehistory, period=92)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_aroon_osc(): ' + str(e))
		return False

	# MACD - 48, 104, 36
	macd_offset = 0.006
	if ( with_macd == True and with_macd_simple == True):
		with_macd_simple = False

	macd = []
	macd_signal = []
	macd_histogram = []
	try:
		macd, macd_avg, macd_histogram = tda_gobot_helper.get_macd(pricehistory, short_period=48, long_period=104, signal_period=36)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_macd(): ' + str(e))
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

	# VPT - Volume Price Trend
	vpt = []
	vpt_sma = []
	try:
		vpt, vpt_sma = tda_gobot_helper.get_vpt(pricehistory, period=vpt_sma_period)

	except Exception as e:
		print('Error: stochrsi_analyze_new(' + str(ticker) + '): get_vpt(): ' + str(e))
		return False

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

	# Check the SMA and EMA to see if stock is bearish or bullish
	sma = {}
	ema = {}
	if ( check_ma == True ):
		import av_gobot_helper
		sma = av_gobot_helper.av_get_ma(ticker, ma_type='sma', time_period=200)
		ema = av_gobot_helper.av_get_ma(ticker, ma_type='ema', time_period=50)


	# Run through the RSI values and log the results
	results				= []

	if ( stochrsi_5m == True ):
		stochrsi_idx		= len(pricehistory['candles']) - len(rsi_k) * 5
	else:
		stochrsi_idx		= len(pricehistory['candles']) - len(rsi_k)

	rsi_idx				= len(pricehistory['candles']) - len(rsi)

	mfi_idx				= len(pricehistory['candles']) - len(mfi)

	adx_idx				= len(pricehistory['candles']) - len(adx)
	di_idx				= len(pricehistory['candles']) - len(plus_di)

	aroonosc_idx			= len(pricehistory['candles']) - len(aroonosc)
	aroonosc_92_idx			= len(pricehistory['candles']) - len(aroonosc_92)
	macd_idx			= len(pricehistory['candles']) - len(macd)

	buy_signal			= False
	sell_signal			= False
	short_signal			= False
	buy_to_cover_signal		= False

	final_buy_signal		= False
	final_sell_signal		= False
	final_short_signal		= False
	final_buy_to_cover_signal	= False

	exit_percent_signal		= False

	rsi_signal			= False
	mfi_signal			= False
	adx_signal			= False
	dmi_signal			= False
	macd_signal			= False
	aroonosc_signal			= False
	vwap_signal			= False
	vpt_signal			= False
	resistance_signal		= False

	plus_di_crossover		= False
	minus_di_crossover		= False
	macd_crossover			= False
	macd_avg_crossover		= False

	default_incr_threshold		= incr_threshold
	default_decr_threshold		= decr_threshold
	orig_incr_threshold		= incr_threshold
	orig_decr_threshold		= decr_threshold
	orig_exit_percent		= exit_percent

	first_day			= datetime.fromtimestamp(float(pricehistory['candles'][0]['datetime'])/1000, tz=mytimezone)
	start_day			= first_day + timedelta( days=1 )
	start_day_epoch			= int( start_day.timestamp() * 1000 )

	last_hour_threshold		= 0.2 # Last hour trading threshold

	signal_mode = 'buy'
	if ( shortonly == True ):
		signal_mode = 'short'


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

		# Indicators current values
		if ( stochrsi_5m == True ):
			cur_rsi_k = rsi_k[int((idx - stochrsi_idx) / 5)]
			prev_rsi_k = rsi_k[int((idx - stochrsi_idx) / 5) - 1]

			cur_rsi_d = rsi_d[int((idx - stochrsi_idx) / 5)]
			prev_rsi_d = rsi_d[int((idx - stochrsi_idx) / 5) - 1]

		else:
			cur_rsi_k = rsi_k[idx - stochrsi_idx]
			prev_rsi_k = rsi_k[(idx - stochrsi_idx) - 1]

			cur_rsi_d = rsi_d[idx - stochrsi_idx]
			prev_rsi_d = rsi_d[(idx - stochrsi_idx) - 1]

		cur_rsi = rsi[idx - rsi_idx]
		prev_rsi = rsi[(idx - rsi_idx) - 1]

		cur_mfi = mfi[idx - mfi_idx]
		prev_mfi = mfi[(idx - mfi_idx) - 1]

		# Additional indicators
		cur_adx = adx[idx - adx_idx]
		cur_plus_di = plus_di[idx - di_idx]
		prev_plus_di = plus_di[(idx - di_idx) - 1]
		cur_minus_di = minus_di[idx - di_idx]
		prev_minus_di = minus_di[(idx - di_idx) - 1]

		cur_macd = macd[idx - macd_idx]
		prev_macd = macd[(idx - macd_idx) - 1]

		cur_macd_avg = macd_avg[idx - macd_idx]
		prev_macd_avg = macd_avg[(idx - macd_idx) - 1]

		cur_aroonosc = aroonosc[idx - aroonosc_idx]
		prev_aroonosc = aroonosc[idx - aroonosc_idx - 1]
		cur_aroonosc_92 = aroonosc_92[idx - aroonosc_92_idx]
		prev_aroonosc_92 = aroonosc_92[idx - aroonosc_92_idx - 1]

		cur_vpt = vpt[idx]
		prev_vpt = vpt[idx-1]

		cur_vpt_sma = vpt_sma[idx - vpt_sma_period]
		prev_vpt_sma = vpt_sma[idx - vpt_sma_period]

		cur_atr = atr[int(idx / 5) - atr_period]
		cur_natr = natr[int(idx / 5) - atr_period]


		# Skip all candles until start_date, if it is set
		date = datetime.fromtimestamp(int(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone)
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

		# Check SMA/EMA to see if stock is bullish or bearish
		if ( check_ma == True ):
			cur_day = date.strftime('%Y-%m-%d')

			try:
				cur_sma = sma['moving_avg'][cur_day]
				cur_ema = ema['moving_avg'][cur_day]

			except Exception as e:
				cur_sma = 0
				cur_ema = 0

			if ( cur_sma <= cur_ema ):
				# Stock is bullish, disable shorting for now
				noshort = True
				if ( signal_mode == 'short' ):
					signal_mode = 'buy'

			elif ( cur_sma > cur_ema ):
				# Stock is bearish, allow shorting
				noshort = False

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
			if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit and noshort == False ):
				reset_signals()
				signal_mode = 'short'
				continue

			# Check StochRSI
			if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit ):

				# Monitor if K and D intersect
				# A buy signal occurs when an increasing %K line crosses above the %D line in the oversold region.
				#  or if the %K line crosses below the rsi limit
				if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
					buy_signal = True

			elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
				if ( cur_rsi_k >= rsi_low_limit ):
					buy_signal = True

			elif ( cur_rsi_k > stochrsi_signal_cancel_low_limit and cur_rsi_d > stochrsi_signal_cancel_low_limit ):
				reset_signals()
				buy_signal = False

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
			if ( cur_natr > 0.24 and with_aroonosc_simple == True ):
				cur_aroonosc = cur_aroonosc_92
				prev_aroonosc = prev_aroonosc_92

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

				if ( no_use_resistance == False and resistance_signal != True ):
					final_buy_signal = False

			# BUY SIGNAL
			if ( buy_signal == True and final_buy_signal == True ):
				purchase_price = float(pricehistory['candles'][idx]['close'])
				base_price = purchase_price
				purchase_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(purchase_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(purchase_time) )

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(purchase_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
					print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) + ' signal: ' + str(dmi_signal))
					print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
					print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
					print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))
					print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
					print('(' + str(ticker) + '): BUY signal: ' + str(buy_signal) + ', Final BUY signal: ' + str(final_buy_signal))
				# DEBUG

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
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( incr_threshold > cur_natr * 2 ):
							incr_threshold = cur_natr * 2
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
							str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(sell_time) )

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
			# Do not use stochrsi as an exit signal if strict_exit_percent is set to True
			# Also, if exit_percent_signal is triggered that means we've surpassed the exit_percent threshold and
			#   should wait for either a red candle or for decr_threshold to be hit.
			if ( strict_exit_percent == False and exit_percent_signal == False ):
				if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit ):

					# Monitor if K and D intercect
					# A sell signal occurs when a decreasing %K line crosses below the %D line in the overbought region
					if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
						sell_signal = True

				elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
					if ( cur_rsi_k <= rsi_high_limit ):
						sell_signal = True

			if ( sell_signal == True ):

				# Sell
				sell_price = float(pricehistory['candles'][idx]['close'])
				sell_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				# sell_price,bool(short),rsi,stochrsi,sell_time
				results.append( str(sell_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(sell_time) )

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
			if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit ):
				reset_signals()
				signal_mode = 'buy'
				continue

			# Monitor RSI
			if ( cur_rsi_k > rsi_high_limit and cur_rsi_d > rsi_high_limit ):

				# Monitor if K and D intercect
				# A sell-short signal occurs when a decreasing %K line crosses below the %D line in the overbought region
				if ( prev_rsi_k > prev_rsi_d and cur_rsi_k <= cur_rsi_d ):
					short_signal = True

			elif ( prev_rsi_k > rsi_high_limit and cur_rsi_k < prev_rsi_k ):
				if ( cur_rsi_k <= rsi_high_limit ):
					short_signal = True

			elif ( cur_rsi_k < stochrsi_signal_cancel_high_limit and cur_rsi_d < stochrsi_signal_cancel_high_limit ):
				reset_signals()
				short_signal = False


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
			if ( cur_natr > 0.24 and with_aroonosc_simple == True ):
				cur_aroonosc = cur_aroonosc_92
				prev_aroonosc = prev_aroonosc_92

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
			if ( with_vpt == True ):
				# Short signal - VPT crosses below vpt_sma
				if ( prev_vpt > prev_vpt_sma and cur_vpt < cur_vpt_sma ):
					vpt_signal = True

				# Cancel signal if VPT cross back over
				elif ( cur_vpt > cur_vpt_sma ):
					vpt_signal = False

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

				if ( no_use_resistance == False and resistance_signal != True ):
					final_short_signal = False

			# SHORT SIGNAL
			if ( short_signal == True and final_short_signal == True ):
				short_price = float(pricehistory['candles'][idx]['close'])
				base_price = short_price
				short_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(short_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr, 3)) + ',' + str(round(cur_adx, 2)) + ',' + str(short_time) )

				# DEBUG
				if ( debug_all == True ):
					print('(' + str(ticker) + '): ' + str(signal_mode).upper() + ' / ' + str(short_time) + ' (' + str(pricehistory['candles'][idx]['datetime']) + ')')
					print('(' + str(ticker) + '): StochRSI K/D: ' + str(round(cur_rsi_k, 3)) + ' / ' + str(round(cur_rsi_d,3)))
					print('(' + str(ticker) + '): MFI: ' + str(round(cur_mfi, 2)) + ' signal: ' + str(mfi_signal))
					print('(' + str(ticker) + '): DI+/-: ' + str(round(cur_plus_di, 3)) + ' / ' + str(round(cur_minus_di,3)) + ' signal: ' + str(dmi_signal))
					print('(' + str(ticker) + '): ADX: ' + str(round(cur_adx, 3)) + ' signal: ' + str(adx_signal))
					print('(' + str(ticker) + '): MACD (cur/avg): ' + str(round(cur_macd, 3)) + ' / ' + str(round(cur_macd_avg,3)) + ' signal: ' + str(macd_signal))
					print('(' + str(ticker) + '): AroonOsc: ' + str(cur_aroonosc) + ' signal: ' + str(aroonosc_signal))
					print('(' + str(ticker) + '): ATR/NATR: ' + str(cur_atr) + ' / ' + str(cur_natr))
					print('(' + str(ticker) + '): SHORT signal: ' + str(short_signal) + ', Final SHORT signal: ' + str(final_short_signal))
				# DEBUG

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
						# Note that currently we may reduce these values, but we do not increase them above
						#  their settings configured by the user.
						if ( incr_threshold > cur_natr * 2 ):
							incr_threshold = cur_natr * 2
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
							str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(buy_to_cover_time) )

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
				if ( cur_rsi_k < rsi_low_limit and cur_rsi_d < rsi_low_limit ):

					# Monitor if K and D intercect
					# A buy-to-cover signal occurs when an increasing %K line crosses above the %D line in the oversold region.
					if ( prev_rsi_k < prev_rsi_d and cur_rsi_k >= cur_rsi_d ):
						buy_to_cover_signal = True

				elif ( prev_rsi_k < rsi_low_limit and cur_rsi_k > prev_rsi_k ):
					if ( cur_rsi_k >= rsi_low_limit ):
						buy_to_cover_signal = True

			# BUY-TO-COVER
			if ( buy_to_cover_signal == True ):

				buy_to_cover_price = float(pricehistory['candles'][idx]['close'])
				buy_to_cover_time = datetime.fromtimestamp(float(pricehistory['candles'][idx]['datetime'])/1000, tz=mytimezone).strftime('%Y-%m-%d %H:%M:%S.%f')

				results.append( str(buy_to_cover_price) + ',' + str(short) + ',' +
						str(cur_rsi_k) + '/' + str(cur_rsi_d) + ',' +
						str(round(cur_natr,3)) + ',' + str(round(cur_adx,2)) + ',' + str(buy_to_cover_time) )

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
