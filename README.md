# cloudconfig-writer
Write a CoreOS cloud-config file from a 'master' cloudconfig file


## Problem
You use similar CoreOS cloud-config files on different providers (or similar ones on the same provider). You have to copy/paste things and you find yourself repeating things.
##Solution
Generate a CoreOS cloud-config file from a 'master' file. This master file is an 'inventory' of components you use for the generated file.
###How it Works
The component types identified in the master cloud-config file are: `coreos.units`,  `write_files`, and `users`. These sections are addressed because they often have many entries that the user might want to include in another cloud-config file (the code can easily be modified to include other sections in addition to non-CoreOS could-config files). In YAML parlance, these sections are called block sequences.

Furthermore, entries in a block sequence are idenified by a 'key'. These keys are `name`, `path`, and `name` for `coreos.units`,  `write_files`, and `users` respectively.

The user lists desired components in a 'skeleton' yaml file. It's still a valid, but useless, cloud-init file with the 'stuffing' from each entry removed.

The usage section should help clarify how it works. The code works with `python` 2.7 and needs `pyyaml` (a recent `pyyaml` should work).

####Usage:
You'll need a master cloud-config file, a skeleton cloud-config file, and, optionally, environment variable files.
#####Master cloud-config File
Begin with a master cloud-config file and insert substitution tokens like `$VAR` or `${VAR}`. As a convenience, `VAR==` will be substituted with `VAR=${VAR}`. Use capital letters.
#####Skeleton
As a convenience, you can make a skeleton file from the subcommand:
```shell
> python constructor.py skeleton samples/user-data.master.yaml
```
```yaml
#cloud-config
coreos:
  etcd2:
    advertise-client-urls: http://$public_ipv4:2379
    discovery: https://discovery.etcd.io/<token>
    initial-advertise-peer-urls: http://$private_ipv4:2380
    listen-client-urls: http://0.0.0.0:2379,http://0.0.0.0:4001
    listen-peer-urls: http://$private_ipv4:2380,http://$private_ipv4:7001
  fleet:
    metadata: loc=local , role=init
    public-ip: $public_ipv4
  units:
  - name: fleet.service
  - name: docker.service
hostname: $HOSTNAME
users:
- name: elroy
write_files:
- path: /etc/resolv.conf
- path: /etc/motd
- path: /tmp/like_this
- path: /tmp/or_like_this
- path: /tmp/todolist
- path: /home/core/vartest.script
```
Obviously, we don't want to include everything so just delete stuff you don't need:
```yaml
#cloud-config
coreos:
  fleet:
    metadata: loc=local , role=init
    public-ip: $public_ipv4
  units:
  - name: docker.service
hostname: $HOSTNAME
users:
  - name: elroy
write_files:
- path: /etc/resolv.conf
- path: /etc/motd
- path: /home/core/vartest.script
```
#####Env Files
Also, make file(s) that have substitutions for your variables. I will call them env(ironment) files. These files have the format
```shell
#comments
VAR1=value1
VAR2=value2
```
You can check what variables you need by issuing:
```shell
> python constructor.py unassigned samples/user-data.master.yaml samples/skeleton.yaml 
```

#####Generate cloud-init file
Now all that is left is to create your CoreOS cloud-init file by:
```shell
> python constructor.py samples/user-data.master.yaml samples/skeleton.yaml samples/env1 samples/env2
```
```yaml
#cloud-config

coreos:
  fleet:
    metadata: loc=local , role=init
    public-ip: $public_ipv4
  units:
  - command: start
    drop-ins:
    - content: '[Service]

        Environment=DOCKER_OPTS=''--insecure-registry="10.0.1.0/24"''

        '
      name: 50-insecure-registry.conf
    name: docker.service
hostname: NOTONE
users:
- groups:
  - sudo
  - docker
  name: elroy
  passwd: abc123
write_files:
- content: 'nameserver 8.8.8.8

    '
  owner: root
  path: /etc/resolv.conf
  permissions: 420
- content: 'Good news, everyone!

    '
  owner: root
  path: /etc/motd
  permissions: 420
- content: "#this should go in as VAR=${VAR}\nVAR=${VAR}\n\n \n"
  path: /home/core/vartest.script
```
The output is not as human-friendly as our example master file but it's still a valid CoreOS cloud-config file.

You can supply multiple env files. Values of variables with the same name will be replaced with the value of its later occurance. Check again if you missed a variable by using the `unassigned` sub-command with the env files.

```shell
> python constructor.py unassigned samples/user-data.master.yaml samples/skeleton.yaml samples/env1 samples/env2
```
In this example, `VAR` still has no value.



## Miscellaneous
- The processing presented here is basic (on purpose). However, it can form the basis for more sophisticated processing.
- Keep private data, such as passwords and keys, private by putting private data in env files out of the scope of source control.
- A cool thing that you can do is have `production.env` file but then 'override' some of those variables in a `development.env`. DRY to the max!