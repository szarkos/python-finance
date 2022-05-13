#!/bin/bash

command=${1-""}
command=$(echo -n "$command" | tr '[:upper:]' '[:lower:]')

# This is just a small script to kick off the gobot
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/../.."

echo "CWD is `pwd`"

if [ "$command" != "force" ]; then

	# Wait until market opens to run the script
	echo "Sleeping until 06:30AM Eastern time..."
	while [ 1 ] ; do
		cur_time=$(TZ="America/New_York" date +%H:%M)
		echo "Current time is $cur_time"

		if [ "$cur_time" == "09:20" ]; then
			break
		fi
		sleep 30
	done
fi

# The list of tickers is contained in the $CUR_SET variable in tickers.conf
mkdir ./logs 2>/dev/null
source ./stock-analyze/tickers.conf
tickers=$CUR_SET
tickers="SPY,QQQ"

nohup ./tda-stochrsi-gobot-v2.py --stoploss --stocks=${tickers} --short --unsafe --fake --singleday \
	--decr_threshold=0.2 --incr_threshold=0.25 --exit_percent=0.4 --max_failed_txs=5 --stock_usd=20000 \
	--options_decr_threshold=20 --options_incr_threshold=2.5 --options_exit_percent=10 --options_usd=2000 \
	--resist_pct_dynamic --price_resistance_pct=0.25 --price_support_pct=0.25 \
	--otm_level=2 --near_expiration --start_day_offset=1 \
	\
	--algos=algo_id:sp_monitor_tsalgo_options,primary_sp_monitor,sp_monitor_tickers:AAPL:7.07+MSFT:5.97+AMZN:2.81+TSLA:1.98+GOOGL:2.03+GOOG:1.88+BRK.B:1.69+UNH:1.36+JNJ:1.38+NVDA:1.3+FB:1.35+PG:1.1+XOM:1.06+V:0.95+JPM:1.04+HD:0.9+MA:0.83+CVX:0.92+PFE:0.82+ABBV:0.79,time_sales_algo,time_sales_use_keylevel,time_sales_size_threshold:3000,time_sales_kl_size_threshold:6000,va_check,options,quick_exit,quick_exit_percent:10 \
	--algos=algo_id:mama_spmon_tsalgo_options,primary_mama_fama,sp_monitor,sp_monitor_tickers:AAPL:7.07+MSFT:5.97+AMZN:2.81+TSLA:1.98+GOOGL:2.03+GOOG:1.88+BRK.B:1.69+UNH:1.36+JNJ:1.38+NVDA:1.3+FB:1.35+PG:1.1+XOM:1.06+V:0.95+JPM:1.04+HD:0.9+MA:0.83+CVX:0.92+PFE:0.82+ABBV:0.79,time_sales_algo,time_sales_use_keylevel,time_sales_size_threshold:3000,time_sales_kl_size_threshold:6000,va_check,options,quick_exit,quick_exit_percent:10 \
	\
	--algo_valid_tickers=sp_monitor_tsalgo_options:SPY,QQQ \
	--algo_valid_tickers=mama_spmon_tsalgo_options:SPY,QQQ \
	\
	--tx_log_dir=TX_LOGS_v2 1> logs/gobot-v2.log 2>&1 &

disown


#--algos=algo_id:sp_monitor_options,primary_sp_monitor,sp_monitor_tickers:AAPL:6.99+MSFT:5.95+AMZN:3.11+TSLA:2.09+GOOGL:1.96+GOOG:1.83+BRK.B:1.69+UNH:1.37+JNJ:1.36+NVDA:1.33+FB:1.32+PG:1.10+XOM:1.03+V:1.01+JPM:1.01+HD:0.90+MA:0.90+CVX:0.86+PFE:0.79+ABBV:0.74,sp_monitor_strict,sp_monitor_stacked_ma_type:hma,sp_monitor_stacked_ma_periods:5.8.13,sp_monitor_threshold:3,use_keylevel,va_check,options,ph_only,quick_exit,quick_exit_percent:20 \
#--algos=algo_id:sp_monitor_tick_options,primary_sp_monitor,sp_monitor_tickers:AAPL:6.88+MSFT:5.63+AMZN:3.56+TSLA:2.21+GOOGL:2.05+GOOG:1.9+BRK.B:1.69+NVDA:1.43+UNH:1.35+FB:1.3+JNJ:1.27+PG:1.02+JPM:1+XOM:1+V:0.95+CVX:0.89+HD:0.85+MA:0.83+PFE:0.8+ABBV:0.77,sp_monitor_use_trix,sp_monitor_trix_ma_type:hma,sp_monitor_trix_ma_period=14,tick:tick_ma_type:ema,tick_ma_period:5,use_keylevel,va_check,use_pdc,use_vwap,use_natr_resistance,options,quick_exit,quick_exit_percent:20 \



#	--algos=algo_id:trintick_scalp_options,primary_trin,tick,use_keylevel,va_check,trin_ma_type:trima,trin_ma_period:8,options,quick_exit,quick_exit_percent:2 \
#	--algos=algo_id:stochrsi_scalp_options,primary_stochrsi,tick,trin,use_keylevel,va_check,rsi_period:14,stochrsi_period:14,stochrsi_offset:0,trin_ma_type:trima,trin_ma_period:8,options,quick_exit,quick_exit_percent:2 \
#	\
#	--algo_valid_tickers=trintick_scalp_options:SPY,QQQ \
#	--algo_valid_tickers=stochrsi_scalp_options:SPY,QQQ \
#	\
#	--algos=algo_id:TQQQ_trintick_scalp_options,primary_trin,tick,use_keylevel,keylevel_use_daily,va_check,support_resistance,trin_ma_type:hma,trin_ma_period:5,options,quick_exit,quick_exit_percent:2 \
#	--algos=algo_id:TQQQ_stochrsi_scalp_options,primary_stochrsi,tick,trin,use_keylevel,keylevel_use_daily,va_check,support_resistance,rsi_period:14,stochrsi_period:14,stochrsi_offset:0,trin_ma_type:hma,trin_ma_period:5,options,quick_exit,quick_exit_percent:2 \
#	\
#	--algo_valid_tickers=TQQQ_trintick_scalp_options:TQQQ \
#	--algo_valid_tickers=TQQQ_stochrsi_scalp_options:TQQQ \
