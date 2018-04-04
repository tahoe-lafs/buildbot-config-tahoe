# -*- coding: utf-8 -*-

from os.path import dirname, join

import yaml

secrets_yaml = join(dirname(__file__), "secrets.yaml")
with open(secrets_yaml) as secrets_fobj:
    secrets = yaml.safe_load(secrets_fobj)
