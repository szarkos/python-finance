#!/bin/bash

time_wait=${1-"1"}

# This is just a small script to kick off the gobot
parent_path=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "${parent_path}/../.."

echo "CWD is `pwd`"
echo "Sleeping $time_wait seconds..."
sleep $time_wait

source ./stock-analyze/tickers.conf
tickers=$CUR_SET

nohup ./tda-stochrsi-gobot-v2.py --stoploss --stock_usd=25000 --stocks=${tickers} --short --singleday \
	--decr_threshold=1.6 --incr_threshold=0.5 --max_failed_txs=2 --exit_percent=0.5 \
	\
	--algos=algo_id:main,primary_stochrsi,stochrsi_offset:3,dmi_simple,aroonosc,adx,support_resistance,use_natr_resistance,adx_threshold:6,min_intra_natr:0.15,min_daily_natr:6 \
	--algos=algo_id:stackedma_kama,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,support_resistance,min_intra_natr:0.65,min_daily_natr:6 \
	\
	--algo_valid_tickers=main:$HIGH_NATR \
	--algo_valid_tickers=stackedma_kama:$HIGH_NATR \
	\
	--stacked_ma_periods_primary=8,13,21 --stacked_ma_periods=34,55,89 \
	--bbands_kchannel_offset=0.15 --bbands_kchan_squeeze_count=8 \
	--rsi_high_limit=75 --rsi_low_limit=25 --stochrsi_offset=3 --daily_atr_period=3  \
	--aroonosc_with_macd_simple --variable_exit --lod_hod_check \
	--weekly_ifile=stock-analyze/weekly-csv/TICKER-weekly-2019-2021.pickle \
	--daily_ifile=stock-analyze/daily-csv/TICKER-daily-2019-2021.pickle \
	--tx_log_dir=TX_LOGS_v2 1> logs/gobot-v2.log 2>&1 &

disown


# Other algos - TBD
#	--algos=algo_id:stackedma_sma,primary_stacked_ma,stacked_ma_type_primary:sma,bbands_kchannel,support_resistance,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stackedma_vwma,primary_stacked_ma,stacked_ma_type_primary:vwma,bbands_kchannel,support_resistance,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stackedma_wma,primary_stacked_ma,stacked_ma_type_primary:wma,bbands_kchannel,support_resistance,min_intra_natr:0.45,min_daily_natr:6 \
#	--algos=algo_id:stackedma_sma_vwma,primary_stacked_ma,stacked_ma,stacked_ma_type_primary:sma,stacked_ma_type:vwma,bbands_kchannel,support_resistance,min_intra_natr:0.45,min_daily_natr:6 \
#
#	--algos=algo_id:main2,primary_stochrsi,stochrsi_offset:6,dmi_simple,aroonosc,adx,support_resistance,use_natr_resistance,adx_threshold:6,supertrend,min_daily_natr:3 \
#	--algos=primary_stochrsi,mfi,dmi_simple,aroonosc,adx,support_resistance,adx_threshold:6 \
#	--algos=primary_stochrsi,dmi_simple,aroonosc,adx,support_resistance,adx_threshold:6,stochrsi_offset:12 \
#	--algos=primary_stochrsi,mfi,aroonosc,adx,support_resistance,mfi_high_limit:95,mfi_low_limit:5,adx_threshold:20,adx_period:48 \
#	--algos=primary_stochrsi,rsi,mfi,adx,support_resistance,adx_threshold:20,mfi_high_limit:95,mfi_low_limit:5 \


# "Portfolio-based" algos - TBD
#	--algos=algo_id:stochrsi_stochmfi_chop_simple,\
#primary_stochrsi,stochmfi,chop_simple,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_chop_index,\
#primary_stochrsi,stochmfi,chop_index,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_chop_simple_mfi,\
#primary_stochrsi,stochmfi,chop_simple,mfi,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_chop_index_mfi,\
#primary_stochrsi,stochmfi,chop_index,mfi,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_macd,\
#primary_stochrsi,stochmfi,macd,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#macd_short_period:42,macd_long_period:52,macd_signal_period:5,macd_offset:0.00475,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4\
#	\
#	--algos=algo_id:stochrsi_stochmfi_macd_chop_simple,\
#primary_stochrsi,stochmfi,macd,chop_simple,adx,support_resistance,\
#rsi_high_limit:80,rsi_low_limit:20,stochmfi_period:128,stochrsi_offset:1.5,\
#macd_short_period:42,macd_long_period:52,macd_signal_period:5,macd_offset:0.00475,\
#adx_threshold:7,max_daily_natr:3.5,min_intra_natr:0.15,max_intra_natr:0.4 \
#	\
#	--algo_valid_tickers=stochrsi_stochmfi_chop_simple:LOW,C,WDC,RTX,TPR,ZM,NLOK,IR,MSFT,GIS,CRWD,WELL,VTR,TXN,GILD,CF,CAG \
#	--algo_valid_tickers=stochrsi_stochmfi_chop_index:MT,MS,PYPL,MRVL,ABNB,BX,BP,GLW,FITB,BIDU,BEN,ZM,RCL,HUN,GM,DISCA,AVTR,INTC,DDOG \
#	--algo_valid_tickers=stochrsi_stochmfi_chop_simple_mfi:MT,OKE,FITB,AIG,ADI,RCL,LOW,ZM,TPR,GIS,DIS,DBX,CAT \
#	--algo_valid_tickers=stochrsi_stochmfi_chop_index_mfi:UBER,XOM,MOS,BEN,ATVI,WFC,PYPL,MS,CFG,AAPL \
#	--algo_valid_tickers=stochrsi_stochmfi_macd:BA,FB,UNH,EXPE \
#	--algo_valid_tickers=stochrsi_stochmfi_macd_chop_simple:BA,FB,UNH,EXPE \

