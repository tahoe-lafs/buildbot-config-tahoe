import re
from buildbot.steps.shell import ShellCommand, WithProperties, Compile
from buildbot.status.builder import FAILURE, SUCCESS, WARNINGS

class PythonCommand(ShellCommand):
    # set python_command= to a list of everything but the leading "python",
    # or pass it in kwargs. Pass python= in kwargs to override it.
    python = None
    python_command = None

    def __init__(self, python="python", python_command=None, *args, **kwargs):
        python = python or self.python
        if python is None:
            python = "python"
        python_command = python_command or self.python_command
        kwargs["command"] = [python] + python_command
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(python=python, python_command=python_command)

class ToolVersions(PythonCommand):
    name = "show-tool-versions"
    description = ["tool", "versions"]
    workdir = "."
    flunkOnFailure = False
    python_command = ["misc/build_helpers/show-tool-versions.py"]

    def createSummary(self, log):
        python_re = re.compile(r'^python: (\S+)\s')
        twisted_re = re.compile(r'^buildbot: .* Twisted version: (\S+)')
        self.tool_versions = []
        for line in log.readlines():
            line = line.strip()
            mo = python_re.search(line)
            if mo:
                self.tool_versions.append( ("py", mo.group(1)) )
            mo = twisted_re.search(line)
            if mo:
                self.tool_versions.append( ("tw", mo.group(1)) )

    def getText(self, cmd, results):
        text = ["tool", "versions"]
        for (tool, version) in self.tool_versions:
            text.append(tool + version)
        return text

class CompileAndShowVersion(Compile):
    """Emit the version number in the status box
    """
    version = None

    def createSummary(self, log):
        ver_re = re.compile("wrote '([^']+)' into src/allmydata/_version.py")
        for line in log.readlines():
            m = ver_re.search(line)
            if m:
                self.version = m.group(1)
                self.setProperty("tahoe-version", self.version)
                return

    def getText(self, cmd, results):
        text = ["compile"]
        if self.version:
            text.append(self.version)
        return text

class BuildTahoe(PythonCommand):
    """
    Step to test the build/local-install of tahoe by running the
    ./setup.py build command.
    """
    flunkOnFailure = True
    haltOnFailure = True
    name = "build"
    description = ["building", "tahoe"]
    descriptionDone = ["build"]
    python_command = ["setup.py", "-v", "build"]

class BuiltTest(PythonCommand):
    """
    Step to run the test suite after a typical installation of tahoe done
    by the ./setup.py build command.
    """
    flunkOnFailure = True
    name = "test"
    description = ["testing"]
    descriptionDone = ["test"]
    logfiles = {"test.log": "_trial_temp/test.log"}

    def __init__(self, test_suite=None, *args, **kwargs):
        python_command = ["setup.py", "test", "--reporter=timing"]
        if test_suite is not None:
            python_command.extend(["--suite", test_suite])
        kwargs["python_command"] = python_command
        PythonCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(test_suite=test_suite)

    def createSummary(self, log):
        # scan the log, measure time consumed per test, show a sorted list
        # with the most time-consuming test at the top
        last_test = None
        tests = []
        test_re = re.compile(r'^(allmydata\.test\.\S+) \.\.\.')
        time_re = re.compile(r'^\(([\d\.]+) secs\)')
        for line in log.readlines():
            line = line.strip()
            mo = test_re.search(line)
            if mo:
                last_test = mo.group(1)
                continue
            if not last_test:
                continue
            mo = time_re.search(line.strip())
            if mo:
                t = float(mo.group(1))
                tests.append( (t, last_test) )
                last_test = None
        tests.sort()
        tests.reverse()
        if tests:
            timings = "\n".join(["%7s seconds: %s" % (("%.3f" % t[0]), t[1])
                                 for t in tests]) + "\n"
            self.addCompleteLog("timings", timings)

class TestDeprecations(PythonCommand):
    warnOnFailure = False
    flunkOnFailure = False
    name = "deprecations"
    description = ["testing", "deprecations"]
    descriptionDone = ["test", "deprecations"]
    logfiles = {"test.log": "_trial_temp/test.log"}
    python_command = ["setup.py", "test"]

    def __init__(self, *args, **kwargs):
        kwargs["env"] = {"PYTHONWARNINGS": "default::DeprecationWarning"}
        PythonCommand.__init__(self, *args, **kwargs)

    def createSummary(self, log):
        # create a logfile with the de-duped DeprecationWarning messages
        warnings = set()
        warn_re = re.compile(r'DeprecationWarning: ')
        for line in log.readlines(): # add stderr
            line = line.strip()
            mo = warn_re.search(line)
            if mo:
                warnings.add(line)
        if warnings:
            self.addCompleteLog("warnings", "\n".join(sorted(warnings))+"\n")

