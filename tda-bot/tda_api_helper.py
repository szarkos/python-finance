#!/usr/bin/python3 -u

# tda-api is used for both HTTP and streaming client
# https://tda-api.readthedocs.io/en/stable
import tda as tda_api
from tda.client import Client

import json


def get_watchlist_id( tda_client=None, tda_account=None, watchlist_name=None ):

	if ( tda_client == None or tda_account == None or watchlist_name == None ):
		return None

	watchlists = tda_client.get_watchlists_for_single_account(tda_account)
	watchlists = watchlists.json()

	for list in watchlists:
		if ( list['name'] == watchlist_name ):
			return list['watchlistId']

	return None


def delete_watchlist_byname( tda_client=None, tda_account=None, watchlist_name=None ):

	if ( tda_client == None or tda_account == None or watchlist_name == None ):
		return False

	watchlist_id = get_watchlist_id(tda_client, tda_account, watchlist_name)
	if ( watchlist_id == None ):
		return False

	tda_client.delete_watchlist( tda_account, watchlist_id )

	return True

