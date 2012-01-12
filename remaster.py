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

import os
import sys
import json

from urllib2 import urlopen

from cluster import Cluster
from host import Host

# your amazon keys
key = os.environ['EC2_KEY_ID']
access = os.environ['EC2_SECRET_KEY']

# what is the domain to work with
name = os.environ['REDIS_NAME'].strip()
zone = os.environ['HOSTED_ZONE_NAME'].rstrip('.')

# the name (and identity) of the cluster (the master)
name = "{0}.{1}".format(name, zone)

# get/create the cluster environment
cluster = Cluster(key, access, name, userdata)

if __name__ == '__main__':
	# first, we have to get the instance
	host = Host(key, access, name, userdata)

	node = host.get_node()
	endpoint = host.get_endpoint()

	# get the failing master
	old = cluster.get_master(node)
	cluster.delete_node(old)

	new = cluster.get_master(node)
	host.set_master(new)
	if new == None:
		route53.update_record(name, endpoint)
