# buildbot-config-tahoe

Buildbot config for Tahoe-LAFS and related projects

# Secrets

## Sops

Some secrets are managed with [sops](https://github.com/mozilla/sops).

To use sops on the buildmaster, set up sops keyservice forwarding::

```
Host tahoe-lafs.org
     User buildmaster

     # Get a sops keyservice
     PermitLocalCommand yes
     LocalCommand sops keyservice --network unix --address /var/run/user/1000/sops-keyservice.sock &
     # Forward the sops keyservice
     RemoteForward /var/run/user/1007/<per-user-identifier>-sops-keyservice.sock /var/run/user/1000/sops-keyservice.sock
```

The first path given to ``RemoteForward`` is the remote path.
The per-user-identifier in this path avoids a conflict between multiple clients logging in to the buildmaster with this configuration at the same time.
Take note of the remote path for the next steps.

Note that the ``sops keyservice`` command will keep running after the SSH session completes.
Future SSH sessions will not spawn additional keyservices, though.
You can also skip this ssh configuration and run the keyservice manually, of course.

### Deploy Updated Secrets

This is the only step which is typically executed on the buildmaster.

1. Update the checkout on the buildmaster.
2. Run `sops --keyservice unix://$REMOTE_PATH -d secrets.enc.yaml > secrets.yaml`.
   Only this operation requires the keyservice.
3. Restart the buildmaster.

### Modify Secrets

Perform this step locally.
This avoids the need to deal with keyservice forwarding.

1. Run `sops secrets.enc.yaml`.
2. Make changes, save, exit.
3. Check in to version control.

### Add a New Contributor

Perform this step locally.
This avoids the need to deal with keyservice forwarding.

1. `sops --add-pgp <fingerprint> secrets.enc.yaml`

See `sops --help` and the GitHub page for more usage information.
