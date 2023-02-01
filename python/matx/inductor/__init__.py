# Copyright 2022 ByteDance Ltd. and/or its affiliates.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import inspect
from typing import List

import torch

from matx.env import MATX_DEV_MODE
from matx.script import context
from matx.toolchain import path_prefix
from matx.torch_compiler.codegen import extract_inductor_code, matx_cpp_code_format


def from_source(compiling_obj: type, example_inputs: List[torch.Tensor]) -> context.ScriptContext:
    try:
        # set sc_ctx attributes to be compatible with existing matx code
        sc_ctx = context.ScriptContext()
        sc_ctx.build_type = context.BuildType.FUNCTION
        sc_ctx.main_node.raw = compiling_obj
        inductor_context = context.InductorContext(fn_name=compiling_obj.__name__)
        sc_ctx.main_node.context = inductor_context
        # set source code TODO: formatting source code
        sc_ctx.main_node.span.source_code = inspect.getsource(compiling_obj)
        # set filename. TODO: this is too hack
        frame = inspect.stack()[3]
        sc_ctx.main_node.span.file_name = frame[0].f_code.co_filename

        # set args types.
        from .. import ir

        # TODO: currently, we only support argument as NDArray. We may support nested inputs later
        signature = inspect.signature(compiling_obj)
        for param in signature.parameters.values():
            sc_ctx.main_node.context.arg_types[param.name] = ir.type.NDArrayType()

        # compile the kernel and set the code
        code, kernel_name, fake_output = extract_inductor_code(compiling_obj, example_inputs)
        code = matx_cpp_code_format(code, kernel_name, example_inputs, fake_output)

        # export code
        path = path_prefix(sc_ctx)
        with open(path, 'w') as f:
            f.write(code)

        # set rt_module
        from .. import _ffi
        build_module = _ffi.get_global_func("embedded.build.c")
        sc_ctx.rt_module = build_module(code.encode())

        return sc_ctx
    except BaseException as e:
        if MATX_DEV_MODE:
            raise
        else:
            raise Exception(str(e)) from None
