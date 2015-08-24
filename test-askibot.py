#!/usr/bin/env python3
# -*- encoding: utf8 -*-

import askibot
import unittest
import socket
import tempfile
import time
import threading
import shutil

class TestMopoposterConn(unittest.TestCase):
    def testEmptyConn(self):
        """Doing nothing should work, just start and stop."""
        mp = askibot.Mopoposter(12345, lambda x: None)
        mp.start()
        mp.stop()
        # no exceptions? good

    def testLonelyStop(self):
        """This won't happen in practice but test anyway, stop won't assume
        that poster has started yet."""
        mp = askibot.Mopoposter(12345, lambda x: None)
        mp.stop()
        # no exceptions? good

class TestMopoposterOps(unittest.TestCase):
    PORT = 12346
    def setUp(self):
        """These ops need a poster that has a callback back to here for the
        messages received via TCP."""
        self.msgs = []
        self.mp = askibot.Mopoposter(self.PORT, self.msgFunc)
        self.mp.start()

    def tearDown(self):
        """Clean up the poster resources."""
        self.mp.stop()

    def msgFunc(self, msg):
        """The poster acknowledged a new message"""
        self.msgs.append(msg)

    def newConn(self):
        """Create a new connection to the listening poster, needed for all
        the tests."""
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', self.PORT))
        return client

    def waitmsgs(self, n):
        """Wait until n messages have been received."""
        while len(self.msgs) < n:
            # FIXME: this is ugly
            pass

    # TODO test file update (what?)

    def testSingle(self):
        """Just a single message sent and back."""
        client = self.newConn()
        msg = b'this is a test message'
        client.send(msg)

        self.waitmsgs(1)

        self.assertEqual(self.msgs, [msg])

        client.shutdown(socket.SHUT_RDWR)
        client.close()

    def testSingleClosed(self):
        """Just a single message, close the socket immediately."""
        client = self.newConn()
        msg = b'this is a test message'
        client.send(msg)
        client.shutdown(socket.SHUT_RDWR)
        client.close()

        self.waitmsgs(1)

        self.assertEqual(self.msgs, [msg])


    def testMultiple(self):
        """Multiple messages work, in order."""
        msgs = [
                b'this is a test message 1',
                b'this is a test message 2',
                b'this is a test message 3'
        ]
        clients = []
        for msg in msgs:
            client = self.newConn()
            client.send(msg)
            clients.append(client)

        self.waitmsgs(3)

        self.assertEqual(self.msgs, msgs)

        for client in clients:
            client.shutdown(socket.SHUT_RDWR)
            client.close()

class TestKeulii(unittest.TestCase):
    def setUp(self):
        """One temporary file with dummy messages and a Keulii on it."""
        self.datafile = tempfile.NamedTemporaryFile()
        self.lines = ['first line', 'second line', 'third line']
        self.datafile.write(('\n'.join(self.lines) + '\n').encode('utf-8'))
        self.datafile.flush()
        self.keulii = askibot.Keulii(self.datafile.name)

    def tearDown(self):
        self.datafile.close()
        del self.keulii

    def testSingle(self):
        """One random message is one of those in the file."""
        dest, msg = self.keulii.get('chan', 'user', '')
        self.assertEqual(dest, 'chan')
        self.assertIn(msg, self.lines)

    def testAllCovered(self):
        """All messages are found before long (and implicitly also multiple
        users can ask for messages in a row)."""

        msgs = []
        # enough random in this range
        for i in range(999):
            dest, msg = self.keulii.get('chan', 'user' + str(i), '')
            self.assertEqual(dest, 'chan')
            msgs.append(msg)
            if len(set(msgs)) == 3:
                break

        self.assertEqual(sorted(self.lines), sorted(set(msgs)))

    def testSearch(self):
        """Word search works any number of times and returns just the one
        searched for."""
        for i in range(999):
            dest, msg = self.keulii.get('chan', 'user' + str(i), 'first')
            self.assertEqual(dest, 'chan')
            self.assertEqual(msg, 'first line')

    def testManyChansAllowed(self):
        """Same user can query on several channels with no delay."""
        dest, msg = self.keulii.get('chan1', 'user', '')
        self.assertEqual(dest, 'chan1')
        self.assertIn(msg, self.lines)

        dest, msg = self.keulii.get('chan2', 'user', '')
        self.assertEqual(dest, 'chan2')
        self.assertIn(msg, self.lines)

    def testTooOften(self):
        """Same user on one channel gets an error message directed to himself
        for too high frequency."""
        self.keulii.get('chan', 'user', '')
        dest, msg = self.keulii.get('chan', 'user', '')
        self.assertEqual(dest, 'user')
        self.assertEqual(msg, self.keulii.ERR_MSG)

    def testTooOftenTimeout(self):
        """Same user on one channel can query again after the time limit."""
        self.keulii.get('chan', 'user', '')
        self.keulii.TIME_LIMIT = 0.01
        time.sleep(0.02)
        dest, msg = self.keulii.get('chan', 'user', '')
        self.assertEqual(dest, 'chan')
        self.assertIn(msg, self.lines)

