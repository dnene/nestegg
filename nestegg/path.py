import os.path
import os
from nestegg import NesteggException

class Path(object):
    def __init__(self,p) :
        self.p = os.path.expanduser(p) if p.startswith("~") else \
                 os.path.abspath(p)
    def __pos__(self) :
        return self.p
    def __add__(self, p):
        return Path(os.path.join(self.p, p))
    def __getitem__(self, p):
        return Path(os.path.join(self.p, p))
    def __getattr__(self,p) :
        return Path(os.path.join(self.p, p))
    def __str__(self):
        return self.p
    def __repr__(self):
        return self.p
    def __call__(self, *args, **kwargs) :
        path, method = os.path.split(self.p)
        dfunc  = getattr(os.path,method,None) or getattr(os, method,None)
        if dfunc  :
            return dfunc (path, *args, **kwargs)
        raise NesteggException("Invalid method {} on path".format(method))
        
