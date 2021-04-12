#!/usr/bin/perl -w

# Process files created by "tda-gobot-analyze.py"

$stock = '';
$algo = '';
$days = 0;
$avg_txs = 0;
$success_rate = 0;
$fail_rate = 0;
$avg_gain = 0;
$avg_loss = 0;
$avg_gain_per_share = 0;
$rating = '';

$found = 0;

while (<>) {
	chomp($_);

	# Remove any console escape codes (text coloring)
	$_ =~ s/\x1B\[([0-9]{1,3}(;[0-9]{1,2})?)?[mGK]//g;

	# Get the stock ticker name
	if ( $_ =~ /[0-9]{1,2}-day/ )  {

		if ( $found != 0 )  {
			print "$stock,$algo,$days,$avg_txs,$success_rate,$fail_rate,$avg_gain,$avg_loss,$avg_gain_per_share,$rating\n";
		}

		$found = 1;
		$_ =~ s/Analyzing [0-9]{1,2}-day history for stock //;

		$days = $&;
		$days =~ s/Analyzing //;
		$days =~ s/\-day .+ //;

		$_ =~ s/ using .+//;
		$stock = $_;

		$algo = $&;
		$algo =~ s/ using the //;
		$algo =~ s/ algorithm://;
		next;
	}

	# Average transactions
	elsif ( $_ =~ /Average txs/ ) {
		$_ =~ s/Average txs\/day: //;
		$avg_txs = $_;
		next;
	}

	# Success rate
	elsif ( $_ =~ /Success rate/ ) {
		$_ =~ s/Success rate: //;
		$success_rate = $_;
		next;
	}

	# Fail rate
	elsif ( $_ =~ /Fail rate/ ) {
		$_ =~ s/Fail rate: //;
		$fail_rate = $_;
		next;
	}

	# Average gain
	elsif ( $_ =~ /Average gain:/ ) {
		$_ =~ s/Average gain: //;
		$_ =~ s/ \/ share//;
		$avg_gain = $_;
		next;
	}

	# Average loss
	elsif ( $_ =~ /Average loss/ ) {
		$_ =~ s/Average loss: //;
		$_ =~ s/ \/ share//;
		$avg_loss = $_;
		next;
	}

	# Average gain per share
	elsif ( $_ =~ /Average gain per share/ ) {
		$_ =~ s/Average gain per share: //;
		$avg_gain_per_share = $_;
		next;
	}

	# Rating
	elsif ( $_ =~ /Stock rating/ ) {
		$_ =~ s/Stock rating: //;
		$rating = $_;
		next;
	}

	$_ =~ s/^[\s\t]+//;
	$_ =~ s/[\s\t]+$//;
	if ( $_ eq '' || $_ !~ /,/ )  {
		next;
	}

#	# Process the verbose transaction log
#	my( $buy_price, $sell_price, $net_change) = split(/[\s\t]+/, $_);
#
#	if ( $sell_price > $buy_price )  {
#		$success++;
#	}
#	else  {
#		$fail++;
#	}

}

print "$stock,$algo,$days,$avg_txs,$success_rate,$fail_rate,$avg_gain,$avg_loss,$avg_gain_per_share,$rating\n";
