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

import ast
import inspect
import numbers
from typing import Any, List

from .ops import OpRegistry
from .symbol import is_symbol
from .. import ir as _ir
from ..ir import type_inference as _type_infer
from ..ir import type_relation as _type_rel
from ..ir.tensor_stmt import decl_buffer
from ..script import analysis
from ..script import context


def parse_ast(func):
    src_code = inspect.getsource(func)
    src_file_path = inspect.getfile(func)
    source_file_content, src_line_number = inspect.findsource(func)
    src_ast = ast.parse(src_code)
    ast.increment_lineno(src_ast, src_line_number)

    return src_ast, src_file_path, src_line_number, src_code


def extract_symbol_from_type(t):
    shape = t.shape
    symbols = set([dim for dim in shape if is_symbol(dim)])
    return {str(s): s for s in symbols}


def ndarrayType_to_ndarray(t):
    from ..ir.type import NDArrayType
    return NDArrayType()


class KernelParser:

    def __init__(self, func):
        self.func = func
        self.func_name = func.__name__
        self.file_name = inspect.getfile(func)
        # get args
        self.signature = inspect.signature(func)
        self.args = {k: v.annotation for k, v in self.signature.parameters.items()}
        # get return type
        self.return_types = self.signature.return_annotation
        # get shape symbols in dict like {'x':X}
        self.symbols = dict()
        for arg_type in self.args.values():
            shape_symbol = extract_symbol_from_type(arg_type)
            self.symbols.update(shape_symbol)

    def parse2(self):
        sc_ctx = context.ScriptContext()
        sc_ctx.main_node.raw = self.func

        dep_anls = analysis.DepsAnalysis()
        src_anls = analysis.SourceAnalysis()
        mdo_anls = analysis.ModuleAnalysis()
        src_anls.run(sc_ctx)
        mdo_anls.run(sc_ctx)

        while dep_anls.run(sc_ctx):
            src_anls.run(sc_ctx)
            mdo_anls.run(sc_ctx)

        fn_context = context.FunctionContext()
        # todo support default args
        fn_context.arg_defaults = []
        fn_context.arg_names = list(self.args.keys())
        # todo support args_reassigns
        fn_context.arg_reassigns = {k: False for k in self.args.keys()}
        # todo support types other than ndarry
        fn_context.arg_types = {k: ndarrayType_to_ndarray(v) for k, v in self.args.items()}
        fn_context.fn_name = self.func_name
        # context.fn_type = None
        fn_context.is_abstract = False
        fn_context.return_type = ndarrayType_to_ndarray(self.return_types)
        fn_context.unbound_name = self.func_name
        sc_ctx.main_node.context = fn_context

        sc_ctx.main_node.ir_schema = _ir.FuncType(
            list(fn_context.arg_types.values()), fn_context.return_type)

        def parser_node(node: context.ASTNode):
            node.ir = KernelNodeVisitor(self, node, sc_ctx).visit(node.ast)
            print(node.ir)

        parser_node(sc_ctx.main_node)


class NDArrayContext:
    def __init__(self, name, type_, span):
        self.name = name
        self.type = type_
        self.ndarray_var = None
        self.data_var = None
        self.buffer = None


