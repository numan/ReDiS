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

from events import Events

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

events = Events(key, access, cluster.name())
node = Host(cluster).get_node()
component = os.path.basename(sys.argv[0])
def log(message, logging='info'):
	events.log(node, component, message, logging)

r = redis.StrictRedis(host='localhost', port=6379)

if __name__ == '__main__':
	# get the host (uses domain name, gets the rest from the instance itself)
	host = Host(cluster.domain.name)

	node = host.get_node()
	endpoint = host.get_endpoint()

	# make sure we get the redis master, perhaps our master is already gone
	# from the cluster
	try:
		log('get Redis INFO', 'info')
		info = r.info()
		log('get the link_status', 'info')
		link_status = info['master_link_status']

		log('determine if our master is up', 'info')
		if link_status != "up":
			log('how long are we down?', 'info')
			link_down_since_seconds = info['master_link_down_since_seconds']

			down = (link_down_since_seconds > 30)
		else:
			down = False
	except Exception as e:
		log('we are down, or we were master, in case we should not be here ', 'info')
		down = True

	if down:
		log('down: find a new master!', 'info')
		master = r.info()['master_host']
		log("master: {0}".format(master), 'info')
		if cluster.exists(master):
			grandmaster = cluster.get_master(master)
			log("{0} = cluster.get_master({1})".format(grandmaster, master), 'info')

			# and make sure the master doesn't participate anymore
			cluster.incarcerate_node(master)
			log("cluster.incarcerate_node({0})".format(master), 'info')
		else:
			grandmaster = cluster.get_master(node)
			log("{0} = cluster.get_master({1})".format(grandmaster, node), 'info')

		if grandmaster == None:
			r53_zone.update_record(cluster.domain.name, endpoint)
			log("r53_zone.update_record({0}, {1})".format(cluster.domain.name, endpoint), 'info')
			host.set_master()
			log("host.set_master()", 'info')
		else:
			host.set_master(grandmaster)
			log("host.set_master({0})".format(grandmaster), 'info')
	else:
		log("master is up (and running)", 'info')
