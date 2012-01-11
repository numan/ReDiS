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

try:
	url = "http://169.254.169.254/latest/"

	user_data = json.load(urllib2.urlopen(url + "user-data"))
	fqdn =  urllib2.urlopen(url + "meta-data/public-hostname").read()
	instance_id = urllib2.urlopen(url + "meta-data/instance-id").read()

	availability_zone = urllib2.urlopen(url + "meta-data/placement/availability-zone").read()
	region = availability_zone[:-1]
except Exception as e:
	print e
	exit( "We couldn't get user-data or other meta-data...")

device = "/dev/sdf"
mount = "/var/lib/redis"

def provision(key, access, cluster, persistence=None):
	metadata = administration.get_cluster_metadata(key, access, cluster)

	# ec2 is region specific
	region_info = RegionInfo(name=region,
							endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)

	def create_device(snapshot=None):
		# if we have the device (/dev/sdf) just don't do anything anymore
		mapping = ec2.get_instance_attribute(instance_id, 'blockDeviceMapping')
		try:
			volume_id = mapping['blockDeviceMapping'][device].volume_id
		except:
			volume = ec2.create_volume(
					metadata['size'], availability_zone, snapshot)
			volume.attach(instance_id,device)
			volume_id = volume.id

			# make sure the volume is deleted upon termination
			# should also protect from disaster like loosing an instance
			# (it doesn't work with boto, so we do it 'outside')
			os.system("/usr/bin/ec2-modify-instance-attribute --block-device-mapping \"{0}=:true\" {1} --region {2}".format(device, instance_id, region))

			# if we start from snapshot we are almost done
			if snapshot == "" or None == snapshot:
				# first create filesystem
				os.system("/sbin/mkfs.xfs {0}".format(device))

			# mount
			os.system("/bin/mount -t xfs -o defaults {0} {1}".format(device, mount))
			# and grow (if necessary)
			os.system("/usr/sbin/xfs_growfs {0}".format(mount))

		return volume_id

	def prepare(persistence):
		# from this point we are sure we don't have to be careful
		# with local files/devices/disks/etc

		# we are going to work with local files, we need our path
		path = os.path.dirname(os.path.abspath(__file__))

		dst = "/etc/redis/redis.conf"
		redis = "{0}/etc/redis/{1}.conf".format(path, persistence)
		cron = "{0}/cron.d/{1}.cron".format(path, persistence)

		# redis will start with this conf
		os.system("/bin/ln -fs {0} {1}".format(redis, dst))
		# and root's cron will be set accordingly as well
		os.system("/usr/bin/crontab {0}".format(cron))

		# ok, ready to set up assets like bucket and volume
		if "no" != persistence:
			backup.create_bucket(key, access, cluster)

			try:
				# only try to create one if we have one
				if "" == metadata['snapshot']:
					raise Exception('metadata','empty snapshot')
				else:
					create_device(metadata['snapshot'])
			except:
				try:
					latest = administration.get_latest_snapshot(key,
															access, cluster)
					create_device(latest)
				except:
					create_device()

			# we have a bucket, and perhaps a device. lets try to restore
			# from rdb, first from metadata later from user_data.
			if "" != metadata['rdb']:
				backup.restore(key, access, cluster, metadata['rdb'])

			latest = administration.get_latest_RDB(key, access, cluster)
			if "" != latest:
				backup.restore(key, access, cluster, latest)

	# get local persistence first (if not overwritten)
	if None == persistence:
		try:
			persistence = metadata['persistence']
		except:
			persistence = 'no'

	if os.path.ismount(mount) == False:
		prepare(persistence)

def withdrawal(key, access, cluster, persistence=None):
	metadata = administration.get_cluster_metadata(key, access, cluster)

	# get local persistence first (if not overwritten)
	if None == persistence:
		try:
			persistence = metadata['persistence']
		except:
			persistence = 'no'

	# make a last backup
	if "no" != persistence:
		# take the latest RDB and move it to S3
		rdb = backup.put_RDB(key, access, cluster, 'monthly')
		administration.set_RDB(key, access, cluster, rdb)

		# if we have a volume, make a last snapshot
		if "low" != persistence:
			snapshot = backup.make_snapshot(key, access, cluster, 'monthly')
			administration.add_snapshot(key, access, cluster, snapshot)

	# we don't have to get rid any the volume, it is deleted on termination

	# change to the default (no persistence)
	os.system("/bin/rm -f /etc/redis/redis.conf")
	# and empty the cron as well
	os.system("/bin/echo | /usr/bin/crontab")

if __name__ == '__main__':
	import sys
	try:
		provision(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
	except IndexError:
		provision(sys.argv[1], sys.argv[2], sys.argv[3])
