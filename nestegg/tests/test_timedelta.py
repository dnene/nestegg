import unittest
from nestegg.config import get_timedelta

class TestTimeDelta(unittest.TestCase):
    def test1sec(self):
        self.assertEquals(1, get_timedelta("1s"))
        
    def test1min1sec(self):
        self.assertEquals(61, get_timedelta("1m 1s"))

    def test1hr1min1sec(self):
        self.assertEquals(3661, get_timedelta("1h 1m 1s"))
        
    def test1day1hr1min1sec(self):
        self.assertEquals(90061, get_timedelta("1d 1h 1m 1s"))
        
    def test1wk1day1hr1min1sec(self):
        self.assertEquals(694861, get_timedelta("1w 1d 1h 1m 1s"))
        self.assertEquals(694861, get_timedelta("1s 1m 1h 1d 1w"))
        