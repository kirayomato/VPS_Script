#!/bin/bash
source ~/miniconda3/etc/profile.d/conda.sh

# screen -X -S vtb quit
conda activate blrec
cd ~/vtb_dynamic_push
screen -T xterm-256color -S vtb python main.py

conda activate blrec
cd ~/vtb_dynamic_push
screen -S image python image_proxy.py

conda activate blrec
cd
screen -S blrec_api python blrec_api.py

# screen -S blrec
conda activate blrec
cd ~/blrec
screen -S blrec python -m blrec -c settings.toml --host 0.0.0.0 --port 2233

conda activate blrec
cd ~/blrec
screen -S danmaku python -m blrec -c settings2.toml --host 0.0.0.0 --port 2234 --danmaku-only

screen -S gotify sudo ./gotify-linux-amd64

conda activate blrec
screen -S blrec_check python blrec_check.py

conda activate blrec
cd ~/AutoFund
screen -S fund python web_app.py

export HTTP_PROXY=socks5://127.0.0.1:10809
export HTTPS_PROXY=socks5://127.0.0.1:10809

docker run -d \
  --name brec \
  -p 2356:2356 \
  -v ~/brec:/rec \
  -e BREC_HTTP_BASIC_USER=admin \
  -e BREC_HTTP_BASIC_PASS=2377839qw \
  -e UMASK=022 \
  -e PUID=1000 \
  -e PGID=1000 \
  bililive/recorder:latest

cSd9xhG2Qc6KXknn
kAKw6Wdbv68UGFyZ
root@185.223.252.21 H7q6BMkWY4ek462Ogp
ubuntu@185.223.252.21 2377839qw
