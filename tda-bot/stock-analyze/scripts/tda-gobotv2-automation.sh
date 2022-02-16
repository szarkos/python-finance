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

nohup ./tda-stochrsi-gobot-v2.py --stoploss --stock_usd=20000 --stocks=${tickers} --short --singleday \
	--decr_threshold=1.25 --incr_threshold=0.5 --max_failed_txs=2 --exit_percent=0.5 \
	\
	--algos=algo_id:stackedma_macheck_kama_wma_rocstrict,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,bbands_roc_strict,bbands_kchan_ma_check,bbands_kchan_squeeze_count:10,support_resistance,use_trend,use_combined_exit,use_bbands_kchannel_xover_exit,check_etf_indicators,min_intra_natr:0.65,min_daily_natr:6 \
	--algos=algo_id:mamafama_ema-tema_bbands5_kchan-sma,primary_mama_fama,stacked_ma,stacked_ma_periods:5.8.13,stacked_ma_type:ema,stacked_ma_secondary,stacked_ma_type_secondary:tema,bbands_kchannel,bbands_kchan_squeeze_count:8,use_bbands_kchannel_xover_exit,bbands_matype:5,kchan_matype:sma,check_etf_indicators,support_resistance,use_trend,use_combined_exit,min_intra_natr:0.65,min_daily_natr:6 \
	--algos=algo_id:stackedma_kama_wma_rocstrict,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,bbands_roc_strict,bbands_kchan_squeeze_count:10,support_resistance,use_trend,use_combined_exit,use_bbands_kchannel_xover_exit,check_etf_indicators,min_intra_natr:0.65,min_daily_natr:6 \
	--algos=algo_id:stochrsi_rsstrict,primary_stochrsi,stochrsi_offset:3,dmi_simple,aroonosc,adx,support_resistance,use_natr_resistance,check_etf_indicators,check_etf_indicators_strict,adx_threshold:6,min_intra_natr:0.6,min_daily_natr:5 \
	\
	--algo_exclude_tickers=mamafama_ema-tema_bbands5_kchan-sma:${mamafama_ema_tema_bbands5_kchan_sma} \
	--algo_exclude_tickers=stackedma_kama_wma_rocstrict:${stackedma_kama_wma_rocstrict} \
	--algo_exclude_tickers=stackedma_macheck_kama_wma_rocstrict:${stackedma_kama_wma_rocstrict} \
	--algo_exclude_tickers=stochrsi_rsstrict:${stochrsi_rsstrict} \
	\
	--algos=algo_id:qqq_mesasine_strict,primary_mesa_sine,mesa_sine_strict,stacked_ma,stacked_ma_type:kama,stacked_ma_periods:5.8.13,stacked_ma_secondary,stacked_ma_type_secondary:tema,stacked_ma_periods_secondary:34.55.89,check_etf_indicators,check_etf_indicators_strict,etf_min_rs:0,etf_tickers:XLF.XLRE.XLI.XPH.XHB.XLV.XRT.XOP.XLU.XBI.KBE.XLE.SPXS.SQQQ.XLP,support_resistance,use_trend,use_combined_exit \
	--algos=algo_id:tqqq_mesasine_strict,primary_mesa_sine,mesa_sine_strict,stacked_ma,stacked_ma_type:kama,stacked_ma_periods:5.8.13,stacked_ma_secondary,stacked_ma_type_secondary:tema,stacked_ma_periods_secondary:34.55.89,check_etf_indicators,check_etf_indicators_strict,etf_min_rs:0,etf_tickers:XLC.XLP.XLV,support_resistance,use_trend,use_combined_exit \
	--algos=algo_id:qqq_mesasine,primary_mesa_sine,stacked_ma,stacked_ma_type:kama,stacked_ma_periods:5.8.13,stacked_ma_secondary,stacked_ma_type_secondary:tema,stacked_ma_periods_secondary:34.55.89,check_etf_indicators,check_etf_indicators_strict,etf_min_rs:0,etf_tickers:XLF.XLRE.XLI.XPH.XHB.XLV.XRT.XOP.XLU.XBI.KBE.XLE.KIE.SPXS.SQQQ.XLP,support_resistance,use_trend,use_combined_exit \
	--algos=algo_id:tqqq_mesasine,primary_mesa_sine,stacked_ma,stacked_ma_type:kama,stacked_ma_periods:5.8.13,stacked_ma_secondary,stacked_ma_type_secondary:tema,stacked_ma_periods_secondary:34.55.89,check_etf_indicators,check_etf_indicators_strict,etf_min_rs:0,etf_tickers:XLC.XLP.XLV,support_resistance,use_trend,use_combined_exit \
	--algos=algo_id:xop_mesasine,primary_mesa_sine,stacked_ma,stacked_ma_type:kama,stacked_ma_periods:5.8.13,stacked_ma_secondary,stacked_ma_type_secondary:tema,stacked_ma_periods_secondary:34.55.89,check_etf_indicators,check_etf_indicators_strict,etf_min_rs:0,etf_tickers:TQQQ.XSD,support_resistance,use_trend,use_combined_exit \
	\
	--algo_valid_tickers=qqq_mesasine_strict:QQQ \
	--algo_valid_tickers=qqq_mesasine:QQQ \
	--algo_valid_tickers=tqqq_mesasine_strict:TQQQ \
	--algo_valid_tickers=tqqq_mesasine:TQQQ \
	--algo_valid_tickers=xop_mesasine:XOP \
	\
	--etf_tickers_allowtrade=QQQ,TQQQ,XOP \
	\
	--stacked_ma_periods_primary=8,13,21 --stacked_ma_periods=34,55,89 --stacked_ma_periods_secondary=34,55,89 \
	--check_etf_indicators --etf_min_rs=4 --etf_min_natr=0.1 \
	--bbands_kchannel_offset=0.15 --bbands_kchan_squeeze_count=10 --bbands_roc_threshold=0 \
	--daily_atr_period=3 --variable_exit --lod_hod_check --use_combined_exit \
	--rsi_high_limit=75 --rsi_low_limit=25 --aroonosc_with_macd_simple \
	--weekly_ifile=stock-analyze/weekly-csv/TICKER-weekly-2019-2021.pickle \
	--tx_log_dir=TX_LOGS_v2 1> logs/gobot-v2.log 2>&1 &