class TestOldDep(PythonCommand):
    """
    Run a special test to confirm that the build system builds a new
    dependency (from source) when faced with an .egg version that is too old.
    See <http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1342>.
    """
    flunkOnFailure = True
    description = ["test-old-dep"]
    name = "test-old-dep"
    logfiles = {"test.log": "src/_trial_temp/test.log"}
    python_command = ["misc/build_helpers/test-dont-use-too-old-dep.py"]

class TestAlreadyHaveDep(PythonCommand):
    """
    Run a special test to confirm that the build system refrains from
    attempting to build a dependency when that dep is already satisfied. See
    <http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1342>.
    """
    flunkOnFailure = True
    description = ["test-already-have-dep"]
    name = "test-already-have-dep"
    logfiles = {"test.log": "src/_trial_temp/test.log"}
    python_command = ["misc/build_helpers/test-dont-install-newer-dep-when-you-already-have-sufficiently-new-one.py"]

class UploadTarballs(ShellCommand):
    """
    Invoke "make tarballs" with an env var to tell it what branch.
    """

    flunkOnFailure = True
    description = ["uploading", "tarballs"]
    descriptionDone = ["upload", "tarballs"]
    name = "upload-tarballs"

    def __init__(self, make=None,  *args, **kwargs):
        kwargs['command'] = [make, "upload-tarballs"]
        kwargs['env'] = {'BB_BRANCH': WithProperties("%(branch)s")}
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(make=make)
        self.not_uploaded = False

    def commandComplete(self, cmd):
        # check to see if the upload actually happened
        if "not uploading tarballs" in cmd.logs['stdio'].getText():
            self.not_uploaded = True

    def evaluateCommand(self, cmd):
        rc = ShellCommand.evaluateCommand(self, cmd)
        if self.not_uploaded:
            rc = WARNINGS
        return rc

    def getText(self, cmd, results):
        text = ["upload", "tarballs"]
        if self.not_uploaded:
            text.append("skipped")
        return text

class GenCoverage(PythonCommand):
    """
    Step to run the test suite with coverage after a typical installation of
    tahoe done by the ./setup.py build command.
    """
    flunkOnFailure = True # This substitutes for the normal unit tests.
    description = ["testing", "(coverage)"]
    descriptionDone = ["test", "(coverage)"]
    name = "test-coverage"
    logfiles = {"test.log": "_trial_temp/test.log"}
    python_command = ["setup.py", "test", "--reporter=bwverbose-coverage"]

