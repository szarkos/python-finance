declare lower;

input ticker_nyse = "$TRIN";     # NYSE $TRIN
input ticker_nsdq = "$TRIN/Q";   # NASDAQ $TRIN
input reversed = yes;            # Reverse $TRIN so that downtrends are <0 and vice versa

# Get current and previous candles
def trin_nyse;
def trin_nyse_1;
def cur_trin_nyse = hlc3(symbol=ticker_nyse);
def prev_trin_nyse = hlc3(symbol=ticker_nyse)[1];
trin_nyse = CompoundValue(1, if IsNaN(cur_trin_nyse) then trin_nyse[1] else cur_trin_nyse, cur_trin_nyse);
trin_nyse_1 = CompoundValue(1, if IsNaN(prev_trin_nyse) then trin_nyse_1[1] else prev_trin_nyse, prev_trin_nyse);

def trin_nsdq;
def trin_nsdq_1;
def cur_trin_nsdq = hlc3(symbol=ticker_nsdq);
def prev_trin_nsdq = hlc3(symbol=ticker_nsdq)[1];
trin_nsdq = CompoundValue(1, if IsNaN(cur_trin_nsdq) then trin_nsdq[1] else cur_trin_nsdq, cur_trin_nsdq);
trin_nsdq_1 = CompoundValue(1, if IsNaN(prev_trin_nsdq) then trin_nsdq_1[1] else prev_trin_nsdq, prev_trin_nsdq);

# Find the 1-period rate-of-change
def roc_nyse = ((trin_nyse - trin_nyse_1) / trin_nyse_1) * 100;
def roc_nsdq = ((trin_nsdq - trin_nsdq_1) / trin_nsdq_1) * 100;

# Display the EMA of the average of roc_nyse and roc_nsdq
plot PercentChg;
if reversed == yes then {
    PercentChg = MovAvgExponential( ((-roc_nyse + -roc_nsdq) / 2), 4);
} else {
    PercentChg = MovAvgExponential( ((roc_nyse + roc_nsdq) / 2), 4);
}

plot Hist = PercentChg;
Hist.SetPaintingStrategy(PaintingStrategy.HISTOGRAM);
Hist.SetLineWeight(5);

Hist.AssignValueColor(
if reversed == yes then
    if PercentChg >= 0 then
        Color.GREEN
    else
        Color.RED
else
    if PercentChg >= 0 then
        Color.RED
    else
        Color.GREEN
);

plot ZeroLine = 0;
ZeroLine.SetDefaultColor(GetColor(7));

plot oversold;
plot overbought;
if reversed == yes then {
    oversold = 1;
    overbought = -3;
} else {
    oversold = 3;
    overbought = -1;
}

oversold.SetDefaultColor(GetColor(5));
overbought.SetDefaultColor(GetColor(5));


