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

import os, sys, redis

from urllib2 import urlopen

from cluster import Cluster
from host import Host
from route53 import Route53Zone
from ec2 import EC2

# your amazon keys
key = os.environ['EC2_KEY_ID']
access = os.environ['EC2_SECRET_KEY']

# what is the domain to work with
name = os.environ['REDIS_NAME'].strip()
zone_name = os.environ['HOSTED_ZONE_NAME'].rstrip('.')
zone_id = os.environ['HOSTED_ZONE_ID']

# the name (and identity) of the cluster (the master)
cluster = "{0}.{1}".format(name, zone_name)

# get/create the cluster environment
cluster = Cluster(key, access, cluster)
r53_zone = Route53Zone(key, access, zone_id)
ec2 = EC2(key, access)

r = redis.StrictRedis(host='localhost', port=6379)

if __name__ == '__main__':
	# get the host (uses domain name, gets the rest from the instance itself)
	host = Host(cluster.domain.name)

	node = host.get_node()
	endpoint = host.get_endpoint()

	# make sure we get the redis master, perhaps our master is already gone
	# from the cluster
	try:
		info = r.info()
		link_status = info['master_link_status']

		if link_status != "up":
			link_down_since_seconds = info['master_link_down_since_seconds']

			down = (link_down_since_seconds > 30)
		else:
			down = False
	except Exception as e:
		down = True

	if down:
		master = r.info()['master_host']
		print "master: {0}".format(master)
		if cluster.exists(master):
			grandmaster = cluster.get_master(master)
			print "{0} = cluster.get_master({1})".format(grandmaster, master)

			# and make sure the master doesn't participate anymore
			cluster.incarcerate_node(master)
			print "cluster.incarcerate_node({0})".format(master)
		else:
			grandmaster = cluster.get_master(node)
			print "{0} = cluster.get_master({1})".format(grandmaster, node)

		if grandmaster == None:
			r53_zone.update_record(cluster.domain.name, endpoint)
			print "r53_zone.update_record({0}, {1})".format(cluster.domain.name, endpoint)
			host.set_master()
			print "host.set_master()"
		else:
			host.set_master(grandmaster)
			print "host.set_master({0})".format(grandmaster)
	else:
		print "master is up (and running)"
