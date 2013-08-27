from bottle import run,route,abort,static_file,SimpleTemplate,default_app,app,request,redirect
from hashlib import md5
from pkg_resources import Requirement, resource_string
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
from sh import git, hg, cd, cp
from subprocess import call
from yaml import load, dump
from requests import head
from datetime import timedelta
from datetime import datetime as dt
from argparse import ArgumentParser
from apscheduler.scheduler import Scheduler
import logging.config
import os
import shutil
import sys
import tempfile
import os.path as opath

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class NesteggException(Exception): pass
class Generic(object): pass

def lookup_config_file(filename):
    for f in [opath.join(opath.expanduser('~'), filename),
              '/etc/{}'.format(filename) ] :
        if opath.exists(f) : return f
    raise NesteggException("Cannot find config file {}".format(filename))

def get_config(data) :
    if isinstance(data, dict) :
        config = Generic()
        for key, value in data.items() :
            setattr(config, key, get_config(value))
        return config
    elif isinstance(data, (list, tuple)) :
        return [get_config(item) for item in data]
    return data

def scan_packages(config) :
    packages = {}
    for dirname in os.listdir(config.pypi_dir) :
        if opath.isdir(opath.join(config.pypi_dir,dirname)) :
            packages[dirname.lower()] = dirname
    config.runtime.packages = packages

def get_app(args):
    app = default_app()
    default_config = {
        "nestegg_dir" : "{}/.nestegg".format(opath.expanduser('~')),
        "index_url": "https://pypi.python.org/simple",
        "port": 7654,  "fresh": "0", "refresh_interval": "1d",
    }
    config_file = args.conf or lookup_config_file("nestegg.yml")
    if config_file :
        with open(config_file,"r") as in_config :
            config = get_config(load(in_config))
        for key, value in default_config.items() :
            if not hasattr(config,key): 
                setattr(config,key,value)
    else :
        config = get_config(default_config)

    config.refresh_interval = get_timedelta(config.refresh_interval)
    config.pypi_dir = os.path.join(config.nestegg_dir,"pypi")
    config.checkout_dir = os.path.join(config.nestegg_dir,"checkout")
    config.tests_co_dir = os.path.join(config.nestegg_dir,"tests_checkout")
    config.tests_log_dir = os.path.join(config.nestegg_dir,"tests_logs")
    config.source_dir = os.path.join(config.nestegg_dir,"source_builds")
    config.archives_dir =os.path.join(config.nestegg_dir,"archived_builds")
    config.pvt_pkgs = set()
    config.runtime = Generic()
    os.makedirs(config.pypi_dir,0o755, exist_ok=True)
    #os.makedirs(config.checkout_dir,0o755, exist_ok=True)
    os.makedirs(config.tests_co_dir,0o755, exist_ok=True)
    os.makedirs(config.tests_log_dir,0o755, exist_ok=True)
    os.makedirs(config.pypi_dir,0o755, exist_ok=True)
    scan_packages(config)
    app.config['ctx'] = config
    return app

class NesteggPackageIndex(PackageIndex):
    def __init__(self, fresh, *args, **kwargs):
        self.fresh = "fresh" == "1"
        super().__init__(*args,**kwargs)
    
    def process_index(self, url, page):
        if self.fresh: 
            del self.fetched_urls[url]
        super().process_index(url, page)

durations = { "w": "weeks", "d": "days", 
              "h": "hours", "m": "minutes", "s": "seconds"}

def get_timedelta(td_str):
    return timedelta(**{durations[tok[-1]]:int(tok[:-1]) 
                        for tok in td_str.split()}).total_seconds()

def source_build_dir(config, pkg_name) : 
    return opath.join(config.source_dir, pkg_name)

def archives_dir(config, pkg_name) : 
    return opath.join(config.archives_dir, pkg_name)

def source_build_file(config, pkg_name, file_name) : 
    return opath.join(config.source_dir, pkg_name, file_name)

def check_branch_tag(pkg, ver) :
    if hasattr(ver,"tag") ==  hasattr(ver, "branch"):
        raise NesteggException(
            "Exactly one of Branch/Tag should be specified for {}/{}".\
                    format(pkg.name, ver.version))
    if hasattr(ver,"branch") :
        ver.tag = ver.branch
        ver.branch = None
        ver.is_branch = True
    else :
        ver.is_branch = False

