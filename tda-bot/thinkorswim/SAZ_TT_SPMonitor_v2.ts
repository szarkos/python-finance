declare lower;

input price = FundamentalType.HLC3;
input priceType = PriceType.MARK;

input S1 = "AAPL";
def S1_pct = 6.72 / 100;

input S2 = "MSFT";
def S2_pct = 5.97 / 100;

input S3 = "AMZN";
def S3_pct = 3.61 / 100;

input S4 = "GOOGL";
def S4_pct = 2.17 / 100;

input S5 = "GOOG";
def S5_pct = 2.02 / 100;

input S6 = "TSLA";
def S6_pct = 1.85 / 100;

input S7 = "BRK/B";
def S7_pct = 1.66 / 100;

input S8 = "NVDA";
def S8_pct = 1.66 / 100;

input S9 = "FB";
def S9_pct = 1.3 / 100;

input S10 = "UNH";
def S10_pct = 1.27 / 100;

input S11 = "JNJ";
def S11_pct = 1.24 / 100;

input S12 = "JPM";
def S12_pct = 1.11 / 100;

input S13 = "PG";
def S13_pct = 0.98 / 100;

input S14 = "V";
def S14_pct = 0.96 / 100;

input S15 = "HD";
def S15_pct = 0.94 / 100;

input S16 = "XOM";
def S16_pct = 0.88 / 100;

input S17 = "BAC";
def S17_pct = 0.83 / 100;

input S18 = "CVX";
def S18_pct = 0.82 / 100;

input S19 = "MA";
def S19_pct = 0.81 / 100;

input S20 = "PFE";
def S20_pct = 0.8 / 100;

# Get current and previous candles
def P1;
def P1_1;
def cur_P1 = Fundamental(fundamentalType=price, symbol=S1, priceType=priceType);
def prev_P1 = Fundamental(fundamentalType=price, symbol=S1, priceType=priceType)[1];
P1 = CompoundValue(1, if IsNaN(cur_P1) then P1[1] else cur_P1, cur_P1);
P1_1 = CompoundValue(1, if IsNaN(prev_P1) then P1_1[1] else prev_P1, prev_P1);

def P2;
def P2_1;
def cur_P2 = Fundamental(fundamentalType=price, symbol=S2, priceType=priceType);
def prev_P2 = Fundamental(fundamentalType=price, symbol=S2, priceType=priceType)[1];
P2 = CompoundValue(1, if IsNaN(cur_P2) then P2[1] else cur_P2, cur_P2);
P2_1 = CompoundValue(1, if IsNaN(prev_P2) then P2_1[1] else prev_P2, prev_P2);

def P3;
def P3_1;
def cur_P3 = Fundamental(fundamentalType=price, symbol=S3, priceType=priceType);
def prev_P3 = Fundamental(fundamentalType=price, symbol=S3, priceType=priceType)[1];
P3 = CompoundValue(1, if IsNaN(cur_P3) then P3[1] else cur_P3, cur_P3);
P3_1 = CompoundValue(1, if IsNaN(prev_P3) then P3_1[1] else prev_P3, prev_P3);

def P4;
def P4_1;
def cur_P4 = Fundamental(fundamentalType=price, symbol=S4, priceType=priceType);
def prev_P4 = Fundamental(fundamentalType=price, symbol=S4, priceType=priceType)[1];
P4 = CompoundValue(1, if IsNaN(cur_P4) then P4[1] else cur_P4, cur_P4);
P4_1 = CompoundValue(1, if IsNaN(prev_P4) then P4_1[1] else prev_P4, prev_P4);

def P5;
def P5_1;
def cur_P5 = Fundamental(fundamentalType=price, symbol=S5, priceType=priceType);
def prev_P5 = Fundamental(fundamentalType=price, symbol=S5, priceType=priceType)[1];
P5 = CompoundValue(1, if IsNaN(cur_P5) then P5[1] else cur_P5, cur_P5);
P5_1 = CompoundValue(1, if IsNaN(prev_P5) then P5_1[1] else prev_P5, prev_P5);

def P6;
def P6_1;
def cur_P6 = Fundamental(fundamentalType=price, symbol=S6, priceType=priceType);
def prev_P6 = Fundamental(fundamentalType=price, symbol=S6, priceType=priceType)[1];
P6 = CompoundValue(1, if IsNaN(cur_P6) then P6[1] else cur_P6, cur_P6);
P6_1 = CompoundValue(1, if IsNaN(prev_P6) then P6_1[1] else prev_P6, prev_P6);

def P7;
def P7_1;
def cur_P7 = Fundamental(fundamentalType=price, symbol=S7, priceType=priceType);
def prev_P7 = Fundamental(fundamentalType=price, symbol=S7, priceType=priceType)[1];
P7 = CompoundValue(1, if IsNaN(cur_P7) then P7[1] else cur_P7, cur_P7);
P7_1 = CompoundValue(1, if IsNaN(prev_P7) then P7_1[1] else prev_P7, prev_P7);

