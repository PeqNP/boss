# Server

Provides build, installation and run instructions for BOSS systems.

## Install Dependencies on Development Machine

Building is done via cross-compilation on macOS.

Install Swiftly. This allows you to install any version of Swift.

```bash
curl -O https://download.swift.org/swiftly/darwin/swiftly.pkg && \
installer -pkg swiftly.pkg -target CurrentUserHomeDirectory && \
~/.swiftly/bin/swiftly init --quiet-shell-followup && \
. "${SWIFTLY_HOME_DIR:-~/.swiftly}/env.sh" && \
hash -r
```

> Please use the same version of `swift` that Xcode uses. You check the version using `xcrun swift --version`, but I've found it isn't accurate. The only way to check is running `/bin/prepare` and seeing the version mismatch.

Install cross-compilation tools for Linux

6.2.1

```bash
swift sdk install https://download.swift.org/swift-6.2.1-release/static-sdk/swift-6.2.1-RELEASE/swift-6.2.1-RELEASE_static-linux-0.0.1.artifactbundle.tar.gz --checksum 08e1939a504e499ec871b36826569173103e4562769e12b9b8c2a50f098374ad
swiftly install 6.2.1
swiftly use 6.2.1
```

Use the latest version of swift.

```bash
. "/Users/ericchamberlain/.swiftly/env.sh"
```

To list sdks

```bash
swift sdk list
```

To remove an SDK

```bash
swift sdk remove <name>
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
cd boss
sudo chmod -R o+rx ./public
sudo cp ./server/web/boss.service /etc/systemd/system/
sudo apt-get install nginx git-lfs sqlite3 zsh python3-pip python3.12-venv python3-certbot-nginx
```

Generate the SSL certificates

(Public) If creating a public server, use LetsEncyprt
```
sudo cp ./private/nginx.conf /etc/nginx/sites-available/default
```

TBD: Instructions to install letsEncrypt as well as updating SSL cert
```
sudo systemctl reload nginx snapd
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
```

(Private) If you are creating a development server, copy the `pem`s used for development to the dev server:
(Local)
```
sudo cp ./private/dev-nginx.conf /etc/nginx/sites-available/default
scp ./docs/ssl/* ~/.boss/key.pem boss-dev@192.168.50.77:~/.boss/
```
You will need to update the nginx.conf to point to the correct home location.

(Remote)

```
cd ~
python3 -m venv create ~/.venv
source ~/.venv/bin/activate
```

> The instructions are still out-of-date. I will fix this when I create a new server.

(Public)
Test DNS by creating simple Python server in `boss`. This must be done first in order for `certbot` to succeed.

```
$ cd ~/boss
$ sudo python3 -m http.server 80
```

Test at http://www.bithead.io. If you see the directory contents, you're good to go to the next step.

Install certbot certs.

```
$ sudo certbot certonly --nginx
```

A `~/.boss/config` file must be created and uploaded. The config should contain all of the following keys:

```
env: dev
db_path: /home/ubuntu/db
boss_path: /home/ubuntu/boss
sandbox_path: /home/ubuntu/sandbox
hmac_key: <Add key here>
host: <Root host value e.g. https://bithead.io>
media_path: /home/ubuntu/boss/public
log_path: /home/ubuntu/logs
login_enabled: false
jira_url:

apn_key:
apn_key_id:
apn_team_id:
apn_topic:
slack_client_id:
slack_client_secret:
slack_token:

smtp_enabled: 0
smtp_host:
smtp_port:
smtp_username:
smtp_password:
smtp_sender_email:
smtp_sender_name:
phone_number: +1 555-555-5555
email_address: test@example.com
```

### Configure `ngnix.conf`

Make sure the `nginx.conf` is running as the user of your machine e.g. `ubuntu`, `boss-dev`, etc. Running as `www-data` causes way too many problems. I was not able to have the user be able to see `boss/public` even though the permissions were set correctly.

```
vim /etc/nginx/nginx.conf
user ubuntu;
```

### Configure Python PATH

```bash
file: ~/.bashrc
export PYTHONPATH=/home/ubuntu/boss/private
```

### Build and Install `boss` server

(Local)
On your development machine, build the boss Swift+Vapor service.

```
cd /path/to/boss
./bin/prepare ~/.boss/machine
```

> Note: The `~/.boss/machine` file consists of a single line with the user@server config. e.g. `boss@192.168.50.77`. This is how I store my public and private server configuration, without adding it in the repository.

(Remote)
Install and run the services.

(Public)

```
cd ~/boss
./bin/install
```

(Private)

```
cd ~/boss
./bin/install-private
```

> Note: You may need to update the `sites-available/default` file before installing. There is no nginx.conf for private servers yet.

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
./bin/backup
./bin/prepare
```
- (Remote) Install update. Please note, after signing in, the server may have performed updates. Run `sudo reboot`, if necessary.
```
ssh -i ~/.boss/boss-key.pem <user@server_ip>
cd boss
./bin/install
```

### Database updates

Database updates are performed within `bosslib`. Please refer to `bosslib/Sources/bosslib/Database/v1_1_0.swift` for an example.

### Backup database

```bash
./bin/backup
```

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

You can check if the Swift server is working with

```
curl http://127.0.0.1:8081/version
```

## Debugging server crashes

It's necessary to build the Swift binary that does not remove debug symbols.

Update the `./bin/prepare` and uncomment out the `swift` line that does not have `-Xswiftc -gnone` then run `./bin/prepare`

On the server, comment out the `strip` line in `./bin/install`.


```
sudo apt update
sudo apt install systemd-coredump gdb lldb
sudo systemctl enable --now systemd-coredump.socket
sudo systemctl edit boss.service
```

Add the following, if it does not already exist:

```
[Service]
LimitCORE=infinity
```

Then get the debugger running again
```
sudo systemctl daemon-reload
sudo systemctl restart boss.service
```

Perform the action that causes the server to crash. Then run:

```
sudo coredumpctl debug --debugger lldb
```

To remove coredumps

```
sudo journalctl --flush --rotate --vacuum-time=1s
sudo journalctl --user --flush --rotate --vacuum-time=1s
```

It should pick the last coredump. You can check by running `sudo coredumpctl list`. The timestamp should match the last one.


## Certbot

### Re-issue SSL certificate

```
sudo systemctl stop nginx.service
sudo certbot renew
sudo systemctl start nginx
```

### Test cron

```
sudo systemctl status certbot.timer
```

If not enabled

```
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```
