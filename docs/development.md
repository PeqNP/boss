# Install Instructions (Development)

Install the latest BOSS apps into the public apps directory.

```bash
$ cp -r sandbox/io.bithead.boss-code/* public/boss/app/
```

This effectively "installs" all BOSS apps to the public facing BOSS instance.

## Configure Xcode

Before you can run the Swift server you have to set the working directory

- Open `web` project in Xcode
- Hover over `boss` binary in middle of window pane and `Edit scheme`
- In the `Run` tab, select `Options` tab
- Check `Use custom working directory:`
- Add `/path/to/boss/swift/web`

For who knows what reason, this must be added to your `~/.gitconfig` in order for Yams to resolve... W T F
```
[url "git@github.com:"]
    insteadOf = https://github.com/
```

## Dependencies

Clone the following repositories in `~/source`:
```bash
mkdir -p ~/source
git clone git@github.com:PeqNP/ays-server.git
git clone git@github.com:PeqNP/boss.git
```

### Selenium

```bash
$ brew install python3 openssl
```

> Note: Installing openssl _before_ creating a virtual environment ensures `python3` links to `openssl` instead of using the sysystem-install `libressl`, which is incompatible with `urllib3`.

This will install a version of Python where packages may not be installed except through a virtual env.

```bash
$ python3 -m venv create ~/.venv
$ source ~/.venv/bin/activate
$ cd test
$ pip3 install --upgrade pip
$ pip3 install -r requirements.txt
$ cd ../private
$ pip3 install --upgrade pip
$ pip3 install -r requirements.txt
```

To run Selenium tests:

```bash
$ cd test
$ ./run_tests
```

### `nginx`

BOSS requires `nginx` in order to map resources to different running services.

```
brew update
brew install nginx
```

If the service fails to start run

```
cp private/dev-nginx.conf /opt/homebrew/etc/nginx/servers/
nginx -t
brew services restart nginx
```

You can also see if it's in error

```
brew services list
```

#### SSL

In order for your local environment to behave like production in all browsers, you must use a
self-signed SSL certificate and run BOSS on 443.

```
$ openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
$ mv cert.pem key.pem ~/.boss/
```

#### `nginx` configuration

> Assumes running development on macOS.

- Config file @ `/opt/homebrew/etc/nginx/nginx.conf`
- Access log @ `/opt/homebrew/var/log/nginx/access.log`
- Error log @ `/opt/homebrew/var/log/nginx/error.log`

The file is located in `/boss/private/dev-ngninx.conf`.

To run `nginx`:

```zsh
$ brew services restart nginx
```

> Some private services, such as those that provide authentication, are ran w/ Swift+Vapor and are not included in this repository.

### Run Web Services

Now that `nginx` is running, and all dependencies are installed, you can start the services using:

```zsh
$ ./private/start
```

To run the Swift+Vapor server, open the Xcode project in `/path/to/boss/web` and `Run`.

> The Swift+Vapor server is currently not open source.

### Configure Python PATH

```bash
file: ~/.bashrc
export PYTHONPATH=~/source/boss/private
```

### Developing on Safari

Most browsers simply ask you to proceed when a self-signed SSL cert is provided. For Safari, do the following to allow self-signed certs:

- Open https://localhost
- Tap `Show Details`
- Tap `visit this website` link (It's inside of some verbiage)

