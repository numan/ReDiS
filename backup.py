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

#
# backup.py is a backup module for RDB (redis dumps) on S3, and EBS
# snapshots of the volume behind /dev/sdf.
#
# The S3 objects will have one of the following prefixes
#	 hourly/
#	 daily/
#	 weekly/
#	 monthly/
# using S3 object expiration (lifecycle management) you can create a
# sophisticated backup solution.
#
# The EBS snapshots are tagged with the expiration, and at the same time
# administerd in SimpleDB.
#
# Usage:
#	 backup.py <cmd> EC2_KEY_ID EC2_SECRET_KEY <expiration>
#
# <cmd>: rdb, snapshot or purge
# <expiration>: hourly (default), daily, weekly, monthly
#

import os, sys
import json, urllib2

from time import gmtime,strftime,time

from boto.s3.connection import S3Connection
from boto.s3.connection import Location
from boto.ec2.connection import EC2Connection
from boto.ec2.regioninfo import RegionInfo
from boto.exception import S3CreateError
from boto.s3.key import Key

import administration

try:
	url = "http://169.254.169.254/latest/meta-data/"

	instance_id = urllib2.urlopen(url + "instance-id").read()
	zone = urllib2.urlopen(url + "placement/availability-zone").read()

	region = zone[:-1]
except Exception as e:
	print e
	exit( "We couldn't get user-data or other meta-data...")

# expiration in the future, calculated like this
days = 24 * 60 * 60
form = "%Y-%m-%d %H:%M:%S"
expires = {'hourly': strftime(form, gmtime(time() + 2 * days)),
		   'daily': strftime(form, gmtime(time() + 14 * days)),
		   'weekly': strftime(form, gmtime(time() + 61 * days)),
		   'monthly': strftime(form, gmtime(time() + 365 * days))}

src = "/var/lib/redis/dump.rdb"

def create_bucket(key, access, cluster):
	s3 = S3Connection(key, access)

	# our create_bucket is not idempotent, we can't recreate buckets
	try:
		s3.create_bucket( cluster.replace('.', '-'), location=Location.EU)
	except S3CreateError:
		pass

def put_RDB(key, access, cluster, prefix='hourly'):
	s3 = S3Connection(key, access)
	bucket = s3.get_bucket( cluster.replace('.', '-'))

	# first cp/gzip RDB to temporary location
	now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
	filename = "{1}.rdb.gz".format(prefix, now)
	os.system("/bin/gzip -c {0} > '/tmp/{1}'".format(src, filename))

	# copy the file to the bucket (with a prefix)
	dump = Key(bucket)
	dump.key = "{0}/{1}".format(prefix, filename)
	dump.set_contents_from_filename( "/tmp/{0}".format( filename))

	# we are done, remove it
	os.system("/bin/rm '/tmp/{0}'".format(filename))

	return dump.key

def make_snapshot(key, access, cluster, expiration='hourly'):
	device = "/dev/sdf"
	mount = "/var/lib/redis"

	region_info = RegionInfo(name=region,
						endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)
	
	# if we have the device (/dev/sdf) just don't do anything anymore
	mapping = ec2.get_instance_attribute(instance_id, 'blockDeviceMapping')
	try:
		volume_id = mapping['blockDeviceMapping'][device].volume_id

		os.system("/usr/sbin/xfs_freeze -f {0}".format(mount))
		snapshot = ec2.create_snapshot(volume_id,
					"Backup of {0} - expires {1}".format(volume_id,
														expires[expiration]))
		os.system("/usr/sbin/xfs_freeze -u {0}".format(mount))
	except:
		pass

	return ["{0}".format(snapshot.id), expires[expiration]]

def purge_snapshots(key, access, cluster, snapshots):
	region_info = RegionInfo(name=region,
							endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)

	for snapshot in snapshots:
		if ec2.delete_snapshot(snapshot['snapshot']):
			administration.delete_snapshot(key,
											access,
											cluster,
											snapshot['snapshot'])

def restore(key, access, cluster, rdb):
	s3 = S3Connection(key, access)
	bucket = s3.get_bucket( cluster.replace('.', '-'))

	dump = Key(bucket, rdb)
	dump.get_contents_to_filename("{0}.gz".format(src))
	
	os.system("/bin/gzip -df {0}.gz".format(src))
	#print os.system("/bin/cat {0}".format(src))

# for convenience we can call this file to make backups directly
if __name__ == '__main__':
	s3 = S3Connection(sys.argv[2],sys.argv[3])

	# get the bucket, from the cluster name
	name = os.environ['REDIS_NAME'].strip()
	hosted_zone = os.environ['HOSTED_ZONE_NAME'].rstrip('.')
	cluster = "{0}.{1}".format(name, hosted_zone)
	bucket = s3.get_bucket( cluster.replace('.', '-'))

	if "rdb" == sys.argv[1]:
		create_bucket(sys.argv[2], sys.argv[3], cluster)
		key = put_RDB(sys.argv[2], sys.argv[3], cluster, sys.argv[4])
		administration.set_RDB(sys.argv[2], sys.argv[3], cluster, key)
	elif "snapshot" == sys.argv[1]:
		backup = make_snapshot(sys.argv[2], sys.argv[3], cluster, sys.argv[4])
		administration.add_snapshot(sys.argv[2], sys.argv[3],
											cluster, backup)
	elif "purge" == sys.argv[1]:
		snapshots = administration.get_expired_snapshots(sys.argv[2],
											sys.argv[3], cluster)
		purge_snapshots(sys.argv[2], sys.argv[3], cluster, snapshots)