def check_repositories(config):
    cwd = os.getcwd()
    os.makedirs(config.checkout_dir,exist_ok=True)
    for pkg in  config.repositories :
        for ver in pkg.versions : check_branch_tag(pkg, ver)
        if not hasattr(pkg, "private") : setattr(pkg, "private", False)
        elif pkg.private : config.pvt_pkgs.add(pkg.name)
        if any(not opath.exists(source_build_file(config,pkg.name, v.dist_file)) 
                    for v in pkg.versions) :
            os.makedirs(source_build_dir(config,pkg.name), exist_ok=True)
            pkg_co_dir=opath.join(config.checkout_dir,pkg.name)
            if opath.exists(pkg_co_dir): shutil.rmtree(pkg_co_dir)
            cd(config.checkout_dir)
            call([pkg.repo_type, "clone", pkg.repo_url, pkg.name]) 
            cd(pkg_co_dir)
            for ver in pkg.versions :
                pyexe = "python" if not hasattr(ver,"python") else ver.python
                call([pkg.repo_type, "checkout", ver.tag])
                call([pyexe, "setup.py", "sdist"])
                cp(opath.join(pkg_co_dir,"dist",ver.dist_file),
                   opath.join(source_build_dir(config, pkg.name),
                       ver.dist_file))
    cd(cwd)

def tester(config, pkg, ver) :
    def test() :
        pkg_dir=opath.join(config.tests_co_dir,pkg.name)
        tag_dir=opath.join(config.tests_co_dir,pkg.name,ver.tag)
        if not opath.exists(tag_dir) :
            os.makedirs(pkg_dir,0o755, exist_ok=True)
            cd(pkg_dir)
            call([pkg.repo_type, "clone", pkg.repo_url, ver.tag]) 
        cd(tag_dir)
        call([pkg.repo_type, "checkout", ver.tag])
        call(["tox"]) 
    return test

def start_schedules(config) :
    sched = Scheduler()
    config.scheduler = sched
    sched.start()
    for pkg in config.repositories :
        for ver in pkg.versions :
            if hasattr(ver,"test_schedule") :
                if not ver.is_branch :
                    raise NesteggException(
                        "{}:{} is not a branch. Cannot apply test_schedule".\
                            format(pkg.name, ver.version))
                sched.add_cron_job(tester(config,pkg,ver), 
                    **ver.test_schedule.__dict__)

def file_md5(path) :
    m = md5()
    with open(path,"rb") as infile :
        for chunk in iter(lambda: infile.read(8192), b'') :
            m.update(chunk)
    return m.hexdigest()

def update_versions(config, dir_type, pkg_name, pkg_path, versions) :
    pkg_dir = opath.join(getattr(config,dir_type + "_dir"), pkg_name)
    if opath.exists(pkg_dir) :
        for fname in os.listdir(pkg_dir) :
            fpath = opath.join(pkg_dir,fname)
            if opath.isfile(fpath) :
                cp(fpath, pkg_path)
                versions[fname] =  "md5={}".format(file_md5(fpath))

def get_pkg_html(config, pkg_path, pkg_idx, pkg_name, pindex):
    os.makedirs(pkg_path, exist_ok=True)
    html_file = opath.join(pkg_path, "index.html")
    versions = {} if pkg_name in config.pvt_pkgs or not pkg_idx[pkg_name] else\
        dict((egg_info(d.location) for d in pkg_idx[pkg_name]))
    if (not opath.exists(html_file)) or (dt.now().timestamp() > \
        (opath.getmtime(html_file) + config.refresh_interval)):
        log.debug("Refreshing versions for package {}".format(pkg_name))
        update_versions(config, "archives", pkg_name, pkg_path, versions)
        update_versions(config, "source", pkg_name, pkg_path, versions)
        with open(html_file, "w") as outfile : outfile.write(
                pindex.render(**{"name" : pkg_name,"versions": versions }))
    return (pkg_path, "index.html")
                
