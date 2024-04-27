#!/bin/bash

mkdir -p /data/ssh
mkdir -p ~/.ssh
mkdir -p /run/sshd
chown root:ssh /run/sshd
chmod 700 /run/sshd
if [ -f /data/ssh/id_rsa ]; then
  echo "SSH key already exists at /data/ssh/id_rsa"
else
  # Generate a new key if it doesn't exist
  ssh-keygen -t rsa -b 4096 -f /data/ssh/id_rsa -N ""
fi
cp -a /data/ssh/id_rsa.pub ~/.ssh/authorized_keys

exec /usr/sbin/sshd -D