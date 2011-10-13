#!/usr/bin/env python

# Copyright (C) 2010 by WooMe.com
# Author: Nic Ferrier, <nferrier@woome.com>

# veh is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# veh is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with veh.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import with_statement
__version__ = "0.91.0"

from cmd import Cmd
import sys
import os
from ConfigParser import ConfigParser, NoSectionError, NoOptionError
from os.path import exists as pathexists
from os.path import splitext
from os.path import expanduser
from StringIO import StringIO
from subprocess import Popen
from subprocess import PIPE
import tempfile
import re

from veh import clone

VENV_DIR = '.venvs'
ACTIVEFILE = '.active'
VENV_PREFIX = 'venv-'


class Exists(Exception):
    """File exists"""
    pass


class ConfigMissing(Exception):
    """File exists"""
    pass


def find_root_with_file(filename, start):
    """Walk UP the filesystem looking for filename.

filename -- is the filename to search for (not a pattern).
start -- is the location to start from. 

Raises an Exception if we get to / without finding filename.
"""
    fulldir = os.path.abspath(start)
    files = os.listdir(fulldir)
    if not filename in files:
        newdir = os.path.dirname(fulldir)
        if newdir == "/":
            raise Exception("not found")
        return find_root_with_file(filename, newdir)
    return fulldir


# This flag controls certain sorts of logging
_verbose = False

def _popencmd(cmd, env=None, pipe=False):
    """Simple Popen wrapper"""
    p = Popen(cmd, env=env, stdout=PIPE if pipe else None)
    p.wait()
    return p


def _new_venv_path(repo):
    basepth = "%s/%s" % (repo, VENV_DIR)
    if not os.path.exists(basepth):
        os.mkdir(basepth)
    return tempfile.mktemp(prefix=VENV_PREFIX, dir=basepth)


def _get_active_venv(repo):
    venvdir = os.path.join(repo, VENV_DIR)
    activefile = os.path.join(venvdir, ACTIVEFILE)
    if not os.path.exists(activefile):
        return None
    repo = os.path.realpath(activefile)
    return repo


def _clear_active(repo):
    venvdir = os.path.join(repo, VENV_DIR)
    activefile = os.path.join(venvdir, ACTIVEFILE)
    if os.path.exists(activefile):
        os.remove(activefile)


def _mark_venv_active(repo, venv):
    venvdir = os.path.join(repo, VENV_DIR)
    activefile = os.path.join(venvdir, ACTIVEFILE)
    tmpfile = "%s.tmp" % activefile
    if os.path.exists(tmpfile):
        raise Exception('tmpfile %r exists.' % tmpfile)
    os.symlink(venv, tmpfile)
    os.rename(tmpfile, activefile)


def _get_inactive_venvs(repo):
    venvdir = os.path.join(repo, VENV_DIR)
    try:
        dirs = os.walk(venvdir).next()[1]
    except StopIteration, e:
        return []
    activevenv = _get_active_venv(repo)
    if activevenv:
        activevenv = os.path.basename(activevenv)
        dirs = [i for i in dirs if i != activevenv and i != ACTIVEFILE]
    dirs = [os.path.join(venvdir, i) for i in dirs]
    return dirs


def make_venv(repo):
    """Make a virtualenv for the specified repo"""
    # TODO read a user or site wide config file for whether to use virtualenvwrapper
    # could have a "make virtualenv config with a possible 'internal' value"
    venvpath = _new_venv_path(repo)
    _popencmd(["virtualenv", "--no-site-packages", venvpath])
    write_startup_rc(venvpath)
    _mark_venv_active(repo, venvpath)
    return venvpath


def write_startup_rc(venvpath):
    with open("%s/.startup_rc" % venvpath, "w") as out:
        if sys.platform != 'darwin' and os.path.exists(expanduser("~/.bashrc")):
            print >>out , "source %s\n" % expanduser("~/.bashrc")
        elif sys.platform == 'darwin' and os.path.exists(expanduser("~/.bash_profile")):
            print >>out , "source %s\n" % expanduser("~/.bash_profile")
        print >>out , "source %s\n" % ("%s/bin/activate" % venvpath)


