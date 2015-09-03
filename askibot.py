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
import pickle
import collections

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
        lines = [x.strip() for x in self._listQuotes(chan_id)
                if term in x.lower()]
        return random.choice(lines) if len(lines) else None

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
            with open('%s/%s' % (self.quotefile_dir, chan_id), 'rb') as fh:
                return pickle.load(fh)
        except IOError:
            return []

    def addQuote(self, chan_id, quote):
        quotes = self._listQuotes(chan_id)
        quotes.append(quote)
        with open('%s/%s' % (self.quotefile_dir, chan_id), 'wb') as fh:
            pickle.dump(quotes, fh)


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


def getUserDesc(user):
    """Either "username" or "first last" (one of those should exist)

    Use only for human interaction, not for detecting stuff like with IDs"""
    return user.get('username',
            '%s %s' % (
                user.get('first_name', ''),
                user.get('last_name', '')))

def getChatDesc(chat):
    """Either chat title or the user if it's a personal 1-on-1 chat

    Use only for human interaction, not for detecting stuff like with IDs"""
    return chat.get('title', getUserDesc(chat))


class AskibotTg:
    MOPOPOSTER_SAVE_FILENAME = 'mopoposter.pickle'
    def __init__(self, connection, keuliifilename, mopoposterport, quotesdir):
        self.conn = connection
        self.update_offset = 0

        try:
            with open(self.MOPOPOSTER_SAVE_FILENAME, 'rb') as fh:
                self.mopoposter_broadcast = pickle.load(fh)
        except IOError:
            self.mopoposter_broadcast = {}
        self.mopoposter = Mopoposter(mopoposterport, self.sendMopoposter)
        self.keulii = Keulii(keuliifilename)
        self.quotes = Quotes(quotesdir)
        # record the last /addq place to save the quote to the right place when
        # forwarded to the bot.
        self.last_addq_chat = {}

        self.running = False

        me = self.conn.getMe()
        self.username = me['username']

    def saveMopoposterBroadcast(self):
        try:
            with open(self.MOPOPOSTER_SAVE_FILENAME, 'wb') as fh:
                pickle.dump(self.mopoposter_broadcast, fh)
        except IOError:
            logging.error('Cannot open mopoposter save %s' % self.MOPOPOSTER_SAVE_FILENAME)

    def helpMsg(self):
        return '''Olen ASkiBot, killan irkistä tuttu robotti. Living tissue over metal endoskeleton.

/keulii HAKUTEKSTI - Hae mopopostereista tekstinpätkää, hakutekstillä tai ilman.
/keuliiregister - Rekisteröi tämä kanava reaaliaikaiseksi mopoposterikuuntelijaksi.
/keuliiunregister - Kumoa rekisteröinti, viestejä ei enää tule. Sallittu vain rekisteröijälle ja ylläpitäjälle.

/q HAKUTEKSTI - kuin mopoposter, mutta kanavakohtaisille quoteille.
/addq - merkitse lisättävä quote tälle kanavalle. Lisää se sitten forwardaamalla yksityisesti botille.

Bottia ylläpitää sooda.
'''
# TODO:
#/mopoposterpost VIESTI - Lähetä mopoposteri tietokantaan. HUOM: älä käytä lähetystä turhuuksiin, vaan harvinaisiin herkkuihin joista täytyy jättää jälki jälkipolville sekä välitön viesti irkkiin ja rekisteröityneille tg-ryhmille.
#

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
            self.conn.sendMessage(chatid, 'KEULII! ' + msg)

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

            if 'forward_from' in msg:
                # this is a private message; from and chat are the same (the
                # bot can't see public ones). forward_from is the original
                # user, but the original chat is lost
                self.cmdForwardedMessage(msg, msg['from'],
                        msg['forward_from'])

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
        title = getChatDesc(chat)
        if self.mopoposter_broadcast.get(chat['id'], None):
            self.conn.sendMessage(user['id'],
                    'Pöh, keuliiviestit jo rekisteröity (' + title + ')')
        else:
            self.mopoposter_broadcast[chat['id']] = user['id']
            self.saveMopoposterBroadcast()
            self.conn.sendMessage(user['id'],
                    'OK, keuliiviestit rekisteröity: ' + title)

    def cmdKeuliiUnRegister(self, text, chat, user):
        """Unregister this chat from the keulii broadcast list.

        Others can re-register immediately and the ownership changes then.
        """
        title = getChatDesc(chat)
        owner = self.mopoposter_broadcast.get(chat['id'], None)
        if owner == user['id']:
            del self.mopoposter_broadcast[chat['id']]
            self.saveMopoposterBroadcast()
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
        """Query for a quote."""
        target, response = self.quotes.get(chat['id'], user['id'], text)
        if isinstance(response, TgQuote):
            # the from-id is somehow paired to the msgid, but doesn't seem to
            # show in the chat ui (or the forward_from field). can't send the
            # msg if from-id is wrong.
            self.conn.forwardMessage(target, response.adder['id'], response.msgid)
        elif response is not None:
            # nag the user
            self.conn.sendMessage(target, response)

    def cmdForwardedMessage(self, msg, user, fwd_from):
        """Received a private forward, interpreted as a quote to be added"""
        chat = self.last_addq_chat.get(user['id'])
        if chat is None:
            self.conn.sendMessage(user['id'],
                    'Virhe: Mistä tämä tuli? Merkitse keskustelukanava ensin komentamalla siellä /addq')
            return

        msgid = msg['message_id']
        text = msg['text']

        quote = TgQuote(fwd_from, msgid, text, user)
        self.quotes.addQuote(chat['id'], quote)

        self.conn.sendMessage(chat['id'],
                'addq ({} lisäsi) {}: {}'.format(getUserDesc(user), getUserDesc(fwd_from), text))

    def cmdAddQuote(self, text, chat, user):
        """addq marks the chat to record the next forward on"""
        self.last_addq_chat[user['id']] = chat
        title = getChatDesc(chat)
        self.conn.sendMessage(user['id'],
                'addq: Forwardaa viesti niin tallennan (' + title + ')')

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
