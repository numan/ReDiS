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
from boto.ec2.volume import Volume
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

def test(key, access):
	# ec2 is region specific
	region_info = RegionInfo(name=region,
							endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)

	#ec2.modify_instance_attribute(instance_id,
	#								"blockDeviceMapping",
	#								"{0}=:true".format(device))

	mapping = ec2.get_instance_attribute(instance_id, 'blockDeviceMapping')
	return mapping['blockDeviceMapping']['/dev/sdf'].volume_id

if __name__ == '__main__':
	import sys
	print test(sys.argv[1], sys.argv[2])
