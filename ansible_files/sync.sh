#!/bin/sh

set -eu

k(){
    runuser -u minikube -- kubectl "$@"
}

# First, mark the sync target as snapshotting
mv {{ synctarget_mountpoint }}/ready {{ synctarget_mountpoint }}/snapshotting || test -e {{ synctarget_mountpoint }}/snapshotting

# Then, compare the last copy date
OLD_SNAP="$(cat /kube/localcopy/snapshotting)"
NEW_SNAP="$(cat {{ synctarget_mountpoint }}/snapshotting)"
if [ "$OLD_SNAP" = "$NEW_SNAP" ]; then
    echo "No change" >&2
    mv {{ synctarget_mountpoint }}/snapshotting {{ synctarget_mountpoint }}/ready
    exit 0
fi
echo "Proceeding with snapshot, replacing $OLD_SNAP with $NEW_SNAP..."

# Then scale everything to 0
{% for scale_target in scale_targets %}
k -n {{ scale_target.namespace }} scale {{ scale_target.target }} --replicas=0
{% endfor %}
{% for scale_target in scale_targets %}
k -n {{ scale_target.namespace }} wait --for=delete --timeout=120s pod --all
{% endfor %}

# Remove the previous snapshot
umount /kube/localcopy
lvremove -y {{ lvm_vg }}/{{ lvm_local_lv }}

# Make the new snapshot
lvcreate -n {{ lvm_local_lv }} --snapshot {{ lvm_vg }}/{{ lvm_synctarget_lv }}
lvchange -ay -k n {{ lvm_vg }}/{{ lvm_local_lv }}
mount -o discard /dev/{{ lvm_vg }}/{{ lvm_local_lv }} /kube/localcopy

# Mark the sync target as ready
mv {{ synctarget_mountpoint }}/snapshotting {{ synctarget_mountpoint }}/ready

# Scale everything back up
{% for scale_target in scale_targets %}
k -n {{ scale_target.namespace }} scale {{ scale_target.target }} --replicas={{ scale_target.nominal_replicas }}
{% endfor %}
