This is a system that replicates a Kubernetes deployment on a remote machine outside of Kubernetes. It is used for failover in case the cluster is unavailable.

A CronJob running on Kubernetes creates clones of designated PersistentVolumeClaims, rsync them to a remote machine, where replicas of the containers are run over a thin clone of the volume (using lvmthin).

This repository contains both the code for the CronJob, cloning and copying the data, and the remote VM setup, as an Ansible playbook.
