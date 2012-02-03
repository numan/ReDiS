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
import json, urllib2

from boto.ec2.connection import EC2Connection
from boto.ec2.regioninfo import RegionInfo

import administration, backup
from host import Host
from events import Events

try:
	url = "http://169.254.169.254/latest/"

	userdata = json.load(urllib2.urlopen(url + "user-data"))
except Exception as e:
	print e
	exit( "We couldn't get user-data or other meta-data...")

device = "/dev/sdf"
mount = "/var/lib/redis"

# we are going to work with local files, we need our path
path = os.path.dirname(os.path.abspath(__file__))

def delete_monitor():
	os.system( "rm {0}/etc/monit/data".format(path))

def decommission(key, access, cluster, persistence="no"):
	events = Events(key, access, cluster)
	node = Host(cluster, events).get_node()
	def log(message, logging='warning'):
		events.log(node, 'Decommission', message, logging)

	log('start dommissioning', 'info')
	# make a last backup
	if "no" != persistence:
		log('make last backups, first RDB', 'info')
		# take the latest RDB and move it to S3
		rdb = backup.put_RDB(key, access, cluster, 'monthly')
		administration.set_RDB(key, access, cluster, rdb)

		# make a last snapshot
		log('and now a snapshot', 'info')
		snapshot = backup.make_snapshot(key, access, cluster, 'monthly')
		administration.add_snapshot(key, access, cluster, snapshot)

		delete_monitor()

	# we don't have to get rid any the volume, it is deleted on termination

	# change to the default (no persistence)
	log('remove redis.conf', 'info')
	os.system("/bin/rm -f /etc/redis/redis.conf")
	# and empty the cron as well
	log('empty the cron', 'info')
	os.system("/bin/echo | /usr/bin/crontab")

	# make sure we make a clean AMI, with all monit checks monitored
	log('finally, monitor all (monit), for making AMIs', 'info')
	os.system("/usr/sbin/monit monitor all")

if __name__ == '__main__':
	import os, sys

	try:
		persistence = userdata['persistence']
	except:
		persistence = None

	# what is the domain to work with
	name = os.environ['REDIS_NAME'].strip()
	zone = os.environ['HOSTED_ZONE_NAME'].rstrip('.')

	# the name (and identity) of the cluster (the master)
	cluster = "{0}.{1}".format(name, zone)

	decommission(sys.argv[1], sys.argv[2], cluster, persistence=persistence)
