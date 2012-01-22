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
import json, hashlib

from urllib2 import urlopen
from datetime import datetime

from boto.ec2.cloudwatch import CloudWatchConnection
from boto.ec2.regioninfo import RegionInfo

from cluster import Cluster
from host import Host

#
# REDIS MONITOR
#
#
class Monitor:
	def __init__(self, key, access, cluster):
		try:
			url = "http://169.254.169.254/latest/meta-data/"

			public_hostname = urlopen(url + "public-hostname").read()
			zone = urlopen(url + "placement/availability-zone").read()
			region = zone[:-1]
		except:
			sys.exit("We should be getting user-data here...")

		# the name (and identity) of the cluster (the master)
		self.cluster = cluster

		# get the host
		self.host = Host(cluster)

		self.redis = redis.StrictRedis(host='localhost', port=6379)

		endpoint = "monitoring.{0}.amazonaws.com".format(region)
		region_info = RegionInfo(name=region, endpoint=endpoint)

		self.cloudwatch = CloudWatchConnection(key, access, region=region_info)
		self.namespace = '9apps/redis'

	def collect(self):
		now = datetime.now()

		items = self.redis.info()

		names = []
		values = []
		units = []
		dimensions = { 'node' : self.host.get_node(),
					'cluster' : self.cluster }

		if items['aof_enabled']:
			names.append('bgrewriteaof_in_progress')
		values.append(items['bgrewriteaof_in_progress'])
		units.append('Count')

		names.append('aof_pending_bio_fsync')
		values.append(items['aof_pending_bio_fsync'])
		units.append('Count')

		names.append('aof_buffer_length')
		values.append(items['aof_buffer_length'])
		units.append('Count')

		names.append('aof_current_size')
		values.append(items['aof_current_size'])
		units.append('Bytes')

		names.append('aof_pending_rewrite')
		values.append(items['aof_pending_rewrite'])
		units.append('Count')

		names.append('aof_base_size')
		values.append(items['aof_base_size'])
		units.append('Bytes')

		# master/slave
		names.append(items['role'])
		values.append(1)
		units.append('Count')

		for item in items:
			if item >= 'db0' and item < 'dc':
				names.append("{0}_keys".format(item))
				values.append(items[item]['keys'])
				units.append('Count')

				names.append("{0}_expires".format(item))
				values.append(items[item]['expires'])
				units.append('Count')

		# pub/sub
		names.append('pubsub_channels')
		values.append(items['pubsub_channels'])
		units.append('Count')

		names.append('pubsub_patterns')
		values.append(items['pubsub_patterns'])
		units.append('Count')

		# memory
		names.append('used_memory')
		values.append(items['used_memory'])
		units.append('Bytes')

		names.append('used_memory_peak')
		values.append(items['used_memory_peak'])
		units.append('Bytes')

		names.append('used_memory_rss')
		values.append(items['used_memory_rss'])
		units.append('Bytes')

		names.append('mem_fragmentation_ratio')
		values.append(items['mem_fragmentation_ratio'])
		units.append('None')

		names.append('connected_slaves')
		values.append(items['connected_slaves'])
		units.append('Count')

		#
		names.append('loading')
		values.append(items['loading'])
		units.append('Count')

		names.append('bgsave_in_progress')
		values.append(items['bgsave_in_progress'])
		units.append('Count')

		# clients
		names.append('connected_clients')
		values.append(items['connected_clients'])
		units.append('Count')

		names.append('blocked_clients')
		values.append(items['blocked_clients'])
		units.append('Count')

		# connection/command totals
		names.append('total_connections_received')
		values.append(items['total_connections_received'])
		units.append('Count')

		names.append('total_commands_processed')
		values.append(items['total_commands_processed'])
		units.append('Count')

		# client input/output
		names.append('client_biggest_input_buf')
		values.append(items['client_biggest_input_buf'])
		units.append('Bytes')

		names.append('client_longest_output_list')
		values.append(items['client_longest_output_list'])
		units.append('Bytes')

		# keys
		names.append('expired_keys')
		values.append(items['expired_keys'])
		units.append('Count')

		names.append('evicted_keys')
		values.append(items['evicted_keys'])
		units.append('Count')

		# last_save
		names.append('changes_since_last_save')
		values.append(items['changes_since_last_save'])
		units.append('Count')

		# keyspace
		names.append('keyspace_misses')
		values.append(items['keyspace_misses'])
		units.append('Count')

		names.append('keyspace_hits')
		values.append(items['keyspace_hits'])
		units.append('Count')

		return [names, values, units, dimensions]

	def put(self):
		# first get all we need
		[names, values, units, dimensions] = self.collect()

		# we can't send all at once, only 20 at a time
		# first aggregated over all
		result1 = self.cloudwatch.put_metric_data(self.namespace,
										names[:20], value=values[:20],
										unit=units[:20])
		result2 = self.cloudwatch.put_metric_data(self.namespace,
										names[20:], value=values[20:],
										unit=units[20:])
		for dimension in dimensions:
			dimension = { dimension : dimensions[dimension] }
			result1 = self.cloudwatch.put_metric_data(self.namespace,
										names[:20], value=values[:20],
										unit=units[:20],
										dimensions=dimension)
			result2 = self.cloudwatch.put_metric_data(self.namespace,
										names[20:], value=values[20:],
										unit=units[20:],
										dimensions=dimension)
		return (result1 and result2)
	
	def metrics(self):
		return self.cloudwatch.list_metrics()

if __name__ == '__main__':
	key = os.environ['EC2_KEY_ID']
	access = os.environ['EC2_SECRET_KEY']

	name = os.environ['REDIS_NAME'].strip()
	zone = os.environ['HOSTED_ZONE_NAME'].rstrip('.')
	cluster = "{0}.{1}".format(name, zone)

	# easy testing, use like this (requires environment variables)
	#	python cluster.py get_master cluster 2c922342a.cluster
	monitor = Monitor(key, access, cluster)
	print getattr(monitor, sys.argv[1])(*sys.argv[3:])
