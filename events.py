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
from time import gmtime,strftime,time

from boto.sdb.connection import SDBConnection
from boto.sdb.regioninfo import RegionInfo

#
# REDIS LOGGING
#
class Events:
	def __init__(self, key, access, cluster):
		try:
			url = "http://169.254.169.254/latest/meta-data/"
			userdata_url = "http://169.254.169.254/latest/user-data/"

			userdata = json.load(urlopen(userdata_url))
			public_hostname = urlopen(url + "public-hostname").read()
			zone = urlopen(url + "placement/availability-zone").read()
			region = zone[:-1]
		except:
			sys.exit("We should be getting user-data here...")

		endpoint = "sdb.{0}.amazonaws.com".format(region)
		region_info = RegionInfo(name=region, endpoint=endpoint)

		sdb = SDBConnection(key, access, region=region_info)

		try:
			self.logging = userdata['logging']
		except:
			self.logging = 'warning'

		self.events = "events.{0}".format(cluster)

		self.domain = sdb.lookup(self.events, True)
		if self.domain == None:
			sdb.create_domain(self.events)
			self.domain = sdb.lookup(self.events, True)

			auto_increment = self.domain.new_item('auto-increment')
			auto_increment.add_value('value',0)
			auto_increment.save()

	def log(self, node, component, message, logging=None):
		if None == logging:
			logging = self.logging

		if self.logging != 'error':
			if not (logging == 'info' and self.logging == 'warning'):
				increment = self.increment()

				now = strftime("%Y-%m-%d %H:%M:%S", gmtime())
				new = self.domain.new_item(increment)
				new.add_value('logging', logging)
				new.add_value('component', component)
				new.add_value('message', message)
				new.add_value('node', node)
				new.add_value('created', now)
				new.save()

				return increment

	def increment(self):
		incremented = False
		while not incremented:
			value = int(self.domain.get_item('auto-increment', True)['value'])
			try:
				self.domain.put_attributes('auto-increment',
										{'value' : value + 1},
										expected_value=['value', value])

				value = value + 1
				incremented = True
			except:
				pass

		return value

	def purge(self, days=7):
		# by default purge everything older than a week
		seconds = 24 * 60 * 60
		form = "%Y-%m-%d %H:%M:%S"

		timestamp = strftime(form, gmtime(time() - int(days) * seconds))

		select = "select * from `{0}` where itemName() != 'auto-increment' and created < '{1}'"
		events = self.domain.select(select.format(self.domain.name, timestamp))
		for event in events:
			self.domain.delete_item(event)

		return True

	def tail(self, limit=10):
		now = strftime("%Y-%m-%d %H:%M:%S", gmtime(time()))

		select = "select * from `{0}` where itemName() != 'auto-increment' and created < '{1}' order by created desc limit {2}"
		events = self.domain.select(select.format(self.domain.name, now, limit))
		msg = ""

		for event in events:
			msg = "[{0}] (3): {1}, {2} ({4})\n{5}".format(event['created'],
														event['component'],
														event['message'],
														event['logging'],
														event['node'], msg)
			limit = int(limit) - 1
			if limit <= 0:
				break

		return msg.rstrip("\n")

	def reset(self):
		# first delete all existing items
		select = "select * from `{0}` where itemName() != 'auto-increment'"
		events = self.domain.select(select.format(self.domain.name))
		for event in events:
			self.domain.delete_item(event)

		return self.domain.put_attributes('auto-increment', {'value' : 0})

if __name__ == '__main__':
	key = os.environ['EC2_KEY_ID']
	access = os.environ['EC2_SECRET_KEY']

	# easy testing, use like this (requires environment variables)
	#	python events.py log cluster component message
	events = Events(key, access, sys.argv[2])
	print getattr(events, sys.argv[1])(*sys.argv[3:])
