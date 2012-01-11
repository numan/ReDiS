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

import identity, administration, setup

# your amazon keys
key = os.environ['EC2_KEY_ID']
access = os.environ['EC2_SECRET_KEY']

if __name__ == '__main__':
	# what is the domain to work with
	name = os.environ['REDIS_NAME'].strip()
	zone = os.environ['HOSTED_ZONE_NAME'].rstrip('.')
	cluster = "{0}.{1}".format(name, zone)

	# make sure we persist the cluster meta data
	administration.set_cluster_metadata(key, access, cluster)

	# now, set the endpoints in route53 and as Name tag
	identity.set_endpoint(key, access, cluster)

	# now provision the instance
	setup.provision(key, access, cluster)
