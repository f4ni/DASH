
## How to run P4 based BMV2 and Python based DASH model:

* Assuming the DASH is cloned
* Go to 'DASH/dash-pipeline'
* Open 5 terminal sessions
 
* Go to 'DASH/dash-pipeline' in each of these 5 sessions
 
* Run these commands one-by-one in 1st terminal session: 

   ./dash_run.sh py-clean
 
   ./dash_run.sh sai-clean
 
   ./dash_run.sh sai-server-clean
 
   ./dash_run.sh bmv2-build         # to build BMV2 =OR=
   ./dash_run.sh pymodel-build      # to build pymodel
 
 
* Run `./dash_run.sh bmv2` in 1st terminal session to run BMV2 =OR=
* Run `./dash_run.sh pymodel` in 1st terminal session to run pymodel
 
* Run `./dash_run.sh dpapp` in 2nd terminal session
 
* Run `./dash_run.sh saiserver` in 3rd terminal session
 
* Run `./dash_run.sh ptftest` in 4th terminal session

* Run `./dash_run.sh kill` in 5th terminal session to kill the setup