def _rm_r(dir):
    "Recursively remove directory."
    for r, dirs, files in os.walk(dir, topdown=False):
        for fn in files:
            os.remove(os.path.join(r, fn))
        for dn in dirs:
            full = os.path.join(r, dn)
            if os.path.islink(full):
                os.remove(full)
            else:
                os.rmdir(os.path.join(r, dn))
    os.rmdir(dir)

def _venvsh(root, venvdir, shellcommand=None, exec_=False, pipe=False):
    """Run the shellcommand inside the specified venv.

    If the shellcommand is None then a new interactive shell is
    created.

    The shell used is whatever is in os.environ["SHELL"] at the time.

    If the virtualenv is not active then it is activated to run the
    shell, interactive or otherwise.
    """

    sh = os.environ['SHELL']
    command = [sh]
    env = None

    if os.environ.get("VEHACTIVE", None) != root:
        env = os.environ.copy()
        env["VEHACTIVE"] = root

        # When the shell is interactive we specify the venv's startup_rc file
        # the venv startup_rc is
        command += ["--rcfile", "%s/.startup_rc" % venvdir]

        if shellcommand:
            from os.path import basename
            activate_script = os.path.join(venvdir, "bin", "activate")
            env["BASH_ENV"] = activate_script
            env["ENV"] = activate_script

    # Add the shell command if we have one
    if shellcommand:
        command += ["-c", shellcommand]

    if _verbose:
        print >>sys.stderr,  "running %s inside the venv %s in %s" % (command, venvdir, root)

    if exec_:
        os.execve(sh, command, env if env is not None else os.environ.copy())
    else:
        return _popencmd(command, env=env, pipe=pipe)


def cleanup_inactive_venvs(repo):
    "Deletes inactive virtualenv directories."
    dirs = _get_inactive_venvs(repo)
    for dir in dirs:
        sys.stdout.write("removing %s\n" % dir)
        _rm_r(dir)

# Packages that we should force easy_install for.
# This should probably be configurable inside veh.
FORCE_EASY_INSTALL = [
    "egenix-mx-base",  # see http://bitbucket.org/ianb/pip/issue/40/package-egenix-mx-base-cant-be-installed-with
    ]


def get_config(repo, rev=None):
    """Get the config from the veh root.

Using a specified rev only works on Mercurial repos right now."""
    if not rev:
        repo_root = find_root_with_file(".veh.conf", repo)
        cfgfile = os.path.join(repo_root, '.veh.conf')
        if not pathexists(cfgfile):
            raise ConfigMissing(cfgfile)

        with open(cfgfile) as fd:
            cfg = ConfigParser()
            cfg.readfp(fd, '.veh.conf')

        return cfg

    else:
        # This obviously needs fixing to be DVCS agnostic

        from mercurial import hg, ui, error
        # NOTE: rev = None in the mercurial api will give you the working dir.
        u = ui.ui()
        try:
            repo = hg.repository(u, repo)
        except error.RepoError, e:
            # repo not found
            raise
        try:
            cfgdata = repo[rev]['.veh.conf'].data()
        except error.RepoLookupError, e:
            # revision not found
            raise
        except error.LookupError, e:
            # config not found
            cfgfile = os.path.join(repo.root, '.veh.conf')
            raise ConfigMissing(cfgfile)

        cfg = ConfigParser()
        cfg.readfp(StringIO(cfgdata), '.veh.conf')
        return cfg


PIP_VERSION_RE=re.compile("(?P<packagename>[^=]+)==(?P<version>[0-9.]+)")

def _pip_freeze(root, venv):
    """Runs pip freeze in the specified virtual env.

    Returns a list of packages with the key the packagename and the
    value the version.
    """
    process = _venvsh(root, venv, "pip freeze", pipe=True)
    stdout, stderr = process.communicate()
    specs = stdout.split("\n")
    packages = {}
    for spec in specs:
        if spec:
            m = PIP_VERSION_RE.match(spec)
            if m:
                packages[m.group("packagename")] = m.group("version")
    return packages

