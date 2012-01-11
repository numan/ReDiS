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
import hashlib

from time import gmtime,strftime

from boto.sdb.connection import SDBConnection
from boto.sdb.regioninfo import RegionInfo

try:
	url = "http://169.254.169.254/latest/"

	public_hostname = urllib2.urlopen(url + "meta-data/public-hostname").read()
	availability_zone = urllib2.urlopen(url + "meta-data/placement/availability-zone").read()
	region = availability_zone[:-1]
except:
	exit("We should be getting user-data here...")

region_info = RegionInfo(name=region,endpoint="sdb.{0}.amazonaws.com".format(region))

def set_cluster_metadata(key, access, cluster):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	# set the basic values in the 'master' record
	metadata = domain.new_item('metadata')
	#master = "{0}.{1}".format(
	#						os.environ['REDIS_NAME'].strip(),
	#						os.environ['HOSTED_ZONE_NAME'].rstrip('.'))
	#metadata.add_value('master', master)

	try:
		if "" != os.environ['REDIS_SIZE'].strip():
			metadata.add_value('size', os.environ['REDIS_SIZE'])
	except:
		pass

	try:
		if "" != os.environ['REDIS_PERSISTENCE'].strip():
			metadata.add_value('persistence', os.environ['REDIS_PERSISTENCE'])
		else:
			metadata.add_value('persistence', 'no')
	except:
		metadata.add_value('persistence', 'no')

	try:
		if "" != os.environ['REDIS_SNAPSHOT'].strip():
			metadata.add_value('snapshot', os.environ['REDIS_SNAPSHOT'])
	except:
		pass

	try:
		if "" != os.environ['REDIS_RDB'].strip():
			metadata.add_value('rdb', os.environ['REDIS_RDB'])
	except:
		pass

	try:
		if "" != os.environ['REDIS_AOF'].strip():
			metadata.add_value('aof', os.environ['REDIS_AOF'])
	except:
		pass

	metadata.save()

def get_cluster_metadata(key, access, cluster):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	return domain.get_item('metadata', True)

def set_RDB(key, access, cluster, location):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	# add the latest rdb (for automatic restores)
	latest = domain.new_item('rdb')
	latest.add_value('rdb', location)
	# get the expiration date from the object name (for comparison)
	latest.add_value('created', strftime("%Y-%m-%d %H:%M:%S", gmtime()))
	latest.save()

def get_latest_RDB(key, access, cluster):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	return domain.get_item('rdb', True)['rdb']

def add_snapshot(key, access, cluster, snapshot):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	# add the latest rdb (for automatic restores)
	latest = domain.new_item('snapshot')
	latest.add_value('snapshot', snapshot[0])
	# get the expiration date from the object name (for comparison)
	latest.add_value('created', strftime("%Y-%m-%d %H:%M:%S", gmtime()))
	latest.save()

	# add the snapshot for expiration
	backup = domain.new_item(snapshot[0])
	backup.add_value('snapshot', snapshot[0])
	backup.add_value('expires', snapshot[1])
	backup.save()

	# add the latest (for automatic restores)
	latest = domain.new_item('snapshot')
	latest.add_value('snapshot', snapshot[0])
	latest.save()

def get_latest_snapshot(key, access, cluster):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	return domain.get_item('snapshot', True)['snapshot']

def delete_snapshot(key, access, cluster, snapshot_id):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	return domain.delete_item(domain.get_item(snapshot_id))

def get_expired_snapshots(key, access, cluster):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
	select = "select * from `{0}` where itemName() > 'snap-' and itemName() != 'snapshot' and expires < '{1}'".format(cluster, now)
	snapshots = domain.select(select)
	return snapshots

def get_identity(key, access, cluster):
	sdb = SDBConnection(key, access, region=region_info)

	domain = sdb.lookup(cluster, True)
	if domain == None:
		domain = sdb.create_domain(cluster)

	slave_id = hashlib.md5(public_hostname).hexdigest()[:8]
	slave_fqdn = "{0}.{1}".format(slave_id, cluster)

	slave = domain.new_item(slave_fqdn)
	slave.add_value('id', slave_id)
	slave.add_value('endpoint', public_hostname)
	slave.save()

	return slave_fqdn

if __name__ == '__main__':
	import sys
	#set_cluster_metadata(sys.argv[1],sys.argv[2])
	metadata = get_cluster_metadata(sys.argv[1],sys.argv[2])
	print metadata['master']
