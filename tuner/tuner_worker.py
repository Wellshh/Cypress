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

from dataclasses import make_dataclass, fields, asdict
from operator import itemgetter
import os
import hashlib
import json
import math
import platform
import subprocess
from pathlib import Path
import logging
import numpy as np
import torch
import ConfigSpace as CS
import ConfigSpace.hyperparameters as CSH
from ConfigSpace.read_and_write import json as CS_JSON

from hpbandster.core.worker import Worker
from dreamplace.Placer import PlacementEngine

from tuner.tuner_configs import (
    AUTODMP_BASE_CONFIG,
    AUTODMP_BASE_PPA,
    AUTODMP_BAD_RATIO,
    AUTODMP_BEST_CFG,
)

opj = os.path.join


def _sanitize_config(config):
    """Convert numpy types in config dict to native Python types for JSON/Pyro4 serialization."""
    sanitized = {}
    for k, v in config.items():
        if isinstance(v, np.integer):
            sanitized[k] = int(v)
        elif isinstance(v, np.floating):
            sanitized[k] = float(v)
        elif isinstance(v, np.ndarray):
            sanitized[k] = v.tolist()
        elif isinstance(v, np.bool_):
            sanitized[k] = bool(v)
        elif isinstance(v, np.str_):
            sanitized[k] = str(v)
        else:
            sanitized[k] = v
    return sanitized


# Wrap AutoDMP config in dataclass
def update_cfg(self, cfg):
    my_fields = [f.name for f in fields(self)]
    for p, v in cfg.items():
        if p in my_fields:
            setattr(self, p, type(getattr(self, p))(v))
        elif "GP_" in p:
            p = p.replace("GP_", "")
            gp = self.global_place_stages[0]
            if p in gp:
                gp[p] = type(gp[p])(v)


AutoDMPConfig = make_dataclass(
    "AutoDMPConfig", AUTODMP_BASE_CONFIG, namespace={"update_cfg": update_cfg}
)


