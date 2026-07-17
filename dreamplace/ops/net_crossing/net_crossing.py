# Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
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


##
# @file   net_crossing.py
# @author Niansong Zhang
# @date   Jul 2024
# @brief  Compute net crossing
#

import math
import torch
from torch import nn
from torch.autograd import Function

import dreamplace.ops.net_crossing.net_crossing_cpp as net_crossing_cpp
import dreamplace.configure as configure
if configure.compile_configurations["CUDA_FOUND"] == "TRUE":
    import dreamplace.ops.net_crossing.net_crossing_cuda as net_crossing_cuda

import pdb

class NetCrossingFunction(Function):
    @staticmethod
    def forward(ctx, pos, flat_netpin, netpin_start, net_mask, pin_side,
                _lambda, _mu, _sigma, deterministic):
        use_cpu_reference = pos.is_cuda and deterministic
        if use_cpu_reference:
            cpu_args = [
                tensor.detach().cpu().contiguous()
                for tensor in (
                    pos, flat_netpin, netpin_start, net_mask, pin_side,
                    _lambda, _mu, _sigma,
                )
            ]
            output = net_crossing_cpp.forward(*cpu_args)
            output = [tensor.to(pos.device) for tensor in output]
        elif pos.is_cuda:
            output = net_crossing_cuda.forward(pos.view(pos.numel()), flat_netpin, netpin_start, net_mask, pin_side, _lambda, _mu, _sigma)
        else:
            output = net_crossing_cpp.forward(pos.view(pos.numel()), flat_netpin, netpin_start, net_mask, pin_side, _lambda, _mu, _sigma)

        ctx.grad_intermediate = output[1]
        if pos.is_cuda:
            torch.cuda.synchronize()
        return output[0]

    @staticmethod
    def backward(ctx, grad_pos):
        output = ctx.grad_intermediate * grad_pos
        return output, None, None, None, None, None, None, None, None

class NetCrossing(nn.Module):

    def __init__(self,
                flat_netpin=None,
                netpin_start=None,
                net_mask=None,
                pin_side=None,
                _lambda=None,
                _mu=None,
                _sigma=None,
                deterministic=False):
        super(NetCrossing, self).__init__()
        tensors = {
            "flat_netpin": flat_netpin,
            "netpin_start": netpin_start,
            "net_mask": net_mask,
            "pin_side": pin_side,
            "lambda": _lambda,
            "mu": _mu,
            "sigma": _sigma,
        }
        missing = [name for name, tensor in tensors.items() if tensor is None]
        if missing:
            raise ValueError("missing net_crossing tensors: %s" % missing)
        if any(not torch.is_tensor(tensor) for tensor in tensors.values()):
            raise TypeError("all net_crossing inputs must be torch tensors")
        for name in ("flat_netpin", "netpin_start", "net_mask", "pin_side"):
            if tensors[name].dim() != 1:
                raise ValueError("%s must be one-dimensional" % name)
        if netpin_start.numel() < 1:
            raise ValueError("netpin_start must contain at least the terminal offset")
        if flat_netpin.dtype != torch.int32 or netpin_start.dtype != torch.int32:
            raise TypeError("flat_netpin and netpin_start must use int32 storage")
        if net_mask.dtype != torch.uint8:
            raise TypeError("net_mask must use uint8 storage")
        if pin_side.dtype != torch.int32:
            raise TypeError("pin_side must use int32 storage")
        if net_mask.numel() != netpin_start.numel() - 1:
            raise ValueError("net_mask length must match the CSR net count")
        if flat_netpin.numel() != pin_side.numel():
            raise ValueError("flat_netpin must enumerate every pin exactly once")

        starts = netpin_start.detach().cpu()
        if starts[0].item() != 0 or starts[-1].item() != flat_netpin.numel():
            raise ValueError("netpin_start must span the complete flat_netpin array")
        if starts.numel() > 1 and torch.any(starts[1:] < starts[:-1]).item():
            raise ValueError("netpin_start must be monotonically non-decreasing")
        if flat_netpin.numel():
            pins = flat_netpin.detach().cpu()
            if pins.min().item() < 0 or pins.max().item() >= pin_side.numel():
                raise ValueError("flat_netpin contains an out-of-range pin ID")

        devices = {tensor.device for tensor in tensors.values()}
        if len(devices) != 1:
            raise ValueError("all net_crossing tensors must be on the same device")
        scalar_parameters = (_lambda, _mu, _sigma)
        if any(parameter.numel() != 1 for parameter in scalar_parameters):
            raise ValueError("lambda, mu, and sigma must be scalar tensors")
        if len({parameter.dtype for parameter in scalar_parameters}) != 1:
            raise TypeError("lambda, mu, and sigma must use the same dtype")
        
        self.flat_netpin = flat_netpin
        self.netpin_start = netpin_start
        self.net_mask = net_mask
        self.pin_side = pin_side
        self._lambda = _lambda
        self._mu = _mu
        self._sigma = _sigma
        self.deterministic = bool(deterministic)

    def forward(self, pos):
        expected_coordinates = 2 * self.pin_side.numel()
        if pos.numel() != expected_coordinates:
            raise ValueError(
                "net_crossing received %d coordinates for %d pins; expected %d"
                % (pos.numel(), self.pin_side.numel(), expected_coordinates)
            )
        if pos.device != self.pin_side.device:
            raise ValueError("position and net_crossing metadata must share a device")
        if pos.dtype != self._lambda.dtype:
            raise TypeError("position and net_crossing parameters must share a dtype")
        if pos.dtype not in (torch.float32, torch.float64):
            raise TypeError("net_crossing supports only float32 and float64")
        if not self.net_mask.numel():
            return pos.sum() * 0
        return NetCrossingFunction.apply(
            pos.contiguous().view(-1), self.flat_netpin, self.netpin_start,
            self.net_mask, self.pin_side,
            self._lambda, self._mu, self._sigma, self.deterministic)
