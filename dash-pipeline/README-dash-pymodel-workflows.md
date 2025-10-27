**>> I Don't have time to RTFM!***   [Jump to Concise Developer Workflows](#concise-developer-workflows)

*(Read the Fancy Manual)

See also:
* [README.md](README.md) Top-level README for dash-pipeline
* [README-dash-workflows.md](README-dash-workflows.md) for bmv2-based workflows
* [README-pymodel.md](README-pymodel.md) for Python model architecture overview
* [README-dash-ci](README-dash-ci.md) for CI pipelines
* [README-dash-docker](README-dash-docker.md) for Docker overview and workflows
* [README-saithrift](README-saithrift.md) for saithrift client/server and test workflows
* [README-ptftests](README-ptftests.md) for saithrift PTF test-case development and usage

**Table of Contents**
- [Concise Developer Workflows](#concise-developer-workflows)
  - [Use Case I - Developing Python Model Code](#use-case-i---developing-python-model-code)
    - [Sending packets "manually" into the switch](#sending-packets-manually-into-the-switch)
  - [Use-Case II - Developing End-to-End Tests with saithrift PTF](#use-case-ii---developing-end-to-end-tests-with-saithrift-ptf)
  - [Use-Case III - Incremental Test-Case Development](#use-case-iii---incremental-test-case-development)
- [Make Target Summary](#make-target-summary)
  - [Make "ALL" Targets](#make-all-targets)
  - [Build Artifacts](#build-artifacts)
  - [Launch Daemons/Containers](#launch-daemonscontainers)
  - [Run Tests](#run-tests)
- [Detailed Python Model Build Workflow](#detailed-python-model-build-workflow)
  - [Docker Image(s)](#docker-images)
  - [Build Workflow Diagram](#build-workflow-diagram)
  - [Make Py-Artifacts](#make-py-artifacts)
  - [Cleanup](#cleanup)
  - [Stop Containers](#stop-containers)
  - [Generate Python Model Artifacts](#generate-python-model-artifacts)
  - [Build libsai.so adaptor library](#build-libsaiso-adaptor-library)
  - [Build saithrift-server](#build-saithrift-server)
  - [Create veth pairs for py_model](#create-veth-pairs-for-py_model)
  - [Run Python Model](#run-python-model)
  - [Run saithrift-server](#run-saithrift-server)
  - [Build saithrift-client docker image](#build-saithrift-client-docker-image)
  - [Run saithrift-client PTF tests](#run-saithrift-client-ptf-tests)
  - [Run saithrift-client "Dev" PTF tests](#run-saithrift-client-dev-ptf-tests)

# Concise Developer Workflows
This section gives you a quick idea of how to work on various tasks efficiently with the Python model. The Python model provides an alternative to the bmv2-based switch for faster development cycles and easier debugging.

>Do you have another use-case in mind? Help document it with a Pull-Request, or ask the community.

## Use Case I - Developing Python Model Code
Developing Python model code requires generating artifacts via `make py-artifacts`. This is very quick since Python code doesn't need compilation. You can run the code via `make pymodel`. This setup doesn't support any switch configuration, so the testability is minimal. You can send in packets and observe the Python console logging to verify packet parsing/deparsing. See [Sending packets "manually" into the switch](#sending-packets-manually-into-the-switch)

![dev-workflow-pymodel](images/dev-workflow-pymodel.svg)

### Sending packets "manually" into the switch
Assuming you've done `make all` at least once, you will have a handy saithrift-client docker image which contains scapy, snappi libraries to run ixia-c SW traffic generator, etc. See the "optional" box in the figure above.

You can enter the container and run ad-hoc scapy commands, see below:
```
make pymodel                    # console 1 - runs Python model with packet sniffer
make run-saithrift-client-bash  # console 2
...
root@chris-z4:/tests-dev/saithrift# scapy
>>> p=Ether()/IP()/UDP()
>>> sendp(p, iface='veth0')
.
Sent 1 packets.
>>>
```

## Use-Case II - Developing End-to-End Tests with saithrift PTF
End-to-end tests require building artifacts and saithrift-client docker image.

A concise set of commands to run, in three separate terminals:
```
[make clean &&] make py-artifacts sai TARGET=pymodel saithrift-server docker-saithrift-client pymodel   # console 1
make run-saithrift-server             # console 2
make run-saithrift-client-ptftests   # console 3
```

![dev-workflow-pymodel-saithrift](images/dev-workflow-pymodel-saithrift.svg)

## Use-Case III - Incremental Test-Case Development
This builds upon the previous use-case.

Once you have stable Python model code, `libsai` and a saithrift client/server framework, you can start the Python model and sai-thrift server, then develop test-cases interactively. The figure above illustrates this process in the lower-right corner. You can edit and save saithrift PTF tests in your host PC's workspace; save the files; then run selected, or all tests, interactively from inside the saithrift-client container. See [Developer: Run tests selectively from `bash` inside saithrift-client container](README-saithrift.md#developer-run-tests-selectively-from-bash-inside-saithrift-client-container) for details.

# Make Target Summary
The tables below summarize the most important `make` targets for the Python model for easy reference. You can click on a link to jump to further explanations. Not all make targets are shown. See the [Makefile](Makefile) to learn more.

Dockerfile build targets are separately described in [README-dash-docker](README-dash-docker.md) since they are mainly for infrastructure and generally not part of day-to-day code and test-case development. The one exception is the [docker-saithrift-client](#build-saithrift-client-docker-image) target.

## Make "ALL" Targets
| Target(s)              | Description                                                                  |
| ---------------------- | --------------------------------------------------|
| [clean](#cleanup)      | Deletes built artifacts and restores distro directories to clean state                    |
| [kill-all](#stop-containers)             | Stops all running containers                      |

## Build Artifacts
| Target(s)              | Description                                                                  |
| ---------------------- | --------------------------------------------------|
| [py-artifacts](#generate-python-model-artifacts)<br>[py-artifacts-clean](#generate-python-model-artifacts)| Generates P4Info `.json` and `.txt` files from Python model code<br>Delete py-model artifacts |
| [sai TARGET=pymodel](#build-libsaiso-adaptor-library)<br>[sai-clean](#build-libsaiso-adaptor-library)| Auto-generate sai headers, sai adaptor code and compile into `libsai.so` library<br>Cleans up artifacts and restores SAI submodule |
| [saithrift-server](#build-saithrift-server) | Auto-generate the saithrift client-server framework and libraries |
| [docker-saithrift-client](#build-saithrift-client-docker-image) | Build a docker image containing tools, libraries and saithrift test-cases for PTF

## Launch Daemons/Containers
| Target(s)              | Description                                                                  |
| ---------------------- | --------------------------------------------------|
| [pymodel](#run-python-model)<br>[kill-pymodel](#run-python-model) | Run the Python model packet sniffer<br>Stop the Python model process |
| [run-saithrift-server](#run-saithrift-server)<br>[kill-saithrift-server](#run-saithrift-server) | Run a saithrift server which translates SAI over thrift into P4Runtime<br>Stop the saithrift server container|

## Run Tests
| Target(s)              | Description                                                                  |
| ---------------------- | --------------------------------------------------|
| [run-saithrift-ptftests](#run-saithrift-client-ptf-tests) | Run PTF tests under [test/test-cases/functional](../test/test-cases/functional) using tests built into [docker-saithrift-client](#build-saithrift-client-docker-image) image
| [run-saithrift-dev-ptftests](#run-saithrift-client-dev-ptf-tests) | Run PTF tests from host directory [test/test-cases/functional](../test/test-cases/functional) instead of tests built into the `saithrift-client` container for faster test-case development code/test cycles.

# Detailed Python Model Build Workflow

This explains the various build steps for the Python model in more details. The CI pipeline does most of these steps as well. All filenames and directories mentioned in the sections below are relative to the `dash-pipeline` directory (containing this README) unless otherwise specified.

The workflows described here are primarily driven by a [Makefile](Makefile) and are suitable for a variety of use-cases:
* Manual execution by developers - edit, build, test; commit and push to GitHub
* Automated script-based execution in a development or production environment, e.g. regression testing
* Cloud-based CI (Continuous Integration) build and test, every time code is pushed to GitHub or a Pull Request is submitted to the upstream repository.

See the [Diagram](#build-workflow-diagram) below. You can read the [dockerfiles](dockerfiles) and all `Makefiles` in various directories to get a deeper understanding of the build process. You generally use the targets from the main [Makefile](Makefile) and not any subordinate ones.

## Docker Image(s)
>**NOTE** Python model developers generally **don't** need to build Docker images; they are pulled automatically, on-demand, from a registry. Developers who create and maintain the Docker images **do** need to build and push new images.

Several docker images are used to compile artifacts or run processes. These Dockerfiles should not change often and are stored/retrieved from an external docker registry. See [README-dash.docker](README-dash.docker.md) for details. When a Dockerfile does change, it needs to be published in the registry. Dockerfile changes also trigger rebuilds of the docker images in the CI pipeline.

See the diagram below. You can read the [Dockerfile](Dockerfile) and all `Makefiles` to get a deeper understanding of the build process.

## Build Workflow Diagram

![dash-pymodel-thrift-workflow](images/dash-pymodel-thrift-workflow.svg)

## Make Py-Artifacts
This make target will generate artifacts from the Python model:
* Generate P4Info JSON and text files from Python model code
* These artifacts can be used to auto-generate DASH SAI API header files
* Compile `libsai` for dash including SAI-to-P4Runtime adaptor
* Auto-generate the saithrift server and client framework (server daemon + client libraries) based on the DASH SAI headers
* Build a saithrift-client Docker image containing all needed tools and test suites

```
make py-artifacts
```

## Cleanup
This will delete all built artifacts, restore the SAI submodule and kill all running containers.
```
make clean
```

## Stop Containers
This will kill one or all containers:
```
pkill -f main_dash.py           # stop the Python model
make kill-saithrift-server       # stop the RPC server
make kill-all                    # all of the above
```

## Generate Python Model Artifacts
```
make py-artifacts-clean # optional
make py-artifacts
```

The primary outputs of interest are:
 * `py_model/dash_pipeline.py_model/dash_pipeline_p4rt.json` - the P4Info metadata which describes all the P4 entities (P4 tables, counters, etc.). This metadata is used downstream as follows:
    * P4Runtime controller used to manage the pipeline. The SAI API adaptor converts SAI library "c" code calls to P4Runtime socket calls.
    * P4-to-SAI header code generation (see next step below)
 * `py_model/dash_pipeline.py_model/dash_pipeline_p4rt.txt` - text-based P4Info format
 * `py_model/dash_pipeline.py_model/dash_pipeline_ir.json` - intermediate representation JSON

## Build libsai.so adaptor library
This library is the crucial item to allow integration with a Network Operating System (NOS) like SONiC. It wraps an implementation specific "SDK" with standard Switch Abstraction Interface (SAI) APIs. In this case, an adaptor translates SAI API table/attribute CRUD operations into equivalent P4Runtime RPC calls, which is the native RPC API for the Python model's gRPC server.

```
make sai-headers TARGET=pymodel     # Auto-generate headers & adaptor code
make libsai TARGET=pymodel          # Compile into libsai.so
make sai TARGET=pymodel             # Combines steps above
make sai-clean                      # Clean up artifacts and Git Submodule
```

These targets generate SAI headers from the P4Info which was described above. It uses [Jinja2](https://jinja.palletsprojects.com/en/3.1.x/) which renders [SAI/templates](SAI/templates) into C++ source code for the SAI headers corresponding to the DASH API as defined in the Python model code. It then compiles this code into a shared library `libsai.so` which will later be used to link to a test server (Thrift) or `syncd` daemon for production.

This consists of two main steps
* Generate the SAI headers and implementation code via [SAI/sai_api_gen.py](SAI/sai_api_gen.py). This uses templates stored in [SAI/templates](SAI/templates).

  Headers are emitted into the imported `SAI` submodule (under `SAI/SAI`) under its `inc`, `meta` and `experimental` directories.

  Implementation code for each SAI accessor are emitted into the `SAI/lib` directory.
* Compile the implementation source code into `libsai.so`, providing the definitive DASH data plane API. Note this `libsai` makes calls to the Python model's embedded P4Runtime Server and must be linked with numerous libraries.

## Build saithrift-server
This builds a saithrift-server daemon, which is linked to the `libsai` library and also includes the SAI-to-P4Runtime adaptor. It also builds Python thrift libraries and saithrift libraries.
```
make saithrift-server
```

## Create veth pairs for py_model
This needs to be run just once. It will create veth pairs, set their MTU, disable IPV6, etc.

```
make network
```

You can delete the veth pairs when you're done testing via this command:
```
make network-clean
```

## Run Python Model
This will run the Python model packet sniffer in the foreground. The main process is `main_dash.py` which includes an embedded P4Runtime gRPC server (listening on port 9559) and uses scapy to sniff packets on configured interfaces. This will spew out verbose content when control APIs are called or packets are processed. Use additional terminals to run other test scripts.

>**NOTE:** Stop the process (CTRL-c) to shut down the Python model. You can also invoke `pkill -f main_dash.py` from another terminal or script.

```
make pymodel HAVE_DPAPP=y   # launches Python model with packet sniffer
```

## Run saithrift-server
>**Note:** the Python model must be running, see [Run Python Model](#run-python-model)

When this server is launched, it will establish a P4Runtime session (behind the scenes) to the running Python model. The thrift server listens on port `9092` for Thrift messages carrying SAI rpc commands. These commands are dispatched to the SAI library handlers. These handlers translate them into corresponding P4Runtime RPC commands and are sent to the Python model daemon onto a socket at standard P4Runtime port `9559`.

```
make run-saithrift-server
```

When the server starts, the first SAI command it receives will load the `libsai.so` shared library and establish a P4Runtime connection. This results in a console message similar to below. Note this message doesn't necessarily appear when the daemon starts. This also loads the Python model with the P4Info (JSON file), see [Initialize Python Model](#initialize-python-model).

```
Server listening on 0.0.0.0:9559
```

To stop it:
```
make kill-saithrift-server
```

## Build saithrift-client docker image
```
make docker-saithrift-client
```

This will build a docker image which has all libraries needed to talk to the saithrift-server daemon, including:
* saithrift client libraries (Python)
* PTF framework from [OCP SAI repo](https://github.com/opencomputeproject/SAI.git), including all test cases
* The [PTF repo](https://github.com/p4lang/ptf) imported from p4lang
* Scapy etc.

It also contains all the artifacts under `tests/` which includes PTF test-cases. Thus, it comprises a self-contained test resource with tools, libraries and test scripts.

## Run saithrift-client PTF tests
To run all PTF tests which use the saithrift interface, execute the following. You must have the Python model and saithrift-server running.

```
make run-saithrift-ptftests
```

This will launch a saithrift-client docker container and execute tests under `test/test-cases/functional`.

## Run saithrift-client "Dev" PTF tests
You can also run "dev" versions of tests using the following make target. This uses test scripts mounted from the host's file system, allowing a faster development workflow. No dockers need to be rebuilt to try out test cases iteratively.

```
make run-saithrift-client-dev-ptftests    # run PTF tests from host mount
```

This provides a faster development cycle where you can edit PTF test cases on your host machine and immediately run them without rebuilding the docker image.
