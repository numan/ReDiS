#!/bin/bash

rm /var/run/redis/info
sudo -u redis sh -c "/usr/local/bin/redis-cli info > /var/run/redis/info"