@route('/simple/')
def get_root():
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    index_file = opath.join(config.pypi_dir,"index.html")
    if (not opath.exists(index_file)) or (dt.now().timestamp() >
        (opath.getmtime(index_file) + config.refresh_interval)):
        log.debug("Refreshing base index")
        pkg_idx.scan_all()
        with open(opath.join(config.pypi_dir,"index.html"), "w") as h :
            h.write(app.config['views'].gindex.render(
                pkgs=sorted(pkg_idx.package_pages)))
    return static_file("index.html", root=config.pypi_dir)    

def is_valid_package(config, pkg_idx, pkg_name) :
    if pkg_name in config.pvt_pkgs : return True
    if opath.exists(archives_dir(config, pkg_name)) : return True
    if opath.exists(source_build_dir(config, pkg_name)) :
        if not pkg_idx[pkg_name] :
            config.pvt_pkgs.add(pkg_name)
        return True
    return True if pkg_idx[pkg_name] else False

def get_real_mixed_case_name(config, pkg_name):
    mixed_case_name = config.runtime.packages.get(pkg_name.lower(),None)
    if mixed_case_name and mixed_case_name == pkg_name :
        return pkg_name
    response = head("https://pypi.python.org/simple/{}/".format(pkg_name))
    if 200 <= response.status_code < 300 : return pkg_name
    elif response.status_code < 400 :
        new_pkg_name = response.headers["location"].split("/")[-1]
        if pkg_name.lower() == new_pkg_name.lower() :
            config.runtime.packages[pkg_name.lower()] = new_pkg_name 
            return new_pkg_name
    raise NesteggException(
        "Unable to get mixed case package name for {}".format(pkg_name))
    
@route('/simple/<pkg_name>/')
def get_package(pkg_name):
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    real_pkg_name = get_real_mixed_case_name(config,pkg_name)
    if real_pkg_name != pkg_name :
        redirect('/simple/{}/'.format(real_pkg_name))
    if pkg_name not in config.pvt_pkgs :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
    pkg_path = opath.join(config.pypi_dir, pkg_name)
    if is_valid_package(config, pkg_idx, pkg_name) :
        root, html = get_pkg_html(config, pkg_path, pkg_idx, pkg_name,
                request.app.config['views'].pindex)
        return static_file(html, root=root)  
    else:
        abort(404, "No such package {}".format(pkg_name))

@route('/simple/<pkg_name>/<egg_name>')
@route('/simple/<pkg_name>/<egg_name>/')
def get_egg(pkg_name, egg_name):
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    log.debug("Package: {} egg:{}".format(pkg_name, egg_name))
    pkg_dir = opath.join(config.pypi_dir, pkg_name)
    if not egg_name.startswith(pkg_name) :
        egg_name="{}-{}.".format(pkg_name,egg_name)
        if opath.exists(pkg_dir) :
            for fname in os.listdir(pkg_dir) :
                if fname.startswith(egg_name) and fname != egg_name :
                    egg_name = fname
                    break
    fpath = opath.join(config.pypi_dir, pkg_name, egg_name)
    if not opath.exists(fpath) :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
        for dist in pkg_idx[pkg_name] :
            if egg_info(dist.location)[0] == egg_name:
                log.debug("Fetch {}/{}".format(pkg_name,egg_name))
                tmp = tempfile.gettempdir()
                try :
                    shutil.move(pkg_idx.download(dist.location, tmp), fpath)
                    return static_file(egg_name, root=pkg_dir)
                except Exception as _e :
                    pass
        abort(404,"No egg found for {} {}".format(pkg_name,egg_name))
    else :
        return static_file(egg_name, root=pkg_dir)

def get_argparser() :
    parser = ArgumentParser( description='lightweight pypi mirror and continuous integration tool')
    parser.add_argument('--conf', help='configuration file')
    return parser

def main() :
    app = get_app(get_argparser().parse_args(sys.argv[1:]))
    config = app.config['ctx']
    pkg_idx = NesteggPackageIndex(config.fresh, config.index_url)
    app.config['pkg_idx'] = pkg_idx
    check_repositories(app.config["ctx"])
    start_schedules(app.config["ctx"])
    app.config['views'] = Generic()
    app.config['views'].pindex = \
        SimpleTemplate(resource_string('nestegg','views/package.tpl'))
    app.config['views'].gindex = \
        SimpleTemplate(resource_string('nestegg','views/all_packages.tpl'))
    run(app=app, host='0.0.0.0', port = config.port)

if __name__ == "__main__" :
    main()
