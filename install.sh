# blrec
git clone https://github.com/kirayomato/blrec blrec-master
mkdir blrec

# vtb-dynamic
git clone https://github.com/kirayomato/vtb_dynamic_push

# miniconda
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash ~/Miniconda3-latest-Linux-x86_64.sh
source ~/.bashrc

conda create -n blrec python=3.13 -y

conda activate blrec
cd blrec-master && pip install -e .

# openlist
curl -fsSL https://res.oplist.org/script/v4.sh > install-openlist-v4.sh && sudo bash install-openlist-v4.sh

# codeserver
curl -fsSL https://code-server.dev/install.sh | sh
sudo systemctl enable --now code-server
vim ~/.config/code-server/config.yaml
sudo systemctl daemon-reload
sudo systemctl restart code-server
sudo systemctl status code-server

# brec
sudo usermod -aG docker $USER
newgrp docker
docker pull bililive/recorder:latest

# gotify
# download from https://github.com/gotify/server/releases
unzip gotify-{PLATFORM}.zip
chmod +x gotify-{PLATFORM}