class KernelNodeVisitor(ast.NodeVisitor):
    def __init__(
            self,
            kernel_p: KernelParser,
            node: context.ASTNode,
            sc_ctx: context.ScriptContext):
        self.kernel_p = kernel_p
        self.custom_ast_node = node
        self.sc_ctx = sc_ctx
        self.fn_ctx = node.context
        self.context = None
        self.session_handle_var_ctx = []
        self.buffer_table = {}
        self.return_buffer = None

    def build_span(self, node):
        root_span = self.custom_ast_node.span
        abs_lineno = root_span.lineno + node.lineno - 1
        source_code = root_span.source_code

        return _ir.Span(root_span.file_name,
                        abs_lineno,
                        self.custom_ast_node.context.name,
                        source_code)

    def generic_visit(self, node):
        """Override method in ast.NodeVisitor.
        To directly filter out invalidate type of stmt.
        """
        raise NotImplementedError(f'This node is not supported now: {node}')

    def visit(self, node: ast.AST) -> Any:
        """Override method in ast.NodeVisitor"""
        method = "visit_" + node.__class__.__name__
        print(method)
        visitor = getattr(self, method, self.generic_visit)
        visit_res = visitor(node)
        return visit_res

    def parse_body(self, auto_add_return=False):
        body = []
        last_ast = None
        while len(self.context.node_stack[-1]) > 0:
            last_ast = self.context.node_stack[-1].pop()
            res = self.visit(last_ast)
            if res is not None:
                if not isinstance(res, _ir.Stmt):
                    raise SyntaxError('Every IR node here should be a stmt!')
                body.append(res)
            else:
                # ignore the stmt
                pass
        if (auto_add_return
                and (len(body) == 0 or not isinstance(last_ast, ast.Return))):
            body.append(self.visit(ast.Return(value=None)))
        return body

    @staticmethod
    def to_seq_stmt(body: List[_ir.Stmt], span: _ir.Span):
        if body is None or len(body) == 0:
            return _ir.SeqStmt(body, span)
        return _ir.SeqStmt(body, span) if len(body) > 1 else body[0]

    def push_handle_var(self, handle_var):
        self.session_handle_var_ctx.append(handle_var)

    def pop_handle_var(self):
        self.session_handle_var_ctx.pop()

    def declare_shape_var(self, type_annotation):
        pass

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.context = context.ScopeContext()
        self.context.new_scope(nodes=node.body)
        span = self.build_span(node)
        # add parameters of function
        for arg, type_annotation in self.kernel_p.args.items():
            arg_var = _ir.PrimVar(arg, self.kernel_p.args[arg].dtype_str(), span)
            self.context.update_symbol(arg, arg_var)
            self.context.func_params.append(arg_var)
            self.buffer_table[arg] = decl_buffer((10,))

        return_type = decl_buffer((10,))
        self.return_buffer = return_type

        # append session_pointer_var
        pointer_var_name = "handle_2_71828182846"
        pointer_var = _ir.PrimVar(
            pointer_var_name,
            _ir.PrimType("handle")
        )
        self.context.update_symbol(pointer_var_name, pointer_var)
        self.context.func_params.append(pointer_var)

        self.push_handle_var(self.context.func_params[-1])

        body_stmts = self.parse_body(True)

        func = _ir.Function(
            self.context.func_params,
            # [HLOVar(x, ty=ObjectTypeNode), HLOVar(y, ty=ObjectTypeNode), handle_2_71828182846]
            [],  # [_ir.PrimCast("handle", _ir.const(0))],
            self.to_seq_stmt(body_stmts, span),
            # [CallNode(Op(ir.nd_module_add), [HLOVar(x, ty=ObjectTypeNode), HLOVar(y, ty=ObjectTypeNode)], []) -> NDArrayType]
            ret_type=ndarrayType_to_ndarray(return_type),  # NDArray[ndim=?, dtype=?]
            span=span
        )
        self.pop_handle_var()
        self.context.pop_scope()
        return func

    def visit_Constant(self, node: ast.Constant) -> Any:
        if node.value is None:
            return _ir.NoneExpr()
        elif isinstance(node.value, numbers.Number):
            return _ir.const(node.value, _type_infer(node.value).dtype)
        else:
            raise NotImplementedError(f'Unsupported value {node.value}')

    # variables
    def visit_Name(self, node: ast.Name) -> Any:
        name = node.id
        if name in self.kernel_p.symbols:
            return name
        if name in self.kernel_p.args.keys():
            return name
        return node.id

    # Expressions
    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        print("visit_UnaryOp", type(node.op))
        opname = type(node.op).__name__
        operand = self.visit(node.operand)
        operand_t = self._get_type(operand)

        # op_func = OpReplacementRepo

        # todo finish

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        opname = type(node.op).__name__
        lhs = self.visit(node.left)
        rhs = self.visit(node.right)
        lhs_t = self._get_type(lhs)
        rhs_t = self._get_type(rhs)

        op_func = OpRegistry.get_bin_operator(lhs_t, rhs_t, opname)
        return op_func(
            self.context.symbols[0][lhs],
            self.context.symbols[0][rhs],
            self.buffer_table[lhs],
            self.buffer_table[rhs],
            self.return_buffer,
            lhs_t,
            rhs_t)
        # todo insert to ir

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        raise NotImplementedError("visit_BoolOp is not Implemented")

    def visit_Compare(self, node: ast.Compare) -> Any:
        raise NotImplementedError("visit_Compare is not Implemented")

    def visit_Call(self, node: ast.Call) -> Any:
        raise NotImplementedError("visit_Call is not Implemented")

    def visit_keyword(self, node: ast.keyword) -> Any:
        """Keyword visitor
        AST abstract grammar:
            keyword = (identifier? arg, expr value)
        """

        return node.arg, self.visit(node.value)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        value = self.visit(node.value)
        attr_name = node.attr
        if not isinstance(value, list):
            return [value, attr_name]
        return [*value, attr_name]

    # statement
    def visit_Assign(self, node: ast.Assign) -> Any:
        assert len(node.targets) == 1, "assigning multiple var at the same time is not supported"
        target = node.targets[0]
        id = self.visit(target)
        value = self.visit(node.value)

        if isinstance(target, ast.Attribute) and id[0] not in self.scope_arrays:
            raise SyntaxError(f"assigning value to variable {id[0]} which is not in this scope")

        if isinstance(target, ast.Name):
            pass
        raise NotImplementedError("visit_Assign is not Implemented")

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        pass

    def visit_AugAssign(self, node: ast.AugAssign) -> Any:
        pass

    # control flow

    def visit_If(self, node: ast.If) -> Any:
        pass

    def visit_For(self, node: ast.For) -> Any:
        pass

    def visit_Return(self, node: ast.Return) -> Any:
        # for now kernel does not return anything.
        if node.value is None:
            rt_expr = _type_rel.smart_adapt_to(_ir.NoneExpr(), self.context.func_ret_type)
            return _ir.ReturnStmt(rt_expr)
        span = self.build_span(node)
        rt_expr = self.visit(node.value)
        if isinstance(rt_expr, tuple):
            raise SyntaxError("returning tuple is not support")
        # todo return type conversion
        return _ir.ReturnStmt(None, span)

    def _get_type(self, operand):
        if isinstance(operand, str) and operand in self.kernel_p.args.keys():
            result = self.kernel_p.args[operand]
        # elif isinstance(operand, str) and operand in self.scope_arrays:
        #    result = type(self.scope_arrays[operand])
        # elif isinstance(operand, tuple(dtypes.DTYPE_TO_TYPECLASS.keys())):
        #    if isinstance(operand, (bool, numpy.bool_)):
        #        result.append((operand, 'BoolConstant'))
        #    else:
        #        result.append((operand, 'NumConstant'))
        # elif isinstance(operand, sympy.Basic):
        #    result.append((operand, 'symbol'))
        else:
            raise SyntaxError("unable to find the type of", operand)
            # result = type(operand)
        return result