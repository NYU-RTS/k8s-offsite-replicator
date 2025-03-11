#!/bin/sh

set -eu

KUBECONFIG=/root/.kube/config

# First, mark the copy as snapshotting
mv /netbox/replicated/ready /netbox/replicated/snapshotting || test -e /netbox/replicated/snapshotting

# Then, compare the last copy date
OLD_SNAP="$(cat /kube/netbox/snapshotting)"
NEW_SNAP="$(cat /netbox/replicated/snapshotting)"
if [ "$OLD_SNAP" = "$NEW_SNAP" ]; then
    echo "No change" >&2
    mv /netbox/replicated/snapshotting /netbox/replicated/ready
    exit 0
fi
echo "Proceeding with snapshot, replacing $OLD_SNAP with $NEW_SNAP..."

# Then stop NetBox
kubectl -n hsrn-netbox scale deploy/hsrn-netbox deploy/hsrn-netbox-worker sts/hsrn-netbox-postgresql sts/hsrn-netbox-redis-master --replicas=0
kubectl -n hsrn-netbox wait --for=delete --timeout=120s pod --all

# Remove the previous snapshot
umount /kube/netbox
lvremove -y data/localcopy

# Make the new snapshot
lvcreate -n localcopy --snapshot data/replicated
lvchange -ay -k n data/localcopy
mount -o discard /dev/data/localcopy /kube/netbox

# Mark the copy as ready
mv /netbox/replicated/snapshotting /netbox/replicated/ready

# Restart the cluster
kubectl -n hsrn-netbox scale deploy/hsrn-netbox deploy/hsrn-netbox-worker sts/hsrn-netbox-postgresql sts/hsrn-netbox-redis-master --replicas=1
