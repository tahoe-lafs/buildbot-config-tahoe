# -*- coding: utf-8 -*-

from os.path import dirname, join

import yaml

config_yaml = join(dirname(__file__), "config.yaml")
with open(config_yaml) as config_fobj:
    config = yaml.safe_load(config_fobj)
