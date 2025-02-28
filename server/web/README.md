# README

Provides @ys web services.

## @ys Configuration File

Create the @ys configuration file at `~/.boss/config`.

## Project Configuration

A working directory must be set to the root of the project.

- Select `ays-server` scheme
- Tap `Edit scheme`
- Tap `Run`
- Tap `Options`
- Enable `Working directory`
- Set the root directory to the root of the Swift project

## Swagger UI & Docs

Please refer to `/docs/swagger.md` to learn how to install Swagger UI, which is used by the @ys server and accessed at the resource `/swagger/`.

## Linux Installation

Please use `multipass`. Refer to docs/multipass.md.

This will create an instance named `primary` w/ latest version of Ubuntu. You must give the instance enough disk space.
```
multipass shell primary --disk=20G --memory=4G
```

Install Swift dependencies
```
echo "Ubuntu distribution"
lsb_release -a
echo "--------------------"
# Will tell you Ubuntu version. Install respective Swift.
# You can then use wget to DL binary
sudo apt-get git
ssh-keygen -t ed25519 -C "eric.j.chamberlain@protonmail.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
echo "Generated keys. Add to GitHub."
# TODO: Wait here
# Take output and copy into GitHub
git clone git@github.com:PeqNP/ays-server.git
sudo apt-get install clang libicu-dev build-essential pkg-config zlib1g-dev
```

Install Swift

Download respective version for Ubuntu version at [Swift](https://www.swift.org/download/#releases).

```bash
echo "Downloading swift..."
wget https://download.swift.org/swift-6.0-release/ubuntu2404-aarch64/swift-6.0-RELEASE/swift-6.0-RELEASE-ubuntu24.04-aarch64.tar.gz
echo "Installing swift..."
tar xvzf swift-6.0-RELEASE-ubuntu24.04-aarch64.tar.gz
sudo mkdir /swift
sudo mv swift-6.0-RELEASE-ubuntu24.04-aarch64 /swift/swift-6.0
sudo ln -s /swift/swift-6.0/usr/bin/swift /usr/bin/swift
swift --version
echo "Successfully installed Swift!"
# TODO: Wait for user input
```

Now build the `ays-server`

```bash
cd ~/ays-server/web
swift build
```

To build for production:

```bash
swift build -c release
```

The following must be done on all servers, but especially production.

```bash
useradd --user-group --create-home --system --skel /dev/null --home-dir /app vapor
cd /app
```
