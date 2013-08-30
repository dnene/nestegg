import os.path

class Path(object):
    class Methods(object):
        @staticmethod
        def exists(path) :
            return os.path.exists(path)
        @staticmethod
        def listdir(path):
            return os.listdir(path)
        @staticmethod
        def isdir(path):
            return os.path.isdir(path)
        @staticmethod
        def isfile(path):
            return os.path.isfile(path)
        @staticmethod
        def getmtime(path):
            return os.path.getmtime(path)

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
        return getattr(Path.Methods,method)(path, *args, **kwargs)
        
