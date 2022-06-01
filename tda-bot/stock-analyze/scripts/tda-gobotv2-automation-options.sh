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

# SP Monitor tickers and weights
SPMON_SPY='AAPL:6.57+MSFT:5.74+AMZN:2.82+GOOGL:2.03+GOOG:1.88+TSLA:1.79+BRK.B:1.69+JNJ:1.39+UNH:1.34+FB:1.34+NVDA:1.27+XOM:1.16+JPM:1.07+PG:1.05+V:1+CVX:0.98+HD:0.90+MA:0.87+PFE:0.85+ABBV:0.81'
SPMON_QQQ='AAPL:12.359+MSFT:10.422+AMZN:6.027+GOOG:3.798+TSLA:3.777+FB:3.683+GOOGL:3.606+NVDA:3.233+PEP:2.049+AVGO:2.032+CMCSA:1.735+ADBE:1.721+COST:1.686+CSCO:1.629+INTC:1.549+TMUS:1.438+TXN:1.432+AMD:1.39+QCOM:1.354+AMGN:1.259'

# The list of tickers is contained in the $CUR_SET variable in tickers.conf
mkdir ./logs 2>/dev/null
source ./stock-analyze/tickers.conf
tickers=$CUR_SET
tickers="SPY,QQQ,TQQQ"

nohup ./tda-gobot-v2.py --stoploss --stocks=${tickers} --short --multiday \
	--singleday --unsafe --last_hour_block=30 --fake \
	--decr_threshold=0.2 --incr_threshold=0.25 --exit_percent=0.4 --max_failed_txs=5 --stock_usd=20000 \
	\
	--options_decr_threshold=12 --options_incr_threshold=2.5 --options_exit_percent=10 --options_usd=2000 \
	--otm_level=1 --near_expiration --start_day_offset=1 \
	--resist_pct_dynamic --price_resistance_pct=0.25 --price_support_pct=0.25 \
	\
	--account_number=252298311 --passcode_prefix=sazarkos --consumer_key_prefix=sazarkos --token_fname=sazarkos_tda.pickle --tdaapi_token_fname=sazarkos_tda2.pickle \
	\
	--time_sales_kl_size_threshold=7500 --time_sales_size_max=999999 \
	--use_keylevel --last_hour_threshold=4 --sp_monitor_threshold=1.5 \
	\
	--algos=algo_id:SPY_sp_monitor_tsalgo_options,primary_sp_monitor,sp_monitor_tickers:${SPMON_SPY},time_sales_algo,time_sales_use_keylevel,time_sales_size_threshold:3000,va_check,options,quick_exit,quick_exit_percent:7 \
	--algos=algo_id:SPY_mama_spmon_tsalgo_options,primary_mama_fama,sp_monitor,sp_monitor_tickers:${SPMON_SPY},time_sales_algo,time_sales_use_keylevel,time_sales_size_threshold:3000,va_check,options,quick_exit,quick_exit_percent:7 \
	\
	--algos=algo_id:QQQ_sp_monitor_tsalgo_options,primary_sp_monitor,sp_monitor_tickers:${SPMON_QQQ},time_sales_algo,time_sales_use_keylevel,time_sales_size_threshold:3000,va_check,options,quick_exit,quick_exit_percent:7 \
	--algos=algo_id:QQQ_mama_spmon_tsalgo_options,primary_mama_fama,sp_monitor,sp_monitor_tickers:${SPMON_QQQ},time_sales_algo,time_sales_use_keylevel,time_sales_size_threshold:3000,va_check,options,quick_exit,quick_exit_percent:7 \
	\
	--algos=algo_id:TQQQ_sp_monitor_tsalgo_options,primary_sp_monitor,sp_monitor_tickers:${SPMON_QQQ},time_sales_algo,time_sales_use_keylevel,va_check,time_sales_size_threshold:7500,time_sales_size_max:20000,time_sales_kl_size_threshold:45000,time_sales_kl_size_max:80000,time_sales_large_tx_threshold:22000,time_sales_large_tx_max:80000,options,quick_exit,quick_exit_percent:7 \
	--algos=algo_id:TQQQ_mama_spmon_tsalgo_options,primary_mama_fama,sp_monitor,sp_monitor_tickers:${SPMON_QQQ},time_sales_algo,time_sales_use_keylevel,va_check,time_sales_size_threshold:7500,time_sales_size_max:20000,time_sales_kl_size_threshold:45000,time_sales_kl_size_max:80000,time_sales_large_tx_threshold:22000,time_sales_large_tx_max:80000,options,quick_exit,quick_exit_percent:7 \
	\
	--algo_valid_tickers=SPY_sp_monitor_tsalgo_options:SPY \
	--algo_valid_tickers=SPY_mama_spmon_tsalgo_options:SPY \
	--algo_valid_tickers=QQQ_sp_monitor_tsalgo_options:QQQ \
	--algo_valid_tickers=QQQ_mama_spmon_tsalgo_options:QQQ \
	--algo_valid_tickers=TQQQ_sp_monitor_tsalgo_options:TQQQ \
	--algo_valid_tickers=TQQQ_mama_spmon_tsalgo_options:TQQQ \
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