def P8;
def P8_1;
def cur_P8 = Fundamental(fundamentalType=price, symbol=S8, priceType=priceType);
def prev_P8 = Fundamental(fundamentalType=price, symbol=S8, priceType=priceType)[1];
P8 = CompoundValue(1, if IsNaN(cur_P8) then P8[1] else cur_P8, cur_P8);
P8_1 = CompoundValue(1, if IsNaN(prev_P8) then P8_1[1] else prev_P8, prev_P8);

def P9;
def P9_1;
def cur_P9 = Fundamental(fundamentalType=price, symbol=S9, priceType=priceType);
def prev_P9 = Fundamental(fundamentalType=price, symbol=S9, priceType=priceType)[1];
P9 = CompoundValue(1, if IsNaN(cur_P9) then P9[1] else cur_P9, cur_P9);
P9_1 = CompoundValue(1, if IsNaN(prev_P9) then P9_1[1] else prev_P9, prev_P9);

def P10;
def P10_1;
def cur_P10 = Fundamental(fundamentalType=price, symbol=S10, priceType=priceType);
def prev_P10 = Fundamental(fundamentalType=price, symbol=S10, priceType=priceType)[1];
P10 = CompoundValue(1, if IsNaN(cur_P10) then P10[1] else cur_P10, cur_P10);
P10_1 = CompoundValue(1, if IsNaN(prev_P10) then P10_1[1] else prev_P10, prev_P10);

def P11;
def P11_1;
def cur_P11 = Fundamental(fundamentalType=price, symbol=S11, priceType=priceType);
def prev_P11 = Fundamental(fundamentalType=price, symbol=S11, priceType=priceType)[1];
P11 = CompoundValue(1, if IsNaN(cur_P11) then P11[1] else cur_P11, cur_P11);
P11_1 = CompoundValue(1, if IsNaN(prev_P11) then P11_1[1] else prev_P11, prev_P11);

def P12;
def P12_1;
def cur_P12 = Fundamental(fundamentalType=price, symbol=S12, priceType=priceType);
def prev_P12 = Fundamental(fundamentalType=price, symbol=S12, priceType=priceType)[1];
P12 = CompoundValue(1, if IsNaN(cur_P12) then P12[1] else cur_P12, cur_P12);
P12_1 = CompoundValue(1, if IsNaN(prev_P12) then P12_1[1] else prev_P12, prev_P12);

def P13;
def P13_1;
def cur_P13 = Fundamental(fundamentalType=price, symbol=S13, priceType=priceType);
def prev_P13 = Fundamental(fundamentalType=price, symbol=S13, priceType=priceType)[1];
P13 = CompoundValue(1, if IsNaN(cur_P13) then P13[1] else cur_P13, cur_P13);
P13_1 = CompoundValue(1, if IsNaN(prev_P13) then P13_1[1] else prev_P13, prev_P13);

def P14;
def P14_1;
def cur_P14 = Fundamental(fundamentalType=price, symbol=S14, priceType=priceType);
def prev_P14 = Fundamental(fundamentalType=price, symbol=S14, priceType=priceType)[1];
P14 = CompoundValue(1, if IsNaN(cur_P14) then P14[1] else cur_P14, cur_P14);
P14_1 = CompoundValue(1, if IsNaN(prev_P14) then P14_1[1] else prev_P14, prev_P14);

def P15;
def P15_1;
def cur_P15 = Fundamental(fundamentalType=price, symbol=S15, priceType=priceType);
def prev_P15 = Fundamental(fundamentalType=price, symbol=S15, priceType=priceType)[1];
P15 = CompoundValue(1, if IsNaN(cur_P15) then P15[1] else cur_P15, cur_P15);
P15_1 = CompoundValue(1, if IsNaN(prev_P15) then P15_1[1] else prev_P15, prev_P15);

def P16;
def P16_1;
def cur_P16 = Fundamental(fundamentalType=price, symbol=S16, priceType=priceType);
def prev_P16 = Fundamental(fundamentalType=price, symbol=S16, priceType=priceType)[1];
P16 = CompoundValue(1, if IsNaN(cur_P16) then P16[1] else cur_P16, cur_P16);
P16_1 = CompoundValue(1, if IsNaN(prev_P16) then P16_1[1] else prev_P16, prev_P16);

def P17;
def P17_1;
def cur_P17 = Fundamental(fundamentalType=price, symbol=S17, priceType=priceType);
def prev_P17 = Fundamental(fundamentalType=price, symbol=S17, priceType=priceType)[1];
P17 = CompoundValue(1, if IsNaN(cur_P17) then P17[1] else cur_P17, cur_P17);
P17_1 = CompoundValue(1, if IsNaN(prev_P17) then P17_1[1] else prev_P17, prev_P17);

