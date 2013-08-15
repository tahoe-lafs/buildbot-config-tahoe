
"""
Github post-commit web hook Buildbot ChangeSource

This ChangeSource lets builds be triggered by the Github post-commit webhook.
It adds a special resource to your WebStatus server which listens for change
information. You then configure github to POST to this URL after each commit.

To use this, in your buildbot master.cfg, create a WebStatus instance but not
a ChangeSource. Pick a URL under your WebStatus (the default is /github_hook
, but you can make it unguessable if you want to decrease the chances that an
attacker can push fake changes to your buildmaster). If your WebStatus is
normally reachable at http://example.org:8010 , then the default posthook URL
would be http://example.org:8010/github_hook .

Then call github_posthook.setup(BuildmasterConfig, webstatus, url_path)

That will create the necessary Resource, attach it to your webstatus in the
right place, and glue it into a new ChangeSource.

Then, on your Github repo, use the Admin page, under 'Service Hooks', and add
this URL into the 'Post-Receive URLs' section.

"""

import json
import re
from twisted.internet import defer
from twisted.web.resource import Resource
from datetime import datetime, timedelta

from buildbot.changes.base import ChangeSource

def parse_iso9601(s):
    # returns a datetime. sometimes I hate python
    # note: look at http://pypi.python.org/pypi/iso8601plus/0.1.6
    mo = re.search(r'^([\d\-]+T(?:\d+):(?:\d+):(?:\d+))(.*)$', s)
    time_string = mo.group(1) ; tz_string = mo.group(2)
    mo = re.search(r'^([+-]*)(\d+):(\d+)$', tz_string)
    tz_sign = mo.group(1) ; tz_hour = mo.group(2); tz_min = mo.group(3)
    d = datetime.strptime(time_string, "%Y-%m-%dT%H:%M:%S")
    offset_seconds = (60*int(tz_hour)+int(tz_min))*60
    if tz_sign == "-":
        offset_seconds = -offset_seconds
    return d + timedelta(seconds=-offset_seconds)

class GithubHookChangeSource(ChangeSource):
    def addChangeFromHook(self, ign, payload, change, branch):
        p = payload
        c = change
        d = self.master.addChange(author=c["author"]["email"],
                                  files=(c["modified"]+c["added"]),
                                  comments=c["message"],
                                  when_timestamp=parse_iso9601(c["timestamp"]),
                                  revision=c["id"],
                                  branch=branch,
                                  # guard this with a GoodRepo!
                                  repository=p["repository"]["url"],
                                  revlink=c["url"])
        return d

class GithubHook(Resource):
    def __init__(self, cs):
        Resource.__init__(self)
        self.cs = cs
    def render_POST(self, request):
        # By default, github post-receive URLs are handed an
        # application/x-www-form-urlencoded body with one field named
        # "payload" that contains JSON. The repo admin page only lets you
        # change the target URL. If you use the github API
        # (http://developer.github.com/v3/repos/hooks/), you can change other
        # settings for each hook (see
        # https://github.com/github/github-services/blob/master/services/web.rb
        # for details), including .content_type="json", which will give you
        # application/json that could be parsed by json.load(request.content)
        p = json.loads(request.args["payload"][0])
        d = defer.succeed(None)
        for c in p["commits"]:
            branch = p["ref"].split("/",2)[2]
            d.addCallback(self.cs.addChangeFromHook, payload=p, change=c,
                          branch=branch)
        if not p["commits"] and p["ref"].startswith("refs/tags/"):
            # a tag was pushed. Pretend the new value was just committed.
            # Note that if you push a new branch tip and a tag at the same
            # time, we'll see two separate commits occur right next to each
            # other, on the same branch, for the same revision. As long as
            # the buildmaster's treeStableTimer is more than about 0.5s,
            # these should be merged into the same build.
            if "base_ref" in p:
                # .bash_ref seems to be set when the tag happens to point at
                # a branch head. So we can pretend the tag is a new commit on
                # the branch head.
                branch = p["base_ref"].split("/",2)[2]
            else:
                # the tag points elsewhere, so we don't know what branch it
                # is on. Leave the branch blank and hope for the best.
                branch = None
            d.addCallback(self.cs.addChangeFromHook, payload=p,
                          change=p["head_commit"], branch=branch)
        request.setHeader("content-type", "text/plain")
        return "Thanks!\n"

def setup(c, ws, url_path="github_hook"):
    c['change_source'] = cs = GithubHookChangeSource()
    ws.putChild(url_path, GithubHook(cs))
