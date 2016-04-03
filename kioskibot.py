#!/usr/bin/env python3
# -*- encoding: utf8 -*-

"""kioskibot"""

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
QUOTES_DIR = 'quotes'

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
    def __init__(self, connection, quotesdir):
        self.conn = connection
        self.update_offset = 0

        self.quotes = Quotes(quotesdir)
        # record the last /addq place to save the quote to the right place when
        # forwarded to the bot.
        self.last_addq_chat = {}

        self.running = False

        me = self.conn.getMe()
        self.username = me['username']

    def helpMsg(self):
        return '''Näe maailma eri tavalla kuin muut

/kioski HAKUTEKSTI - hae satunnainen kioskiläppä tältä kanavalta
/vink - merkitse lisättävä kioskiläppä tälle kanavalle. Lisää se sitten forwardaamalla yksityisesti botille.

Botti on huono vitsi eikä liity mihinkään yleisradioon mitenkään.
'''

    def run(self):
        """Start the main loop that goes on until user ^C's this."""
        self.running = True
        try:
            self.loopUpdates()
        except KeyboardInterrupt:
            pass

    def stop(self):
        # just for the tests
        self.running = False

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
                    '/kioski': self.cmdQuote,
                    '/vink': self.cmdAddQuote,
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
                    'Virhe: Mistä tämä tuli? Merkitse keskustelukanava ensin komentamalla siellä /vink')
            return

        msgid = msg['message_id']
        text = msg['text']

        quote = TgQuote(fwd_from, msgid, text, user)
        self.quotes.addQuote(chat['id'], quote)

        self.conn.sendMessage(chat['id'],
                'vink ({} kioskivinkkasi) {}: {}'.format(getUserDesc(user), getUserDesc(fwd_from), text))

        del self.last_addq_chat[user['id']]

    def cmdAddQuote(self, text, chat, user):
        """addq marks the chat to record the next forward on"""
        self.last_addq_chat[user['id']] = chat
        title = getChatDesc(chat)
        self.conn.sendMessage(user['id'],
                'vink: Forwardaa viesti niin tallennan (' + title + ')')

def main():
    logging.basicConfig(filename='debug.log', level=logging.DEBUG,
            format='%(asctime)s [%(levelname)-8s] %(message)s')
    token = open(TOKEN_TXT).read().strip()
    bot = AskibotTg(tgbot.TgbotConnection(token),
            QUOTES_DIR)
    print(bot.conn.getMe())
    bot.run()

if __name__ == '__main__':
    main()
