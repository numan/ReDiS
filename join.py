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
from route53 import Route53Zone
from ec2 import EC2

from events import Events

# your amazon keys
key = os.environ['EC2_KEY_ID']
access = os.environ['EC2_SECRET_KEY']

# what is the domain to work with
name = os.environ['REDIS_NAME'].strip()
zone_name = os.environ['HOSTED_ZONE_NAME']
zone_id = os.environ['HOSTED_ZONE_ID']

# the name (and identity) of the cluster (the master)
cluster = "{0}.{1}".format(name, zone_name.rstrip('.'))

# get/create the cluster environment
cluster = Cluster(key, access, cluster)
r53_zone = Route53Zone(key, access, zone_id)
ec2 = EC2(key, access)

events = Events(key, access, cluster.name())
node = Host(cluster).get_node()
component = os.path.basename(sys.argv[0])
def log(message, verbose='normal'):
	events.log(node, component, message, verbose)

if __name__ == '__main__':
	log('joining the cluster')
	# and get the instance up and running
	log('configuring the host', 'debug')
	host = Host(cluster.domain.name)

	node = host.get_node()
	endpoint = host.get_endpoint()

	log('adding the node to the cluster', 'debug')
	# now we are ready to be (added to) the cluster
	cluster.add_node(node, endpoint)
	log('creating a Route53 records', 'debug')
	r53_zone.create_record(node, endpoint)
	log('setting the tag', 'debug')
	ec2.set_tag(node)

	log('getting the master of the node', 'debug')
	master = cluster.get_master(node)
	# if we don't have a master, we ARE the master
	if master == None:
		log('setting the main Route53 record for the cluster', 'debug')
		r53_zone.update_record(cluster.domain.name, endpoint)

		# and make sure we 'run' correctly (no-slave, well-monitored)
		log('set the host to run as master', 'debug')
		host.set_master()
	else:
		# attach to the master (and start watching its availability)
		log('set the host to run as slave of {0}'.format(master), 'debug')
		host.set_master(master)

	log('joined the cluster')
