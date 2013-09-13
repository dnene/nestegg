from apscheduler.scheduler import Scheduler
from argparse import ArgumentParser
from bottle import run, route, abort, static_file, SimpleTemplate, default_app, \
    app, request, redirect
from datetime import datetime as dt
from hashlib import md5
from nestegg import NesteggException
from nestegg.config import get_config, Generic
from pkg_resources import Requirement, resource_string, safe_name
from requests import head
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
from sh import git, hg, cd, cp
from subprocess import call
import logging.config
import os
import os.path
import shutil
import sys
import tempfile

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

#temporary

log.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
#formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#ch.setFormatter(formatter)
log.addHandler(ch)

def idx_safe_name(n): return safe_name(n).lower()

def scan_packages(config) :
    packages = {}
    config.pypi_dir.makedirs(0o755, exist_ok=True)
    for dirname in config.pypi_dir.listdir() :
        if config.pypi_dir[dirname].isdir() :
            packages[normalise(dirname)] = dirname
    config.runtime.packages = packages

class NesteggPackageIndex(PackageIndex):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
    
    #def process_index(self, url, page):
        #if self.fresh: 
            #del self.fetched_urls[url]
        #super().process_index(url, page)

def check_repositories(config):
    cwd = os.getcwd()
    config.checkout_dir.makedirs(0o755, exist_ok=True)
    for repo in  config.repositories :
        if repo.private : config.pvt_pkgs.add(repo.name)
        repo.build_dist_for()
    cd(cwd)

def tester(config, repo, branch) :
    def test() :
        repo_dir=config.tests_co_dir[repo.name]
        tag_dir=repo_dir[branch.name]
        if not tag_dir.exists() :
            repo_dir.makedirs(0o755, exist_ok=True)
            cd(+repo_dir)
            call([repo.vcs, "clone", repo.url, branch.name]) 
        cd(+tag_dir)
        call([repo.vcs, "checkout", branch.name])
        call(["tox"]) 
    return test

def start_schedules(config) :
    sched = Scheduler()
    config.scheduler = sched
    sched.start()
    for repo in config.repositories :
        for branch in repo.branches :
            if branch.schedule :
                sched.add_cron_job(tester(config,repo,branch), 
                    **branch.schedule)

def file_md5(path) :
    m = md5()
    with open(path,"rb") as infile :
        for chunk in iter(lambda: infile.read(8192), b'') :
            m.update(chunk)
    return m.hexdigest()

def update_versions(config, dir_type, pkg_name, pkg_path, versions) :
    pkg_dir = getattr(config,dir_type + "_dir")[pkg_name]
    if pkg_dir.exists() :
        for fname in os.listdir(+pkg_dir) :
            fpath = pkg_dir[fname]
            if fpath.isfile() :
                cp(+fpath, +pkg_path)
                versions[fname] =  "md5={}".format(file_md5(+fpath))

def get_pkg_html(config, pkg_path, pkg_idx, pkg_name, pindex):
    pkg_path.makedirs(0o755, exist_ok=True)
    safe_pkg_name = idx_safe_name(pkg_name)
    html_file = pkg_path["index.html"]
    versions = {} if pkg_name in config.pvt_pkgs or not pkg_idx[safe_pkg_name]\
            else dict((egg_info(d.location) for d in pkg_idx[safe_pkg_name]))
    if is_stale(config,html_file) :
        log.debug("Refreshing package {}".format(pkg_name))
        update_versions(config, "archives", pkg_name, pkg_path, versions)
        update_versions(config, "src_dist", pkg_name, pkg_path, versions)
        with open(+html_file, "w") as outfile : outfile.write(
                pindex.render(**{"name" : pkg_name,"versions": versions }))
    return (pkg_path, "index.html")

def is_stale(config, index_file) :
    return (not index_file.exists()) or (dt.now().timestamp() >
            (index_file.getmtime() + config.refresh_interval))

@route('/simple/')
def get_root():
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    if is_stale(config, config.pypi_dir["index.html"]) :
        log.debug("Refreshing base index")
        pkg_idx.scan_all()
        with open(+config.pypi_dir["index.html"], "w") as h :
            h.write(app.config['views'].gindex.render(
                pkgs=sorted(pkg_idx.package_pages)))
    return static_file("index.html", root=+config.pypi_dir)    

