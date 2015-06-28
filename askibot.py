#!/usr/bin/env python3
import tgbot
import logging

class AskibotTg(tgbot.Tgbot):
    def __init__(self, token):
        super().__init__(token)

def main():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)-8s] %(message)s')
    token = open('token.txt').read().strip()
    print(AskibotTg(token).getMe())

if __name__ == '__main__':
    main()
