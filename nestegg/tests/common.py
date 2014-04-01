import unittest
from tempfile import mkdtemp
from shutil import rmtree
import logging

log = logging.getLogger(__name__)

class TmpDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = mkdtemp("nestegg")
        log.debug(self.tmp_dir)
        
    def tearDown(self):
        rmtree(self.tmp_dir)
