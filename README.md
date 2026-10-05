To get this running:

git clone https://github.com/Laurirai/SAMD_SERVER.git

cd SAMD_SERVER

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

---

(NOTE! this needs to have been done & mosquitto launched prior to launching.)
uvicorn app.main:app --host 0.0.0.0:8000 --reload


for the mosquitto broker & certs do these.

mkdir -p /etc/mosquitto/certs
mkdir -p /etc/mosquitto/conf.d

sudo nvim /etc/mosquitto/acl
copy&paste\
user samd\
topic write sleep/data\
topic write sleep/status\
topic read  sleep/cmd

user server\
topic read  sleep/data\
topic read  sleep/status\
topic write sleep/cmd

----
