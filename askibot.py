#!/usr/bin/env python3
import tgbot
import logging

class AskibotTg(tgbot.Tgbot):
    def __init__(self, token):
        super().__init__(token)
        self.update_offset = 0

    def run(self):
        try:
            while True:
                for update in self.getUpdates(offset=self.update_offset, timeout=60):
                    self.handleUpdate(update)
        except KeyboardInterrupt:
            # no special exit necessary yet, just don't dump a long backtrace
            pass

    def handleUpdate(self, update):
        upid = update['update_id']
        msg = update['message']
        self.handleMessage(msg)
        self.update_offset = upid + 1

    def handleMessage(self, msg):
        if 'text' in msg:
            text = msg['text']
            commands = {
                    '/help': self.respHelp,
                    '/start': self.respStart,
            }
            cmdname = text.split(' ')[0].lower()
            if cmdname in commands:
                commands[cmdname](msg)

    def respHelp(self, msg):
        self.sendMessage(msg['chat']['id'], 'hello, world')

    def respStart(self, msg):
        self.sendMessage(msg['chat']['id'], 'please stop')



def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG, format='%(asctime)s [%(levelname)-8s] %(message)s')
    token = open('token.txt').read().strip()
    bot = AskibotTg(token)
    print(bot.getMe())
    bot.run()

if __name__ == '__main__':
    main()
