from nestegg.config import get_config
from nestegg.tests.common import TmpDirTestCase
from os.path import join
from yaml import dump

class Object: pass
        
class TestGetConfig(TmpDirTestCase):
    def test_default_get_config(self):
        pass
    
    def test_basic_get_config(self):
        args = Object()
        config_file = join(self.tmp_dir,"nestegg.yml")
        args.conf = config_file
        with open(config_file,"w") as out :
            out.write(dump({"storage_dir": "/foo/bar","port":3333}))
        config = get_config(args)
        self.assertEqual(3333,config.port)
        self.assertEqual("/foo/bar",config.storage_dir.p)
        