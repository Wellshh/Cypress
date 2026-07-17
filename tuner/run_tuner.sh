# SPDX-FileCopyrightText: Copyright (c) 2022 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# example use: sh run_tuner.sh 0 0 \"\" ariane.aux ariane \"\" 10 4 0.1 0.1 32 tunerLog
# Multi-GPU example: sh run_tuner.sh 1 0 cfg.json design.aux \"\" \"\" 100 8 0 0 10 ./tuner ./logs 0-7
#
# Arguments:
#   1  gpu          : 1=enable GPU, 0=CPU only
#   2  multiobj     : 1=MOBOHB multi-objective, 0=BOHB single-objective
#   3  cfg          : ConfigSpace search config JSON
#   4  aux          : Benchmark .aux file
#   5  base_ppa     : Base PPA for comparison (or \"\")
#   6  reuse_params : Reuse params (or \"\")
#   7  iterations   : BOHB iterations
#   8  workers      : Number of parallel workers (recommend <= num_gpus)
#   9  d_ratio      : Density cost ratio
#   10 c_ratio      : Congestion cost ratio
#   11 m_points     : Min points in model
#   12 script_dir   : Tuner script directory
#   13 log_dir      : Log output directory
#   14 gpu_pool     : (Optional) GPU IDs to use, e.g. \"0,1,2,3\" or \"0-7\". Default: all GPUs.

#!/bin/bash -x

# export PYTHONPATH=/AutoDMP

gpu=${1}
multiobj=${2}
cfg=${3}
aux=${4}
base_ppa=${5}
reuse_params=${6}
iterations=${7}
workers=${8}
d_ratio=${9}
c_ratio=${10}
m_points=${11}
script_dir=${12}
log_dir=${13}
gpu_pool=${14:--1}
auxbase=$(basename $aux .aux)
# script_dir=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "Parameters:" $@
printf "# Parameters: %s\n" "${#@}"
printf "# Workers: %s\n" "${workers}"

# Detect GPUs if in GPU mode
if [ "$gpu" -eq 1 ]; then
    if command -v nvidia-smi &> /dev/null; then
        available_gpus=$(nvidia-smi -L | wc -l)
        echo "Detected $available_gpus GPU(s)"
        if [ "$gpu_pool" != "-1" ]; then
            echo "Using GPU pool: $gpu_pool"
        else
            echo "Using all available GPUs (pool: auto-detect)"
        fi
        if [ "$workers" -gt "$available_gpus" ]; then
            echo "WARNING: workers ($workers) > GPUs ($available_gpus). Multiple workers will share GPUs."
        fi
    else
        echo "WARNING: nvidia-smi not found. GPU mode requested but cannot detect GPUs."
    fi
fi

# kill previous processes
# ps -fA | grep tuner_train | awk '{print $2}' | xargs kill -9 $1

# Array to store PIDs
pids=()

# Launch master process
python3.11 $script_dir/tuner_train.py --multiobj $multiobj --cfgSearchFile $cfg --n_workers $workers --n_iterations $iterations --min_points_in_model $m_points --log_dir $log_dir/$auxbase --run_args aux_input=$aux &
pids+=($!)

# Launch worker processes
for i in $(seq $workers); do
    python3.11 $script_dir/tuner_train.py --multiobj $multiobj --log_dir $log_dir/$auxbase --worker --worker_id $i --run_args aux_input=$aux gpu=$gpu base_ppa=$base_ppa reuse_params=$reuse_params --density_ratio $d_ratio --congestion_ratio $c_ratio --gpu_pool "$gpu_pool" &
    pids+=($!)
done

# Wait for all processes to finish and check for failures
while true; do
    wait -n
    code=$?
    if [ $? -ne 0 ]; then
        echo "A process failed, killing all jobs"
        jobs -p | xargs kill
        exit 1
    fi
    if [ -z "$(jobs -r)" ]; then
        break
    fi
done

# If all processes succeeded
echo "All processes finished successfully"