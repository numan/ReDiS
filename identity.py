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
import platform
import json, urllib2

from boto.route53.connection import Route53Connection
from boto.route53.record import ResourceRecordSets
from boto.ec2.connection import EC2Connection
from boto.ec2.regioninfo import RegionInfo

import administration

try:
	url = "http://169.254.169.254/latest/"

	user_data = urllib2.urlopen(url + "user-data").read()
	fqdn =  urllib2.urlopen(url + "meta-data/public-hostname").read()
	instance_id = urllib2.urlopen(url + "meta-data/instance-id").read()

	availability_zone = urllib2.urlopen(url + "meta-data/placement/availability-zone").read()
	region = availability_zone[:-1]
except Exception as e:
	print e
	exit( "We couldn't get user-data or other meta-data...")

name = os.environ['REDIS_NAME'].strip()
hosted_zone_name = os.environ['HOSTED_ZONE_NAME']
hosted_zone_id = os.environ['HOSTED_ZONE_ID']

def set_endpoint(key, access, cluster):
	zones = {}
	value = ''
	route53 = Route53Connection(key, access)

	# ec2 is region specific
	region_info = RegionInfo(name=region,
						endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)
	
	# get hosted zone for HOSTED_ZONE_NAME
	results = route53.get_hosted_zone(hosted_zone_id)
	zone = results['GetHostedZoneResponse']['HostedZone']
	zone_id = zone['Id'].replace('/hostedzone/', '')
	zones[zone['Name']] = zone_id

	changes = ResourceRecordSets(route53, zone_id)

	# always add a unique FQDN 'inside' the redis cluster
	identity = administration.get_identity(key, access, cluster) + "."
	change = changes.add_change("CREATE", identity, "CNAME", 60)
	change.add_value(fqdn)

	# if there is master (no master record in Route53), we are the master
	metadata = administration.get_cluster_metadata(key, access, cluster)
	name = metadata['master'] + "."
	sets = route53.get_all_rrsets(zones[hosted_zone_name], None)
	for rset in sets:
		if rset.name == name:
			value = rset.resource_records[0]

	if "" == value:
		# ok, add ourselves as master (head)
		change = changes.add_change("CREATE", name, "CNAME", 60)
		change.add_value(fqdn)
	except:
		print "Couldn't add Route53 record or set the instance Name tag for " + name + ". It probably already exists."

	changes.commit()

	# and change the tag Name of the instance (and remove the dot)
	ec2.create_tags( [instance_id], { "Name": name.rstrip('.') })

def unset_endpoint(key, access, cluster):
	zones = {}
	value = ''
	route53 = Route53Connection(key, access)

	# ec2 is region specific
	region_info = RegionInfo(name=region,endpoint="ec2.{0}.amazonaws.com".format(region))
	ec2 = EC2Connection(key, access, region=region_info)
	
	# get hosted zone for HOSTED_ZONE_NAME
	results = route53.get_hosted_zone(hosted_zone_id)
	zone = results['GetHostedZoneResponse']['HostedZone']
	zone_id = zone['Id'].replace('/hostedzone/', '')
	zones[zone['Name']] = zone_id

	# first get the old value
	metadata = administration.get_cluster_metadata(key, access, cluster)
	name = metadata['master'] + "."
	sets = route53.get_all_rrsets(zones[hosted_zone_name], None)
	for rset in sets:
		if rset.name == name:
			value = rset.resource_records[0]

	# delete old record
	changes = ResourceRecordSets(route53, zone_id)

	if value != '':
		change = changes.add_change("DELETE", name, "CNAME", 60)
		change.add_value(value)

		changes.commit()

	# and reset the tag Name of the instance
	ec2.delete_tags( [instance_id], ["Name"])

if __name__ == '__main__':
	import sys
	set_endpoint(sys.argv[1],sys.argv[2])
