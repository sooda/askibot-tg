#!/usr/bin/env python3
# -*- encoding: utf8 -*-

import pickle
import collections
import sys

# this just matches the actual version, pickle didn't like importing because namespace
class TgQuote(collections.namedtuple('TgQuoteBase', 'origin msgid text adder')):
	pass

def stringize(q):
	user = q.origin
	msg = q.text
	return "<%s (%s %s)> %s" % (user.get('username'), user.get('first_name'), user.get('last_name'), msg)

qs = pickle.load(open(sys.argv[1], 'rb'))

print("\n\n".join(map(stringize, qs)))
