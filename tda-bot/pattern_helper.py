#!/usr/bin/python3 -u

# Helper module for candle pattern matching functions

# Differential pattern
# This is a short-term trend reversal pattern
def pattern_differential(pricehistory=None):

	diff_signals = []
	diff_signals.append(None)
	for i in range( 1, len(pricehistory['candles']) ):

		cur_low		= float( pricehistory['candles'][i]['low'] )
		prev_low	= float( pricehistory['candles'][i-1]['low'] )
		prev_prev_low	= float( pricehistory['candles'][i-2]['low'] )

		cur_high	= float( pricehistory['candles'][i]['high'] )
		prev_high	= float( pricehistory['candles'][i-1]['high'] )
		prev_prev_high	= float( pricehistory['candles'][i-2]['high'] )

		cur_close	= float( pricehistory['candles'][i]['close'] )
		prev_close	= float( pricehistory['candles'][i-1]['close'] )
		prev_prev_close	= float( pricehistory['candles'][i-2]['close'] )

		# True low
		true_low	= min(cur_low, prev_low)
		true_low	= cur_close - true_low

		prev_true_low	= min(prev_low, prev_prev_low)
		prev_true_low	= prev_close - prev_true_low

		# True high
		true_high	= max(cur_high, prev_high)
		true_high	= cur_close - true_high

		prev_true_high	= max(prev_high, prev_prev_high)
		prev_true_high	= prev_close - true_high

		# Differential pattern
		if ( cur_close < prev_close and prev_close < prev_prev_close and \
			true_low > prev_true_low and true_high < prev_true_high ):

			diff_signals.append('buy')

		elif ( cur_close > prev_close and prev_close > prev_prev_close and \
			true_low < prev_true_low and true_high > prev_true_high ):

			diff_signals.append('short')

		else:
			diff_signals.append(None)

	return diff_signals


# Reverse differential pattern
# This is a trend continuation pattern
def pattern_reverse_differential(pricehistory=None):

	diff_signals = []
	diff_signals.append(None)
	for i in range( 1, len(pricehistory['candles']) ):

		cur_low		= float( pricehistory['candles'][i]['low'] )
		prev_low	= float( pricehistory['candles'][i-1]['low'] )
		prev_prev_low	= float( pricehistory['candles'][i-2]['low'] )

		cur_high	= float( pricehistory['candles'][i]['high'] )
		prev_high	= float( pricehistory['candles'][i-1]['high'] )
		prev_prev_high	= float( pricehistory['candles'][i-2]['high'] )

		cur_close	= float( pricehistory['candles'][i]['close'] )
		prev_close	= float( pricehistory['candles'][i-1]['close'] )
		prev_prev_close	= float( pricehistory['candles'][i-2]['close'] )

		# True low
		true_low	= min(cur_low, prev_low)
		true_low	= cur_close - true_low

		prev_true_low	= min(prev_low, prev_prev_low)
		prev_true_low	= prev_close - prev_true_low

		# True high
		true_high	= max(cur_high, prev_high)
		true_high	= cur_close - true_high

		prev_true_high	= max(prev_high, prev_prev_high)
		prev_true_high	= prev_close - true_high

		# Reverse differential
		if ( cur_close < prev_close and prev_close < prev_prev_close and \
			true_low < prev_true_low and true_high > prev_true_high ):

			diff_signals.append('buy')

		elif ( cur_close > prev_close and prev_close > prev_prev_close and \
			true_low > prev_true_low and true_high < prev_true_high ):

			diff_signals.append('short')

		else:
			diff_signals.append(None)

	return diff_signals


# Anti-differential pattern
# This is a short-term trend reversal pattern
def pattern_anti_differential(pricehistory=None):

	diff_signals = []
	diff_signals.append(None)
	for i in range( 1, len(pricehistory['candles']) ):

		cur_close	= float( pricehistory['candles'][i]['close'] )
		prev_close	= float( pricehistory['candles'][i-1]['close'] )
		prev_close2	= float( pricehistory['candles'][i-2]['close'] )
		prev_close3	= float( pricehistory['candles'][i-3]['close'] )
		prev_close4	= float( pricehistory['candles'][i-4]['close'] )

		if ( cur_close < prev_close and prev_close > prev_close2 and \
			prev_close2 < prev_close3 and prev_close3 < prev_close4 ):

			diff_signals.append('buy')

		elif ( cur_close > prev_close and prev_close < prev_close2 and \
			prev_close2 > prev_close3 and prev_close3 > prev_close4 ):

			diff_signals.append('short')

		else:
			diff_signals.append(None)

	return diff_signals


# Fibonacci Timing Pattern
# Reference: https://medium.com/the-investors-handbook/multiple-indicator-trading-strategy-in-python-a-full-guide-78305cb2732b
#
# For a bullish Fibonacci Timing Pattern, we need 8 closes where each close is lower
#   than the close 5 periods ago, lower than the close 3 periods ago, and lower than the
#   close 1 period ago. Upon the completion of this pattern, we will have a bullish signal.
#   Any interruption in the sequence will invalidate the pattern.
#
# For a bearish Fibonacci Timing Pattern, we need 8 closes where each close is higher
#   than the close 5 periods ago, higher than the close 3 periods ago, and higher than the
#   close 1 period ago. Upon the completion of this pattern, we will have a bearish signal.
#   Any interruption in the sequence will invalidate the pattern.
def pattern_fibonacci_timing(pricehistory=None, count=8, step=5, step_two=3, step_three=2):

	# Initialize fib_signals
	fib_signals	= []
	for i in range(0, len(pricehistory['candles'])):
		fib_signals.append( {   'bull_signal': 0,
					'bear_signal': 0,
					'datetime': int(pricehistory['candles'][i]['datetime']) } )

	# Bullish Fibonacci Timing Pattern
	counter = -1
	for i in range(0, len(pricehistory['candles'])):
		cur_close	= float( pricehistory['candles'][i]['close'] )
		prev_close	= float( pricehistory['candles'][i-step]['close'] )
		prev_close2	= float( pricehistory['candles'][i-step_two]['close'] )
		prev_close3	= float( pricehistory['candles'][i-step_three]['close'] )

		if ( cur_close < prev_close and cur_close < prev_close2 and cur_close < prev_close3 ):
			fib_signals[i]['bull_signal'] = counter
			counter += -1

			if ( counter == -count - 1 ):
				counter = 0
			else:
				continue

		elif ( cur_close >= prev_close ):
			counter = -1
			fib_signals[i]['bull_signal'] = counter

		else:
			fib_signals[i]['bull_signal'] = 0

	# Bearish Fibonacci Timing Pattern
	counter = 1
	for i in range(0, len(pricehistory['candles'])):
		cur_close	= float( pricehistory['candles'][i]['close'] )
		prev_close	= float( pricehistory['candles'][i-step]['close'] )
		prev_close2	= float( pricehistory['candles'][i-step_two]['close'] )
		prev_close3	= float( pricehistory['candles'][i-step_three]['close'] )

		if ( cur_close > prev_close and cur_close > prev_close2 and cur_close > prev_close3 ):
			fib_signals[i]['bear_signal'] = counter
			counter += 1

			if (counter == count + 1 ):
				counter = 0
			else:
				continue

		elif ( cur_close <= prev_close ):
			counter = 1
			fib_signals[i]['bear_signal'] = counter

		else:
			fib_signals[i]['bear_signal'] = 0


	return fib_signals
