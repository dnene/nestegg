# nestegg

On-demand, lightweight, package building pypi mirror

## Features 

While it has sufficient capabilities for me to start using it, _this is an early pre-alpha implementation_

### _Implemented_
* **Pypi Mirror**: Mirrors packages from pypi.python.org. 
* **On demand**: Packages are downloaded only when requested for. 
* **Lightweight**: Downloads and mirrors only those versions requested for.
* **Pypi like repository**: For locally customised open source software or private in house packages.

### _TODO_

* **Continuous testing**: Test all defined source builds at defined intervals
* Apache integration using mod\_wsgi
* Refresh pypi packages and indices
* Additional python versions (currently tested only with python 3.3)

## Quick start

* Create and activate a python 3.3 virtual env. (Currently not tested using any other version)
* Install package

```
pip install nestegg
```

* Create configuration file for nestegg in your home directory `$HOME/nestegg.yml`. Sample :

```yaml
nestegg:
  nestegg_dir: /var/cache/nestegg                         # Where nestegg makes a nest
  port: 7654                                              # Port to run on
  index-url: https://pypi.python.org/simple               # Pypi Index URL
  source_builds:                                          # List of source builds
    - name: my_package_name                               # package name
      repo_type: git                                      # git and hg supported
      repo_url: git@mygithost.com:myuserid/mypackage.git  # git url here
      private: Yes                                        # private or public
      versions:
        - version: 1.0.0                                  # python version
          tag: 1.0.0                                      # git/hg branch/tag name
          dist_file: mypackage-1.0.0.tar.gz               # source dist file name
```

For each source build / version defined, nestegg will :
* Create a git or hg clone from the git / hg repo
* Checkout the defined tag / branch
* Create a source distribution using `python setup.py sdist`
* Publish the distribution to the nestegg package repository. 
* You can install/use the distribution using pip, easy_install etc.

All the source builds and versions you defined will be cloned, the corresponding tag checked out and source distributi

* Start the server

```
$ nestegg
Bottle v0.11.6 server starting up (using WSGIRefServer())...
Listening on http://0.0.0.0:7654/
Hit Ctrl-C to quit.

```

Use http://localhost:7654 as the index url with pip or tox or other clients

eg. :

```
pip install SQLAlchemy==0.8.2 --index-url=http://localhost:7654 
```


## Why ?

* Create a desktop / intranet mirror of all packages used. Create new test virtualenvs readily without having to wait for long downloads
* Manage versions of your package dependencies (even if pypi eventually does not publish the versions you rely upon)
* Publish versions of libraries you fork, or any you create to a pypi like repository without having to publish it globally.
* Ensure access control. Continues to work with git/hg authentication over ssh
* (TODO) Continuous / automatic testing of python packages you author and maintain.
