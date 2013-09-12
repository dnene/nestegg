from bottle import run,route,abort,static_file,SimpleTemplate,default_app,app,request,redirect
from hashlib import md5
from pkg_resources import Requirement, resource_string
from setuptools.package_index import PackageIndex, egg_info_for_url as egg_info
from sh import git, hg, cd, cp
from subprocess import call
from requests import head
from datetime import datetime as dt
from argparse import ArgumentParser
from apscheduler.scheduler import Scheduler
import logging.config
import os
import shutil
import sys
import tempfile
from nestegg.config import get_config, Generic
from nestegg import NesteggException

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

def scan_packages(config) :
    packages = {}
    config.pypi_dir.makedirs(0o755, exist_ok=True)
    for dirname in config.pypi_dir.listdir() :
        if config.pypi_dir[dirname].isdir() :
            packages[dirname.lower()] = dirname
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
    html_file = pkg_path["index.html"]
    versions = {} if pkg_name in config.pvt_pkgs or not pkg_idx[pkg_name] else\
        dict((egg_info(d.location) for d in pkg_idx[pkg_name]))
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
    pkg_path = config.pypi_dir[pkg_name]
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
    pkg_dir = config.pypi_dir[pkg_name]
    if not egg_name.startswith(pkg_name) :
        egg_name="{}-{}.".format(pkg_name,egg_name)
        if pkg_dir.exists() :
            for fname in os.listdir(+pkg_dir) :
                if fname.startswith(egg_name) and fname != egg_name :
                    egg_name = fname
                    break
    fpath = config.pypi_dir[pkg_name][egg_name]
    if not fpath.exists() :
        pkg_idx.find_packages(Requirement.parse(pkg_name))
        for dist in pkg_idx[pkg_name] :
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
