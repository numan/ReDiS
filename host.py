# Copyright (C) 2011, 2012 9apps B.V.
# 
# This file is part of Redis for AWS.
# 
# Redis for AWS is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Redis for AWS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Redis for AWS. If not, see <http://www.gnu.org/licenses/>.


import os, sys

import json
import hashlib
import redis

from urllib2 import urlopen

#
# REDIS HOST
#
# ...
#
class Host:
	def __init__(self, cluster):
		try:
			url = "http://169.254.169.254/latest/"
			self.endpoint = urlopen(url + "meta-data/public-hostname").read()
			self.userdata = json.load(urlopen(url + "user-data"))
		except:
			sys.exit("We should be getting user-data here...")

		self.cluster = cluster
		self.id = hashlib.md5(self.endpoint).hexdigest()[:8]
		self.node = "{0}.{1}".format(self.id, self.cluster)
		self.master = None

		self.redis = redis.StrictRedis(host="localhost", port=6379)

	def get_node(self):
		return self.node

	def get_endpoint(self):
		return self.endpoint

	def get_master(self):
		return self.master

	def set_master(self, master=None):
		self.master = master
		if None == master:
			self.redis.slaveof()

			os.system("/usr/sbin/monit unmonitor is-slave")
			os.system("/usr/sbin/monit monitor is-master")
		else:
			self.redis.slaveof(master, 6379)

			os.system("/usr/sbin/monit monitor is-slave")
			os.system("/usr/sbin/monit unmonitor is-master")

	def monitor(self):
		os.system("/usr/sbin/monit monitor redis")
		self.set_master()

	def unmonitor(self):
		os.system("/usr/sbin/monit unmonitor redis")
		os.system("/usr/sbin/monit unmonitor is-slave")
		os.system("/usr/sbin/monit unmonitor is-master")

if __name__ == '__main__':
	# easy testing, use like this (requires environment variables)
	#	python host.py set_master cluster 2c922342a.cluster
	host = Host(sys.argv[2])
	print getattr(host, sys.argv[1])(*sys.argv[3:])
