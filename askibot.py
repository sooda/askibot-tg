#!/usr/bin/env python3
# -*- encoding: utf8 -*-

"""ASkiBot, cloned from IRC to TG because newfags can't even."""

import tgbot
import logging
import socket
import threading
import time
import random
import errno

TOKEN_TXT = 'token.txt'
KEULII_TXT = 'keulii.txt'
QUOTES_DIR = 'quotes'
MOPOPOSTERPORT = 6688

class Mopoposter:
    """Simple message receiver on a tcp socket.

    Keulii messages go here too in realtime.
    They get logged to a file elsewhere.

    Listen for messages on new connections.
    One message per connection, closed automatically.
    Messages sent to a callback.
    """
    ENCODING = 'latin-1'
    def __init__(self, port, sendfunc):
        self.port = port
        self.sendfunc = sendfunc
        self.serversocket = None
        self.thread = None

    def start(self):
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serversocket.bind(('127.0.0.1', self.port))
        self.serversocket.listen(20)

        self.thread = threading.Thread(target=self.acceptLoop)
        self.thread.start()

    def acceptLoop(self):
        while True:
            try:
                (clientsocket, address) = self.serversocket.accept()
            except OSError as err:
                if err.errno == errno.EINVAL:
                    # invalid argument, servsocket closed
                    break
                if err.errno == errno.EBADF:
                    # bad file descriptor also equals to closing
                    break
                raise

            self.handleConnection(clientsocket)

    def handleConnection(self, sock):
        sock.settimeout(5.0)
        try:
            msg = sock.recv(1024)
        except socket.timeout:
            # just clean up
            pass
        else:
            if len(msg) > 0:
                self.sendfunc(msg.decode(self.ENCODING))
        finally:
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()

    def stop(self):
        if self.serversocket:
            self.serversocket.shutdown(socket.SHUT_RDWR)
            self.serversocket.close()
        if self.thread:
            self.thread.join()

class QuotesBase:
    """Get a random quote for a chat channel."""
    TIME_LIMIT = 15*60
    ERR_MSG = 'Elä quottaile liikaa'

    def __init__(self):
        self.last_requests = {}

    def get(self, chan_id, user_id, search_term):
        """Public api to get one message; search term is for whole lines.

        The number of gets is restricted to one within the time limit for a
        single user, unless another user asks for one; then the limit starts
        for that user."""
        now = time.time()
        last_user, last_time = self.last_requests.get(chan_id, (None, 0))
        if user_id == last_user and now - last_time < self.TIME_LIMIT:
            return (user_id, self.ERR_MSG)

        msg = self._search(chan_id, search_term)
        # the user can try again if nothing was found
        if msg is not None:
            self.last_requests[chan_id] = (user_id, now)
            return (chan_id, msg)

        return (chan_id, None)

    def _search(self, chan_id, term):
        """Find that message on a chat channel."""
        term = term.lower().strip()
        lines = [x for x in self._listQuotes(chan_id)
                if term in x.lower().strip()]
        return random.choice(lines).strip() if len(lines) else None

    def _listQuotes(self):
        """Subclasses should do this"""
        raise NotImplementedError

class Keulii(QuotesBase):
    """One global quotefile for all chats.

    Time limit is still per chat.
    Adding not supported, since it's done elsewhere.
    They're just read in here.
    """
    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def _listQuotes(self, chan_id):
        try:
            # FIXME utf8
            with open(self.filename, encoding='latin-1') as fh:
                return list(fh)
        except IOError:
            return []

class Quotes(QuotesBase):
    """Unique quote file for each chat."""
    def __init__(self, quotefile_dir):
        super().__init__()
        self.quotefile_dir = quotefile_dir

    def _listQuotes(self, chan_id):
        try:
            with open(self.quotefile_dir + '/' + chan_id) as fh:
                return list(fh)
        except IOError:
            return []

    def addQuote(self, chan_id, msg):
        with open(self.quotefile_dir + '/' + chan_id, 'a') as fh:
            fh.write(msg + '\n')