# This variable controls whether we check inside virtualenvs for version differences
# It's not necessary since we use PIP inside the venv now and that checks
VIRTUALENV_VERSION_PEEKING = False

def fill_venv(repo, cfg=None):
    """Install packages into the venv.

    Makes the venv if it needs to.
    """
    venvdir = _get_active_venv(repo)
    if not venvdir or not pathexists(venvdir):
        venvdir = make_venv(repo)

    if cfg is None:
        cfg = get_config(repo)

    installed_list = {}

    # Install each package in the venv
    venviron = venvdir
    packages = cfg.items("packages")
    for package in packages:
        package_name = package[1] or package[0]

        # Have you already got installed the version that is being requested
        if VIRTUALENV_VERSION_PEEKING:
            if not installed_list:
                installed_list = _pip_freeze(repo, venvdir) 
            packagespec = PIP_VERSION_RE.match(package_name)
            if packagespec:
                if packagespec.group("version") == installed_list[packagespec.group("packagename")]:
                    continue

        # Check whether pip can't install it.
        if package[0] in FORCE_EASY_INSTALL or package_name in FORCE_EASY_INSTALL:
            ez_command = "easy_install %s" % package_name
            ez = _venvsh(repo, venvdir, ez_command)
        else:
            # Use pip to install into the venv
            cmd = "pip install -v"

            # Some things that you can specify about pip with veh config
            if (cfg.has_option('pip', 'always-upgrade')
                and cfg.getboolean('pip', 'always-upgrade')):
                ## FIXME we've turned this off now we're using pip inside the venv
                #cmd += ' --upgrade'
                pass

            if cfg.has_option("pip", "download-cache"):
                cachedir = expanduser(cfg.get("pip", "download-cache"))
                try:
                    if not pathexists(cachedir):
                        os.mkdir(cachedir)
                except:
                    print >>sys.stderr, "%s does not exist but cannot be created" % cachedir
                else:
                    cmd += " --download-cache=%s" % cachedir

            pip_command = cmd + " " + package_name
            pip = _venvsh(repo, venvdir, pip_command)


def venv(repo, cfg=None):
    """Make the repos venv"""

    venvdir = _get_active_venv(repo)
    if not venvdir or not pathexists(venvdir):
        fill_venv(repo, cfg=cfg)
        venvdir = _get_active_venv(repo)
    return venvdir


def edit_file(filename):
    """Open the filename in the editor.

    Actually does the whole pattern of opening a temp file.
    """
    _, extension = splitext(filename)
    from tempfile import mkstemp
    try:
        fd, tempfilename = mkstemp(suffix=".conf", text=True)
        data = CFG_TEMPLATE
        if pathexists(filename):
            with open(filename) as srcfd:
                data = srcfd.read()

        print os.write(fd, data)
        os.close(fd)
    except Exception, e:
        print >>sys.stderr, "problem making temp file: " + str(e)
    else:
        editor = os.environ.get("VISUAL", os.environ.get("EDITOR", "editor"))
        try:
            p = Popen([editor, tempfilename])
            p.wait()
        except Exception, e:
            print >>sys.stderr, "problem running editor"
        else:
            # Copy the temp file in
            if pathexists(filename):
                os.remove(filename)
            os.rename(tempfilename, filename)

CFG_TEMPLATE = """[packages]
# enter package names here like
#   packagelabel = packagename
#
# The package name on the right are passed directly to pip.
# The package label is not used right now.
#
# This makes it easy to use either a pypi name:
#   packagelabel = packagename
# or if the package name is the same as the option label:
#   packagelabel =
#
# or a url:
#   packagelabel = http://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.4.9.tar.gz#md5=c49067cab242b5ff8c7b681a5a99533a
#
# or a vc reference:
#   packagelabel = hg+http://domain/repo

[veh]
# supported options for veh:
#  rebuilding creates a brand new virtualenv leaving the old in place.
#  the following options controls whether the previously active virtualenv
#  is deleted during rebuild or not:
#   delete-on-rebuild = true


[pip]
# supported options for pip:
#   always-upgrade = true
#   supply the --upgrade option to pip when building the virtualenv
#   download-cache = DIRECTORY
#   specifies a directory to use for pip's download cache

# End
"""


