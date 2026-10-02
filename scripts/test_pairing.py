import unittest
from types import SimpleNamespace
from review_server import Handler, TOKEN

class PairingTests(unittest.TestCase):
    def handler(self, host='192.168.1.2:8765', client='192.168.1.3', token=''):
        h=object.__new__(Handler)
        h.headers={'Host':host,'X-Pair-Token':token}
        h.client_address=(client,1234)
        h.server=SimpleNamespace(server_port=8765,allowed_hosts={'127.0.0.1','192.168.1.2'})
        return h
    def test_lan_requires_pairing(self):
        self.assertFalse(self.handler().authenticated())
        self.assertTrue(self.handler(token=TOKEN).authenticated())
    def test_local_access_stays_available(self):
        self.assertTrue(self.handler(client='127.0.0.1').authenticated())
    def test_other_host_rejected_even_with_pairing_token(self):
        self.assertFalse(self.handler(host='attacker.example:8765',token=TOKEN).allowed())
        self.assertTrue(self.handler().allowed())
