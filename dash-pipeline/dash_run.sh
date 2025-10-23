
#To run the BMv2 model, run:
make network
make run-switch

#To run the BMv2 model with DPAPP support, run:
make network HAVE_DPAPP=y
make run-switch HAVE_DPAPP=y

#To generate all the python model artifacts, run:
make py-artifacts

#To clean all the python model artifacts, run:
make py-artifacts-clean

#To run the python model, run:
make pymodel

#To run the python model with DPAPP support, run:
make pymodel HAVE_DPAPP=y

#To build SAI for the python model, run:
sudo make sai TARGET_MODEL=pymodel

#To build SAI for the bmv2, run:
sudo make sai

#To clean SAI headers, run:
sudo chown -R <username>:<username> .
sudo make sai-clean HOST_USER=$(id -u) HOST_GROUP=$(id -g)

#To build SAI Server, run:
sudo chown -R <username>:<username> .
sudo make saithrift-server HOST_USER=$(id -u) HOST_GROUP=$(id -g)

#To clean SAI Server, run:
sudo make saithrift-server-clean HOST_USER=$(id -u) HOST_GROUP=$(id -g)

#To build SAI Client, run:
make docker-saithrift-client

#To run DPAPP, run:
make run-dpapp

#To run SAI Server, run:
# make saithrift-server
docker rm -f dash-saithrift-server-"${USER}"
make run-saithrift-server

#To run PTF Tests, run:
make docker-saithrift-client
make run-saithrift-ptftests

#To kill all consoles, run:
make kill-all
make kill-dpapp
pkill -f main_dash.py
