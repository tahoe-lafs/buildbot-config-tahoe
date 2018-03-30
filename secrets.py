# -*- coding: utf-8 -*-

import yaml

with open("secrets.yaml") as secrets_fobj:
    secrets = yaml.safe_load(secrets_fobj)