class TestQuotes(unittest.TestCase):
    def setUp(self):
        """One temporary directory for all messages and a Quotes on it."""
        self.datadir = tempfile.mkdtemp()
        self.quotes = askibot.Quotes(self.datadir)

    def tearDown(self):
        shutil.rmtree(self.datadir)
        del self.quotes

    def testAddSingle(self):
        """Add one message to one channel, get and verify it."""
        msg = 'a test message'
        self.quotes.addQuote('chan', 'a test message')
        for i in range(99):
            # no others
            dest, text = self.quotes.get('chan', 'user' + str(i), '')
            self.assertEqual(text, msg)

    def testAddMsgsChannel(self):
        """Many messages on one channel."""
        lines = ['line 1', 'line 2', 'line 3']
        for line in lines:
            self.quotes.addQuote('chan', line)

        msgs = []
        # enough random in this range
        for i in range(999):
            dest, msg = self.quotes.get('chan', 'user' + str(i), '')
            self.assertEqual(dest, 'chan')
            msgs.append(msg)
            if len(set(msgs)) == 3:
                break

        self.assertEqual(sorted(lines), sorted(set(msgs)))

    def testAddMsgChannels(self):
        """One unique message for many channels."""
        numchans = 42
        for c in range(numchans):
            self.quotes.addQuote('chan ' + str(c), 'msg ' + str(c))

        for c in range(numchans):
            # many times to verify e.g. empty newlines
            for i in range(3):
                dest, msg = self.quotes.get('chan ' + str(i),
                        'user' + str(c), '')
                self.assertEqual(dest, 'chan ' + str(i))
                self.assertEqual(msg, 'msg ' + str(i))

class TgbotConnStub:
    """Fake connection for the tgbot to test without actual tg.

    Incoming messages come from the server, outgoing go out of the bot."""
    def __init__(self):
        self.incoming = []
        self.inmsg = threading.Event()
        self.outgoing = []
        self.outmsg = threading.Event()
        self.outidx = 0

    def queue(self, msg):
        """To the bot."""
        self.incoming.append(msg)
        self.inmsg.set()

    def read(self):
        """Wait for messages for the server (that's us, the tester)."""
        while len(self.outgoing) <= self.outidx:
            self.outmsg.wait()

        self.outidx += 1
        return self.outgoing[self.outidx - 1]

    def getUpdates(self, offset, limit=99999, timeout=None):
        """Ask for messages for the bot."""
        self.inmsg.wait()
        return self.incoming[offset:offset+limit]

    def sendMessage(self, chat_id, text):
        """To the server."""
        self.outgoing.append((chat_id, text))
        self.outmsg.set()

class testAskibot(unittest.TestCase):
    def setUp(self):
        self.conn = TgbotConnStub()

        self.keuliifile = tempfile.NamedTemporaryFile()
        self.mopoposterport = 12345

        self.bot = askibot.AskibotTg(self.conn, self.keuliifile.name,
                self.mopoposterport, 'quotes')
        self.botthread = threading.Thread(target=lambda: self.bot.run())
        self.botthread.start()
        self.msgid = 0

        self.group = {'id': 42, 'title': 'world'}
        self.user = {'id': 1337, 'username': 'dude'}

    def tearDown(self):
        self.bot.stop()

    def groupMsg(self, group, sender, text):
        """A generic group message block with increasing msgid."""
        return {'message': {
                    'from': sender, 'message_id': self.msgid, 'date': 0,
                    'chat': group, 'text': text},
                'update_id': self.msgid}

    def queue(self, group, sender, text):
        """Append a message on the server for the bot to receive."""
        msg = self.groupMsg(group, sender, text)
        self.conn.queue(msg)
        self.msgid += 1

    def testRunStop(self):
        """No messages during bot lifetime is okay."""
        pass

    def testHelp(self):
        """Help message is help message."""
        self.queue(self.group, self.user, '/help')
        group, msg = self.conn.read()
        self.assertEqual(group, self.group['id'])
        self.assertTrue(msg.startswith('Olen ASkiBot'))

    # ... FIXME


if __name__ == '__main__':
    unittest.main(verbosity=2)
