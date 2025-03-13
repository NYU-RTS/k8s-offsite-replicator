This is a system that replicates a Kubernetes deployment on a remote machine outside of Kubernetes. It is used for failover in case the cluster is unavailable.

A CronJob running on Kubernetes creates clones of designated PersistentVolumeClaims, rsync them to a remote machine, where replicas of the containers are run over a thin clone of the volume (using lvmthin).

This repository contains both the code for the CronJob, cloning and copying the data, and the remote VM setup, as an Ansible playbook.

# Setup process

1. Get a cloud VM, attach a disk to it for lvmthin volumes

2. Run the ansible playbook against it: `ansible-playbook -u ubuntu --become -v playbook.yaml -i inventory.yaml`

3. Generate an SSH key for syncing: `ssh-keygen -f upload-key -N "" -t ed25519`

4. Add the SSH pubkey to the cloud VM: `sudo -Hu uploader sh -c 'mkdir --mode 700 $HOME/.ssh && cat > $HOME/.ssh/authorized_keys'`

5. Create the SSH secret on your cluster: `kubectl create secret generic replication "--from-literal=host-pubkey=$(ssh-keyscan 10.144.1.2)" --from-file=upload-key=upload-key`

6. Create the CronJob to sync from your cluster: `kubectl apply -f k8s-cronjob.yaml`

7. Deploy your app on the minikube cluster on the cloud VM, changing persistent volumes to use local volumes pointing to `/kube/...`