def is_valid_package(config, pkg_idx, pkg_name) :
    if pkg_name in config.pvt_pkgs : return True
    if config.archives_dir[pkg_name].exists() : return True
    if config.src_dist_dir[pkg_name].exists() :
        if not pkg_idx[pkg_name] :
            config.pvt_pkgs.add(pkg_name)
        return True

    return idx_safe_name(pkg_name) in pkg_idx

def normalise(pkg_name):
    return pkg_name.lower().replace("-","_")

def get_real_mixed_case_name(config, pkg_name):
    normalised_name = normalise(pkg_name)
    mixed_case_name = config.runtime.packages.get(normalised_name,None)
    if mixed_case_name and mixed_case_name == pkg_name :
        return pkg_name
    response = head("https://pypi.python.org/simple/{}/".format(pkg_name))
    if 200 <= response.status_code < 300 : return pkg_name
    elif response.status_code < 400 :
        new_pkg_name = response.headers["location"].split("/")[-1]
        if normalised_name == normalise(new_pkg_name) :
            config.runtime.packages[normalised_name] = new_pkg_name 
            return new_pkg_name
    if pkg_name not in config.pvt_pkgs :
        log.debug(config.pvt_pkgs)
        raise NesteggException("Unable to get mixed case package name for {}"\
                               .format(pkg_name))
    else :
        return pkg_name
    
@route('/simple/<pkg_name>/')
def get_package(pkg_name):
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    real_pkg_name = get_real_mixed_case_name(config,pkg_name)
    log.debug("Request for package {} denormalised to {}".format(pkg_name, real_pkg_name))
    if real_pkg_name != pkg_name :
        log.debug("Redirecting to denormalised name {}".format(real_pkg_name))
        redirect('/simple/{}/'.format(real_pkg_name))
    if pkg_name not in config.pvt_pkgs :
        log.debug("Fetching requirements for {}".format(pkg_name))
        pkg_idx.find_packages(Requirement.parse(pkg_name))
        log.debug("package is {}".format(pkg_idx[idx_safe_name(pkg_name)]))
    pkg_path = config.pypi_dir[pkg_name]
    log.debug("Package path is {}".format(pkg_path))
    if is_valid_package(config, pkg_idx, pkg_name) :
        root, html = get_pkg_html(config, pkg_path, pkg_idx, pkg_name,
                request.app.config['views'].pindex)
        return static_file(html, root=+root)  
    else:
        abort(404, "No such package {}".format(pkg_name))

@route('/simple/<pkg_name>/<egg_name>')
@route('/simple/<pkg_name>/<egg_name>/')
def get_egg(pkg_name, egg_name):
    config, pkg_idx = request.app.config['ctx'], request.app.config['pkg_idx']
    log.debug("Package: {} egg:{}".format(pkg_name, egg_name))
    packages = {normalise(f): f for f in config.pypi_dir.listdir() 
                                    if config.pypi_dir[f].isdir()}
    pkg_name = packages.get(normalise(pkg_name), pkg_name)
    pkg_dir = config.pypi_dir[pkg_name]
    log.debug("package dir is {}".format(pkg_dir))
    if not egg_name.startswith(pkg_name) :
        egg_name="{}-{}.".format(pkg_name,egg_name)
        if pkg_dir.exists() :
            for fname in os.listdir(+pkg_dir) :
                if fname.startswith(egg_name) and fname != egg_name :
                    egg_name = fname
                    break
    fpath = config.pypi_dir[pkg_name][egg_name]
    log.debug("Egg path is {}".format(fpath))
    if not fpath.exists() :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
        for dist in pkg_idx[idx_safe_name(pkg_name)] :
            if egg_info(dist.location)[0] == egg_name:
                log.debug("Fetch {}/{}".format(pkg_name,egg_name))
                tmp = tempfile.gettempdir()
                try :
                    shutil.move(pkg_idx.download(dist.location, tmp), +fpath)
                    return static_file(egg_name, root=+pkg_dir)
                except Exception as _e :
                    pass
        abort(404,"No egg found for {} {}".format(pkg_name,egg_name))
    else :
        return static_file(egg_name, root=+pkg_dir)

def get_app(args):
    app = default_app()
    config = get_config(args)
    scan_packages(config)
    app.config['ctx'] = config
    return app

def get_argparser() :
    parser = ArgumentParser(description=
                'lightweight pypi mirror and continuous integration tool')
    parser.add_argument('--conf', help='configuration file')
    return parser

def main() :
    app = get_app(get_argparser().parse_args(sys.argv[1:]))
    config = app.config['ctx']
    pkg_idx = NesteggPackageIndex(config.index_url)
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
