# envoy_wasm_vm_memory_consumption
Collect memory consumption of variant Wasm VMs in Envoy

## Steps

```
$ pwd
/workspaces/envoy

$ cat user.bazelrc
build --define wasm=wamr
#build --define wasm=wasmtime
#build --define wasm=wavm

$ ./ci/run_envoy_docker.sh './ci/do_ci.sh bazel.release.server_only'

$ cp -r linux/amd64/build_envoy_release_stripped/envoy exe_2_v8/envoy-static
# or
$ cp -r linux/amd64/build_envoy_release_stripped/envoy exe_3_wamr/envoy-static

$ python3 run.py

```
