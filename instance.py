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
import platform
import sys

from boto.route53.connection import Route53Connection
from boto.route53.record import ResourceRecordSets
from boto.ec2.connection import EC2Connection
from boto.ec2.regioninfo import RegionInfo

# your amazon keys
key = os.environ['R53_KEY_ID']
access = os.environ['R53_SECRET_KEY']

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

if( len(sys.argv) > 1):
	NAME = sys.argv[1]
else:
	print "usage: 'python launch.py <name>'"
	sys.exit()

EC2_INSTANCE_ID = os.environ['EC2_INSTANCE_ID']
HOSTED_ZONE_NAME = os.environ['HOSTED_ZONE_NAME']
HOSTED_ZONE_ID = os.environ['HOSTED_ZONE_ID']

if __name__ == '__main__':
	zones = {}
	value = ''
	route53 = Route53Connection(key, access)

	# ec2 is region specific
	region_info = RegionInfo(name=region,endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)
	
	# get hosted zone for HOSTED_ZONE_NAME
	results = route53.get_hosted_zone(HOSTED_ZONE_ID)
	zone = results['GetHostedZoneResponse']['HostedZone']
	zone_id = zone['Id'].replace('/hostedzone/', '')
	zones[zone['Name']] = zone_id

	# first get the old value
	name = "{0}.{1}".format(NAME, HOSTED_ZONE_NAME)
	sets = route53.get_all_rrsets(zones[HOSTED_ZONE_NAME], None)
	for rset in sets:
		if rset.name == name:
			value = rset.resource_records[0]

	# only change when necessary
	if value != fqdn:
		# first delete old record
		changes = ResourceRecordSets(route53, zone_id)

		if value != '':
			change = changes.add_change("DELETE", name, "CNAME", 60)
			change.add_value(value)

		# now, add ourselves as zuckerberg
		change = changes.add_change("CREATE", name, "CNAME", 60)
		change.add_value(fqdn)

		changes.commit()

		# and change the tag Name of the instance (and remove the dot)
		ec2.create_tags( [EC2_INSTANCE_ID], { "Name": name.rstrip('.') })
