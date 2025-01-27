#  Copyright 2023 ByteDance Ltd. and/or its affiliates.
#
#  Licensed to the Apache Software Foundation (ASF) under one
#  or more contributor license agreements.  See the NOTICE file
#  distributed with this work for additional information
#  regarding copyright ownership.  The ASF licenses this file
#  to you under the Apache License, Version 2.0 (the
#  "License"); you may not use this file except in compliance
#  with the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing,
#  software distributed under the License is distributed on an
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#  KIND, either express or implied.  See the License for the
#  specific language governing permissions and limitations
#  under the License.
import unittest

import sympy

from matx.kernel.kernel_parser import KernelParser
from matx.kernel.typing import int32, float32


class TestForLoopParser(unittest.TestCase):
    def test_scalar_op1(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    k: int32 = i + j
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_scalar_op2(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int32[M, N]:
            k: int32 = 0
            for i in range(M):
                for j in range(N):
                    k = i + j
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_idx_operation1(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int32[M, N]:
            k: int32 = 0
            for i in range(M):
                for j in range(N):
                    k = a[(i + 1) // 2, j] + j
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_idx_operation2(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int32[M, N]:
            k: int32 = 0
            for i in range(M):
                for j in range(N):
                    a[(i + 1) / 2, j] = i + j
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_idx_operation3(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int32[M, N]:
            k: int32 = 0
            for i in range(M):
                for j in range(N):
                    m: int32 = i * j
                    k = a[m // (i + j + 1), j] + j
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_scalar_rhs_nd1(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N], b: int32[M, N]) -> int32[M, N]:
            k: int32 = 0
            for i in range(M):
                for j in range(N):
                    k = a[i, j] + b[i, j]
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_scalar_rhs_nd2(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N], b: int32[M, N]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    k: int32 = a[i, j] + 1
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_scalar_both_nd(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N], b: int32[M, N]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    b[i, j] = a[i, j] + 1
            return b

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_scalar_both_nd_different_type(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N], b: float32[M, N]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    b[i, j] = a[i, j] + b[i, j]
            return b

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_scalar_different_type_many_nd(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N], b: float32[M, N], c: int32[N], d: float32[M]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    b[i, j] = (a[i, j] + c[j]) / (b[i, j] * d[i])
            return b

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_scalar_op_on_idx(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N], b: float32[2 * M, N], c: int32[N], d: float32[M]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    b[i + 1, j] = (a[i, j] + c[j]) / (b[i, j] * d[i])
            return b

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_symbol_expression_range(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N], b: float32[2 * M, N], c: int32[N], d: float32[M]) -> int32[M, N]:
            for i in range(2, M // 2, 2):
                for j in range(N - 10, N - 1, 1):
                    b[i + 1, j] = (a[i, j] + c[j]) / (b[i, j] * d[i])
            return b

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_basic_if_block(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    if i + j > 10:
                        k: int32 = i
                    else:
                        k: int32 = j
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_basic_if_block_nd_condition(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(a: int32[M, N]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    if a[i, j] % 2 == 1:
                        k: int32 = i
                    else:
                        k: int32 = j
            return a

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure

    def test_if_block_nd_body(self):
        M = sympy.Symbol('M', positive=True)
        N = sympy.Symbol('N', positive=True)

        def foo(A: int32[M, N], B: int32[M, N]) -> int32[M, N]:
            for i in range(M):
                for j in range(N):
                    if i % 2 == 0:
                        B[i, j] = A[i, j]
                    else:
                        B[i, j] = A[i + 1, j]
            return B

        p = KernelParser(foo)
        p.parse()
        # todo check ir structure
