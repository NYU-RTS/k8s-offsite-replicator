#!/bin/sh

set -eu

# First, mark the copy as snapshotting
mv /netbox/replicated/ready /netbox/replicated/snapshotting || test -e /netbox/replicated/snapshotting

# Then stop the cluster
sudo -u ubuntu -g docker -H minikube stop

# Remove the previous snapshot
umount /kube/netbox
lvremove -y data/localcopy

# Make the new snapshot
lvcreate -n localcopy --snapshot data/replicated
lvchange -ay -k n data/localcopy
mount -o discard /dev/data/localcopy /kube/netbox

# Restart the cluster
sudo -u ubuntu -g docker -H minikube start --kubernetes-version=1.30.10 --driver=docker --nodes=1 --memory=no-limit --mount-string=/kube:/kube --mount --ports=0.0.0.0:80:32080 --ports=0.0.0.0:443:32043

# Finally, mark the copy as ready
mv /netbox/replicated/snapshotting /netbox/replicated/ready
