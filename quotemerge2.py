#!/usr/bin/env python3
# -*- encoding: utf8 -*-

import pickle
from sys import argv
from askibot import quotemerge

def main():
	quotemerge(argv[1], argv[2], argv[3])

if __name__ == '__main__':
	main()
