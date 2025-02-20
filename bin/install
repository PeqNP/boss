#!/bin/zsh
#
# Install latest version of BOSS.
#
# This is ran on the production server.
#

echo "Stopping services..."
source ~/.venv/bin/activate
sudo systemctl stop nginx
sudo systemctl stop boss

echo "Updating services..."
cd boss
./private/stop
git pull
sudo cp ./private/nginx.conf /etc/nginx/sites-available/default
# FIXME: Push any resources that were created
# git commit -m "[Name, Mon Day Time]" e.g. Fri, Dec 13 7:24AM
# git push origin head
cd private
pip3 install -r requirements.txt
cd ..

echo "Starting services..."
./private/start
cd ~/

# TODO: Check if `boss-server-update` exists. Only move it if it exists.
mv boss-server-update boss-server
sudo systemctl start boss
sudo systemctl start nginx
