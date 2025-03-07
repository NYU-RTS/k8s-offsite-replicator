import argparse
import kubernetes.client as k8s_client
import kubernetes.config as k8s_config
import logging
import os
import sys


logger = logging.getLogger('k8s_replicator')


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Parse command line
    parser = argparse.ArgumentParser(
        'k8s_replicator',
        description="Replicates a Kubernetes deployment on a remote machine",
    )
    parser.add_argument('--kubeconfig', nargs=None)
    parser.add_argument('--namespace', nargs=None, required=True)
    parser.add_argument('--target', nargs=None, required=True)
    parser.add_argument('volumeclaim', nargs='+')
    args = parser.parse_args()

    if args.kubeconfig:
        logger.info("Using specified config file")
        k8s_config.load_kube_config(args.kubeconfig)
    else:
        logger.info("Using in-cluster config")
        k8s_config.load_incluster_config()

    # Get current Job identity, to set as owner for other objects
    if 'OWNER_JOB' in os.environ:
        owner = {
            'apiVersion': 'batch/v1',
            'blockOwnerDeletion': true,
            'kind': 'Job',
            'name': os.environ['OWNER_JOB'],
        }
    else:
        owner = None

    api = k8s_client.ApiClient()
    corev1 = k8s_client.CoreV1Api(api)

    # Clone the PersistentVolumeClaims
    for name in args.volumeclaim:
        # Get it
        claim = corev1.read_namespaced_persistent_volume_claim(
            name,
            args.namespace,
        )

        # Change the name, ownership, and strip other metadata
        # Also set dataSource to clone the original
        claim = k8s_client.V1PersistentVolumeClaim(
            api_version='v1',
            kind='PersistentVolumeClaim',
            metadata=k8s_client.V1ObjectMeta(
                name='replication-' + name,
                namespace=args.namespace,
                owner_references=owner,
            ),
            spec=k8s_client.V1PersistentVolumeClaimSpec(
                volume_mode='Filesystem',
                access_modes=['ReadWriteOnce'],
                resources=claim.spec.resources,
                storage_class_name=claim.spec.storage_class_name,
                data_source={
                    'kind': 'PersistentVolumeClaim',
                    'name': name,
                }
            )
        )

        # Create the clone
        corev1.create_namespaced_persistent_volume_claim(
            claim.metadata.namespace,
            claim,
        )


if __name__ == '__main__':
    main()
