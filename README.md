# master
this is a repository for my master thesis dont bother pulling until the readme tells its finished 
a script for weekly renewal of certs

#!/bin/sh
export STEPPATH=/root/.step
step ssh renew ssh_host_ecdsa_key-cert.pub ssh_host_ecdsa_key --force 2> /dev/null
sudo cp ssh_host_ecdsa_key-cert.pub /etc/ssh
exit 0