class ArchiveCoverage(ShellCommand):
    """
    Put coverage results into an archive for transport.
    """

    flunkOnFailure = True
    description = ["arch cov"]
    name = "arch cov"
    COMMAND_TEMPL = 'rm cov-*.tar.bz2 ; VER=`python setup.py --name`-`python setup.py --version` ; export VER ; coverage html ; mv .coverage "coverage-${VER}" && mv .coverage-results "coverage-results-${VER}" && mv htmlcov "htmlcov-${VER}" && %s cjvf "cov-${VER}.tar.bz2" "coverage-${VER}" "coverage-results-${VER}" "htmlcov-${VER}"'

    def __init__(self, TAR, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(TAR=TAR)
        self.command = self.COMMAND_TEMPL % TAR

class UploadCoverage(ShellCommand):
    """
    Use the 'flappclient' tool to upload the coverage archive.
    """

    flunkOnFailure = True
    description = ["upload cov"]
    name = "upload cov"

    def __init__(self, upload_furlfile=None, *args, **kwargs):
        kwargs['command'] = 'flappclient --furlfile %s upload-file cov-*.tar.bz2' \
                            % (upload_furlfile,)
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(upload_furlfile=upload_furlfile)

class UnarchiveCoverage(ShellCommand):
    """
    Use the 'flappclient' tool to trigger unarchiving of the coverage archive.
    """

    flunkOnFailure = True
    description = ["unarch cov"]
    name = "unarch cov"

    def __init__(self, unarch_furlfile=None, *args, **kwargs):
        kwargs['command'] = 'flappclient --furlfile %s run-command' % (unarch_furlfile,)
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(unarch_furlfile=unarch_furlfile)

class PushCoverage(ShellCommand):
    UPLOAD_HOST = "buildslave@dev.allmydata.com"
    COVERAGEDIR = "coverage-results-%d"
    UPLOAD_TARGET = "%s:public_html/tahoe/%s/" % (UPLOAD_HOST, COVERAGEDIR)
    URLBASE = "http://tahoe-lafs.org/tahoe-lafs-coverage/%s/index.html" % COVERAGEDIR
    name = "push-coverage"
    description = ["pushing", "coverage", "output"]
    descriptionDone = ["push", "coverage", "output"]

    def __init__(self, MAKE, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(MAKE=MAKE)
        self.command = [MAKE, "upload-coverage",
                   WithProperties("UPLOAD_TARGET=%s" % self.UPLOAD_TARGET,
                                  "buildnumber"),
                   "UPLOAD_HOST=%s" % self.UPLOAD_HOST,
                   WithProperties("COVERAGEDIR=%s" % self.COVERAGEDIR, "buildnumber"),
                   ]

    def commandComplete(self, cmd):
        self.addURL("coverage", self.URLBASE % self.getProperty("buildnumber"))


# the 'make upload-coverage' target runs two commands:
#       rsync -a coverage-html/ $(UPLOAD_TARGET)
#       ssh $(UPLOAD_HOST) make update-tahoe-coverage $(COVERAGEDIR)
# and the latter invokes buildslave@dev:Makefile, which does:
#       rm -f public_html/tahoe/current
#       ln -s $(COVERAGEDIR) public_html/tahoe/current
#       rsync -a public_html/tahoe/ org:public_html/tahoe/

class CoverageDeltaHTML(ShellCommand):
    """
    Create HTML code coverage display, after test-coverage has been run. We
    also fetch the previous code-coverage data from tahoe-lafs.org, so we can
    compute a delta (lines newly covered, lines no longer covered).
    """
    name = "coverage-html"
    description = ["rendering", "coverage", "html"]
    descriptionDone = ["render", "coverage"]

    def __init__(self, MAKE, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(MAKE=MAKE)
        self.command = [MAKE, "get-old-coverage-coverage", "coverage-delta-output"]

    def createSummary(self, log):
        self.counts = {}
        count_re = re.compile(r"^([\w ]+): ([\d\.]+)$")
        namemap = {"total files": "count-files",
                   "total source lines": "source-lines",
                   "total covered lines": "covered-lines",
                   "total uncovered lines": "uncovered-lines",
                   "lines added": "lines-added",
                   "lines removed": "lines-removed",
                   "total coverage percentage": "coverage-percentage",
                   }
        for line in log.readlines():
            m = count_re.search(line.strip())
            if m:
                name = namemap.get(m.group(1), m.group(1))
                if "percentage" in name:
                    value = float(m.group(2))
                else:
                    value = int(m.group(2))
                self.setProperty("coverage-" + name, value)
                self.counts[name] = value

    def getText(self, cmd, results):
        text = ["render", "coverage"]
        if self.counts.get("lines-removed"):
            text.append("%d lost" % self.counts["lines-removed"])
        if self.counts.get("lines-added"):
            text.append("%d gained" % self.counts["lines-added"])
        if "uncovered-lines" in self.counts:
            text.append("%d not covered" % self.counts["uncovered-lines"])
        return text


class TahoeVersion(PythonCommand):
    """
    Step to check if the tahoe version can be found through the 'tahoe'
    command-line executable script.
    """

    python_command = ["bin/tahoe", "--version-and-path"]
    flunkOnFailure = True
    description = ["tahoe-version"]
    name = "tahoe-version"

    def createSummary(self, log):
        ver_re = re.compile("^allmydata-tahoe: ([^ ]+)")
        for line in log.readlines():
            m = ver_re.search(line)
            if m:
                self.tahoeversion = m.group(1).split(',')[0]
                self.setProperty("tahoe-version", self.tahoeversion)
                return
        if not hasattr(self, 'tahoeversion'):
            return FAILURE # "Tahoe version could not be found."

    def getText(self, cmd, results):
        text = ShellCommand.getText(self, cmd, results)
        if hasattr(self, 'tahoeversion'):
            text.append(self.tahoeversion)
        return text

class Stdeb(ShellCommand):
    """
    Use the 'stdeb' tool to create the Debian files and then run the Debian
    'dpkg_buildpackage' tool to build a .deb.
    """

    flunkOnFailure = True
    description = ["stdeb"]
    name = "stdeb"

    def __init__(self, python="python", *args, **kwargs):
        kwargs['command'] = python + ' setup.py --command-packages=stdeb.command sdist_dsc && cd `find deb_dist -mindepth 1 -maxdepth 1 -type d` && dpkg-buildpackage -rfakeroot -uc -us'
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(python=python)

class UploadDeb(ShellCommand):
    """
    Use the 'flappclient' tool to upload the .deb.
    """

    flunkOnFailure = True
    description = ["upload deb"]
    name = "upload deb"

    def __init__(self, upload_furlfile=None, deb_filename_base=None,
                 *args, **kwargs):
        kwargs['command'] = 'flappclient --furlfile %s upload-file %s*.deb' \
                            % (upload_furlfile, deb_filename_base)
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(upload_furlfile=upload_furlfile,
                                 deb_filename_base=deb_filename_base)

class UploadEgg(ShellCommand):
    """
    Use the 'flappclient' tool to upload the .egg.
    """

    flunkOnFailure = True
    description = ["upload egg"]
    name = "upload egg"

    def __init__(self, upload_furlfile=None, egg_filename_base=None,
                 *args, **kwargs):
        kwargs['command'] = 'flappclient --furlfile %s upload-file %s*.egg' \
                            % (upload_furlfile, egg_filename_base)
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(upload_furlfile=upload_furlfile,
                                 egg_filename_base=egg_filename_base)

class UploadEggToPyPI(PythonCommand):
    """
    Use the 'setup.py upload' tool to upload the .egg to PyPI (requires a
    login/password for PyPI).
    """

    flunkOnFailure = True
    description = ["upload egg to PyPI"]
    name = "upload egg to PyPI"
    python_command = ["setup.py", "bdist_egg", "upload"]

class UploadSdistToPyPI(PythonCommand):
    """
    Use the 'setup.py upload' tool to upload the sdist (.tar.gz) to PyPI
    (requires a login/password for PyPI).
    """

    flunkOnFailure = True
    description = ["upload sdist to PyPI"]
    name = "upload sdist to PyPI"
    python_command = ["setup.py", "sdist", "upload"]

class UpdateAptRepo(ShellCommand):
    """
    Use the 'flappclient' tool to trigger update of the apt repo index.
    """

    flunkOnFailure = True
    description = ["update apt repo"]
    name = "update apt repo"

    def __init__(self, update_furlfile=None, *args, **kwargs):
        kwargs['command'] = 'flappclient --furlfile %s run-command' % (update_furlfile,)
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(update_furlfile=update_furlfile)

class CreateEgg(PythonCommand):
    """
    Step to create an egg so that we can test an egg-installation of Tahoe.
    """

    flunkOnFailure = True
    description = ["create-egg"]
    name = "create-egg"
    python_command = ["setup.py", "bdist_egg"]

class InstallToEgg(PythonCommand):
    """
    Step to install the Tahoe egg into a temporary install directory.
    """

    # If your buildslave doesn't have "easy_install" installed, then this
    # test will fail, but that's okay.
    flunkOnFailure = False
    description = ["install-to-egg"]
    name = "install-to-egg"

    def __init__(self, egginstalldir="egginstalldir", *args, **kwargs):
        # This does the equivalent of:
        #  mkdir _install_temp egginstalldir
        #  cd _install_temp
        #  PYTHONPATH=../egginstalldir easy_install -d ../egginstalldir ../dist/*.egg
        #
        # The temporary directory is necessary to keep certain versions of
        # setuptools (at least distribute-0.6.10, as used on the troublesome
        # buildslave) from seeing the Twisted egg that gets put into the
        # source directory (due to a setup_requires= line that may be
        # obsolete by now). If it sees that egg, it won't install Twisted
        # into the egginstalldir, and then TestFromEgg doesn't work. See
        # #2378 for details.

        python_command = ["-c", ("import glob, os, subprocess, sys;"
                                 " os.mkdir('_install_temp');"
                                 " os.mkdir('"+egginstalldir+"');"
                                 " tahoe_egg = os.path.realpath(glob.glob(os.path.join('dist', '*.egg'))[0]);"
                                 " os.chdir('_install_temp');"
                                 " sys.exit(subprocess.call(['easy_install', '-d', '../"+egginstalldir+"', tahoe_egg]))")]

        kwargs['env'] = {"PYTHONPATH": "../"+egginstalldir}
        kwargs['python_command'] = python_command
        PythonCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(egginstalldir=egginstalldir)

class TestFromEggTrial(PythonCommand):
    """
    Step to run the Tahoe-LAFS tests from the egg-installation. With Trial!
    """
    flunkOnFailure = True
    description = ["test-from-egg"]
    name = "test-from-egg"

    def __init__(self, testsuite=None, egginstalldir="egginstalldir", srcbasedir=".", *args, **kwargs):
        if testsuite:
            assert isinstance(testsuite, basestring)
            pcmd = (
                "import glob,os,subprocess,sys;"
                "os.chdir('"+srcbasedir+"');"
                "eggs=[os.path.realpath(egg) for egg in glob.glob('*.egg')];"
                "testsuite='"+testsuite+"';"
                "os.chdir('"+egginstalldir+"');"
                "eggs+=[os.path.realpath(egg) for egg in glob.glob('*.egg')];"
                "os.environ['PATH']=os.getcwd()+os.pathsep+os.environ['PATH'];"
                "os.environ['PYTHONPATH']=os.pathsep.join(eggs)+os.pathsep+os.environ.get('PYTHONPATH','');"
                "sys.exit(subprocess.call(['trial', testsuite], env=os.environ))")

        else:
            pcmd = (
                "import glob,os,subprocess,sys;"
                "os.chdir('"+srcbasedir+"');"
                "eggs=[os.path.realpath(egg) for egg in glob.glob('*.egg')];"
                "testsuite=subprocess.Popen([sys.executable, 'setup.py', '--name'], stdout=subprocess.PIPE).communicate()[0].strip()+'.test';"
                "os.chdir('"+egginstalldir+"');"
                "eggs+=[os.path.realpath(egg) for egg in glob.glob('*.egg')];"
                "os.environ['PATH']=os.getcwd()+os.pathsep+os.environ['PATH'];"
                "os.environ['PYTHONPATH']=os.pathsep.join(eggs)+os.pathsep+os.environ.get('PYTHONPATH','');"
                "sys.exit(subprocess.call(['trial', testsuite], env=os.environ))")

        python_command = ["-c", pcmd]
        logfiles = {"test.log": egginstalldir+"/_trial_temp/test.log"}
        kwargs['python_command'] = python_command
        kwargs['logfiles'] = logfiles
        PythonCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(testsuite=testsuite, egginstalldir=egginstalldir, srcbasedir=srcbasedir)

class TestFromEgg(PythonCommand):
    """
    Step to run the Tahoe-LAFS tests from the egg-installation.
    """
    flunkOnFailure = True
    description = ["test-from-egg"]
    name = "test-from-egg"

    def __init__(self, testsuite=None, egginstalldir="egginstalldir", srcbasedir=".", *args, **kwargs):
        pcmd = (
            "import glob,os,subprocess,sys;"
            "os.chdir('"+srcbasedir+"');"
            "os.chdir('"+egginstalldir+"');"
            "os.environ['PATH']=os.getcwd()+os.pathsep+os.environ['PATH'];"
            "os.environ['PYTHONPATH']=os.path.realpath('.')+os.pathsep+os.environ.get('PYTHONPATH','');"
            )
        if testsuite:
            assert isinstance(testsuite, basestring)
            pcmd += ("sys.exit(subprocess.call([sys.executable, 'tahoe', 'debug', 'trial', '%s'], env=os.environ))"
                     % (testsuite,))
        else:
            pcmd += ("sys.exit(subprocess.call([sys.executable, 'tahoe', 'debug', 'trial'], env=os.environ))")

        python_command = ["-c", pcmd]
        logfiles = {"test.log": egginstalldir+"/_trial_temp/test.log"}
        kwargs['python_command'] = python_command
        kwargs['logfiles'] = logfiles
        PythonCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(testsuite=testsuite, egginstalldir=egginstalldir, srcbasedir=srcbasedir)

class LineCount(ShellCommand):
    name = "line-count"
    description = ["counting", "lines"]
    flunkOnFailure = False

    def createSummary(self, log):
        self.counts = {}
        count_re = re.compile(r"^(\w+): (\d+)$")
        for line in log.readlines():
            m = count_re.search(line)
            if m:
                name = m.group(1)
                value = int(m.group(2))
                self.setProperty("line-count-%s" % name, value)
                self.counts[name] = value

    def evaluateCommand(self, cmd):
        if self.counts.get("TODO"):
            return WARNINGS
        else:
            return SUCCESS

    def getText(self, cmd, results):
        text = ["line", "counts"]
        for name, value in self.counts.items():
            text.append("%s=%d" % (name, value))
        return text

class CheckMemory(ShellCommand):
    name = "check-memory"
    description = ["checking", "memory", "usage"]
    logfiles = {"stats": "_test_memory/stats.out",
                "nodelog": "_test_memory/client.log",
                "driver": "_test_memory/driver.log",
                }

    def __init__(self, platform, command, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(platform=platform, command=command)
        self.platform = platform
        self.command = command

    def createSummary(self, cmd):
        self.memstats = []
        # TODO: buildbot wants to have BuildStep.getLog("stats")
        for l in self.step_status.getLogs():
            if l.getName() == "stats":
                break
        else:
            return
        fn = open("tahoe-memstats-%s.out" % self.platform, "w")
        for line in l.readlines():
            fn.write(line)
            if ":" not in line:
                continue
            name, value = line.split(":")
            value = int(value.strip())
            self.setProperty("memory-usage-%s" % name, value)
            self.memstats.append( (name,value) )
        fn.close()

    def getText(self, cmd, results):
        text = ["memory", "usage"]
        modes = []
        peaks = {}
        for name, value in self.memstats:
            # current values of 'name' are:
            #  upload {0B,10kB,10MB,50MB}
            #  upload-POST {0B,10kB,10MB,50MB}
            #  download {0B,10kB,10MB,50MB}
            #  download-GET {0B,10kB,10MB,50MB}
            #  download-GET-slow {0B,10kB,10MB,50MB}
            #  receive {0B,10kB,10MB,50MB}
            #
            # we want to make these as short as possible to keep the column
            # narrow, so strings like "up-10k: 22M" and "POST-10M: 54M".
            # Also, only show the largest test of each type.
            mode, size = name.split()
            mode = {"upload": "up",
                    "upload-POST": "post",
                    "upload-self": "self",
                    "download": "down",
                    "download-GET": "get",
                    "download-GET-slow": "slow",
                    "receive": "rx",
                    }.get(mode, mode)
            if value >= 1e6:
                value_s = "%dM" % (value / 1e6)
            elif value >= 1e3:
                value_s = "%dk" % (value / 1e3)
            else:
                value_s = "%d" % value
            if size != "init":
                size_s = size
                if size_s.endswith("B"):
                    size_s = size_s[:-1]
                size_int = self._convert(size)
                if mode not in modes:
                    modes.append(mode)
                if mode not in peaks or (size_int > peaks[mode][0]):
                    peaks[mode] = (size_int, size_s, value_s)
            if name == "upload init":
                text.append("init: %s" % (value_s,))
        for mode in modes:
            size, size_s, value_s = peaks[mode]
            text.append("%s-%s: %s" % (mode, size_s, value_s))
        return text

    def _convert(self, value):
        if value.endswith("B"):
            value = value[:-1]
        if value.endswith("M"):
            return 1e6 * int(value[:-1])
        elif value.endswith("k"):
            return 1e3 * int(value[:-1])
        else:
            return int(value)

class CheckSpeed(ShellCommand):
    name = "check-speed"
    description = ["running", "speed", "test"]
    descriptionDone = ["speed", "test"]

    def __init__(self, clientdir, linkname, MAKE, *args, **kwargs):
        ShellCommand.__init__(self, *args, **kwargs)
        self.addFactoryArguments(clientdir=clientdir, linkname=linkname, MAKE=MAKE)
        self.command = [MAKE, "check-speed", "TESTCLIENTDIR=%s" % clientdir]
        self.linkname = linkname

    def createSummary(self, cmd):
        for l in self.step_status.getLogs():
            if l.getName() == "stdio":
                break
        else:
            return
        for line in l.readlines():
            if ":" not in line:
                continue
            line = line.strip()
            # we're following stdout here, so random deprecation warnings and
            # whatnot will also have ":" in them and might confuse us.
            name, value = line.split(":", 1)
            # we record Ax+B in build properties
            if name == "upload per-file time":
                self.setProperty("upload-B", self.parse_seconds(value))
            elif name.startswith("upload speed ("):
                # later tests (with larger files) override earlier ones
                self.setProperty("upload-A", self.parse_rate(value))
            elif name == "download per-file time":
                self.setProperty("download-B", self.parse_seconds(value))
            elif name.startswith("download speed ("):
                self.setProperty("download-A", self.parse_rate(value))

            elif name == "download per-file times-avg-RTT":
                self.setProperty("download-B-RTT", float(value))
            elif name == "upload per-file times-avg-RTT":
                self.setProperty("upload-B-RTT", float(value))

            elif name == "create per-file time SSK":
                self.setProperty("create-B-SSK", self.parse_seconds(value))
            elif name == "upload per-file time SSK":
                self.setProperty("upload-B-SSK", self.parse_seconds(value))
            elif name.startswith("upload speed SSK ("):
                self.setProperty("upload-A-SSK", self.parse_rate(value))
            elif name == "download per-file time SSK":
                self.setProperty("download-B-SSK", self.parse_seconds(value))
            elif name.startswith("download speed SSK ("):
                self.setProperty("download-A-SSK", self.parse_rate(value))

    def parse_seconds(self, value):
        if value.endswith("s"):
            value = value[:-1]
        return float(value)

    def parse_rate(self, value):
        if value.endswith("MBps"):
            return float(value[:-4]) * 1e6
        if value.endswith("kBps"):
            return float(value[:-4]) * 1e3
        if value.endswith("Bps"):
            return float(value[:-4])

    def format_seconds(self, s):
        # 1.23s, 790ms, 132us
        s = float(s)
        if s >= 1.0:
            return "%.2fs" % s
        if s >= 0.01:
            return "%dms" % (1000*s)
        if s >= 0.001:
            return "%.1fms" % (1000*s)
        return "%dus" % (1000000*s)

    def format_rate(self, r):
        # 21.8kBps, 554.4kBps 4.37MBps
        r = float(r)
        if r > 1000000:
            return "%1.2fMBps" % (r/1000000)
        if r > 1000:
            return "%.1fkBps" % (r/1000)
        return "%dBps" % r

    def getText(self, cmd, results):
        text = ["speed"]
        f = open("tahoe-speed-%s.out" % self.linkname, "w")
        try:
            up_A = self.getProperty("upload-A")
            f.write("upload-A: %f\n" % up_A)
            up_B = self.getProperty("upload-B")
            f.write("upload-B: %f\n" % up_B)
            text.extend(["up:",
                         self.format_seconds(up_B),
                         self.format_rate(up_A)])
            up_B_rtt = self.getProperty("upload-B-RTT")
            f.write("upload-B-RTT: %f\n" % up_B_rtt)
        except KeyError:
            pass

        try:
            down_A = self.getProperty("download-A")
            f.write("download-A: %f\n" % down_A)
            down_B = self.getProperty("download-B")
            f.write("download-B: %f\n" % down_B)
            text.extend(["down:",
                         self.format_seconds(down_B),
                         self.format_rate(down_A)])
            down_B_rtt = self.getProperty("download-B-RTT")
            f.write("download-B-RTT: %f\n" % down_B_rtt)
        except KeyError:
            pass

        try:
            create_B_SSK = self.getProperty("create-B-SSK")
            up_B_SSK = self.getProperty("upload-B-SSK")
            up_A_SSK = self.getProperty("upload-A-SSK")
            f.write("create-B-SSK: %f\n" % create_B_SSK)
            # create-B-SSK used to be upload-B-SSK
            f.write("upload-B-SSK: %f\n" % up_B_SSK)
            f.write("upload-A-SSK: %f\n" % up_A_SSK)
            down_B_SSK = self.getProperty("download-B-SSK")
            down_A_SSK = self.getProperty("download-A-SSK")
            f.write("download-B-SSK: %f\n" % down_B_SSK)
            f.write("download-A-SSK: %f\n" % down_A_SSK)
            text.extend(["SSK:",
                         "c:%s" % self.format_seconds(create_B_SSK),
                         "u:%s" % self.format_seconds(up_B_SSK),
                         self.format_rate(up_A_SSK),
                         "d:%s" % self.format_seconds(down_B_SSK),
                         self.format_rate(down_A_SSK),
                         ])
        except KeyError:
            pass

        f.close()
        return text
