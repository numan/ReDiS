#!/bin/bash 
 
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

# get, and sanitize for our bruteforce json parsing below
userdata=`curl --silent http://169.254.169.254/latest/user-data | python -mjson.tool`

grep="grep"
regex='s/.*\:[ \t]*"\{0,1\}\([^,"]*\)"\{0,1\},\{0,1\}/\1/'
sed="sed '${regex}'"

if [ "${userdata}" != "" ]; then
	# basic settings
	export REDIS_NAME=`eval "echo '${userdata}' | ${grep} '\"name\"' | ${sed}"`
	# calculate size dynamically (3x the memory)
	export REDIS_SIZE=`grep MemTotal /proc/meminfo | awk '{printf "%.f", ( \$2 * 3 / (1024*1024)) }'`
	export REDIS_PERSISTENCE=`eval "echo '${userdata}' | ${grep} '\"persistence\"' | ${sed}"`
	export REDIS_SNAPSHOT=`eval "echo '${userdata}' | ${grep} '\"snapshot\"' | ${sed}"`
	export REDIS_RDB=`eval "echo '${userdata}' | ${grep} '\"RDB\"' | ${sed}"`
fi

# AWS settings
export AWS_ACCOUNT_ID=""

# EC2 settings (needs some EBS and Route53 priviliges)
export EC2_KEY_ID=""
export EC2_SECRET_KEY=""

export R53_KEY_ID=${EC2_KEY_ID}
export R53_SECRET_KEY=${EC2_SECRET_KEY}
export HOSTED_ZONE_NAME="."
export HOSTED_ZONE_ID=""

# SQS settings
export SQS_KEY_ID=${EC2_KEY_ID}
export SQS_ACCESS_KEY=${EC2_SECRET_KEY}

# some of these things are present on the instance
export EC2_KEY_DIR=/root/.ec2
export AWS_CREDENTIAL_FILE=${EC2_KEY_DIR}/aws_credentials.txt
export EC2_PRIVATE_KEY=${EC2_KEY_DIR}/pk-.pem
export EC2_CERT=${EC2_KEY_DIR}/cert-.pem
export EC2_ACCESS_KEY=${EC2_KEY_ID}
export AWS_ACCESS_KEY_ID=${EC2_KEY_ID}
export EC2_SECRET_KEY=${EC2_SECRET_KEY}
export AWS_SECRET_ACCESS_KEY=${EC2_SECRET_KEY}
export EC2_USER_ID=${AWS_ACCOUNT_ID}

curl="curl --retry 3 --silent --show-error --fail"
instance_data_url=http://169.254.169.254/latest

export EC2_AVAILABILITY_ZONE=$($curl $instance_data_url/meta-data/placement/availability-zone)
export EC2_REGION=${EC2_AVAILABILITY_ZONE:0:${#EC2_AVAILABILITY_ZONE}-1}
export EC2_INSTANCE_ID=$($curl $instance_data_url/meta-data/instance-id)

# this will only work with a patched simpledb (see SIMPLEDB)
export SDB_SERVICE_URL="https://sdb.${EC2_REGION}.amazonaws.com"

# changing this is entirely your own responsibility, I wouldn't do it
export SQS_TASK_QUEUE="${REDIS_NAME}-tasks"
export FQDN=$($curl $instance_data_url/meta-data/public-hostname)
