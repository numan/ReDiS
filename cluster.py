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
import json
import hashlib

from urllib2 import urlopen
from time import gmtime,strftime

from boto.sdb.connection import SDBConnection
from boto.sdb.regioninfo import RegionInfo

#
# REDIS CLUSTER
#
# our cluster has one topology, at this moment. we'll implement the cluster
# as a chain. the advantage of this is that the nodes are relatively
# independent. if a node is lost, it will be picked up by the slave, which
# moves itself up a place in the chain. another advantage is that the slaves
# might have lag, but the lag is always relative. moving up is no problem,
# adding slaves is done at the tail.
#
# the cluster's structure is managed in SimpleDB, and made accessible using
# Route43. the head of the chain is the mydomain.com, the tail is
# accessible through tail.mydomain.com. every individual node has a unique
# fqdn like 4821541d.mydomain.com.
#
class Cluster:
	def __init__(self, key, access, cluster):
		try:
			url = "http://169.254.169.254/latest/meta-data/"

			public_hostname = urlopen(url + "public-hostname").read()
			zone = urlopen(url + "placement/availability-zone").read()
			region = zone[:-1]
		except:
			sys.exit("We should be getting user-data here...")

		endpoint = "sdb.{0}.amazonaws.com".format(region)
		region_info = RegionInfo(name=region, endpoint=endpoint)

		sdb = SDBConnection(key, access, region=region_info)

		self.domain = sdb.create_domain(cluster)

		self.metadata = self.domain.get_item('metadata', consistent_read=True)
		if None == self.metadata:
			self.metadata = self.domain.new_item('metadata')

			self.metadata.add_value('master', '')
			self.metadata.add_value('slave', '')
			self.metadata.save()
	
	def name(self):
		return self.domain.name

	def add_node(self, node, endpoint):
		try:
			head = self.metadata['master']
		except:
			head = ""

		try:
			tail = self.metadata['slave']
		except:
			tail = ""

		# create a new node, always added to the tail
		new = self.domain.new_item(node)
		new.add_value('endpoint', endpoint)

		try:
			if head == tail == "":
				# we are empty; a cluster of one
				self.metadata['master'] = self.metadata['slave'] = node
			else:
				# now, we extend, by adding a new tail
				self.metadata['slave'] = node

				self.domain.put_attributes(node, {'master': head})
				self.domain.put_attributes(tail, {'slave': node})

				new.add_value('master', tail)

			self.metadata.save()
			new.save()
			return True
		except:
			# head or tail (perhaps both) are None?
			pass

		return False

	def delete_node(self, node):
		head = self.metadata['master']
		tail = self.metadata['slave']

		item = self.domain.get_item(node, True)

		if None != item:
			# we have to be careful, node might be head or tail
			if node == head == tail:
				self.metadata['master'] = None
				self.metadata['slave'] = None
			elif node == tail:
				master = self.get_master(node)
				self.metadata['slave'] = master
				self.domain.delete_attributes(master, ['slave'])
			elif node == head:
				slave = self.get_slave(node)
				self.metadata['master'] = slave
				self.domain.delete_attributes(slave, ['master'])
			else:
				master = self.get_master(node)
				slave = self.get_slave(node)

				self.domain.put_attributes(master, {'slave': slave})
				self.domain.put_attributes(slave, {'master': master})

			item.delete()
			self.metadata.save()
			return True
		else:
			return False

	# blaming can be done in case of loss of connection. if a slave
	# looses connection, it can blame its master, and start searching for
	# a new master (or become THE master).
	def incarcerate_node(self, node):
		head = self.metadata['master']
		tail = self.metadata['slave']

		item = self.domain.get_item(node, True)

		if None != item:
			# we have to be careful, node might be head or tail
			if node == head == tail:
				self.metadata['master'] = None
				self.metadata['slave'] = None
			elif node == tail:
				master = self.get_master(node)
				self.metadata['slave'] = master
				self.domain.delete_attributes(master, ['slave'])
			elif node == head:
				slave = self.get_slave(node)
				self.metadata['master'] = slave
				self.domain.delete_attributes(slave, ['master'])
			else:
				master = self.get_master(node)
				slave = self.get_slave(node)

				self.domain.put_attributes(master, {'slave': slave})
				self.domain.put_attributes(slave, {'master': master})

			self.domain.delete_attributes(node, ['master'])
			self.domain.delete_attributes(node, ['slave'])
			self.metadata.save()

			return True
		else:
			return False

	def exists(self, node):
		return (self.domain.get_item(node, True) != None)

	def get_endpoint(self, node):
		try:
			return self.domain.get_item(node, True)['endpoint']
		except:
			return None

	def get_master(self, node=None):
		if node == None or node == "":
			return self.metadata['master']

		try:
			return self.domain.get_item(node, True)['master']
		except:
			return None

	def get_slave(self, node=None):
		if node == None or node == "":
			return self.metadata['slave']

		try:
			return self.domain.get_item(node, True)['slave']
		except:
			return None
	
	def size(self):
		select = "select count(*) from `{0}` where itemName() like '%.{0}'".format(self.domain.name)
		return int(self.domain.select(select, consistent_read=True).next()['Count'])

	def check_integrity(self, cluster):
		pass
	
if __name__ == '__main__':
	key = os.environ['EC2_KEY_ID']
	access = os.environ['EC2_SECRET_KEY']

	# easy testing, use like this (requires environment variables)
	#	python cluster.py get_master cluster 2c922342a.cluster
	cluster = Cluster(key, access, sys.argv[2])
	print getattr(cluster, sys.argv[1])(*sys.argv[3:])
