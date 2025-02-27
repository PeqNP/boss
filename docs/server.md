# Server

Provides build, installation and run instructions for BOSS systems.

## Install Dependencies on Development Machine

Building is done via cross-compilation on macOS.

Download and install the Swift dependencies.

```
$ wget https://download.swift.org/swift-6.0.3-release/xcode/swift-6.0.3-RELEASE/swift-6.0.3-RELEASE-osx.pkg
```

Open `pkg` and select the toolchain. Add this to `~/.zshrc` so that you don't have to do it every time you build.

```
export TOOLCHAINS=$(plutil -extract CFBundleIdentifier raw /Library/Developer/Toolchains/swift-6.0.3-RELEASE.xctoolchain/Info.plist)
```

Install SDK

```
swift sdk install https://download.swift.org/swift-6.0.3-release/static-sdk/swift-6.0.3-RELEASE/swift-6.0.3-RELEASE_static-linux-0.0.1.artifactbundle.tar.gz --checksum 67f765e0030e661a7450f7e4877cfe008db4f57f177d5a08a6e26fd661cdd0b
```

> You can [download the latest release](https://www.swift.org/install/linux/ubuntu/22_04/#latest) from Swift.

### Cleaning

Sometimes the build gets stuck. Do fix this, clean the build.

```
$ swift package clean
$ rm -rf .build
```

## AWS

Create A record w/ public IP address in Namecheap > Advanced DNS for respective host (`bithead.io`).

- Find the `Public IPv4 Address` in respective EC2 instance
- Login to Namecheap > `bithead.io` > Advanced DNS
- Create A record w/ `@` and IP address

In order for cerbot to determine if you own the domain, you must temporarily open port 80 for HTTP requests. Do this by

- Navigating to the EC2 instance
- Tapping the `Security` tab
- Tap the `Security groups` link for the EC2 instance
- `Edit inbound rules`
- `Add rule`
- Add HTTP port 80 w/ CIDR 0.0.0.0/0

### Installation

t4g.small 24.04 Ubuntu w/ 8GiB disk, arm64 2 CPUs

> Reference [vapor systemd](https://docs.vapor.codes/deploy/systemd/)

(Remote) Prepare environment

- To SSH you need the key pair. You can download the key-pair if you go into the instance. I named it `boss-key`.
- Download, place in `~/.boss/boss-key.pem`.
- `chmod 400 ~/.boss/boss-key.pem`
- SSH into server
```
$ ssh -i ~/.boss/boss-key.pem <user@server_address>
```

Create SSH token for GitHub

```
$ ssh-keygen -t ed25519 -C "<email>"
$ eval "$(ssh-agent -s)"
$ vim ~/.ssh/config
```

And add to `/.ssh/config`

```
Host github.com
  AddKeysToAgent yes
  IdentityFile ~/.ssh/id_ed25519
```

> Add `UseKeychain yes` if on macOS.

Copy and paste in new SSH key in GitHub

```
$ cat ~/.ssh/id_ed25519.pub
```

Install dependencies

```
mkdir ~/.boss
mkdir db
mkdir logs
git clone git@github.com:PeqNP/boss.git
sudo chmod -R o+rx /home/ubuntu/boss/public
sudo cp ./boss/swift/boss.service /etc/systemd/system/
sudo apt-get install nginx git-lfs sqlite3 zsh python3-pip python3.12-venv
sudo cp ./boss/private/nginx.conf /etc/nginx/sites-available/default
sudo systemctl reload nginx snapd
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
python3 -m venv create ~/.venv
source ~/.venv/bin/activate
cd boss/private
pip3 install -r requirements.txt
```

> Unfortunately the above instructions may be out-of-date. I will fix this when I create a new server.

Test DNS by creating simple Python server in `boss`. This must be done first in order for `certbot` to succeed.

```
$ cd ~/boss
$ sudo python3 -m http.server 80
```

Test at http://www.bithead.io. If you see the directory contents, you're good to go to the next step.

Install certbot certs.

```
$ sudo certbot certonly --standalone
```

A `~/.boss/config` file must be created and uploaded. The config should look like the following:

```
env: prod
db_path: /home/ubuntu/db
boss_path: /home/ubuntu/boss
sandbox_path: /home/ubuntu/sandbox
hmac_key: <key goes here>
host: https://bithead.io
media_path: /home/ubuntu/boss/public
log_path: /home/ubuntu/logs
login_enabled: true
```

### Configure `ngnix.conf`

Make sure the `nginx.conf` is running as the `ubuntu` user. Running as `www-data` causes way too many problems. I was not able to have the user be able to see `boss/public` even though the permissions were set correctly.

```
vim /etc/nginx/nginx/com
```

Set `user ubuntu;`

### Configure Python PATH

```bash
file: ~/.bashrc
export PYTHONPATH=/home/ubuntu/boss/private
```

### `systemd` Commands

```bash
sudo systemctl daemon-reload
sudo systemctl enable boss
sudo systemctl start boss
sudo systemctl stop boss
sudo systemctl restart boss
```

### Updating the Service

(Local) Build and upload new binary

- Close Xcode
- (Client / dev or build machine) Build the app and backup the production system.
```
./bin/prepare
```
- (Remote) Install update
```
ssh -i ~/.boss/boss-key.pem <user@server_ip>
cd boss
./bin/install
```

### Database updates

Updates are performed by running the following:

```bash
$ ./db/update.py
```

Updates are stored in `update.sql` files in `db/<version>/update.sql`. Where version follows the `#.#.#` (major.minor.revision) format.

e.g. Version `1.0.1` would be in `db/1.0.1/update.sql`.

A CSV file in the root directory `db/versions.sql` contains the list of supported versions. The versions are ordered in ascending order, oldest to latest.

```
file: versions.sql
1.0.0
1.0.1
1.1.0
1.5.0
2.0.0
```

The Python script checks the current version of the database, finds the row that matches its version, and then applies all updates that appear after its version. Each update is performed in a transaction. If one of the updates fails, the process stops at the version that failed.

### Backup database

```
scp -i ~/.boss/boss-key.pem -r ubuntu@ec2-35-93-38-194.us-west-2.compute.amazonaws.com:~/db/ays.sqlite3 ~/tmp/
```

This is also part of the update instructions.

> Media is currently stored in `boss/public/upload`. This may change in the future, where all media is stored on S3.

## Development

Refer to [Development](/docs/development.md) for development installation instructions.

## Debugging nginx

Determine if configuration has syntax errors

```bash
sudo nginx -t
```

Reload configuration

```bash
sudo systemctl reload nginx
```

Check status

```bash
systemctl status nginx.service
```

Watch `boss-server` logs

```
sudo journalctl -f -u boss.service
```

Watch `nginx` logs

```
tail -f /var/log/nginx/error.log
```

For more thorough logs, enable `debug` log level in `/etc/ngingx/nginx.conf`

```
error_log /var/log/nginx/error.log debug;
```

