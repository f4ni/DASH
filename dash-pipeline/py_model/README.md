# IN PROGRESS

## How to run P4 based BMV2 and Python based DASH model:

* Assuming the DASH is cloned
* Assuming the Python Model is cloned
* Go to 'dash_py_model'
* Run `./run.sh build` to build all required modules
* Run `./run.sh genjson`, this will generate `py_p4rt.json` file
* Open 5 terminal sessions
* Run `./run.sh pymodel` in 1st terminal session to run Python Model
* Run `./run.sh bmv2` in 1st terminal session to run BMV2
* Run `./run.sh dpapp` in 2nd terminal session
* Run `./run.sh saiserver` in 3rd terminal session
* Run `./run.sh ptftest` in 4th terminal session
* Run `./run.sh kill` in 5th terminal session to kill the setup
