# Server

Provides build, installation and run instructions for BOSS systems that run on arm64 machines.

The server consists of

- Swift+Vapor: Critical parts of the OS (user and sessions) are written in Swift
- Python: Provides BOSS subsystems for desktop. All apps are written in Python to avoid having to recompile the Swift+Vapor backend. This allows a specific Python backend to be restarted w/o affecting other systems when an app is "installed."

You will see (Remote) and (Local) tags. When you see (Remote), this indicates that the commands must be ran on the remote server (the server that is hosting BOSS). When you see (Local), run these commands on your development machine (e.g. macOS)

## Install Dependencies on Development Machine

BOSS is designed to run on arm64 Ubuntu 24.04. I see no reason why it could not run on other archs or OSes (It runs fine on macOS). I did this only because I have little time and wanted to reduce variables.

(Local)

Building of the Swift+Vapor server is done via cross-compilation on macOS.

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

Sometimes the build gets stuck. Do this to clean the build:

```
$ swift package clean
$ rm -rf .build
```

## AWS

If you are going to host your instance of BOSS on AWS, please doe the following. Otherwise, skip this section.

Create `A record` w/ public IP address in your (DNS Provider) for respective host (e.g. `bithead.io`).

- Find the `Public IPv4 Address` in respective EC2 instance
- Login to (DNS Provider) > `bithead.io` > (Advanced) DNS
- Create `A record` w/ `@` and IP address

In order for cerbot to determine if you own the domain, you must temporarily open port 80 for HTTP requests. Do this by:

- Navigating to the EC2 instance
- Tapping the `Security` tab
- Tap the `Security groups` link for the EC2 instance
- `Edit inbound rules`
- `Add rule`
- Add HTTP port 80 w/ CIDR 0.0.0.0/0

### Installation

You can easily run BOSS on a `t4g.small` instance - 24.04 Ubuntu w/ 8GiB disk, arm64 2 CPUs

> Reference [vapor systemd](https://docs.vapor.codes/deploy/systemd/)

> Note: This expects the system user to be `ubuntu`. Otherwise, `install`, `prepare`, and `update` scripts will not work.

(Remote) Prepare environment so that `bin` scripts can sign in w/o user/pass:

- (?) Create SSH key on remote server
- To SSH into the server w/ key-pair, download from the instance. I named it `boss-key`.
- Download (scp), place in your development machine at `~/.boss/boss-key.pem`.
- `chmod 400 ~/.boss/boss-key.pem`
- SSH into server and clone BOSS
```
ssh -i ~/.boss/boss-key.pem ubuntu@<server_address>
sudo apt-get install git-lfs zsh
git clone https://github.com/PeqNP/boss.git
git lfs install
cd boss
```

> Note: If running BOSS in a production environment, your server must be reachable by its public domain name (e.g. http://bithead.io) before running `./bin/install prod`
>
> This is requried for LetsEncrypt to work.
>
> To test this, create a HTTP service and make sure you can read the directory contents
> ```
> sudo python3 -m http.server 80
> ```

Run the server installation script and follow the directions:

For development

```
./bin/install dev
```

For production

```
./bin/install prod
```

This will do the following:
- Guide you through installing GitHub SSH key
- Install dependencies
- Configure nginx
- Generate SSL certificates
- Install & run BOSS

> TODO: When installing a prod instance, open port 80 on nginx instead of redirecting to HTTPS. This allows `snapd` to regenerate SSL certs, when needed.

### Build, Install, & Run BOSS Server

Use this process when running your BOSS server for the first time and every subsequent time you wish to update your BOSS server.

> Note: It is not necessary to run the `./bin/install` script ever again.

(Local)

Build the boss Swift+Vapor service.

```
cd /path/to/boss
./bin/prepare ~/.boss/machine
```

> Note: The `~/.boss/machine` file consists of a single line with the server config. e.g. `192.168.50.77`. This is how I store my public and private server configuration, without adding it to the repository.

(Remote)

Update and run the services.

```
cd ~/boss
./bin/update
```

### `systemd` Commands

```bash
sudo systemctl daemon-reload
sudo systemctl enable boss
sudo systemctl start boss
sudo systemctl stop boss
sudo systemctl restart boss
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