class AskibotTg:
    def __init__(self, connection, keuliifilename, mopoposterport, quotesdir):
        self.conn = connection
        self.update_offset = 0
        self.mopoposter_broadcast = {}
        self.mopoposter = Mopoposter(mopoposterport, self.sendMopoposter)
        self.keulii = Keulii(keuliifilename)
        self.running = False
        me = self.conn.getMe()
        self.username = me['username']

    def helpMsg(self):
        return '''Olen ASkiBot, killan irkistä tuttu robotti. Living tissue over metal endoskeleton.

/keulii HAKUTEKSTI - Hae mopopostereista tekstinpätkää, hakutekstillä tai ilman.
/keuliiregister - Rekisteröi tämä kanava reaaliaikaiseksi mopoposterikuuntelijaksi.
/keuliiunregister - Kumoa rekisteröinti, viestejä ei enää tule. Sallittu vain rekisteröijälle ja ylläpitäjälle.

Bottia ylläpitää sooda.
'''
# TODO:
#/mopoposterpost VIESTI - Lähetä mopoposteri tietokantaan. HUOM: älä käytä lähetystä turhuuksiin, vaan harvinaisiin herkkuihin joista täytyy jättää jälki jälkipolville sekä välitön viesti irkkiin ja rekisteröityneille tg-ryhmille.
#
#/q HAKUTEKSTI - kuin mopoposter, mutta kanavakohtaisille quoteille.
#/addq VIESTI - lisää quote tälle kanavalle.

    def run(self):
        """Start the main loop that goes on until user ^C's this."""
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
        """Got a message, broadcast it to the listeners."""
        for chatid in self.mopoposter_broadcast.keys():
            self.conn.sendMessage(chatid, msg)

    def loopUpdates(self):
        while self.running:
            # btw, looks like the server timeouts with status ok and an empty
            # result set after just 20 seconds
            for update in self.conn.getUpdates(
                    offset=self.update_offset, timeout=60):
                self.handleUpdate(update)

    def handleUpdate(self, update):
        """Got one line from the server."""
        upid = update['update_id']
        msg = update['message']
        self.handleMessage(msg)
        self.update_offset = upid + 1

    def handleMessage(self, msg):
        """Manage the message itself; just pass it around to a handler."""
        if 'text' in msg:
            text = msg['text']
            commands = {
                    '/help': self.cmdHelp,
                    '/start': self.cmdStart,
                    '/keulii': self.cmdKeulii,
                    '/keuliiregister': self.cmdKeuliiRegister,
                    '/keuliiunregister': self.cmdKeuliiUnRegister,
                    '/mopoposterpost': self.cmdMopoposterPost,
                    '/q': self.cmdQuote,
                    '/addq': self.cmdAddQuote,
            }

            try:
                cmdname, args = text.split(' ', 1)
            except ValueError:
                # no args
                cmdname = text
                args = ''
            # tg specifies that /cmd@nick should work just for us
            if '@' in cmdname:
                cmdname, target = cmdname.split('@', 1)
                if target.lower() != self.username.lower():
                    return
            cmdname = cmdname.lower()
            # just silently ignore other commands: they may be directed to
            # other bots
            if cmdname in commands:
                commands[cmdname](args, msg['chat'], msg['from'])

    def cmdHelp(self, text, chat, user):
        """Respond in the chat with the command list."""
        self.conn.sendMessage(chat['id'], self.helpMsg())

    def cmdStart(self, text, chat, user):
        """Was this suggested by the protocol or something?"""
        self.conn.sendMessage(chat['id'], 'please stop')

    def cmdKeulii(self, text, chat, user):
        """Query for a keulii msg."""
        target, response = self.keulii.get(chat['id'], user['id'], text)
        if response is not None:
            self.conn.sendMessage(target, response)

    def cmdKeuliiRegister(self, text, chat, user):
        """Register this chat to the keulii broadcast list."""
        # public and private registrations are accepted, chat is one of them
        title = chat.get('title', chat.get('username'))
        if self.mopoposter_broadcast.get(chat['id'], None):
            self.conn.sendMessage(user['id'],
                    'Pöh, keuliiviestit jo rekisteröity (' + title + ')')
        else:
            self.mopoposter_broadcast[chat['id']] = user['id']
            self.conn.sendMessage(user['id'],
                    'OK, keuliiviestit rekisteröity: ' + title)

    def cmdKeuliiUnRegister(self, text, chat, user):
        """Unregister this chat from the keulii broadcast list.

        Others can re-register immediately and the ownership changes then.
        """
        title = chat.get('title', chat.get('username'))
        owner = self.mopoposter_broadcast.get(chat['id'], None)
        if owner == user['id']:
            del self.mopoposter_broadcast[chat['id']]
            self.conn.sendMessage(user['id'],
                    'OK, keuliiviestejä ei enää lähetetä: ' + title)
        elif owner is None:
            self.conn.sendMessage(user['id'],
                    'Pöh, keuliiviestejä ei rekisteröity (' + title + ')')
        else:
            self.conn.sendMessage(user['id'],
                    'Pöh, keuliiviestit on rekisteröinyt joku muu (' + title + ')')

    def cmdMopoposterPost(self, text, chat, user):
        self.conn.sendMessage(user['id'],
                'Ei toimi vielä')

    def cmdQuote(self, text, chat, user):
        self.conn.sendMessage(user['id'],
                'Ei toimi vielä')

    def cmdAddQuote(self, text, chat, user):
        self.conn.sendMessage(user['id'],
                'Ei toimi vielä')

def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG,
            format='%(asctime)s [%(levelname)-8s] %(message)s')
    token = open(TOKEN_TXT).read().strip()
    bot = AskibotTg(tgbot.TgbotConnection(token), KEULII_TXT,
            MOPOPOSTERPORT, QUOTES_DIR)
    print(bot.conn.getMe())
    bot.run()

if __name__ == '__main__':
    main()
