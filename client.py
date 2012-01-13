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

from urllib2 import urlopen
from time import gmtime,strftime

from boto.sdb.connection import SDBConnection
from boto.sdb.regioninfo import RegionInfo

#
# ReDiS CLIENT
#
#
class Client:
	def __init__(self, key, access, cluster):
		try:
			url = "http://169.254.169.254/latest/meta-data/"

			zone = urlopen(url + "placement/availability-zone").read()
			region = zone[:-1]
		except:
			sys.exit("We should be getting user-data here...")

		endpoint = "sdb.{0}.amazonaws.com".format(region)
		region_info = RegionInfo(name=region, endpoint=endpoint)

		sdb = SDBConnection(key, access, region=region_info)

		self.domain = sdb.lookup(cluster, True)
		self.metadata = self.domain.get_item('metadata', True)
	
	def get_endpoint(self, node):
		try:
			return self.domain.get_item(node)['endpoint']
		except:
			return None

	def get_master(self, node=None):
		try:
			master = self.domain.get_item(node)['master']

			return master
		except
			return self.metadata['master']

	def get_slave(self, node=None):
		try:
			slave = self.domain.get_item(node)['slave']

			return slave
		except:
			return self.metadata['slave']
	
	def size(self):
		select = "select count(*) from `{0}` where itemName() like '%.{0}'".format(self.domain.name)
		return int(self.domain.select(select).next()['Count'])

	def slaves(self):
		select = "select itemName() from `{0}` where master is not null and itemName() like '%.{0}'".format(self.domain.name)
		items = self.domain.select(select)
		
		slaves = []
		for item in items:
			slaves.append(item.name)

		return slaves

if __name__ == '__main__':
	key = os.environ['EC2_KEY_ID']
	access = os.environ['EC2_SECRET_KEY']

	# easy testing, use like this (requires environment variables)
	#	python client.py get_master client 2c922342a.client
	client = Client(key, access, sys.argv[2])
	print getattr(client, sys.argv[1])(*sys.argv[3:])