def install(repo):
    """Install a veh config file

    Opens VISUAL (and EDITOR if it can't find that) with a template.
    """
    # TODO I think this should commit really. For now, it doesn't.
    # TODO we need to add the line to hgignore for the state file
    cfgfile = "%s/.veh.conf" % repo
    if pathexists(cfgfile):
        raise Exists(cfgfile)
    edit_file(cfgfile)


def edit(repo):
    """Edit the veh config file

    Opens VISUAL on the veh config file."""
    cfgfile = "%s/.veh.conf" % repo
    if pathexists(cfgfile):
        edit_file(cfgfile)
    else:
        print >>sys.stderr, "%s does not exist" % cfgfile


class SysArgsCmd(Cmd):
    """Let's you use cmd with arg lists"""

    def onecmd(self, args):
        """Make a onecmd that operates on an array"""
        cmdarg = args[0]
        try:
            func = getattr(self, 'do_' + cmdarg)
        except AttributeError:
            return self.default(args[1:])
        else:
            return func(args[1:])

    def do_help(self, arg):
        """A version of help that deals with the array args"""
        return Cmd.do_help(self, " ".join(arg))



class VehCmd(SysArgsCmd):
    repo = None

    def __init__(self, **kwargs):
        from StringIO import StringIO
        Cmd.__init__(self, StringIO())
        self.opts = kwargs
        global _verbose
        _verbose=self.opts.get("verbose", False)

    def _findroot(self):
        """It would be better to walk the tree looking for .veh.conf"""
        try:
            foundroot = find_root_with_file(".veh.conf", os.getcwd())
        except:
            return os.getcwd()
        return foundroot

    def _getroot(self):
        from os.path import realpath
        from os.path import expanduser
        from os import getcwd
        foundroot = self._findroot()
        root = self.opts.get("root") or foundroot
        return realpath(expanduser(root))

    def do_install(self, arg):
        """Install a virtualenv for the repository.

Actually installs just the config file. The venv is made on first use.
        """
        install(self._getroot())

    def do_edit(self, arg):
        """Edit the repositorys veh config file.

Opens VISUAL or EDITOR or /usr/bin/edit on your repositorys config file.
        """
        edit(self._getroot())

    def do_check(self, arg):
        """Report whether the repository has an associated veh.
        """
        root = self._getroot()
        vehenv = _get_active_venv(root)
        if vehenv and pathexists(vehenv):
            print root
        else:
            return 1

    def do_lspackages(self, arg):
        """List the packages specified in the veh config"""

        root = self._getroot()
        cfg = get_config(root)
        for p in cfg.items("packages"):
            print "%s %s" % p

    def do_active(self, arg):
        """Is the virtualenv active? print the path if it is."""
        venv = os.environ.get("VIRTUAL_ENV")
        root = self._getroot()
        active = _get_active_venv(root)

        if active and venv and os.path.abspath(venv) == os.path.abspath(active):
            print venv
        else:
            return 1

    def do_clear(self, arg):
        """Blow away the virtualenv(s)."""
        root = self._getroot()
        # delete the dir
        _popencmd(["rm", "-rf", os.path.join(root, VENV_DIR)])

    def do_rebuild(self, arg):
        """Rebuild the virtualenv.

This builds a new virtualenv from scratch. The old virtualenv is not
affected at all."""
        root = self._getroot()
        cfg = get_config(root, *arg[:1])
        active = _get_active_venv(root)
        if active:
            _clear_active(root)
            deleteold = False  # default value
            try:
                deleteold = cfg.getboolean('veh', 'delete-on-rebuild')
            except (NoSectionError, NoOptionError), e:
                pass
            if deleteold:
                _rm_r(active)
        # Rebuild it.
        venv(root, cfg)

    def do_refresh(self, revision):
        """Refresh all packages, optionally from a specific version or tag.

Packages that don't exist in the currently active virtual env are
retrieved. 

Packages that differ in version to the current install are also
reinstalled.

With an argyment, reads the veh.conf from the revision or tag specified, thus:

  veh refresh tip

will read from tip, and:

  veh refresh release_20110201

will read the veh.conf packages from the version marked with the tag 'release_20110201'.

No revision means the working copy will be read for the veh.conf
"""
        root = self._getroot()
        cfg = get_config(root, *revision[:1])
        fill_venv(root, cfg=cfg)

    def do_cat(self, arg):
        """Cat the veh config file"""
        root = self._getroot()
        cfgfile = "%s/.veh.conf" % root
        if pathexists(cfgfile):
            with open(cfgfile) as fd:
                cfgcontent = fd.read()
                sys.stdout.write(cfgcontent)

    def do_shell(self, shellcmd):
        """Start a shell inside the venv'd repository possibly running shellcmd.

First checks that the virtualenv for the repository has been built and builds
if necessary.

Changes directory and spawns the user's SHELL.

Sets the environment variable VEHACTIVE to the root of the
venv'd repository.

Beware: it is NOT possible to run a posix mode shell inside the
virtualenv with a command. This:

  SHELL=/bin/sh veh shell -- ipython

will NOT run ipython in the virtualenv.
"""
        # It is not possible to use posix mode shells because posix
        # shells do not run an rcfile on startup when given a command.
        root = self._getroot()
        vmdir = venv(root)
        _venvsh(root, vmdir, " ".join(shellcmd), exec_=True)

    def do_noop(self, arg):
        """No-op. Just checks the virtualenv.
        """
        venv(self._getroot())

    def do_cleanup(self, arg):
        """Cleanup inactive virtual environments"""
        root = self._getroot()
        cleanup_inactive_venvs(root)

    def do_lsvirtualenvs(self, arg):
        """List active and inactive virtualenvs."""
        root = self._getroot()
        active = _get_active_venv(root)
        if active:
            sys.stdout.write("active - %s\n" % active)
        for inactive in _get_inactive_venvs(root):
            sys.stdout.write("inactive - %s\n" % inactive)

    def do_clone(self, arg):
        """Make a copy of the specified virtualenv"""
        root = self._getroot()
        active = _get_active_venv(root)
        if not active:
            print >> sys.stdout, "no active venv to clone"
            sys.exit(1)
        newvenv = _new_venv_path(root)
        try:
            clone.clone_virtualenv(active, newvenv)
        except Exception, e:
            if os.path.exists(newvenv):
                _rm_r(newvenv)
            print >> sys.stdout, "cloning active virtualenv failed"
            sys.exit(1)

        # Now rewrite the startup rc file
        write_startup_rc(newvenv)

        # ... and finally mark it as the active one
        _mark_venv_active(root, newvenv)


def main():
    from optparse import OptionParser
    p = OptionParser()
    p.add_option(
        "-R",
        "--repository",
        dest="root",
        help="specify the root of the veh protected repository"
        )
    p.add_option(
        "-v",
        "--verbose",
        action="store_true",
        dest="verbose",
        help="verbose flag"
        )
    p.add_option(
        "-V",
        "--version",
        action="store_true",
        dest="version",
        help="show the current version"
        )

    o, a = p.parse_args(sys.argv[1:])

    # Print the version if necessary
    if o.__dict__["version"]:
        print __version__
        sys.exit(0)

    # Make the processor
    cmdproc = VehCmd(**o.__dict__)

    # Now run the command
    try:
        ret = cmdproc.onecmd(a)
    except IndexError:
        print >>sys.stderr, "not enough arguments. Ask for help ?"
    else:
        if ret:
            sys.exit(ret)


if __name__ == "__main__":
    main()

# End
