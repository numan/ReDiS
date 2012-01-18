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
zone_name = os.environ['HOSTED_ZONE_NAME'].rstrip('.')
zone_id = os.environ['HOSTED_ZONE_ID']

# the name (and identity) of the cluster (the master)
cluster = "{0}.{1}".format(name, zone_name)

# get/create the cluster environment
cluster = Cluster(key, access, cluster)
r53_zone = Route53Zone(key, access, zone_id)
ec2 = EC2(key, access)

events = Events(sys.argv[1], sys.argv[2], cluster)
node = Host(cluster).get_node()
component = os.path.basename(sys.argv[0])
def log(message, verbose='normal'):
    events.log(node, component, message, verbose)

if __name__ == '__main__':
	log('leaving the cluster')
	try:
		# get the host, us
		log('get the host', 'debug')
		host = Host(cluster.domain.name)
		# make sure we are not connected to anything anymore
		log('disconnect from other nodes', 'debug')
		host.set_master()

		node = host.get_node()
		endpoint = host.get_endpoint()
	except Exception as e:
		log(e)

	try:
		# delete all there is to us
		log('unset the tag', 'debug')
		ec2.unset_tag()
	except Exception as e:
		log(e)

	try:
		log('delete the Route53 record', 'debug')
		r53_zone.delete_record(node)
	except Exception as e:
		log(e)

	try:
		log('delete from the cluster', 'debug')
		cluster.delete_node(node)

		# and the last to leave, please close the door
		size = cluster.size()
		if size <= 0:
			log('delete the master Route53 record', 'debug')
			r53_zone.delete_record(cluster.domain.name)
	except Exception as e:
		log(e)
