#!/usr/bin/env python3
# -*- encoding: utf8 -*-
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
        self.serversocket = None
        self.thread = None

    def start(self):
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serversocket.bind((socket.gethostname(), self.port))
        self.serversocket.listen(5)

        self.thread = threading.Thread(target=self.acceptLoop)
        self.thread.start()

    def acceptLoop(self):
        while True:
            try:
                (clientsocket, address) = self.serversocket.accept()
            except OSError as err:
                if err.errno == 22:
                    # invalid argument, it closed
                    break
                raise

            self.handleConnection(clientsocket)

    def handleConnection(self, sock):
        msg = sock.recv(1024)
        sock.shutdown(socket.SHUT_RDWR)
        sock.close()
        self.sendfunc(msg)

    def stop(self):
        if self.serversocket:
            self.serversocket.shutdown(socket.SHUT_RDWR)
            self.serversocket.close()
        if self.thread:
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
            with open(self.quotes_dir + '/' + chan_id) as fh:
                return list(fh)
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
            with open(self.filename) as fh:
                return list(fh)
        except IOError:
            return []

class AskibotTg:
    def __init__(self, connection, keuliifilename, mopoposterport, quotesdir):
        self.conn = connection
        self.update_offset = 0
        self.mopoposter_broadcast = {}
        self.mopoposter = Mopoposter(mopoposterport, self.sendMopoposter)
        self.keulii = Keulii(keuliifilename)
        self.running = False

    def helpMsg(self):
        return '''Olen ASkiBot.

/keulii TEKSTI: hae mopopostereista tekstinpätkää, teksti voi olla tyhjä.
/mopoposter VIESTI: postaa mopoposteri tietokantaan. HUOM: älä käytä tätä turhuuksiin, vaan harvinaisiin herkkuihin joista täytyy jättää jälki jälkipolville sekä välitön viesti irkkiin ja rekisteröityneille tg-ryhmille.
/keulii-register: rekisteröi tämä kanava reaaliaikaiseksi mopoposterikuuntelijaksi.
/keulii-unregister: kumoa rekisteröinti, viestejä ei enää tule.

Bottia ylläpitää sooda.
'''

    def run(self):
        self.running = True
        try:
            self.mopoposter.start()
            self.loopUpdates()
        except KeyboardInterrupt:
            pass

        self.mopoposter.stop()

    def stop(self):
        # just for the tests
        self.running = False

    def sendMopoposter(self, msg):
        for chatid in self.mopoposter_broadcast.keys():
            self.conn.sendMessage(chatid, msg)

    def loopUpdates(self):
        while self.running:
            for update in self.conn.getUpdates(offset=self.update_offset, timeout=60):
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
        self.conn.sendMessage(msg['chat']['id'], self.helpMsg())

    def cmdStart(self, msg):
        self.conn.sendMessage(msg['chat']['id'], 'please stop')

    def cmdKeulii(self, msg):
        target, response = self.keulii.get(msg['chat']['id'], msg['from']['id'],
                msg['text'][len('/keulii '):])
        if response is not None:
            self.conn.sendMessage(target, response)

    def cmdKeuliiRegister(self, msg):
        chat_id = msg['chat']['id']
        user_id = msg['from']['id']
        title = msg['chat']['title'] if 'title' in msg['chat'] else msg['chat']['username']
        if self.mopoposter_broadcast.get(chat_id, None):
            self.conn.sendMessage(user_id, 'Pöh, keuliiviestit jo rekisteröity (' + title + ')')
        else:
            self.mopoposter_broadcast[chat_id] = user_id
            self.conn.sendMessage(user_id, 'OK, keuliiviestit rekisteröity: ' + title)

    def cmdKeuliiUnRegister(self, msg):
        chat_id = msg['chat']['id']
        user_id = msg['from']['id']
        title = msg['chat']['title'] if 'title' in msg['chat'] else msg['chat']['username']
        registrar = self.mopoposter_broadcast.get(chat_id, None)
        if registrar == user_id:
            del self.mopoposter_broadcast[chat_id]
            self.conn.sendMessage(user_id, 'OK, keuliiviestejä ei enää lähetetä: ' + title)
        elif registrar is None:
            self.conn.sendMessage(user_id, 'Pöh, keuliiviestejä ei rekisteröity (' + title + ')')
        else:
            self.conn.sendMessage(user_id, 'Pöh, keuliiviestit on rekisteröinyt joku muu (' + title + ')')

    def cmdQuote(self, msg):
        # FIXME
        pass

    def cmdAddQuote(self, msg):
        # FIXME
        pass

def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG, format='%(asctime)s [%(levelname)-8s] %(message)s')
    token = open(TOKEN_TXT).read().strip()
    bot = AskibotTg(tgbot.TgbotConnection(token), KEULII_TXT, MOPOPOSTERPORT, QUOTES_DIR)
    print(bot.conn.getMe())
    bot.run()

if __name__ == '__main__':
    main()
