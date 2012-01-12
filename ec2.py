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
import platform
import json, urllib2

from boto.ec2.connection import EC2Connection
from boto.ec2.regioninfo import RegionInfo

class EC2:
	def __init__(self, key, access):
		try:
			url = "http://169.254.169.254/latest/meta-data/"

			self.instance_id = urllib2.urlopen(url + "instance-id").read()

			zone = urllib2.urlopen(url + "placement/availability-zone").read()
			region = zone[:-1]
		except Exception as e:
			exit( "We couldn't get user-data or other meta-data..." + e)

		endpoint = "ec2.{0}.amazonaws.com".format(region)
		region_info = RegionInfo(name=region, endpoint=endpoint)
		self.ec2 = EC2Connection(key, access, region=region_info)

	def set_tag(self, tag):
		self.ec2.create_tags( [self.instance_id], { "Name": tag.rstrip('.') })

	def unset_tag(self):
		self.ec2.delete_tags( [self.instance_id], [ "Name" ])

if __name__ == '__main__':
	key = os.environ['EC2_KEY_ID']
	access = os.environ['EC2_SECRET_KEY']

	# easy testing, use like this (requires environment variables)
	#	python cluster.py get_master cluster 2c922342a.cluster
	ec2 = EC2(key, access)
	print getattr(ec2, sys.argv[1])(*sys.argv[2:])
