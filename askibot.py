#!/usr/bin/env python3
import tgbot
import logging
import socket
import threading
import time
import random

TOKEN_TXT = 'token.txt'
KEULII_TXT = 'keulii.txt'
QUOTES_DIR = 'quotes'
MOPOPOSTERPORT = 6688

class Mopoposter:
    def __init__(self, port, sendfunc):
        self.port = port
        self.sendfunc = sendfunc

    def start(self):
        self.thread = threading.Thread(target=self.acceptLoop)
        self.thread.start()

    def acceptLoop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket = server
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((socket.gethostname(), self.port))
        server.listen(5)
        while True:
            (clientsocket, address) = server.accept()
            self.handleConnection(clientsocket)

    def handleConnection(self, sock):
        msg = sock.recv(1024)
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        self.sendfunc(msg)

    def stop(self):
        self.serversocket.shutdown(socket.SHUT_RDWR)
        self.thread.join()

class QuotesBase:
    TIME_LIMIT = 15*60
    ERR_MSG = 'Elä quottaile liikaa'

    def __init__(self):
        self.last_requests = {}

    def get(self, chan_id, user_id, search_term):
        now = time.time()
        last_user, last_time = self.last_requests.get(chan_id, (None, 0))
        if user_id == last_user and now - last_time < self.TIME_LIMIT:
            return (user_id, self.ERR_MSG)

        msg = self.search(chan_id, search_term)
        if msg is not None:
            self.last_requests[chan_id] = (user_id, now)
            return (chan_id, msg)

        return (chan_id, None)

    def search(self, chan_id, term):
        term = term.lower().strip()
        lines = [x for x in self.listQuotes(chan_id) if term in x.lower().strip()]
        return random.choice(lines).strip() if len(lines) else None

    def listQuotes(self):
        raise NotImplementedError

class Quotes(QuotesBase):
    def __init__(self, quotes_dir):
        super().__init__()
        self.quotefile_dir = quotes_dir

    def listQuotes(self, chan_id):
        try:
            return list(open(self.quotes_dir + '/' + chan_id))
        except IOError:
            return []

    def addQuote(self, chan_id, user_id, msg):
        with open(self.quotes_dir + '/' + chan_id, 'w') as fh:
            fh.write(msg + '\n')

class Keulii(QuotesBase):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def listQuotes(self, chan_id):
        try:
            return list(open(self.filename))
        except IOError:
            return []

class AskibotTg(tgbot.Tgbot):
    def __init__(self, token, keuliifilename, mopoposterport, quotesdir):
        super().__init__(token)
        self.update_offset = 0
        self.mopoposter_broadcast = {}
        self.mopoposter = Mopoposter(mopoposterport, self.sendMopoposter)
        self.keulii = Keulii(keuliifilename)

    def run(self):
        try:
            self.mopoposter.start()
            self.loopUpdates()
        except KeyboardInterrupt:
            pass

        self.mopoposter.stop()

    def sendMopoposter(self, msg):
        for chatid in self.mopoposter_broadcast.keys():
            self.sendMessage(chatid, msg)

    def loopUpdates(self):
        while True:
            for update in self.getUpdates(offset=self.update_offset, timeout=60):
                self.handleUpdate(update)

    def handleUpdate(self, update):
        upid = update['update_id']
        msg = update['message']
        self.handleMessage(msg)
        self.update_offset = upid + 1

    def handleMessage(self, msg):
        if 'text' in msg:
            text = msg['text']
            commands = {
                    '/help': self.cmdHelp,
                    '/start': self.cmdStart,
                    '/keulii': self.cmdKeulii,
                    '/keulii-register': self.cmdKeuliiRegister,
                    '/keulii-unregister': self.cmdKeuliiUnRegister,
                    '/q': self.cmdQuote,
                    '/addq': self.cmdAddQuote,
            }
            cmdname = text.split(' ')[0].lower()
            if cmdname in commands:
                commands[cmdname](msg)

    def cmdHelp(self, msg):
        self.sendMessage(msg['chat']['id'], 'hello, world')

    def cmdStart(self, msg):
        self.sendMessage(msg['chat']['id'], 'please stop')

    def cmdKeulii(self, msg):
        target, response = self.keulii.get(msg['chat']['id'], msg['from']['id'],
                msg['text'][len('/keulii '):])
        if response is not None:
            self.sendMessage(target, response)

    def cmdKeuliiRegister(self, msg):
        chat_id = msg['chat']['id']
        user_id = msg['from']['id']
        title = msg['chat']['title'] if 'title' in msg['chat'] else msg['chat']['username']
        if self.mopoposter_broadcast.get(chat_id, None):
            self.sendMessage(user_id, 'Pöh, keuliiviestit jo rekisteröity (' + title + ')')
        else:
            self.mopoposter_broadcast[chat_id] = user_id
            self.sendMessage(user_id, 'OK, keuliiviestit rekisteröity: ' + title)

    def cmdKeuliiUnRegister(self, msg):
        chat_id = msg['chat']['id']
        user_id = msg['from']['id']
        title = msg['chat']['title'] if 'title' in msg['chat'] else msg['chat']['username']
        registrar = self.mopoposter_broadcast.get(chat_id, None)
        if registrar == user_id:
            del self.mopoposter_broadcast[chat_id]
            self.sendMessage(user_id, 'OK, keuliiviestejä ei enää lähetetä: ' + title)
        elif registrar is None:
            self.sendMessage(user_id, 'Pöh, keuliiviestejä ei rekisteröity (' + title + ')')
        else:
            self.sendMessage(user_id, 'Pöh, keuliiviestit on rekisteröinyt joku muu (' + title + ')')

    def cmdQuote(self, msg):
        # FIXME
        pass

    def cmdAddQuote(self, msg):
        # FIXME
        pass

def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG, format='%(asctime)s [%(levelname)-8s] %(message)s')
    token = open(TOKEN_TXT).read().strip()
    bot = AskibotTg(token, KEULII_TXT, MOPOPOSTERPORT, QUOTES_DIR)
    print(bot.getMe())
    bot.run()

if __name__ == '__main__':
    main()
