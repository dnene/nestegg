from nestegg import NesteggException
import os.path 
from datetime import timedelta
from yaml import load
import logging
from nestegg.path import Path

log = logging.getLogger(__name__)

class Generic(object): pass

def get_out(msg,*vals): raise NesteggException(msg.format(*vals))

durations = { "w": "weeks", "d": "days", 
              "h": "hours", "m": "minutes", "s": "seconds"}

def get_timedelta(td_str):
    return timedelta(**{durations[tok[-1]]:int(tok[:-1]) 
                        for tok in td_str.split()}).total_seconds()

def existing_dist_candidate(base_path, name, version) :
    return (c for c in dist_candidates(name, version) if 
             (base_path + name + c).exists())
    
def dist_candidates(name, version) :
        return ("{}-{}.{}".format(name, version, ext) 
                for ext in (".tar.gz", ".egg", ".zip"))

class CommitState(object) :
    @property
    def archive(self): 
        return self.dist_file or list(f for f in (
            self.parent.parent.checkout_dir[self.parent.name].dist).listdir() 
            if f.startswith("{}-{}".format(self.parent.name, self.version)))[0]

class Release(CommitState):
    def __init__(self, parent, version = None, tag = None, python=None,
                       dist_file = None) :
        self.parent = parent
        self.version = version or get_out("version mandatory for a release")
        self.tag = tag or version
        self.python = python or "python"
        self.dist_file = dist_file


class Branch(CommitState):
    def __init__(self, parent, name = None, python=None, schedule = {},
                               dist_file = None) :
        self.parent = parent
        self.name = name or get_out("name mandatory for a branch")
        self.python = python if python else "python"
        self.schedule = schedule
        self.dist_file = dist_file

class Repository(object) :
    def __init__(self, parent, name=None, vcs=None, url=None, private=None,
                       releases=[], branches=[]) :
        self.parent = parent
        self.name = name or get_out("name is mandatory for a repository")
        self.vcs = vcs if vcs in ("git", "hg") else \
                    get_out("vcs type must be git or hg")
        self.url = url or get_out("vcs url must be provided")
        self.private = private == True
        self.releases = list(Release(self, **r) for r in releases) 
        self.branches = list(Branch(self, **b) for b in branches) 

class Config(object):
    def __init__(self, storage_dir=None, index_url=None, port=None, 
                       refresh_interval=None, repositories=None):
        self.storage_dir = Path(storage_dir or \
                           "{}/.nestegg".format(os.path.expanduser('~')))
        self.index_url = index_url or "https://pypi.python.org/simple"
        self.port = int(port) or 7654
        self.refresh_interval = get_timedelta(refresh_interval or "1d")
        self.pypi_dir = self.storage_dir.pypi
        self.checkout_dir = self.storage_dir.checkout
        self.tests_co_dir = self.storage_dir.checkout_testing
        self.testlog_dir = self.storage_dir.testlog
        self.archives_dir = self.storage_dir.archived_builds
        self.src_dist_dir = self.storage_dir.source_dists
        self.repositories = list(Repository(self,**r) for r in repositories)
        self.pvt_pkgs = set()
        self.runtime = Generic()

def lookup_config_file(filename):
    for f in [+(Path('~')[filename]),
              '/etc/{}'.format(filename) ] :
        if os.path.exists(f) : return f

def get_config(args) :
    config_file = args.conf or lookup_config_file("nestegg.yml")
    if config_file :
        with open(config_file,"r") as in_config :
            config = Config(**load(in_config))
    else:
        config = Config()
    return config

