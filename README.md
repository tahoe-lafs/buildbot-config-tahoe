buildbot-config-tahoe
=====================

Buildbot config for Tahoe-LAFS and related projects

Secrets
=======

Some secrets are managed with [sops](https://github.com/mozilla/sops).

To deploy updated secrets:

1. Make sure you have pgp agent forwarding.
1. Update the checkout on the buildmaster.
2. Run `sops -d secrets.enc.yaml > secrets.yaml`.
   Only this operation requires your pgp key.
3. Restart the buildmaster.

To modify secrets:

1. Run `sops secrets.enc.yaml`.
2. Make changes, save, exit.
3. Check in to version control.

To add a new contributor:

1. `sops --add-pgp <fingerprint> secrets.enc.yaml`

See `sops --help` and the GitHub page for more usage information.
