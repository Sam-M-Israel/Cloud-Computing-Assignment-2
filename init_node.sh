#!/bin/bash
echo "Starting setup..."
sudo apt -f install
sudo apt -y update && sudo apt -y dist-upgrade
sudo apt install git
sudo apt -y install python3-pip
sudo apt-get install python3-flask -y
sudo apt -y install build-essential libssl-dev libffi-dev python3-dev
cd /home/ubuntu
git clone https://github.com/Sam-M-Israel/Cloud-Computing-Assignment-2.git
echo "Successfully cloned github code…"
cd Cloud-Computing-Assignment-2
pip3 install -r requirements.txt && pip3 freeze > requirements.txt
export FLASK_APP=app.py && export FLASK_ENV=production && export FLASK_DEBUG=0
echo "Starting flask server, you can access this instances EC2 public IP, port 8080"
nohup flask run --host 0.0.0.0 >/dev/null & exit
