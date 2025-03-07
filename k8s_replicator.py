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
    parser.add_argument('--target-path', nargs=None, required=True)
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
    cloned_claims = {}
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
        cloned_claims[name] = claim.metadata.name

    # Assemble the copy script
    ssh = 'ssh -i /var/run/secrets/replication/upload-key'
    script = [
        'set -eu',
        'mkdir /root/.ssh',
        'printf \'%s\\n\' "${HOST_KEY}" > /root/.ssh/known_hosts',
    ]
    # First, mark remote copy as incomplete
    script.append(ssh + ' ${TARGET} "rm -f ${TARGET_PATH}/ready"')
    # Then copy each PVC
    volume_mounts = []
    volumes = []
    for name in args.volumeclaim:
        script.append(
            'rsync'
            ' -e \'' + ssh + '\''
            ' --exclude /lost+found'
            ' -az /data/' + name + '/'
            ' ${TARGET}:${TARGET_PATH}/' + name,
        )
        volume_mounts.append(
            k8s_client.V1VolumeMount(
                mount_path='/data/' + name,
                name='pvc-' + name,
            ),
        )
        volumes.append(
            k8s_client.V1Volume(
                name='pvc-' + name,
                persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(
                    claim_name=cloned_claims[name],
                ),
            ),
        )
    # Finally, mark remote copy as complete
    script.append(ssh + ' ${TARGET} "touch ${TARGET_PATH}/ready"')

    # Create the copy job
    volume_mounts.append(
        k8s_client.V1VolumeMount(
            mount_path='/var/run/secrets/replication',
            name='key',
        ),
    )
    volumes.append(
        k8s_client.V1Volume(
            name='key',
            secret=k8s_client.V1SecretVolumeSource(
                secret_name='replication',
                default_mode=0o700,
            ),
        ),
    )
    container =  k8s_client.V1Container(
        name='copy',
        image='quay.io/remram44/networking:20250306',
        image_pull_policy='IfNotPresent',
        args=['sh', '-c', '\n'.join(script)],
        env=[
            k8s_client.V1EnvVar(
                name='TARGET',
                value=args.target,
            ),
            k8s_client.V1EnvVar(
                name='TARGET_PATH',
                value=args.target_path,
            ),
            k8s_client.V1EnvVar(
                name='HOST_KEY',
                value="10.144.64.227 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIL56p9h1LtsjTK+RdcrhnOjgbUfTdANf74+nhozAtGNh",
            ),
        ],
        volume_mounts=volume_mounts,
    )
    job = k8s_client.V1Job(
        api_version='batch/v1',
        kind='Job',
        metadata=k8s_client.V1ObjectMeta(
            name='replication-copy',
            namespace=args.namespace,
            owner_references=owner,
        ),
        spec=k8s_client.V1JobSpec(
            active_deadline_seconds=3600,
            backoff_limit=3,
            template=k8s_client.V1PodTemplateSpec(
                spec=k8s_client.V1PodSpec(
                    restart_policy='Never',
                    containers=[container],
                    volumes=volumes,
                ),
            ),
        ),
    )
    batchv1 = k8s_client.BatchV1Api()
    batchv1.create_namespaced_job(
        body=job,
        namespace=args.namespace,
    )


if __name__ == '__main__':
    main()
