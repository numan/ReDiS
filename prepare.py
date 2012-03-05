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

import os, sys, re
import json, urllib2

from boto.ec2.connection import EC2Connection
from boto.ec2.regioninfo import RegionInfo

import backup, administration
from events import Events
from host import Host

try:
	url = "http://169.254.169.254/latest/"

	userdata = json.load(urllib2.urlopen(url + "user-data"))
	instance_id = urllib2.urlopen(url + "meta-data/instance-id").read()
	hostname = urllib2.urlopen(url + "meta-data/public-hostname/").read()

	zone = urllib2.urlopen(url + "meta-data/placement/availability-zone").read()
	region = zone[:-1]
except Exception as e:
	print e
	exit( "We couldn't get user-data or other meta-data...")

device = "/dev/sdf"
device_mounted_name = "/dev/xvdf"
mount = "/var/lib/redis"

# what is the domain to work with
redis_name = os.environ['REDIS_NAME'].strip()
hosted_zone = os.environ['HOSTED_ZONE_NAME'].rstrip('.')

# the name (and identity) of the cluster (the master)
cluster = "{0}.{1}".format(redis_name, hosted_zone)

events = Events(sys.argv[1], sys.argv[2], cluster)
node = Host(cluster, events).get_node()
component = os.path.basename(sys.argv[0])
def log(message, logging='warning'):
	events.log(node, component, message, logging)

# we are going to work with local files, we need our path
path = os.path.dirname(os.path.abspath(__file__))

def provision(key, access, cluster, size, persistence="no", snapshot=None, rdb=None):
	log('start provisioning', 'info')
	# ec2 is region specific
	region_info = RegionInfo(name=region,
							endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)

	def add_monitor(device="/dev/sdf", name="main"):
		f = open( "{0}/etc/monit/{1}".format(path, name), "w")
		f.write("  check filesystem {0} with path {1}".format(name, device))
		f.write("   if failed permission 660 then alert")
		f.write("   if failed uid root then alert")
		f.write("   if failed gid disk then alert")
		f.write("   if space usage > 80% for 5 times within 15 cycles then alert")
		f.close()

	def create_device(snapshot=None):
		log('getting a device', 'info')
		# if we have the device (/dev/sdf) just don't do anything anymore
		mapping = ec2.get_instance_attribute(instance_id, 'blockDeviceMapping')
		try:
			volume_id = mapping['blockDeviceMapping'][device].volume_id
			log('using existing volume', 'info')
		except:
			log('creating a new volume', 'info')
			volume = ec2.create_volume(size, zone, snapshot)
			volume.attach(instance_id, device)
			volume_id = volume.id
			log('created ' + volume_id, 'info')

			# we can't continue without a properly attached device
			log('waiting for ' + device, 'info')
			os.system("while [ ! -b {0} ] ; do /bin/true ; done".format(device_mounted_name))

			# make sure the volume is deleted upon termination
			# should also protect from disaster like loosing an instance
			# (it doesn't work with boto, so we do it 'outside')
			log('set delete-on-termination', 'info')
			os.system("/usr/bin/ec2-modify-instance-attribute --block-device-mapping \"{0}=:true\" {1} --region {2}".format(device, instance_id, region))

			# if we start from snapshot we are almost done
			if snapshot == "" or None == snapshot:
				log('creating a filesystem', 'info')
				# first create filesystem
				os.system("/sbin/mkfs.xfs {0}".format(device_mounted_name))

			log('mounting the filesystem', 'info')
			# mount, but first wait until the device is ready
			os.system("/bin/mount -t xfs -o defaults {0} {1}".format(device_mounted_name, mount))
			# and grow (if necessary)
			log('growing the filesystem', 'info')
			os.system("/usr/sbin/xfs_growfs {0}".format(mount))

			add_monitor(device_mouted_name, 'data')

		log('volume {0} is attached to {1} and mounted ({2}) and ready for use'.format(volume_id, device, mount), 'info')
		return volume_id

	def prepare():
		log('prepare the environment', 'info')
		# from this point we are sure we don't have to be careful
		# with local files/devices/disks/etc

		dst = "/etc/redis/redis.conf"
		redis = "{0}/etc/redis/{1}.conf".format(path, persistence)
		cron = "{0}/cron.d/{1}.cron".format(path, persistence)

		# redis will start with this conf
		log('configuring redis', 'info')
		os.system("/bin/cp -f {0} {1}".format(redis, dst))
		# and root's cron will be set accordingly as well
		log('setting up cron', 'info')
		os.system("/bin/sed 's:INSTALLPATH:{0}:' {1} | /usr/bin/crontab".format(path, cron))

		# ok, ready to set up assets like bucket and volume
		# also, if we have a valid mount, we don't do anything
		log('set up persistence', 'info')
		if os.path.ismount(mount) == False and "no" != persistence:
			log('create bucket {0}'.format(cluster), 'info')
			backup.create_bucket(key, access, cluster)

			try:
				# only try to create one if we have one
				if "" == snapshot or None == snapshot:
					raise Exception('metadata','empty snapshot')
				else:
					create_device(snapshot)
			except:
				try:
					latest = administration.get_latest_snapshot(key,
															access, cluster)
					create_device(latest)
				except:
					create_device()

			# we have a bucket, and perhaps a device. lets try to restore
			# from rdb, first from metadata later from user_data.
			if rdb != None and "" != rdb:
				log('restore rdb {0}/{1}'.format(cluster, rdb), 'info')
				backup.restore(key, access, cluster, rdb)

			latest = administration.get_latest_RDB(key, access, cluster)
			if "" != latest:
				log('restore rdb {0}/{1}'.format(cluster, latest), 'info')
				backup.restore(key, access, cluster, latest)

	prepare()

def meminfo():
	"""
	dict of data from meminfo (str:int).
	Values are in kilobytes.
	"""
	re_parser = re.compile(r'^(?P<key>\S*):\s*(?P<value>\d*)\s*kB')
	result = dict()
	for line in open('/proc/meminfo'):
		match = re_parser.match(line)
		if not match:
			continue # skip lines that don't parse
		key, value = match.groups(['key', 'value'])
		result[key] = int(value)
	return result

if __name__ == '__main__':
	import os, sys

	try:
		persistence = userdata['persistence']
	except:
		persistence = None
	try:
		snapshot = userdata['snapshot']
	except:
		snapshot = None
	try:
		rdb = userdata['rdb']
	except:
		rdb = None

	size = 3 * ( meminfo()['MemTotal'] / ( 1024 * 1024 ) )

	provision(sys.argv[1], sys.argv[2], cluster, size,
				persistence=persistence, snapshot=snapshot, rdb=rdb)