disown

# Doghouse
#	--algos=algo_id:mamafama_kama-vwma_bbands1_kchan-ema,primary_mama_fama,stacked_ma,stacked_ma_periods:5.8.13,stacked_ma_type:kama,stacked_ma_secondary,stacked_ma_type_secondary:vwma,bbands_kchannel,bbands_kchan_squeeze_count:8,use_bbands_kchannel_xover_exit,bbands_matype:1,kchan_matype:ema,check_etf_indicators,support_resistance,use_trend,use_combined_exit,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stackedma_kama_wma_rsstrict_rocstrict,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,bbands_roc_strict,bbands_kchan_squeeze_count:10,support_resistance,use_trend,use_combined_exit,use_bbands_kchannel_xover_exit,check_etf_indicators,check_etf_indicators_strict,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stackedma_kama_trima_mamafama,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma_periods_primary:5.8.13,stacked_ma,stacked_ma_type:trima,mama_fama,bbands_kchannel,support_resistance,use_trend,use_combined_exit,use_bbands_kchannel_xover_exit,check_etf_indicators,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stackedma_kama_wma,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,support_resistance,use_trend,use_combined_exit,use_bbands_kchannel_xover_exit,check_etf_indicators,min_intra_natr:0.65,min_daily_natr:6 \

# Older algo combinations
#	--algos=algo_id:mama-fama_kama-trima_bbands5_kchan-sma,primary_mama_fama,stacked_ma,stacked_ma_periods:5.8.13,stacked_ma_type:kama,stacked_ma_secondary,stacked_ma_type_secondary:trima,bbands_kchannel,bbands_kchan_squeeze_count:8,use_bbands_kchannel_xover_exit,bbands_matype:5,kchan_matype:sma,check_etf_indicators,support_resistance,use_trend,use_combined_exit,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:mama-fama_wma_rsstrict_rocstrict,primary_mama_fama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,bbands_roc_strict,bbands_kchan_squeeze_count:10,support_resistance,use_trend,use_combined_exit,use_bbands_kchannel_xover_exit,check_etf_indicators,check_etf_indicators_strict,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stackedma_kama_wma_bbands-mama_kchan-hma,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,bbands_matype:7,kchan_matype:hma,support_resistance,use_trend,use_combined_exit,use_bbands_kchannel_xover_exit,check_etf_indicators,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stochrsi,primary_stochrsi,stochrsi_offset:3,dmi_simple,aroonosc,adx,support_resistance,use_natr_resistance,adx_threshold:6,min_intra_natr:0.15,min_daily_natr:6 \
#	--algos=algo_id:stackedma_kama_5m,primary_stacked_ma,use_bbands_kchannel_5m,stacked_ma_type_primary:kama,bbands_kchannel,bbands_period:15,kchannel_period:15,kchannel_atr_period:15,bbands_kchan_squeeze_count:20,bbands_kchannel_offset:0.45,support_resistance,min_intra_natr:0.65,min_daily_natr:6 \
#	--algos=algo_id:stackedma_kama_wma,primary_stacked_ma,stacked_ma_type_primary:kama,stacked_ma,stacked_ma_type:wma,bbands_kchannel,support_resistance,min_intra_natr:0.65,min_daily_natr:6 \

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

