buildbot-config-tahoe
=====================

Buildbot config for Tahoe-LAFS and related projects

Secrets
=======

Some secrets are managed with [sops](https://github.com/mozilla/sops).
To deploy updated secrets:

1. Make sure you have pgp agent forwarding.
1. Update the checkout on the buildmaster.
2. Run `sops -d secrets.yaml.enc > secrets.yaml`.
   Only this operation requires your pgp key.
3. Restart the buildmaster.
