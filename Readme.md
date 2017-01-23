A set of scripts to set up and run Debian under qemu-kvm

### Usage
Check if your machine supports hardware virtualization, the KVM project has
[instructions](http://www.linux-kvm.org/page/FAQ#How_can_I_tell_if_I_have_Intel_VT_or_AMD-V.3F).

Install dependencies. These are the packages for debian:
```
sudo apt-get install python3 xorriso
sudo apt-get install qemu-system-x86 qemu-kvm
```

Patch the official `netinst` image:
```
mkdir /tmp/vmkit; cd /tmp/vmkit
curl -OL 'http://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-8.7.1-amd64-netinst.iso'
mkdir netinst-iso
sudo mount -o loop debian-8.7.1-amd64-netinst.iso netinst-iso
sudo path/to/vmkit.py patchiso netinst-iso -o debian-8.7.1-vmkit.iso
sudo umount netinst-iso
```

Install the vm. It will show the installer output in the console using qemu's
serial port output:
```
sudo path/to/vmkit install --iso /tmp/vmkit/debian-8.7.1-vmkit.iso myvm
```

Run the VM; this will start up with the serial console connected to the current
terminal and log into a root shell:
```
sudo path/to/vmkit console --vm myvm
```
