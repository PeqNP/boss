# multipass

Multipass is a tool that allows you to create Ubuntu VMs. I use it to test `/bin/*` scripts before installing on production machines. It can also be used to validate that BOSS will work correctly in a production environment.

- [Install multipass](https://canonical.com/multipass/install)
- Install 24.04 LTS `multipass launch 24.04 --name boss-dev`
  - Subsequent launches: `multipass launch boss-dev`
- Access interactive shell `multipass shell boss-dev`

Now read `/docs/server.md` to install and run BOSS.

## Installing SSH key

After generating a SSH key on the host machine (the machine that will host the VM), install the SSH key with the following

```
multipass exec boss-dev -- bash -c 'mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys' < ~/.ssh/id_ed25519.pub
```

Then SSH into the VM

```
ssh ubuntu@10.211.55.4 -i ~/.ssh/id_ed25519
```

To find the VMs IP, run `multipass list`.
