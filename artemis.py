import sys
import os
import yaml
import boto3

class Artemis(object):
	def __init__(self, config_file):
		self.config = yaml.load_file(config_file)

if __name__ == '__main__':
    pass
