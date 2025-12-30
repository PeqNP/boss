# CanaKit (Raspberry Pi 5)

Documentation on configuring a CanaKit Raspberry Pi 5 module.

### Create SD image

Use the Raspberry Pi Imager to create a 24.04 image for Rasp Pi 5

### Connect via RJ-45

To communicate with the CanaKit, using a Belkin RJ-45 to USB-C adaptor, you will need to configure the adaptor to assign its own IP address if no connection is found.

Connect mini-HDMI, keyboard, and RJ-45 > USB-C adaptor to the CanaKit. Then do the following:

```
sudo vim /etc/netplan/99-direct-connection.yaml

// file: 99-direct-connection.yaml
// Should be an empty file. Paste the below:
network:
  version: 2
  renderer: networkd
  ethernets:
    eth0:
      dhcp4: true
      optional: true
      link-local: [ipv4]
// -> Save (:x)

sudo netplan generate
sudo netplan apply
```

You can see the unit's IP address by doing the following:

```
ip addr show eth0
```

> Note: On subsequent boots, it will apply this same configuration.

Because the IP address may change between boots, you can use the following command on macOS to find all machines on the local network if the IP address changes:

```
arp -a | grep 169.254
```

#### Sharing internet

You can share MacBook's internet with your CanaKit by doing the following

- Settings > Sharing > Internet Sharing
- Configure respective RJ-45 adaptor to be enabled e.g. Toggle `Belkin USB-C LAN` to "on"
- It may be necessary to toggle `Internet Sharing` "on" even after configuration
- Powercycle the CanaKit. This ensures it is assigned an IP from MacBook.

To test
```
ip addr show
```

It should an IP address like `192.186.3.2`.

You should now have internet access. I use `ping google.com` to test.

### Connect via WiFi

If connecting over WiFi, there should be no additional work, so long as you configured the WiFi endpoint correctly.
