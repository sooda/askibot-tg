#!/usr/bin/env python3
# -*- encoding: utf8 -*-

import askibot
import unittest
import socket
import tempfile
import time
import threading

class TestMopoposterConn(unittest.TestCase):
    def testEmptyConn(self):
        mp = askibot.Mopoposter(12345, lambda x: None)
        mp.start()
        mp.stop()
        # no exceptions? good

    def testLonelyStop(self):
        mp = askibot.Mopoposter(12345, lambda x: None)
        mp.stop()
        # no exceptions? good

class TestMopoposterOps(unittest.TestCase):
    PORT = 12349
    def setUp(self):
        self.msgs = []
        self.mp = askibot.Mopoposter(self.PORT, self.msgFunc)
        self.mp.start()

    def tearDown(self):
        self.mp.stop()

    def msgFunc(self, msg):
        self.msgs.append(msg)

    def newConn(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', self.PORT))
        return client

    def testSingle(self):
        client = self.newConn()
        msg = b'this is a test message'
        client.send(msg)
        while len(self.msgs) != 1:
            # FIXME: this is ugly
            pass

        self.assertEqual(self.msgs, [msg])

        # should get the msg without closing first
        client.shutdown(socket.SHUT_RDWR)
        client.close()

    def testMultiple(self):
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

        while len(self.msgs) != 3:
            # FIXME: this is ugly
            pass

        self.assertEqual(self.msgs, msgs)

        for client in clients:
            client.shutdown(socket.SHUT_RDWR)
            client.close()

class TestKeulii(unittest.TestCase):
    def setUp(self):
        self.datafile = tempfile.NamedTemporaryFile()
        self.lines = ['first line', 'second line', 'third line']
        self.datafile.write(('\n'.join(self.lines) + '\n').encode('utf-8'))
        self.datafile.flush()
        self.keulii = askibot.Keulii(self.datafile.name)

    def tearDown(self):
        self.datafile.close()
        del self.keulii

    def testSingle(self):
        dest, msg = self.keulii.get('chan', 'user', '')
        self.assertEqual(dest, 'chan')
        self.assertIn(msg, self.lines)

    def testAllCovered(self):
        # this implicitly tests also multiple users

        msgs = []
        # enough random in this range
        for i in range(100):
            dest, msg = self.keulii.get('chan', 'user' + str(i), '')
            self.assertEqual(dest, 'chan')
            msgs.append(msg)
            if len(set(msgs)) == 3:
                break

        self.assertEqual(sorted(self.lines), sorted(set(msgs)))

    def testSearch(self):
        # enough random in this range
        for i in range(100):
            dest, msg = self.keulii.get('chan', 'user' + str(i), 'first')
            self.assertEqual(dest, 'chan')
            self.assertEqual(msg, 'first line')

    def testManyChansAllowed(self):
        dest, msg = self.keulii.get('chan1', 'user', '')
        self.assertEqual(dest, 'chan1')
        self.assertIn(msg, self.lines)

        dest, msg = self.keulii.get('chan2', 'user', '')
        self.assertEqual(dest, 'chan2')
        self.assertIn(msg, self.lines)

    def testTooOften(self):
        self.keulii.get('chan', 'user', '')
        dest, msg = self.keulii.get('chan', 'user', '')
        self.assertEqual(dest, 'user')
        self.assertEqual(msg, self.keulii.ERR_MSG)

        self.keulii.TIME_LIMIT = 0.01
        time.sleep(0.02)

        dest, msg = self.keulii.get('chan', 'user', '')
        self.assertEqual(dest, 'chan')
        self.assertIn(msg, self.lines)

class TgbotConnStub:
    def __init__(self):
        self.incoming = []
        self.inmsg = threading.Event()
        self.outgoing = []
        self.outmsg = threading.Event()
        self.outidx = 0

    def queue(self, msg):
        self.incoming.append(msg)
        self.inmsg.set()

    def read(self):
        while len(self.outgoing) <= self.outidx:
            self.outmsg.wait()

        self.outidx += 1
        return self.outgoing[self.outidx - 1]

    def getUpdates(self, offset, limit=99999, timeout=None):
        self.inmsg.wait()
        return self.incoming[offset:offset+limit]

    def sendMessage(self, chat_id, text):
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
        return {'message': {
                    'from': sender, 'message_id': self.msgid, 'date': 0,
                    'chat': group, 'text': text},
                'update_id': self.msgid}

    def queue(self, group, sender, text):
        msg = self.groupMsg(group, sender, text)
        self.conn.queue(msg)
        self.msgid += 1

    def testRunStop(self):
        # empty on purpose
        pass

    def testHelp(self):
        self.queue(self.group, self.user, '/help')
        group, msg = self.conn.read()
        self.assertEqual(group, self.group['id'])
        self.assertTrue(msg.startswith('Olen ASkiBot.'))


if __name__ == '__main__':
    unittest.main()
