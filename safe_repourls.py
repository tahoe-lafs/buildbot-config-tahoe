
# the webhook sends us: https://github.com/tahoe-lafs/tahoe-lafs
# We used to replace this with git: (because some buildslaves had problems
# with SSL), but now we don't.

from zope.interface import implements
from buildbot.interfaces import IRenderable
from twisted.python import log

class GoodRepo:
    implements(IRenderable)
    def __init__(self, repos, default_repourl):
        self.repos = repos
        self.default_repourl = default_repourl
    def getRenderingFor(self, props):
        # the 'repository' property might be missing or an empty string
        repourl = props.getProperty("repository", None) or self.default_repourl
        if repourl not in self.repos:
            log.msg("refusing to build from unsafe repo '%s'"
                    " (will only accept: %s)" % (repourl, ",".join(self.repos)))
            raise ValueError("refusing to build from unsafe repo, see logs")
        return repourl