def P18;
def P18_1;
def cur_P18 = Fundamental(fundamentalType=price, symbol=S18, priceType=priceType);
def prev_P18 = Fundamental(fundamentalType=price, symbol=S18, priceType=priceType)[1];
P18 = CompoundValue(1, if IsNaN(cur_P18) then P18[1] else cur_P18, cur_P18);
P18_1 = CompoundValue(1, if IsNaN(prev_P18) then P18_1[1] else prev_P18, prev_P18);

def P19;
def P19_1;
def cur_P19 = Fundamental(fundamentalType=price, symbol=S19, priceType=priceType);
def prev_P19 = Fundamental(fundamentalType=price, symbol=S19, priceType=priceType)[1];
P19 = CompoundValue(1, if IsNaN(cur_P19) then P19[1] else cur_P19, cur_P19);
P19_1 = CompoundValue(1, if IsNaN(prev_P19) then P19_1[1] else prev_P19, prev_P19);

def P20;
def P20_1;
def cur_P20 = Fundamental(fundamentalType=price, symbol=S20, priceType=priceType);
def prev_P20 = Fundamental(fundamentalType=price, symbol=S20, priceType=priceType)[1];
P20 = CompoundValue(1, if IsNaN(cur_P20) then P20[1] else cur_P20, cur_P20);
P20_1 = CompoundValue(1, if IsNaN(prev_P20) then P20_1[1] else prev_P20, prev_P20);

#def agg = AggregationPeriod.DAY;
def roc1 = ((P1 - P1_1) / P1_1) * S1_pct;
def roc2 = ((P2 - P2_1) / P2_1) * S2_pct;
def roc3 = ((P3 - P3_1) / P3_1) * S3_pct;
def roc4 = ((P4 - P4_1) / P4_1) * S4_pct;
def roc5 = ((P5 - P5_1) / P5_1) * S5_pct;
def roc6 = ((P6 - P6_1) / P6_1) * S6_pct;
def roc7 = ((P7 - P7_1) / P7_1) * S7_pct;
def roc8 = ((P8 - P8_1) / P8_1) * S8_pct;
def roc9 = ((P9 - P9_1) / P9_1) * S9_pct;
def roc10 = ((P10 - P10_1) / P10_1) * S10_pct;
def roc11 = ((P11 - P11_1) / P11_1) * S11_pct;
def roc12 = ((P12 - P12_1) / P12_1) * S12_pct;
def roc13 = ((P13 - P13_1) / P13_1) * S13_pct;
def roc14 = ((P14 - P14_1) / P14_1) * S14_pct;
def roc15 = ((P15 - P15_1) / P15_1) * S15_pct;
def roc16 = ((P16 - P16_1) / P16_1) * S16_pct;
def roc17 = ((P17 - P17_1) / P17_1) * S17_pct;
def roc18 = ((P18 - P18_1) / P18_1) * S18_pct;
def roc19 = ((P19 - P19_1) / P19_1) * S19_pct;
def roc20 = ((P20 - P20_1) / P20_1) * S20_pct;

# Formula is (roc1 + roc2 .... ) / ( (stock1_prev_cndl / stock1_pct) + .... )
def total_roc_prelim = roc1 + roc2 + roc3 + roc4 + roc5 + roc6 + roc7 + roc8 + roc9 + roc10 + roc11 + roc12 + roc13 + roc14 + roc15 + roc16 + roc17 + roc18 + roc19 + roc20;

def prev_cndl_sum_t = (P1_1 * S1_pct) + (P2_1 * S2_pct) + (P3_1 * S3_pct) + (P4_1 * S4_pct) + (P5_1 * S5_pct) +
(P6_1 * S6_pct) + (P7_1 * S7_pct) + (P8_1 * S8_pct) + (P9_1 * S9_pct) + (P10_1 * S10_pct) + (P11_1 * S11_pct) +
(P12_1 * S12_pct) + (P13_1 * S13_pct) + (P14_1 * S14_pct) + (P15_1 * S15_pct) + (P16_1 * S16_pct) + (P17_1 * S17_pct) +
(P18_1 * S18_pct) + (P19_1 * S19_pct) + (P20_1 * S20_pct);

# Make sure then denominator is not 0 otherwise things get buggy
def prev_cndl_sum = CompoundValue(1, if prev_cndl_sum_t == 0 then prev_cndl_sum_t[1] else prev_cndl_sum_t, prev_cndl_sum_t);

def total_roc = ( total_roc_prelim / prev_cndl_sum ) * 10000000; # Yeah, the roc values are super tiny

plot PercentChg = MovAvgExponential(total_roc, 4);
plot Hist = PercentChg;
Hist.setPaintingStrategy(paintingStrategy.HISTOGRAM);
Hist.setLineWeight(5);
Hist.assignValueColor(if PercentChg >=0 then color.green else color.red);

plot ZeroLine = 0;
ZeroLine.SetDefaultColor(GetColor(7));