class AutoDMPWorker(Worker):
    def __init__(
        self,
        log_dir,
        *args,
        default_config,
        congestion_ratio,
        density_ratio,
        multiobj=False,
        study_seed=0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.log_dir = log_dir
        self.congestion_ratio = congestion_ratio
        self.density_ratio = density_ratio
        self.multiobj = multiobj
        self.study_seed = int(study_seed)
        self.runtime_metadata = self._get_runtime_metadata()

        # update default with best parameters
        reuse_params = default_config.get("reuse_params", "")
        path_reuse = Path(str(reuse_params))
        if path_reuse.suffix == ".json" and path_reuse.is_file():
            with path_reuse.open() as f:
                best_params = json.load(f)
        else:
            best_params = AUTODMP_BEST_CFG.get(reuse_params, {})
        print("Reusing best parameters:", best_params)
        self.default_config = {**best_params, **default_config}

        # setup PPA reference
        base_ppa = default_config["base_ppa"]
        path_ppa = Path(str(base_ppa))
        if isinstance(base_ppa, dict):
            self.base_ppa = base_ppa
        elif path_ppa.suffix == ".json" and path_ppa.is_file():
            with path_ppa.open() as f:
                self.base_ppa = json.load(f)
        else:
            self.base_ppa = AUTODMP_BASE_PPA[base_ppa]
        print("PPA reference:", self.base_ppa)
        self.bad_run = {
            k: float(v * AUTODMP_BAD_RATIO) for k, v in self.base_ppa.items()
        }

    def _create_params(self, config):
        params = AutoDMPConfig(**AUTODMP_BASE_CONFIG)
        params.update_cfg(self.default_config)
        params.update_cfg(config)
        return asdict(params)

    def _seed_for_replicate(self, replicate_id):
        payload = f"{self.study_seed}:{replicate_id}".encode("ascii")
        return int.from_bytes(hashlib.sha256(payload).digest()[:4], "little") & 0x7FFFFFFF

    @staticmethod
    def _get_runtime_metadata():
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            commit = "unknown"
        gpu_name = None
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(torch.cuda.current_device())
        return {
            "commit": commit,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "torch": torch.__version__,
            "torch_cuda": torch.version.cuda,
            "gpu": gpu_name,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        }

    @staticmethod
    def _result_is_valid(result):
        required = ("rsmt", "congestion", "density", "net_crossing", "hpwl")
        return all(math.isfinite(float(result.get(key, float("inf")))) for key in required)

    def _normalized_metrics(self, result):
        ppa = result if self._result_is_valid(result) else self.bad_run
        return {
            "rsmt": ppa["rsmt"] / self.base_ppa["rsmt"],
            "congestion": ppa["congestion"] / self.base_ppa["congestion"],
            "density": ppa["density"] / self.base_ppa["density"],
            "net_crossing": ppa.get("net_crossing", float("inf")),
            "hpwl": ppa["hpwl"] / self.base_ppa["hpwl"],
        }

    def _scalar_cost(self, metrics):
        return float(
            metrics["rsmt"]
            + self.congestion_ratio * metrics["congestion"]
            + self.density_ratio * metrics["density"]
            + metrics["net_crossing"] * 1e-3
            + metrics["hpwl"]
        )

    def _update_logger(self, working_directory, suffix=""):
        # change logger
        log = logging.getLogger()
        filehandler = logging.FileHandler(
            opj(working_directory, f"AutoDMP{suffix}.log"), "w"
        )
        formatter = logging.Formatter("[%(levelname)-7s] %(name)s - %(message)s")
        filehandler.setFormatter(formatter)
        log = logging.getLogger()
        for hdlr in log.handlers[:]:  # remove existing file handler
            if isinstance(hdlr, logging.FileHandler):
                log.removeHandler(hdlr)
        log.addHandler(filehandler)
        log.setLevel(logging.DEBUG)

    def compute(self, config_id, config, budget, working_directory, **kwargs):
        print("WORKER compute: starting job %s" % str(config_id))
        config = _sanitize_config(config)
        config_identifier = "run-" + "_".join([str(x) for x in config_id])
        replicate_count = max(1, int(math.ceil(float(budget))))
        run_directory = opj(
            self.log_dir, config_identifier, f"budget-{replicate_count}"
        )
        os.makedirs(run_directory, exist_ok=True)

        results = []
        seeds = []
        for replicate_id in range(replicate_count):
            seed = self._seed_for_replicate(replicate_id)
            seeds.append(seed)
            replicate_directory = opj(run_directory, f"seed-{seed}")
            os.makedirs(replicate_directory, exist_ok=True)
            self._update_logger(replicate_directory, suffix=f"-seed-{seed}")

            replicate_config = dict(config)
            replicate_config["random_seed"] = seed
            replicate_config["result_dir"] = replicate_directory
            params = self._create_params(replicate_config)
            placer = PlacementEngine(params)
            placer.params.dump(opj(replicate_directory, "parameters.json"))
            with open(opj(replicate_directory, "run_metadata.json"), "w") as stream:
                json.dump(
                    {
                        **self.runtime_metadata,
                        "study_seed": self.study_seed,
                        "evaluation_seed": seed,
                        "replicate_id": replicate_id,
                        "budget": replicate_count,
                        "config_id": list(config_id),
                    },
                    stream,
                    indent=2,
                )

            try:
                result = placer.run()
            except Exception as error:
                logging.exception("Error during search: %s", error)
                result = {
                    "rsmt": float("inf"),
                    "congestion": float("inf"),
                    "density": float("inf"),
                    "net_crossing": float("inf"),
                    "hpwl": float("inf"),
                }
            results.append(result)

        normalized = [self._normalized_metrics(result) for result in results]
        normalized_aggregate = {
            key: float(np.median([metrics[key] for metrics in normalized]))
            for key in normalized[0]
        }
        scored_results = [
            result if self._result_is_valid(result) else self.bad_run
            for result in results
        ]
        aggregate = {
            key: float(np.median([result[key] for result in scored_results]))
            for key in ("rsmt", "congestion", "density", "net_crossing", "hpwl")
        }
        failure_rate = float(
            np.mean([not self._result_is_valid(result) for result in results])
        )

        if self.multiobj:
            return {
                "loss": tuple(normalized_aggregate[key] for key in (
                    "rsmt", "congestion", "density", "net_crossing", "hpwl"
                )),
                "info": {
                    "aggregate": aggregate,
                    "normalized_aggregate": normalized_aggregate,
                    "replicates": results,
                    "seeds": seeds,
                    "failure_rate": failure_rate,
                },
            }
        else:
            costs = np.asarray([self._scalar_cost(metrics) for metrics in normalized])
            median_cost = float(np.median(costs))
            cost_iqr = float(np.percentile(costs, 75) - np.percentile(costs, 25))
            cost = median_cost + 0.25 * cost_iqr
            return {
                "loss": float(cost),
                "info": {
                    "aggregate": aggregate,
                    "normalized_aggregate": normalized_aggregate,
                    "replicates": results,
                    "seeds": seeds,
                    "failure_rate": failure_rate,
                    "median_cost": median_cost,
                    "cost_iqr": cost_iqr,
                },
            }

    @staticmethod
    def get_configspace(config_file: str, seed=None):
        # read JSON config if provided
        if os.path.isfile(config_file):
            with open(config_file, "r") as f:
                cs = CS_JSON.read(f.read())
                if seed is not None:
                    cs.seed(seed)
            return cs

        # otherwise, setup default config space
        cs = CS.ConfigurationSpace(seed=seed)

        init_x = CSH.UniformFloatHyperparameter(
            "init_loc_perc_x", lower=0.2, upper=0.8, default_value=0.5
        )
        init_y = CSH.UniformFloatHyperparameter(
            "init_loc_perc_y", lower=0.2, upper=0.8, default_value=0.5
        )
        td = CSH.UniformFloatHyperparameter(
            "target_density", lower=0.50, upper=0.80, default_value=0.70
        )
        dw = CSH.UniformFloatHyperparameter(
            "density_weight", lower=1e-6, upper=1e-0, default_value=8e-3, log=True
        )
        halox = CSH.UniformIntegerHyperparameter(
            "macro_halo_x",
            lower=4000,
            upper=8000,
            default_value=5000,
            log=True,
        )
        haloy = CSH.UniformIntegerHyperparameter(
            "macro_halo_y",
            lower=4000,
            upper=8000,
            default_value=5000,
            log=True,
        )
        ovflow = CSH.UniformFloatHyperparameter(
            "stop_overflow", lower=0.06, upper=0.10, default_value=0.07
        )
        gamma = CSH.UniformFloatHyperparameter(
            "gamma", lower=0.10, upper=0.50, default_value=0.1318231577
        )
        lr = CSH.UniformFloatHyperparameter(
            "GP_learning_rate", lower=1e-4, upper=1e-2, default_value=2.5e-4
        )
        lr_decay = CSH.UniformFloatHyperparameter(
            "GP_learning_rate_decay", lower=0.99, upper=1.0, default_value=1.0
        )
        optimizer = CSH.CategoricalHyperparameter(
            "GP_optimizer", ["adam", "nesterov"], default_value="nesterov"
        )
        nbinx = CSH.CategoricalHyperparameter(
            "GP_num_bins_x", [256, 512, 1024, 2048], default_value=512
        )
        nbiny = CSH.CategoricalHyperparameter(
            "GP_num_bins_y", [256, 512, 1024, 2048], default_value=512
        )
        wl = CSH.CategoricalHyperparameter(
            "GP_wirelength",
            ["weighted_average", "logsumexp"],
            default_value="weighted_average",
        )
        llambda = CSH.UniformIntegerHyperparameter(
            "GP_Llambda_density_weight_iteration",
            lower=1,
            upper=3,
            default_value=1,
        )
        lsub = CSH.UniformIntegerHyperparameter(
            "GP_Lsub_iteration",
            lower=1,
            upper=3,
            default_value=1,
        )
        replace_wl = CSH.UniformIntegerHyperparameter(
            "RePlAce_ref_hpwl", lower=150000, upper=550000, default_value=350000
        )
        replace_low = CSH.UniformFloatHyperparameter(
            "RePlAce_LOWER_PCOF", lower=0.90, upper=0.99, default_value=0.95
        )
        replace_up = CSH.UniformFloatHyperparameter(
            "RePlAce_UPPER_PCOF", lower=1.02, upper=1.15, default_value=1.05
        )
        pd = CSH.UniformFloatHyperparameter(
            "pin_density", lower=0.1, upper=0.5, default_value=0.5
        )
        risa = CSH.CategoricalHyperparameter("risa_weights", [0, 1], default_value=0)

        hyperparameters = {
            "all": [
                init_x,
                init_y,
                td,
                dw,
                halox,
                haloy,
                # ovflow,
                gamma,
                lr,
                lr_decay,
                optimizer,
                nbinx,
                nbiny,
                wl,
                # llambda,
                # lsub,
                replace_wl,
                replace_low,
                replace_up,
                # pd,
                risa,
            ],
            "refine": [init_x, init_y, td, dw, halox, haloy],
            "refine_fixed_macros": [init_x, init_y, td, dw],
            "optimizer": [gamma, lr, lr_decay, optimizer, nbinx, nbiny, wl],
            "RePlace": [replace_wl, replace_low, replace_up],
        }

        modes = ["all"]
        selected = itemgetter(*modes)(hyperparameters)
        if len(modes) > 1:
            selected = [parameter for mode in selected for parameter in mode]
        unique_parameters = list(dict.fromkeys(parameter.name for parameter in selected))
        parameters_by_name = {parameter.name: parameter for parameter in selected}
        cs.add([parameters_by_name[name] for name in unique_parameters])

        return cs
