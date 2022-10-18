#!/usr/bin/env python3

import datetime
import os
import re
import shlex
from sqlite3 import Timestamp
import subprocess
import time
import traceback

def start_envoy(env_path, cfg="envoy.yaml"):
    cmd = f"{env_path} -c {cfg} --concurrency 2"
    p = subprocess.Popen(shlex.split(cmd), bufsize=1024, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert p is not None

    start = time.time()
    # timeout in 5s
    while time.time() - start < 5:
        outs = p.stdout.readline().strip()
        if "starting main dispatch loop" in outs:
            print(outs)
            break
    else:
        assert("Reach a timeout" == None)

    return p

def grep_envoy_pid(envoy_path):
    cmd = "ps aux"
    p = subprocess.run(shlex.split(cmd), check=True, capture_output=True, text=True)

    assert p.stdout is not None
    for proc_info in p.stdout.split("\n"):
        info_wo_empty = [t for t in proc_info.split(" ") if t]
        if len(info_wo_empty) == 0:
            continue

        if info_wo_empty[10].startswith(envoy_path):
            return info_wo_empty[1]

    return 0


def read_proc_status(pid):
    content = ""
    with open(f"/proc/{pid}/status") as f:
        for line in f:
            if line.startswith("Vm"):
                content += line

            if line.startswith("Rss"):
                content += line

            if line.startswith("Threads"):
                content += line
    return content

def write_report(report_path, key, content):
    with open(report_path, 'a') as f:
        line = ""
        line += (f"## {key}")
        line += os.linesep
        line += "```\n"
        line += content
        line += "```\n"
        line += "---"
        line += os.linesep

        print(line)
        f.write(line)
    
def start_envoy_and_collect_vm_info(key, envoy_path, cfg, report_path):
    envoy_proc = None
    try:
        envoy_proc  = start_envoy(envoy_path, cfg)
        assert envoy_proc is not None

        # wait for a second 
        time.sleep(1)

        pid = grep_envoy_pid(envoy_path)
        assert pid != 0
        print(f"envoy-static pid is {pid}")

        vm_content = read_proc_status(pid)
        write_report(report_path, key, vm_content)
    except AssertionError as err:
        traceback.print_exception(err)
        traceback.print_stack()
    finally:
        envoy_proc.kill()
        time.sleep(1)

def calculate_delta(data):
    deltas = []
    prev = 0
    for i, v in enumerate(data):
        if i == 0:
            prev = v
            continue
        
        deltas.append(v - prev)
        prev = v

    return *deltas, sum(deltas) / len(deltas)

def parse_vmdata(line, key):
    m = re.match(f"{key}:\s+(\d+)\s+kB", line)
    assert m is not None
    return int(m.groups()[0])

def parse_threads(line, key):
    m = re.match(f"{key}:\s+(\d+)", line)
    assert m is not None
    return int(m.groups()[0])

def parse_report(report_path):
    memory_info = []
    round = {}
    with open(report_path) as f:
        for line in f:
            if line.startswith("##"):
                m = re.match("## (\S+)_(\d+)_vm", line)
                assert m is not None

                round["vm_name"] = m.groups()[0]
                round["vm_insts"] = m.groups()[1]
            elif line.startswith("VmSize"):
                round["VmSize"] = parse_vmdata(line, "VmSize")
            elif line.startswith("VmRSS"):
                round["VmRSS"] = parse_vmdata(line, "VmRSS")
            elif line.startswith("Threads"):
                round["Threads"] = parse_threads(line, "Threads")
            elif line.startswith("--"):
                memory_info.append(round)
                round = {}
            else:
                pass
    
    return memory_info

def analyze_report_data(report_data):
    def fill_a_line(data, vm, key):
        key_data = [r[key] for r in data]
        key_delta = calculate_delta(key_data)

        result = f"|{vm}|{key}|"
        result += "|".join([str(x) for x in key_data])
        result += "|"
        result += "|".join([str(x) for x in key_delta])
        result += "|"
        result += os.linesep
        return result

    """
    complete customized
    """
    result = "# Summary "
    result += 2 * os.linesep
    result += "Collect from */proc/[pid]/status*"
    result += 2 * os.linesep
    result += "| wasm vm | vm inst amount |1 vm | 2 vms | 3 vms | delta_1 | delta_2 | delta_avg |"
    result += os.linesep
    result += "| -- | -- | -- | -- | -- | -- | -- | -- |"
    result += os.linesep

    #
    # v8
    v8_rounds = [r for r in report_data if r["vm_name"] == "v8"]
    result += fill_a_line(v8_rounds, "v8", "VmSize")
    result += fill_a_line(v8_rounds, "v8", "VmRSS")
    result += fill_a_line(v8_rounds, "v8", "Threads")

    #
    # wamr
    wamr_rounds = [r for r in report_data if r["vm_name"] == "wamr"]
    result += fill_a_line(wamr_rounds, "wamr", "VmSize")
    result += fill_a_line(wamr_rounds, "wamr", "VmRSS")
    result += fill_a_line(wamr_rounds, "wamr", "Threads")

    return result




def main():
    timestamp = datetime.datetime.today().strftime("%Y-%m-%dT%H-%M-%S")
    report_path  = f"report_{timestamp}.md"

    print("Start recording...")

    #
    # v8
    start_envoy_and_collect_vm_info("v8_1_vm", "exe_2_v8/envoy-static", "envoy_v8_1.yaml", report_path)
    start_envoy_and_collect_vm_info("v8_2_vm", "exe_2_v8/envoy-static", "envoy_v8_2.yaml", report_path)
    start_envoy_and_collect_vm_info("v8_3_vm", "exe_2_v8/envoy-static", "envoy_v8_3.yaml", report_path)
    #
    # wamr
    start_envoy_and_collect_vm_info("wamr_1_vm", "exe_3_wamr/envoy-static", "envoy_wamr_1.yaml", report_path)
    start_envoy_and_collect_vm_info("wamr_2_vm", "exe_3_wamr/envoy-static", "envoy_wamr_2.yaml", report_path)
    start_envoy_and_collect_vm_info("wamr_3_vm", "exe_3_wamr/envoy-static", "envoy_wamr_3.yaml", report_path)

    print("Start reporting...")
    report_data = parse_report(report_path)
    report_result = analyze_report_data(report_data)
    print(report_result)

    with open(report_path, "a") as f:
        f.write(os.linesep)
        f.write(report_result)


if __name__ == "__main__":
    main()