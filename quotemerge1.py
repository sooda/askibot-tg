#!/usr/bin/env python3
# -*- encoding: utf8 -*-

import pickle
from sys import argv
import collections

class TgQuote(collections.namedtuple('TgQuoteBase', 'origin msgid text adder')):
    def strip(self):
        return self

    def lower(self):
        return self

    def __contains__(self, item):
        # origin is always a user; try all of those three for easier searching
        return item in ('%s %s %s %s' % (
            self.origin.get('username', ''),
            self.origin.get('first_name', ''),
            self.origin.get('last_name', ''),
            self.text)).lower()


def main():
	a = pickle.load(open(argv[1], 'rb'))
	b = pickle.load(open(argv[2], 'rb'))
	pickle.dump(a + b, open(argv[3], 'wb'))

if __name__ == '__main__':
	main()
