# python-finance

TODO

Add short sell capability:
 - Write new functions shortsell_stock_marketprice() and buytocover_stock_marketprice()
   - I think the json is mostly the same, except "instruction" will be "SELL_SHORT" and "BUY_TO_COVER"
     respectively. Need to test this.
 - Add --short option to both tda-gobot.py and tda-rsi-gobot.py to enable short sale
 - Also add --short option to tda-sell-stock.py in case we immediately need to initiate a BUY_TO_COVER
 - Fixup both tda-gobot.py and tda-rsi-gobot.py to enable short sale algorithm
   - Add new "signal_mode" options "short" and "buy_to_cover"
   - Essentially turns the algorithm upside down
 - Enable algorithms to tda-rsi-gobot.py --analyze as well
 - See if we can find an automated way to determine if a stock is ETB (easy to buy) to avoid higher fees


